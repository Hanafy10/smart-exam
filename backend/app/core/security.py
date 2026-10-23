import os
from datetime import datetime, timedelta, timezone
from typing import Any, Union, Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import (
    SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_HOURS,
    MAX_LOGIN_ATTEMPTS,
    LOCK_MINUTES,
    RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW_MINUTES,
)
from backend.app.core.database import get_db
from backend.app.models.models import User, UserRole, ExamRoom

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# Simple in-memory rate limiter: {key: list[datetime]}
_rate_limit_store: dict[str, list[datetime]] = {}

def _check_rate_limit(key: str, limit: int = RATE_LIMIT_REQUESTS, window_minutes: int = RATE_LIMIT_WINDOW_MINUTES) -> bool:
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=window_minutes)
    timestamps = _rate_limit_store.get(key, [])
    valid_timestamps = [t for t in timestamps if t > window_start]
    _rate_limit_store[key] = valid_timestamps
    if len(valid_timestamps) >= limit:
        return False
    _rate_limit_store[key].append(now)
    return True

def validate_password_strength(password: str) -> None:
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters")

def create_access_token(subject: Union[str, Any], role: str, assigned_room_id: Optional[int] = None, expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "role": role,
        "assigned_room_id": assigned_room_id,
        "type": "access",
    }
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(subject: Union[str, Any]) -> str:
    # 2 hours per requirement
    expire = datetime.now(timezone.utc) + timedelta(hours=REFRESH_TOKEN_EXPIRE_HOURS)
    to_encode = {"exp": expire, "sub": str(subject), "type": "refresh"}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
        token_type = payload.get("type")
        if token_type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    user = (await db.execute(select(User).where(User.id == user_id))).scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session user no longer exists",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been deactivated",
        )
    return user

async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permissions required",
        )
    return user

async def require_invigilator(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.INVIGILATOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invigilator permissions required",
        )
    return user

async def get_assigned_room(
    user: User = Depends(require_invigilator), db: AsyncSession = Depends(get_db)
) -> ExamRoom:
    """
    Retrieves the invigilator's assigned room from trusted database state.
    Raises 403 Forbidden with 'No exam room assigned' if unassigned or invalid.
    """
    if user.assigned_room_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No exam room assigned",
        )
    
    room = (
        await db.execute(select(ExamRoom).where(ExamRoom.id == user.assigned_room_id))
    ).scalars().first()

    if not room:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No exam room assigned",
        )
    return room

def _client_ip(request: Request) -> Optional[str]:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None
