"""
Password hashing and JWT issuing/verification.

Uses bcrypt and PyJWT directly rather than passlib + python-jose: both of those
are effectively unmaintained, and on a serverless host their dependency trees
are dead weight against the function size limit.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import get_db
from ..models import User

logger = logging.getLogger(__name__)
settings = get_settings()

# auto_error=False so a missing header reaches our own handler and returns the
# app's error envelope instead of FastAPI's bare {"detail": "Not authenticated"}.
_bearer = HTTPBearer(auto_error=False)

# bcrypt silently truncates at 72 bytes; rejecting longer input is safer than
# letting two different passwords authenticate the same account.
_MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        # Malformed hash in the database — treat as a failed login, never a 500.
        return False


def password_too_long(password: str) -> bool:
    return len(password.encode()) > _MAX_PASSWORD_BYTES


def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def _unauthorized(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "UNAUTHORIZED", "message": message},
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """FastAPI dependency: resolve the bearer token to a live, active user."""
    if creds is None:
        raise _unauthorized("Sign in to continue.")

    try:
        payload = jwt.decode(
            creds.credentials, settings.secret_key, algorithms=[settings.algorithm]
        )
        user_id = int(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Your session has expired. Please sign in again.")
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        raise _unauthorized("Invalid session. Please sign in again.")

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or not user.is_active:
        raise _unauthorized("Account not found or disabled.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
