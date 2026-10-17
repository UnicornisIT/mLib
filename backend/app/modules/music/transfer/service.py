from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import utcnow
from app.modules.music.metadata import normalize_identity
from app.modules.music.models import CatalogTrack, Playlist, PlaylistTrack, TransferJob
from app.modules.music.transfer.sources import ParsedLibrary, SourceTrack

ACTIVE_STATUSES = {"queued", "enriching"}
LOOKUP_CHUNK = 500


def _chunks(values: list[str], size: int = LOOKUP_CHUNK):
    for start in range(0, len(values), size):
        yield values[start : start + size]


def _existing_catalog(
    db: Session, tracks: list[SourceTrack]
) -> tuple[dict[str, CatalogTrack], dict[str, CatalogTrack]]:
    by_external: dict[str, CatalogTrack] = {}
    by_isrc: dict[str, CatalogTrack] = {}
    for chunk in _chunks([track.external_id for track in tracks]):
        for item in db.scalars(select(CatalogTrack).where(CatalogTrack.apple_track_id.in_(chunk))):
            by_external[item.apple_track_id] = item
    for chunk in _chunks([track.isrc for track in tracks if track.isrc]):
        for item in db.scalars(select(CatalogTrack).where(CatalogTrack.isrc.in_(chunk))):
            by_isrc.setdefault(item.isrc or "", item)
    return by_external, by_isrc


def import_library(db: Session, job: TransferJob, parsed: ParsedLibrary) -> dict[str, CatalogTrack]:
    """Adds unknown tracks to the catalog. Never removes or rewrites existing entries."""
    by_external, by_isrc = _existing_catalog(db, parsed.tracks)
    resolved: dict[str, CatalogTrack] = {}
    added = existing = 0
    for source in parsed.tracks:
        catalog_track = by_external.get(source.external_id) or (by_isrc.get(source.isrc) if source.isrc else None)
        if catalog_track is not None:
            existing += 1
        else:
            catalog_track = CatalogTrack(
                apple_track_id=source.external_id,
                isrc=source.isrc,
                title=source.title,
                artist_name=source.artist,
                album_title=source.album,
                normalized_title=normalize_identity(source.title),
                normalized_artist=normalize_identity(source.artist),
                source=job.source,
                transfer_job_id=job.id,
                enrich_status="pending",
            )
            db.add(catalog_track)
            by_external[source.external_id] = catalog_track
            if source.isrc:
                by_isrc[source.isrc] = catalog_track
            added += 1
        resolved[source.external_id] = catalog_track
    job.rows_total = parsed.rows_total
    job.unique_total = len(parsed.tracks)
    job.added = added
    job.existing = existing
    job.invalid_rows = parsed.invalid_rows
    job.errors = parsed.invalid_rows
    db.flush()
    return resolved


def import_playlists(
    db: Session, owner_id: str, playlists: dict[str, list[str]], resolved: dict[str, CatalogTrack]
) -> list[str]:
    """Creates (or extends) one playlist per "Playlist name"; entries already present are kept once."""
    touched: list[str] = []
    for name, external_ids in playlists.items():
        playlist = db.scalar(
            select(Playlist).where(Playlist.owner_id == owner_id, Playlist.name == name, Playlist.is_system.is_(False))
        )
        if playlist is None:
            playlist = Playlist(owner_id=owner_id, name=name[:255])
            db.add(playlist)
            db.flush()
        present = {item.catalog_track_id for item in playlist.items if item.catalog_track_id}
        present |= {
            item.track.catalog_track_id for item in playlist.items if item.track and item.track.catalog_track_id
        }
        position = max((item.position for item in playlist.items), default=-1) + 1
        for external_id in external_ids:
            catalog_track = resolved.get(external_id)
            if catalog_track is None or catalog_track.id in present:
                continue
            db.add(PlaylistTrack(playlist_id=playlist.id, catalog_track_id=catalog_track.id, position=position))
            present.add(catalog_track.id)
            position += 1
        playlist.updated_at = utcnow()
        touched.append(playlist.name)
    db.flush()
    return touched


def refresh_counters(db: Session, job: TransferJob) -> None:
    rows = db.execute(
        select(CatalogTrack.enrich_status, func.count(CatalogTrack.id))
        .where(CatalogTrack.transfer_job_id == job.id)
        .group_by(CatalogTrack.enrich_status)
    ).all()
    counts = {status: int(count) for status, count in rows}
    job.enriched = counts.get("enriched", 0)
    job.not_found = counts.get("not_found", 0)
    job.errors = job.invalid_rows + counts.get("error", 0)


def pending_count(db: Session, job_id: str) -> int:
    return int(
        db.scalar(
            select(func.count(CatalogTrack.id)).where(
                CatalogTrack.transfer_job_id == job_id, CatalogTrack.enrich_status == "pending"
            )
        )
        or 0
    )


def finish_job(db: Session, job: TransferJob, status: str = "completed") -> None:
    refresh_counters(db, job)
    job.status = status
    job.worker_token = None
    job.finished_at = utcnow()
