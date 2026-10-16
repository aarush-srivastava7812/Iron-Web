import secrets

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import get_db
from .models import User
from .security import decode_token

_bearer = HTTPBearer(auto_error=False)


def _scope_user(db: Session, user_id: str) -> None:
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT set_config('voyara.user_id', :user_id, true)"), {"user_id": user_id})


def current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)
) -> User:
    uid = _identity(request, creds)
    user = db.get(User, uid) if uid else None
    if not user or not user.is_active:
        raise HTTPException(401, "Not authenticated", headers={"WWW-Authenticate": "Bearer"})
    _scope_user(db, user.id)
    return user


def optional_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)
) -> User | None:
    if not creds and not request.cookies.get("voyara_session"):
        return None
    uid = _identity(request, creds)
    user = db.get(User, uid) if uid else None
    if not user or not user.is_active:
        raise HTTPException(401, "Not authenticated", headers={"WWW-Authenticate": "Bearer"})
    _scope_user(db, user.id)
    return user


def _identity(request, creds):
    if creds:
        return decode_token(creds.credentials)
    token = request.cookies.get("voyara_session")
    if token and request.method not in {"GET", "HEAD", "OPTIONS"}:
        cookie = request.cookies.get("voyara_csrf", "")
        header = request.headers.get("x-csrf-token", "")
        if not cookie or not secrets.compare_digest(cookie, header):
            raise HTTPException(403, "Session security check failed. Reload and try again.")
    return decode_token(token) if token else None
