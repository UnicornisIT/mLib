import json
import logging
import re
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import mutagen
from mutagen.flac import FLAC
from mutagen.id3 import APIC, ID3
from mutagen.mp4 import MP4, MP4Cover

from app.core.config import Settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class EmbeddedArtwork:
    data: bytes
    mime_type: str


@dataclass(slots=True)
class NormalizedTrackMetadata:
    title: str
    artist: str
    album_artist: str
    album: str | None
    genre: str | None
    year: int | None
    track_number: int | None
    disc_number: int | None
    composer: str | None
    copyright: str | None
    comment: str | None
    duration: float
    bitrate: int | None
    sample_rate: int | None
    channels: int | None
    codec: str | None
    format: str
    artwork: EmbeddedArtwork | None
    title_from_filename: bool = False
    artist_from_fallback: bool = False


def normalize_identity(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", value).strip().casefold()


def _first(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list | tuple):
        value = value[0] if value else None
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _number(value: Any) -> int | None:
    text = _first(value)
    if not text:
        return None
    match = re.search(r"\d+", text)
    return int(match.group()) if match else None


def _year(value: Any) -> int | None:
    number = _number(value)
    return number if number is not None and 0 <= number <= 9999 else None


def _id3_text(tags: ID3, key: str) -> str | None:
    frame = tags.get(key)
    return _first(getattr(frame, "text", None))


def _from_id3(tags: ID3) -> tuple[dict[str, Any], EmbeddedArtwork | None]:
    artwork = None
    pictures = tags.getall("APIC")
    if pictures:
        picture: APIC = pictures[0]
        artwork = EmbeddedArtwork(bytes(picture.data), picture.mime or "image/jpeg")
    comments = tags.getall("COMM")
    return (
        {
            "title": _id3_text(tags, "TIT2"),
            "artist": _id3_text(tags, "TPE1"),
            "album_artist": _id3_text(tags, "TPE2"),
            "album": _id3_text(tags, "TALB"),
            "genre": _id3_text(tags, "TCON"),
            "year": _id3_text(tags, "TDRC") or _id3_text(tags, "TYER"),
            "track_number": _id3_text(tags, "TRCK"),
            "disc_number": _id3_text(tags, "TPOS"),
            "composer": _id3_text(tags, "TCOM"),
            "copyright": _id3_text(tags, "TCOP"),
            "comment": _first(getattr(comments[0], "text", None)) if comments else None,
        },
        artwork,
    )


def _from_mp4(audio: MP4) -> tuple[dict[str, Any], EmbeddedArtwork | None]:
    tags = audio.tags or {}
    covers = tags.get("covr", [])
    artwork = None
    if covers:
        cover: MP4Cover = covers[0]
        mime = "image/png" if cover.imageformat == MP4Cover.FORMAT_PNG else "image/jpeg"
        artwork = EmbeddedArtwork(bytes(cover), mime)
    track_number = tags.get("trkn")
    disc_number = tags.get("disk")
    return (
        {
            "title": _first(tags.get("\xa9nam")),
            "artist": _first(tags.get("\xa9ART")),
            "album_artist": _first(tags.get("aART")),
            "album": _first(tags.get("\xa9alb")),
            "genre": _first(tags.get("\xa9gen")),
            "year": _first(tags.get("\xa9day")),
            "track_number": track_number[0][0] if track_number else None,
            "disc_number": disc_number[0][0] if disc_number else None,
            "composer": _first(tags.get("\xa9wrt")),
            "copyright": _first(tags.get("cprt")),
            "comment": _first(tags.get("\xa9cmt")),
        },
        artwork,
    )


def _from_vorbis(audio: Any) -> tuple[dict[str, Any], EmbeddedArtwork | None]:
    tags = audio.tags or {}
    artwork = None
    if isinstance(audio, FLAC) and audio.pictures:
        picture = audio.pictures[0]
        artwork = EmbeddedArtwork(bytes(picture.data), picture.mime or "image/jpeg")
    return (
        {
            "title": _first(tags.get("title")),
            "artist": _first(tags.get("artist")),
            "album_artist": _first(tags.get("albumartist") or tags.get("album artist")),
            "album": _first(tags.get("album")),
            "genre": _first(tags.get("genre")),
            "year": _first(tags.get("date") or tags.get("year")),
            "track_number": _first(tags.get("tracknumber")),
            "disc_number": _first(tags.get("discnumber")),
            "composer": _first(tags.get("composer")),
            "copyright": _first(tags.get("copyright")),
            "comment": _first(tags.get("comment") or tags.get("description")),
        },
        artwork,
    )


def _probe(path: Path, settings: Settings) -> dict[str, Any]:
    try:
        result = subprocess.run(
            [
                settings.ffprobe_path,
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=codec_name,bit_rate,sample_rate,channels:format=duration,format_name",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            logger.warning("ffprobe failed for %s: %s", path.name, result.stderr.strip())
            return {}
        payload = json.loads(result.stdout)
        stream = (payload.get("streams") or [{}])[0]
        fmt = payload.get("format") or {}
        return {
            "codec": stream.get("codec_name"),
            "bitrate": _number(stream.get("bit_rate")),
            "sample_rate": _number(stream.get("sample_rate")),
            "channels": _number(stream.get("channels")),
            "duration": float(fmt.get("duration") or 0),
            "format": fmt.get("format_name"),
        }
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError, ValueError) as exc:
        logger.info("ffprobe unavailable for %s: %s", path.name, exc)
        return {}


def extract_metadata(
    path: Path,
    original_name: str,
    settings: Settings,
    use_embedded: bool = True,
) -> NormalizedTrackMetadata:
    try:
        audio = mutagen.File(path)
    except Exception as exc:
        raise ValueError("Не удалось прочитать аудиофайл") from exc
    if audio is None or not hasattr(audio, "info"):
        raise ValueError("Файл не распознан как поддерживаемое аудио")

    tags: dict[str, Any]
    artwork: EmbeddedArtwork | None
    if not use_embedded:
        tags, artwork = {}, None
    elif isinstance(audio, MP4):
        tags, artwork = _from_mp4(audio)
    elif isinstance(getattr(audio, "tags", None), ID3):
        tags, artwork = _from_id3(audio.tags)
    else:
        tags, artwork = _from_vorbis(audio)

    info = audio.info
    probe = _probe(path, settings)
    duration = float(getattr(info, "length", 0) or probe.get("duration") or 0)
    if duration <= 0:
        raise ValueError("Не удалось определить длительность аудиофайла")
    fallback_title = Path(original_name).stem.strip() or "Без названия"
    embedded_title = _first(tags.get("title"))
    embedded_artist = _first(tags.get("artist"))
    artist = embedded_artist or "Неизвестный исполнитель"
    album_artist = _first(tags.get("album_artist")) or artist
    extension = path.suffix.lower().lstrip(".")
    return NormalizedTrackMetadata(
        title=embedded_title or fallback_title,
        artist=artist,
        album_artist=album_artist,
        album=_first(tags.get("album")),
        genre=_first(tags.get("genre")),
        year=_year(tags.get("year")),
        track_number=_number(tags.get("track_number")),
        disc_number=_number(tags.get("disc_number")),
        composer=_first(tags.get("composer")),
        copyright=_first(tags.get("copyright")),
        comment=_first(tags.get("comment")),
        duration=duration,
        bitrate=_number(getattr(info, "bitrate", None)) or probe.get("bitrate"),
        sample_rate=_number(getattr(info, "sample_rate", None)) or probe.get("sample_rate"),
        channels=_number(getattr(info, "channels", None)) or probe.get("channels"),
        codec=probe.get("codec") or extension,
        format=extension,
        artwork=artwork,
        title_from_filename=embedded_title is None,
        artist_from_fallback=embedded_artist is None,
    )
