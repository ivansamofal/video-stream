from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.security import decode_token

limiter = Limiter(key_func=get_remote_address, storage_uri=settings.redis_url)


def user_or_ip(request: Request) -> str:
    """Rate-limit key: authenticated user ID when available, otherwise IP."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        payload = decode_token(auth[7:])
        if payload and payload.get("sub"):
            return f"user:{payload['sub']}"
    return get_remote_address(request)
