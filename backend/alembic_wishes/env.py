from logging.config import fileConfig

from alembic import context
from app.database.base import *  # noqa: F403
from app.database.session import WishesBase, wishes_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
target_metadata = WishesBase.metadata


def run_migrations_offline() -> None:
    from app.core.config import get_settings

    context.configure(url=get_settings().wishes_database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with wishes_engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_offline() if context.is_offline_mode() else run_migrations_online()
