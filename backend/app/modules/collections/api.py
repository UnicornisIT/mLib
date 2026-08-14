from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import CurrentUser
from app.core.config import Settings, get_settings
from app.database.session import get_collections_db
from app.modules.collections.models import Collection, CustomField, Item, ItemFieldValue, ItemPhoto, Tag
from app.modules.collections.schemas import (
    BulkOperation,
    BulkResult,
    CollectionCreate,
    CollectionRead,
    CollectionsDashboard,
    CollectionUpdate,
    CustomFieldCreate,
    CustomFieldRead,
    CustomFieldUpdate,
    ItemCreate,
    ItemPage,
    ItemPhotoRead,
    ItemRead,
    ItemUpdate,
    TagCreate,
    TagRead,
)
from app.modules.collections.storage import CollectionPhotoStorage

router = APIRouter(prefix="/collections", tags=["collections"])
FIELD_TYPES = {"text", "long_text", "number", "date", "checkbox", "select", "url", "price", "rating"}


def clean_optional(value: str | None, limit: int | None = None) -> str | None:
    cleaned = (value or "").strip()
    return (cleaned[:limit] if limit else cleaned) or None


def item_options():
    return (
        selectinload(Item.collection),
        selectinload(Item.photos),
        selectinload(Item.tags),
        selectinload(Item.field_values).selectinload(ItemFieldValue.field),
    )


def require_collection(db: Session, collection_id: str, owner_id: str) -> Collection:
    collection = db.scalar(
        select(Collection)
        .where(Collection.id == collection_id, Collection.owner_id == owner_id)
        .options(selectinload(Collection.fields))
    )
    if collection is None:
        raise HTTPException(status_code=404, detail="Коллекция не найдена")
    return collection


def require_item(db: Session, item_id: str, owner_id: str) -> Item:
    item = db.scalar(select(Item).where(Item.id == item_id, Item.owner_id == owner_id).options(*item_options()))
    if item is None:
        raise HTTPException(status_code=404, detail="Предмет не найден")
    return item


def serialize_collection(db: Session, collection: Collection) -> CollectionRead:
    item_count = int(db.scalar(select(func.count(Item.id)).where(Item.collection_id == collection.id)) or 0)
    photo_count = int(
        db.scalar(
            select(func.count(ItemPhoto.id)).join(Item).where(Item.collection_id == collection.id)
        )
        or 0
    )
    return CollectionRead(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        color=collection.color,
        item_count=item_count,
        photo_count=photo_count,
        fields=[CustomFieldRead.model_validate(field) for field in collection.fields],
        created_at=collection.created_at,
        updated_at=collection.updated_at,
    )


