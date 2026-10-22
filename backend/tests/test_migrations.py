import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_all_service_migrations_apply_to_clean_databases(tmp_path: Path) -> None:
    env = os.environ.copy()
    env.update(
        {
            "CORE_DATABASE_URL": f"sqlite:///{(tmp_path / 'core.db').as_posix()}",
            "MUSIC_DATABASE_URL": f"sqlite:///{(tmp_path / 'music.db').as_posix()}",
            "MOVIE_DATABASE_URL": f"sqlite:///{(tmp_path / 'movie.db').as_posix()}",
            "BOOKS_DATABASE_URL": f"sqlite:///{(tmp_path / 'books.db').as_posix()}",
            "COLLECTIONS_DATABASE_URL": f"sqlite:///{(tmp_path / 'collections.db').as_posix()}",
            "GAMES_DATABASE_URL": f"sqlite:///{(tmp_path / 'games.db').as_posix()}",
            "WISHES_DATABASE_URL": f"sqlite:///{(tmp_path / 'wishes.db').as_posix()}",
            "MEDIA_ROOT": str(tmp_path / "media"),
        }
    )

    backend_root = Path(__file__).resolve().parents[1]
    for service in ("core", "music", "movie", "books", "collections", "games", "wishes"):
        subprocess.run(
            [sys.executable, "-m", "alembic", "-n", service, "upgrade", "head"],
            cwd=backend_root,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )


