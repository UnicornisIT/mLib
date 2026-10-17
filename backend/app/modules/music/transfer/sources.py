import csv
import io
import re
from dataclasses import dataclass, field
from typing import Protocol

MAX_SOURCE_BYTES = 20 * 1024 * 1024
ISRC_PATTERN = re.compile(r"[A-Z]{2}[A-Z0-9]{3}\d{7}")


class LibraryParseError(ValueError):
    """Raised with a user-facing Russian message when an export cannot be imported."""


@dataclass(frozen=True, slots=True)
class SourceTrack:
    external_id: str
    title: str
    artist: str
    album: str | None
    isrc: str | None


@dataclass(slots=True)
class ParsedLibrary:
    rows_total: int = 0
    invalid_rows: int = 0
    tracks: list[SourceTrack] = field(default_factory=list)
    # Playlist name -> external ids of deduplicated tracks, in export order.
    playlists: dict[str, list[str]] = field(default_factory=dict)


class LibrarySource(Protocol):
    """A parser for one kind of library export."""

    name: str
    label: str

    def parse(self, data: bytes) -> ParsedLibrary: ...


def normalize_isrc(value: str | None) -> str | None:
    text = re.sub(r"[\s-]+", "", value or "").upper()
    return text if ISRC_PATTERN.fullmatch(text) else None


def _column_key(value: str) -> str:
    return re.sub(r"[\s_\-]+", " ", value.replace("﻿", "")).strip().casefold()


def decode_text(data: bytes) -> str:
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8", errors="replace")
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp1251")


class AppleMusicCsvSource:
    """Playlist export of an Apple Music library (Track name, Artist name, Album, ISRC, Apple - id)."""

    name = "apple_music_csv"
    label = "Apple Music (CSV)"
    columns = {
        "title": "Track name",
        "artist": "Artist name",
        "album": "Album",
        "isrc": "ISRC",
        "external_id": "Apple - id",
    }
    playlist_column = "Playlist name"

    def parse(self, data: bytes) -> ParsedLibrary:
        if len(data) > MAX_SOURCE_BYTES:
            raise LibraryParseError("Файл слишком большой: экспорт фонотеки должен быть меньше 20 МБ")
        text = decode_text(data).lstrip("﻿")
        if not text.strip():
            raise LibraryParseError("Файл пустой")
        header_line = text.splitlines()[0]
        delimiter = max(",;\t", key=header_line.count)
        try:
            rows = list(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter))
        except csv.Error as exc:
            raise LibraryParseError(f"Не удалось прочитать CSV: {exc}") from exc
        header = [_column_key(value) for value in rows[0]]
        positions: dict[str, int] = {}
        missing: list[str] = []
        for key, column in self.columns.items():
            if _column_key(column) in header:
                positions[key] = header.index(_column_key(column))
            else:
                missing.append(f"«{column}»")
        if missing:
            raise LibraryParseError(
                "Это не похоже на экспорт Apple Music: в файле нет обязательных колонок " + ", ".join(missing)
            )
        playlist_key = _column_key(self.playlist_column)
        playlist_position = header.index(playlist_key) if playlist_key in header else None

        parsed = ParsedLibrary()
        by_external_id: dict[str, str] = {}
        by_isrc: dict[str, str] = {}
        for row in rows[1:]:
            if not any(cell.strip() for cell in row):
                continue
            parsed.rows_total += 1

            def cell(position: int | None, row: list[str] = row) -> str:
                return " ".join(row[position].split()) if position is not None and position < len(row) else ""

            external_id = cell(positions["external_id"])
            title = cell(positions["title"])
            artist = cell(positions["artist"])
            if not external_id.isdigit() or not title or not artist:
                parsed.invalid_rows += 1
                continue
            isrc = normalize_isrc(cell(positions["isrc"]))
            kept_id = by_external_id.get(external_id) or (by_isrc.get(isrc) if isrc else None)
            if kept_id is None:
                kept_id = external_id
                parsed.tracks.append(
                    SourceTrack(
                        external_id=external_id,
                        title=title,
                        artist=artist,
                        album=cell(positions["album"]) or None,
                        isrc=isrc,
                    )
                )
                if isrc:
                    by_isrc[isrc] = external_id
            by_external_id[external_id] = kept_id
            playlist = cell(playlist_position)
            if playlist:
                members = parsed.playlists.setdefault(playlist, [])
                if kept_id not in members:
                    members.append(kept_id)
        if parsed.rows_total == 0:
            raise LibraryParseError("В файле нет ни одной строки с треками")
        if not parsed.tracks:
            raise LibraryParseError("Ни в одной строке нет названия, исполнителя и числового «Apple - id»")
        return parsed


SOURCES: dict[str, LibrarySource] = {AppleMusicCsvSource.name: AppleMusicCsvSource()}
