"""Add shared user profile fields."""

import sqlalchemy as sa

from alembic import op

revision = "0002_user_profile"
down_revision = "0001_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("users")}
    columns = (
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=120), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("avatar_color", sa.String(length=7), nullable=False, server_default="#f25f45"),
    )
    for column in columns:
        if column.name not in existing:
            op.add_column("users", column)


def downgrade() -> None:
    op.drop_column("users", "avatar_color")
    op.drop_column("users", "birth_date")
    op.drop_column("users", "location")
    op.drop_column("users", "bio")
    op.drop_column("users", "display_name")
