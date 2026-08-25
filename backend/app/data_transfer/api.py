from collections.abc import Callable
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import AdminUser
from app.core.config import Settings, get_settings
from app.data_transfer.schemas import DataOperationResult, DataPathRequest, DataTransferStatus
from app.data_transfer.service import (
    EXPORT_VERSION,
    SCHEMA_VERSION,
    DataTransferError,
    create_backup,
    create_portable_export,
    import_portable_export,
    restore_backup_with_client_state,
)

router = APIRouter(prefix="/data", tags=["data transfer"])


def _desktop_only(settings: Settings) -> None:
    if not settings.is_desktop:
        raise HTTPException(status_code=404, detail="Desktop data dialogs are unavailable in server mode")


def _run(operation: Callable[[], tuple[Path, Path | None] | Path], kind: str, message: str) -> DataOperationResult:
    try:
        result = operation()
    except DataTransferError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Не удалось выполнить файловую операцию") from exc
    if isinstance(result, tuple):
        path, safety = result
    else:
        path, safety = result, None
    return DataOperationResult(
        status="completed",
        path=str(path),
        kind=kind,
        message=message,
        safety_backup=str(safety) if safety else None,
    )


@router.get("/status", response_model=DataTransferStatus)
def data_status(
    _: AdminUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DataTransferStatus:
    return DataTransferStatus(
        desktop=settings.is_desktop,
        data_root=str(settings.data_root) if settings.is_desktop else None,
        media_root=str(settings.media_root),
        backups_root=str(settings.backups_root),
        export_version=EXPORT_VERSION,
        schema_version=SCHEMA_VERSION,
    )


@router.post("/export", response_model=DataOperationResult)
def export_library(
    payload: DataPathRequest,
    _: AdminUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DataOperationResult:
    _desktop_only(settings)
    return _run(
        lambda: create_portable_export(Path(payload.path), settings),
        "export",
        "Переносимый экспорт библиотеки создан",
    )


@router.post("/import", response_model=DataOperationResult)
def import_library(
    payload: DataPathRequest,
    _: AdminUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DataOperationResult:
    _desktop_only(settings)
    return _run(
        lambda: import_portable_export(Path(payload.path), settings),
        "import",
        "Библиотека импортирована; защитная копия предыдущих данных сохранена",
    )


@router.post("/backup", response_model=DataOperationResult)
def backup_library(
    payload: DataPathRequest,
    _: AdminUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DataOperationResult:
    _desktop_only(settings)
    return _run(
        lambda: create_backup(Path(payload.path), settings, client_state=payload.client_state),
        "backup",
        "Резервная копия создана",
    )


@router.post("/restore", response_model=DataOperationResult)
def restore_library(
    payload: DataPathRequest,
    _: AdminUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DataOperationResult:
    _desktop_only(settings)
    try:
        path, safety, client_state = restore_backup_with_client_state(Path(payload.path), settings)
    except DataTransferError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Не удалось выполнить файловую операцию") from exc
    return DataOperationResult(
        status="completed",
        path=str(path),
        kind="restore",
        message="Резервная копия восстановлена; предыдущие данные сохранены отдельно",
        safety_backup=str(safety) if safety else None,
        client_state=client_state,
    )
