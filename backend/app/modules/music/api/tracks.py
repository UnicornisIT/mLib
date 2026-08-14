import logging
import mimetypes
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Header, HTTPException, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import AdminUser, CurrentUser
from app.core.config import Settings, get_settings
from app.core.security import utcnow
from app.database.session import get_music_db as get_db
from app.modules.music.library import (
    DuplicateTrackError,
    import_staged_file,
    pagination,
    serialize_track,
    track_query,
    update_track_metadata,
)
from app.modules.music.models import Album, Artist, Artwork, Favorite, Track
from app.modules.music.quality import attention_filter
from app.modules.music.schemas import MetadataAttentionSummary, Page, TrackRead, TrackUpdate, UploadResult
from app.storage.service import LocalMediaStorage

logger = logging.getLogger(__name__)
router = APIRouter(tags=["music tracks"])


def get_track_or_404(db: Session, track_id: str) -> Track:
    track = db.scalar(
        select(Track).where(Track.id == track_id).options(selectinload(Track.artist), selectinload(Track.album))
    )
    if track is None:
        raise HTTPException(status_code=404, detail="Трек не найден")
    return track


@router.get("/tracks", response_model=Page)
def list_tracks(
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    page: int = 1,
    page_size: int = 50,
    q: str | None = None,
    genre: str | None = None,
    favorite: bool = False,
    attention: bool = False,
    sort: str = "date_added",
    order: str = "desc",
) -> Page:
    page = max(1, page)
    page_size = min(200, max(1, page_size))
    predicates = []
    joins_artist = bool(q) or attention
    if q:
        term = f"%{q.strip()}%"
        predicates.append(or_(Track.title.ilike(term), Artist.name.ilike(term), Album.title.ilike(term)))
    if genre:
        predicates.append(func.lower(Track.genre) == genre.strip().lower())

    count_stmt = select(func.count(func.distinct(Track.id))).select_from(Track)
    stmt = track_query(user.id)
    if joins_artist:
        stmt = stmt.join(Artist).outerjoin(Album)
        count_stmt = count_stmt.join(Artist).outerjoin(Album)
    if favorite:
        favorite_filter = (
            select(Favorite.track_id)
            .where(Favorite.track_id == Track.id, Favorite.user_id == user.id)
            .correlate(Track)
            .exists()
        )
        stmt = stmt.where(favorite_filter)
        count_stmt = count_stmt.where(favorite_filter)
    if attention:
        predicates.append(attention_filter())
    if predicates:
        stmt = stmt.where(*predicates)
        count_stmt = count_stmt.where(*predicates)

    sort_columns = {
        "title": Track.title,
        "artist": Artist.name,
        "album": Album.title,
        "year": Track.year,
        "duration": Track.duration,
        "date_added": Track.date_added,
    }
    sort_column = sort_columns.get(sort, Track.date_added)
    if sort in {"artist", "album"} and not joins_artist:
        stmt = stmt.join(Artist).outerjoin(Album)
    direction = asc if order == "asc" else desc
    total = int(db.scalar(count_stmt) or 0)
    offset, limit, pages = pagination(total, page, page_size)
    rows = db.execute(stmt.order_by(direction(sort_column), Track.id).offset(offset).limit(limit)).all()
    return Page(
        items=[serialize_track(track, favorite_value) for track, favorite_value in rows],
        page=page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


@router.get("/tracks/attention-summary", response_model=MetadataAttentionSummary)
def metadata_attention_summary(_: CurrentUser, db: Annotated[Session, Depends(get_db)]) -> MetadataAttentionSummary:
    total = db.scalar(select(func.count(Track.id)).select_from(Track).join(Artist).where(attention_filter()))
    return MetadataAttentionSummary(total=int(total or 0))


@router.get("/tracks/{track_id}", response_model=TrackRead)
def get_track(track_id: str, user: CurrentUser, db: Annotated[Session, Depends(get_db)]) -> TrackRead:
    row = db.execute(track_query(user.id).where(Track.id == track_id)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Трек не найден")
    return serialize_track(row[0], row[1])


@router.patch("/tracks/{track_id}", response_model=TrackRead)
def edit_track(
    track_id: str,
    payload: TrackUpdate,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> TrackRead:
    track = get_track_or_404(db, track_id)
    values = payload.model_dump(exclude_unset=True)
    update_track_metadata(db, track, values)
    row = db.execute(track_query(user.id).where(Track.id == track_id)).one()
    return serialize_track(row[0], row[1])


@router.post("/tracks/{track_id}/metadata-reviewed", response_model=TrackRead)
def mark_metadata_reviewed(
    track_id: str,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> TrackRead:
    track = get_track_or_404(db, track_id)
    track.metadata_reviewed_at = utcnow()
    db.commit()
    row = db.execute(track_query(user.id).where(Track.id == track_id)).one()
    return serialize_track(row[0], row[1])


@router.delete("/tracks/{track_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_track(
    track_id: str,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    track = get_track_or_404(db, track_id)
    storage = LocalMediaStorage(settings)
    try:
        path = storage.ensure_managed_path(settings.media_root / track.file_path)
        path.unlink(missing_ok=True)
    except (OSError, ValueError) as exc:
        logger.error("Failed to remove track file %s: %s", track.id, exc)
        raise HTTPException(status_code=500, detail="Не удалось удалить аудиофайл") from exc
    db.delete(track)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/tracks/{track_id}/favorite", response_model=TrackRead)
def favorite_track(track_id: str, user: CurrentUser, db: Annotated[Session, Depends(get_db)]) -> TrackRead:
    track = get_track_or_404(db, track_id)
    favorite = db.get(Favorite, (user.id, track_id))
    if favorite is None:
        db.add(Favorite(user_id=user.id, track_id=track_id))
        db.commit()
    return serialize_track(track, True)


@router.delete("/tracks/{track_id}/favorite", response_model=TrackRead)
def unfavorite_track(track_id: str, user: CurrentUser, db: Annotated[Session, Depends(get_db)]) -> TrackRead:
    track = get_track_or_404(db, track_id)
    favorite = db.get(Favorite, (user.id, track_id))
    if favorite:
        db.delete(favorite)
        db.commit()
    return serialize_track(track, False)


@router.post("/tracks/{track_id}/played", status_code=status.HTTP_204_NO_CONTENT)
def record_play(track_id: str, _: CurrentUser, db: Annotated[Session, Depends(get_db)]) -> Response:
    track = get_track_or_404(db, track_id)
    track.play_count += 1
    track.last_played_at = utcnow()
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def parse_range_header(value: str, file_size: int) -> tuple[int, int]:
    if not value.lower().startswith("bytes=") or "," in value:
        raise ValueError("Поддерживается только один диапазон bytes")
    start_text, separator, end_text = value[6:].partition("-")
    if not separator:
        raise ValueError("Некорректный Range")
    if not start_text:
        suffix = int(end_text)
        if suffix <= 0:
            raise ValueError("Некорректный суффикс Range")
        start = max(0, file_size - suffix)
        end = file_size - 1
    else:
        start = int(start_text)
        end = int(end_text) if end_text else file_size - 1
    if start < 0 or start >= file_size or end < start:
        raise ValueError("Диапазон вне файла")
    return start, min(end, file_size - 1)


def iter_file_range(path: Path, start: int, length: int, chunk_size: int = 1024 * 256):
    with path.open("rb") as handle:
        handle.seek(start)
        remaining = length
        while remaining > 0:
            chunk = handle.read(min(chunk_size, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


@router.get("/tracks/{track_id}/stream")
def stream_track(
    track_id: str,
    _: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    range_header: Annotated[str | None, Header(alias="Range")] = None,
):
    track = get_track_or_404(db, track_id)
    storage = LocalMediaStorage(settings)
    try:
        path = storage.ensure_managed_path(settings.media_root / track.file_path)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail="Некорректный путь аудиофайла") from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Аудиофайл отсутствует в хранилище")
    file_size = path.stat().st_size
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    headers = {"Accept-Ranges": "bytes", "Cache-Control": "private, max-age=3600"}
    if range_header:
        try:
            start, end = parse_range_header(range_header, file_size)
        except (ValueError, TypeError):
            return Response(status_code=416, headers={"Content-Range": f"bytes */{file_size}"})
        length = end - start + 1
        headers.update({"Content-Range": f"bytes {start}-{end}/{file_size}", "Content-Length": str(length)})
        return StreamingResponse(
            iter_file_range(path, start, length),
            status_code=206,
            media_type=media_type,
            headers=headers,
        )
    headers["Content-Length"] = str(file_size)
    return StreamingResponse(iter_file_range(path, 0, file_size), media_type=media_type, headers=headers)


@router.get("/artwork/{artwork_id}/{size}")
def get_artwork(
    artwork_id: str,
    size: str,
    _: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> FileResponse:
    artwork = db.get(Artwork, artwork_id)
    if artwork is None:
        raise HTTPException(status_code=404, detail="Обложка не найдена")
    paths = {"original": artwork.original_path, "512": artwork.path_512, "256": artwork.path_256, "64": artwork.path_64}
    relative = paths.get(size)
    if not relative:
        raise HTTPException(status_code=404, detail="Размер обложки не найден")
    try:
        path = LocalMediaStorage(settings).ensure_managed_path(settings.media_root / relative)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail="Некорректный путь обложки") from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Файл обложки отсутствует")
    return FileResponse(path, media_type=artwork.mime_type, headers={"Cache-Control": "private, max-age=86400"})


@router.post("/upload", response_model=list[UploadResult])
async def upload_tracks(
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    files: Annotated[list[UploadFile], File()],
) -> list[UploadResult]:
    storage = LocalMediaStorage(settings)
    results: list[UploadResult] = []
    for upload in files:
        filename = Path(upload.filename or "track").name
        try:
            staged = await storage.stage_upload(upload)
            track = await run_in_threadpool(import_staged_file, db, staged, storage, settings)
            results.append(
                UploadResult(filename=filename, status="added", detail="Добавлено", track=serialize_track(track))
            )
            logger.info("Uploaded track %s", filename)
        except DuplicateTrackError as exc:
            results.append(
                UploadResult(filename=filename, status="duplicate", detail=str(exc), track=serialize_track(exc.track))
            )
        except HTTPException as exc:
            results.append(UploadResult(filename=filename, status="error", detail=str(exc.detail)))
        except Exception as exc:
            logger.exception("Failed to process upload %s", filename)
            results.append(
                UploadResult(filename=filename, status="error", detail=str(exc) or "Не удалось обработать файл")
            )
    return results
