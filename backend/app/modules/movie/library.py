import hashlib
import json
import math
import shutil
import uuid
from datetime import timedelta
from pathlib import Path

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings
from app.core.security import utcnow
from app.modules.movie.metadata import (
    ParsedVideoName,
    get_tmdb_details,
    normalize_title,
    parse_video_filename,
    probe_video,
    search_tmdb,
    tmdb_values,
)
from app.modules.movie.models import EpisodeWatch, MediaTitle, TitleTracking, VideoFile, VideoUpload, WatchProgress
from app.modules.movie.schemas import MediaTitleRead, VideoFileRead, WatchProgressRead


class DuplicateVideoError(ValueError):
    def __init__(self, video: VideoFile) -> None:
        super().__init__("Этот видеофайл уже находится в movieLib")
        self.video = video


class MovieStorage:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        settings.movie_originals_dir.mkdir(parents=True, exist_ok=True)
        settings.movie_staging_dir.mkdir(parents=True, exist_ok=True)

    def create_upload_path(self, upload_id: str, filename: str) -> Path:
        extension = Path(filename).suffix.lower()
        path = self.settings.movie_staging_dir / f"{upload_id}{extension}"
        path.touch(exist_ok=False)
        return path

    def commit(self, staged_path: Path, video_uuid: str) -> Path:
        extension = staged_path.suffix.lower()
        directory = self.settings.movie_originals_dir / video_uuid[:2]
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / f"{video_uuid}{extension}"
        shutil.move(str(staged_path), destination)
        return destination

    def managed(self, relative: str | Path) -> Path:
        path = (self.settings.media_root / relative).resolve()
        root = self.settings.media_root.resolve()
        if path != root and root not in path.parents:
            raise ValueError("Путь находится вне управляемого хранилища")
        return path


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(4 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _apply_tmdb(title: MediaTitle, payload: dict[str, object]) -> None:
    values = tmdb_values(payload, title.media_type)
    for key, value in values.items():
        if value is not None or key in {"next_air_date", "overview", "poster_url", "backdrop_url"}:
            setattr(title, key, value)
    title.normalized_title = normalize_title(title.title)
    title.metadata_synced_at = utcnow()


def resolve_media_title(db: Session, parsed: ParsedVideoName, settings: Settings) -> MediaTitle:
    normalized = normalize_title(parsed.title)
    predicates = [MediaTitle.media_type == parsed.media_type, MediaTitle.normalized_title == normalized]
    if parsed.year:
        predicates.append(or_(MediaTitle.year == parsed.year, MediaTitle.year.is_(None)))
    existing = db.scalar(select(MediaTitle).where(*predicates).options(selectinload(MediaTitle.files)))
    if existing:
        return existing

    metadata = search_tmdb(parsed, settings)
    if metadata and metadata.get("id"):
        tmdb_id = int(metadata["id"])
        existing = db.scalar(
            select(MediaTitle)
            .where(MediaTitle.media_type == parsed.media_type, MediaTitle.tmdb_id == tmdb_id)
            .options(selectinload(MediaTitle.files))
        )
        if existing:
            return existing

    title = MediaTitle(
        media_type=parsed.media_type,
        title=parsed.title,
        normalized_title=normalized,
        year=parsed.year,
        metadata_synced_at=utcnow(),
    )
    if metadata:
        _apply_tmdb(title, metadata)
    db.add(title)
    db.flush()
    return title


def resolve_tmdb_title(db: Session, media_type: str, payload: dict[str, object]) -> MediaTitle:
    tmdb_id = int(payload["id"])
    title = db.scalar(
        select(MediaTitle)
        .where(MediaTitle.media_type == media_type, MediaTitle.tmdb_id == tmdb_id)
        .options(selectinload(MediaTitle.files))
    )
    if title is None:
        name = str(payload.get("name") or payload.get("title") or "Без названия")
        title = MediaTitle(media_type=media_type, title=name, normalized_title=normalize_title(name))
        db.add(title)
        db.flush()
    _apply_tmdb(title, payload)
    db.commit()
    db.refresh(title)
    return title


def finalize_upload(db: Session, upload: VideoUpload, settings: Settings) -> VideoFile:
    storage = MovieStorage(settings)
    staged_path = storage.managed(upload.temp_path)
    sha256 = hash_file(staged_path)
    duplicate = db.scalar(
        select(VideoFile).where(VideoFile.file_hash == sha256, VideoFile.file_size == upload.total_size)
    )
    if duplicate:
        staged_path.unlink(missing_ok=True)
        raise DuplicateVideoError(duplicate)

    parsed = parse_video_filename(upload.original_filename)
    technical = probe_video(staged_path, settings)
    if upload.target_title_id:
        title = db.get(MediaTitle, upload.target_title_id)
        if title is None:
            raise ValueError("Карточка фильма или сериала больше не существует")
    else:
        title = resolve_media_title(db, parsed, settings)
    video_uuid = str(uuid.uuid4())
    committed: Path | None = None
    try:
        committed = storage.commit(staged_path, video_uuid)
        if title.media_type == "series" and parsed.season_number is not None and parsed.episode_number is not None:
            display_title = f"S{parsed.season_number:02d}E{parsed.episode_number:02d}"
            if parsed.episode_title:
                display_title += f" · {parsed.episode_title}"
        else:
            display_title = title.title
        video = VideoFile(
            uuid=video_uuid,
            title_id=title.id,
            display_title=display_title,
            season_number=parsed.season_number,
            episode_number=parsed.episode_number,
            episode_title=parsed.episode_title,
            file_path=committed.relative_to(settings.media_root).as_posix(),
            original_filename=upload.original_filename,
            file_size=upload.total_size,
            file_hash=sha256,
            format=technical.format,
            mime_type=technical.mime_type,
            duration=technical.duration,
            video_codec=technical.video_codec,
            audio_codec=technical.audio_codec,
            width=technical.width,
            height=technical.height,
        )
        db.add(video)
        db.flush()
        upload.file_id = video.id
        upload.status = "completed"
        db.commit()
        db.refresh(video)
        return video
    except Exception:
        db.rollback()
        if committed:
            committed.unlink(missing_ok=True)
        else:
            staged_path.unlink(missing_ok=True)
        raise


def refresh_title_metadata(db: Session, title: MediaTitle, settings: Settings, force: bool = False) -> bool:
    if not settings.tmdb_api_token or not title.tmdb_id:
        return False
    cutoff = utcnow() - timedelta(hours=settings.movie_metadata_refresh_hours)
    synced = title.metadata_synced_at
    tracking_metadata_missing = (
        title.media_type == "series" and (not title.total_episodes or title.seasons == "[]")
    ) or (title.media_type == "movie" and title.runtime_minutes is None) or title.cast == "[]"
    if (
        not force
        and not tracking_metadata_missing
        and synced is not None
        and synced.replace(tzinfo=None) > cutoff.replace(tzinfo=None)
    ):
        return False
    payload = get_tmdb_details(title.media_type, title.tmdb_id, settings)
    if not payload:
        return False
    _apply_tmdb(title, payload)
    db.commit()
    return True


def refresh_stale_titles(db: Session, settings: Settings, limit: int = 2) -> None:
    if not settings.tmdb_api_token:
        return
    cutoff = utcnow() - timedelta(hours=settings.movie_metadata_refresh_hours)
    titles = db.scalars(
        select(MediaTitle)
        .where(
            MediaTitle.tmdb_id.is_not(None),
            or_(MediaTitle.metadata_synced_at.is_(None), MediaTitle.metadata_synced_at < cutoff),
        )
        .order_by(MediaTitle.metadata_synced_at.asc())
        .limit(limit)
    ).all()
    for title in titles:
        refresh_title_metadata(db, title, settings, force=True)


def progress_for(db: Session, user_id: str, file_id: str) -> WatchProgress | None:
    return db.get(WatchProgress, (user_id, file_id))


def tracking_for(db: Session, user_id: str, title_id: str) -> TitleTracking | None:
    return db.get(TitleTracking, (user_id, title_id))


def serialize_progress(progress: WatchProgress | None) -> WatchProgressRead | None:
    if progress is None:
        return None
    return WatchProgressRead(
        position=progress.position,
        duration=progress.duration,
        completed=progress.completed,
        updated_at=progress.updated_at,
    )


def serialize_file(db: Session, user_id: str, video: VideoFile) -> VideoFileRead:
    return VideoFileRead(
        id=video.id,
        display_title=video.display_title,
        season_number=video.season_number,
        episode_number=video.episode_number,
        episode_title=video.episode_title,
        original_filename=video.original_filename,
        file_size=video.file_size,
        format=video.format,
        mime_type=video.mime_type,
        duration=video.duration,
        video_codec=video.video_codec,
        audio_codec=video.audio_codec,
        width=video.width,
        height=video.height,
        added_at=video.added_at,
        progress=serialize_progress(progress_for(db, user_id, video.id)),
    )


def serialize_title(db: Session, user_id: str, title: MediaTitle, include_files: bool = False) -> MediaTitleRead:
    files = list(title.files)
    progress_items = [progress_for(db, user_id, video.id) for video in files]
    completed_files = sum(1 for progress in progress_items if progress and progress.completed)
    file_units = 0.0
    for video, progress in zip(files, progress_items, strict=True):
        if not progress:
            continue
        if progress.completed:
            file_units += 1
        else:
            duration = progress.duration or video.duration
            if duration > 0:
                file_units += min(1, progress.position / duration)
    tracking = tracking_for(db, user_id, title.id)
    watched_episodes = int(
        db.scalar(
            select(func.count(EpisodeWatch.id)).where(
                EpisodeWatch.user_id == user_id,
                EpisodeWatch.title_id == title.id,
            )
        )
        or 0
    )
    total_episodes = title.total_episodes or (len(files) if title.media_type == "series" else 0)
    if title.media_type == "series":
        watched = watched_episodes or completed_files
        progress_percent = round(watched / total_episodes * 100, 1) if total_episodes else 0
    else:
        watched = 1 if tracking and tracking.status == "watched" else completed_files
        progress_percent = 100.0 if watched else round(file_units / len(files) * 100, 1) if files else 0
    season_counts = dict(
        db.execute(
            select(EpisodeWatch.season_number, func.count(EpisodeWatch.id))
            .where(EpisodeWatch.user_id == user_id, EpisodeWatch.title_id == title.id)
            .group_by(EpisodeWatch.season_number)
        ).all()
    )
    seasons = json.loads(title.seasons or "[]")
    for season in seasons:
        season["watched_count"] = int(season_counts.get(int(season["season_number"]), 0))
    values = dict(
        id=title.id,
        media_type=title.media_type,
        title=title.title,
        original_title=title.original_title,
        year=title.year,
        overview=title.overview,
        poster_url=title.poster_url,
        backdrop_url=title.backdrop_url,
        genres=json.loads(title.genres or "[]"),
        tmdb_rating=title.tmdb_rating,
        release_status=title.release_status,
        next_air_date=title.next_air_date,
        runtime_minutes=title.runtime_minutes,
        episode_runtime_minutes=title.episode_runtime_minutes,
        total_episodes=total_episodes,
        total_seasons=title.total_seasons,
        seasons=seasons,
        directors=json.loads(title.directors or "[]"),
        cast=json.loads(title.cast or "[]"),
        tracking=(
            {"status": tracking.status, "watched_at": tracking.watched_at}
            if tracking
            else None
        ),
        metadata_provider=title.metadata_provider,
        metadata_synced_at=title.metadata_synced_at,
        file_count=len(files),
        watched_count=watched,
        progress_percent=progress_percent,
        added_at=title.added_at,
    )
    if include_files:
        from app.modules.movie.schemas import MediaTitleDetail

        return MediaTitleDetail(**values, files=[serialize_file(db, user_id, video) for video in files])
    return MediaTitleRead(**values)


def pagination(total: int, page: int, page_size: int) -> tuple[int, int, int]:
    pages = max(1, math.ceil(total / page_size))
    return (page - 1) * page_size, page_size, pages
