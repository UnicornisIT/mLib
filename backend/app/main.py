import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.auth.api import router as auth_router
from app.core.config import get_settings
from app.database.session import (
    BooksSessionLocal,
    CollectionsSessionLocal,
    CoreSessionLocal,
    GamesSessionLocal,
    MovieSessionLocal,
    MusicSessionLocal,
    WishesSessionLocal,
)
from app.modules.books.api import router as books_router
from app.modules.collections.api import router as collections_router
from app.modules.games.api import router as games_router
from app.modules.movie.api.router import router as movie_router
from app.modules.music.api.router import router as music_router
from app.modules.wishes.api import router as wishes_router
from app.settings.api import router as settings_router
from app.settings.models import CoreSetting
from app.storage.service import LocalMediaStorage

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        with CoreSessionLocal() as db:
            configured_root = db.get(CoreSetting, "library_path")
            if configured_root and configured_root.value:
                from pathlib import Path

                settings.media_root = Path(configured_root.value).expanduser().resolve()
    except Exception:
        logging.getLogger(__name__).info("Application settings are not initialized yet")
    LocalMediaStorage(settings)
    yield


app = FastAPI(
    title="mLib API",
    version=settings.app_version,
    description="Self-hosted modular media library API",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Range"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"],
)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "version": settings.app_version}


def database_status(session_factory) -> str:
    try:
        with session_factory() as db:
            db.execute(text("SELECT 1"))
        return "available"
    except Exception:
        logging.getLogger(__name__).exception("Service database health check failed")
        return "unavailable"


@app.get(f"{settings.api_prefix}/services/status", tags=["system"])
def services_status() -> dict[str, dict[str, str]]:
    return {
        "music": {"status": database_status(MusicSessionLocal)},
        "movie": {"status": database_status(MovieSessionLocal)},
        "books": {"status": database_status(BooksSessionLocal)},
        "collections": {"status": database_status(CollectionsSessionLocal)},
        "games": {"status": database_status(GamesSessionLocal)},
        "wishes": {"status": database_status(WishesSessionLocal)},
    }


app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(music_router, prefix=settings.api_prefix)
app.include_router(movie_router, prefix=settings.api_prefix)
app.include_router(books_router, prefix=settings.api_prefix)
app.include_router(collections_router, prefix=settings.api_prefix)
app.include_router(games_router, prefix=settings.api_prefix)
app.include_router(wishes_router, prefix=settings.api_prefix)
app.include_router(settings_router, prefix=settings.api_prefix)
