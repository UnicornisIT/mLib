from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FieldType = Literal["text", "long_text", "number", "date", "checkbox", "select", "url", "price", "rating"]
FieldValue = str | float | int | bool | date | None


class CustomFieldCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    field_type: FieldType
    required: bool = False
    show_on_card: bool = False
    options: list[str] = Field(default_factory=list, max_length=100)


class CustomFieldUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    required: bool | None = None
    show_on_card: bool | None = None
    options: list[str] | None = Field(default=None, max_length=100)
    position: int | None = Field(default=None, ge=0)


class CustomFieldRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    field_type: FieldType
    position: int
    required: bool
    show_on_card: bool
    options: list[str]


class CollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    color: str = Field(default="#b96842", pattern=r"^#[0-9a-fA-F]{6}$")


class CollectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")


class CollectionRead(BaseModel):
    id: str
    name: str
    description: str | None
    color: str
    item_count: int
    photo_count: int
    fields: list[CustomFieldRead]
    created_at: datetime
    updated_at: datetime


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    color: str = Field(default="#8b6f5d", pattern=r"^#[0-9a-fA-F]{6}$")


class TagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    color: str


class ItemCreate(BaseModel):
    collection_id: str
    name: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=10000)
    quantity: int = Field(default=1, ge=1, le=1_000_000)
    location: str | None = Field(default=None, max_length=500)
    tag_ids: list[str] = Field(default_factory=list, max_length=100)
    custom_values: dict[str, FieldValue] = Field(default_factory=dict)


class ItemUpdate(BaseModel):
    collection_id: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=10000)
    quantity: int | None = Field(default=None, ge=1, le=1_000_000)
    location: str | None = Field(default=None, max_length=500)
    tag_ids: list[str] | None = Field(default=None, max_length=100)
    custom_values: dict[str, FieldValue] | None = None


class ItemPhotoRead(BaseModel):
    id: str
    original_filename: str
    position: int
    is_cover: bool
    created_at: datetime


class ItemRead(BaseModel):
    id: str
    collection_id: str
    collection_name: str
    name: str
    description: str | None
    quantity: int
    location: str | None
    photos: list[ItemPhotoRead]
    tags: list[TagRead]
    custom_values: dict[str, FieldValue]
    created_at: datetime
    updated_at: datetime


class ItemPage(BaseModel):
    items: list[ItemRead]
    total: int
    locations: list[str]


class CollectionsDashboard(BaseModel):
    collections: int
    items: int
    photos: int
    locations: int


class BulkOperation(BaseModel):
    item_ids: list[str] = Field(min_length=1, max_length=500)
    operation: Literal["move", "set_location", "add_tag", "remove_tag", "delete"]
    collection_id: str | None = None
    location: str | None = Field(default=None, max_length=500)
    tag_id: str | None = None


class BulkResult(BaseModel):
    affected: int
