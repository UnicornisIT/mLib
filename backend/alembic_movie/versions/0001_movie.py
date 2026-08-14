"""Initial movie database."""

from alembic import op
from app.database.base import *  # noqa: F403
from app.database.session import MovieBase

revision = "0001_movie"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    MovieBase.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    MovieBase.metadata.drop_all(bind=op.get_bind())
