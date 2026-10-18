"""Background enrichment of catalog tracks through iTunes lookup.

All progress lives in the database: a job is claimed with a heartbeat, so after a restart (or a
crashed worker) the job is picked up again and only still-pending tracks are looked up.
"""

import logging
import re
import threading
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.security import utcnow
from app.database.session import MusicSessionLocal
from app.modules.music.library import credited_artists
from app.modules.music.metadata import normalize_identity
from app.modules.music.models import CatalogTrack, TransferJob
from app.modules.music.transfer.itunes import (
    LOOKUP_BATCH_SIZE,
    ItunesLookupClient,
    LookupRateLimitedError,
    TrackLookupClient,
    TrackLookupError,
    catalog_values,
)
from app.modules.music.transfer.service import finish_job, refresh_counters

logger = logging.getLogger(__name__)

REQUEST_INTERVAL_SECONDS = 3.0
# Apple allows about 20 searches a minute.
SEARCH_INTERVAL_SECONDS = 3.5
SEARCH_BATCH_SIZE = 10
TITLE_NOISE = re.compile(
    r"\s*[(\[][^)\]]*\b(feat|ft|with|remaster(ed)?|version|explicit|radio edit|edit|mono|stereo|bonus)\b[^)\]]*[)\]]"
    r"|\s+-\s+.*\b(remaster(ed)?|version|edit|mix)\b.*$",
    re.IGNORECASE,
)
RATE_LIMIT_BACKOFF_SECONDS = 60.0
HEARTBEAT_TIMEOUT = timedelta(seconds=90)
MAX_ATTEMPTS = 3
BUSY_WAIT_SECONDS = 30.0


