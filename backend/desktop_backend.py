from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory


def resource_root() -> Path:
    bundled = getattr(sys, "_MEIPASS", None)
    return Path(bundled) if bundled else Path(__file__).resolve().parent


MIGRATIONS = {
    "core": "alembic_core",
    "music": "alembic_music",
    "movie": "alembic_movie",
    "books": "alembic_books",
    "collections": "alembic_collections",
    "games": "alembic_games",
    "wishes": "alembic_wishes",
}


def migration_config(folder: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(resource_root() / folder))
    return config


def apply_migrations() -> None:
    from app.core.config import get_settings
    from app.data_transfer.service import DOMAINS, automatic_migration_backup, restore_backup

    settings = get_settings()
    current: dict[str, str | None] = {}
    target: dict[str, str | None] = {}
    for domain in DOMAINS:
        config = migration_config(MIGRATIONS[domain.name])
        target[domain.name] = ScriptDirectory.from_config(config).get_current_head()
        with domain.engine.connect() as connection:
            current[domain.name] = MigrationContext.configure(connection).get_current_revision()

    requires_migration = any(current[name] != target[name] for name in MIGRATIONS)
    existing_library = any(revision is not None for revision in current.values())
    safety_backup = automatic_migration_backup(settings) if requires_migration and existing_library else None
    try:
        for name, folder in MIGRATIONS.items():
            if current[name] != target[name]:
                command.upgrade(migration_config(folder), "head")
    except Exception:
        if safety_backup:
            restore_backup(safety_backup, settings, make_safety_backup=False)
        raise


def run() -> int:
    try:
        from app.core.config import get_settings

        settings = get_settings()
        for directory in (
            settings.data_root,
            settings.media_root,
            settings.backups_root,
            settings.temp_root,
            settings.log_file.parent if settings.log_file else None,
        ):
            if directory:
                directory.mkdir(parents=True, exist_ok=True)

        # Importing app.main configures rotating file logging before migrations.
        from app.main import app

        apply_migrations()

        import uvicorn

        port = int(os.environ.get("MLIB_BACKEND_PORT", "0"))
        if not 1 <= port <= 65535:
            raise RuntimeError("MLIB_BACKEND_PORT is invalid")
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            log_config=None,
            access_log=False,
            server_header=False,
        )
        server = uvicorn.Server(config)

        def request_shutdown() -> None:
            server.should_exit = True

        app.state.desktop_shutdown = request_shutdown
        server.run()
        return 0
    except Exception:
        logging.getLogger("mlib.desktop").exception("Desktop backend failed")
        return 1


if __name__ == "__main__":
    from multiprocessing import freeze_support

    freeze_support()
    raise SystemExit(run())
