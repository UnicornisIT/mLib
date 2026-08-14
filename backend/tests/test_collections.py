from io import BytesIO

from PIL import Image

from app.auth.models import User
from app.core.security import hash_password
from app.database.session import CoreSessionLocal


def photo_bytes(color: str = "#9c5d3f") -> bytes:
    output = BytesIO()
    Image.new("RGB", (900, 700), color).save(output, "JPEG")
    return output.getvalue()


def create_collection(client, name: str = "Виниловые пластинки") -> dict:
    response = client.post(
        "/api/collections",
        json={"name": name, "description": "Редкие издания", "color": "#9c5d3f"},
    )
    assert response.status_code == 201
    return response.json()


def test_collection_item_custom_fields_photos_and_location(authenticated_client):
    collection = create_collection(authenticated_client)
    field_response = authenticated_client.post(
        f"/api/collections/{collection['id']}/fields",
        json={
            "name": "Год выпуска",
            "field_type": "number",
            "required": True,
            "show_on_card": True,
        },
    )
    assert field_response.status_code == 201
    field_id = field_response.json()["id"]

    item_response = authenticated_client.post(
        "/api/collections/items",
        json={
            "collection_id": collection["id"],
            "name": "The Dark Side of the Moon",
            "description": "Первое британское издание",
            "quantity": 1,
            "location": "Кабинет · стеллаж 2 · полка 4",
            "custom_values": {field_id: 1973},
        },
    )
    assert item_response.status_code == 201
    item = item_response.json()
    assert item["location"] == "Кабинет · стеллаж 2 · полка 4"
    assert item["custom_values"][field_id] == 1973

    photos = authenticated_client.post(
        f"/api/collections/items/{item['id']}/photos",
        files=[
            ("files", ("front.jpg", photo_bytes(), "image/jpeg")),
            ("files", ("back.jpg", photo_bytes("#334455"), "image/jpeg")),
        ],
    )
    assert photos.status_code == 201
    item = photos.json()
    assert len(item["photos"]) == 2
    assert item["photos"][0]["is_cover"] is True

    content = authenticated_client.get(f"/api/collections/photos/{item['photos'][0]['id']}/thumb")
    assert content.status_code == 200
    assert content.headers["content-type"] == "image/webp"

    listing = authenticated_client.get("/api/collections/items?q=стеллаж")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["locations"] == ["Кабинет · стеллаж 2 · полка 4"]

    dashboard = authenticated_client.get("/api/collections/dashboard")
    assert dashboard.json() == {"collections": 1, "items": 1, "photos": 2, "locations": 1}


def test_required_field_and_bulk_operations(authenticated_client):
    source = create_collection(authenticated_client, "Монеты")
    target = create_collection(authenticated_client, "Архив")
    field = authenticated_client.post(
        f"/api/collections/{source['id']}/fields",
        json={"name": "Страна", "field_type": "text", "required": True},
    ).json()

    invalid = authenticated_client.post(
        "/api/collections/items",
        json={"collection_id": source["id"], "name": "Один рубль"},
    )
    assert invalid.status_code == 422

    item_ids = []
    for name in ("Один рубль", "Два рубля"):
        created = authenticated_client.post(
            "/api/collections/items",
            json={
                "collection_id": source["id"],
                "name": name,
                "custom_values": {field["id"]: "Россия"},
            },
        )
        assert created.status_code == 201
        item_ids.append(created.json()["id"])

    located = authenticated_client.post(
        "/api/collections/items/bulk",
        json={"item_ids": item_ids, "operation": "set_location", "location": "Сейф"},
    )
    assert located.status_code == 200
    assert located.json()["affected"] == 2

    moved = authenticated_client.post(
        "/api/collections/items/bulk",
        json={"item_ids": item_ids, "operation": "move", "collection_id": target["id"]},
    )
    assert moved.status_code == 200
    listing = authenticated_client.get(f"/api/collections/items?collection_id={target['id']}&location=Сейф")
    assert listing.json()["total"] == 2
    assert all(not item["custom_values"] for item in listing.json()["items"])


def test_collection_data_is_isolated_between_users(client):
    client.post("/api/auth/setup", json={"username": "owner", "password": "correct-horse-battery-staple"})
    collection = create_collection(client, "Личная коллекция")
    client.post("/api/auth/logout")
    with CoreSessionLocal() as db:
        db.add(User(username="second", password_hash=hash_password("second-strong-password"), is_admin=False))
        db.commit()
    login = client.post("/api/auth/login", json={"username": "second", "password": "second-strong-password"})
    assert login.status_code == 200
    assert client.get("/api/collections").json() == []
    assert client.delete(f"/api/collections/{collection['id']}").status_code == 404
