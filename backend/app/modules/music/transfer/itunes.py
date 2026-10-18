import json
import logging
import re
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

LOOKUP_URL = "https://itunes.apple.com/lookup"
SEARCH_URL = "https://itunes.apple.com/search"
# The search endpoint allows roughly 20 requests a minute; lookup by id is used whenever an id is known.
SEARCH_LIMIT = 10
# Verified: one lookup request accepts at least 200 comma-separated ids; unknown ids are omitted.
LOOKUP_BATCH_SIZE = 100
ARTWORK_SIZE_PATTERN = re.compile(r"/\d+x\d+(bb)?\.(jpg|jpeg|png|webp)$", re.IGNORECASE)


class TrackLookupError(Exception):
    """The lookup request failed; the batch can be retried later."""


class LookupRateLimitedError(TrackLookupError):
    """Apple asked us to slow down (HTTP 403/429/503)."""


class TrackLookupClient(Protocol):
    def lookup(self, track_ids: list[str], country: str) -> dict[str, dict[str, Any]]: ...

    def search(self, term: str, country: str) -> list[dict[str, Any]]: ...


class ItunesLookupClient:
    """iTunes Search API lookup by trackId; needs no key and no extra dependencies."""

    def __init__(self, base_url: str = LOOKUP_URL, timeout: float = 20, search_url: str = SEARCH_URL) -> None:
        self.base_url = base_url
        self.search_url = search_url
        self.timeout = timeout

    def lookup(self, track_ids: list[str], country: str) -> dict[str, dict[str, Any]]:
        if not track_ids:
            return {}
        results = self._get(self.base_url, {"id": ",".join(track_ids), "country": country, "entity": "song"})
        return {
            str(item["trackId"]): item
            for item in results
            if isinstance(item, dict) and item.get("wrapperType") == "track" and item.get("trackId")
        }

    def search(self, term: str, country: str) -> list[dict[str, Any]]:
        """Songs found by free text ("artist title"); used for exports from services other than Apple Music."""
        query = {"term": term, "country": country, "entity": "song", "media": "music", "limit": SEARCH_LIMIT}
        return [
            item
            for item in self._get(self.search_url, query)
            if isinstance(item, dict) and item.get("wrapperType") == "track" and item.get("trackId")
        ]

    def _get(self, url: str, params: dict[str, Any]) -> list[Any]:
        request = Request(f"{url}?{urlencode(params)}", headers={"Accept": "application/json"})
        try:
            with urlopen(request, timeout=self.timeout) as response:  # noqa: S310 - fixed Apple origin
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            logger.warning("iTunes request to %s failed: HTTP %s", url, exc.code)
            if exc.code in {403, 429, 503}:
                raise LookupRateLimitedError from exc
            raise TrackLookupError from exc
        except (URLError, TimeoutError, OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.warning("iTunes request to %s failed: %s", url, exc)
            raise TrackLookupError from exc
        results = payload.get("results") if isinstance(payload, dict) else None
        return results if isinstance(results, list) else []


def _clean_url(value: Any) -> str | None:
    if not isinstance(value, str) or not value.startswith("https://"):
        return None
    parts = urlsplit(value)
    query = "&".join(item for item in parts.query.split("&") if item and not item.startswith("uo="))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


def catalog_values(item: dict[str, Any]) -> dict[str, Any]:
    """Fields kept from a lookup result. previewUrl is deliberately never stored (Apple terms)."""
    release = str(item.get("releaseDate") or "")
    duration = item.get("trackTimeMillis")
    values: dict[str, Any] = {
        "title": str(item.get("trackName") or "").strip() or None,
        "artist_name": str(item.get("artistName") or "").strip() or None,
        "album_title": str(item.get("collectionName") or "").strip() or None,
        "collection_id": str(item["collectionId"]) if item.get("collectionId") else None,
        "genre": str(item.get("primaryGenreName") or "").strip()[:100] or None,
        "apple_url": _clean_url(item.get("trackViewUrl")),
        "artwork_url": _clean_url(item.get("artworkUrl100")),
        "year": int(release[:4]) if release[:4].isdigit() else None,
        "duration_ms": int(duration) if isinstance(duration, int | float) and duration > 0 else None,
    }
    return {key: value for key, value in values.items() if value is not None}


def sized_artwork_url(url: str | None, size: int = 600) -> str | None:
    if not url:
        return None
    return ARTWORK_SIZE_PATTERN.sub(lambda match: f"/{size}x{size}bb.{match.group(2)}", url)


def spotify_search_url(artist: str, title: str) -> str:
    return "https://open.spotify.com/search/" + quote(f"{artist} {title}".strip(), safe="")
