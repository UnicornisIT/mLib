from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


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


class CatalogTrackBrief(BaseModel):
    """Catalog data shown for a file linked to a catalog track; the file's own tags stay untouched."""

    id: str
    apple_track_id: str | None = None
    isrc: str | None = None
    title: str
    artist_name: str
    album_title: str | None = None
    collection_id: str | None = None
    # Catalog album this track belongs to: same album title and lead artist.
    album_key: str | None = None
    artist_key: str | None = None
    genre: str | None = None
    year: int | None = None
    duration_ms: int | None = None
    # Apple artwork is only linked, never downloaded; artwork embedded in the file takes priority.
    artwork_url: str | None = None
    apple_music_url: str | None = None
    # Search link: Spotify ids are not part of the Apple export.
    spotify_url: str


class CatalogTrackRead(CatalogTrackBrief):
    enrich_status: Literal["pending", "enriched", "not_found", "error"]
    has_file: bool
    track_id: str | None = None
    # Artwork embedded in the linked file; shown instead of artwork_url when present.
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
    catalog: CatalogTrackBrief | None = None
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


class CatalogGenreRead(GenreRead):
    # Catalog tracks of the genre; the rest are library files that are not linked to the catalog.
    catalog_count: int


class UploadResult(BaseModel):
    filename: str
    status: str
    detail: str
    track: TrackRead | None = None
    catalog_track_id: str | None = None
    catalog_candidates: int = 0


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
    linked: int = 0
    ambiguous_track_ids: list[str] = Field(default_factory=list)
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
    # The playable file: the entry's own track, or the file attached to its catalog track.
    track: TrackRead | None = None
    catalog_track: CatalogTrackRead | None = None


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
    track_id: str | None = None
    catalog_track_id: str | None = None
    position: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def require_one_source(self) -> "PlaylistTrackAdd":
        if (self.track_id is None) == (self.catalog_track_id is None):
            raise ValueError("Укажите либо трек, либо трек из каталога")
        return self


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


class TransferJobRead(BaseModel):
    id: str
    source: str
    filename: str
    status: Literal["queued", "enriching", "completed", "failed", "cancelled"]
    storefronts: list[str]
    create_playlists: bool
    rows_total: int
    unique_total: int
    added: int
    existing: int
    enriched: int
    not_found: int
    errors: int
    invalid_rows: int
    pending: int
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None = None


class TransferSummaryRead(BaseModel):
    total: int
    enriched: int
    not_found: int
    pending: int


class CatalogTrackPage(BaseModel):
    items: list[CatalogTrackRead]
    page: int
    page_size: int
    total: int
    pages: int


class CatalogAlbumRead(BaseModel):
    """Catalog tracks with the same album title and lead artist, across Apple editions."""

    key: str
    title: str
    # Lead artist shared by the tracks: "Daft Punk & X" and "Daft Punk, Y" give "Daft Punk".
    artist_name: str
    # Catalog artist page of the lead artist; none for "various artists".
    artist_key: str | None = None
    year: int | None = None
    artwork_url: str | None = None
    artwork_id: str | None = None
    apple_music_url: str | None = None
    track_count: int
    with_file: int
    # Library albums built from the tags of linked files; the catalog album stands in for them.
    local_album_ids: list[str] = []


class CatalogAlbumDetail(CatalogAlbumRead):
    tracks: list[CatalogTrackRead]


class CatalogArtistRead(BaseModel):
    """Lead artist of catalog tracks; featured artists stay on the track of the lead artist."""

    key: str
    name: str
    artwork_url: str | None = None
    artwork_id: str | None = None
    album_count: int
    track_count: int
    with_file: int
    # Library artists built from the tags of linked files; the catalog artist stands in for them.
    local_artist_ids: list[str] = []


class CatalogArtistDetail(CatalogArtistRead):
    albums: list[CatalogAlbumRead]
    tracks: list[CatalogTrackRead]


class CatalogFileLink(BaseModel):
    track_id: str


class CatalogFileResult(BaseModel):
    status: Literal["added", "linked_existing"]
    detail: str
    catalog_track: CatalogTrackRead
    track: TrackRead
