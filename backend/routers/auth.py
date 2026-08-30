"""
POST /api/v1/auth/signup — create an account
POST /api/v1/auth/login  — exchange credentials for a JWT
GET  /api/v1/auth/me     — the signed-in user
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.security import (
    CurrentUser,
    create_access_token,
    hash_password,
    verify_password,
)
from ..database import get_db
from ..models import User
from ..schemas import LoginRequest, SignupRequest, TokenResponse, UserOut

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# Emails are matched case-insensitively; store them folded so "A@x.com" and
# "a@x.com" cannot become two accounts.
def _normalize(email: str) -> str:
    return email.strip().lower()


@router.post(
    "/signup",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account",
)
@limiter.limit("5/minute")
async def signup(
    request: Request,
    payload: SignupRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    email = _normalize(payload.email)

    existing = (
        await db.execute(select(User).where(func.lower(User.email) == email))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "EMAIL_TAKEN",
                "message": "That email already has an account. Try signing in.",
            },
        )

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name.strip(),
    )
    db.add(user)
    await db.flush()          # assigns user.id without ending the transaction
    await db.refresh(user)

    logger.info("Account created: %s", email)
    return TokenResponse(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenResponse, summary="Sign in")
@limiter.limit("10/minute")
async def login(
    request: Request,
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    email = _normalize(payload.email)
    user = (
        await db.execute(select(User).where(func.lower(User.email) == email))
    ).scalar_one_or_none()

    # One message for both "no such account" and "wrong password" — telling them
    # apart lets anyone enumerate which emails are registered.
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "BAD_CREDENTIALS", "message": "Incorrect email or password."},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ACCOUNT_DISABLED", "message": "This account has been disabled."},
        )

    return TokenResponse(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut, summary="Current user")
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)
