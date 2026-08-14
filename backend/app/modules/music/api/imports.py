from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import AdminUser
from app.core.config import Settings, get_settings
from app.database.session import get_music_db as get_db
from app.modules.music.models import MusicSetting
from app.modules.music.scanner import jobs, scan_directory
from app.modules.music.schemas import ImportJobRead, ImportRequest

router = APIRouter(prefix="/imports", tags=["music import"])


def configured_import_root(db: Session, settings: Settings) -> Path | None:
    if settings.import_root:
        return settings.import_root.resolve()
    value = db.get(MusicSetting, "import_path")
    return Path(value.value).expanduser().resolve() if value and value.value else None


@router.post("", response_model=ImportJobRead, status_code=status.HTTP_202_ACCEPTED)
def start_import(
    payload: ImportRequest,
    background_tasks: BackgroundTasks,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ImportJobRead:
    requested = Path(payload.path).expanduser().resolve()
    allowed = configured_import_root(db, settings)
    if allowed is None:
        raise HTTPException(status_code=409, detail="Сначала укажите разрешённую папку импорта в настройках")
    if requested != allowed and allowed not in requested.parents:
        raise HTTPException(status_code=403, detail="Папка находится вне разрешённой директории импорта")
    if not requested.is_dir():
        raise HTTPException(status_code=404, detail="Папка импорта не найдена")
    job = jobs.create(requested)
    background_tasks.add_task(scan_directory, job.id, requested, settings)
    return ImportJobRead(**jobs.snapshot(job.id))


@router.get("/{job_id}", response_model=ImportJobRead)
def import_status(job_id: str, _: AdminUser) -> ImportJobRead:
    job = jobs.snapshot(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Задача импорта не найдена")
    return ImportJobRead(**job)
