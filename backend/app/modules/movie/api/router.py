import logging
import math
from collections import defaultdict
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import AdminUser, CurrentUser
from app.core.config import Settings
from app.core.config import get_settings as get_base_settings
from app.core.security import utcnow
from app.database.session import get_movie_db as get_db
from app.modules.movie.library import (
    DuplicateVideoError,
    MovieStorage,
    finalize_upload,
    pagination,
    refresh_stale_titles,
    refresh_title_metadata,
    resolve_tmdb_title,
    serialize_file,
    serialize_title,
)
from app.modules.movie.metadata import (
    TmdbCredentialError,
    TmdbServiceError,
    get_tmdb_catalog,
    get_tmdb_details,
    get_tmdb_person,
    get_tmdb_season,
    is_supported_tmdb_credential,
    validate_tmdb_credential,
)
from app.modules.movie.models import (
    EpisodeWatch,
    MediaTitle,
    MovieSetting,
    TitleTracking,
    VideoFile,
    VideoUpload,
    WatchProgress,
)
from app.modules.movie.schemas import (
    ContinueWatchingRead,
    EpisodeWatchUpdate,
    MediaTitleDetail,
    MediaTitlePage,
    MovieDashboardRead,
    MovieProfileRead,
    MovieSettingsRead,
    MovieSettingsUpdate,
    PersonFilmographyRead,
    ProfileActivityRead,
    ProfileSummaryRead,
    SeasonRead,
    TitleTrackingRead,
    TitleTrackingUpdate,
    TmdbCatalogPage,
    TmdbCatalogTitleRead,
    UploadCreate,
    UploadRead,
    WatchProgressRead,
    WatchProgressUpdate,
)
from app.modules.movie.settings import get_movie_settings as get_settings
from app.modules.movie.tracking import (
    clear_tracking_status,
    record_file_completion,
    serialize_season,
    serialize_tracking,
    set_episode_watched,
    set_tracking_status,
)
from app.modules.music.api.tracks import iter_file_range, parse_range_header

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/movie", tags=["movie library"])


def title_query():
    return select(MediaTitle).options(selectinload(MediaTitle.files))


def get_title(db: Session, title_id: str) -> MediaTitle:
    title = db.scalar(title_query().where(MediaTitle.id == title_id))
    if title is None:
        raise HTTPException(status_code=404, detail="Фильм или сериал не найден")
    return title


def get_video(db: Session, file_id: str) -> VideoFile:
    video = db.scalar(select(VideoFile).where(VideoFile.id == file_id).options(selectinload(VideoFile.media_title)))
    if video is None:
        raise HTTPException(status_code=404, detail="Видеофайл не найден")
    return video


def serialize_upload(db: Session, upload: VideoUpload) -> UploadRead:
    title_id = upload.target_title_id
    if upload.file_id:
        video = db.get(VideoFile, upload.file_id)
        title_id = video.title_id if video else None
    return UploadRead(
        id=upload.id,
        filename=upload.original_filename,
        size=upload.total_size,
        offset=upload.offset,
        status=upload.status,
        file_id=upload.file_id,
        title_id=title_id,
        error=upload.error_message,
    )


def serialize_tmdb_catalog_item(item: dict, local: MediaTitle | None) -> TmdbCatalogTitleRead:
    media_type = str(item.get("media_type") or "movie")
    release_date = item.get("first_air_date") if media_type == "series" else item.get("release_date")
    year_text = str(release_date or "")[:4]
    poster_path = item.get("poster_path")
    backdrop_path = item.get("backdrop_path")
    rating = float(item.get("vote_average") or 0) or None
    return TmdbCatalogTitleRead(
        tmdb_id=int(item["id"]),
        media_type=media_type,
        title=str(item.get("name") or item.get("title") or "Без названия"),
        original_title=item.get("original_name") or item.get("original_title"),
        year=int(year_text) if year_text.isdigit() else None,
        overview=item.get("overview") or None,
        poster_url=f"https://image.tmdb.org/t/p/w780{poster_path}" if poster_path else None,
        backdrop_url=f"https://image.tmdb.org/t/p/w1280{backdrop_path}" if backdrop_path else None,
        tmdb_rating=rating,
        local_title_id=local.id if local else None,
        file_count=len(local.files) if local else 0,
        match_reason=item.get("_match_reason"),
    )


