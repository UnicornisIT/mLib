import wave
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from mutagen.id3 import TIT2, TPE1, TSRC
from mutagen.mp4 import MP4FreeForm
from mutagen.wave import WAVE
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.modules.music.metadata import _from_mp4, _from_vorbis, extract_metadata
from app.modules.music.models import CatalogTrack, Track
from app.modules.music.scanner import jobs, scan_directory

_counter = iter(range(1, 10_000))


def make_wav(path: Path, *, title: str, artist: str, isrc: str | None = None, seconds: float = 2.0) -> Path:
    frames = int(8000 * seconds)
    salt = next(_counter)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(8000)
        output.writeframes(salt.to_bytes(2, "little") * frames)
    audio = WAVE(path)
    audio.add_tags()
    audio.tags.add(TIT2(encoding=3, text=[title]))
    audio.tags.add(TPE1(encoding=3, text=[artist]))
    if isrc:
        audio.tags.add(TSRC(encoding=3, text=[isrc]))
    audio.save()
    return path


def add_card(
    db: Session, apple_id: str, title: str, artist: str, *, isrc: str | None = None, duration_ms: int | None = None
) -> CatalogTrack:
    item = CatalogTrack(
        apple_track_id=apple_id,
        isrc=isrc,
        title=title,
        artist_name=artist,
        album_title=f"{title} - Single",
        normalized_title=title.casefold(),
        normalized_artist=artist.casefold(),
        duration_ms=duration_ms,
        enrich_status="enriched",
    )
    db.add(item)
    db.commit()
    return item


def upload_files(client: TestClient, *paths: Path):
    files = [("files", (path.name, path.read_bytes(), "audio/wav")) for path in paths]
    response = client.post("/api/music/upload", files=files)
    assert response.status_code == 200, response.text
    return response.json()


def test_isrc_is_read_from_id3_vorbis_and_mp4_tags(tmp_path: Path) -> None:
    path = make_wav(tmp_path / "a.wav", title="Искала", artist="Земфира", isrc="ru-a11-99-00001")
    metadata = extract_metadata(path, path.name, Settings(ffprobe_path="__missing__"))
    assert metadata.isrc == "RUA119900001"

    vorbis, _ = _from_vorbis(SimpleNamespace(tags={"isrc": ["GBAAA2400004"]}))
    assert vorbis["isrc"] == "GBAAA2400004"
    mp4, _ = _from_mp4(SimpleNamespace(tags={"----:com.apple.iTunes:ISRC": [MP4FreeForm(b"USAAA2400001")]}))
    assert mp4["isrc"] == "USAAA2400001"
    broken = make_wav(tmp_path / "b.wav", title="X", artist="Y", isrc="not an isrc")
    assert extract_metadata(broken, broken.name, Settings(ffprobe_path="__missing__")).isrc is None


def test_upload_into_catalog_track_ignores_differing_tags(
    authenticated_client: TestClient, db: Session, tmp_path: Path
) -> None:
    card = add_card(db, "1001", "Искала", "Земфира", isrc="RUA119900001")
    path = make_wav(tmp_path / "rip.wav", title="Track 01", artist="Unknown")
    url = f"/api/music/transfer/tracks/{card.id}/file"

    response = authenticated_client.post(url, files={"file": (path.name, path.read_bytes(), "audio/wav")})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "added"
    assert body["catalog_track"]["has_file"] is True
    assert body["catalog_track"]["artwork_id"] == body["track"]["artwork_id"]
    assert body["track"]["title"] == "Track 01"
    stored = db.get(Track, body["track"]["id"])
    assert stored.catalog_track_id == card.id
    assert stored.title == "Track 01"

    other = make_wav(tmp_path / "other.wav", title="Другое", artist="Unknown")
    taken = authenticated_client.post(url, files={"file": (other.name, other.read_bytes(), "audio/wav")})
    assert taken.status_code == 409
    assert "уже есть файл" in taken.json()["detail"]

    second_card = add_card(db, "1002", "Другая", "Земфира")
    same_file = authenticated_client.post(
        f"/api/music/transfer/tracks/{second_card.id}/file",
        files={"file": (path.name, path.read_bytes(), "audio/wav")},
    )
    assert same_file.status_code == 409
    assert "привязан к другому" in same_file.json()["detail"]

    listing = authenticated_client.get("/api/music/transfer/tracks", params={"status": "with_file"}).json()
    assert [item["id"] for item in listing["items"]] == [card.id]
    without = authenticated_client.get("/api/music/transfer/tracks", params={"status": "without_file"}).json()
    assert [item["id"] for item in without["items"]] == [second_card.id]
    assert authenticated_client.get("/api/music/transfer/tracks", params={"q": "друг"}).json()["total"] == 1