def _music_alembic(env: dict[str, str], *args: str) -> None:
    backend_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-n", "music", *args],
        cwd=backend_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def _seed_legacy_music(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys=ON")
    connection.executescript(
        """
        INSERT INTO music_artists (id, name, sort_name, normalized_name, created_at)
        VALUES ('artist-1', 'Земфира', 'Земфира', 'земфира', '2026-01-01 00:00:00');
        INSERT INTO music_tracks (
            id, uuid, title, artist_id, duration, file_path, original_filename, file_size, file_hash,
            format, play_count, title_from_filename, artist_from_fallback, date_added, date_modified
        ) VALUES (
            'track-1', 'uuid-1', 'Искала', 'artist-1', 215.0, 'originals/uu/uuid-1.mp3', 'Искала.mp3', 10,
            'hash-1', 'mp3', 3, 0, 0, '2026-01-01 00:00:00', '2026-01-01 00:00:00'
        );
        INSERT INTO music_favorites (user_id, track_id, created_at) VALUES ('user-1', 'track-1', '2026-01-01');
        INSERT INTO music_playlists (id, owner_id, name, is_system, created_at, updated_at)
        VALUES ('playlist-1', 'user-1', 'Любимое', 0, '2026-01-01', '2026-01-01');
        INSERT INTO music_playlist_tracks (id, playlist_id, track_id, position, added_at)
        VALUES ('item-1', 'playlist-1', 'track-1', 0, '2026-01-01');
        """
    )
    connection.commit()
    connection.close()


def _legacy_rows(path: Path) -> dict[str, list[tuple]]:
    connection = sqlite3.connect(path)
    try:
        return {
            "tracks": connection.execute("SELECT id, title, play_count FROM music_tracks").fetchall(),
            "favorites": connection.execute("SELECT user_id, track_id FROM music_favorites").fetchall(),
            "items": connection.execute(
                "SELECT id, playlist_id, track_id, position FROM music_playlist_tracks"
            ).fetchall(),
        }
    finally:
        connection.close()


def _columns(path: Path, table: str) -> set[str]:
    connection = sqlite3.connect(path)
    try:
        return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
    finally:
        connection.close()


def test_library_transfer_migration_keeps_existing_music_data(tmp_path: Path) -> None:
    database = tmp_path / "music.db"
    env = os.environ.copy()
    env.update({"MUSIC_DATABASE_URL": f"sqlite:///{database.as_posix()}", "MEDIA_ROOT": str(tmp_path / "media")})
    _music_alembic(env, "upgrade", "head")
    _music_alembic(env, "downgrade", "0003_metadata_provenance")
    assert "catalog_track_id" not in _columns(database, "music_tracks")
    _seed_legacy_music(database)
    before = _legacy_rows(database)

    _music_alembic(env, "upgrade", "head")
    assert _legacy_rows(database) == before
    assert {"catalog_track_id", "isrc"} <= _columns(database, "music_tracks")
    assert {"apple_track_id", "isrc", "enrich_status"} <= _columns(database, "music_catalog_tracks")
    assert {"status", "rows_total", "not_found"} <= _columns(database, "music_transfer_jobs")

    assert "catalog_track_id" in _columns(database, "music_playlist_tracks")
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA foreign_keys=ON")
    connection.executescript(
        """
        INSERT INTO music_catalog_tracks (
            id, apple_track_id, title, artist_name, normalized_title, normalized_artist, source,
            enrich_status, enrich_attempts, created_at, updated_at
        ) VALUES
            ('card-1', '1001', 'Искала', 'Земфира', 'искала', 'земфира', 'apple_music_csv', 'enriched', 0,
             '2026-01-01', '2026-01-01'),
            ('card-2', '1002', 'Без файла', 'Земфира', 'без файла', 'земфира', 'apple_music_csv', 'pending', 0,
             '2026-01-01', '2026-01-01');
        UPDATE music_tracks SET catalog_track_id = 'card-1' WHERE id = 'track-1';
        INSERT INTO music_playlist_tracks (id, playlist_id, catalog_track_id, position, added_at) VALUES
            ('item-2', 'playlist-1', 'card-1', 1, '2026-01-01'),
            ('item-3', 'playlist-1', 'card-2', 2, '2026-01-01');
        """
    )
    connection.commit()
    try:
        connection.execute(
            "INSERT INTO music_playlist_tracks (id, playlist_id, position, added_at) "
            "VALUES ('broken', 'playlist-1', 3, '2026-01-01')"
        )
        raise AssertionError("an entry without track and catalog track must be rejected")
    except sqlite3.IntegrityError:
        pass
    connection.close()

    # 0007 only lifts NOT NULL from apple_track_id: links of files and playlists to the catalog must survive.
    def catalog_links() -> list[tuple]:
        connection = sqlite3.connect(database)
        try:
            return [
                *connection.execute("SELECT id, catalog_track_id FROM music_tracks ORDER BY id"),
                *connection.execute("SELECT id, catalog_track_id FROM music_playlist_tracks ORDER BY id"),
            ]
        finally:
            connection.close()

    links = catalog_links()
    _music_alembic(env, "downgrade", "0006_track_isrc")
    assert not {"source_service", "source_track_id"} & _columns(database, "music_catalog_tracks")
    _music_alembic(env, "upgrade", "head")
    assert catalog_links() == links
    assert {"source_service", "source_track_id"} <= _columns(database, "music_catalog_tracks")
    connection = sqlite3.connect(database)
    connection.execute(
        "INSERT INTO music_catalog_tracks (id, title, artist_name, normalized_title, normalized_artist, source, "
        "source_service, source_track_id, enrich_status, enrich_attempts, created_at, updated_at) VALUES "
        "('card-3', 'Teardrop', 'Massive Attack', 'teardrop', 'massive attack', 'spotify', 'spotify', 'x1', "
        "'pending', 0, '2026-01-01', '2026-01-01')"
    )
    connection.commit()
    assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    connection.close()

    _music_alembic(env, "downgrade", "0003_metadata_provenance")
    assert _legacy_rows(database)["tracks"] == before["tracks"]
    assert _legacy_rows(database)["favorites"] == before["favorites"]
    assert _legacy_rows(database)["items"] == [*before["items"], ("item-2", "playlist-1", "track-1", 1)]
    assert not {"catalog_track_id", "isrc"} & _columns(database, "music_tracks")
    assert "catalog_track_id" not in _columns(database, "music_playlist_tracks")
    _music_alembic(env, "upgrade", "head")
    assert _legacy_rows(database)["favorites"] == before["favorites"]
