import logging
import secrets
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.auth.api import router as auth_router
from app.auth.models import User
from app.auth.password_reset import PasswordResetError, reset_user_password
from app.auth.schemas import PasswordResetRequest, PasswordResetResult
from app.core.config import get_settings
from app.data_transfer.api import router as data_transfer_router
from app.database.session import (
    BooksSessionLocal,
    CollectionsSessionLocal,
    CoreSessionLocal,
    GamesSessionLocal,
    MovieSessionLocal,
    MusicSessionLocal,
    WishesSessionLocal,
    dispose_all_engines,
    get_core_db,
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


def configure_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    root = logging.getLogger()
    root.setLevel(level)
    if settings.log_file:
        settings.log_file.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            settings.log_file,
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        handler.setFormatter(formatter)
        root.handlers.clear()
        root.addHandler(handler)
    elif not root.handlers:
        logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s")


configure_logging()


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
    try:
        yield
    finally:
        dispose_all_engines()


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
    return {"status": "ok", "version": settings.app_version, "mode": settings.app_mode}


@app.post("/desktop/shutdown", include_in_schema=False)
def desktop_shutdown(
    desktop_token: Annotated[str | None, Header(alias="X-mLib-Desktop-Token")] = None,
) -> dict[str, str]:
    """Ask the embedded uvicorn server to exit without exposing shutdown in server mode."""
    require_desktop_token(desktop_token)
    callback = getattr(app.state, "desktop_shutdown", None)
    if callback is None:
        raise HTTPException(status_code=503, detail="Desktop lifecycle is not initialized")
    callback()
    return {"status": "shutting-down"}


def require_desktop_token(desktop_token: str | None) -> None:
    if not settings.is_desktop:
        raise HTTPException(status_code=404)
    if not settings.desktop_token or not desktop_token or not secrets.compare_digest(
        settings.desktop_token, desktop_token
    ):
        raise HTTPException(status_code=403)


@app.post("/desktop/password-reset", response_model=PasswordResetResult, include_in_schema=False)
def desktop_password_reset(
    payload: PasswordResetRequest,
    db: Annotated[Session, Depends(get_core_db)],
    desktop_token: Annotated[str | None, Header(alias="X-mLib-Desktop-Token")] = None,
) -> PasswordResetResult:
    require_desktop_token(desktop_token)
    user = db.scalar(
        select(User)
        .where(User.is_admin.is_(True), User.is_active.is_(True))
        .order_by(User.created_at.asc())
    )
    if user is None:
        raise HTTPException(status_code=409, detail="Профиль администратора ещё не создан")
    try:
        reset_user_password(
            db,
            user,
            payload.new_password,
            payload.new_password_confirmation,
        )
    except PasswordResetError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return PasswordResetResult(username=user.username)


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
app.include_router(data_transfer_router, prefix=settings.api_prefix)