def serialize_item(item: Item) -> ItemRead:
    photos = sorted(item.photos, key=lambda photo: (not photo.is_cover, photo.position, photo.created_at))
    return ItemRead(
        id=item.id,
        collection_id=item.collection_id,
        collection_name=item.collection.name,
        name=item.name,
        description=item.description,
        quantity=item.quantity,
        location=item.location,
        photos=[
            ItemPhotoRead(
                id=photo.id,
                original_filename=photo.original_filename,
                position=photo.position,
                is_cover=photo.is_cover,
                created_at=photo.created_at,
            )
            for photo in photos
        ],
        tags=[TagRead.model_validate(tag) for tag in sorted(item.tags, key=lambda tag: tag.name.lower())],
        custom_values={value.field_id: value.value for value in item.field_values},
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def normalize_field_value(field: CustomField, value: object) -> object | None:
    if value is None or value == "":
        return None
    if field.field_type in {"text", "long_text", "url", "date", "select"}:
        if isinstance(value, date):
            value = value.isoformat()
        if not isinstance(value, str):
            raise HTTPException(status_code=422, detail=f"Поле «{field.name}» должно содержать текст")
        value = value.strip()
        if field.field_type == "select" and value and value not in field.options:
            raise HTTPException(status_code=422, detail=f"Недопустимое значение поля «{field.name}»")
        return value or None
    if field.field_type == "checkbox":
        if not isinstance(value, bool):
            raise HTTPException(status_code=422, detail=f"Поле «{field.name}» должно быть флажком")
        return value
    if field.field_type in {"number", "price", "rating"}:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise HTTPException(status_code=422, detail=f"Поле «{field.name}» должно быть числом")
        if field.field_type == "rating" and not 0 <= float(value) <= 5:
            raise HTTPException(status_code=422, detail=f"Рейтинг «{field.name}» должен быть от 0 до 5")
        return value
    raise HTTPException(status_code=422, detail="Неизвестный тип поля")


def apply_values(db: Session, item: Item, collection: Collection, values: dict[str, object], replace: bool) -> None:
    fields = {field.id: field for field in collection.fields}
    unknown = set(values) - set(fields)
    if unknown:
        raise HTTPException(status_code=422, detail="Одно из настраиваемых полей не относится к коллекции")
    existing = {value.field_id: value for value in item.field_values}
    merged = {field_id: value.value for field_id, value in existing.items()}
    if replace:
        merged = {}
    merged.update(values)
    for field in collection.fields:
        normalized = normalize_field_value(field, merged.get(field.id))
        if field.required and normalized in (None, ""):
            raise HTTPException(status_code=422, detail=f"Заполните обязательное поле «{field.name}»")
        record = existing.get(field.id)
        if normalized is None:
            if record is not None:
                db.delete(record)
            continue
        if record is None:
            db.add(ItemFieldValue(item=item, field=field, value=normalized))
        else:
            record.value = normalized


def resolve_tags(db: Session, owner_id: str, tag_ids: list[str]) -> list[Tag]:
    unique_ids = list(dict.fromkeys(tag_ids))
    if not unique_ids:
        return []
    tags = list(db.scalars(select(Tag).where(Tag.owner_id == owner_id, Tag.id.in_(unique_ids))).all())
    if len(tags) != len(unique_ids):
        raise HTTPException(status_code=422, detail="Один из тегов не найден")
    return tags


@router.get("", response_model=list[CollectionRead])
def list_collections(user: CurrentUser, db: Annotated[Session, Depends(get_collections_db)]) -> list[CollectionRead]:
    collections = db.scalars(
        select(Collection)
        .where(Collection.owner_id == user.id)
        .options(selectinload(Collection.fields))
        .order_by(Collection.name.asc())
    ).all()
    return [serialize_collection(db, collection) for collection in collections]


@router.post("", response_model=CollectionRead, status_code=status.HTTP_201_CREATED)
def create_collection(
    payload: CollectionCreate,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_collections_db)],
) -> CollectionRead:
    collection = Collection(
        owner_id=user.id,
        name=payload.name.strip(),
        description=clean_optional(payload.description),
        color=payload.color.lower(),
    )
    db.add(collection)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Коллекция с таким названием уже существует") from exc
    db.refresh(collection)
    collection.fields = []
    return serialize_collection(db, collection)


@router.get("/dashboard", response_model=CollectionsDashboard)
def dashboard(user: CurrentUser, db: Annotated[Session, Depends(get_collections_db)]) -> CollectionsDashboard:
    filters = Item.owner_id == user.id
    return CollectionsDashboard(
        collections=int(db.scalar(select(func.count(Collection.id)).where(Collection.owner_id == user.id)) or 0),
        items=int(db.scalar(select(func.count(Item.id)).where(filters)) or 0),
        photos=int(db.scalar(select(func.count(ItemPhoto.id)).join(Item).where(filters)) or 0),
        locations=int(
            db.scalar(
                select(func.count(func.distinct(func.lower(Item.location)))).where(
                    filters, Item.location.is_not(None), Item.location != ""
                )
            )
            or 0
        ),
    )


@router.get("/tags", response_model=list[TagRead])
def list_tags(user: CurrentUser, db: Annotated[Session, Depends(get_collections_db)]) -> list[Tag]:
    return list(db.scalars(select(Tag).where(Tag.owner_id == user.id).order_by(Tag.name.asc())).all())


@router.post("/tags", response_model=TagRead, status_code=status.HTTP_201_CREATED)
def create_tag(payload: TagCreate, user: CurrentUser, db: Annotated[Session, Depends(get_collections_db)]) -> Tag:
    tag = Tag(owner_id=user.id, name=payload.name.strip(), color=payload.color.lower())
    db.add(tag)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Тег с таким названием уже существует") from exc
    db.refresh(tag)
    return tag