def person_credit_items(payload: dict) -> list[dict]:
    credits = payload.get("combined_credits") or {}
    unique: dict[tuple[str, int], dict] = {}

    def add_credit(raw_credit: dict, reason: str) -> None:
        credit_type = raw_credit.get("media_type")
        if credit_type not in {"movie", "tv"} or not raw_credit.get("id") or raw_credit.get("adult"):
            return
        item = dict(raw_credit)
        item["media_type"] = "series" if credit_type == "tv" else "movie"
        item["_match_reason"] = reason
        key = (item["media_type"], int(item["id"]))
        current = unique.get(key)
        if current is None:
            unique[key] = item
            return
        current_reason = str(current.get("_match_reason") or "")
        if reason not in current_reason:
            current["_match_reason"] = f"{current_reason} · {reason}" if current_reason else reason

    for credit in credits.get("cast", []):
        role = str(credit.get("character") or "").strip()
        add_credit(credit, f"Актёр · {role}" if role else "Актёр")
    crew_labels = {
        "Director": "Режиссёр",
        "Series Director": "Режиссёр",
        "Creator": "Создатель",
    }
    for credit in credits.get("crew", []):
        label = crew_labels.get(str(credit.get("job") or ""))
        if label:
            add_credit(credit, label)

    def release_key(item: dict) -> tuple[str, float]:
        release_date = str(item.get("release_date") or item.get("first_air_date") or "")
        return release_date, float(item.get("popularity") or 0)

    return sorted(unique.values(), key=release_key, reverse=True)


def movie_library_bytes(settings: Settings) -> int:
    root = settings.media_root / "movie"
    if not root.exists():
        return 0
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


