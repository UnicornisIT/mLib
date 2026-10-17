import os
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import utcnow
from app.modules.music.models import CatalogTrack, TransferJob
from app.modules.music.transfer import worker as transfer_worker
from app.modules.music.transfer.itunes import (
    LookupRateLimitedError,
    TrackLookupError,
    catalog_values,
    sized_artwork_url,
    spotify_search_url,
)
from app.modules.music.transfer.sources import AppleMusicCsvSource, LibraryParseError
from app.modules.music.transfer.worker import TransferWorker

# Synthetic export: BOM, Cyrillic, quoted commas, a duplicate ISRC under another Apple id,
# a repeated Apple id and one broken row.
SAMPLE_CSV = (
    "﻿Track name,Artist name,Album,Playlist name,Type,ISRC,Apple - id\n"
    "Искала,Земфира,Земфира,Дорога,Playlist,RUA119900001,1001\n"
    '"Hello, World",Тестовый артист,"Альбом, часть 1",Дорога,Playlist,USAAA2400001,1002\n'
    "Only Turkey,Sezen Aksu,Albüm,Ev,Playlist,TRAAA2400003,1003\n"
    "Missing Everywhere,Nobody,,Ev,Playlist,GBAAA2400004,1004\n"
    "Искала (single),Земфира,Искала,Ev,Playlist,RUA119900001,1005\n"
    "Искала,Земфира,Земфира,Ev,Playlist,RUA119900001,1001\n"
    ",Broken,,Ev,Playlist,,abc\n"
)


def lookup_payload(track_id: str, name: str, artist: str = "Artist", **extra) -> dict:
    return {
        "wrapperType": "track",
        "kind": "song",
        "trackId": int(track_id),
        "trackName": name,
        "artistName": artist,
        "collectionName": f"{name} - Single",
        "collectionId": 9000 + int(track_id) % 1000,
        "trackViewUrl": f"https://music.apple.com/ru/album/x/{track_id}?i={track_id}&uo=4",
        "artworkUrl100": f"https://is1-ssl.mzstatic.com/image/thumb/Music/{track_id}/100x100bb.jpg",
        "previewUrl": "https://audio-ssl.itunes.apple.com/preview.m4a",
        "releaseDate": "2019-04-05T07:00:00Z",
        "trackTimeMillis": 215000,
        **extra,
    }


class FakeLookup:
    def __init__(self, catalog: dict[str, dict[str, dict]], failures: list[Exception] | None = None) -> None:
        self.catalog = catalog
        self.failures = list(failures or [])
        self.calls: list[tuple[list[str], str]] = []

    def lookup(self, track_ids: list[str], country: str) -> dict[str, dict]:
        self.calls.append((list(track_ids), country))
        if self.failures:
            raise self.failures.pop(0)
        storefront = self.catalog.get(country, {})
        return {track_id: storefront[track_id] for track_id in track_ids if track_id in storefront}


DEFAULT_CATALOG = {
    "ru": {
        "1001": lookup_payload("1001", "Искала", "Земфира"),
        "1002": lookup_payload("1002", "Hello, World", "Тестовый артист"),
    },
    "us": {"1002": lookup_payload("1002", "Hello, World (US)", "Test Artist")},
    "tr": {"1003": lookup_payload("1003", "Only Turkey", "Sezen Aksu")},
}


@pytest.fixture(autouse=True)
def no_background_worker(monkeypatch: pytest.MonkeyPatch) -> list[bool]:
    started: list[bool] = []
    monkeypatch.setattr(transfer_worker, "ensure_worker", lambda: started.append(True))
    return started


def run_worker(client=None) -> FakeLookup:
    fake = client or FakeLookup(DEFAULT_CATALOG)
    TransferWorker(client=fake, sleep=lambda _: None).run()
    return fake


def upload(client: TestClient, content: str | bytes = SAMPLE_CSV, filename: str = "library.csv", **data):
    payload = content.encode("utf-8") if isinstance(content, str) else content
    return client.post("/api/music/transfer", files={"file": (filename, payload, "text/csv")}, data=data)


def test_apple_music_parser_handles_bom_quotes_cyrillic_and_duplicates() -> None:
    parsed = AppleMusicCsvSource().parse(SAMPLE_CSV.encode("utf-8"))

    assert parsed.rows_total == 7
    assert parsed.invalid_rows == 1
    assert [track.external_id for track in parsed.tracks] == ["1001", "1002", "1003", "1004"]
    hello = parsed.tracks[1]
    assert (hello.title, hello.artist, hello.album) == ("Hello, World", "Тестовый артист", "Альбом, часть 1")
    assert parsed.tracks[0].isrc == "RUA119900001"
    assert parsed.playlists == {"Дорога": ["1001", "1002"], "Ev": ["1003", "1004", "1001"]}


