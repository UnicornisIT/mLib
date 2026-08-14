from sqlalchemy import inspect

from app.database.session import (
    collections_engine,
    core_engine,
    games_engine,
    movie_engine,
    music_engine,
    wishes_engine,
)
from app.modules.movie.metadata import is_supported_tmdb_credential
from app.modules.movie.models import MovieSetting
from app.modules.music.models import MusicSetting


def test_service_schemas_are_physically_isolated():
    core_tables = set(inspect(core_engine).get_table_names())
    music_tables = set(inspect(music_engine).get_table_names())
    movie_tables = set(inspect(movie_engine).get_table_names())
    collections_tables = set(inspect(collections_engine).get_table_names())
    games_tables = set(inspect(games_engine).get_table_names())
    wishes_tables = set(inspect(wishes_engine).get_table_names())

    assert {"users", "core_settings"} <= core_tables
    assert "music_tracks" not in core_tables
    assert "movie_titles" not in core_tables
    assert "users" not in music_tables
    assert {"music_tracks", "music_settings"} <= music_tables
    assert "users" not in movie_tables
    assert {"movie_titles", "movie_settings"} <= movie_tables
    assert {"collections", "collection_items", "collection_item_photos"} <= collections_tables
    assert {"games"} <= games_tables
    assert {"wishes"} <= wishes_tables
    assert "users" not in games_tables
    assert "users" not in wishes_tables
    assert "users" not in collections_tables


def test_new_tmdb_developer_plan_token_format_is_supported():
    assert is_supported_tmdb_credential("TMDB" + "a" * 43)


def test_service_status_checks_each_library_database(client):
    response = client.get("/api/services/status")

    assert response.status_code == 200
    assert response.json() == {
        "music": {"status": "available"},
        "movie": {"status": "available"},
        "books": {"status": "available"},
        "collections": {"status": "available"},
        "games": {"status": "available"},
        "wishes": {"status": "available"},
    }


def test_movie_settings_do_not_leak_into_music(authenticated_client, db, movie_db, monkeypatch):
    import app.modules.movie.api.router as movie_router

    token = "a" * 32
    monkeypatch.setattr(movie_router, "validate_tmdb_credential", lambda value, settings: value)
    response = authenticated_client.patch(
        "/api/movie/settings",
        json={"tmdb_api_token": token, "metadata_refresh_hours": 72},
    )
    assert response.status_code == 200
    assert response.json()["tmdb_enabled"] is True
    assert response.json()["metadata_refresh_hours"] == 72

    assert movie_db.get(MovieSetting, "tmdb_api_token").value == token
    assert db.get(MusicSetting, "tmdb_api_token") is None
    assert "tmdb_enabled" not in authenticated_client.get("/api/settings").json()["metadata"]


def test_movie_settings_reject_an_invalid_tmdb_credential(authenticated_client, movie_db):
    response = authenticated_client.patch(
        "/api/movie/settings",
        json={"tmdb_api_token": "not-a-tmdb-key"},
    )

    assert response.status_code == 422
    assert movie_db.get(MovieSetting, "tmdb_api_token") is None
