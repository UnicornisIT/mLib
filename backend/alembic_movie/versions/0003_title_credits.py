"""Add title directors and cast metadata."""

import sqlalchemy as sa

from alembic import op

revision = "0003_title_credits"
down_revision = "0002_watch_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("movie_titles")}
    columns = (
        sa.Column("directors", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("cast", sa.Text(), nullable=False, server_default="[]"),
    )
    for column in columns:
        if column.name not in existing:
            op.add_column("movie_titles", column)


def downgrade() -> None:
    op.drop_column("movie_titles", "cast")
    op.drop_column("movie_titles", "directors")
