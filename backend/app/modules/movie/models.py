import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.security import utcnow
from app.database.session import MovieBase


def uuid4() -> str:
    return str(uuid.uuid4())


class MovieSetting(MovieBase):
    __tablename__ = "movie_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class MediaTitle(MovieBase):
    __tablename__ = "movie_titles"
    __table_args__ = (
        UniqueConstraint("media_type", "tmdb_id", name="uq_movie_title_tmdb"),
        Index("idx_movie_titles_identity", "media_type", "normalized_title", "year"),
        Index("idx_movie_titles_updated", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    media_type: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    original_title: Mapped[str | None] = mapped_column(String(500))
    normalized_title: Mapped[str] = mapped_column(String(500), nullable=False)
    year: Mapped[int | None] = mapped_column(Integer)
    overview: Mapped[str | None] = mapped_column(Text)
    poster_url: Mapped[str | None] = mapped_column(Text)
    backdrop_url: Mapped[str | None] = mapped_column(Text)
    genres: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    tmdb_id: Mapped[int | None] = mapped_column(Integer)
    tmdb_rating: Mapped[float | None] = mapped_column(Float)
    release_status: Mapped[str | None] = mapped_column(String(80))
    next_air_date: Mapped[date | None] = mapped_column(Date)
    runtime_minutes: Mapped[int | None] = mapped_column(Integer)
    episode_runtime_minutes: Mapped[int | None] = mapped_column(Integer)
    total_episodes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_seasons: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    seasons: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    directors: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    cast: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    metadata_provider: Mapped[str | None] = mapped_column(String(40))
    metadata_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    files: Mapped[list["VideoFile"]] = relationship(
        back_populates="media_title",
        cascade="all, delete-orphan",
        order_by="VideoFile.season_number, VideoFile.episode_number, VideoFile.added_at",
    )
    tracking: Mapped[list["TitleTracking"]] = relationship(back_populates="media_title", cascade="all, delete-orphan")
    episode_watches: Mapped[list["EpisodeWatch"]] = relationship(
        back_populates="media_title", cascade="all, delete-orphan"
    )


class TitleTracking(MovieBase):
    __tablename__ = "movie_title_tracking"
    __table_args__ = (Index("idx_movie_tracking_user_status", "user_id", "status"),)

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title_id: Mapped[str] = mapped_column(ForeignKey("movie_titles.id", ondelete="CASCADE"), primary_key=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    watched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    media_title: Mapped[MediaTitle] = relationship(back_populates="tracking")


class EpisodeWatch(MovieBase):
    __tablename__ = "movie_episode_watches"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "title_id", "season_number", "episode_number", name="uq_movie_episode_watch"
        ),
        Index("idx_movie_episode_watch_user_date", "user_id", "watched_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    title_id: Mapped[str] = mapped_column(ForeignKey("movie_titles.id", ondelete="CASCADE"), nullable=False)
    season_number: Mapped[int] = mapped_column(Integer, nullable=False)
    episode_number: Mapped[int] = mapped_column(Integer, nullable=False)
    tmdb_episode_id: Mapped[int | None] = mapped_column(Integer)
    episode_name: Mapped[str | None] = mapped_column(String(500))
    runtime_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    watched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    media_title: Mapped[MediaTitle] = relationship(back_populates="episode_watches")


class VideoFile(MovieBase):
    __tablename__ = "movie_files"
    __table_args__ = (
        Index("idx_movie_files_title_episode", "title_id", "season_number", "episode_number"),
        Index("idx_movie_files_added", "added_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    uuid: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=uuid4, nullable=False)
    title_id: Mapped[str] = mapped_column(ForeignKey("movie_titles.id", ondelete="CASCADE"), index=True)
    display_title: Mapped[str] = mapped_column(String(500), nullable=False)
    season_number: Mapped[int | None] = mapped_column(Integer)
    episode_number: Mapped[int | None] = mapped_column(Integer)
    episode_title: Mapped[str | None] = mapped_column(String(500))
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    source_path: Mapped[str | None] = mapped_column(Text)
    original_filename: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    format: Mapped[str] = mapped_column(String(80), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    duration: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    video_codec: Mapped[str | None] = mapped_column(String(80))
    audio_codec: Mapped[str | None] = mapped_column(String(80))
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    media_title: Mapped[MediaTitle] = relationship(back_populates="files")
    progress: Mapped[list["WatchProgress"]] = relationship(back_populates="video_file", cascade="all, delete-orphan")


class WatchProgress(MovieBase):
    __tablename__ = "movie_watch_progress"

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    file_id: Mapped[str] = mapped_column(ForeignKey("movie_files.id", ondelete="CASCADE"), primary_key=True)
    position: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    duration: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    video_file: Mapped[VideoFile] = relationship(back_populates="progress")


class VideoUpload(MovieBase):
    __tablename__ = "movie_uploads"
    __table_args__ = (Index("idx_movie_uploads_owner_updated", "owner_id", "updated_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    owner_id: Mapped[str] = mapped_column(String(36), index=True)
    original_filename: Mapped[str] = mapped_column(String(1000), nullable=False)
    total_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    offset: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    temp_path: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="uploading", nullable=False)
    target_title_id: Mapped[str | None] = mapped_column(ForeignKey("movie_titles.id", ondelete="SET NULL"))
    file_id: Mapped[str | None] = mapped_column(ForeignKey("movie_files.id", ondelete="SET NULL"))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
