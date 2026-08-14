from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.auth.models import User
from app.auth.password_policy import password_policy_error
from app.auth.schemas import AuthStatus, Credentials, PasswordChangeRequest, SetupRequest, UserProfileUpdate, UserRead
from app.core.config import Settings, get_settings
from app.core.security import (
    create_session_token,
    decode_session_token,
    hash_password,
    normalize_password,
    password_needs_rehash,
    utcnow,
    verify_password,
)
from app.database.session import get_core_db, get_music_db
from app.modules.music.models import MusicSetting
from app.settings.models import CoreSetting

router = APIRouter(prefix="/auth", tags=["authentication"])


def set_session_cookie(response: Response, user: User, settings: Settings) -> None:
    token = create_session_token(user.id, settings.secret_key, settings.session_ttl_hours, user.session_version)
    response.set_cookie(
        "mlib_session",
        token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.get("/status", response_model=AuthStatus)
def auth_status(
    db: Annotated[Session, Depends(get_core_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    mlib_session: Annotated[str | None, Cookie()] = None,
) -> AuthStatus:
    setup_required = (db.scalar(select(func.count(User.id))) or 0) == 0
    authenticated = False
    if mlib_session:
        identity = decode_session_token(mlib_session, settings.secret_key)
        user = db.get(User, identity.user_id) if identity else None
        authenticated = bool(
            user and user.is_active and user.session_version == identity.version
        )
    return AuthStatus(setup_required=setup_required, authenticated=authenticated)


@router.post("/setup", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def setup(
    payload: SetupRequest,
    response: Response,
    db: Annotated[Session, Depends(get_core_db)],
    music_db: Annotated[Session, Depends(get_music_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    if (db.scalar(select(func.count(User.id))) or 0) > 0:
        raise HTTPException(status_code=409, detail="Первоначальная настройка уже выполнена")
    if policy_error := password_policy_error(payload.password, payload.username):
        raise HTTPException(status_code=422, detail=policy_error)
    user = User(username=payload.username, password_hash=hash_password(payload.password), is_admin=True)
    db.add(user)
    if payload.library_path:
        library_path = Path(payload.library_path).expanduser().resolve()
        try:
            library_path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise HTTPException(status_code=422, detail="Не удалось создать папку медиатеки") from exc
        settings.media_root = library_path
        db.add(CoreSetting(key="library_path", value=str(library_path)))
    if payload.import_path:
        import_path = Path(payload.import_path).expanduser().resolve()
        if not import_path.is_dir():
            raise HTTPException(status_code=422, detail="Папка импорта не существует")
        music_db.add(MusicSetting(key="import_path", value=str(import_path)))
        music_db.commit()
    db.commit()
    db.refresh(user)
    set_session_cookie(response, user, settings)
    return user


@router.post("/login", response_model=UserRead)
def login(
    payload: Credentials,
    response: Response,
    db: Annotated[Session, Depends(get_core_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    user = db.scalar(select(User).where(func.lower(User.username) == payload.username.lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверное имя пользователя или пароль")
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)
        db.add(user)
        db.commit()
        db.refresh(user)
    set_session_cookie(response, user, settings)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    response.delete_cookie("mlib_session", path="/")


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser) -> User:
    return user


@router.patch("/me", response_model=UserRead)
def update_me(
    payload: UserProfileUpdate,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_core_db)],
) -> User:
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("avatar_color") is None:
        changes.pop("avatar_color", None)
    for field, value in changes.items():
        setattr(user, field, value)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _seconds_until(value: datetime | None) -> int:
    if value is None:
        return 0
    comparable = value if value.tzinfo else value.replace(tzinfo=UTC)
    return max(0, int((comparable - utcnow()).total_seconds()) + 1)


@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: PasswordChangeRequest,
    response: Response,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_core_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    retry_after = _seconds_until(user.password_change_locked_until)
    if retry_after:
        raise HTTPException(
            status_code=429,
            detail="Слишком много неудачных попыток. Повторите позже",
            headers={"Retry-After": str(retry_after)},
        )
    if user.password_change_locked_until is not None:
        user.password_change_locked_until = None
        user.password_change_failures = 0

    if not verify_password(payload.current_password, user.password_hash):
        user.password_change_failures += 1
        if user.password_change_failures >= 5:
            user.password_change_locked_until = utcnow() + timedelta(minutes=15)
        db.add(user)
        db.commit()
        if user.password_change_locked_until:
            raise HTTPException(
                status_code=429,
                detail="Слишком много неудачных попыток. Смена пароля временно заблокирована на 15 минут",
                headers={"Retry-After": "900"},
            )
        raise HTTPException(status_code=400, detail="Текущий пароль указан неверно")

    if normalize_password(payload.new_password) != normalize_password(payload.new_password_confirmation):
        raise HTTPException(status_code=422, detail="Новые пароли не совпадают")
    if policy_error := password_policy_error(payload.new_password, user.username):
        raise HTTPException(status_code=422, detail=policy_error)
    if verify_password(payload.new_password, user.password_hash):
        raise HTTPException(status_code=422, detail="Новый пароль должен отличаться от текущего")

    user.password_hash = hash_password(payload.new_password)
    user.password_changed_at = utcnow()
    user.password_change_failures = 0
    user.password_change_locked_until = None
    user.session_version += 1
    db.add(user)
    db.commit()
    db.refresh(user)

    set_session_cookie(response, user, settings)
    response.headers["Cache-Control"] = "no-store"
