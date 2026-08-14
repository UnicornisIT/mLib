"""Initial collections database."""

from alembic import op
from app.database.base import *  # noqa: F403
from app.database.session import CollectionsBase

revision = "0001_collections"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    CollectionsBase.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    CollectionsBase.metadata.drop_all(bind=op.get_bind())
