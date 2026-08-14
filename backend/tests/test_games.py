def game_payload(**overrides):
    payload = {
        "title": "Disco Elysium",
        "developer": "ZA/UM",
        "publisher": "ZA/UM",
        "release_year": 2019,
        "genre": "RPG",
        "platform": "PC",
        "purchase_date": "2026-08-12",
        "acquired_from": "Steam",
        "status": "playing",
        "playtime_minutes": 750,
        "personal_rating": 9.5,
        "achievements_unlocked": 12,
        "achievements_total": 45,
        "cover_url": "https://example.com/disco.jpg",
        "screenshots": ["https://example.com/screen.jpg"],
    }
    payload.update(overrides)
    return payload


def test_game_crud_dashboard_and_filters(authenticated_client):
    created = authenticated_client.post("/api/games", json=game_payload())
    assert created.status_code == 201
    game = created.json()
    assert game["title"] == "Disco Elysium"
    assert game["playtime_minutes"] == 750

    listing = authenticated_client.get("/api/games?platform=PC&status=playing&q=elysium")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    updated = authenticated_client.patch(
        f"/api/games/{game['id']}",
        json={"status": "completed", "playtime_minutes": 1440, "personal_rating": 10},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "completed"

    dashboard = authenticated_client.get("/api/games/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json() == {
        "total": 1,
        "playing": 0,
        "completed": 1,
        "completed_100": 0,
        "playtime_minutes": 1440,
        "achievements_unlocked": 12,
        "achievements_total": 45,
    }

    deleted = authenticated_client.delete(f"/api/games/{game['id']}")
    assert deleted.status_code == 204
    assert authenticated_client.get(f"/api/games/{game['id']}").status_code == 404


def test_game_validation_rejects_invalid_achievement_progress(authenticated_client):
    response = authenticated_client.post(
        "/api/games",
        json=game_payload(achievements_unlocked=50, achievements_total=45),
    )
    assert response.status_code == 422
