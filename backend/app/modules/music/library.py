import logging
import math
import re
import uuid
from collections import Counter
from collections.abc import Sequence
from functools import partial
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings
from app.core.security import utcnow
from app.modules.music.artwork import save_artwork
from app.modules.music.metadata import NormalizedTrackMetadata, extract_metadata, normalize_identity
from app.modules.music.models import Album, Artist, CatalogTrack, Favorite, MusicSetting, Track
from app.modules.music.quality import attention_status, metadata_issues, needs_attention
from app.modules.music.schemas import (
    AlbumBrief,
    ArtistBrief,
    CatalogAlbumRead,
    CatalogTrackBrief,
    CatalogTrackRead,
    TrackRead,
)
from app.modules.music.transfer.itunes import sized_artwork_url, spotify_search_url
from app.storage.service import LocalMediaStorage, StagedFile

logger = logging.getLogger(__name__)


class DuplicateTrackError(ValueError):
    def __init__(self, track: Track) -> None:
        super().__init__("Этот файл уже находится в медиатеке")
        self.track = track


def track_query(user_id: str):
    return (
        select(Track)
        .options(selectinload(Track.artist), selectinload(Track.album), selectinload(Track.catalog_track))
        .add_columns(
            select(Favorite.track_id)
            .where(Favorite.track_id == Track.id, Favorite.user_id == user_id)
            .correlate(Track)
            .exists()
            .label("favorite")
        )
    )


def serialize_track(track: Track, favorite: bool = False) -> TrackRead:
    issues = metadata_issues(track)
    album = None
    if track.album:
        album = AlbumBrief(
            id=track.album.id,
            title=track.album.title,
            album_artist=track.album.album_artist,
            year=track.album.year,
            artwork_id=track.album.artwork_id,
        )
    return TrackRead(
        id=track.id,
        uuid=track.uuid,
        title=track.title,
        artist=ArtistBrief(id=track.artist.id, name=track.artist.name),
        album=album,
        album_artist=track.album_artist,
        genre=track.genre,
        year=track.year,
        track_number=track.track_number,
        disc_number=track.disc_number,
        composer=track.composer,
        copyright=track.copyright,
        comment=track.comment,
        duration=track.duration,
        file_size=track.file_size,
        format=track.format,
        codec=track.codec,
        bitrate=track.bitrate,
        sample_rate=track.sample_rate,
        channels=track.channels,
        artwork_id=track.artwork_id or (track.album.artwork_id if track.album else None),
        catalog=catalog_brief(track.catalog_track) if track.catalog_track else None,
        favorite=favorite,
        needs_attention=needs_attention(track, issues),
        metadata_status=attention_status(track, issues),
        metadata_issues=issues,
        play_count=track.play_count,
        last_played_at=track.last_played_at,
        date_added=track.date_added,
        date_modified=track.date_modified,
    )


def catalog_brief(item: CatalogTrack) -> CatalogTrackBrief:
    return CatalogTrackBrief(
        id=item.id,
        apple_track_id=item.apple_track_id,
        isrc=item.isrc,
        title=item.title,
        artist_name=item.artist_name,
        album_title=item.album_title,
        collection_id=item.collection_id,
        album_key=catalog_album_key(item),
        year=item.year,
        duration_ms=item.duration_ms,
        artwork_url=sized_artwork_url(item.artwork_url),
        apple_music_url=item.apple_url,
        spotify_url=spotify_search_url(item.artist_name, item.title),
    )


def serialize_catalog_track(item: CatalogTrack) -> CatalogTrackRead:
    track = item.track
    return CatalogTrackRead(
        **catalog_brief(item).model_dump(),
        enrich_status=item.enrich_status,
        has_file=track is not None,
        track_id=track.id if track else None,
        artwork_id=track.artwork_id if track else None,
    )


def lead_artist(names: list[str]) -> str:
    """Artist credited on most tracks: "Daft Punk & X" and "Daft Punk, Y" give "Daft Punk"."""
    unique = list(dict.fromkeys(names))
    if len(unique) <= 1:
        return unique[0] if unique else ""
    counts: Counter[str] = Counter()
    spelling: dict[str, str] = {}
    for name in names:
        for part in FEATURED_ARTIST.split(name):
            if part.strip():
                normalized = normalize_identity(part)
                spelling.setdefault(normalized, part.strip())
                counts[normalized] += 1
    artist, count = counts.most_common(1)[0]
    return spelling[artist] if count * 2 > len(names) else "Разные исполнители"


FEATURED_ARTIST = re.compile(r"\s*(?:,|&|\+|\bfeat\.?|\bft\.?|\bfeaturing\b|\bwith\b|\bx\b|\bи\b)\s*", re.IGNORECASE)


