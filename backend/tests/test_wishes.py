from app.modules.movie.models import MediaTitle, TitleTracking


def wish_payload(**overrides):
    payload = {
        "category": "watch",
        "target_type": "movie",
        "title": "Dune: Part Three",
        "creator": None,
        "notes": "Посмотреть в кино",
        "reference_url": "https://example.com/dune",
        "image_url": "https://example.com/dune.jpg",
    }
    payload.update(overrides)
    return payload


def game_payload(title: str):
    return {
        "title": title,
        "platform": "PC",
        "status": "not_started",
        "playtime_minutes": 0,
        "achievements_unlocked": 0,
        "achievements_total": 0,
        "screenshots": [],
    }


def test_wish_crud_and_manual_completion(authenticated_client):
    created = authenticated_client.post("/api/wishes", json=wish_payload())
    assert created.status_code == 201
    wish = created.json()
    assert wish["status"] == "active"

    listing = authenticated_client.get("/api/wishes?category=watch&status=active")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    completed = authenticated_client.patch(f"/api/wishes/{wish['id']}", json={"status": "fulfilled"})
    assert completed.status_code == 200
    assert completed.json()["status"] == "fulfilled"
    assert completed.json()["auto_fulfilled"] is False

    dashboard = authenticated_client.get("/api/wishes/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json()["fulfilled"] == 1

    assert authenticated_client.delete(f"/api/wishes/{wish['id']}").status_code == 204


def test_buy_wish_is_auto_fulfilled_when_game_appears(authenticated_client):
    wish = authenticated_client.post(
        "/api/wishes",
        json=wish_payload(category="buy", target_type="game", title="Hades II", notes=None),
    ).json()
    assert wish["status"] == "active"

    game = authenticated_client.post("/api/games", json=game_payload("Hades II"))
    assert game.status_code == 201

    reconciled = authenticated_client.get("/api/wishes?status=all").json()["items"][0]
    assert reconciled["status"] == "fulfilled"
    assert reconciled["auto_fulfilled"] is True
    assert reconciled["matched_service"] == "games"
    assert reconciled["matched_item_id"] == game.json()["id"]


def test_watch_wish_links_movie_without_creating_tracking_state(authenticated_client, movie_db):
    movie = MediaTitle(media_type="movie", title="Dune: Part Three", normalized_title="dune part three", year=2026)
    movie_db.add(movie)
    movie_db.commit()

    wish = authenticated_client.post("/api/wishes", json=wish_payload()).json()
    assert wish["status"] == "fulfilled"
    assert wish["matched_service"] == "movie"
    assert wish["matched_item_id"] == movie.id
    assert movie_db.query(TitleTracking).count() == 0
