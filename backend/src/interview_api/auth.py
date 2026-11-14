"""Passwords (argon2id) and cookie sessions (opaque random token; only its SHA-256 is stored)."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import AuthSession, User

_hasher = PasswordHasher()  # argon2id with the library's current recommended parameters
# Verified against when the email is unknown, so a login takes the same time either way.
_DUMMY_HASH = _hasher.hash("not-a-real-password-just-for-timing")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def burn_dummy_verify(password: str) -> None:
    verify_password(_DUMMY_HASH, password)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def cookie_secure(request: Request) -> bool:
    mode = get_settings().cookie_secure
    if mode != "auto":
        return mode == "true"
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    return proto.split(",")[0].strip().lower() == "https"


def create_session(db: Session, user: User, request: Request, response: Response) -> None:
    settings = get_settings()
    token = secrets.token_urlsafe(32)
    expires = datetime.now(UTC) + timedelta(days=settings.session_days)
    db.add(AuthSession(user_id=user.id, token_hash=token_hash(token), expires_at=expires))
    # Opportunistic clean-up of this user's expired sessions.
    db.execute(
        delete(AuthSession).where(
            AuthSession.user_id == user.id, AuthSession.expires_at < datetime.now(UTC)
        )
    )
    db.commit()
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_days * 86400,
        httponly=True,
        secure=cookie_secure(request),
        samesite="lax",
        path="/",
    )


def end_session(db: Session, request: Request, response: Response) -> None:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == token_hash(token)))
        db.commit()
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        httponly=True,
        secure=cookie_secure(request),
        samesite="lax",
    )


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Dependency: the logged-in user, or 401."""
    token = request.cookies.get(get_settings().session_cookie_name)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in")
    row = db.execute(
        select(AuthSession).where(
            AuthSession.token_hash == token_hash(token),
            AuthSession.expires_at > datetime.now(UTC),
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")
    return row.user


def client_ip(request: Request) -> str:
    if get_settings().trust_proxy_headers:
        # Set by our own Next.js proxy, which overwrites anything the browser sent. Needed on hosts
        # whose internal service-to-service hop rewrites X-Forwarded-For (Vercel bindings do). The
        # name is app-specific so it cannot collide with a header a platform sets.
        own = (request.headers.get("x-interview-client-ip") or "").strip()
        if own:
            return own
        # The right-most entry was added by the proxy closest to us; earlier entries are
        # whatever the client claimed and can't be trusted.
        fwd = request.headers.get("x-forwarded-for")
        if fwd and fwd.split(",")[-1].strip():
            return fwd.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"
