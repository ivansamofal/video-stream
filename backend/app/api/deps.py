import json
from datetime import datetime

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import decode_token
from app.models.user import User

bearer = HTTPBearer()

_redis: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def _user_from_cache(data: dict) -> User:
    user = User(
        id=data["id"],
        email=data["email"],
        hashed_password=data["hashed_password"],
        is_admin=data["is_admin"],
        created_at=datetime.fromisoformat(data["created_at"]),
    )
    return user


def _user_to_cache(user: User) -> str:
    return json.dumps({
        "id": user.id,
        "email": user.email,
        "hashed_password": user.hashed_password,
        "is_admin": user.is_admin,
        "created_at": user.created_at.isoformat(),
    })


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> User:
    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user_id = int(payload["sub"])
    redis = _get_redis()

    cached = await redis.get(f"user_cache:{user_id}")
    if cached:
        return _user_from_cache(json.loads(cached))

    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    ttl = settings.access_token_expire_minutes * 60
    await redis.setex(f"user_cache:{user_id}", ttl, _user_to_cache(user))
    return user


async def get_admin_user(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user