class TransferWorker:
    def __init__(
        self,
        client: TrackLookupClient | None = None,
        settings: Settings | None = None,
        session_factory: sessionmaker[Session] = MusicSessionLocal,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client or ItunesLookupClient()
        self.session_factory = session_factory
        self.sleep = sleep
        self.token = str(uuid.uuid4())

    def run(self) -> None:
        """Processes enriching jobs until none are left, then fills in data older transfers did not keep."""
        while True:
            with self.session_factory() as db:
                job_ids = db.scalars(
                    select(TransferJob.id).where(TransferJob.status == "enriching").order_by(TransferJob.created_at)
                ).all()
            if not job_ids:
                self.backfill_genres()
                return
            claimed = next((job_id for job_id in job_ids if self.claim(job_id)), None)
            if claimed is None:
                # Another live worker owns every job; check back once its heartbeat may expire.
                self.sleep(BUSY_WAIT_SECONDS)
                continue
            try:
                self.process(claimed)
            except Exception as exc:
                logger.exception("Library transfer %s failed", claimed)
                with self.session_factory() as db:
                    job = db.get(TransferJob, claimed)
                    if job is not None and job.worker_token == self.token:
                        job.error_message = str(exc) or "Внутренняя ошибка обогащения"
                        finish_job(db, job, status="failed")
                        db.commit()

    def claim(self, job_id: str) -> bool:
        now = utcnow()
        with self.session_factory() as db:
            result = db.execute(
                update(TransferJob)
                .where(
                    TransferJob.id == job_id,
                    TransferJob.status == "enriching",
                    or_(
                        TransferJob.worker_token.is_(None),
                        TransferJob.worker_token == self.token,
                        TransferJob.heartbeat_at.is_(None),
                        TransferJob.heartbeat_at < now - HEARTBEAT_TIMEOUT,
                    ),
                )
                .values(worker_token=self.token, heartbeat_at=now)
            )
            db.commit()
            return result.rowcount == 1

    def _owned_job(self, db: Session, job_id: str) -> TransferJob | None:
        job = db.get(TransferJob, job_id)
        if job is None or job.status != "enriching" or job.worker_token != self.token:
            return None
        return job

    def process(self, job_id: str) -> None:
        while True:
            with self.session_factory() as db:
                job = self._owned_job(db, job_id)
                if job is None:
                    return
                pending = (CatalogTrack.transfer_job_id == job_id, CatalogTrack.enrich_status == "pending")
                if not self.settings.itunes_lookup_enabled:
                    now = utcnow()
                    for item in db.scalars(select(CatalogTrack).where(*pending)):
                        item.enrich_status = "error"
                        item.enriched_at = now
                    job.error_message = "Поиск в Apple Music отключён в настройках сервера"
                    finish_job(db, job)
                    db.commit()
                    return
                storefronts = [value for value in job.storefronts.split(",") if value]
                ids = list(
                    db.scalars(
                        select(CatalogTrack.apple_track_id)
                        .where(*pending, CatalogTrack.apple_track_id.is_not(None))
                        .order_by(CatalogTrack.created_at, CatalogTrack.id)
                        .limit(LOOKUP_BATCH_SIZE)
                    ).all()
                )
                searches = []
                if not ids:
                    searches = list(
                        db.execute(
                            select(CatalogTrack.id, CatalogTrack.artist_name, CatalogTrack.title)
                            .where(*pending, CatalogTrack.apple_track_id.is_(None))
                            .order_by(CatalogTrack.created_at, CatalogTrack.id)
                            .limit(SEARCH_BATCH_SIZE)
                        ).all()
                    )
                    if not searches:
                        finish_job(db, job)
                        db.commit()
                        return
            if ids:
                if not self.process_lookup(job_id, ids, storefronts):
                    return
                continue
            for catalog_id, artist, title in searches:
                if not self.process_search(job_id, catalog_id, artist, title, storefronts):
                    return

    def process_lookup(self, job_id: str, ids: list[str], storefronts: list[str]) -> bool:
        """Apple Music exports carry Apple ids: up to 100 tracks per request."""
        found, failed = self.lookup(job_id, ids, storefronts)
        if failed is None:
            return False
        with self.session_factory() as db:
            job = self._owned_job(db, job_id)
            if job is None:
                return False
            tracks = db.scalars(
                select(CatalogTrack).where(
                    CatalogTrack.apple_track_id.in_(ids), CatalogTrack.enrich_status == "pending"
                )
            ).all()
            now = utcnow()
            for item in tracks:
                result = found.get(item.apple_track_id or "")
                if result is not None:
                    storefront, payload = result
                    apply_lookup(item, payload, storefront)
                    item.enrich_status = "enriched"
                    item.enriched_at = now
                else:
                    mark_missing(item, failed, now)
            refresh_counters(db, job)
            job.heartbeat_at = now
            db.commit()
        return True

    def process_search(self, job_id: str, catalog_id: str, artist: str, title: str, storefronts: list[str]) -> bool:
        """Other services only give artist and title: one search per track, checked strictly."""
        found: tuple[str, dict] | None = None
        failed = False
        for storefront in storefronts:
            results = None
            for attempt in range(1, MAX_ATTEMPTS + 1):
                if not self.heartbeat(job_id):
                    return False
                try:
                    results = self.client.search(f"{artist} {title}", storefront)
                    break
                except LookupRateLimitedError:
                    self.sleep(RATE_LIMIT_BACKOFF_SECONDS * attempt)
                except TrackLookupError:
                    self.sleep(SEARCH_INTERVAL_SECONDS * attempt)
            self.sleep(SEARCH_INTERVAL_SECONDS)
            if results is None:
                failed = True
                continue
            payload = best_search_match(results, artist, title)
            if payload is not None:
                found = (storefront, payload)
                break
        with self.session_factory() as db:
            job = self._owned_job(db, job_id)
            item = db.get(CatalogTrack, catalog_id)
            if job is None:
                return False
            if item is None or item.enrich_status != "pending":
                return True
            now = utcnow()
            if found is not None:
                storefront, payload = found
                apple_id = str(payload["trackId"])
                # The same recording may already be in the catalog from another export: keep both, link one id.
                if db.scalar(select(CatalogTrack.id).where(CatalogTrack.apple_track_id == apple_id)) is None:
                    item.apple_track_id = apple_id
                apply_lookup(item, payload, storefront)
                item.enrich_status = "enriched"
                item.enriched_at = now
            else:
                mark_missing(item, failed, now)
            refresh_counters(db, job)
            job.heartbeat_at = now
            db.commit()
        return True

    def lookup(
        self, job_id: str, ids: list[str], storefronts: list[str]
    ) -> tuple[dict[str, tuple[str, dict]], bool | None]:
        """Looks ids up storefront by storefront. Returns (found, failed); failed=None means stop."""
        found: dict[str, tuple[str, dict]] = {}
        remaining = list(ids)
        for storefront in storefronts:
            if not remaining:
                break
            for attempt in range(1, MAX_ATTEMPTS + 1):
                if not self.heartbeat(job_id):
                    return found, None
                try:
                    results = self.client.lookup(remaining, storefront)
                    break
                except LookupRateLimitedError:
                    self.sleep(RATE_LIMIT_BACKOFF_SECONDS * attempt)
                except TrackLookupError:
                    self.sleep(REQUEST_INTERVAL_SECONDS * attempt)
            else:
                return found, True
            for track_id, payload in results.items():
                if track_id in remaining:
                    found[track_id] = (storefront, payload)
            remaining = [track_id for track_id in remaining if track_id not in found]
            self.sleep(REQUEST_INTERVAL_SECONDS)
        return found, False

    def backfill_genres(self) -> None:
        """Catalog tracks found before genres were kept get their Apple genre, 100 tracks per request."""
        if not self.settings.itunes_lookup_enabled:
            return
        fallback = (self.settings.itunes_storefronts or ["us"])[0]
        while True:
            with self.session_factory() as db:
                rows = db.execute(
                    select(CatalogTrack.apple_track_id, CatalogTrack.storefront)
                    .where(*missing_genre())
                    .order_by(CatalogTrack.storefront, CatalogTrack.id)
                    .limit(LOOKUP_BATCH_SIZE)
                ).all()
            if not rows:
                return
            storefront = rows[0][1] or fallback
            ids = [apple_id for apple_id, value in rows if (value or fallback) == storefront]
            try:
                found = self.client.lookup(ids, storefront)
            except TrackLookupError:
                logger.info("Genre backfill paused: Apple Music lookup is not available")
                return
            with self.session_factory() as db:
                for item in db.scalars(select(CatalogTrack).where(CatalogTrack.apple_track_id.in_(ids))):
                    payload = found.get(item.apple_track_id or "")
                    item.genre = catalog_values(payload).get("genre", "") if payload else ""
                db.commit()
            self.sleep(REQUEST_INTERVAL_SECONDS)

    def heartbeat(self, job_id: str) -> bool:
        with self.session_factory() as db:
            result = db.execute(
                update(TransferJob)
                .where(
                    TransferJob.id == job_id,
                    TransferJob.status == "enriching",
                    TransferJob.worker_token == self.token,
                )
                .values(heartbeat_at=utcnow())
            )
            db.commit()
            return result.rowcount == 1


def missing_genre():
    return (
        CatalogTrack.enrich_status == "enriched",
        CatalogTrack.apple_track_id.is_not(None),
        CatalogTrack.genre.is_(None),
    )


def mark_missing(item: CatalogTrack, failed: bool, now: datetime) -> None:
    if failed:
        item.enrich_attempts += 1
        if item.enrich_attempts >= MAX_ATTEMPTS:
            item.enrich_status = "error"
            item.enriched_at = now
    else:
        item.enrich_status = "not_found"
        item.enriched_at = now


def _clean_title(title: str) -> str:
    return normalize_identity(TITLE_NOISE.sub("", title))


def best_search_match(results: list[dict], artist: str, title: str) -> dict | None:
    """A search result by the same artist with the same title; "(feat. ...)" or "- Remastered" may differ."""
    artists = credited_artists(artist)
    wanted, wanted_clean = normalize_identity(title), _clean_title(title)
    close = None
    for result in results:
        if not artists & credited_artists(str(result.get("artistName") or "")):
            continue
        name = str(result.get("trackName") or "")
        if normalize_identity(name) == wanted:
            return result
        if close is None and wanted_clean and _clean_title(name) == wanted_clean:
            close = result
    return close


def apply_lookup(item: CatalogTrack, payload: dict, storefront: str) -> None:
    values = catalog_values(payload)
    for key, value in values.items():
        setattr(item, key, value)
    item.normalized_title = normalize_identity(item.title)
    item.normalized_artist = normalize_identity(item.artist_name)
    item.storefront = storefront


_worker_lock = threading.Lock()
_worker_thread: threading.Thread | None = None
_rerun_requested = False


def _run_worker() -> None:
    global _rerun_requested, _worker_thread
    while True:
        with _worker_lock:
            _rerun_requested = False
        try:
            TransferWorker().run()
        except Exception:
            logger.exception("Library transfer worker stopped")
        with _worker_lock:
            # A job queued while run() was finishing would otherwise wait for the next restart.
            if not _rerun_requested:
                _worker_thread = None
                return


def ensure_worker() -> None:
    """Starts the background worker unless it is already running in this process."""
    global _rerun_requested, _worker_thread
    with _worker_lock:
        _rerun_requested = True
        if _worker_thread is not None and _worker_thread.is_alive():
            return
        _worker_thread = threading.Thread(target=_run_worker, name="music-transfer", daemon=True)
        _worker_thread.start()


def resume_pending_jobs() -> None:
    """Called on startup: continues jobs interrupted by a shutdown."""
    try:
        with MusicSessionLocal() as db:
            pending = db.scalar(select(TransferJob.id).where(TransferJob.status == "enriching").limit(1))
            pending = pending or db.scalar(select(CatalogTrack.id).where(*missing_genre()).limit(1))
    except Exception:
        logger.info("Music transfer jobs are not available yet")
        return
    if pending:
        ensure_worker()
