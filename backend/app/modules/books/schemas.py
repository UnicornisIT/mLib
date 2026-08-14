from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class BookRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    media_type: Literal["ebook", "audiobook"]
    title: str
    author: str
    description: str | None
    genre: str | None
    language: str | None
    publication_year: int | None
    publisher: str | None
    isbn: str | None
    narrator: str | None
    page_count: int | None
    duration: float | None
    original_filename: str
    file_size: int
    format: str
    mime_type: str
    has_cover: bool
    added_at: datetime
    updated_at: datetime


class BookPage(BaseModel):
    items: list[BookRead]
    total: int


class BooksDashboard(BaseModel):
    total: int
    ebooks: int
    audiobooks: int
    authors: int
    storage_bytes: int
