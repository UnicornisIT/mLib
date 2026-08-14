def upload_video(client, filename: str = "The Example (2024).mkv", content: bytes = b"0123456789") -> dict:
    created = client.post("/api/movie/uploads", json={"filename": filename, "size": len(content)})
    assert created.status_code == 201
    upload = created.json()
    completed = client.patch(
        f"/api/movie/uploads/{upload['id']}",
        content=content,
        headers={"Upload-Offset": "0", "Content-Type": "application/offset+octet-stream"},
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    return completed.json()


def test_chunked_movie_upload_builds_catalog_card(authenticated_client):
    uploaded = upload_video(authenticated_client)
    listing = authenticated_client.get("/api/movie/titles")
    assert listing.status_code == 200
    payload = listing.json()
    assert payload["total"] == 1
    assert payload["items"][0]["title"] == "The Example"
    assert payload["items"][0]["year"] == 2024
    assert payload["items"][0]["media_type"] == "movie"
    assert uploaded["title_id"] == payload["items"][0]["id"]


def test_series_episodes_are_grouped_and_progress_is_saved(authenticated_client):
    first = upload_video(authenticated_client, "Great.Show.S01E01.Pilot.mkv", b"first-episode")
    upload_video(authenticated_client, "Great.Show.S01E02.Next.mkv", b"second-episode")
    detail = authenticated_client.get(f"/api/movie/titles/{first['title_id']}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["media_type"] == "series"
    assert payload["file_count"] == 2
    assert [item["episode_number"] for item in payload["files"]] == [1, 2]

    progress = authenticated_client.put(
        f"/api/movie/files/{first['file_id']}/progress",
        json={"position": 95, "duration": 100},
    )
    assert progress.status_code == 200
    assert progress.json()["completed"] is True


def test_movie_stream_supports_byte_ranges(authenticated_client):
    uploaded = upload_video(authenticated_client, content=b"0123456789")
    response = authenticated_client.get(
        f"/api/movie/files/{uploaded['file_id']}/stream",
        headers={"Range": "bytes=3-6"},
    )
    assert response.status_code == 206
    assert response.content == b"3456"
    assert response.headers["content-range"] == "bytes 3-6/10"


def test_tmdb_catalog_card_accepts_a_targeted_upload(authenticated_client, monkeypatch):
    import app.modules.movie.api.router as movie_router
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "tmdb_api_token", "a" * 32)
    catalog_item = {
        "id": 101,
        "title": "Большой фильм",
        "original_title": "The Big Movie",
        "release_date": "2026-04-12",
        "overview": "Описание из каталога",
        "poster_path": "/poster.jpg",
        "backdrop_path": "/backdrop.jpg",
        "vote_average": 8.2,
        "popularity": 100,
        "media_type": "movie",
    }
    monkeypatch.setattr(
        movie_router,
        "get_tmdb_catalog",
        lambda *args, **kwargs: {"page": 1, "results": [catalog_item], "total_pages": 10, "total_results": 200},
    )
    monkeypatch.setattr(
        movie_router,
        "get_tmdb_details",
        lambda *args, **kwargs: {**catalog_item, "genres": [{"name": "Драма"}], "status": "Released"},
    )

    catalog = authenticated_client.get("/api/movie/catalog")
    assert catalog.status_code == 200
    assert catalog.json()["items"][0]["title"] == "Большой фильм"
    assert catalog.json()["items"][0]["local_title_id"] is None

    card = authenticated_client.post("/api/movie/catalog/movie/101")
    assert card.status_code == 200
    title_id = card.json()["id"]
    assert card.json()["files"] == []

    created = authenticated_client.post(
        "/api/movie/uploads",
        json={"filename": "Big.Movie.2026.mkv", "size": 10, "title_id": title_id},
    )
    assert created.status_code == 201
    assert created.json()["title_id"] == title_id
    completed = authenticated_client.patch(
        f"/api/movie/uploads/{created.json()['id']}",
        content=b"0123456789",
        headers={"Upload-Offset": "0", "Content-Type": "application/offset+octet-stream"},
    )
    assert completed.status_code == 200
    assert completed.json()["title_id"] == title_id

    detail = authenticated_client.get(f"/api/movie/titles/{title_id}")
    assert detail.status_code == 200
    assert detail.json()["title"] == "Большой фильм"
    assert detail.json()["file_count"] == 1


def test_person_filmography_links_back_to_main_catalog_cards(authenticated_client, monkeypatch):
    import app.modules.movie.api.router as movie_router
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "tmdb_api_token", "a" * 32)
    monkeypatch.setattr(
        movie_router,
        "get_tmdb_details",
        lambda *_args, **_kwargs: {
            "id": 101,
            "title": "Главный фильм",
            "release_date": "2024-02-01",
            "genres": [{"name": "Драма"}],
            "status": "Released",
        },
    )
    saved = authenticated_client.post("/api/movie/catalog/movie/101")
    assert saved.status_code == 200

    monkeypatch.setattr(
        movie_router,
        "get_tmdb_person",
        lambda *_args, **_kwargs: {
            "id": 525,
            "name": "Test Person",
            "known_for_department": "Acting",
            "birthday": "1980-01-02",
            "place_of_birth": "London",
            "profile_path": "/person.jpg",
            "combined_credits": {
                "cast": [
                    {
                        "id": 101,
                        "media_type": "movie",
                        "title": "Главный фильм",
                        "release_date": "2024-02-01",
                        "character": "Главная роль",
                    },
                    {
                        "id": 202,
                        "media_type": "tv",
                        "name": "Большой сериал",
                        "first_air_date": "2022-05-03",
                    },
                ],
                "crew": [
                    {
                        "id": 101,
                        "media_type": "movie",
                        "title": "Главный фильм",
                        "release_date": "2024-02-01",
                        "job": "Director",
                    }
                ],
            },
        },
    )

    response = authenticated_client.get("/api/movie/people/525")
    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Test Person"
    assert len(payload["items"]) == 2
    movie = next(item for item in payload["items"] if item["media_type"] == "movie")
    assert movie["local_title_id"] == saved.json()["id"]
    assert movie["match_reason"] == "Актёр · Главная роль · Режиссёр"
    assert any(item["media_type"] == "series" for item in payload["items"])


