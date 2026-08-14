from app.core.config import get_settings
from app.modules.movie import metadata


def test_catalog_search_expands_a_director_to_their_credits(monkeypatch):
    settings = get_settings().model_copy(update={"tmdb_api_token": "a" * 32})

    def fake_request(path, *_args, **_kwargs):
        if path == "search/multi":
            return {
                "page": 1,
                "total_pages": 1,
                "total_results": 1,
                "results": [{"id": 525, "name": "Christopher Nolan", "media_type": "person"}],
            }
        if path == "person/525/combined_credits":
            return {
                "cast": [],
                "crew": [
                    {
                        "id": 27205,
                        "media_type": "movie",
                        "title": "Inception",
                        "release_date": "2010-07-15",
                        "job": "Director",
                        "popularity": 100,
                    }
                ],
            }
        raise AssertionError(path)

    monkeypatch.setattr(metadata, "_tmdb_request", fake_request)
    result = metadata.get_tmdb_catalog("all", 1, "Christopher Nolan", "popular", settings)

    assert result["results"][0]["title"] == "Inception"
    assert result["results"][0]["media_type"] == "movie"
    assert result["results"][0]["_match_reason"] == "Режиссёр: Christopher Nolan"


def test_tmdb_values_include_director_and_cast():
    values = metadata.tmdb_values(
        {
            "id": 11,
            "title": "Example",
            "release_date": "2026-01-01",
            "credits": {
                "crew": [{"id": 1, "name": "Director Name", "job": "Director", "profile_path": "/d.jpg"}],
                "cast": [{"id": 2, "name": "Actor Name", "character": "Hero", "profile_path": "/a.jpg"}],
            },
        },
        "movie",
    )

    assert "Director Name" in values["directors"]
    assert "Actor Name" in values["cast"]
    assert "Hero" in values["cast"]


def test_cyrillic_person_names_are_transliterated_for_tmdb_search():
    assert metadata.transliterate_search("Кристофер Нолан") == "Kristofer Nolan"
    assert metadata.transliterate_search("Киану Ривз") == "Kianu Rivz"
