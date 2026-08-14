from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class CoreBase(DeclarativeBase):
    pass


class MusicBase(DeclarativeBase):
    pass


class MovieBase(DeclarativeBase):
    pass


class BooksBase(DeclarativeBase):
    pass


class CollectionsBase(DeclarativeBase):
    pass


class GamesBase(DeclarativeBase):
    pass


class WishesBase(DeclarativeBase):
    pass


def _engine(url: str) -> Engine:
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def enable_sqlite_foreign_keys(dbapi_connection: object, _: object) -> None:
            cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


settings = get_settings()
core_engine = _engine(settings.core_database_url)
music_engine = _engine(settings.music_database_url)
movie_engine = _engine(settings.movie_database_url)
books_engine = _engine(settings.books_database_url)
collections_engine = _engine(settings.collections_database_url)
games_engine = _engine(settings.games_database_url)
wishes_engine = _engine(settings.wishes_database_url)

CoreSessionLocal = sessionmaker(bind=core_engine, autoflush=False, expire_on_commit=False)
MusicSessionLocal = sessionmaker(bind=music_engine, autoflush=False, expire_on_commit=False)
MovieSessionLocal = sessionmaker(bind=movie_engine, autoflush=False, expire_on_commit=False)
BooksSessionLocal = sessionmaker(bind=books_engine, autoflush=False, expire_on_commit=False)
CollectionsSessionLocal = sessionmaker(bind=collections_engine, autoflush=False, expire_on_commit=False)
GamesSessionLocal = sessionmaker(bind=games_engine, autoflush=False, expire_on_commit=False)
WishesSessionLocal = sessionmaker(bind=wishes_engine, autoflush=False, expire_on_commit=False)


def _session(factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    db = factory()
    try:
        yield db
    finally:
        db.close()


def get_core_db() -> Generator[Session, None, None]:
    yield from _session(CoreSessionLocal)


def get_music_db() -> Generator[Session, None, None]:
    yield from _session(MusicSessionLocal)


def get_movie_db() -> Generator[Session, None, None]:
    yield from _session(MovieSessionLocal)


def get_books_db() -> Generator[Session, None, None]:
    yield from _session(BooksSessionLocal)


def get_collections_db() -> Generator[Session, None, None]:
    yield from _session(CollectionsSessionLocal)


def get_games_db() -> Generator[Session, None, None]:
    yield from _session(GamesSessionLocal)


def get_wishes_db() -> Generator[Session, None, None]:
    yield from _session(WishesSessionLocal)
