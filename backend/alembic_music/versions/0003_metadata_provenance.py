"""Track fallback title and artist provenance."""

import sqlalchemy as sa

from alembic import op

revision = "0003_metadata_provenance"
down_revision = "0002_metadata_review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("music_tracks")}
    columns = (
        sa.Column("title_from_filename", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("artist_from_fallback", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    for column in columns:
        if column.name not in existing:
            op.add_column("music_tracks", column)


def downgrade() -> None:
    op.drop_column("music_tracks", "artist_from_fallback")
    op.drop_column("music_tracks", "title_from_filename")
