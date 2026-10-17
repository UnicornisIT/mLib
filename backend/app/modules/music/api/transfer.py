from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.auth.dependencies import AdminUser, CurrentUser
from app.core.config import Settings, get_settings
from app.core.security import utcnow
from app.database.session import get_music_db as get_db
from app.modules.music.models import CatalogTrack, TransferJob
from app.modules.music.schemas import TransferJobRead, TransferSummaryRead
from app.modules.music.transfer import worker as transfer_worker
from app.modules.music.transfer.service import (
    ACTIVE_STATUSES,
    finish_job,
    import_library,
    import_playlists,
    pending_count,
)
from app.modules.music.transfer.sources import MAX_SOURCE_BYTES, SOURCES, AppleMusicCsvSource, LibraryParseError

router = APIRouter(prefix="/transfer", tags=["music transfer"])


def serialize_job(db: Session, job: TransferJob) -> TransferJobRead:
    return TransferJobRead(
        id=job.id,
        source=job.source,
        filename=job.filename,
        status=job.status,
        storefronts=[value for value in job.storefronts.split(",") if value],
        create_playlists=job.create_playlists,
        rows_total=job.rows_total,
        unique_total=job.unique_total,
        added=job.added,
        existing=job.existing,
        enriched=job.enriched,
        not_found=job.not_found,
        errors=job.errors,
        invalid_rows=job.invalid_rows,
        pending=pending_count(db, job.id) if job.status in ACTIVE_STATUSES else 0,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
        finished_at=job.finished_at,
    )


def get_job(db: Session, job_id: str, owner_id: str) -> TransferJob:
    job = db.scalar(select(TransferJob).where(TransferJob.id == job_id, TransferJob.owner_id == owner_id))
    if job is None:
        raise HTTPException(status_code=404, detail="Перенос фонотеки не найден")
    return job


@router.post("", response_model=TransferJobRead, status_code=status.HTTP_202_ACCEPTED)
async def start_transfer(
    user: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    file: Annotated[UploadFile, File()],
    create_playlists: Annotated[bool, Form()] = False,
) -> TransferJobRead:
    filename = Path(file.filename or "library.csv").name
    if Path(filename).suffix.lower() not in {".csv", ".txt"}:
        raise HTTPException(status_code=422, detail="Загрузите экспорт фонотеки в формате CSV")
    data = await file.read(MAX_SOURCE_BYTES + 1)
    source = SOURCES[AppleMusicCsvSource.name]
    try:
        parsed = source.parse(data)
    except LibraryParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    job = TransferJob(
        owner_id=user.id,
        source=source.name,
        filename=filename,
        status="queued",
        storefronts=",".join(settings.itunes_storefronts) or "us",
        create_playlists=create_playlists,
    )
    db.add(job)
    db.flush()
    resolved = import_library(db, job, parsed)
    if create_playlists and parsed.playlists:
        import_playlists(db, user.id, parsed.playlists, resolved)
    if pending_count(db, job.id):
        job.status = "enriching"
    else:
        finish_job(db, job)
    db.commit()
    db.refresh(job)
    if job.status == "enriching":
        transfer_worker.ensure_worker()
    return serialize_job(db, job)


@router.get("/summary", response_model=TransferSummaryRead)
def transfer_summary(_: CurrentUser, db: Annotated[Session, Depends(get_db)]) -> TransferSummaryRead:
    rows = db.execute(
        select(CatalogTrack.enrich_status, func.count(CatalogTrack.id)).group_by(CatalogTrack.enrich_status)
    )
    counts = {status_value: int(count) for status_value, count in rows}
    return TransferSummaryRead(
        total=sum(counts.values()),
        enriched=counts.get("enriched", 0),
        not_found=counts.get("not_found", 0) + counts.get("error", 0),
        pending=counts.get("pending", 0),
    )


@router.get("/latest", response_model=TransferJobRead | None)
def latest_transfer(user: CurrentUser, db: Annotated[Session, Depends(get_db)]) -> TransferJobRead | None:
    job = db.scalar(
        select(TransferJob).where(TransferJob.owner_id == user.id).order_by(TransferJob.created_at.desc()).limit(1)
    )
    return serialize_job(db, job) if job else None


@router.get("/{job_id}", response_model=TransferJobRead)
def transfer_status(job_id: str, user: CurrentUser, db: Annotated[Session, Depends(get_db)]) -> TransferJobRead:
    return serialize_job(db, get_job(db, job_id, user.id))


@router.post("/{job_id}/cancel", response_model=TransferJobRead)
def cancel_transfer(job_id: str, user: AdminUser, db: Annotated[Session, Depends(get_db)]) -> TransferJobRead:
    job = get_job(db, job_id, user.id)
    if job.status not in ACTIVE_STATUSES:
        raise HTTPException(status_code=409, detail="Перенос уже завершён")
    finish_job(db, job, status="cancelled")
    db.commit()
    db.refresh(job)
    return serialize_job(db, job)


@router.post("/{job_id}/retry", response_model=TransferJobRead)
def retry_transfer(job_id: str, user: AdminUser, db: Annotated[Session, Depends(get_db)]) -> TransferJobRead:
    """Looks up again the tracks Apple did not return (and those left pending by a cancel)."""
    job = get_job(db, job_id, user.id)
    if job.status in ACTIVE_STATUSES:
        raise HTTPException(status_code=409, detail="Перенос ещё выполняется")
    result = db.execute(
        update(CatalogTrack)
        .where(
            CatalogTrack.transfer_job_id == job.id,
            CatalogTrack.enrich_status.in_(("not_found", "error", "pending")),
        )
        .values(enrich_status="pending", enrich_attempts=0, enriched_at=None)
    )
    if not result.rowcount:
        raise HTTPException(status_code=409, detail="Все треки этого переноса уже найдены в Apple Music")
    job.status = "enriching"
    job.error_message = None
    job.finished_at = None
    job.worker_token = None
    job.heartbeat_at = None
    job.updated_at = utcnow()
    db.commit()
    db.refresh(job)
    transfer_worker.ensure_worker()
    return serialize_job(db, job)
