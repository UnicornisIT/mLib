import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import utcnow
from app.database.session import GamesBase


def uuid4() -> str:
    return str(uuid.uuid4())


class Game(GamesBase):
    __tablename__ = "games"
    __table_args__ = (
        Index("idx_games_updated", "updated_at"),
        Index("idx_games_status", "status"),
        Index("idx_games_platform", "platform"),
        Index("idx_games_title", "title"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    developer: Mapped[str | None] = mapped_column(String(500))
    publisher: Mapped[str | None] = mapped_column(String(500))
    release_year: Mapped[int | None] = mapped_column(Integer)
    genre: Mapped[str | None] = mapped_column(String(255))
    platform: Mapped[str] = mapped_column(String(32), nullable=False, default="PC")
    purchase_date: Mapped[date | None] = mapped_column(Date)
    acquired_from: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_started")
    playtime_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    personal_rating: Mapped[float | None] = mapped_column(Float)
    achievements_unlocked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    achievements_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cover_url: Mapped[str | None] = mapped_column(Text)
    screenshots: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
