from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.database.session import get_movie_db
from app.modules.movie.models import MovieSetting


def movie_value(db: Session, key: str, default: str = "") -> str:
    setting = db.get(MovieSetting, key)
    return setting.value if setting else default


def get_movie_settings(
    base: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_movie_db)],
) -> Settings:
    token = movie_value(db, "tmdb_api_token", base.tmdb_api_token or "") or None
    refresh = movie_value(db, "movie_metadata_refresh_hours", str(base.movie_metadata_refresh_hours))
    try:
        refresh_hours = max(1, int(refresh))
    except ValueError:
        refresh_hours = base.movie_metadata_refresh_hours
    return base.model_copy(update={"tmdb_api_token": token, "movie_metadata_refresh_hours": refresh_hours})
