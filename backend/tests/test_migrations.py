import os
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
