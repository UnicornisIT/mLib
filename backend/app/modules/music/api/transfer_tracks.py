from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import AdminUser, CurrentUser
from app.core.config import Settings, get_settings
from app.database.session import get_music_db as get_db
from app.modules.music.library import (
    DuplicateTrackError,
    import_staged_file,
    pagination,
    serialize_catalog_track,
    serialize_track,
    track_query,
)
from app.modules.music.metadata import normalize_identity
from app.modules.music.models import CatalogTrack, Track
from app.modules.music.schemas import CatalogFileLink, CatalogFileResult, CatalogTrackPage, CatalogTrackRead
from app.modules.music.transfer.matching import match_for_track
from app.storage.service import LocalMediaStorage

# Registered before the job routes so that /transfer/tracks is not taken for a job id.
router = APIRouter(prefix="/transfer", tags=["music transfer"])

FILE_TAKEN = "У этого трека уже есть файл. Сначала отвяжите его."


def catalog_track_or_404(db: Session, catalog_track_id: str) -> CatalogTrack:
    item = db.scalar(
        select(CatalogTrack)
        .where(CatalogTrack.id == catalog_track_id)
        .options(selectinload(CatalogTrack.track))
        .execution_options(populate_existing=True)
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Трек каталога не найден")
    return item


def file_result(
    db: Session, user_id: str, catalog_track_id: str, result: Literal["added", "linked_existing"], detail: str
) -> CatalogFileResult:
    item = catalog_track_or_404(db, catalog_track_id)
    track, favorite = db.execute(track_query(user_id).where(Track.catalog_track_id == catalog_track_id)).one()
    return CatalogFileResult(
        status=result,
        detail=detail,
        catalog_track=serialize_catalog_track(item),
        track=serialize_track(track, favorite),
    )


def has_file_filter():
    return select(Track.id).where(Track.catalog_track_id == CatalogTrack.id).correlate(CatalogTrack).exists()


@router.get("/tracks", response_model=CatalogTrackPage)
def list_catalog_tracks(
    _: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    page: int = 1,
    page_size: int = 50,
    q: str | None = None,
    file_status: Annotated[Literal["all", "with_file", "without_file", "enriched", "not_found"], Query(alias="status")] = "all",
) -> CatalogTrackPage:
    page = max(1, page)
    page_size = min(200, max(1, page_size))
    filters = []
    if q and q.strip():
        # Normalized columns are already casefolded: SQLite LIKE ignores case only for ASCII.
        term = f"%{normalize_identity(q)}%"
        filters.append(
            or_(
                CatalogTrack.normalized_title.like(term),
                CatalogTrack.normalized_artist.like(term),
                CatalogTrack.album_title.ilike(f"%{q.strip()}%"),
            )
        )
    if file_status == "with_file":
        filters.append(has_file_filter())
    elif file_status == "without_file":
        filters.append(~has_file_filter())
    elif file_status == "enriched":
        filters.append(CatalogTrack.enrich_status == "enriched")
    elif file_status == "not_found":
        filters.append(CatalogTrack.enrich_status.in_(("not_found", "error")))
    total = int(db.scalar(select(func.count(CatalogTrack.id)).where(*filters)) or 0)
    offset, limit, pages = pagination(total, page, page_size)
    items = db.scalars(
        select(CatalogTrack)
        .where(*filters)
        .options(selectinload(CatalogTrack.track))
        .order_by(func.lower(CatalogTrack.artist_name), func.lower(CatalogTrack.title), CatalogTrack.id)
        .offset(offset)
        .limit(limit)
    ).all()
    return CatalogTrackPage(
        items=[serialize_catalog_track(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


@router.get("/tracks/{catalog_track_id}", response_model=CatalogTrackRead)
def get_catalog_track(
    catalog_track_id: str, _: CurrentUser, db: Annotated[Session, Depends(get_db)]
) -> CatalogTrackRead:
    return serialize_catalog_track(catalog_track_or_404(db, catalog_track_id))


@router.post("/tracks/{catalog_track_id}/file", response_model=CatalogFileResult, status_code=status.HTTP_201_CREATED)
async def upload_catalog_file(
    catalog_track_id: str,
    user: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    file: Annotated[UploadFile, File()],
) -> CatalogFileResult:
    """Stores the file for exactly this catalog track, whatever its tags say."""
    if catalog_track_or_404(db, catalog_track_id).track is not None:
        raise HTTPException(status_code=409, detail=FILE_TAKEN)
    storage = LocalMediaStorage(settings)
    staged = await storage.stage_upload(file)
    try:
        await run_in_threadpool(import_staged_file, db, staged, storage, settings, catalog_track_id=catalog_track_id)
    except DuplicateTrackError as exc:
        existing = exc.track
        if existing.catalog_track_id not in (None, catalog_track_id):
            raise HTTPException(
                status_code=409, detail="Этот файл уже есть в медиатеке и привязан к другому треку каталога"
            ) from exc
        existing.catalog_track_id = catalog_track_id
        db.commit()
        return file_result(db, user.id, catalog_track_id, "linked_existing", "Файл уже был в медиатеке и привязан")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc) or "Не удалось обработать файл") from exc
    return file_result(db, user.id, catalog_track_id, "added", "Файл добавлен")


@router.put("/tracks/{catalog_track_id}/file", response_model=CatalogFileResult)
def link_catalog_file(
    catalog_track_id: str,
    payload: CatalogFileLink,
    user: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> CatalogFileResult:
    item = catalog_track_or_404(db, catalog_track_id)
    track = db.get(Track, payload.track_id)
    if track is None:
        raise HTTPException(status_code=404, detail="Трек не найден")
    if item.track is not None and item.track.id != track.id:
        raise HTTPException(status_code=409, detail=FILE_TAKEN)
    if track.catalog_track_id not in (None, catalog_track_id):
        raise HTTPException(status_code=409, detail="Файл уже привязан к другому треку каталога")
    track.catalog_track_id = catalog_track_id
    db.commit()
    return file_result(db, user.id, catalog_track_id, "linked_existing", "Файл привязан")


@router.delete("/tracks/{catalog_track_id}/file", response_model=CatalogTrackRead)
def unlink_catalog_file(
    catalog_track_id: str, _: AdminUser, db: Annotated[Session, Depends(get_db)]
) -> CatalogTrackRead:
    """Detaches the file; it stays in the library as an ordinary track."""
    item = catalog_track_or_404(db, catalog_track_id)
    if item.track is None:
        raise HTTPException(status_code=404, detail="У этого трека нет файла")
    item.track.catalog_track_id = None
    db.commit()
    return serialize_catalog_track(catalog_track_or_404(db, catalog_track_id))


@router.get("/candidates/{track_id}", response_model=list[CatalogTrackRead])
def catalog_candidates(
    track_id: str, _: CurrentUser, db: Annotated[Session, Depends(get_db)]
) -> list[CatalogTrackRead]:
    """Catalog tracks without a file that may belong to this file, for a manual choice."""
    track = db.scalar(select(Track).where(Track.id == track_id).options(selectinload(Track.artist)))
    if track is None:
        raise HTTPException(status_code=404, detail="Трек не найден")
    match = match_for_track(db, track)
    found = [match.catalog_track] if match.catalog_track else match.candidates
    return [serialize_catalog_track(item) for item in found]
