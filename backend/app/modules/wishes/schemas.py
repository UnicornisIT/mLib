from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

WishCategory = Literal["watch", "read", "listen", "buy"]
WishTargetType = Literal["movie", "series", "book", "album", "game", "item", "other"]
WishStatus = Literal["active", "fulfilled"]


class WishFields(BaseModel):
    category: WishCategory
    target_type: WishTargetType
    title: str = Field(min_length=1, max_length=500)
    creator: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=4000)
    reference_url: str | None = Field(default=None, max_length=4000)
    image_url: str | None = Field(default=None, max_length=4000)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Укажите название желания")
        return value.strip()

    @field_validator("creator", "notes", "reference_url", "image_url")
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None


class WishCreate(WishFields):
    pass


class WishUpdate(BaseModel):
    category: WishCategory | None = None
    target_type: WishTargetType | None = None
    title: str | None = Field(default=None, min_length=1, max_length=500)
    creator: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=4000)
    reference_url: str | None = Field(default=None, max_length=4000)
    image_url: str | None = Field(default=None, max_length=4000)
    status: WishStatus | None = None

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Укажите название желания")
        return value.strip() if value else value

    @field_validator("creator", "notes", "reference_url", "image_url")
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None


class WishRead(WishFields):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: WishStatus
    matched_service: str | None
    matched_item_id: str | None
    auto_fulfilled: bool
    created_at: datetime
    updated_at: datetime
    fulfilled_at: datetime | None


class WishPage(BaseModel):
    items: list[WishRead]
    total: int


class WishesDashboard(BaseModel):
    total: int
    active: int
    fulfilled: int
    auto_fulfilled: int
    by_category: dict[WishCategory, int]