def test_watch_tracking_records_movies_episodes_and_profile_stats(authenticated_client, monkeypatch):
    import app.modules.movie.api.router as movie_router
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "tmdb_api_token", "a" * 32)
    movie_payload = {
        "id": 501,
        "title": "Tracked Movie",
        "release_date": "2026-01-01",
        "runtime": 120,
        "genres": [],
        "status": "Released",
    }
    series_payload = {
        "id": 502,
        "name": "Tracked Series",
        "first_air_date": "2026-01-01",
        "episode_run_time": [45],
        "number_of_episodes": 2,
        "number_of_seasons": 1,
        "seasons": [{"season_number": 1, "name": "Season 1", "episode_count": 2}],
        "genres": [],
        "status": "Returning Series",
    }
    season_payload = {
        "season_number": 1,
        "name": "Season 1",
        "episodes": [
            {"id": 7001, "season_number": 1, "episode_number": 1, "name": "Pilot", "runtime": 45},
            {"id": 7002, "season_number": 1, "episode_number": 2, "name": "Next", "runtime": 50},
        ],
    }
    monkeypatch.setattr(
        movie_router,
        "get_tmdb_details",
        lambda media_type, *_: series_payload if media_type == "series" else movie_payload,
    )
    monkeypatch.setattr(movie_router, "get_tmdb_season", lambda *_: season_payload)

    movie = authenticated_client.post("/api/movie/catalog/movie/501").json()
    series = authenticated_client.post("/api/movie/catalog/series/502").json()
    watched_movie = authenticated_client.put(
        f"/api/movie/titles/{movie['id']}/tracking",
        json={"status": "watched"},
    )
    assert watched_movie.status_code == 200
    assert watched_movie.json()["status"] == "watched"

    watched_episode = authenticated_client.put(
        f"/api/movie/titles/{series['id']}/seasons/1/episodes/1",
        json={"watched": True},
    )
    assert watched_episode.status_code == 200
    assert watched_episode.json()["watched_count"] == 1
    assert watched_episode.json()["episodes"][0]["watched"] is True

    dashboard = authenticated_client.get("/api/movie/dashboard")
    assert dashboard.status_code == 200
    continue_watching = dashboard.json()["continue_watching"]
    assert len(continue_watching) == 1
    assert continue_watching[0]["title"]["id"] == series["id"]
    assert continue_watching[0]["title"]["watched_count"] == 1
    assert continue_watching[0]["file"] is None

    profile = authenticated_client.get("/api/movie/profile")
    assert profile.status_code == 200
    assert profile.json()["summaries"]["all"]["movies"] == 1
    assert profile.json()["summaries"]["all"]["episodes"] == 1
    assert profile.json()["summaries"]["all"]["minutes"] == 165
    assert profile.json()["series_status_counts"]["watching"] == 1

    completed_episode = authenticated_client.put(
        f"/api/movie/titles/{series['id']}/seasons/1/episodes/2",
        json={"watched": True},
    )
    assert completed_episode.status_code == 200
    assert completed_episode.json()["watched_count"] == 2
    completed_series = authenticated_client.get(f"/api/movie/titles/{series['id']}").json()
    assert completed_series["tracking"]["status"] == "completed"
    completed_dashboard = authenticated_client.get("/api/movie/dashboard").json()
    assert all(item["title"]["id"] != series["id"] for item in completed_dashboard["continue_watching"])


def test_tracking_status_can_be_removed_from_profile(authenticated_client, monkeypatch):
    import app.modules.movie.api.router as movie_router
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "tmdb_api_token", "a" * 32)
    monkeypatch.setattr(
        movie_router,
        "get_tmdb_details",
        lambda *_args, **_kwargs: {
            "id": 801,
            "name": "Accidental Series",
            "first_air_date": "2025-01-01",
            "genres": [],
            "status": "Returning Series",
        },
    )

    series = authenticated_client.post("/api/movie/catalog/series/801").json()
    planned = authenticated_client.put(
        f"/api/movie/titles/{series['id']}/tracking",
        json={"status": "planned"},
    )
    assert planned.status_code == 200
    assert authenticated_client.get("/api/movie/profile").json()["series_status_counts"]["planned"] == 1

    removed = authenticated_client.delete(f"/api/movie/titles/{series['id']}/tracking")
    assert removed.status_code == 204
    assert authenticated_client.get(f"/api/movie/titles/{series['id']}").json()["tracking"] is None
    assert authenticated_client.get("/api/movie/titles?tracked=true").json()["total"] == 0
    assert authenticated_client.get("/api/movie/profile").json()["series_status_counts"]["planned"] == 0

    assert authenticated_client.delete(f"/api/movie/titles/{series['id']}/tracking").status_code == 204
