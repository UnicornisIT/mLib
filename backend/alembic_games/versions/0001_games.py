"""Initial games database."""

from alembic import op
from app.database.base import *  # noqa: F403
from app.database.session import GamesBase

revision = "0001_games"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    GamesBase.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    GamesBase.metadata.drop_all(bind=op.get_bind())
