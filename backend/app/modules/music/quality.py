from typing import Literal

from sqlalchemy import and_, func, or_

from app.modules.music.models import Artist, Track

MetadataIssue = Literal["missing_title", "unknown_artist", "missing_album", "missing_genre", "missing_year"]
MetadataStatus = Literal["complete", "incomplete", "critical", "reviewed"]

UNKNOWN_TITLES = {
    "без названия",
    "неизвестный трек",
    "track",
    "unknown",
    "unknown title",
    "untitled",
}
UNKNOWN_ARTISTS = {
    "без исполнителя",
    "неизвестен",
    "неизвестный артист",
    "неизвестный исполнитель",
    "ingen",
    "n/a",
    "no artist",
    "none",
    "unknown",
    "unknown artist",
}


def _normalized(value: str | None) -> str:
    return " ".join((value or "").split()).casefold()


def metadata_issues(track: Track) -> list[MetadataIssue]:
    issues: list[MetadataIssue] = []
    if track.title_from_filename or _normalized(track.title) in UNKNOWN_TITLES:
        issues.append("missing_title")
    if track.artist_from_fallback or _normalized(track.artist.name if track.artist else None) in UNKNOWN_ARTISTS:
        issues.append("unknown_artist")
    if track.album_id is None:
        issues.append("missing_album")
    if not _normalized(track.genre):
        issues.append("missing_genre")
    if track.year is None:
        issues.append("missing_year")
    return issues


def attention_status(track: Track, issues: list[MetadataIssue] | None = None) -> MetadataStatus:
    issues = issues if issues is not None else metadata_issues(track)
    critical = "missing_title" in issues or "unknown_artist" in issues
    incomplete_count = sum(issue in {"missing_album", "missing_genre", "missing_year"} for issue in issues)
    if track.metadata_reviewed_at is not None and (critical or incomplete_count >= 2):
        return "reviewed"
    if critical:
        return "critical"
    if incomplete_count >= 2:
        return "incomplete"
    return "complete"


def needs_attention(track: Track, issues: list[MetadataIssue] | None = None) -> bool:
    return attention_status(track, issues) in {"critical", "incomplete"}


def attention_filter():
    title = func.lower(func.trim(Track.title))
    artist = func.lower(func.trim(Artist.name))
    missing_genre = or_(Track.genre.is_(None), func.trim(Track.genre) == "")
    incomplete = or_(
        and_(Track.album_id.is_(None), missing_genre),
        and_(Track.album_id.is_(None), Track.year.is_(None)),
        and_(missing_genre, Track.year.is_(None)),
    )
    critical = or_(
        Track.title_from_filename.is_(True),
        Track.artist_from_fallback.is_(True),
        title.in_(UNKNOWN_TITLES),
        artist.in_(UNKNOWN_ARTISTS),
    )
    return and_(Track.metadata_reviewed_at.is_(None), or_(critical, incomplete))
