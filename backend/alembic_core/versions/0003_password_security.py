"""Add password security and session revocation fields."""

import sqlalchemy as sa

from alembic import op

revision = "0003_password_security"
down_revision = "0002_user_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("users")}
    columns = (
        sa.Column("session_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("password_change_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("password_change_locked_until", sa.DateTime(timezone=True), nullable=True),
    )
    for column in columns:
        if column.name not in existing:
            op.add_column("users", column)


def downgrade() -> None:
    op.drop_column("users", "password_change_locked_until")
    op.drop_column("users", "password_change_failures")
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "session_version")