@router.get("/items", response_model=ItemPage)
def list_items(
    user: CurrentUser,
    db: Annotated[Session, Depends(get_collections_db)],
    collection_id: str | None = None,
    q: str | None = None,
    location: str | None = None,
    tag_id: str | None = None,
    sort: Annotated[str, Query(pattern="^(updated|created|name|location)$")] = "updated",
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> ItemPage:
    filters = [Item.owner_id == user.id]
    if collection_id:
        require_collection(db, collection_id, user.id)
        filters.append(Item.collection_id == collection_id)
    if location:
        filters.append(Item.location == location.strip())
    if tag_id:
        filters.append(Item.tags.any(Tag.id == tag_id, Tag.owner_id == user.id))
    if q and q.strip():
        term = f"%{q.strip()}%"
        filters.append(
            or_(
                Item.name.like(term),
                func.coalesce(Item.description, "").like(term),
                func.coalesce(Item.location, "").like(term),
                Item.tags.any(Tag.name.like(term)),
            )
        )
    ordering = {
        "created": (Item.created_at.desc(),),
        "name": (Item.name.asc(),),
        "location": (Item.location.asc().nullslast(), Item.name.asc()),
    }.get(sort, (Item.updated_at.desc(),))
    total = int(db.scalar(select(func.count(Item.id)).where(*filters)) or 0)
    items = db.scalars(select(Item).where(*filters).options(*item_options()).order_by(*ordering).limit(limit)).all()
    locations = [
        value
        for value in db.scalars(
            select(Item.location)
            .where(Item.owner_id == user.id, Item.location.is_not(None), Item.location != "")
            .distinct()
            .order_by(Item.location.asc())
        ).all()
        if value
    ]
    return ItemPage(items=[serialize_item(item) for item in items], total=total, locations=locations)


@router.post("/items", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
def create_item(
    payload: ItemCreate,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_collections_db)],
) -> ItemRead:
    collection = require_collection(db, payload.collection_id, user.id)
    item = Item(
        owner_id=user.id,
        collection=collection,
        name=payload.name.strip(),
        description=clean_optional(payload.description),
        quantity=payload.quantity,
        location=clean_optional(payload.location, 500),
        tags=resolve_tags(db, user.id, payload.tag_ids),
    )
    db.add(item)
    apply_values(db, item, collection, payload.custom_values, replace=True)
    db.commit()
    return serialize_item(require_item(db, item.id, user.id))