def primary_artist(name: str) -> str:
    """First credited artist: "Daft Punk, Pharrell Williams & Nile Rodgers" gives "Daft Punk"."""
    return FEATURED_ARTIST.split(name, maxsplit=1)[0].strip() or name


def credited_artists(name: str) -> set[str]:
    return {normalize_identity(part) for part in FEATURED_ARTIST.split(name) if part.strip()}


def catalog_album_key(item: CatalogTrack) -> str | None:
    """Album title and lead artist of a track; an album is found by the key of any of its tracks."""
    if not item.album_title:
        return None
    return f"{normalize_identity(item.album_title)}|{normalize_identity(primary_artist(item.artist_name))}"


def _union_root(parent: list[int], index: int) -> int:
    while parent[index] != index:
        parent[index] = parent[parent[index]]
        index = parent[index]
    return index


def catalog_album_groups(items: Sequence[CatalogTrack]) -> list[tuple[str, set[str], list[CatalogTrack]]]:
    """
    Tracks with the same album title form one album when they share a credited artist or an Apple album:
    editions of "Pieces of a Dream" and a soundtrack by many artists stay whole, while "Greatest Hits"
    of two different artists stays apart.
    """
    by_title: dict[str, list[CatalogTrack]] = {}
    for item in items:
        if item.album_title:
            by_title.setdefault(normalize_identity(item.album_title), []).append(item)
    groups = []
    for tracks in by_title.values():
        parent = list(range(len(tracks)))
        root = partial(_union_root, parent)
        seen: dict[str, int] = {}
        for index, item in enumerate(tracks):
            links = {f"artist:{artist}" for artist in credited_artists(item.artist_name)}
            if item.collection_id:
                links.add(f"apple:{item.collection_id}")
            for link in links:
                if link in seen:
                    parent[root(index)] = root(seen[link])
                else:
                    seen[link] = index
        components: dict[int, list[CatalogTrack]] = {}
        for index, item in enumerate(tracks):
            components.setdefault(root(index), []).append(item)
        for members in components.values():
            keys = {key for key in map(catalog_album_key, members) if key}
            groups.append((min(keys), keys, members))
    return groups


def group_catalog_albums(items: Sequence[CatalogTrack]) -> list[CatalogAlbumRead]:
    albums = []
    for key, _, tracks in catalog_album_groups(items):
        first = tracks[0]
        linked = [item.track for item in tracks if item.track is not None]
        with_art = next((track for track in linked if track.artwork_id), None)
        apple_art = next((item for item in tracks if item.artwork_url), None)
        years = [item.year for item in tracks if item.year]
        album_url = next((item.apple_url for item in tracks if item.apple_url), None)
        albums.append(
            CatalogAlbumRead(
                key=key,
                title=first.album_title or "",
                artist_name=lead_artist([item.artist_name for item in tracks]),
                year=min(years) if years else None,
                artwork_url=sized_artwork_url(apple_art.artwork_url) if apple_art else None,
                artwork_id=with_art.artwork_id if with_art else None,
                # Track links look like .../album/x/1?i=7001: without "i" the link opens the album.
                apple_music_url=album_url.split("?")[0] if album_url else None,
                track_count=len(tracks),
                with_file=len(linked),
                local_album_ids=sorted({track.album_id for track in linked if track.album_id}),
            )
        )
    return sorted(albums, key=lambda album: (album.artist_name.casefold(), album.title.casefold()))


def resolve_artist(db: Session, name: str) -> Artist:
    display_name = " ".join(name.split()).strip() or "Неизвестный исполнитель"
    normalized = normalize_identity(display_name)
    artist = db.scalar(select(Artist).where(Artist.normalized_name == normalized))
    if artist is None:
        artist = Artist(name=display_name, sort_name=display_name, normalized_name=normalized)
        db.add(artist)
        db.flush()
    return artist


def resolve_album(
    db: Session,
    metadata: NormalizedTrackMetadata,
    artwork_id: str | None,
) -> Album | None:
    if not metadata.album:
        return None
    normalized_title = normalize_identity(metadata.album)
    normalized_album_artist = normalize_identity(metadata.album_artist)
    album = db.scalar(
        select(Album).where(
            Album.normalized_title == normalized_title,
            Album.normalized_album_artist == normalized_album_artist,
        )
    )
    if album is None:
        album_artist = resolve_artist(db, metadata.album_artist)
        album = Album(
            title=" ".join(metadata.album.split()),
            normalized_title=normalized_title,
            artist_id=album_artist.id,
            album_artist=album_artist.name,
            normalized_album_artist=normalized_album_artist,
            year=metadata.year,
            genre=metadata.genre,
            artwork_id=artwork_id,
        )
        db.add(album)
        db.flush()
    elif album.artwork_id is None and artwork_id:
        album.artwork_id = artwork_id
    return album


