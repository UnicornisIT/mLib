"""Keep the Apple Music genre of catalog tracks, so a transferred library has genres before any file."""

import sqlalchemy as sa

from alembic import op

revision = "0008_catalog_track_genre"
down_revision = "0007_catalog_track_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("music_catalog_tracks")}
    if "genre" not in columns:
        # Plain ADD COLUMN: the table is not rebuilt, so links of files and playlists stay untouched.
        op.add_column("music_catalog_tracks", sa.Column("genre", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("music_catalog_tracks", "genre")
