from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth.dependencies import AdminUser, CurrentUser
from app.database.session import get_games_db
from app.modules.games.models import Game
from app.modules.games.schemas import (
    GameCreate,
    GamePage,
    GamePlatform,
    GameRead,
    GamesDashboard,
    GameStatus,
    GameUpdate,
)

router = APIRouter(prefix="/games", tags=["games"])


def require_game(db: Session, game_id: str) -> Game:
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Игра не найдена")
    return game


@router.get("", response_model=GamePage)
def list_games(
    _: CurrentUser,
    db: Annotated[Session, Depends(get_games_db)],
    q: str | None = None,
    platform: GamePlatform | Literal["all"] = "all",
    game_status: Annotated[GameStatus | Literal["all"], Query(alias="status")] = "all",
    sort: Literal["updated", "title", "year", "rating", "playtime"] = "updated",
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> GamePage:
    filters = []
    if platform != "all":
        filters.append(Game.platform == platform)
    if game_status != "all":
        filters.append(Game.status == game_status)
    if q and q.strip():
        term = f"%{q.strip()}%"
        filters.append(
            or_(
                Game.title.like(term),
                func.coalesce(Game.developer, "").like(term),
                func.coalesce(Game.publisher, "").like(term),
                func.coalesce(Game.genre, "").like(term),
            )
        )
    ordering = {
        "title": (Game.title.asc(),),
        "year": (Game.release_year.desc(), Game.title.asc()),
        "rating": (Game.personal_rating.desc(), Game.title.asc()),
        "playtime": (Game.playtime_minutes.desc(), Game.title.asc()),
    }.get(sort, (Game.updated_at.desc(),))
    total = int(db.scalar(select(func.count(Game.id)).where(*filters)) or 0)
    items = db.scalars(select(Game).where(*filters).order_by(*ordering).limit(limit)).all()
    return GamePage(items=[GameRead.model_validate(item) for item in items], total=total)


@router.get("/dashboard", response_model=GamesDashboard)
def dashboard(_: CurrentUser, db: Annotated[Session, Depends(get_games_db)]) -> GamesDashboard:
    def count_for(game_status: str) -> int:
        return int(db.scalar(select(func.count(Game.id)).where(Game.status == game_status)) or 0)

    totals = db.execute(
        select(
            func.count(Game.id),
            func.coalesce(func.sum(Game.playtime_minutes), 0),
            func.coalesce(func.sum(Game.achievements_unlocked), 0),
            func.coalesce(func.sum(Game.achievements_total), 0),
        )
    ).one()
    return GamesDashboard(
        total=int(totals[0]),
        playing=count_for("playing"),
        completed=count_for("completed") + count_for("completed_100"),
        completed_100=count_for("completed_100"),
        playtime_minutes=int(totals[1]),
        achievements_unlocked=int(totals[2]),
        achievements_total=int(totals[3]),
    )


@router.post("", response_model=GameRead, status_code=status.HTTP_201_CREATED)
def create_game(payload: GameCreate, _: AdminUser, db: Annotated[Session, Depends(get_games_db)]) -> GameRead:
    game = Game(**payload.model_dump())
    db.add(game)
    db.commit()
    db.refresh(game)
    return GameRead.model_validate(game)


@router.get("/{game_id}", response_model=GameRead)
def game_detail(game_id: str, _: CurrentUser, db: Annotated[Session, Depends(get_games_db)]) -> GameRead:
    return GameRead.model_validate(require_game(db, game_id))


@router.patch("/{game_id}", response_model=GameRead)
def update_game(
    game_id: str,
    payload: GameUpdate,
    _: AdminUser,
    db: Annotated[Session, Depends(get_games_db)],
) -> GameRead:
    game = require_game(db, game_id)
    values = payload.model_dump(exclude_unset=True)
    unlocked = values.get("achievements_unlocked", game.achievements_unlocked)
    total = values.get("achievements_total", game.achievements_total)
    if total and unlocked > total:
        raise HTTPException(status_code=422, detail="Полученных достижений не может быть больше общего количества")
    for key, value in values.items():
        setattr(game, key, value)
    db.commit()
    db.refresh(game)
    return GameRead.model_validate(game)


@router.delete("/{game_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_game(
    game_id: str,
    _: AdminUser,
    db: Annotated[Session, Depends(get_games_db)],
) -> Response:
    db.delete(require_game(db, game_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
