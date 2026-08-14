import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import utcnow
from app.database.session import WishesBase


def uuid4() -> str:
    return str(uuid.uuid4())


class Wish(WishesBase):
    __tablename__ = "wishes"
    __table_args__ = (
        Index("idx_wishes_owner_status_updated", "owner_id", "status", "updated_at"),
        Index("idx_wishes_owner_category_status", "owner_id", "category", "status"),
        Index("idx_wishes_normalized_title", "normalized_title"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    target_type: Mapped[str] = mapped_column(String(24), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_title: Mapped[str] = mapped_column(String(500), nullable=False)
    creator: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text)
    reference_url: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    matched_service: Mapped[str | None] = mapped_column(String(24))
    matched_item_id: Mapped[str | None] = mapped_column(String(36))
    auto_fulfilled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
