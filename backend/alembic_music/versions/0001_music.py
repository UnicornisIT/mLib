"""Initial music database."""

from alembic import op
from app.database.base import *  # noqa: F403
from app.database.session import MusicBase

revision = "0001_music"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    MusicBase.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    MusicBase.metadata.drop_all(bind=op.get_bind())