def test_apple_music_parser_accepts_other_column_order_delimiter_and_encoding() -> None:
    content = "apple - id;isrc;ARTIST NAME;album;track name\n2001;ru-a11-99-00002;Кино;Группа крови;Кукушка\n"
    for encoded in (content.encode("cp1251"), content.encode("utf-16")):
        parsed = AppleMusicCsvSource().parse(encoded)
        assert parsed.tracks[0].title == "Кукушка"
        assert parsed.tracks[0].artist == "Кино"
        assert parsed.tracks[0].isrc == "RUA119900002"
        assert parsed.playlists == {}


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"", "Файл пустой"),
        (b"Track name,Artist name,Album\nA,B,C\n", "нет обязательных колонок «ISRC», «Apple - id»"),
        (b"Track name,Artist name,Album,ISRC,Apple - id\n", "нет ни одной строки"),
        (b"Track name,Artist name,Album,ISRC,Apple - id\n,,,,\nA,B,C,D,x\n", "числового «Apple - id»"),
    ],
)
def test_apple_music_parser_reports_errors_in_russian(content: bytes, message: str) -> None:
    with pytest.raises(LibraryParseError, match=message):
        AppleMusicCsvSource().parse(content)


@pytest.mark.skipif(not os.environ.get("MLIB_APPLE_MUSIC_CSV"), reason="personal export is not committed")
def test_apple_music_parser_on_real_export() -> None:
    parsed = AppleMusicCsvSource().parse(Path(os.environ["MLIB_APPLE_MUSIC_CSV"]).read_bytes())
    assert parsed.invalid_rows == 0
    assert len({track.external_id for track in parsed.tracks}) == len(parsed.tracks)
    isrcs = [track.isrc for track in parsed.tracks if track.isrc]
    assert len(set(isrcs)) == len(isrcs)


def test_lookup_values_drop_preview_and_tracking_parameters() -> None:
    values = catalog_values(lookup_payload("1001", "Искала", "Земфира"))
    assert "previewUrl" not in values and "preview_url" not in values
    assert values["apple_url"] == "https://music.apple.com/ru/album/x/1001?i=1001"
    assert values["year"] == 2019
    assert values["duration_ms"] == 215000
    assert sized_artwork_url(values["artwork_url"]).endswith("/600x600bb.jpg")
    assert spotify_search_url("Земфира", "Искала") == (
        "https://open.spotify.com/search/%D0%97%D0%B5%D0%BC%D1%84%D0%B8%D1%80%D0%B0%20"
        "%D0%98%D1%81%D0%BA%D0%B0%D0%BB%D0%B0"
    )


def test_transfer_imports_catalog_and_enriches_with_storefront_fallback(
    authenticated_client: TestClient, db: Session, no_background_worker: list[bool]
) -> None:
    response = upload(authenticated_client)
    assert response.status_code == 202, response.text
    job = response.json()
    assert job["status"] == "enriching"
    assert (job["rows_total"], job["unique_total"], job["added"], job["existing"]) == (7, 4, 4, 0)
    assert job["errors"] == 1
    assert job["pending"] == 4
    assert job["storefronts"] == ["ru", "us", "tr"]
    assert no_background_worker == [True]

    fake = run_worker()
    assert [country for _, country in fake.calls] == ["ru", "us", "tr"]
    assert sorted(fake.calls[1][0]) == ["1003", "1004"]

    status = authenticated_client.get(f"/api/music/transfer/{job['id']}").json()
    assert status["status"] == "completed"
    assert (status["enriched"], status["not_found"], status["pending"]) == (3, 1, 0)

    tracks = {item.apple_track_id: item for item in db.scalars(select(CatalogTrack))}
    assert tracks["1002"].title == "Hello, World"
    assert tracks["1002"].storefront == "ru"
    assert tracks["1003"].storefront == "tr"
    assert tracks["1003"].album_title == "Only Turkey - Single"
    assert tracks["1004"].enrich_status == "not_found"
    assert tracks["1004"].title == "Missing Everywhere"
    assert tracks["1001"].isrc == "RUA119900001"

    latest = authenticated_client.get("/api/music/transfer/latest").json()
    assert latest["id"] == job["id"]
    summary = authenticated_client.get("/api/music/transfer/summary").json()
    assert summary == {"total": 4, "enriched": 3, "not_found": 1, "pending": 0}


def test_transfer_reupload_is_idempotent_and_never_deletes(authenticated_client: TestClient, db: Session) -> None:
    upload(authenticated_client)
    run_worker()
    smaller = "Track name,Artist name,Album,ISRC,Apple - id\nНовая,Артист,,RUA112400009,1009\nИскала,Земфира,,,1001\n"
    second = upload(authenticated_client, smaller).json()

    assert (second["added"], second["existing"]) == (1, 1)
    assert db.query(CatalogTrack).count() == 5
    enriched = db.scalar(select(CatalogTrack).where(CatalogTrack.apple_track_id == "1001"))
    assert enriched.enrich_status == "enriched"
    assert enriched.transfer_job_id != second["id"]


