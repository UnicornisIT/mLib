"""Initial core database."""

from alembic import op
from app.database.base import *  # noqa: F403
from app.database.session import CoreBase

revision = "0001_core"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    CoreBase.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    CoreBase.metadata.drop_all(bind=op.get_bind())
