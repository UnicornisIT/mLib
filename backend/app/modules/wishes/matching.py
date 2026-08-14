import re
import unicodedata
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import utcnow
from app.database.session import (
    BooksSessionLocal,
    CollectionsSessionLocal,
    GamesSessionLocal,
    MovieSessionLocal,
    MusicSessionLocal,
)
from app.modules.books.models import Book
from app.modules.collections.models import Item
from app.modules.games.models import Game
from app.modules.movie.models import MediaTitle
from app.modules.music.models import Album
from app.modules.wishes.models import Wish


def normalize_title(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold().replace("ё", "е")
    return " ".join(re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE).split())


@dataclass(frozen=True)
class LibraryCandidate:
    category: str
    target_type: str
    title: str
    creator: str | None
    service: str
    item_id: str


def _candidates(owner_id: str, categories: set[str]) -> list[LibraryCandidate]:
    result: list[LibraryCandidate] = []
    if "watch" in categories:
        with MovieSessionLocal() as db:
            for item in db.scalars(select(MediaTitle)).all():
                result.append(LibraryCandidate("watch", item.media_type, item.title, None, "movie", item.id))
                if item.original_title and normalize_title(item.original_title) != normalize_title(item.title):
                    result.append(
                        LibraryCandidate("watch", item.media_type, item.original_title, None, "movie", item.id)
                    )
    if "read" in categories:
        with BooksSessionLocal() as db:
            for item in db.scalars(select(Book)).all():
                result.append(LibraryCandidate("read", "book", item.title, item.author, "books", item.id))
    if "listen" in categories:
        with MusicSessionLocal() as db:
            for item in db.scalars(select(Album)).all():
                result.append(LibraryCandidate("listen", "album", item.title, item.album_artist, "music", item.id))
    if "buy" in categories:
        with GamesSessionLocal() as db:
            for item in db.scalars(select(Game)).all():
                result.append(LibraryCandidate("buy", "game", item.title, item.developer, "games", item.id))
        with CollectionsSessionLocal() as db:
            for item in db.scalars(select(Item).where(Item.owner_id == owner_id)).all():
                result.append(LibraryCandidate("buy", "item", item.name, None, "collections", item.id))
    return result


def reconcile_wishes(db: Session, owner_id: str) -> int:
    wishes = db.scalars(
        select(Wish).where(Wish.owner_id == owner_id, Wish.status == "active")
    ).all()
    if not wishes:
        return 0
    candidates = _candidates(owner_id, {wish.category for wish in wishes})
    by_title: dict[tuple[str, str], list[LibraryCandidate]] = {}
    for candidate in candidates:
        by_title.setdefault((candidate.category, normalize_title(candidate.title)), []).append(candidate)

    matched = 0
    for wish in wishes:
        possible = by_title.get((wish.category, wish.normalized_title), [])
        if wish.target_type != "other":
            possible = [item for item in possible if item.target_type == wish.target_type]
        if wish.creator:
            creator = normalize_title(wish.creator)
            creator_matches = [item for item in possible if item.creator and normalize_title(item.creator) == creator]
            if creator_matches:
                possible = creator_matches
        if not possible:
            continue
        candidate = possible[0]
        wish.status = "fulfilled"
        wish.fulfilled_at = utcnow()
        wish.matched_service = candidate.service
        wish.matched_item_id = candidate.item_id
        wish.auto_fulfilled = True
        matched += 1
    if matched:
        db.commit()
    return matched
