"""Remember the ISRC read from a file's tags for catalog matching."""

import sqlalchemy as sa

from alembic import op

revision = "0006_track_isrc"
down_revision = "0005_playlist_catalog_items"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "isrc" not in {column["name"] for column in inspector.get_columns("music_tracks")}:
        op.add_column("music_tracks", sa.Column("isrc", sa.String(32), nullable=True))
    if "ix_music_tracks_isrc" not in {index["name"] for index in inspector.get_indexes("music_tracks")}:
        op.create_index("ix_music_tracks_isrc", "music_tracks", ["isrc"])


def downgrade() -> None:
    op.drop_index("ix_music_tracks_isrc", table_name="music_tracks")
    op.drop_column("music_tracks", "isrc")
