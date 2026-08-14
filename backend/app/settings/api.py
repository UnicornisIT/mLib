import shutil
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.dependencies import AdminUser
from app.core.config import Settings, get_settings
from app.database.session import get_core_db, get_music_db
from app.modules.music.models import MusicSetting
from app.settings.models import CoreSetting
from app.settings.schemas import (
    AppearanceSettings,
    LibrarySettings,
    MetadataSettings,
    PlaybackSettings,
    SettingsRead,
    SettingsUpdate,
    SystemStatus,
)

router = APIRouter(prefix="/settings", tags=["music settings"])

DEFAULTS = {
    "embedded_metadata": "true",
    "musicbrainz_enabled": "false",
    "cover_art_archive_enabled": "false",
    "auto_artwork": "false",
    "save_volume": "true",
    "autoplay": "true",
    "default_repeat": "off",
    "theme": "system",
}


def music_value(db: Session, key: str, default: str = "") -> str:
    setting = db.get(MusicSetting, key)
    return setting.value if setting else DEFAULTS.get(key, default)


def core_value(db: Session, key: str, default: str = "") -> str:
    setting = db.get(CoreSetting, key)
    return setting.value if setting else default


def boolean(db: Session, key: str) -> bool:
    return music_value(db, key).lower() == "true"


def library_bytes(root: Path) -> int:
    if not root.exists():
        return 0
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def build_settings(music_db: Session, core_db: Session, settings: Settings) -> SettingsRead:
    try:
        music_db.execute(text("SELECT 1"))
        database_status = "connected"
    except Exception:
        database_status = "error"
    return SettingsRead(
        library=LibrarySettings(
            library_path=core_value(core_db, "library_path", str(settings.media_root)),
            import_path=music_value(music_db, "import_path", str(settings.import_root or "")),
            supported_extensions=list(settings.supported_audio_extensions),
        ),
        metadata=MetadataSettings(
            embedded_metadata=boolean(music_db, "embedded_metadata"),
            musicbrainz_enabled=boolean(music_db, "musicbrainz_enabled"),
            cover_art_archive_enabled=boolean(music_db, "cover_art_archive_enabled"),
            auto_artwork=boolean(music_db, "auto_artwork"),
        ),
        playback=PlaybackSettings(
            save_volume=boolean(music_db, "save_volume"),
            autoplay=boolean(music_db, "autoplay"),
            default_repeat=music_value(music_db, "default_repeat", "off"),
        ),
        appearance=AppearanceSettings(theme=music_value(music_db, "theme", "system")),
        system=SystemStatus(
            version=settings.app_version,
            ffmpeg_available=bool(shutil.which(settings.ffprobe_path)),
            database=database_status,
            library_size=library_bytes(settings.media_root / "music"),
        ),
    )


@router.get("", response_model=SettingsRead)
def read_settings(
    _: AdminUser,
    music_db: Annotated[Session, Depends(get_music_db)],
    core_db: Annotated[Session, Depends(get_core_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SettingsRead:
    return build_settings(music_db, core_db, settings)


@router.patch("", response_model=SettingsRead)
def update_settings(
    payload: SettingsUpdate,
    _: AdminUser,
    music_db: Annotated[Session, Depends(get_music_db)],
    core_db: Annotated[Session, Depends(get_core_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SettingsRead:
    values = payload.model_dump(exclude_unset=True)
    if import_path := values.get("import_path"):
        candidate = Path(str(import_path)).expanduser()
        if not candidate.is_dir():
            raise HTTPException(status_code=422, detail="Папка импорта не существует")
        values["import_path"] = str(candidate.resolve())
    for key, value in values.items():
        encoded = str(value).lower() if isinstance(value, bool) else str(value or "")
        setting = music_db.get(MusicSetting, key)
        if setting:
            setting.value = encoded
        else:
            music_db.add(MusicSetting(key=key, value=encoded))
    music_db.commit()
    return build_settings(music_db, core_db, settings)
