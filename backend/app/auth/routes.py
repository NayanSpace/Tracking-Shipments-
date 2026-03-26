from fastapi import APIRouter, HTTPException, status
from ..schemas import UserLogin, TokenResponse, UserOut
from .utils import create_access_token
from ..config import get_settings
import uuid

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

# Fixed ID for the single app user — stable across restarts
_FIXED_USER_ID = "00000000-0000-0000-0000-000000000001"


def _get_app_user() -> UserOut:
    return UserOut(
        id=uuid.UUID(_FIXED_USER_ID),
        email="amico@tracking.local",
        username=settings.app_username,
        is_admin=True,
        created_at=None,
    )


@router.post("/login", response_model=TokenResponse)
def login(data: UserLogin):
    if data.username != settings.app_username or data.password != settings.app_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_credentials", "message": "Incorrect username or password"},
        )
    token = create_access_token({"sub": _FIXED_USER_ID})
    return {"token": token, "user": _get_app_user()}


@router.get("/me", response_model=UserOut)
def get_me():
    # JWT validation happens in the dependency — if we get here the token is valid
    return _get_app_user()


@router.post("/logout")
def logout():
    return {"message": "Logged out"}
