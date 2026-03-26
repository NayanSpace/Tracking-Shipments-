from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .utils import decode_access_token

bearer_scheme = HTTPBearer()

# Fixed user ID matching the one issued in routes.py
_FIXED_USER_ID = "00000000-0000-0000-0000-000000000001"


class AppUser:
    """Lightweight stand-in for the single app user — no DB needed."""
    id = _FIXED_USER_ID
    is_admin = True
    username = "Amico-Tracking"


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> AppUser:
    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None or payload.get("sub") != _FIXED_USER_ID:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return AppUser()


def get_current_admin(user: AppUser = Depends(get_current_user)) -> AppUser:
    return user  # The single user is always admin