@router.post("/items/bulk", response_model=BulkResult)
def bulk_items(
    payload: BulkOperation,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_collections_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> BulkResult:
    unique_ids = list(dict.fromkeys(payload.item_ids))
    items = list(
        db.scalars(select(Item).where(Item.owner_id == user.id, Item.id.in_(unique_ids)).options(*item_options())).all()
    )
    if len(items) != len(unique_ids):
        raise HTTPException(status_code=404, detail="Один из выбранных предметов не найден")
    if payload.operation == "move":
        if not payload.collection_id:
            raise HTTPException(status_code=422, detail="Выберите коллекцию назначения")
        collection = require_collection(db, payload.collection_id, user.id)
        for item in items:
            item.collection_id = collection.id
            item.collection = collection
            for value in list(item.field_values):
                db.delete(value)
    elif payload.operation == "set_location":
        for item in items:
            item.location = clean_optional(payload.location, 500)
    elif payload.operation in {"add_tag", "remove_tag"}:
        if not payload.tag_id:
            raise HTTPException(status_code=422, detail="Выберите тег")
        tags = resolve_tags(db, user.id, [payload.tag_id])
        tag = tags[0]
        for item in items:
            if payload.operation == "add_tag" and tag not in item.tags:
                item.tags.append(tag)
            if payload.operation == "remove_tag" and tag in item.tags:
                item.tags.remove(tag)
    elif payload.operation == "delete":
        storage = CollectionPhotoStorage(settings)
        for item in items:
            db.delete(item)
            storage.delete_item_directory(item.id)
    db.commit()
    return BulkResult(affected=len(items))


@router.get("/items/{item_id}", response_model=ItemRead)
def item_detail(item_id: str, user: CurrentUser, db: Annotated[Session, Depends(get_collections_db)]) -> ItemRead:
    return serialize_item(require_item(db, item_id, user.id))


@router.patch("/items/{item_id}", response_model=ItemRead)
def update_item(
    item_id: str,
    payload: ItemUpdate,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_collections_db)],
) -> ItemRead:
    item = require_item(db, item_id, user.id)
    data = payload.model_dump(exclude_unset=True)
    target_collection = item.collection
    collection_changed = False
    if "collection_id" in data and data["collection_id"] != item.collection_id:
        target_collection = require_collection(db, data["collection_id"], user.id)
        collection_changed = True
        item.collection_id = target_collection.id
        item.collection = target_collection
        for value in list(item.field_values):
            db.delete(value)
        item.field_values = []
    if "name" in data:
        item.name = data["name"].strip()
    if "description" in data:
        item.description = clean_optional(data["description"])
    if "quantity" in data:
        item.quantity = data["quantity"]
    if "location" in data:
        item.location = clean_optional(data["location"], 500)
    if "tag_ids" in data:
        item.tags = resolve_tags(db, user.id, data["tag_ids"])
    if "custom_values" in data:
        apply_values(db, item, target_collection, data["custom_values"] or {}, replace=True)
    elif collection_changed:
        apply_values(db, item, target_collection, {}, replace=True)
    db.commit()
    return serialize_item(require_item(db, item.id, user.id))


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    item_id: str,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_collections_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    item = require_item(db, item_id, user.id)
    db.delete(item)
    db.commit()
    CollectionPhotoStorage(settings).delete_item_directory(item.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/items/{item_id}/photos", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
async def upload_photos(
    item_id: str,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_collections_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    files: Annotated[list[UploadFile], File()],
) -> ItemRead:
    item = require_item(db, item_id, user.id)
    if not files or len(files) > 20:
        raise HTTPException(status_code=422, detail="За один раз можно добавить от 1 до 20 фотографий")
    storage = CollectionPhotoStorage(settings)
    existing_count = len(item.photos)
    saved_paths: list[tuple[str, str]] = []
    try:
        for offset, upload in enumerate(files):
            photo = ItemPhoto(
                item=item,
                file_path="",
                thumbnail_path="",
                original_filename="",
                position=existing_count + offset,
            )
            db.add(photo)
            db.flush()
            full, thumb, original_name = await storage.save(upload, item.id, photo.id)
            saved_paths.append((full, thumb))
            photo.file_path = full
            photo.thumbnail_path = thumb
            photo.original_filename = original_name
            photo.is_cover = existing_count == 0 and offset == 0
        db.commit()
    except Exception:
        db.rollback()
        for paths in saved_paths:
            storage.delete(*paths)
        raise
    return serialize_item(require_item(db, item.id, user.id))


def require_photo(db: Session, photo_id: str, owner_id: str) -> ItemPhoto:
    photo = db.scalar(
        select(ItemPhoto)
        .join(Item)
        .where(ItemPhoto.id == photo_id, Item.owner_id == owner_id)
        .options(selectinload(ItemPhoto.item))
    )
    if photo is None:
        raise HTTPException(status_code=404, detail="Фотография не найдена")
    return photo


@router.get("/photos/{photo_id}/{size}")
def photo_content(
    photo_id: str,
    size: str,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_collections_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> FileResponse:
    if size not in {"full", "thumb"}:
        raise HTTPException(status_code=404, detail="Размер изображения не найден")
    photo = require_photo(db, photo_id, user.id)
    try:
        path = CollectionPhotoStorage(settings).managed(photo.file_path if size == "full" else photo.thumbnail_path)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail="Некорректный путь фотографии") from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Файл фотографии отсутствует")
    return FileResponse(path, media_type="image/webp", headers={"Cache-Control": "private, max-age=86400"})


@router.post("/photos/{photo_id}/cover", response_model=ItemRead)
def set_cover(photo_id: str, user: CurrentUser, db: Annotated[Session, Depends(get_collections_db)]) -> ItemRead:
    photo = require_photo(db, photo_id, user.id)
    for candidate in db.scalars(select(ItemPhoto).where(ItemPhoto.item_id == photo.item_id)).all():
        candidate.is_cover = candidate.id == photo.id
    db.commit()
    return serialize_item(require_item(db, photo.item_id, user.id))


@router.delete("/photos/{photo_id}", response_model=ItemRead)
def delete_photo(
    photo_id: str,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_collections_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ItemRead:
    photo = require_photo(db, photo_id, user.id)
    item_id = photo.item_id
    was_cover = photo.is_cover
    paths = (photo.file_path, photo.thumbnail_path)
    db.delete(photo)
    db.flush()
    if was_cover:
        replacement = db.scalar(
            select(ItemPhoto).where(ItemPhoto.item_id == item_id).order_by(ItemPhoto.position.asc())
        )
        if replacement:
            replacement.is_cover = True
    db.commit()
    CollectionPhotoStorage(settings).delete(*paths)
    return serialize_item(require_item(db, item_id, user.id))


@router.post("/{collection_id}/fields", response_model=CustomFieldRead, status_code=status.HTTP_201_CREATED)
def create_field(
    collection_id: str,
    payload: CustomFieldCreate,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_collections_db)],
) -> CustomField:
    collection = require_collection(db, collection_id, user.id)
    if payload.field_type not in FIELD_TYPES:
        raise HTTPException(status_code=422, detail="Неизвестный тип поля")
    options = [option.strip()[:100] for option in payload.options if option.strip()]
    if payload.field_type == "select" and not options:
        raise HTTPException(status_code=422, detail="Для списка добавьте хотя бы один вариант")
    position = int(db.scalar(select(func.count(CustomField.id)).where(CustomField.collection_id == collection.id)) or 0)
    field = CustomField(
        collection=collection,
        name=payload.name.strip(),
        field_type=payload.field_type,
        position=position,
        required=payload.required,
        show_on_card=payload.show_on_card,
        options=options,
    )
    db.add(field)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Поле с таким названием уже существует") from exc
    db.refresh(field)
    return field


