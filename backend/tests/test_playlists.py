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
