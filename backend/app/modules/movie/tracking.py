from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import utcnow
from app.modules.movie.models import EpisodeWatch, MediaTitle, TitleTracking, VideoFile
from app.modules.movie.schemas import EpisodeRead, SeasonRead, TitleTrackingRead

SERIES_STATUSES = {"watching", "planned", "dropped", "completed"}
MOVIE_STATUSES = {"planned", "watched"}


def tracking_for(db: Session, user_id: str, title_id: str) -> TitleTracking | None:
    return db.get(TitleTracking, (user_id, title_id))


def set_tracking_status(db: Session, user_id: str, title: MediaTitle, status: str) -> TitleTracking:
    allowed = SERIES_STATUSES if title.media_type == "series" else MOVIE_STATUSES
    if status not in allowed:
        raise ValueError("Неизвестный статус просмотра")
    tracking = tracking_for(db, user_id, title.id)
    was_watched = bool(tracking and tracking.status == "watched")
    if tracking is None:
        tracking = TitleTracking(user_id=user_id, title_id=title.id, status=status)
        db.add(tracking)
    tracking.status = status
    tracking.updated_at = utcnow()
    if title.media_type == "movie":
        if status != "watched":
            tracking.watched_at = None
        elif not was_watched:
            tracking.watched_at = utcnow()
    db.commit()
    db.refresh(tracking)
    return tracking


def clear_tracking_status(db: Session, user_id: str, title_id: str) -> None:
    tracking = tracking_for(db, user_id, title_id)
    if tracking is not None:
        db.delete(tracking)
        db.commit()


def serialize_tracking(tracking: TitleTracking) -> TitleTrackingRead:
    return TitleTrackingRead(status=tracking.status, watched_at=tracking.watched_at)


def episode_watch_for(
    db: Session,
    user_id: str,
    title_id: str,
    season_number: int,
    episode_number: int,
) -> EpisodeWatch | None:
    return db.scalar(
        select(EpisodeWatch).where(
            EpisodeWatch.user_id == user_id,
            EpisodeWatch.title_id == title_id,
            EpisodeWatch.season_number == season_number,
            EpisodeWatch.episode_number == episode_number,
        )
    )


def set_episode_watched(
    db: Session,
    user_id: str,
    title: MediaTitle,
    episode: dict,
    watched: bool,
) -> EpisodeWatch | None:
    season_number = int(episode.get("season_number") or 0)
    episode_number = int(episode.get("episode_number") or 0)
    current = episode_watch_for(db, user_id, title.id, season_number, episode_number)
    if watched and current is None:
        current = EpisodeWatch(
            user_id=user_id,
            title_id=title.id,
            season_number=season_number,
            episode_number=episode_number,
            tmdb_episode_id=int(episode["id"]) if episode.get("id") else None,
            episode_name=episode.get("name") or None,
            runtime_minutes=int(episode.get("runtime") or title.episode_runtime_minutes or 0),
            watched_at=utcnow(),
        )
        db.add(current)
    elif not watched and current is not None:
        db.delete(current)
        current = None

    watched_count = int(
        db.scalar(
            select(func.count(EpisodeWatch.id)).where(
                EpisodeWatch.user_id == user_id,
                EpisodeWatch.title_id == title.id,
            )
        )
        or 0
    ) + (1 if watched and current is not None and current.id is None else 0)
    tracking = tracking_for(db, user_id, title.id)
    if watched:
        next_status = "completed" if title.total_episodes and watched_count >= title.total_episodes else "watching"
        if tracking is None:
            tracking = TitleTracking(user_id=user_id, title_id=title.id, status=next_status)
            db.add(tracking)
        elif tracking.status != next_status:
            tracking.status = next_status
    elif tracking and tracking.status == "completed":
        tracking.status = "watching"
    if tracking is not None:
        tracking.updated_at = utcnow()
    db.commit()
    return current


def record_file_completion(db: Session, user_id: str, video: VideoFile) -> None:
    title = video.media_title
    if title.media_type == "series" and video.season_number is not None and video.episode_number is not None:
        set_episode_watched(
            db,
            user_id,
            title,
            {
                "season_number": video.season_number,
                "episode_number": video.episode_number,
                "name": video.episode_title or video.display_title,
                "runtime": round(video.duration / 60) if video.duration else title.episode_runtime_minutes,
            },
            True,
        )
    elif title.media_type == "movie":
        set_tracking_status(db, user_id, title, "watched")


def serialize_season(db: Session, user_id: str, title: MediaTitle, payload: dict) -> SeasonRead:
    season_number = int(payload.get("season_number") or 0)
    watched_rows = db.scalars(
        select(EpisodeWatch).where(
            EpisodeWatch.user_id == user_id,
            EpisodeWatch.title_id == title.id,
            EpisodeWatch.season_number == season_number,
        )
    ).all()
    watched_by_number = {row.episode_number: row for row in watched_rows}
    episodes = []
    for item in payload.get("episodes", []):
        episode_number = int(item.get("episode_number") or 0)
        watched = watched_by_number.get(episode_number)
        air_date = item.get("air_date")
        still_path = item.get("still_path")
        episodes.append(
            EpisodeRead(
                tmdb_episode_id=int(item["id"]) if item.get("id") else None,
                season_number=season_number,
                episode_number=episode_number,
                name=item.get("name") or f"Эпизод {episode_number}",
                overview=item.get("overview") or None,
                air_date=date.fromisoformat(air_date) if air_date else None,
                runtime_minutes=int(item.get("runtime") or title.episode_runtime_minutes or 0),
                still_url=f"https://image.tmdb.org/t/p/w500{still_path}" if still_path else None,
                watched=watched is not None,
                watched_at=watched.watched_at if watched else None,
            )
        )
    return SeasonRead(
        season_number=season_number,
        name=payload.get("name") or f"Сезон {season_number}",
        overview=payload.get("overview") or None,
        episodes=episodes,
        watched_count=len(watched_rows),
        episode_count=len(episodes),
    )
