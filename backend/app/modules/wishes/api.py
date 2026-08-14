from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.core.security import utcnow
from app.database.session import get_wishes_db
from app.modules.wishes.matching import normalize_title, reconcile_wishes
from app.modules.wishes.models import Wish
from app.modules.wishes.schemas import (
    WishCategory,
    WishCreate,
    WishesDashboard,
    WishPage,
    WishRead,
    WishStatus,
    WishUpdate,
)

router = APIRouter(prefix="/wishes", tags=["wishes"])


def require_wish(db: Session, owner_id: str, wish_id: str) -> Wish:
    wish = db.scalar(select(Wish).where(Wish.id == wish_id, Wish.owner_id == owner_id))
    if wish is None:
        raise HTTPException(status_code=404, detail="Желание не найдено")
    return wish


@router.get("", response_model=WishPage)
def list_wishes(
    user: CurrentUser,
    db: Annotated[Session, Depends(get_wishes_db)],
    q: str | None = None,
    category: WishCategory | Literal["all"] = "all",
    wish_status: Annotated[WishStatus | Literal["all"], Query(alias="status")] = "active",
    sort: Literal["updated", "created", "title"] = "updated",
    limit: Annotated[int, Query(ge=1, le=500)] = 300,
) -> WishPage:
    reconcile_wishes(db, user.id)
    filters = [Wish.owner_id == user.id]
    if category != "all":
        filters.append(Wish.category == category)
    if wish_status != "all":
        filters.append(Wish.status == wish_status)
    if q and q.strip():
        term = f"%{q.strip()}%"
        filters.append(
            or_(
                Wish.title.like(term),
                func.coalesce(Wish.creator, "").like(term),
                func.coalesce(Wish.notes, "").like(term),
            )
        )
    ordering = {
        "created": (Wish.created_at.desc(),),
        "title": (Wish.title.asc(),),
    }.get(sort, (Wish.updated_at.desc(),))
    total = int(db.scalar(select(func.count(Wish.id)).where(*filters)) or 0)
    items = db.scalars(select(Wish).where(*filters).order_by(*ordering).limit(limit)).all()
    return WishPage(items=[WishRead.model_validate(item) for item in items], total=total)


@router.get("/dashboard", response_model=WishesDashboard)
def dashboard(user: CurrentUser, db: Annotated[Session, Depends(get_wishes_db)]) -> WishesDashboard:
    reconcile_wishes(db, user.id)
    base = Wish.owner_id == user.id
    total = int(db.scalar(select(func.count(Wish.id)).where(base)) or 0)
    active = int(db.scalar(select(func.count(Wish.id)).where(base, Wish.status == "active")) or 0)
    fulfilled = total - active
    auto_fulfilled = int(
        db.scalar(
            select(func.count(Wish.id)).where(
                base,
                Wish.status == "fulfilled",
                Wish.auto_fulfilled.is_(True),
            )
        )
        or 0
    )
    by_category = {
        category: int(
            db.scalar(
                select(func.count(Wish.id)).where(
                    base,
                    Wish.status == "active",
                    Wish.category == category,
                )
            )
            or 0
        )
        for category in ("watch", "read", "listen", "buy")
    }
    return WishesDashboard(
        total=total,
        active=active,
        fulfilled=fulfilled,
        auto_fulfilled=auto_fulfilled,
        by_category=by_category,  # type: ignore[arg-type]
    )


@router.post("", response_model=WishRead, status_code=status.HTTP_201_CREATED)
def create_wish(
    payload: WishCreate,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_wishes_db)],
) -> WishRead:
    wish = Wish(owner_id=user.id, normalized_title=normalize_title(payload.title), **payload.model_dump())
    db.add(wish)
    db.commit()
    db.refresh(wish)
    reconcile_wishes(db, user.id)
    db.refresh(wish)
    return WishRead.model_validate(wish)


@router.get("/{wish_id}", response_model=WishRead)
def wish_detail(
    wish_id: str,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_wishes_db)],
) -> WishRead:
    reconcile_wishes(db, user.id)
    return WishRead.model_validate(require_wish(db, user.id, wish_id))


@router.patch("/{wish_id}", response_model=WishRead)
def update_wish(
    wish_id: str,
    payload: WishUpdate,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_wishes_db)],
) -> WishRead:
    wish = require_wish(db, user.id, wish_id)
    values = payload.model_dump(exclude_unset=True)
    for key, value in values.items():
        setattr(wish, key, value)
    if "title" in values and values["title"]:
        wish.normalized_title = normalize_title(values["title"])
    if values.get("status") == "fulfilled":
        wish.fulfilled_at = utcnow()
        wish.auto_fulfilled = False
        wish.matched_service = None
        wish.matched_item_id = None
    elif values.get("status") == "active":
        wish.fulfilled_at = None
        wish.auto_fulfilled = False
        wish.matched_service = None
        wish.matched_item_id = None
    db.commit()
    db.refresh(wish)
    if wish.status == "active":
        reconcile_wishes(db, user.id)
        db.refresh(wish)
    return WishRead.model_validate(wish)


@router.delete("/{wish_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_wish(
    wish_id: str,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_wishes_db)],
) -> Response:
    db.delete(require_wish(db, user.id, wish_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
