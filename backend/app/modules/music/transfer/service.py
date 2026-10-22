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


def _existing_catalog(db: Session, tracks: list[SourceTrack]) -> dict[str, CatalogTrack]:
    """Catalog entries the export already has, under the same aliases the parser uses for deduplication."""
    found: dict[str, CatalogTrack] = {}
    apple_ids = [track.apple_id for track in tracks if track.apple_id]
    for chunk in _chunks(apple_ids):
        for item in db.scalars(select(CatalogTrack).where(CatalogTrack.apple_track_id.in_(chunk))):
            found[f"apple:{item.apple_track_id}"] = item
    for chunk in _chunks([track.isrc for track in tracks if track.isrc]):
        for item in db.scalars(select(CatalogTrack).where(CatalogTrack.isrc.in_(chunk))):
            found.setdefault(f"isrc:{item.isrc}", item)
    services: dict[str, list[str]] = {}
    for track in tracks:
        if track.service and track.service_id:
            services.setdefault(track.service, []).append(track.service_id)
    for service, ids in services.items():
        for chunk in _chunks(ids):
            for item in db.scalars(
                select(CatalogTrack).where(
                    CatalogTrack.source_service == service, CatalogTrack.source_track_id.in_(chunk)
                )
            ):
                found[f"{service}:{item.source_track_id}"] = item
    for chunk in _chunks(list({normalize_identity(track.title) for track in tracks})):
        for item in db.scalars(select(CatalogTrack).where(CatalogTrack.normalized_title.in_(chunk))):
            found.setdefault(f"name:{item.normalized_artist}|{item.normalized_title}", item)
    return found


def _match(found: dict[str, CatalogTrack], source: SourceTrack) -> CatalogTrack | None:
    if source.apple_id:
        # Two different Apple ids are two different recordings even when they share a title.
        return found.get(f"apple:{source.apple_id}") or (found.get(f"isrc:{source.isrc}") if source.isrc else None)
    aliases = [source.key]
    if source.isrc:
        aliases.append(f"isrc:{source.isrc}")
    aliases.append(f"name:{normalize_identity(source.artist)}|{normalize_identity(source.title)}")
    return next((found[alias] for alias in aliases if alias in found), None)


def import_library(db: Session, job: TransferJob, parsed: ParsedLibrary) -> dict[str, CatalogTrack]:
    """Adds unknown tracks to the catalog. Never removes or rewrites existing entries."""
    found = _existing_catalog(db, parsed.tracks)
    resolved: dict[str, CatalogTrack] = {}
    added = existing = 0
    for source in parsed.tracks:
        catalog_track = _match(found, source)
        if catalog_track is not None:
            existing += 1
        else:
            catalog_track = CatalogTrack(
                apple_track_id=source.apple_id,
                source_service=source.service,
                source_track_id=source.service_id,
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
            added += 1
        for alias in (
            source.key,
            f"apple:{source.apple_id}" if source.apple_id else None,
            f"isrc:{source.isrc}" if source.isrc else None,
            f"name:{catalog_track.normalized_artist}|{catalog_track.normalized_title}",
        ):
            if alias:
                found.setdefault(alias, catalog_track)
        resolved[source.key] = catalog_track
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
    for name, keys in playlists.items():
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
        for key in keys:
            catalog_track = resolved.get(key)
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
    # Music sessions do not autoflush: without this the count misses statuses set just before.
    db.flush()
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
