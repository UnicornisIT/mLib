"""Split the legacy monolithic SQLite database into core, music and movie databases."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.database.base import *  # noqa: F403
from app.database.session import CoreBase, MovieBase, MusicBase, core_engine, movie_engine, music_engine

CORE_TABLES = ["users"]
MUSIC_TABLES = [
    "music_artwork",
    "music_artists",
    "music_albums",
    "music_tracks",
    "music_favorites",
    "music_playlists",
    "music_playlist_tracks",
]
MOVIE_TABLES = ["movie_titles", "movie_files", "movie_watch_progress", "movie_uploads"]
MUSIC_SETTING_KEYS = {
    "import_path",
    "embedded_metadata",
    "musicbrainz_enabled",
    "cover_art_archive_enabled",
    "auto_artwork",
    "save_volume",
    "autoplay",
    "default_repeat",
    "theme",
}
MOVIE_SETTING_KEYS = {"tmdb_api_token", "movie_metadata_refresh_hours"}


def sqlite_path(url: str) -> Path:
    parsed = make_url(url)
    if parsed.get_backend_name() != "sqlite" or not parsed.database or parsed.database == ":memory:":
        raise RuntimeError(f"Database split supports file-based SQLite only: {url}")
    return Path(parsed.database).expanduser().resolve()


def table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return (
        connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None
    )


def row_count(connection: sqlite3.Connection, table: str) -> int:
    if not table_exists(connection, table):
        return 0
    return int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])


def copy_table(source: sqlite3.Connection, destination: sqlite3.Connection, table: str) -> int:
    if not table_exists(source, table):
        return 0
    source_columns = [row[1] for row in source.execute(f'PRAGMA table_info("{table}")')]
    target_columns = {row[1] for row in destination.execute(f'PRAGMA table_info("{table}")')}
    columns = [column for column in source_columns if column in target_columns]
    if not columns:
        return 0
    quoted = ", ".join(f'"{column}"' for column in columns)
    placeholders = ", ".join("?" for _ in columns)
    rows = source.execute(f'SELECT {quoted} FROM "{table}"').fetchall()
    if rows:
        destination.executemany(f'INSERT INTO "{table}" ({quoted}) VALUES ({placeholders})', rows)
    return len(rows)


def copy_settings(
    source: sqlite3.Connection,
    destination: sqlite3.Connection,
    table: str,
    keys: set[str],
) -> int:
    if not table_exists(source, "app_settings"):
        return 0
    rows = source.execute("SELECT key, value FROM app_settings").fetchall()
    selected = [(key, value) for key, value in rows if key in keys]
    if selected:
        destination.executemany(f"INSERT INTO {table} (key, value) VALUES (?, ?)", selected)
    return len(selected)


def stamp(connection: sqlite3.Connection, revision: str) -> None:
    connection.execute("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) PRIMARY KEY)")
    connection.execute("DELETE FROM alembic_version")
    connection.execute("INSERT INTO alembic_version (version_num) VALUES (?)", (revision,))


def ensure_empty(connection: sqlite3.Connection, tables: list[str], label: str) -> None:
    populated = {table: row_count(connection, table) for table in tables if row_count(connection, table)}
    if populated:
        raise RuntimeError(f"Refusing to overwrite populated {label} database: {populated}")


def main() -> None:
    settings = get_settings()
    source_path = sqlite_path(settings.database_url)
    destinations = {
        "core": sqlite_path(settings.core_database_url),
        "music": sqlite_path(settings.music_database_url),
        "movie": sqlite_path(settings.movie_database_url),
    }
    if not source_path.is_file():
        raise RuntimeError(f"Legacy database not found: {source_path}")
    if source_path in destinations.values() or len(set(destinations.values())) != 3:
        raise RuntimeError("Legacy, core, music and movie database paths must all be different")
    for path in destinations.values():
        path.parent.mkdir(parents=True, exist_ok=True)

    CoreBase.metadata.create_all(core_engine)
    MusicBase.metadata.create_all(music_engine)
    MovieBase.metadata.create_all(movie_engine)

    connections = {name: sqlite3.connect(path) for name, path in destinations.items()}
    source = sqlite3.connect(source_path)
    try:
        ensure_empty(connections["core"], CORE_TABLES, "core")
        ensure_empty(connections["music"], MUSIC_TABLES, "music")
        ensure_empty(connections["movie"], MOVIE_TABLES, "movie")

        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        backup_path = source_path.with_name(f"{source_path.stem}.pre-split-{timestamp}{source_path.suffix}")
        with sqlite3.connect(backup_path) as backup:
            source.backup(backup)

        for connection in connections.values():
            connection.execute("PRAGMA foreign_keys=OFF")

        copied: dict[str, int] = {}
        for table in CORE_TABLES:
            copied[table] = copy_table(source, connections["core"], table)
        for table in MUSIC_TABLES:
            copied[table] = copy_table(source, connections["music"], table)
        for table in MOVIE_TABLES:
            copied[table] = copy_table(source, connections["movie"], table)
        copied["core_settings"] = copy_settings(source, connections["core"], "core_settings", {"library_path"})
        copied["music_settings"] = copy_settings(source, connections["music"], "music_settings", MUSIC_SETTING_KEYS)
        copied["movie_settings"] = copy_settings(source, connections["movie"], "movie_settings", MOVIE_SETTING_KEYS)

        stamp(connections["core"], "0001_core")
        stamp(connections["music"], "0001_music")
        stamp(connections["movie"], "0001_movie")
        for connection in connections.values():
            connection.commit()

        for table in CORE_TABLES:
            assert row_count(source, table) == row_count(connections["core"], table), table
        for table in MUSIC_TABLES:
            assert row_count(source, table) == row_count(connections["music"], table), table
        for table in MOVIE_TABLES:
            assert row_count(source, table) == row_count(connections["movie"], table), table

        print(f"Backup: {backup_path}")
        print(f"Core:   {destinations['core']}")
        print(f"Music:  {destinations['music']}")
        print(f"Movie:  {destinations['movie']}")
        print("Copied rows:")
        for table, count in copied.items():
            print(f"  {table}: {count}")
    finally:
        source.close()
        for connection in connections.values():
            connection.close()


if __name__ == "__main__":
    main()
