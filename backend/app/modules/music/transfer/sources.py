"""Parsers for library exports made with TuneMyMusic (tunemymusic.com) or written by hand.

TuneMyMusic writes every source service to the same CSV layout: "Track name", "Artist name", "Album",
"Playlist name", "Type", "ISRC" and one id column named after the source ("Apple - id", "Spotify - id",
"YouTube Music - id", "Deezer - id", ...). Its text export and free-text input use "Artist - Title" lines.
"""

import csv
import io
import re
from dataclasses import dataclass, field
from typing import Protocol

from app.modules.music.metadata import normalize_identity

MAX_SOURCE_BYTES = 20 * 1024 * 1024
ISRC_PATTERN = re.compile(r"[A-Z]{2}[A-Z0-9]{3}\d{7}")
DASHES = "‐‑‒–—―"
FAVORITES_PLAYLIST = "Любимые треки"
TEXT_SEPARATOR = re.compile(r"\s+[-‐‑‒–—―]\s+")
TEXT_NUMBERING = re.compile(r"^\s*\d+\s*[.)]\s*")

# Source services as TuneMyMusic names them in "<Service> - id"; unknown names keep a slug of their own.
SERVICES = {
    "apple": "apple_music",
    "apple music": "apple_music",
    "itunes": "apple_music",
    "spotify": "spotify",
    "youtube": "youtube",
    "youtube music": "youtube_music",
    "deezer": "deezer",
    "tidal": "tidal",
    "amazon": "amazon_music",
    "amazon music": "amazon_music",
    "soundcloud": "soundcloud",
    "yandex": "yandex_music",
    "yandex music": "yandex_music",
    "qobuz": "qobuz",
    "beatport": "beatport",
    "beatsource": "beatsource",
    "pandora": "pandora",
    "anghami": "anghami",
    "kkbox": "kkbox",
    "napster": "napster",
    "boomplay": "boomplay",
    "soundmachine": "soundmachine",
    "last.fm": "lastfm",
    "lastfm": "lastfm",
}
FAVORITE_TYPES = {"favorite", "favorites", "favourite", "liked", "liked songs", "library"}


class LibraryParseError(ValueError):
    """Raised with a user-facing Russian message when an export cannot be imported."""


@dataclass(frozen=True, slots=True)
class SourceTrack:
    # Identity of the track inside one export: Apple id, source service id, ISRC or artist and title.
    key: str
    title: str
    artist: str
    album: str | None
    isrc: str | None
    apple_id: str | None = None
    service: str | None = None
    service_id: str | None = None


@dataclass(slots=True)
class ParsedLibrary:
    # Service the export came from ("spotify", "apple_music", ...), "text" for "Artist - Title" lists.
    source: str = "unknown"
    rows_total: int = 0
    invalid_rows: int = 0
    tracks: list[SourceTrack] = field(default_factory=list)
    # Playlist name -> keys of deduplicated tracks, in export order.
    playlists: dict[str, list[str]] = field(default_factory=dict)


class LibrarySource(Protocol):
    """A parser for one kind of library export."""

    name: str
    label: str

    def parse(self, data: bytes, filename: str = "") -> ParsedLibrary: ...


def normalize_isrc(value: str | None) -> str | None:
    text = re.sub(r"[\s-]+", "", value or "").upper()
    return text if ISRC_PATTERN.fullmatch(text) else None


def _column_key(value: str) -> str:
    text = value.replace("﻿", "")
    for dash in DASHES:
        text = text.replace(dash, "-")
    return re.sub(r"[\s_\-]+", " ", text).strip().casefold()


def decode_text(data: bytes) -> str:
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8", errors="replace")
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp1251")


def service_slug(name: str) -> str:
    key = " ".join(name.casefold().split())
    return SERVICES.get(key) or re.sub(r"[^a-z0-9]+", "_", key).strip("_") or "unknown"


class _Collector:
    """Deduplicates tracks of one export and keeps playlist membership."""

    def __init__(self, parsed: ParsedLibrary) -> None:
        self.parsed = parsed
        self.by_key: dict[str, str] = {}

    def add(self, track: SourceTrack, playlist: str | None) -> None:
        aliases = [track.key]
        if track.isrc:
            aliases.append(f"isrc:{track.isrc}")
        aliases.append(f"name:{normalize_identity(track.artist)}|{normalize_identity(track.title)}")
        kept = next((self.by_key[alias] for alias in aliases if alias in self.by_key), None)
        if kept is None:
            kept = track.key
            self.parsed.tracks.append(track)
        for alias in aliases:
            self.by_key.setdefault(alias, kept)
        if playlist:
            members = self.parsed.playlists.setdefault(playlist, [])
            if kept not in members:
                members.append(kept)


