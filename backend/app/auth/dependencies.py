from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.models import User
from app.core.config import Settings, get_settings
from app.core.security import decode_session_token
from app.database.session import get_core_db


def current_user(
    db: Annotated[Session, Depends(get_core_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    mlib_session: Annotated[str | None, Cookie()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    token = mlib_session
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    identity = decode_session_token(token, settings.secret_key) if token else None
    user = db.get(User, identity.user_id) if identity else None
    if user is None or not user.is_active or user.session_version != identity.version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется авторизация")
    return user


def admin_user(user: Annotated[User, Depends(current_user)]) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Требуются права администратора")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
AdminUser = Annotated[User, Depends(admin_user)]