def test_upload_into_catalog_track_reuses_existing_unlinked_file(
    authenticated_client: TestClient, db: Session, tmp_path: Path
) -> None:
    path = make_wav(tmp_path / "song.wav", title="Song", artist="Artist")
    [result] = upload_files(authenticated_client, path)
    card = add_card(db, "2001", "Song (Remastered)", "Artist")

    response = authenticated_client.post(
        f"/api/music/transfer/tracks/{card.id}/file", files={"file": (path.name, path.read_bytes(), "audio/wav")}
    )
    assert response.status_code == 201
    assert response.json()["status"] == "linked_existing"
    assert response.json()["track"]["id"] == result["track"]["id"]
    assert db.query(Track).count() == 1


def test_manual_link_and_unlink(authenticated_client: TestClient, db: Session, tmp_path: Path) -> None:
    [result] = upload_files(authenticated_client, make_wav(tmp_path / "x.wav", title="X", artist="Y"))
    track_id = result["track"]["id"]
    first = add_card(db, "3001", "Первый", "Артист")
    second = add_card(db, "3002", "Второй", "Артист")

    linked = authenticated_client.put(f"/api/music/transfer/tracks/{first.id}/file", json={"track_id": track_id})
    assert linked.status_code == 200
    assert linked.json()["catalog_track"]["track_id"] == track_id
    moved = authenticated_client.put(f"/api/music/transfer/tracks/{second.id}/file", json={"track_id": track_id})
    assert moved.status_code == 409
    missing = authenticated_client.put(f"/api/music/transfer/tracks/{second.id}/file", json={"track_id": "nope"})
    assert missing.status_code == 404

    unlinked = authenticated_client.delete(f"/api/music/transfer/tracks/{first.id}/file")
    assert unlinked.status_code == 200
    assert unlinked.json()["has_file"] is False
    assert authenticated_client.get(f"/api/music/tracks/{track_id}").status_code == 200
    assert authenticated_client.delete(f"/api/music/transfer/tracks/{first.id}/file").status_code == 404
    assert authenticated_client.put(
        f"/api/music/transfer/tracks/{second.id}/file", json={"track_id": track_id}
    ).is_success


def test_upload_auto_links_by_isrc_then_by_name_and_duration(
    authenticated_client: TestClient, db: Session, tmp_path: Path
) -> None:
    by_isrc = add_card(db, "4001", "Совсем другое имя", "Кто-то", isrc="RUA119900001")
    by_name = add_card(db, "4002", "Кукушка", "Кино", duration_ms=3000)
    add_card(db, "4003", "Far Off", "Band", duration_ms=10000)

    results = upload_files(
        authenticated_client,
        make_wav(tmp_path / "1.wav", title="Искала", artist="Земфира", isrc="RUA119900001"),
        make_wav(tmp_path / "2.wav", title="  КУКУШКА ", artist="кино", seconds=2.0),
        make_wav(tmp_path / "3.wav", title="Far Off", artist="Band", seconds=2.0),
        make_wav(tmp_path / "4.wav", title="Nothing", artist="Nobody"),
    )
    assert [item["catalog_track_id"] for item in results] == [by_isrc.id, by_name.id, None, None]
    assert all(item["catalog_candidates"] == 0 for item in results)
    assert db.query(Track).count() == 4


