import datetime as dt
import secrets

import jwt
from argon2 import PasswordHasher

from .config import settings

_ph = PasswordHasher()


def hash_password(p: str) -> str:
    return _ph.hash(p)


def verify_password(hashed: str, p: str) -> bool:
    try:
        return _ph.verify(hashed, p)
    except Exception:
        return False


def create_token(user_id: str) -> str:
    exp = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=settings.access_token_minutes)
    return jwt.encode({"sub": user_id, "exp": exp}, settings.secret_key, algorithm="HS256")


def decode_token(token: str) -> str | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=["HS256"])["sub"]
    except jwt.PyJWTError:
        return None


def set_session_cookies(response, user_id: str):
    ttl = settings.access_token_minutes * 60
    response.set_cookie("voyara_session", create_token(user_id), max_age=ttl, httponly=True,
                        secure=settings.cookie_secure, samesite="lax")
    response.set_cookie("voyara_csrf", secrets.token_urlsafe(32), max_age=ttl,
                        secure=settings.cookie_secure, samesite="lax")
