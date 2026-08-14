from io import BytesIO

from PIL import Image


def cover_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (600, 900), "#23463d").save(output, "PNG")
    return output.getvalue()


def test_upload_list_cover_content_and_delete(authenticated_client):
    response = authenticated_client.post(
        "/api/books",
        data={
            "media_type": "ebook",
            "title": "Мастер и Маргарита",
            "author": "Михаил Булгаков",
            "genre": "Классика",
            "publication_year": "1967",
            "page_count": "480",
            "description": "Роман о любви, свободе и выборе.",
        },
        files={
            "file": ("master.epub", b"epub-test-content", "application/epub+zip"),
            "cover": ("cover.png", cover_bytes(), "image/png"),
        },
    )
    assert response.status_code == 201
    book = response.json()
    assert book["media_type"] == "ebook"
    assert book["title"] == "Мастер и Маргарита"
    assert book["has_cover"] is True

    listing = authenticated_client.get("/api/books?q=Булгаков")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    dashboard = authenticated_client.get("/api/books/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json() == {
        "total": 1,
        "ebooks": 1,
        "audiobooks": 0,
        "authors": 1,
        "storage_bytes": len(b"epub-test-content"),
    }

    cover = authenticated_client.get(f"/api/books/{book['id']}/cover")
    assert cover.status_code == 200
    assert cover.headers["content-type"] == "image/webp"

    content = authenticated_client.get(f"/api/books/{book['id']}/content")
    assert content.status_code == 200
    assert content.content == b"epub-test-content"

    deleted = authenticated_client.delete(f"/api/books/{book['id']}")
    assert deleted.status_code == 204
    assert authenticated_client.get(f"/api/books/{book['id']}").status_code == 404


def test_audiobook_range_and_duplicate_protection(authenticated_client):
    payload = {
        "media_type": "audiobook",
        "title": "Пикник на обочине",
        "author": "Аркадий и Борис Стругацкие",
        "narrator": "Чтец",
    }
    files = {"file": ("picnic.mp3", b"0123456789", "audio/mpeg")}
    first = authenticated_client.post("/api/books", data=payload, files=files)
    assert first.status_code == 201
    book_id = first.json()["id"]

    partial = authenticated_client.get(
        f"/api/books/{book_id}/content",
        headers={"Range": "bytes=2-5"},
    )
    assert partial.status_code == 206
    assert partial.content == b"2345"
    assert partial.headers["content-range"] == "bytes 2-5/10"

    duplicate = authenticated_client.post("/api/books", data=payload, files=files)
    assert duplicate.status_code == 409


def test_rejects_wrong_format_for_book_type(authenticated_client):
    response = authenticated_client.post(
        "/api/books",
        data={"media_type": "ebook", "title": "Wrong", "author": "Author"},
        files={"file": ("wrong.mp3", b"audio", "audio/mpeg")},
    )
    assert response.status_code == 415
