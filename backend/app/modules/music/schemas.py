from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ArtworkRead(BaseModel):
    id: str
    url: str


class ArtistBrief(BaseModel):
    id: str
    name: str


class AlbumBrief(BaseModel):
    id: str
    title: str
    album_artist: str
    year: int | None = None
    artwork_id: str | None = None


class TrackRead(BaseModel):
    id: str
    uuid: str
    title: str
    artist: ArtistBrief
    album: AlbumBrief | None = None
    album_artist: str | None = None
    genre: str | None = None
    year: int | None = None
    track_number: int | None = None
    disc_number: int | None = None
    composer: str | None = None
    copyright: str | None = None
    comment: str | None = None
    duration: float
    file_size: int
    format: str
    codec: str | None = None
    bitrate: int | None = None
    sample_rate: int | None = None
    channels: int | None = None
    artwork_id: str | None = None
    favorite: bool = False
    needs_attention: bool = False
    metadata_status: Literal["complete", "incomplete", "critical", "reviewed"] = "complete"
    metadata_issues: list[
        Literal["missing_title", "unknown_artist", "missing_album", "missing_genre", "missing_year"]
    ] = Field(default_factory=list)
    play_count: int
    last_played_at: datetime | None = None
    date_added: datetime
    date_modified: datetime


class TrackUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    artist: str | None = Field(default=None, min_length=1, max_length=255)
    album: str | None = Field(default=None, min_length=1, max_length=500)
    album_artist: str | None = Field(default=None, max_length=255)
    genre: str | None = Field(default=None, max_length=255)
    year: int | None = Field(default=None, ge=0, le=9999)
    track_number: int | None = Field(default=None, ge=0)
    disc_number: int | None = Field(default=None, ge=0)
    composer: str | None = Field(default=None, max_length=500)
    comment: str | None = Field(default=None, max_length=5000)

    @field_validator("title", "artist", mode="before")
    @classmethod
    def normalize_required_text(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                raise ValueError("Значение не может быть пустым")
            return normalized
        return value

    @field_validator("album", "album_artist", "genre", "composer", "comment", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value


class Page(BaseModel):
    items: list[TrackRead]
    page: int
    page_size: int
    total: int
    pages: int


class MetadataAttentionSummary(BaseModel):
    total: int


class AlbumRead(BaseModel):
    id: str
    title: str
    album_artist: str
    artist: ArtistBrief | None = None
    year: int | None = None
    genre: str | None = None
    artwork_id: str | None = None
    track_count: int
    duration: float


class AlbumDetail(AlbumRead):
    tracks: list[TrackRead]


class AlbumPage(BaseModel):
    items: list[AlbumRead]
    page: int
    page_size: int
    total: int
    pages: int


class ArtistRead(BaseModel):
    id: str
    name: str
    sort_name: str
    artwork_id: str | None = None
    album_count: int
    track_count: int


class ArtistDetail(ArtistRead):
    albums: list[AlbumRead]
    tracks: list[TrackRead]


class ArtistPage(BaseModel):
    items: list[ArtistRead]
    page: int
    page_size: int
    total: int
    pages: int


class GenreRead(BaseModel):
    name: str
    track_count: int
    album_count: int


class UploadResult(BaseModel):
    filename: str
    status: str
    detail: str
    track: TrackRead | None = None


class ImportRequest(BaseModel):
    path: str


class ImportJobRead(BaseModel):
    id: str
    path: str
    status: str
    found: int = 0
    processed: int = 0
    added: int = 0
    skipped: int = 0
    errors: int = 0
    current_file: str | None = None
    error_message: str | None = None


class PlaylistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Название плейлиста не может быть пустым")
        return normalized

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value


class PlaylistUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def normalize_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Название плейлиста не может быть пустым")
        return normalized

    @field_validator("description", mode="before")
    @classmethod
    def normalize_optional_description(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value


class PlaylistItemRead(BaseModel):
    id: str
    position: int
    track: TrackRead


class PlaylistRead(BaseModel):
    id: str
    name: str
    description: str | None = None
    is_system: bool
    created_at: datetime
    updated_at: datetime
    track_count: int
    duration: float
    items: list[PlaylistItemRead] | None = None


class PlaylistTrackAdd(BaseModel):
    track_id: str
    position: int | None = Field(default=None, ge=0)


class PlaylistReorder(BaseModel):
    item_ids: list[str]


class DashboardRead(BaseModel):
    tracks: int
    albums: int
    artists: int
    genres: int
    duration: float
    recently_added: list[TrackRead]
    recently_played: list[TrackRead]
    albums_recent: list[AlbumRead]


class SearchRead(BaseModel):
    tracks: list[TrackRead]
    albums: list[AlbumRead]
    artists: list[ArtistRead]
