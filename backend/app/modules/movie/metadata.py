import json
import logging
import mimetypes
import re
import subprocess
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.core.config import Settings

logger = logging.getLogger(__name__)

CYRILLIC_SEARCH_MAP = str.maketrans(
    {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
        "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p",
        "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts", "ч": "ch",
        "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    }
)


def transliterate_search(value: str) -> str:
    lowered = value.lower()
    translated = lowered.translate(CYRILLIC_SEARCH_MAP)
    return " ".join(part.capitalize() for part in translated.split())


class TmdbCredentialError(Exception):
    """The supplied TMDB credential was rejected."""


class TmdbServiceError(Exception):
    """TMDB could not be reached or returned an unexpected response."""


def normalize_tmdb_credential(value: str) -> str:
    credential = value.strip().strip('"\'')
    if "=" in credential:
        name, candidate = credential.split("=", 1)
        if name.strip().upper() in {"TMDB_API_TOKEN", "TMDB_API_KEY"}:
            credential = candidate.strip().strip('"\'')
    if credential.lower().startswith("bearer "):
        credential = credential[7:].strip()
    return credential


def is_supported_tmdb_credential(value: str | None) -> bool:
    if not value:
        return False
    credential = normalize_tmdb_credential(value)
    is_v3_key = re.fullmatch(r"[a-fA-F0-9]{32}", credential) is not None
    is_read_token = re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", credential) is not None
    is_developer_token = re.fullmatch(r"TMDB[A-Za-z0-9._-]{32,}", credential) is not None
    return is_v3_key or is_read_token or is_developer_token

KNOWN_VIDEO_EXTENSIONS = {
    ".3gp",
    ".asf",
    ".avi",
    ".divx",
    ".f4v",
    ".flv",
    ".m2ts",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".mts",
    ".ogv",
    ".rm",
    ".rmvb",
    ".ts",
    ".vob",
    ".webm",
    ".wmv",
}


@dataclass(slots=True)
class ParsedVideoName:
    title: str
    media_type: str
    year: int | None
    season_number: int | None
    episode_number: int | None
    episode_title: str | None


@dataclass(slots=True)
class VideoTechnicalMetadata:
    duration: float
    format: str
    mime_type: str
    video_codec: str | None
    audio_codec: str | None
    width: int | None
    height: int | None


def normalize_title(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", value).strip().casefold()


def _clean_name(value: str) -> str:
    value = re.sub(r"[._]+", " ", value)
    value = re.sub(r"[\[({].*?[\])}]", " ", value)
    value = re.sub(
        r"\b(2160p|1080p|720p|480p|4k|uhd|hdr10?|dv|bluray|b[dr]rip|"
        r"web[- .]?dl|webrip|hdtv|x26[45]|h\.?26[45]|hevc|av1|remux|proper|repack)\b.*$",
        "",
        value,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", value).strip(" -–—()[]{}")


def parse_video_filename(filename: str) -> ParsedVideoName:
    stem = Path(filename).stem
    episode = re.search(r"(?i)\bS(\d{1,2})[ ._-]*E(\d{1,3})\b|\b(\d{1,2})x(\d{1,3})\b", stem)
    year_match = re.search(r"(?<!\d)((?:19|20)\d{2})(?!\d)", stem)
    year = int(year_match.group(1)) if year_match else None
    if episode:
        season = int(episode.group(1) or episode.group(3))
        number = int(episode.group(2) or episode.group(4))
        title = _clean_name(stem[: episode.start()]) or "Неизвестный сериал"
        episode_title = _clean_name(stem[episode.end() :]) or None
        return ParsedVideoName(title, "series", year, season, number, episode_title)
    title_end = year_match.start() if year_match else len(stem)
    title = _clean_name(stem[:title_end]) or _clean_name(stem) or "Без названия"
    return ParsedVideoName(title, "movie", year, None, None, None)


def probe_video(path: Path, settings: Settings) -> VideoTechnicalMetadata:
    fallback_format = path.suffix.lower().lstrip(".") or "unknown"
    fallback_mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    try:
        result = subprocess.run(
            [
                settings.ffprobe_path,
                "-v",
                "error",
                "-show_entries",
                "stream=codec_type,codec_name,width,height:format=duration,format_name",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
    except FileNotFoundError:
        if path.suffix.lower() not in KNOWN_VIDEO_EXTENSIONS:
            raise ValueError("FFmpeg не найден, поэтому неизвестный формат проверить невозможно") from None
        return VideoTechnicalMetadata(0, fallback_format, fallback_mime, None, None, None, None)
    if result.returncode != 0:
        raise ValueError("Файл не распознан как видео или повреждён")
    payload = json.loads(result.stdout or "{}")
    streams = payload.get("streams") or []
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    if video is None:
        raise ValueError("В файле не найден видеопоток")
    fmt = payload.get("format") or {}
    try:
        duration = float(fmt.get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0
    return VideoTechnicalMetadata(
        duration=max(0, duration),
        format=str(fmt.get("format_name") or fallback_format).split(",", 1)[0],
        mime_type=fallback_mime,
        video_codec=video.get("codec_name"),
        audio_codec=audio.get("codec_name") if audio else None,
        width=int(video["width"]) if video.get("width") else None,
        height=int(video["height"]) if video.get("height") else None,
    )


def _tmdb_request(
    path: str,
    settings: Settings,
    params: dict[str, str | int] | None = None,
    *,
    strict: bool = False,
) -> dict[str, Any] | None:
    if not settings.tmdb_api_token:
        return None
    credential = normalize_tmdb_credential(settings.tmdb_api_token)
    query_params = dict(params or {})
    headers = {"Accept": "application/json"}
    if re.fullmatch(r"[a-fA-F0-9]{32}", credential):
        query_params["api_key"] = credential
    else:
        headers["Authorization"] = f"Bearer {credential}"
    query = urlencode(query_params)
    url = f"https://api.themoviedb.org/3/{path}{'?' + query if query else ''}"
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=12) as response:  # noqa: S310 - fixed TMDB origin
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        logger.warning("TMDB request failed for %s: HTTP %s", path, exc.code)
        if strict:
            if exc.code in {401, 403}:
                raise TmdbCredentialError from exc
            raise TmdbServiceError from exc
        return None
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        logger.warning("TMDB request failed for %s: %s", path, exc)
        if strict:
            raise TmdbServiceError from exc
        return None


def validate_tmdb_credential(value: str, settings: Settings) -> str:
    credential = normalize_tmdb_credential(value)
    if not is_supported_tmdb_credential(credential):
        raise TmdbCredentialError
    runtime = settings.model_copy(update={"tmdb_api_token": credential})
    payload = _tmdb_request("configuration", runtime, strict=True)
    if not payload or "images" not in payload:
        raise TmdbServiceError
    return credential


def search_tmdb(parsed: ParsedVideoName, settings: Settings) -> dict[str, Any] | None:
    endpoint = "tv" if parsed.media_type == "series" else "movie"
    params: dict[str, str | int] = {"query": parsed.title, "language": "ru-RU", "include_adult": "false"}
    if parsed.year:
        params["first_air_date_year" if endpoint == "tv" else "year"] = parsed.year
    payload = _tmdb_request(f"search/{endpoint}", settings, params)
    results = payload.get("results", []) if payload else []
    if not results:
        return None
    result = results[0]
    details = _tmdb_request(f"{endpoint}/{result['id']}", settings, {"language": "ru-RU"})
    return details or result


def get_tmdb_details(media_type: str, tmdb_id: int, settings: Settings) -> dict[str, Any] | None:
    endpoint = "tv" if media_type == "series" else "movie"
    credits_endpoint = "aggregate_credits" if media_type == "series" else "credits"
    return _tmdb_request(
        f"{endpoint}/{tmdb_id}",
        settings,
        {"language": "ru-RU", "append_to_response": credits_endpoint},
    )


def get_tmdb_season(tmdb_id: int, season_number: int, settings: Settings) -> dict[str, Any] | None:
    return _tmdb_request(f"tv/{tmdb_id}/season/{season_number}", settings, {"language": "ru-RU"})


def get_tmdb_person(person_id: int, settings: Settings) -> dict[str, Any] | None:
    payload = _tmdb_request(
        f"person/{person_id}",
        settings,
        {"language": "ru-RU", "append_to_response": "combined_credits"},
        strict=True,
    )
    if payload and not payload.get("biography"):
        fallback = _tmdb_request(f"person/{person_id}", settings, {"language": "en-US"}, strict=True)
        if fallback and fallback.get("biography"):
            payload["biography"] = fallback["biography"]
    return payload


def get_tmdb_catalog(
    media_type: str,
    page: int,
    query: str | None,
    sort: str,
    settings: Settings,
) -> dict[str, Any] | None:
    """Return a live TMDB catalog page without mirroring the whole database locally."""
    if not settings.tmdb_api_token:
        return None
    page = max(1, min(page, 500))
    if query:
        payload = _tmdb_request(
            "search/multi",
            settings,
            {"language": "ru-RU", "include_adult": "false", "page": page, "query": query},
            strict=True,
        )
        if payload is None:
            return {"page": page, "results": [], "total_pages": 0, "total_results": 0}
        search_payloads = [payload]
        transliterated_query = transliterate_search(query)
        if transliterated_query.lower() != query.lower():
            transliterated_payload = _tmdb_request(
                "search/multi",
                settings,
                {
                    "language": "ru-RU",
                    "include_adult": "false",
                    "page": page,
                    "query": transliterated_query,
                },
                strict=True,
            )
            if transliterated_payload:
                search_payloads.append(transliterated_payload)
        direct_results: list[dict[str, Any]] = []
        people: list[dict[str, Any]] = []
        for raw_item in [item for search_payload in search_payloads for item in search_payload.get("results", [])]:
            item = dict(raw_item)
            item_type = item.get("media_type")
            if item_type == "person":
                people.append(item)
                continue
            if item_type not in {"movie", "tv"}:
                continue
            normalized_type = "series" if item_type == "tv" else "movie"
            if media_type != "all" and normalized_type != media_type:
                continue
            item["media_type"] = normalized_type
            direct_results.append(item)

        person_results: list[dict[str, Any]] = []
        for person in people[:3]:
            person_name = str(person.get("name") or query)
            credits = _tmdb_request(
                f"person/{person['id']}/combined_credits",
                settings,
                {"language": "ru-RU"},
                strict=True,
            )
            if not credits:
                continue
            for source, label in (("cast", "Актёр"), ("crew", "Режиссёр")):
                for raw_credit in credits.get(source, []):
                    credit = dict(raw_credit)
                    credit_type = credit.get("media_type")
                    if credit_type not in {"movie", "tv"}:
                        continue
                    normalized_type = "series" if credit_type == "tv" else "movie"
                    if media_type != "all" and normalized_type != media_type:
                        continue
                    if source == "crew" and credit.get("job") not in {"Director", "Creator", "Series Director"}:
                        continue
                    credit["media_type"] = normalized_type
                    credit["_match_reason"] = f"{label}: {person_name}"
                    person_results.append(credit)
        person_results.sort(key=lambda item: float(item.get("popularity") or 0), reverse=True)
        unique_results: dict[tuple[str, int], dict[str, Any]] = {}
        for item in [*direct_results, *person_results]:
            if not item.get("id"):
                continue
            key = (str(item["media_type"]), int(item["id"]))
            if key not in unique_results or item.get("_match_reason"):
                unique_results[key] = item
        results = list(unique_results.values())[:40]
        return {
            "page": page,
            "results": results,
            "total_pages": max(int(item.get("total_pages") or 1) for item in search_payloads),
            "total_results": max(len(results), sum(int(item.get("total_results") or 0) for item in search_payloads)),
        }

    endpoints = ["movie", "tv"] if media_type == "all" else ["tv" if media_type == "series" else "movie"]
    responses: list[dict[str, Any]] = []
    for endpoint in endpoints:
        params: dict[str, str | int] = {
            "language": "ru-RU",
            "include_adult": "false",
            "page": page,
        }
        params["sort_by"] = {
            "rating": "vote_average.desc",
            "new": "primary_release_date.desc" if endpoint == "movie" else "first_air_date.desc",
        }.get(sort, "popularity.desc")
        if sort == "rating":
            params["vote_count.gte"] = 200
        payload = _tmdb_request(f"discover/{endpoint}", settings, params, strict=True)
        if payload is None:
            continue
        for item in payload.get("results", []):
            item["media_type"] = "series" if endpoint == "tv" else "movie"
        responses.append(payload)
    if not responses:
        return {"page": page, "results": [], "total_pages": 0, "total_results": 0}
    results = [item for payload in responses for item in payload.get("results", [])]
    key = {
        "rating": lambda item: float(item.get("vote_average") or 0),
        "new": lambda item: str(item.get("release_date") or item.get("first_air_date") or ""),
    }.get(sort, lambda item: float(item.get("popularity") or 0))
    results.sort(key=key, reverse=True)
    return {
        "page": page,
        "results": results,
        "total_pages": max(int(payload.get("total_pages") or 0) for payload in responses),
        "total_results": sum(int(payload.get("total_results") or 0) for payload in responses),
    }


def tmdb_values(payload: dict[str, Any], media_type: str) -> dict[str, Any]:
    release_date = payload.get("first_air_date") if media_type == "series" else payload.get("release_date")
    next_episode = payload.get("next_episode_to_air") or {}
    next_date = next_episode.get("air_date")
    episode_runtimes = [int(value) for value in payload.get("episode_run_time", []) if value]
    seasons = [
        {
            "season_number": int(season.get("season_number") or 0),
            "name": season.get("name") or f"Сезон {season.get('season_number') or 0}",
            "episode_count": int(season.get("episode_count") or 0),
            "air_date": season.get("air_date"),
            "poster_url": (
                f"https://image.tmdb.org/t/p/w500{season['poster_path']}" if season.get("poster_path") else None
            ),
        }
        for season in payload.get("seasons", [])
        if season.get("season_number") is not None
    ]
    credits = payload.get("aggregate_credits") if media_type == "series" else payload.get("credits")
    credits = credits or {}
    cast = []
    for person in credits.get("cast", [])[:16]:
        roles = person.get("roles") or []
        role = roles[0].get("character") if roles else person.get("character")
        cast.append(
            {
                "tmdb_id": int(person["id"]),
                "name": person.get("name") or person.get("original_name") or "Без имени",
                "role": role or None,
                "profile_url": (
                    f"https://image.tmdb.org/t/p/w185{person['profile_path']}"
                    if person.get("profile_path")
                    else None
                ),
            }
        )
    director_rows = [
        {
            "tmdb_id": int(person["id"]),
            "name": person.get("name") or person.get("original_name") or "Без имени",
            "role": "Создатель" if media_type == "series" else "Режиссёр",
            "profile_url": (
                f"https://image.tmdb.org/t/p/w185{person['profile_path']}" if person.get("profile_path") else None
            ),
        }
        for person in payload.get("created_by", [])
        if person.get("id")
    ]
    for person in credits.get("crew", []):
        jobs = person.get("jobs") or []
        matching_jobs = [job.get("job") for job in jobs if job.get("job") in {"Director", "Creator", "Series Director"}]
        if not matching_jobs and person.get("job") not in {"Director", "Creator", "Series Director"}:
            continue
        director_rows.append(
            {
                "tmdb_id": int(person["id"]),
                "name": person.get("name") or person.get("original_name") or "Без имени",
                "role": "Режиссёр",
                "profile_url": (
                    f"https://image.tmdb.org/t/p/w185{person['profile_path']}"
                    if person.get("profile_path")
                    else None
                ),
            }
        )
    directors = list({person["tmdb_id"]: person for person in director_rows}.values())[:8]
    return {
        "tmdb_id": int(payload["id"]),
        "title": payload.get("name") or payload.get("title") or "Без названия",
        "original_title": payload.get("original_name") or payload.get("original_title"),
        "year": int(str(release_date)[:4]) if release_date and str(release_date)[:4].isdigit() else None,
        "overview": payload.get("overview") or None,
        "poster_url": f"https://image.tmdb.org/t/p/w780{payload['poster_path']}"
        if payload.get("poster_path")
        else None,
        "backdrop_url": f"https://image.tmdb.org/t/p/w1280{payload['backdrop_path']}"
        if payload.get("backdrop_path")
        else None,
        "genres": json.dumps(
            [genre["name"] for genre in payload.get("genres", []) if genre.get("name")], ensure_ascii=False
        ),
        "tmdb_rating": float(payload.get("vote_average") or 0) or None,
        "release_status": payload.get("status") or None,
        "next_air_date": date.fromisoformat(next_date) if next_date else None,
        "runtime_minutes": int(payload.get("runtime") or 0) or None,
        "episode_runtime_minutes": episode_runtimes[0] if episode_runtimes else None,
        "total_episodes": int(payload.get("number_of_episodes") or 0),
        "total_seasons": int(payload.get("number_of_seasons") or 0),
        "seasons": json.dumps(seasons, ensure_ascii=False),
        "directors": json.dumps(directors, ensure_ascii=False),
        "cast": json.dumps(cast, ensure_ascii=False),
        "metadata_provider": "tmdb",
    }
