from pydantic import BaseModel, Field


class LibrarySettings(BaseModel):
    library_path: str
    import_path: str
    supported_extensions: list[str]


class MetadataSettings(BaseModel):
    embedded_metadata: bool
    musicbrainz_enabled: bool
    cover_art_archive_enabled: bool
    auto_artwork: bool


class PlaybackSettings(BaseModel):
    save_volume: bool
    autoplay: bool
    default_repeat: str


class AppearanceSettings(BaseModel):
    theme: str


class SystemStatus(BaseModel):
    version: str
    ffmpeg_available: bool
    database: str
    library_size: int


class SettingsRead(BaseModel):
    library: LibrarySettings
    metadata: MetadataSettings
    playback: PlaybackSettings
    appearance: AppearanceSettings
    system: SystemStatus


class SettingsUpdate(BaseModel):
    import_path: str | None = None
    embedded_metadata: bool | None = None
    musicbrainz_enabled: bool | None = None
    cover_art_archive_enabled: bool | None = None
    auto_artwork: bool | None = None
    save_volume: bool | None = None
    autoplay: bool | None = None
    default_repeat: str | None = Field(default=None, pattern="^(off|all|one)$")
    theme: str | None = Field(default=None, pattern="^(dark|light|system)$")
