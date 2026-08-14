# ruff: noqa: E402

import os
import shutil
import tempfile
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest

TEST_ROOT = Path(tempfile.gettempdir()) / f"mlib-tests-{uuid.uuid4()}"
TEST_ROOT.mkdir(parents=True)
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{(TEST_ROOT / 'legacy.db').as_posix()}"
os.environ["CORE_DATABASE_URL"] = f"sqlite:///{(TEST_ROOT / 'core.db').as_posix()}"
os.environ["MUSIC_DATABASE_URL"] = f"sqlite:///{(TEST_ROOT / 'music.db').as_posix()}"
os.environ["MOVIE_DATABASE_URL"] = f"sqlite:///{(TEST_ROOT / 'movie.db').as_posix()}"
os.environ["BOOKS_DATABASE_URL"] = f"sqlite:///{(TEST_ROOT / 'books.db').as_posix()}"
os.environ["COLLECTIONS_DATABASE_URL"] = f"sqlite:///{(TEST_ROOT / 'collections.db').as_posix()}"
os.environ["GAMES_DATABASE_URL"] = f"sqlite:///{(TEST_ROOT / 'games.db').as_posix()}"
os.environ["WISHES_DATABASE_URL"] = f"sqlite:///{(TEST_ROOT / 'wishes.db').as_posix()}"
os.environ["MEDIA_ROOT"] = str(TEST_ROOT / "media")
os.environ["SECRET_KEY"] = "test-secret-key-with-enough-entropy"
os.environ["FFPROBE_PATH"] = "__missing_ffprobe__"

from fastapi.testclient import TestClient

from app.database.base import *  # noqa: F403
from app.database.session import (
    BooksBase,
    BooksSessionLocal,
    CollectionsBase,
    CollectionsSessionLocal,
    CoreBase,
    CoreSessionLocal,
    GamesBase,
    GamesSessionLocal,
    MovieBase,
    MovieSessionLocal,
    MusicBase,
    MusicSessionLocal,
    WishesBase,
    WishesSessionLocal,
    books_engine,
    collections_engine,
    core_engine,
    games_engine,
    movie_engine,
    music_engine,
    wishes_engine,
)
from app.main import app


@pytest.fixture(autouse=True)
def fresh_database() -> Generator[None, None, None]:
    for base, engine in (
        (BooksBase, books_engine),
        (CollectionsBase, collections_engine),
        (GamesBase, games_engine),
        (WishesBase, wishes_engine),
        (MovieBase, movie_engine),
        (MusicBase, music_engine),
        (CoreBase, core_engine),
    ):
        base.metadata.drop_all(engine)
        base.metadata.create_all(engine)
    yield


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def authenticated_client(client: TestClient) -> TestClient:
    response = client.post(
        "/api/auth/setup",
        json={"username": "owner", "password": "correct-horse-battery-staple"},
    )
    assert response.status_code == 201
    return client


@pytest.fixture
def db():
    with MusicSessionLocal() as session:
        yield session


@pytest.fixture
def core_db():
    with CoreSessionLocal() as session:
        yield session


@pytest.fixture
def movie_db():
    with MovieSessionLocal() as session:
        yield session


@pytest.fixture
def books_db():
    with BooksSessionLocal() as session:
        yield session


@pytest.fixture
def collections_db():
    with CollectionsSessionLocal() as session:
        yield session


@pytest.fixture
def games_db():
    with GamesSessionLocal() as session:
        yield session


@pytest.fixture
def wishes_db():
    with WishesSessionLocal() as session:
        yield session


def pytest_sessionfinish(session, exitstatus) -> None:
    core_engine.dispose()
    music_engine.dispose()
    movie_engine.dispose()
    books_engine.dispose()
    collections_engine.dispose()
    games_engine.dispose()
    wishes_engine.dispose()
    shutil.rmtree(TEST_ROOT, ignore_errors=True)