def require_field(db: Session, field_id: str, owner_id: str) -> CustomField:
    field = db.scalar(
        select(CustomField).join(Collection).where(CustomField.id == field_id, Collection.owner_id == owner_id)
    )
    if field is None:
        raise HTTPException(status_code=404, detail="Поле не найдено")
    return field


@router.patch("/fields/{field_id}", response_model=CustomFieldRead)
def update_field(
    field_id: str,
    payload: CustomFieldUpdate,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_collections_db)],
) -> CustomField:
    field = require_field(db, field_id, user.id)
    data = payload.model_dump(exclude_unset=True)
    if "name" in data:
        field.name = data["name"].strip()
    if "required" in data:
        field.required = data["required"]
    if "show_on_card" in data:
        field.show_on_card = data["show_on_card"]
    if "position" in data:
        field.position = data["position"]
    if "options" in data:
        options = [option.strip()[:100] for option in data["options"] if option.strip()]
        if field.field_type == "select" and not options:
            raise HTTPException(status_code=422, detail="Для списка добавьте хотя бы один вариант")
        field.options = options
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Поле с таким названием уже существует") from exc
    db.refresh(field)
    return field


@router.delete("/fields/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_field(
    field_id: str,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_collections_db)],
) -> Response:
    db.delete(require_field(db, field_id, user.id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{collection_id}", response_model=CollectionRead)
def update_collection(
    collection_id: str,
    payload: CollectionUpdate,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_collections_db)],
) -> CollectionRead:
    collection = require_collection(db, collection_id, user.id)
    data = payload.model_dump(exclude_unset=True)
    if "name" in data:
        collection.name = data["name"].strip()
    if "description" in data:
        collection.description = clean_optional(data["description"])
    if "color" in data:
        collection.color = data["color"].lower()
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Коллекция с таким названием уже существует") from exc
    return serialize_collection(db, require_collection(db, collection.id, user.id))


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_collection(
    collection_id: str,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_collections_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    collection = require_collection(db, collection_id, user.id)
    item_ids = list(db.scalars(select(Item.id).where(Item.collection_id == collection.id)).all())
    db.delete(collection)
    db.commit()
    storage = CollectionPhotoStorage(settings)
    for item_id in item_ids:
        storage.delete_item_directory(item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