def test_ambiguous_matches_are_offered_not_linked(
    authenticated_client: TestClient, db: Session, tmp_path: Path
) -> None:
    single = add_card(db, "5001", "Song", "Artist", isrc="USAAA2400001")
    album = add_card(db, "5002", "Song", "Artist", isrc="USAAA2400001")
    add_card(db, "5003", "Twin", "Duo", duration_ms=2000)
    add_card(db, "5004", "Twin", "Duo", duration_ms=2500)

    results = upload_files(
        authenticated_client,
        make_wav(tmp_path / "1.wav", title="Song", artist="Artist", isrc="USAAA2400001"),
        make_wav(tmp_path / "2.wav", title="Twin", artist="Duo", seconds=2.0),
    )
    assert [item["catalog_track_id"] for item in results] == [None, None]
    assert [item["catalog_candidates"] for item in results] == [2, 2]

    candidates = authenticated_client.get(f"/api/music/transfer/candidates/{results[0]['track']['id']}").json()
    assert {item["id"] for item in candidates} == {single.id, album.id}
    chosen = authenticated_client.put(
        f"/api/music/transfer/tracks/{album.id}/file", json={"track_id": results[0]["track"]["id"]}
    )
    assert chosen.status_code == 200


def test_folder_import_links_catalog_tracks(db: Session, tmp_path: Path) -> None:
    folder = tmp_path / "music"
    folder.mkdir()
    card = add_card(db, "6001", "Кукушка", "Кино", isrc="RUA119900002")
    add_card(db, "6002", "Twin", "Duo", duration_ms=2000)
    add_card(db, "6003", "Twin", "Duo", duration_ms=2100)
    make_wav(folder / "a.wav", title="Кукушка (live)", artist="Кино", isrc="RUA119900002")
    make_wav(folder / "b.wav", title="Twin", artist="Duo")
    make_wav(folder / "c.wav", title="Unknown", artist="Nobody")

    job = jobs.create(folder)
    scan_directory(job.id, folder, get_settings())
    snapshot = jobs.snapshot(job.id)
    assert (snapshot["status"], snapshot["added"], snapshot["linked"]) == ("completed", 3, 1)
    assert len(snapshot["ambiguous_track_ids"]) == 1
    db.expire_all()
    assert db.query(Track).filter_by(catalog_track_id=card.id).count() == 1
    assert db.query(Track).filter(Track.catalog_track_id.is_(None)).count() == 2


def test_linked_track_exposes_catalog_data_without_touching_tags(
    authenticated_client: TestClient, db: Session, tmp_path: Path
) -> None:
    card = add_card(db, "7001", "Искала", "Земфира", isrc="RUA119900001", duration_ms=215000)
    card.apple_url = "https://music.apple.com/ru/album/x/1?i=7001"
    card.artwork_url = "https://is1-ssl.mzstatic.com/image/thumb/Music/a/100x100bb.jpg"
    db.commit()
    path = make_wav(tmp_path / "rip.wav", title="track01", artist="Unknown artist")
    track_id = authenticated_client.post(
        f"/api/music/transfer/tracks/{card.id}/file", files={"file": (path.name, path.read_bytes(), "audio/wav")}
    ).json()["track"]["id"]

    track = authenticated_client.get(f"/api/music/tracks/{track_id}").json()
    assert track["title"] == "track01"
    assert track["artist"]["name"] == "Unknown artist"
    assert track["artwork_id"] is None
    catalog = track["catalog"]
    assert (catalog["title"], catalog["artist_name"], catalog["album_title"]) == (
        "Искала",
        "Земфира",
        "Искала - Single",
    )
    assert catalog["artwork_url"] == "https://is1-ssl.mzstatic.com/image/thumb/Music/a/600x600bb.jpg"
    assert catalog["apple_music_url"] == "https://music.apple.com/ru/album/x/1?i=7001"
    assert (
        catalog["spotify_url"]
        == "https://open.spotify.com/search/%D0%97%D0%B5%D0%BC%D1%84%D0%B8%D1%80%D0%B0%20%D0%98%D1%81%D0%BA%D0%B0%D0%BB%D0%B0"
    )
    listed = authenticated_client.get("/api/music/tracks").json()["items"][0]
    assert listed["catalog"]["id"] == card.id

    no_file = add_card(db, "7002", "Без файла", "Земфира")
    cards = {item["id"]: item for item in authenticated_client.get("/api/music/transfer/tracks").json()["items"]}
    assert cards[card.id]["has_file"] is True and cards[card.id]["track_id"] == track_id
    assert cards[no_file.id]["has_file"] is False
    assert cards[no_file.id]["apple_music_url"] is None
    assert cards[no_file.id]["spotify_url"].startswith("https://open.spotify.com/search/")
