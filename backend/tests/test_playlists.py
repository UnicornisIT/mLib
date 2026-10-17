from tests.helpers import create_track


def test_playlist_ordering(authenticated_client, db):
    first = create_track(db, title="First")
    second = create_track(db, title="Second")
    playlist = authenticated_client.post("/api/music/playlists", json={"name": "Road trip"}).json()
    first_add = authenticated_client.post(
        f"/api/music/playlists/{playlist['id']}/tracks",
        json={"track_id": first.id},
    )
    assert first_add.status_code == 200
    second_add = authenticated_client.post(
        f"/api/music/playlists/{playlist['id']}/tracks",
        json={"track_id": second.id},
    )
    items = second_add.json()["items"]
    assert [item["track"]["title"] for item in items] == ["First", "Second"]

    reordered = authenticated_client.put(
        f"/api/music/playlists/{playlist['id']}/tracks/reorder",
        json={"item_ids": [items[1]["id"], items[0]["id"]]},
    )
    assert reordered.status_code == 200
    assert [item["track"]["title"] for item in reordered.json()["items"]] == ["Second", "First"]


def create_catalog_track(db, apple_id: str, title: str, duration_ms: int | None = 180000):
    from app.modules.music.models import CatalogTrack

    item = CatalogTrack(
        apple_track_id=apple_id,
        title=title,
        artist_name="Каталог",
        normalized_title=title.casefold(),
        normalized_artist="каталог",
        duration_ms=duration_ms,
        enrich_status="enriched",
    )
    db.add(item)
    db.commit()
    return item


def test_playlist_mixes_files_and_catalog_tracks_without_files(authenticated_client, db):
    import pytest
    from sqlalchemy.exc import IntegrityError

    from app.modules.music.models import PlaylistTrack

    local = create_track(db, title="Local")
    card = create_catalog_track(db, "5001", "Без файла")
    playlist = authenticated_client.post("/api/music/playlists", json={"name": "Смешанный"}).json()
    url = f"/api/music/playlists/{playlist['id']}/tracks"

    assert authenticated_client.post(url, json={"track_id": local.id}).status_code == 200
    response = authenticated_client.post(url, json={"catalog_track_id": card.id, "position": 0})
    assert response.status_code == 200
    body = response.json()
    assert body["track_count"] == 2
    assert body["duration"] == 120.0 + 180.0
    first, second = body["items"]
    assert first["track"] is None
    assert first["catalog_track"]["title"] == "Без файла"
    assert first["catalog_track"]["has_file"] is False
    assert second["track"]["title"] == "Local"
    assert second["catalog_track"] is None

    assert authenticated_client.post(url, json={}).status_code == 422
    both = authenticated_client.post(url, json={"track_id": local.id, "catalog_track_id": card.id})
    assert both.status_code == 422
    assert "либо трек" in both.json()["detail"][0]["msg"]
    assert authenticated_client.post(url, json={"catalog_track_id": "missing"}).status_code == 404

    # Once the catalog track gets a file, the same entry becomes playable.
    local_for_card = create_track(db, title="Card File")
    local_for_card.catalog_track_id = card.id
    db.commit()
    detail = authenticated_client.get(f"/api/music/playlists/{playlist['id']}").json()
    assert detail["items"][0]["track"]["title"] == "Card File"
    assert detail["items"][0]["catalog_track"]["has_file"] is True

    reordered = authenticated_client.put(f"{url}/reorder", json={"item_ids": [second["id"], first["id"]]}).json()
    assert [item["id"] for item in reordered["items"]] == [second["id"], first["id"]]
    removed = authenticated_client.delete(f"{url}/{first['id']}").json()
    assert [item["track"]["title"] for item in removed["items"]] == ["Local"]
    assert authenticated_client.get("/api/music/playlists").json()[0]["track_count"] == 1

    db.add(PlaylistTrack(playlist_id=playlist["id"], position=7))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