def find_duplicate(db: Session, sha256: str, size: int) -> Track | None:
    return db.scalar(select(Track).where(Track.file_hash == sha256, Track.file_size == size))


def import_staged_file(
    db: Session,
    staged: StagedFile,
    storage: LocalMediaStorage,
    settings: Settings,
    source_path: str | None = None,
    catalog_track_id: str | None = None,
) -> Track:
    duplicate = find_duplicate(db, staged.sha256, staged.size)
    if duplicate:
        storage.discard(staged)
        raise DuplicateTrackError(duplicate)

    try:
        embedded_setting = db.get(MusicSetting, "embedded_metadata")
        use_embedded = embedded_setting is None or embedded_setting.value.lower() == "true"
        metadata = extract_metadata(staged.path, staged.original_name, settings, use_embedded=use_embedded)
    except Exception:
        storage.discard(staged)
        raise

    artwork = None
    if metadata.artwork:
        try:
            artwork = save_artwork(metadata.artwork, settings)
            db.add(artwork)
            db.flush()
        except ValueError as exc:
            logger.warning("Artwork skipped for %s: %s", staged.original_name, exc)

    track_uuid = str(uuid.uuid4())
    committed_path: Path | None = None
    try:
        artist = resolve_artist(db, metadata.artist)
        album = resolve_album(db, metadata, artwork.id if artwork else None)
        if artwork is None and album and album.artwork_id:
            artwork_id = album.artwork_id
        else:
            artwork_id = artwork.id if artwork else None
        committed_path = storage.commit(staged, track_uuid)
        relative_path = committed_path.relative_to(settings.media_root).as_posix()
        track = Track(
            uuid=track_uuid,
            title=metadata.title,
            artist_id=artist.id,
            album_id=album.id if album else None,
            album_artist=metadata.album_artist,
            genre=metadata.genre,
            year=metadata.year,
            track_number=metadata.track_number,
            disc_number=metadata.disc_number,
            composer=metadata.composer,
            copyright=metadata.copyright,
            comment=metadata.comment,
            duration=metadata.duration,
            file_path=relative_path,
            source_path=source_path,
            original_filename=staged.original_name,
            file_size=staged.size,
            file_hash=staged.sha256,
            format=metadata.format,
            isrc=metadata.isrc,
            catalog_track_id=catalog_track_id,
            codec=metadata.codec,
            bitrate=metadata.bitrate,
            sample_rate=metadata.sample_rate,
            channels=metadata.channels,
            artwork_id=artwork_id,
            title_from_filename=metadata.title_from_filename,
            artist_from_fallback=metadata.artist_from_fallback,
        )
        db.add(track)
        db.commit()
        return db.scalar(
            select(Track).where(Track.id == track.id).options(selectinload(Track.artist), selectinload(Track.album))
        )
    except Exception:
        db.rollback()
        if committed_path:
            committed_path.unlink(missing_ok=True)
        else:
            storage.discard(staged)
        raise


def update_track_metadata(db: Session, track: Track, values: dict[str, object]) -> Track:
    metadata_fields = {"title", "artist", "album", "album_artist", "genre", "year"}
    metadata_changed = bool(metadata_fields.intersection(values))
    if values.get("title"):
        track.title_from_filename = False
    if values.get("artist"):
        track.artist_from_fallback = False
    if artist_name := values.pop("artist", None):
        track.artist = resolve_artist(db, str(artist_name))
    album_title = values.pop("album", None)
    if album_title is not None:
        if album_title:
            metadata = NormalizedTrackMetadata(
                title=track.title,
                artist=track.artist.name,
                album_artist=str(values.get("album_artist") or track.album_artist or track.artist.name),
                album=str(album_title),
                genre=str(values.get("genre") or track.genre) if values.get("genre") or track.genre else None,
                year=int(values.get("year") or track.year) if values.get("year") or track.year else None,
                track_number=track.track_number,
                disc_number=track.disc_number,
                composer=track.composer,
                copyright=track.copyright,
                comment=track.comment,
                duration=track.duration,
                bitrate=track.bitrate,
                sample_rate=track.sample_rate,
                channels=track.channels,
                codec=track.codec,
                format=track.format,
                artwork=None,
            )
            track.album = resolve_album(db, metadata, track.artwork_id)
        else:
            track.album = None
    for key, value in values.items():
        setattr(track, key, value)
    if metadata_changed:
        track.metadata_reviewed_at = None
    track.date_modified = utcnow()
    db.commit()
    db.refresh(track)
    return track


def pagination(total: int, page: int, page_size: int) -> tuple[int, int, int]:
    pages = max(1, math.ceil(total / page_size))
    return (page - 1) * page_size, page_size, pages
