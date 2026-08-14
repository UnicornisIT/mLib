import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_rejects_placeholder_and_short_session_secrets():
    for secret in ("replace-with-a-long-random-secret", "short"):
        with pytest.raises(ValidationError, match="SECRET_KEY"):
            Settings(environment="production", secret_key=secret)


def test_production_accepts_a_unique_long_session_secret():
    settings = Settings(environment="production", secret_key="a-unique-random-value-with-more-than-32-characters")
    assert settings.environment == "production"


def test_setup_rejects_whitespace_and_weak_credentials_without_server_error(client):
    whitespace = client.post(
        "/api/auth/setup",
        json={"username": "   ", "password": "correct horse battery staple"},
    )
    weak_password = client.post(
        "/api/auth/setup",
        json={"username": "owner", "password": "aaaaaaaaaaaaaaa"},
    )

    assert whitespace.status_code == 422
    assert weak_password.status_code == 422
    assert client.get("/api/auth/status").json()["setup_required"] is True


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("patch", "/api/auth/me", {"avatar_color": "red"}),
        ("patch", "/api/auth/me", {"birth_date": "not-a-date"}),
        ("patch", "/api/auth/me", {"birth_date": "2999-01-01"}),
        ("patch", "/api/auth/me", {"display_name": "x" * 121}),
        ("put", "/api/auth/me/password", {"current_password": None}),
        ("patch", "/api/settings", {"theme": "neon"}),
        ("patch", "/api/settings", {"default_repeat": "forever"}),
        ("post", "/api/music/playlists", {"name": ""}),
        ("post", "/api/music/playlists", {"name": "   "}),
        ("post", "/api/music/playlists", {"name": "x" * 256}),
        ("post", "/api/music/playlists", {"name": "valid", "description": "x" * 2001}),
        ("patch", "/api/music/tracks/missing", {"title": ""}),
        ("patch", "/api/music/tracks/missing", {"title": "   "}),
        ("patch", "/api/music/tracks/missing", {"year": -1}),
        ("post", "/api/movie/uploads", {"filename": "movie.mkv", "size": 0}),
        ("post", "/api/movie/uploads", {"filename": "", "size": 1}),
        ("put", "/api/movie/files/missing/progress", {"position": -1, "duration": 10}),
        ("patch", "/api/movie/settings", {"metadata_refresh_hours": 0}),
        ("patch", "/api/movie/settings", {"metadata_refresh_hours": 721}),
    ],
)
def test_invalid_json_inputs_return_validation_errors(authenticated_client, method, path, payload):
    response = authenticated_client.request(method, path, json=payload)

    assert response.status_code == 422
    assert response.status_code < 500


@pytest.mark.parametrize(
    "path",
    [
        "/api/books?limit=0",
        "/api/books?limit=501",
        "/api/books?media_type=video",
        "/api/books?sort=unknown",
    ],
)
def test_invalid_query_inputs_return_validation_errors(authenticated_client, path):
    response = authenticated_client.get(path)

    assert response.status_code == 422
    assert response.status_code < 500


def test_extreme_but_valid_text_is_stored_and_searched_safely(authenticated_client):
    display_name = "<script>alert('x')</script> — Пользователь 🚀"
    profile = authenticated_client.patch(
        "/api/auth/me",
        json={
            "display_name": display_name,
            "bio": "& < > \" ' / \\ " * 25,
            "location": "  Москва & область  ",
        },
    )
    playlist = authenticated_client.post(
        "/api/music/playlists",
        json={"name": "<b>Тестовый плейлист</b>", "description": "🎵 & < >"},
    )
    search = authenticated_client.get("/api/music/search", params={"q": "%_<'\"🚀" * 500})

    assert profile.status_code == 200
    assert profile.json()["display_name"] == display_name
    assert profile.json()["location"] == "Москва & область"
    assert playlist.status_code == 201
    assert playlist.json()["name"] == "<b>Тестовый плейлист</b>"
    assert search.status_code == 200
    assert search.json() == {"tracks": [], "albums": [], "artists": []}
