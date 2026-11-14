from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import (
    burn_dummy_verify,
    client_ip,
    create_session,
    current_user,
    end_session,
    hash_password,
    verify_password,
)
from ..config import get_settings
from ..db import get_db
from ..models import User
from ..ratelimit import limiter
from ..schemas import LoginIn, SignupIn, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _login_limits(request: Request, email: str) -> None:
    s = get_settings()
    limiter.check(f"login-ip:{client_ip(request)}", s.rate_logins_per_15min, 900)
    limiter.check(f"login-email:{email}", s.rate_logins_per_15min, 900)


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def signup(body: SignupIn, request: Request, response: Response, db: Session = Depends(get_db)):
    email = body.email.lower()
    _login_limits(request, email)
    user = User(email=email, name=body.name, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "An account with this email already exists"
        ) from None
    create_session(db, user, response)
    return user


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    email = body.email.lower()
    _login_limits(request, email)
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        burn_dummy_verify(body.password)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")
    if not verify_password(user.password_hash, body.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")
    create_session(db, user, response)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    end_session(db, request, response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user
