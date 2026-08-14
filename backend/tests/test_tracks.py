from app.modules.music.api.tracks import parse_range_header
from app.modules.music.library import find_duplicate
from app.modules.music.models import Favorite
from tests.helpers import create_track
from tests.test_metadata import tagged_wav


def test_duplicate_detection_uses_hash_and_size(db):
    track = create_track(db, title="Unique")
    assert find_duplicate(db, track.file_hash, track.file_size).id == track.id
    assert find_duplicate(db, track.file_hash, track.file_size + 1) is None


def test_upload_with_album_metadata_creates_track_and_album(authenticated_client, tmp_path):
    path = tmp_path / "album-track.wav"
    tagged_wav(path, title="Uploaded Album Track")

    with path.open("rb") as source:
        response = authenticated_client.post(
            "/api/music/upload",
            files={"files": (path.name, source, "audio/wav")},
        )

    assert response.status_code == 200
    result = response.json()[0]
    assert result["status"] == "added"
    assert result["track"]["title"] == "Uploaded Album Track"
    assert result["track"]["artist"]["name"] == "The Artist"
    assert result["track"]["album"]["title"] == "Compilation"


def test_range_parser_supports_open_and_suffix_ranges():
    assert parse_range_header("bytes=2-5", 10) == (2, 5)
    assert parse_range_header("bytes=7-", 10) == (7, 9)
    assert parse_range_header("bytes=-3", 10) == (7, 9)


def test_stream_endpoint_returns_partial_content(authenticated_client, db):
    track = create_track(db, content=b"0123456789")
    response = authenticated_client.get(
        f"/api/music/tracks/{track.id}/stream",
        headers={"Range": "bytes=2-5"},
    )
    assert response.status_code == 206
    assert response.content == b"2345"
    assert response.headers["content-range"] == "bytes 2-5/10"
    assert response.headers["accept-ranges"] == "bytes"


def test_track_crud(authenticated_client, db):
    track = create_track(db)
    listing = authenticated_client.get("/api/music/tracks")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    updated = authenticated_client.patch(
        f"/api/music/tracks/{track.id}",
        json={"title": "Updated", "genre": "Jazz", "track_number": 4},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Updated"
    assert updated.json()["genre"] == "Jazz"


def test_favorite_track_listing_filters_without_query_error(authenticated_client, db):
    favorite_track = create_track(db, title="Favorite Track")
    create_track(db, title="Regular Track")
    user_id = authenticated_client.get("/api/auth/me").json()["id"]
    db.add(Favorite(user_id=user_id, track_id=favorite_track.id))
    db.commit()

    response = authenticated_client.get("/api/music/tracks", params={"favorite": True})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert [item["id"] for item in payload["items"]] == [favorite_track.id]
    assert payload["items"][0]["favorite"] is True


def test_metadata_attention_queue_can_be_reviewed(authenticated_client, db):
    track = create_track(db, title="Needs Metadata")

    listing = authenticated_client.get("/api/music/tracks", params={"attention": True})
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    item = listing.json()["items"][0]
    assert item["id"] == track.id
    assert item["needs_attention"] is True
    assert item["metadata_status"] == "incomplete"
    assert set(item["metadata_issues"]) >= {"missing_album", "missing_genre", "missing_year"}
    assert authenticated_client.get("/api/music/tracks/attention-summary").json() == {"total": 1}

    reviewed = authenticated_client.post(f"/api/music/tracks/{track.id}/metadata-reviewed")
    assert reviewed.status_code == 200
    assert reviewed.json()["needs_attention"] is False
    assert reviewed.json()["metadata_status"] == "reviewed"
    assert authenticated_client.get("/api/music/tracks", params={"attention": True}).json()["total"] == 0
