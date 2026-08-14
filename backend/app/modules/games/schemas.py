from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

GameStatus = Literal["not_started", "playing", "completed", "completed_100", "abandoned"]
GamePlatform = Literal["PC", "PlayStation", "Xbox", "Switch", "Retro"]
Screenshots = Annotated[list[str], Field(max_length=12)]


def clean_optional(value: str | None) -> str | None:
    return value.strip() if value and value.strip() else None


class GameFields(BaseModel):
    developer: str | None = Field(default=None, max_length=500)
    publisher: str | None = Field(default=None, max_length=500)
    release_year: int | None = Field(default=None, ge=1950, le=2100)
    genre: str | None = Field(default=None, max_length=255)
    platform: GamePlatform = "PC"
    purchase_date: date | None = None
    acquired_from: str | None = Field(default=None, max_length=255)
    status: GameStatus = "not_started"
    playtime_minutes: int = Field(default=0, ge=0, le=10_000_000)
    personal_rating: float | None = Field(default=None, ge=0, le=10)
    achievements_unlocked: int = Field(default=0, ge=0, le=100_000)
    achievements_total: int = Field(default=0, ge=0, le=100_000)
    cover_url: str | None = Field(default=None, max_length=4000)
    screenshots: Screenshots = Field(default_factory=list)

    @field_validator("developer", "publisher", "genre", "acquired_from", "cover_url")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return clean_optional(value)

    @field_validator("screenshots")
    @classmethod
    def normalize_screenshots(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in value if item.strip()))

    @model_validator(mode="after")
    def check_achievements(self):
        if self.achievements_unlocked > self.achievements_total and self.achievements_total > 0:
            raise ValueError("Полученных достижений не может быть больше общего количества")
        return self


class GameCreate(GameFields):
    title: str = Field(min_length=1, max_length=500)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Укажите название игры")
        return value.strip()


class GameUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    developer: str | None = Field(default=None, max_length=500)
    publisher: str | None = Field(default=None, max_length=500)
    release_year: int | None = Field(default=None, ge=1950, le=2100)
    genre: str | None = Field(default=None, max_length=255)
    platform: GamePlatform | None = None
    purchase_date: date | None = None
    acquired_from: str | None = Field(default=None, max_length=255)
    status: GameStatus | None = None
    playtime_minutes: int | None = Field(default=None, ge=0, le=10_000_000)
    personal_rating: float | None = Field(default=None, ge=0, le=10)
    achievements_unlocked: int | None = Field(default=None, ge=0, le=100_000)
    achievements_total: int | None = Field(default=None, ge=0, le=100_000)
    cover_url: str | None = Field(default=None, max_length=4000)
    screenshots: Screenshots | None = None

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Укажите название игры")
        return value.strip() if value else value

    @field_validator("developer", "publisher", "genre", "acquired_from", "cover_url")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return clean_optional(value)

    @field_validator("screenshots")
    @classmethod
    def normalize_screenshots(cls, value: list[str] | None) -> list[str] | None:
        return list(dict.fromkeys(item.strip() for item in value if item.strip())) if value is not None else None


class GameRead(GameCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime


class GamePage(BaseModel):
    items: list[GameRead]
    total: int


class GamesDashboard(BaseModel):
    total: int
    playing: int
    completed: int
    completed_100: int
    playtime_minutes: int
    achievements_unlocked: int
    achievements_total: int
