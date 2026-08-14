from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
E2E_ROOT = ROOT / "frontend" / ".e2e"

# This helper may only delete the dedicated ignored E2E directory.
if E2E_ROOT.parent != ROOT / "frontend" or E2E_ROOT.name != ".e2e":
    raise RuntimeError("Unsafe E2E data directory")
shutil.rmtree(E2E_ROOT, ignore_errors=True)
E2E_ROOT.mkdir(parents=True)


def database(name: str) -> str:
    return f"sqlite:///{(E2E_ROOT / f'{name}.db').as_posix()}"


os.environ.update(
    {
        "ENVIRONMENT": "test",
        "SECRET_KEY": "playwright-e2e-only-secret-key-32-chars",
        "DATABASE_URL": database("legacy"),
        "CORE_DATABASE_URL": database("core"),
        "MUSIC_DATABASE_URL": database("music"),
        "MOVIE_DATABASE_URL": database("movie"),
        "BOOKS_DATABASE_URL": database("books"),
        "COLLECTIONS_DATABASE_URL": database("collections"),
        "GAMES_DATABASE_URL": database("games"),
        "WISHES_DATABASE_URL": database("wishes"),
        "MEDIA_ROOT": str(E2E_ROOT / "media"),
        "FFPROBE_PATH": "__missing_ffprobe__",
    }
)

for service in ("core", "music", "movie", "books", "collections", "games", "wishes"):
    subprocess.run(
        [sys.executable, "-m", "alembic", "-n", service, "upgrade", "head"],
        cwd=BACKEND,
        check=True,
        env=os.environ,
    )

os.chdir(BACKEND)
sys.path.insert(0, str(BACKEND))
import uvicorn  # noqa: E402

uvicorn.run("app.main:app", host="127.0.0.1", port=8100, log_level="warning")
