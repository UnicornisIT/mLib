from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "mLib"
    app_version: str = "0.0.1-alpha"
    app_mode: Literal["desktop", "server"] = "server"
    environment: Literal["development", "test", "production"] = "development"
    api_prefix: str = "/api"
    secret_key: str = "change-me-before-production"
    session_ttl_hours: int = 24 * 30
    database_url: str = "sqlite:///./mlib.db"
    core_database_url: str = "sqlite:///./core.db"
    music_database_url: str = "sqlite:///./music.db"
    movie_database_url: str = "sqlite:///./movie.db"
    books_database_url: str = "sqlite:///./books.db"
    collections_database_url: str = "sqlite:///./collections.db"
    games_database_url: str = "sqlite:///./games.db"
    wishes_database_url: str = "sqlite:///./wishes.db"
    media_root: Path = Path("./media")
    data_root: Path = Path("./data")
    backups_root: Path = Path("./backups")
    temp_root: Path = Path("./temp")
    log_file: Path | None = None
    desktop_token: str | None = None
    import_root: Path | None = None
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["http://localhost:3000"])
    max_upload_mb: int = 1024
    cookie_secure: bool = False
    log_level: str = "INFO"
    ffprobe_path: str = "ffprobe"
    tmdb_api_token: str | None = None
    movie_metadata_refresh_hours: int = 24
    supported_audio_extensions: tuple[str, ...] = (
        ".mp3",
        ".flac",
        ".m4a",
        ".aac",
        ".ogg",
        ".wav",
        ".opus",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def validate_production_secret(self) -> "Settings":
        unsafe_values = {
            "change-me-before-production",
            "replace-with-a-long-random-secret",
        }
        if self.environment == "production" and (
            len(self.secret_key) < 32 or self.secret_key in unsafe_values
        ):
            raise ValueError("SECRET_KEY must be a unique random value of at least 32 characters in production")
        return self

    @property
    def originals_dir(self) -> Path:
        return self.media_root / "music" / "originals"

    @property
    def artwork_dir(self) -> Path:
        return self.media_root / "music" / "artwork"

    @property
    def staging_dir(self) -> Path:
        return self.media_root / "music" / "staging"

    @property
    def movie_originals_dir(self) -> Path:
        return self.media_root / "movie" / "originals"

    @property
    def movie_staging_dir(self) -> Path:
        return self.media_root / "movie" / "staging"

    @property
    def books_originals_dir(self) -> Path:
        return self.media_root / "books" / "originals"

    @property
    def books_covers_dir(self) -> Path:
        return self.media_root / "books" / "covers"

    @property
    def books_staging_dir(self) -> Path:
        return self.media_root / "books" / "staging"

    @property
    def collections_photos_dir(self) -> Path:
        return self.media_root / "collections" / "photos"

    @property
    def collections_staging_dir(self) -> Path:
        return self.media_root / "collections" / "staging"

    @property
    def is_desktop(self) -> bool:
        return self.app_mode == "desktop"


@lru_cache
def get_settings() -> Settings:
    return Settings()
