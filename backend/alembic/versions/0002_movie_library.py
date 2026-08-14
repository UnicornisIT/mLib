"""Add movie and TV library schema."""

import sqlalchemy as sa

from alembic import op

revision = "0002_movie_library"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "movie_titles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("media_type", sa.String(16), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("original_title", sa.String(500)),
        sa.Column("normalized_title", sa.String(500), nullable=False),
        sa.Column("year", sa.Integer()),
        sa.Column("overview", sa.Text()),
        sa.Column("poster_url", sa.Text()),
        sa.Column("backdrop_url", sa.Text()),
        sa.Column("genres", sa.Text(), nullable=False),
        sa.Column("tmdb_id", sa.Integer()),
        sa.Column("tmdb_rating", sa.Float()),
        sa.Column("release_status", sa.String(80)),
        sa.Column("next_air_date", sa.Date()),
        sa.Column("metadata_provider", sa.String(40)),
        sa.Column("metadata_synced_at", sa.DateTime(timezone=True)),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("media_type", "tmdb_id", name="uq_movie_title_tmdb"),
    )
    op.create_index("idx_movie_titles_identity", "movie_titles", ["media_type", "normalized_title", "year"])
    op.create_index("idx_movie_titles_updated", "movie_titles", ["updated_at"])
    op.create_table(
        "movie_files",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("uuid", sa.String(36), nullable=False),
        sa.Column("title_id", sa.String(36), sa.ForeignKey("movie_titles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("display_title", sa.String(500), nullable=False),
        sa.Column("season_number", sa.Integer()),
        sa.Column("episode_number", sa.Integer()),
        sa.Column("episode_title", sa.String(500)),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("source_path", sa.Text()),
        sa.Column("original_filename", sa.String(1000), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("format", sa.String(80), nullable=False),
        sa.Column("mime_type", sa.String(120), nullable=False),
        sa.Column("duration", sa.Float(), nullable=False),
        sa.Column("video_codec", sa.String(80)),
        sa.Column("audio_codec", sa.String(80)),
        sa.Column("width", sa.Integer()),
        sa.Column("height", sa.Integer()),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_movie_files_uuid", "movie_files", ["uuid"], unique=True)
    op.create_index("ix_movie_files_title_id", "movie_files", ["title_id"])
    op.create_index("ix_movie_files_file_hash", "movie_files", ["file_hash"], unique=True)
    op.create_index("idx_movie_files_title_episode", "movie_files", ["title_id", "season_number", "episode_number"])
    op.create_index("idx_movie_files_added", "movie_files", ["added_at"])
    op.create_table(
        "movie_watch_progress",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("file_id", sa.String(36), sa.ForeignKey("movie_files.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("position", sa.Float(), nullable=False),
        sa.Column("duration", sa.Float(), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "movie_uploads",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_filename", sa.String(1000), nullable=False),
        sa.Column("total_size", sa.BigInteger(), nullable=False),
        sa.Column("offset", sa.BigInteger(), nullable=False),
        sa.Column("temp_path", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("file_id", sa.String(36), sa.ForeignKey("movie_files.id", ondelete="SET NULL")),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_movie_uploads_owner_id", "movie_uploads", ["owner_id"])
    op.create_index("idx_movie_uploads_owner_updated", "movie_uploads", ["owner_id", "updated_at"])


def downgrade() -> None:
    op.drop_table("movie_uploads")
    op.drop_table("movie_watch_progress")
    op.drop_table("movie_files")
    op.drop_table("movie_titles")
