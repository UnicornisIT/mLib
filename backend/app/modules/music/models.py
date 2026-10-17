import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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
from app.database.session import MusicBase


def uuid4() -> str:
    return str(uuid.uuid4())


class MusicSetting(MusicBase):
    __tablename__ = "music_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class Artwork(MusicBase):
    __tablename__ = "music_artwork"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    original_path: Mapped[str] = mapped_column(Text)
    path_512: Mapped[str | None] = mapped_column(Text)
    path_256: Mapped[str | None] = mapped_column(Text)
    path_64: Mapped[str | None] = mapped_column(Text)
    mime_type: Mapped[str] = mapped_column(String(80), default="image/jpeg")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Artist(MusicBase):
    __tablename__ = "music_artists"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    artwork_id: Mapped[str | None] = mapped_column(ForeignKey("music_artwork.id", ondelete="SET NULL"))
    biography: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    artwork: Mapped[Artwork | None] = relationship()
    albums: Mapped[list["Album"]] = relationship(back_populates="artist")
    tracks: Mapped[list["Track"]] = relationship(back_populates="artist")


class Album(MusicBase):
    __tablename__ = "music_albums"
    __table_args__ = (
        UniqueConstraint("normalized_title", "normalized_album_artist", name="uq_album_identity"),
        Index("idx_music_albums_year", "year"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_title: Mapped[str] = mapped_column(String(500), nullable=False)
    artist_id: Mapped[str | None] = mapped_column(ForeignKey("music_artists.id", ondelete="SET NULL"), index=True)
    album_artist: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_album_artist: Mapped[str] = mapped_column(String(255), nullable=False)
    year: Mapped[int | None] = mapped_column(Integer)
    genre: Mapped[str | None] = mapped_column(String(255), index=True)
    artwork_id: Mapped[str | None] = mapped_column(ForeignKey("music_artwork.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    artist: Mapped[Artist | None] = relationship(back_populates="albums")
    artwork: Mapped[Artwork | None] = relationship()
    tracks: Mapped[list["Track"]] = relationship(back_populates="album")


class Track(MusicBase):
    __tablename__ = "music_tracks"
    __table_args__ = (
        Index("idx_music_tracks_added", "date_added"),
        Index("idx_music_tracks_album_order", "album_id", "disc_number", "track_number"),
        Index("idx_music_tracks_genre", "genre"),
        Index("idx_music_tracks_play_count", "play_count"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    uuid: Mapped[str] = mapped_column(String(36), unique=True, index=True, nullable=False, default=uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    artist_id: Mapped[str] = mapped_column(ForeignKey("music_artists.id", ondelete="RESTRICT"), index=True)
    album_id: Mapped[str | None] = mapped_column(ForeignKey("music_albums.id", ondelete="SET NULL"), index=True)
    album_artist: Mapped[str | None] = mapped_column(String(255))
    genre: Mapped[str | None] = mapped_column(String(255))
    year: Mapped[int | None] = mapped_column(Integer)
    track_number: Mapped[int | None] = mapped_column(Integer)
    disc_number: Mapped[int | None] = mapped_column(Integer)
    composer: Mapped[str | None] = mapped_column(String(500))
    copyright: Mapped[str | None] = mapped_column(Text)
    comment: Mapped[str | None] = mapped_column(Text)
    duration: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    source_path: Mapped[str | None] = mapped_column(Text)
    original_filename: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    format: Mapped[str] = mapped_column(String(32), nullable=False)
    isrc: Mapped[str | None] = mapped_column(String(32), index=True)
    codec: Mapped[str | None] = mapped_column(String(80))
    bitrate: Mapped[int | None] = mapped_column(Integer)
    sample_rate: Mapped[int | None] = mapped_column(Integer)
    channels: Mapped[int | None] = mapped_column(Integer)
    artwork_id: Mapped[str | None] = mapped_column(ForeignKey("music_artwork.id", ondelete="SET NULL"))
    catalog_track_id: Mapped[str | None] = mapped_column(
        ForeignKey("music_catalog_tracks.id", ondelete="SET NULL"), unique=True, index=True
    )
    play_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_played_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    title_from_filename: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    artist_from_fallback: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metadata_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    date_added: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    date_modified: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    artist: Mapped[Artist] = relationship(back_populates="tracks")
    album: Mapped[Album | None] = relationship(back_populates="tracks")
    artwork: Mapped[Artwork | None] = relationship()
    catalog_track: Mapped["CatalogTrack | None"] = relationship(back_populates="track")
    favorited_by: Mapped[list["Favorite"]] = relationship(back_populates="track", cascade="all, delete-orphan")


class CatalogTrack(MusicBase):
    """A track known from an external library export, with or without a local file."""

    __tablename__ = "music_catalog_tracks"
    __table_args__ = (
        Index("idx_music_catalog_tracks_identity", "normalized_artist", "normalized_title"),
        Index("idx_music_catalog_tracks_enrich", "transfer_job_id", "enrich_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    apple_track_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    isrc: Mapped[str | None] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    artist_name: Mapped[str] = mapped_column(String(500), nullable=False)
    album_title: Mapped[str | None] = mapped_column(String(500))
    normalized_title: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_artist: Mapped[str] = mapped_column(String(500), nullable=False)
    collection_id: Mapped[str | None] = mapped_column(String(32))
    apple_url: Mapped[str | None] = mapped_column(Text)
    artwork_url: Mapped[str | None] = mapped_column(Text)
    year: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    storefront: Mapped[str | None] = mapped_column(String(8))
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="apple_music_csv")
    transfer_job_id: Mapped[str | None] = mapped_column(ForeignKey("music_transfer_jobs.id", ondelete="SET NULL"))
    enrich_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    enrich_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    track: Mapped[Track | None] = relationship(back_populates="catalog_track", uselist=False)


class TransferJob(MusicBase):
    """Persistent state of a library transfer, so enrichment survives restarts."""

    __tablename__ = "music_transfer_jobs"
    __table_args__ = (Index("idx_music_transfer_jobs_owner_created", "owner_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    filename: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued", index=True)
    storefronts: Mapped[str] = mapped_column(String(80), nullable=False, default="ru,us,tr")
    create_playlists: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rows_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unique_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    added: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    existing: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enriched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    not_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    worker_token: Mapped[str | None] = mapped_column(String(36))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Favorite(MusicBase):
    __tablename__ = "music_favorites"

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    track_id: Mapped[str] = mapped_column(ForeignKey("music_tracks.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    track: Mapped[Track] = relationship(back_populates="favorited_by")


class Playlist(MusicBase):
    __tablename__ = "music_playlists"
    __table_args__ = (Index("idx_music_playlists_owner_updated", "owner_id", "updated_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    owner_id: Mapped[str] = mapped_column(String(36), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    artwork_id: Mapped[str | None] = mapped_column(ForeignKey("music_artwork.id", ondelete="SET NULL"))
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    items: Mapped[list["PlaylistTrack"]] = relationship(
        back_populates="playlist",
        cascade="all, delete-orphan",
        order_by="PlaylistTrack.position",
    )


PLAYLIST_ITEM_SOURCE_CHECK = (
    "(track_id IS NOT NULL AND catalog_track_id IS NULL) OR (track_id IS NULL AND catalog_track_id IS NOT NULL)"
)


class PlaylistTrack(MusicBase):
    """A playlist entry: either a local file or a catalog track that may not have a file yet."""

    __tablename__ = "music_playlist_tracks"
    __table_args__ = (
        UniqueConstraint("playlist_id", "position", name="uq_playlist_position"),
        CheckConstraint(PLAYLIST_ITEM_SOURCE_CHECK, name="ck_music_playlist_tracks_source"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    playlist_id: Mapped[str] = mapped_column(ForeignKey("music_playlists.id", ondelete="CASCADE"), index=True)
    track_id: Mapped[str | None] = mapped_column(ForeignKey("music_tracks.id", ondelete="CASCADE"), index=True)
    catalog_track_id: Mapped[str | None] = mapped_column(
        ForeignKey("music_catalog_tracks.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    playlist: Mapped[Playlist] = relationship(back_populates="items")
    track: Mapped[Track | None] = relationship()
    catalog_track: Mapped[CatalogTrack | None] = relationship()
