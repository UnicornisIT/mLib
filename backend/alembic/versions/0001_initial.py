"""Initial core and music domain schema."""

import sqlalchemy as sa

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(80), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("username", sa.String(80), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_table(
        "music_artwork",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("original_path", sa.Text(), nullable=False),
        sa.Column("path_512", sa.Text()),
        sa.Column("path_256", sa.Text()),
        sa.Column("path_64", sa.Text()),
        sa.Column("mime_type", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "music_artists",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("sort_name", sa.String(255), nullable=False),
        sa.Column("normalized_name", sa.String(255), nullable=False),
        sa.Column("artwork_id", sa.String(36), sa.ForeignKey("music_artwork.id", ondelete="SET NULL")),
        sa.Column("biography", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_music_artists_normalized_name", "music_artists", ["normalized_name"], unique=True)
    op.create_table(
        "music_albums",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("normalized_title", sa.String(500), nullable=False),
        sa.Column("artist_id", sa.String(36), sa.ForeignKey("music_artists.id", ondelete="SET NULL")),
        sa.Column("album_artist", sa.String(255), nullable=False),
        sa.Column("normalized_album_artist", sa.String(255), nullable=False),
        sa.Column("year", sa.Integer()),
        sa.Column("genre", sa.String(255)),
        sa.Column("artwork_id", sa.String(36), sa.ForeignKey("music_artwork.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("normalized_title", "normalized_album_artist", name="uq_album_identity"),
    )
    op.create_index("ix_music_albums_artist_id", "music_albums", ["artist_id"])
    op.create_index("ix_music_albums_genre", "music_albums", ["genre"])
    op.create_index("idx_music_albums_year", "music_albums", ["year"])
    op.create_table(
        "music_tracks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("uuid", sa.String(36), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("artist_id", sa.String(36), sa.ForeignKey("music_artists.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("album_id", sa.String(36), sa.ForeignKey("music_albums.id", ondelete="SET NULL")),
        sa.Column("album_artist", sa.String(255)),
        sa.Column("genre", sa.String(255)),
        sa.Column("year", sa.Integer()),
        sa.Column("track_number", sa.Integer()),
        sa.Column("disc_number", sa.Integer()),
        sa.Column("composer", sa.String(500)),
        sa.Column("copyright", sa.Text()),
        sa.Column("comment", sa.Text()),
        sa.Column("duration", sa.Float(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("source_path", sa.Text()),
        sa.Column("original_filename", sa.String(1000), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("format", sa.String(32), nullable=False),
        sa.Column("codec", sa.String(80)),
        sa.Column("bitrate", sa.Integer()),
        sa.Column("sample_rate", sa.Integer()),
        sa.Column("channels", sa.Integer()),
        sa.Column("artwork_id", sa.String(36), sa.ForeignKey("music_artwork.id", ondelete="SET NULL")),
        sa.Column("play_count", sa.Integer(), nullable=False),
        sa.Column("last_played_at", sa.DateTime(timezone=True)),
        sa.Column("date_added", sa.DateTime(timezone=True), nullable=False),
        sa.Column("date_modified", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_music_tracks_uuid", "music_tracks", ["uuid"], unique=True)
    op.create_index("ix_music_tracks_artist_id", "music_tracks", ["artist_id"])
    op.create_index("ix_music_tracks_album_id", "music_tracks", ["album_id"])
    op.create_index("ix_music_tracks_file_hash", "music_tracks", ["file_hash"], unique=True)
    op.create_index("idx_music_tracks_added", "music_tracks", ["date_added"])
    op.create_index("idx_music_tracks_album_order", "music_tracks", ["album_id", "disc_number", "track_number"])
    op.create_index("idx_music_tracks_genre", "music_tracks", ["genre"])
    op.create_index("idx_music_tracks_play_count", "music_tracks", ["play_count"])
    op.create_table(
        "music_favorites",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("track_id", sa.String(36), sa.ForeignKey("music_tracks.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "music_playlists",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("artwork_id", sa.String(36), sa.ForeignKey("music_artwork.id", ondelete="SET NULL")),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_music_playlists_owner_id", "music_playlists", ["owner_id"])
    op.create_index("idx_music_playlists_owner_updated", "music_playlists", ["owner_id", "updated_at"])
    op.create_table(
        "music_playlist_tracks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "playlist_id",
            sa.String(36),
            sa.ForeignKey("music_playlists.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("track_id", sa.String(36), sa.ForeignKey("music_tracks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("playlist_id", "position", name="uq_playlist_position"),
    )
    op.create_index("ix_music_playlist_tracks_playlist_id", "music_playlist_tracks", ["playlist_id"])
    op.create_index("ix_music_playlist_tracks_track_id", "music_playlist_tracks", ["track_id"])


def downgrade() -> None:
    op.drop_table("music_playlist_tracks")
    op.drop_table("music_playlists")
    op.drop_table("music_favorites")
    op.drop_table("music_tracks")
    op.drop_table("music_albums")
    op.drop_table("music_artists")
    op.drop_table("music_artwork")
    op.drop_table("users")
    op.drop_table("app_settings")
