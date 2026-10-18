import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..config import settings
from ..deps import current_user
from ..models import User
from ..schemas import LoginIn, RegisterIn, TokenOut, UserOut, UserPatch
from ..security import create_token, hash_password, verify_password, set_session_cookies

router = APIRouter(prefix="/auth", tags=["auth"])

_DEV_USERNAME = "voyara_local_developer"
_DEV_EMAIL = "developer@voyara.example.com"
_DEV_PASSWORD_MARKER = "!local-developer-only!"


def _judge_demo_available():
    return bool(settings.judge_demo_enabled and settings.cookie_secure
                and settings.judge_demo_origins
                and all(origin.startswith("https://") for origin in settings.judge_demo_origins)
                and len(settings.secret_key) >= 32
                and not settings.secret_key.startswith(("dev-only", "change-me")))


@router.get("/judge/config")
def judge_demo_config():
    return {"enabled": _judge_demo_available()}


@router.post("/judge", response_model=UserOut)
def judge_demo_login(request: Request, response: Response, db: Session = Depends(get_db)):
    if not _judge_demo_available():
        raise HTTPException(404, "Not found")
    if (request.headers.get("origin") not in settings.judge_demo_origins
            or request.headers.get("x-voyara-judge") != "1"):
        raise HTTPException(403, "Open judge demo access from the Voyara website.")
    # Separate ordinary travelers prevent judges from sharing trips or impersonating users.
    tag = secrets.token_hex(12)
    user = User(username="judge_" + tag, email="judge_" + tag + "@demo.voyara.example.com",
                full_name="Voyara Judge", password_hash="!judge-demo-session-only!", role="user")
    db.add(user)
    db.commit()
    set_session_cookies(response, user.id)
    return user


def _developer_available(request: Request):
    return bool(settings.developer_login_enabled and not settings.cookie_secure
                and request.client and request.client.host in {"127.0.0.1", "::1"}
                and request.url.hostname in {"localhost", "127.0.0.1", "::1"}
                and not any(key in request.headers for key in ("x-forwarded-for", "x-forwarded-host", "forwarded")))


@router.get("/developer/config")
def developer_config(request: Request):
    return {"enabled": _developer_available(request)}


@router.post("/developer", response_model=UserOut)
def developer_login(request: Request, response: Response, db: Session = Depends(get_db)):
    if not _developer_available(request):
        raise HTTPException(404, "Not found")
    if (request.headers.get("origin") != str(request.base_url).rstrip("/")
            or request.headers.get("x-voyara-developer") != "1"):
        raise HTTPException(403, "Open developer sign-in from the local application.")
    if len(settings.secret_key) < 32 or settings.secret_key.startswith(("dev-only", "change-me")):
        raise HTTPException(503, "Configure a strong SECRET_KEY before signing in.")
    user = db.scalar(select(User).where(or_(User.username == _DEV_USERNAME, User.email == _DEV_EMAIL)))
    if user is None:
        # Ordinary, dedicated account; never impersonate a Google user or grant admin rights.
        user = User(username=_DEV_USERNAME, email=_DEV_EMAIL, full_name="Voyara Developer",
                    password_hash=_DEV_PASSWORD_MARKER, role="user")
        db.add(user)
        db.commit()
    if (user.username != _DEV_USERNAME or user.email != _DEV_EMAIL
            or user.password_hash != _DEV_PASSWORD_MARKER or not user.is_active or user.role != "user"):
        raise HTTPException(409, "Developer account is unavailable; an existing account will not be replaced.")
    set_session_cookies(response, user.id)
    return user


@router.post("/register", response_model=TokenOut, status_code=201)
def register(body: RegisterIn, response: Response, session: bool = False, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(or_(User.email == email, User.username == body.username))):
        raise HTTPException(409, "Email or username already in use")
    user = User(email=email, username=body.username, password_hash=hash_password(body.password),
                full_name=body.full_name, phone=body.phone)
    db.add(user)
    db.commit()
    if session:
        set_session_cookies(response, user.id)
    return TokenOut(access_token=create_token(user.id), user=user)


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, response: Response, session: bool = False, db: Session = Depends(get_db)):
    ident = body.identifier.strip()
    user = db.scalar(select(User).where(or_(User.email == ident.lower(), User.username == ident)))
    if not user or not user.is_active or not verify_password(user.password_hash, body.password):
        raise HTTPException(401, "Invalid credentials")
    if session:
        set_session_cookies(response, user.id)
    return TokenOut(access_token=create_token(user.id), user=user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.patch("/me", response_model=UserOut)
def update_me(body: UserPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(user, k, v)
    db.commit()
    return user
