"""Background enrichment of catalog tracks through iTunes lookup.

All progress lives in the database: a job is claimed with a heartbeat, so after a restart (or a
crashed worker) the job is picked up again and only still-pending tracks are looked up.
"""

import logging
import threading
import time
import uuid
from collections.abc import Callable
from datetime import timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.security import utcnow
from app.database.session import MusicSessionLocal
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
        """Processes enriching jobs until none are left."""
        while True:
            with self.session_factory() as db:
                job_ids = db.scalars(
                    select(TransferJob.id).where(TransferJob.status == "enriching").order_by(TransferJob.created_at)
                ).all()
            if not job_ids:
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
                batch = db.scalars(
                    select(CatalogTrack)
                    .where(CatalogTrack.transfer_job_id == job_id, CatalogTrack.enrich_status == "pending")
                    .order_by(CatalogTrack.created_at, CatalogTrack.id)
                    .limit(LOOKUP_BATCH_SIZE)
                ).all()
                if not batch:
                    finish_job(db, job)
                    db.commit()
                    return
                if not self.settings.itunes_lookup_enabled:
                    for item in batch:
                        item.enrich_status = "error"
                        item.enriched_at = utcnow()
                    job.error_message = "Поиск в Apple Music отключён в настройках сервера"
                    finish_job(db, job)
                    db.commit()
                    return
                storefronts = [value for value in job.storefronts.split(",") if value]
                ids = [item.apple_track_id for item in batch]
            found, failed = self.lookup(job_id, ids, storefronts)
            if failed is None:
                return
            with self.session_factory() as db:
                job = self._owned_job(db, job_id)
                if job is None:
                    return
                tracks = db.scalars(
                    select(CatalogTrack).where(
                        CatalogTrack.apple_track_id.in_(ids), CatalogTrack.enrich_status == "pending"
                    )
                ).all()
                now = utcnow()
                for item in tracks:
                    result = found.get(item.apple_track_id)
                    if result is not None:
                        storefront, payload = result
                        apply_lookup(item, payload, storefront)
                        item.enrich_status = "enriched"
                        item.enriched_at = now
                    elif failed:
                        item.enrich_attempts += 1
                        if item.enrich_attempts >= MAX_ATTEMPTS:
                            item.enrich_status = "error"
                            item.enriched_at = now
                    else:
                        item.enrich_status = "not_found"
                        item.enriched_at = now
                refresh_counters(db, job)
                job.heartbeat_at = now
                db.commit()

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
    except Exception:
        logger.info("Music transfer jobs are not available yet")
        return
    if pending:
        ensure_worker()
