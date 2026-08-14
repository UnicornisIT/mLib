"""Initial wishes database."""

from alembic import op
from app.database.base import *  # noqa: F403
from app.database.session import WishesBase

revision = "0001_wishes"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    WishesBase.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    WishesBase.metadata.drop_all(bind=op.get_bind())
