"""Add music metadata review state."""

import sqlalchemy as sa

from alembic import op

revision = "0002_metadata_review"
down_revision = "0001_music"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("music_tracks")}
    if "metadata_reviewed_at" not in columns:
        op.add_column("music_tracks", sa.Column("metadata_reviewed_at", sa.DateTime(timezone=True), nullable=True))
    indexes = {index["name"] for index in inspector.get_indexes("music_tracks")}
    if "ix_music_tracks_metadata_reviewed_at" not in indexes:
        op.create_index(
            "ix_music_tracks_metadata_reviewed_at",
            "music_tracks",
            ["metadata_reviewed_at"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index("ix_music_tracks_metadata_reviewed_at", table_name="music_tracks")
    op.drop_column("music_tracks", "metadata_reviewed_at")