@router.get("/dashboard", response_model=MovieDashboardRead)
def dashboard(
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MovieDashboardRead:
    refresh_stale_titles(db, settings)
    tracked_title_ids = select(TitleTracking.title_id).where(TitleTracking.user_id == user.id)
    titles = db.scalars(
        title_query().where(MediaTitle.id.in_(tracked_title_ids)).order_by(desc(MediaTitle.updated_at)).limit(12)
    ).all()
    continue_rows = db.execute(
        select(WatchProgress, VideoFile, MediaTitle)
        .join(VideoFile, VideoFile.id == WatchProgress.file_id)
        .join(MediaTitle, MediaTitle.id == VideoFile.title_id)
        .options(selectinload(MediaTitle.files))
        .where(WatchProgress.user_id == user.id, WatchProgress.completed.is_(False), WatchProgress.position > 0)
        .order_by(desc(WatchProgress.updated_at))
        .limit(10)
    ).all()
    active_series_rows = db.execute(
        select(TitleTracking, MediaTitle)
        .join(MediaTitle, MediaTitle.id == TitleTracking.title_id)
        .options(selectinload(MediaTitle.files))
        .where(
            TitleTracking.user_id == user.id,
            TitleTracking.status == "watching",
            MediaTitle.media_type == "series",
        )
        .order_by(desc(TitleTracking.updated_at))
        .limit(10)
    ).all()
    continue_candidates = [
        (progress.updated_at, title, video)
        for progress, video, title in continue_rows
    ] + [
        (tracking.updated_at, title, None)
        for tracking, title in active_series_rows
    ]
    continue_candidates.sort(key=lambda item: item[0], reverse=True)
    continue_items: list[ContinueWatchingRead] = []
    seen_title_ids: set[str] = set()
    for _, title, video in continue_candidates:
        if title.id in seen_title_ids:
            continue
        seen_title_ids.add(title.id)
        continue_items.append(
            ContinueWatchingRead(
                title=serialize_title(db, user.id, title),
                file=serialize_file(db, user.id, video) if video is not None else None,
            )
        )
        if len(continue_items) == 10:
            break
    return MovieDashboardRead(
        titles=int(db.scalar(select(func.count(TitleTracking.title_id)).where(TitleTracking.user_id == user.id)) or 0),
        movies=int(
            db.scalar(
                select(func.count(TitleTracking.title_id))
                .join(MediaTitle, MediaTitle.id == TitleTracking.title_id)
                .where(
                    TitleTracking.user_id == user.id,
                    TitleTracking.status == "watched",
                    MediaTitle.media_type == "movie",
                )
            )
            or 0
        ),
        series=int(
            db.scalar(
                select(func.count(TitleTracking.title_id))
                .join(MediaTitle, MediaTitle.id == TitleTracking.title_id)
                .where(TitleTracking.user_id == user.id, MediaTitle.media_type == "series")
            )
            or 0
        ),
        episodes=int(db.scalar(select(func.count(EpisodeWatch.id)).where(EpisodeWatch.user_id == user.id)) or 0),
        continue_watching=continue_items,
        recently_added=[serialize_title(db, user.id, title) for title in titles],
    )


@router.get("/profile", response_model=MovieProfileRead)
def movie_profile(
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> MovieProfileRead:
    tracking_rows = db.execute(
        select(TitleTracking, MediaTitle)
        .join(MediaTitle, MediaTitle.id == TitleTracking.title_id)
        .where(TitleTracking.user_id == user.id)
        .order_by(desc(TitleTracking.updated_at))
    ).all()
    episode_rows = db.scalars(
        select(EpisodeWatch).where(EpisodeWatch.user_id == user.id).order_by(EpisodeWatch.watched_at)
    ).all()
    watched_movies = [
        (tracking, title)
        for tracking, title in tracking_rows
        if title.media_type == "movie" and tracking.status == "watched"
    ]
    episode_minutes = sum(row.runtime_minutes for row in episode_rows)
    movie_minutes = sum(title.runtime_minutes or 0 for _, title in watched_movies)

    def summary(episodes: int, movies: int, minutes: int) -> ProfileSummaryRead:
        return ProfileSummaryRead(
            episodes=episodes,
            movies=movies,
            minutes=minutes,
            days=math.ceil(minutes / 1440) if minutes else 0,
        )

    activity: dict = defaultdict(
        lambda: {"episodes": 0, "movies": 0, "minutes": 0, "episode_minutes": 0, "movie_minutes": 0}
    )
    for row in episode_rows:
        day = row.watched_at.date()
        activity[day]["episodes"] += 1
        activity[day]["minutes"] += row.runtime_minutes
        activity[day]["episode_minutes"] += row.runtime_minutes
    for tracking, title in watched_movies:
        if tracking.watched_at:
            day = tracking.watched_at.date()
            activity[day]["movies"] += 1
            activity[day]["minutes"] += title.runtime_minutes or 0
            activity[day]["movie_minutes"] += title.runtime_minutes or 0

    series_statuses = {"watching": 0, "planned": 0, "dropped": 0, "completed": 0}
    movie_statuses = {"planned": 0, "watched": 0}
    series_titles = {key: [] for key in series_statuses}
    movie_titles = {key: [] for key in movie_statuses}
    for tracking, title in tracking_rows:
        if title.media_type == "series" and tracking.status in series_statuses:
            series_statuses[tracking.status] += 1
            series_titles[tracking.status].append(serialize_title(db, user.id, title))
        elif title.media_type == "movie" and tracking.status in movie_statuses:
            movie_statuses[tracking.status] += 1
            movie_titles[tracking.status].append(serialize_title(db, user.id, title))

    return MovieProfileRead(
        username=user.username,
        member_since=user.created_at,
        summaries={
            "all": summary(len(episode_rows), len(watched_movies), episode_minutes + movie_minutes),
            "series": summary(len(episode_rows), 0, episode_minutes),
            "movies": summary(0, len(watched_movies), movie_minutes),
        },
        activity=[
            ProfileActivityRead(date=day, **values)
            for day, values in sorted(activity.items())
        ],
        series_status_counts=series_statuses,
        movie_status_counts=movie_statuses,
        series_titles=series_titles,
        movie_titles=movie_titles,
    )


@router.get("/titles", response_model=MediaTitlePage)
def list_titles(
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    page: int = 1,
    page_size: int = 48,
    q: str | None = None,
    media_type: str | None = None,
    has_files: bool | None = None,
    tracked: bool | None = None,
    sort: str = "added",
) -> MediaTitlePage:
    page = max(1, page)
    page_size = min(100, max(1, page_size))
    filters = []
    if q:
        term = f"%{q.strip()}%"
        filters.append(or_(MediaTitle.title.ilike(term), MediaTitle.original_title.ilike(term)))
    if media_type in {"movie", "series"}:
        filters.append(MediaTitle.media_type == media_type)
    if has_files is True:
        filters.append(MediaTitle.files.any())
    if tracked is True:
        filters.append(
            MediaTitle.id.in_(select(TitleTracking.title_id).where(TitleTracking.user_id == user.id))
        )
    total = int(db.scalar(select(func.count(MediaTitle.id)).where(*filters)) or 0)
    offset, limit, pages = pagination(total, page, page_size)
    ordering = {
        "title": MediaTitle.title.asc(),
        "year": MediaTitle.year.desc(),
        "rating": MediaTitle.tmdb_rating.desc(),
    }.get(sort, MediaTitle.added_at.desc())
    items = db.scalars(
        title_query().where(*filters).order_by(ordering, MediaTitle.id).offset(offset).limit(limit)
    ).all()
    return MediaTitlePage(
        items=[serialize_title(db, user.id, title) for title in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/settings", response_model=MovieSettingsRead)
def read_movie_settings(
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MovieSettingsRead:
    return MovieSettingsRead(
        tmdb_enabled=is_supported_tmdb_credential(settings.tmdb_api_token),
        metadata_refresh_hours=settings.movie_metadata_refresh_hours,
        storage_path=str(settings.media_root / "movie"),
        library_size=movie_library_bytes(settings),
        database="connected",
    )


@router.patch("/settings", response_model=MovieSettingsRead)
def update_movie_settings(
    payload: MovieSettingsUpdate,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    base: Annotated[Settings, Depends(get_base_settings)],
) -> MovieSettingsRead:
    values = payload.model_dump(exclude_unset=True)
    stored = {}
    if "tmdb_api_token" in values:
        supplied_token = values["tmdb_api_token"] or ""
        if supplied_token:
            try:
                supplied_token = validate_tmdb_credential(supplied_token, base)
            except TmdbCredentialError as exc:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "TMDB отклонил ключ. Вставьте токен Developer Plan (TMDB…), "
                        "Read Access Token (eyJ…) или API Key v3."
                    ),
                ) from exc
            except TmdbServiceError as exc:
                raise HTTPException(
                    status_code=502,
                    detail="Не удалось связаться с TMDB. Проверьте интернет-соединение и попробуйте ещё раз.",
                ) from exc
        stored["tmdb_api_token"] = supplied_token
    if "metadata_refresh_hours" in values:
        stored["movie_metadata_refresh_hours"] = values["metadata_refresh_hours"]
    for key, value in stored.items():
        setting = db.get(MovieSetting, key)
        encoded = str(value or "")
        if setting:
            setting.value = encoded
        else:
            db.add(MovieSetting(key=key, value=encoded))
    db.commit()
    runtime = get_settings(base, db)
    return MovieSettingsRead(
        tmdb_enabled=is_supported_tmdb_credential(runtime.tmdb_api_token),
        metadata_refresh_hours=runtime.movie_metadata_refresh_hours,
        storage_path=str(runtime.media_root / "movie"),
        library_size=movie_library_bytes(runtime),
        database="connected",
    )


@router.get("/catalog", response_model=TmdbCatalogPage)
def tmdb_catalog(
    _: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    page: int = 1,
    q: str | None = None,
    media_type: str = "all",
    sort: str = "popular",
) -> TmdbCatalogPage:
    if media_type not in {"all", "movie", "series"}:
        raise HTTPException(status_code=422, detail="Неизвестный тип каталога")
    if not is_supported_tmdb_credential(settings.tmdb_api_token):
        return TmdbCatalogPage(items=[], page=1, pages=0, total=0, configured=False)
    try:
        payload = get_tmdb_catalog(media_type, page, q.strip() if q and q.strip() else None, sort, settings)
    except TmdbCredentialError as exc:
        raise HTTPException(
            status_code=422,
            detail="TMDB отклонил сохранённый ключ. Обновите его в настройках.",
        ) from exc
    except TmdbServiceError as exc:
        raise HTTPException(
            status_code=502,
            detail="TMDB сейчас недоступен. Попробуйте обновить каталог позже.",
        ) from exc
    if payload is None:
        return TmdbCatalogPage(items=[], page=1, pages=0, total=0, configured=False)
    raw_items = [item for item in payload.get("results", []) if item.get("id")]
    ids = [int(item["id"]) for item in raw_items]
    local_titles = db.scalars(title_query().where(MediaTitle.tmdb_id.in_(ids))).all() if ids else []
    local_by_key = {(title.media_type, title.tmdb_id): title for title in local_titles}
    items = [
        serialize_tmdb_catalog_item(item, local_by_key.get((str(item.get("media_type")), int(item["id"]))))
        for item in raw_items
    ]
    return TmdbCatalogPage(
        items=items,
        page=int(payload.get("page") or page),
        pages=int(payload.get("total_pages") or 0),
        total=int(payload.get("total_results") or 0),
        configured=True,
    )


@router.post("/catalog/{media_type}/{tmdb_id}", response_model=MediaTitleDetail)
def save_tmdb_card(
    media_type: str,
    tmdb_id: int,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MediaTitleDetail:
    if media_type not in {"movie", "series"}:
        raise HTTPException(status_code=422, detail="Неизвестный тип карточки")
    if not settings.tmdb_api_token:
        raise HTTPException(status_code=503, detail="Для каталога нужно настроить TMDB_API_TOKEN")
    payload = get_tmdb_details(media_type, tmdb_id, settings)
    if not payload:
        raise HTTPException(status_code=502, detail="TMDB временно не отвечает")
    title = resolve_tmdb_title(db, media_type, payload)
    return serialize_title(db, user.id, title, include_files=True)  # type: ignore[return-value]


@router.get("/people/{person_id}", response_model=PersonFilmographyRead)
def person_filmography(
    person_id: int,
    _: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PersonFilmographyRead:
    if not is_supported_tmdb_credential(settings.tmdb_api_token):
        raise HTTPException(status_code=503, detail="Для фильмографии нужно настроить TMDB")
    try:
        payload = get_tmdb_person(person_id, settings)
    except TmdbCredentialError as exc:
        raise HTTPException(
            status_code=422,
            detail="TMDB отклонил сохранённый ключ. Обновите его в настройках.",
        ) from exc
    except TmdbServiceError as exc:
        raise HTTPException(status_code=502, detail="Не удалось загрузить фильмографию из TMDB") from exc
    if not payload:
        raise HTTPException(status_code=404, detail="Участник не найден в TMDB")

    raw_items = person_credit_items(payload)
    ids = [int(item["id"]) for item in raw_items]
    local_titles = db.scalars(title_query().where(MediaTitle.tmdb_id.in_(ids))).all() if ids else []
    local_by_key = {(title.media_type, title.tmdb_id): title for title in local_titles}
    profile_path = payload.get("profile_path")
    return PersonFilmographyRead(
        tmdb_id=int(payload.get("id") or person_id),
        name=str(payload.get("name") or "Без имени"),
        known_for_department=payload.get("known_for_department") or None,
        biography=payload.get("biography") or None,
        birthday=payload.get("birthday") or None,
        place_of_birth=payload.get("place_of_birth") or None,
        profile_url=f"https://image.tmdb.org/t/p/w500{profile_path}" if profile_path else None,
        items=[
            serialize_tmdb_catalog_item(item, local_by_key.get((str(item["media_type"]), int(item["id"]))))
            for item in raw_items
        ],
    )


@router.get("/titles/{title_id}", response_model=MediaTitleDetail)
def title_detail(
    title_id: str,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MediaTitleDetail:
    title = get_title(db, title_id)
    if refresh_title_metadata(db, title, settings):
        title = get_title(db, title_id)
    return serialize_title(db, user.id, title, include_files=True)  # type: ignore[return-value]


def load_season_payload(title: MediaTitle, season_number: int, settings: Settings) -> dict:
    if title.media_type != "series" or not title.tmdb_id:
        raise HTTPException(status_code=422, detail="Сезоны доступны только для сериалов из каталога TMDB")
    payload = get_tmdb_season(title.tmdb_id, season_number, settings)
    if not payload:
        raise HTTPException(status_code=502, detail="Не удалось загрузить эпизоды сезона из TMDB")
    return payload


@router.put("/titles/{title_id}/tracking", response_model=TitleTrackingRead)
def update_title_tracking(
    title_id: str,
    payload: TitleTrackingUpdate,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> TitleTrackingRead:
    title = get_title(db, title_id)
    try:
        tracking = set_tracking_status(db, user.id, title, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return serialize_tracking(tracking)


@router.delete("/titles/{title_id}/tracking", status_code=status.HTTP_204_NO_CONTENT)
def delete_title_tracking(
    title_id: str,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    get_title(db, title_id)
    clear_tracking_status(db, user.id, title_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/titles/{title_id}/seasons/{season_number}", response_model=SeasonRead)
def season_detail(
    title_id: str,
    season_number: int,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SeasonRead:
    title = get_title(db, title_id)
    return serialize_season(db, user.id, title, load_season_payload(title, season_number, settings))


@router.put("/titles/{title_id}/seasons/{season_number}/episodes/{episode_number}", response_model=SeasonRead)
def update_episode_watch(
    title_id: str,
    season_number: int,
    episode_number: int,
    payload: EpisodeWatchUpdate,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SeasonRead:
    title = get_title(db, title_id)
    season_payload = load_season_payload(title, season_number, settings)
    episode = next(
        (item for item in season_payload.get("episodes", []) if int(item.get("episode_number") or 0) == episode_number),
        None,
    )
    if episode is None:
        raise HTTPException(status_code=404, detail="Эпизод не найден")
    set_episode_watched(db, user.id, title, episode, payload.watched)
    return serialize_season(db, user.id, title, season_payload)


@router.put("/titles/{title_id}/seasons/{season_number}/watched", response_model=SeasonRead)
def update_season_watch(
    title_id: str,
    season_number: int,
    payload: EpisodeWatchUpdate,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SeasonRead:
    title = get_title(db, title_id)
    season_payload = load_season_payload(title, season_number, settings)
    for episode in season_payload.get("episodes", []):
        set_episode_watched(db, user.id, title, episode, payload.watched)
    return serialize_season(db, user.id, title, season_payload)


@router.post("/uploads", response_model=UploadRead, status_code=status.HTTP_201_CREATED)
def create_upload(
    payload: UploadCreate,
    user: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UploadRead:
    filename = Path(payload.filename).name
    if not filename:
        raise HTTPException(status_code=422, detail="Некорректное имя файла")
    if payload.title_id and db.get(MediaTitle, payload.title_id) is None:
        raise HTTPException(status_code=404, detail="Карточка фильма или сериала не найдена")
    storage = MovieStorage(settings)
    upload = VideoUpload(
        owner_id=user.id,
        original_filename=filename,
        total_size=payload.size,
        target_title_id=payload.title_id,
        temp_path="",
    )
    db.add(upload)
    db.flush()
    path = storage.create_upload_path(upload.id, filename)
    upload.temp_path = path.relative_to(settings.media_root).as_posix()
    db.commit()
    db.refresh(upload)
    return serialize_upload(db, upload)


@router.get("/uploads/{upload_id}", response_model=UploadRead)
def upload_status(upload_id: str, user: AdminUser, db: Annotated[Session, Depends(get_db)]) -> UploadRead:
    upload = db.get(VideoUpload, upload_id)
    if upload is None or upload.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Загрузка не найдена")
    return serialize_upload(db, upload)


@router.patch("/uploads/{upload_id}", response_model=UploadRead)
async def append_upload(
    upload_id: str,
    request: Request,
    user: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    upload_offset: Annotated[int, Header(alias="Upload-Offset")],
) -> UploadRead:
    upload = db.get(VideoUpload, upload_id)
    if upload is None or upload.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Загрузка не найдена")
    if upload.status != "uploading":
        return serialize_upload(db, upload)
    if upload_offset != upload.offset:
        raise HTTPException(status_code=409, detail=f"Ожидалось смещение {upload.offset}")
    storage = MovieStorage(settings)
    path = storage.managed(upload.temp_path)
    written = 0
    with path.open("ab") as output:
        async for chunk in request.stream():
            if not chunk:
                continue
            if upload.offset + written + len(chunk) > upload.total_size:
                raise HTTPException(status_code=413, detail="Получено больше данных, чем заявлено")
            output.write(chunk)
            written += len(chunk)
    upload.offset += written
    upload.updated_at = utcnow()
    db.commit()
    if upload.offset < upload.total_size:
        return serialize_upload(db, upload)

    upload.status = "processing"
    db.commit()
    try:
        await run_in_threadpool(finalize_upload, db, upload, settings)
    except DuplicateVideoError as exc:
        upload = db.get(VideoUpload, upload_id)
        upload.status = "completed"
        upload.file_id = exc.video.id
        db.commit()
    except Exception as exc:
        logger.exception("Failed to process movie upload %s", upload.original_filename)
        upload = db.get(VideoUpload, upload_id)
        upload.status = "error"
        upload.error_message = str(exc) or "Не удалось обработать видео"
        db.commit()
    upload = db.get(VideoUpload, upload_id)
    return serialize_upload(db, upload)


@router.put("/files/{file_id}/progress", response_model=WatchProgressRead)
def save_progress(
    file_id: str,
    payload: WatchProgressUpdate,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> WatchProgressRead:
    video = get_video(db, file_id)
    duration = payload.duration or video.duration
    completed = (
        payload.completed if payload.completed is not None else bool(duration and payload.position / duration >= 0.9)
    )
    progress = db.get(WatchProgress, (user.id, file_id))
    if progress is None:
        progress = WatchProgress(user_id=user.id, file_id=file_id)
        db.add(progress)
    progress.position = min(payload.position, duration) if duration else payload.position
    progress.duration = duration
    progress.completed = completed
    progress.updated_at = utcnow()
    db.commit()
    if completed:
        record_file_completion(db, user.id, video)
    db.refresh(progress)
    return WatchProgressRead(
        position=progress.position,
        duration=progress.duration,
        completed=progress.completed,
        updated_at=progress.updated_at,
    )


@router.get("/files/{file_id}/stream")
def stream_video(
    file_id: str,
    _: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    range_header: Annotated[str | None, Header(alias="Range")] = None,
):
    video = get_video(db, file_id)
    try:
        path = MovieStorage(settings).managed(video.file_path)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail="Некорректный путь видеофайла") from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Видеофайл отсутствует в хранилище")
    file_size = path.stat().st_size
    headers = {"Accept-Ranges": "bytes", "Cache-Control": "private, max-age=3600"}
    if range_header:
        try:
            start, end = parse_range_header(range_header, file_size)
        except (ValueError, TypeError):
            return Response(status_code=416, headers={"Content-Range": f"bytes */{file_size}"})
        length = end - start + 1
        headers.update({"Content-Range": f"bytes {start}-{end}/{file_size}", "Content-Length": str(length)})
        return StreamingResponse(
            iter_file_range(path, start, length), status_code=206, media_type=video.mime_type, headers=headers
        )
    headers["Content-Length"] = str(file_size)
    return StreamingResponse(iter_file_range(path, 0, file_size), media_type=video.mime_type, headers=headers)