def test_transfer_rejects_invalid_files_with_russian_errors(authenticated_client: TestClient) -> None:
    missing = upload(authenticated_client, "Track name,Artist name\nA,B\n")
    assert missing.status_code == 422
    assert "нет обязательных колонок" in missing.json()["detail"]
    wrong_type = upload(authenticated_client, SAMPLE_CSV, filename="library.xlsx")
    assert wrong_type.status_code == 422
    assert wrong_type.json()["detail"] == "Загрузите экспорт фонотеки в формате CSV"


def test_transfer_retry_and_cancel(authenticated_client: TestClient, db: Session) -> None:
    job = upload(authenticated_client).json()
    cancelled = authenticated_client.post(f"/api/music/transfer/{job['id']}/cancel").json()
    assert cancelled["status"] == "cancelled"
    run_worker()
    assert db.query(CatalogTrack).filter_by(enrich_status="pending").count() == 4
    assert authenticated_client.post(f"/api/music/transfer/{job['id']}/cancel").status_code == 409

    retried = authenticated_client.post(f"/api/music/transfer/{job['id']}/retry").json()
    assert retried["status"] == "enriching"
    run_worker()
    db.expire_all()
    assert db.query(CatalogTrack).filter_by(enrich_status="not_found").count() == 1

    later = dict(DEFAULT_CATALOG, us={"1004": lookup_payload("1004", "Found Later")})
    authenticated_client.post(f"/api/music/transfer/{job['id']}/retry")
    fake = run_worker(FakeLookup(later))
    assert fake.calls[0][0] == ["1004"]
    status = authenticated_client.get(f"/api/music/transfer/{job['id']}").json()
    assert (status["status"], status["enriched"], status["not_found"]) == ("completed", 4, 0)
    assert authenticated_client.post(f"/api/music/transfer/{job['id']}/retry").status_code == 409


def test_transfer_resumes_after_restart_and_respects_live_worker(authenticated_client: TestClient, db: Session) -> None:
    job_id = upload(authenticated_client).json()["id"]
    first = db.scalar(select(CatalogTrack).where(CatalogTrack.apple_track_id == "1001"))
    first.enrich_status = "enriched"
    job = db.get(TransferJob, job_id)
    job.worker_token = "live-worker"
    job.heartbeat_at = utcnow()
    db.commit()

    other = TransferWorker(client=FakeLookup(DEFAULT_CATALOG), sleep=lambda _: None)
    assert other.claim(job_id) is False

    job.heartbeat_at = utcnow() - timedelta(minutes=10)
    db.commit()
    fake = run_worker()
    assert "1001" not in fake.calls[0][0]
    db.expire_all()
    job = db.get(TransferJob, job_id)
    assert job.status == "completed"
    assert job.worker_token is None


def test_transfer_survives_lookup_failures(authenticated_client: TestClient, db: Session) -> None:
    job_id = upload(authenticated_client).json()["id"]
    flaky = FakeLookup(DEFAULT_CATALOG, failures=[LookupRateLimitedError(), TrackLookupError()])
    run_worker(flaky)
    status = authenticated_client.get(f"/api/music/transfer/{job_id}").json()
    assert (status["status"], status["enriched"], status["not_found"]) == ("completed", 3, 1)

    job_id = upload(authenticated_client, "Track name,Artist name,Album,ISRC,Apple - id\nX,Y,,,1010\n").json()["id"]
    broken = FakeLookup({}, failures=[TrackLookupError()] * 9)
    run_worker(broken)
    assert len(broken.calls) == 9
    status = authenticated_client.get(f"/api/music/transfer/{job_id}").json()
    assert status["status"] == "completed"
    assert status["errors"] == 1
    assert db.scalar(select(CatalogTrack.enrich_status).where(CatalogTrack.apple_track_id == "1010")) == "error"


def test_transfer_requires_admin_for_changes(client: TestClient) -> None:
    assert upload(client).status_code == 401


def test_transfer_can_create_playlists_from_playlist_column(authenticated_client: TestClient) -> None:
    assert upload(authenticated_client).status_code == 202
    assert authenticated_client.get("/api/music/playlists").json() == []

    upload(authenticated_client, create_playlists="true")
    upload(authenticated_client, create_playlists="true")
    playlists = {item["name"]: item for item in authenticated_client.get("/api/music/playlists").json()}
    assert set(playlists) == {"Дорога", "Ev"}
    road = authenticated_client.get(f"/api/music/playlists/{playlists['Дорога']['id']}").json()
    assert [item["catalog_track"]["apple_track_id"] for item in road["items"]] == ["1001", "1002"]
    assert all(item["track"] is None for item in road["items"])
    ev = authenticated_client.get(f"/api/music/playlists/{playlists['Ev']['id']}").json()
    assert [item["catalog_track"]["apple_track_id"] for item in ev["items"]] == ["1003", "1004", "1001"]
