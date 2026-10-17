"""Google Identity Services ID-token sign-in; no OAuth client secret required."""
import hashlib
import secrets
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import current_user
from ..models import GoogleIdentity, LoginChallenge, User
from ..schemas import UserOut
from ..security import hash_password, set_session_cookies

router = APIRouter(prefix="/auth", tags=["auth"])


def configured():
    value = settings.google_client_id
    return bool(value.endswith(".apps.googleusercontent.com") and value[0].isdigit()
                and "YOUR" not in value.upper() and "PLACEHOLDER" not in value.upper())


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


@router.get("/google/config")
def google_config(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    if not configured():
        return {"configured": False, "client_id": None, "nonce": None}
    nonce = secrets.token_urlsafe(32)
    now = int(time.time())
    db.execute(delete(LoginChallenge).where(LoginChallenge.expires_at < now))
    db.add(LoginChallenge(digest=digest(nonce), expires_at=now + 600))
    db.commit()
    response.set_cookie("voyara_google_nonce", nonce, max_age=600, httponly=True,
                        secure=settings.cookie_secure, samesite="lax", path="/api/auth")
    return {"configured": True, "client_id": settings.google_client_id, "nonce": nonce}


class GoogleCredential(BaseModel):
    credential: str = Field(min_length=1, max_length=8192)
    nonce: str = Field(min_length=20, max_length=128)


def verify_google(credential):
    # google-auth checks Google's signature, audience, issuer and expiry.
    return id_token.verify_oauth2_token(credential, GoogleRequest(), settings.google_client_id)


@router.post("/google", response_model=UserOut)
def google_login(body: GoogleCredential, request: Request, response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    if not configured():
        raise HTTPException(503, "Google sign-in is not configured. Set GOOGLE_CLIENT_ID in backend/.env.")
    if len(settings.secret_key) < 32 or settings.secret_key.startswith(("dev-only", "change-me")):
        raise HTTPException(503, "Set a strong SECRET_KEY in backend/.env before enabling sign-in.")
    cookie = request.cookies.get("voyara_google_nonce", "")
    challenge = db.get(LoginChallenge, digest(body.nonce))
    if not cookie or not secrets.compare_digest(cookie, body.nonce) or not challenge or challenge.expires_at < time.time():
        raise HTTPException(401, "Sign-in expired. Reload the sign-in page.")
    try:
        claims = verify_google(body.credential)
    except ValueError as error:
        raise HTTPException(401, "Google could not verify this sign-in.") from error
    except Exception as error:
        raise HTTPException(503, "Google verification is temporarily unavailable. Try again.") from error
    if not secrets.compare_digest(str(claims.get("nonce", "")), body.nonce):
        raise HTTPException(401, "Invalid sign-in nonce")
    if not claims.get("sub") or claims.get("email_verified") is not True or not claims.get("email"):
        raise HTTPException(401, "A verified Google email is required")
    # Consume atomically, including when two callbacks arrive concurrently.
    consumed = db.execute(delete(LoginChallenge).where(LoginChallenge.digest == challenge.digest,
                                                      LoginChallenge.expires_at >= int(time.time())))
    if consumed.rowcount != 1:
        raise HTTPException(401, "Sign-in was already used. Reload the sign-in page.")
    identity = db.get(GoogleIdentity, claims["sub"])
    if identity:
        user = db.get(User, identity.user_id)
    else:
        email = str(claims["email"]).lower()
        user = db.scalar(select(User).where(User.email == email))
        authoritative = email.endswith("@gmail.com") or bool(claims.get("hd"))
        if user and not authoritative:
            raise HTTPException(409, "This email already has an account. Contact support to link Google securely.")
        if user and db.scalar(select(GoogleIdentity).where(GoogleIdentity.user_id == user.id)):
            raise HTTPException(409, "This account is linked to a different Google identity.")
        if not user:
            user = User(email=email, username="google_" + uuid.uuid4().hex[:24],
                        password_hash=hash_password(secrets.token_urlsafe(48)),
                        full_name=str(claims.get("name", ""))[:120] or None)
            db.add(user)
            db.flush()
        db.add(GoogleIdentity(subject=claims["sub"], user_id=user.id))
    if not user or not user.is_active:
        raise HTTPException(401, "Account is inactive")
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "Sign-in changed in another tab. Reload and retry.") from error
    set_session_cookies(response, user.id)
    response.delete_cookie("voyara_google_nonce", path="/api/auth")
    return user


@router.post("/logout", status_code=204)
def logout(response: Response, user: User = Depends(current_user)):
    response.delete_cookie("voyara_session")
    response.delete_cookie("voyara_csrf")
