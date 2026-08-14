import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.security import utcnow
from app.database.session import CollectionsBase


def uuid4() -> str:
    return str(uuid.uuid4())


item_tags = Table(
    "collection_item_tags",
    CollectionsBase.metadata,
    Column("item_id", String(36), ForeignKey("collection_items.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", String(36), ForeignKey("collection_tags.id", ondelete="CASCADE"), primary_key=True),
)


class Collection(CollectionsBase):
    __tablename__ = "collections"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_collections_owner_name"),
        Index("idx_collections_owner_updated", "owner_id", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str] = mapped_column(String(7), default="#b96842", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    items: Mapped[list["Item"]] = relationship(back_populates="collection", cascade="all, delete-orphan")
    fields: Mapped[list["CustomField"]] = relationship(
        back_populates="collection", cascade="all, delete-orphan", order_by="CustomField.position"
    )


class CustomField(CollectionsBase):
    __tablename__ = "collection_custom_fields"
    __table_args__ = (
        UniqueConstraint("collection_id", "name", name="uq_collection_fields_name"),
        Index("idx_collection_fields_collection_position", "collection_id", "position"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    collection_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("collections.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    field_type: Mapped[str] = mapped_column(String(24), nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    show_on_card: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    options: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    collection: Mapped[Collection] = relationship(back_populates="fields")
    values: Mapped[list["ItemFieldValue"]] = relationship(
        back_populates="field", cascade="all, delete-orphan"
    )


class Item(CollectionsBase):
    __tablename__ = "collection_items"
    __table_args__ = (
        Index("idx_collection_items_owner_updated", "owner_id", "updated_at"),
        Index("idx_collection_items_collection_name", "collection_id", "name"),
        Index("idx_collection_items_location", "location"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    collection_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("collections.id", ondelete="CASCADE"), nullable=False
    )
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    location: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    collection: Mapped[Collection] = relationship(back_populates="items")
    photos: Mapped[list["ItemPhoto"]] = relationship(
        back_populates="item", cascade="all, delete-orphan", order_by="ItemPhoto.position"
    )
    field_values: Mapped[list["ItemFieldValue"]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )
    tags: Mapped[list["Tag"]] = relationship(secondary=item_tags, back_populates="items")


class ItemPhoto(CollectionsBase):
    __tablename__ = "collection_item_photos"
    __table_args__ = (Index("idx_collection_photos_item_position", "item_id", "position"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("collection_items.id", ondelete="CASCADE"), nullable=False
    )
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    thumbnail_path: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(1000), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(80), default="image/webp", nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_cover: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    item: Mapped[Item] = relationship(back_populates="photos")


class ItemFieldValue(CollectionsBase):
    __tablename__ = "collection_item_field_values"
    __table_args__ = (
        UniqueConstraint("item_id", "field_id", name="uq_collection_item_field_value"),
        Index("idx_collection_values_field", "field_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("collection_items.id", ondelete="CASCADE"), nullable=False
    )
    field_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("collection_custom_fields.id", ondelete="CASCADE"), nullable=False
    )
    value: Mapped[object | None] = mapped_column(JSON)

    item: Mapped[Item] = relationship(back_populates="field_values")
    field: Mapped[CustomField] = relationship(back_populates="values")


class Tag(CollectionsBase):
    __tablename__ = "collection_tags"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_collection_tags_owner_name"),
        Index("idx_collection_tags_owner", "owner_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    color: Mapped[str] = mapped_column(String(7), default="#8b6f5d", nullable=False)

    items: Mapped[list[Item]] = relationship(secondary=item_tags, back_populates="tags")
