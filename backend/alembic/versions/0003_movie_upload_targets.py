"""Attach movie uploads to an existing catalog card."""

import sqlalchemy as sa

from alembic import op

revision = "0003_movie_upload_targets"
down_revision = "0002_movie_library"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("movie_uploads") as batch_op:
        batch_op.add_column(sa.Column("target_title_id", sa.String(36), nullable=True))
        batch_op.create_foreign_key(
            "fk_movie_uploads_target_title",
            "movie_titles",
            ["target_title_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("movie_uploads") as batch_op:
        batch_op.drop_constraint("fk_movie_uploads_target_title", type_="foreignkey")
        batch_op.drop_column("target_title_id")
