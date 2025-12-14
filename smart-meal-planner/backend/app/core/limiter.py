from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request
from jose import JWTError, jwt
from app.core.config import settings
import logging

def get_rate_limit_key(request: Request) -> str:
    """
    Determines the key for rate limiting.
    - If a valid JWT is present, the user's ID is used as the key.
    - Otherwise, the user's IP address is used.
    """
    # Default to IP address
    key = get_remote_address(request)

    # Check for JWT in Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
            try:
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                user_id = payload.get("sub")
                if user_id:
                    key = str(user_id)
            except JWTError as e:
                logging.warning(f"JWTError in rate limiting: {e}")
                # Token is invalid, fall back to IP-based limiting
                pass
    return key

limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=["60/minute"],
)