class TuneMyMusicSource:
    """CSV of any TuneMyMusic source service, or a text list of "Artist - Title" lines."""

    name = "tunemymusic"
    label = "TuneMyMusic (CSV или TXT)"

    def parse(self, data: bytes, filename: str = "") -> ParsedLibrary:
        if len(data) > MAX_SOURCE_BYTES:
            raise LibraryParseError("Файл слишком большой: экспорт фонотеки должен быть меньше 20 МБ")
        text = decode_text(data).lstrip("﻿")
        if not text.strip():
            raise LibraryParseError("Файл пустой")
        header_line = text.lstrip().splitlines()[0]
        delimiter = max(",;\t", key=header_line.count)
        header = [_column_key(value) for value in next(csv.reader([header_line], delimiter=delimiter))]
        if "track name" in header or "artist name" in header:
            parsed = self._parse_csv(text, delimiter)
        elif filename.lower().endswith(".txt") or not header_line.count(delimiter):
            parsed = self._parse_text(text)
        else:
            raise LibraryParseError(
                "Это не похоже на экспорт TuneMyMusic: в файле нет обязательных колонок «Track name», «Artist name»"
            )
        if parsed.rows_total == 0:
            raise LibraryParseError("В файле нет ни одной строки с треками")
        if not parsed.tracks:
            raise LibraryParseError("Ни в одной строке нет названия трека и исполнителя")
        return parsed

    def _parse_csv(self, text: str, delimiter: str) -> ParsedLibrary:
        try:
            rows = list(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter))
        except csv.Error as exc:
            raise LibraryParseError(f"Не удалось прочитать CSV: {exc}") from exc
        header = [_column_key(value) for value in rows[0]]
        missing = [f"«{name}»" for name in ("Track name", "Artist name") if _column_key(name) not in header]
        if missing:
            raise LibraryParseError(
                "Это не похоже на экспорт TuneMyMusic: в файле нет обязательных колонок " + ", ".join(missing)
            )

        def position(*names: str) -> int | None:
            return next((header.index(name) for name in names if name in header), None)

        title_at, artist_at = header.index("track name"), header.index("artist name")
        album_at = position("album", "album name")
        playlist_at = position("playlist name", "playlist")
        type_at = position("type")
        isrc_at = position("isrc")
        id_columns = [(index, name[: -len(" id")]) for index, name in enumerate(header) if name.endswith(" id")]
        # An Apple id lets the background lookup skip the slower search; other ids identify the track.
        id_columns.sort(key=lambda column: service_slug(column[1]) != "apple_music")
        parsed = ParsedLibrary(source=service_slug(id_columns[0][1]) if id_columns else "unknown")
        collector = _Collector(parsed)
        for row in rows[1:]:
            if not any(cell.strip() for cell in row):
                continue
            parsed.rows_total += 1

            def cell(at: int | None, row: list[str] = row) -> str:
                return " ".join(row[at].split()) if at is not None and at < len(row) else ""

            title, artist = cell(title_at), cell(artist_at)
            if not title or not artist:
                parsed.invalid_rows += 1
                continue
            isrc = normalize_isrc(cell(isrc_at))
            apple_id = service = service_id = None
            for at, name in id_columns:
                value = cell(at)
                slug = service_slug(name)
                if slug == "apple_music" and value.isdigit():
                    apple_id = value
                elif value and service is None and slug != "apple_music":
                    service, service_id = slug, value[:128]
            if apple_id:
                key = f"apple:{apple_id}"
            elif service_id:
                key = f"{service}:{service_id}"
            elif isrc:
                key = f"isrc:{isrc}"
            else:
                key = f"name:{normalize_identity(artist)}|{normalize_identity(title)}"
            playlist = cell(playlist_at)
            if not playlist and _column_key(cell(type_at)) in FAVORITE_TYPES:
                playlist = FAVORITES_PLAYLIST
            collector.add(
                SourceTrack(
                    key=key,
                    title=title,
                    artist=artist,
                    album=cell(album_at) or None,
                    isrc=isrc,
                    apple_id=apple_id,
                    service=service,
                    service_id=service_id,
                ),
                playlist or None,
            )
        return parsed

    def _parse_text(self, text: str) -> ParsedLibrary:
        parsed = ParsedLibrary(source="text")
        collector = _Collector(parsed)
        for line in text.splitlines():
            value = TEXT_NUMBERING.sub("", " ".join(line.split()))
            if not value:
                continue
            parsed.rows_total += 1
            parts = TEXT_SEPARATOR.split(value, maxsplit=1)
            if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
                parsed.invalid_rows += 1
                continue
            artist, title = parts[0].strip(), parts[1].strip()
            collector.add(
                SourceTrack(
                    key=f"name:{normalize_identity(artist)}|{normalize_identity(title)}",
                    title=title,
                    artist=artist,
                    album=None,
                    isrc=None,
                ),
                None,
            )
        return parsed


SOURCES: dict[str, LibrarySource] = {TuneMyMusicSource.name: TuneMyMusicSource()}
