"""Matching local files to catalog tracks: ISRC first, then artist + title + duration."""

import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.music.metadata import normalize_identity
from app.modules.music.models import CatalogTrack, Track

logger = logging.getLogger(__name__)

DURATION_TOLERANCE_MS = 2000


@dataclass(slots=True)
class CatalogMatch:
    """An unambiguous match, or candidates for a manual choice (never linked automatically)."""

    catalog_track: CatalogTrack | None = None
    candidates: list[CatalogTrack] = field(default_factory=list)


def _without_file():
    return ~select(Track.id).where(Track.catalog_track_id == CatalogTrack.id).correlate(CatalogTrack).exists()


def find_catalog_match(
    db: Session,
    *,
    isrc: str | None,
    artist: str,
    title: str,
    duration_seconds: float,
) -> CatalogMatch:
    free = _without_file()
    if isrc:
        by_isrc = db.scalars(select(CatalogTrack).where(CatalogTrack.isrc == isrc, free)).all()
        if len(by_isrc) == 1:
            return CatalogMatch(catalog_track=by_isrc[0])
        if by_isrc:
            return CatalogMatch(candidates=list(by_isrc))

    same_name = db.scalars(
        select(CatalogTrack)
        .where(
            CatalogTrack.normalized_artist == normalize_identity(artist),
            CatalogTrack.normalized_title == normalize_identity(title),
            free,
        )
        .order_by(CatalogTrack.created_at)
    ).all()
    duration_ms = duration_seconds * 1000
    if duration_ms <= 0:
        return CatalogMatch(candidates=list(same_name))
    close = [
        item for item in same_name if item.duration_ms and abs(item.duration_ms - duration_ms) <= DURATION_TOLERANCE_MS
    ]
    unknown = [item for item in same_name if not item.duration_ms]
    if len(close) == 1 and not unknown:
        return CatalogMatch(catalog_track=close[0])
    return CatalogMatch(candidates=close + unknown)


def match_for_track(db: Session, track: Track) -> CatalogMatch:
    return find_catalog_match(
        db,
        isrc=track.isrc,
        artist=track.artist.name,
        title=track.title,
        duration_seconds=track.duration,
    )


def auto_link(db: Session, track: Track) -> CatalogMatch:
    """Links an unlinked file when exactly one catalog track fits; the caller commits."""
    if track.catalog_track_id is not None:
        return CatalogMatch(catalog_track=track.catalog_track)
    match = match_for_track(db, track)
    if match.catalog_track is not None:
        track.catalog_track_id = match.catalog_track.id
        db.flush()
    return match


def link_imported_file(db: Session, track: Track) -> CatalogMatch:
    """auto_link for a freshly imported file: commits, and never fails the import itself."""
    try:
        match = auto_link(db, track)
        db.commit()
        return match
    except Exception:
        db.rollback()
        logger.exception("Catalog matching failed for track %s", track.id)
        return CatalogMatch()
