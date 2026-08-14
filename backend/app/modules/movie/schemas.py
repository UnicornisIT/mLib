from datetime import date, datetime

from pydantic import BaseModel, Field


class WatchProgressRead(BaseModel):
    position: float
    duration: float
    completed: bool
    updated_at: datetime


class VideoFileRead(BaseModel):
    id: str
    display_title: str
    season_number: int | None = None
    episode_number: int | None = None
    episode_title: str | None = None
    original_filename: str
    file_size: int
    format: str
    mime_type: str
    duration: float
    video_codec: str | None = None
    audio_codec: str | None = None
    width: int | None = None
    height: int | None = None
    added_at: datetime
    progress: WatchProgressRead | None = None


class SeasonSummaryRead(BaseModel):
    season_number: int
    name: str
    episode_count: int
    air_date: date | None = None
    poster_url: str | None = None
    watched_count: int = 0


class TitleTrackingRead(BaseModel):
    status: str
    watched_at: datetime | None = None


class TitleTrackingUpdate(BaseModel):
    status: str = Field(min_length=3, max_length=24)


class CreditPersonRead(BaseModel):
    tmdb_id: int
    name: str
    role: str | None = None
    profile_url: str | None = None


class MediaTitleRead(BaseModel):
    id: str
    media_type: str
    title: str
    original_title: str | None = None
    year: int | None = None
    overview: str | None = None
    poster_url: str | None = None
    backdrop_url: str | None = None
    genres: list[str]
    tmdb_rating: float | None = None
    release_status: str | None = None
    next_air_date: date | None = None
    runtime_minutes: int | None = None
    episode_runtime_minutes: int | None = None
    total_episodes: int = 0
    total_seasons: int = 0
    seasons: list[SeasonSummaryRead] = Field(default_factory=list)
    directors: list[CreditPersonRead] = Field(default_factory=list)
    cast: list[CreditPersonRead] = Field(default_factory=list)
    tracking: TitleTrackingRead | None = None
    metadata_provider: str | None = None
    metadata_synced_at: datetime | None = None
    file_count: int
    watched_count: int
    progress_percent: float
    added_at: datetime


class MediaTitleDetail(MediaTitleRead):
    files: list[VideoFileRead]


class EpisodeRead(BaseModel):
    tmdb_episode_id: int | None = None
    season_number: int
    episode_number: int
    name: str
    overview: str | None = None
    air_date: date | None = None
    runtime_minutes: int = 0
    still_url: str | None = None
    watched: bool = False
    watched_at: datetime | None = None


class SeasonRead(BaseModel):
    season_number: int
    name: str
    overview: str | None = None
    episodes: list[EpisodeRead]
    watched_count: int
    episode_count: int


class EpisodeWatchUpdate(BaseModel):
    watched: bool


class ProfileSummaryRead(BaseModel):
    episodes: int
    movies: int
    minutes: int
    days: int


class ProfileActivityRead(BaseModel):
    date: date
    episodes: int
    movies: int
    minutes: int
    episode_minutes: int
    movie_minutes: int


class MovieProfileRead(BaseModel):
    username: str
    member_since: datetime
    summaries: dict[str, ProfileSummaryRead]
    activity: list[ProfileActivityRead]
    series_status_counts: dict[str, int]
    movie_status_counts: dict[str, int]
    series_titles: dict[str, list[MediaTitleRead]]
    movie_titles: dict[str, list[MediaTitleRead]]


class MediaTitlePage(BaseModel):
    items: list[MediaTitleRead]
    total: int
    page: int
    page_size: int
    pages: int


class TmdbCatalogTitleRead(BaseModel):
    tmdb_id: int
    media_type: str
    title: str
    original_title: str | None = None
    year: int | None = None
    overview: str | None = None
    poster_url: str | None = None
    backdrop_url: str | None = None
    tmdb_rating: float | None = None
    local_title_id: str | None = None
    file_count: int = 0
    match_reason: str | None = None


class TmdbCatalogPage(BaseModel):
    items: list[TmdbCatalogTitleRead]
    page: int
    pages: int
    total: int
    configured: bool


class PersonFilmographyRead(BaseModel):
    tmdb_id: int
    name: str
    known_for_department: str | None = None
    biography: str | None = None
    birthday: date | None = None
    place_of_birth: str | None = None
    profile_url: str | None = None
    items: list[TmdbCatalogTitleRead]


class ContinueWatchingRead(BaseModel):
    title: MediaTitleRead
    file: VideoFileRead | None = None


class MovieDashboardRead(BaseModel):
    titles: int
    movies: int
    series: int
    episodes: int
    continue_watching: list[ContinueWatchingRead]
    recently_added: list[MediaTitleRead]


class UploadCreate(BaseModel):
    filename: str = Field(min_length=1, max_length=1000)
    size: int = Field(ge=1)
    title_id: str | None = None


class UploadRead(BaseModel):
    id: str
    filename: str
    size: int
    offset: int
    status: str
    chunk_size: int = 8 * 1024 * 1024
    file_id: str | None = None
    title_id: str | None = None
    error: str | None = None


class WatchProgressUpdate(BaseModel):
    position: float = Field(ge=0)
    duration: float = Field(ge=0)
    completed: bool | None = None


class MovieSettingsRead(BaseModel):
    tmdb_enabled: bool
    metadata_refresh_hours: int
    storage_path: str
    library_size: int
    database: str


class MovieSettingsUpdate(BaseModel):
    tmdb_api_token: str | None = Field(default=None, max_length=1000)
    metadata_refresh_hours: int | None = Field(default=None, ge=1, le=720)
