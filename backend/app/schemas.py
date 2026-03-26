from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List
from datetime import datetime, date
from uuid import UUID


# ─── Auth Schemas ─────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("username")
    @classmethod
    def username_min_length(cls, v: str) -> str:
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters")
        return v.strip()


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: UUID
    email: str
    username: str
    is_admin: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    token: str
    user: UserOut


# ─── Tracking Schemas ─────────────────────────────────────────────────────────

class AddTrackingRequest(BaseModel):
    carrier: str
    tracking_numbers: List[str]

    @field_validator("carrier")
    @classmethod
    def validate_carrier(cls, v: str) -> str:
        allowed = {"UPS", "FEDEX", "DAYROSS", "POLARIS"}
        v = v.upper()
        if v not in allowed:
            raise ValueError(f"Carrier must be one of: {', '.join(allowed)}")
        return v

    @field_validator("tracking_numbers")
    @classmethod
    def validate_tracking_numbers(cls, v: List[str]) -> List[str]:
        cleaned = [n.strip() for n in v if n.strip()]
        if not cleaned:
            raise ValueError("At least one tracking number is required")
        if len(cleaned) > 50:
            raise ValueError("Maximum 50 tracking numbers per request")
        return cleaned


class TrackingEventOut(BaseModel):
    id: UUID
    timestamp: datetime
    location: Optional[str]
    status: Optional[str]
    description: Optional[str]

    model_config = {"from_attributes": True}


class TrackingOut(BaseModel):
    id: UUID
    tracking_number: str
    carrier: str
    status: Optional[str]
    current_location: Optional[str]
    estimated_delivery: Optional[date]
    delivered_date: Optional[date]
    last_updated: Optional[datetime]
    created_at: datetime
    delete_at: Optional[datetime]
    error_message: Optional[str]
    retry_count: int
    events: List[TrackingEventOut] = []

    model_config = {"from_attributes": True}


class TrackingListResponse(BaseModel):
    total: int
    page: int
    per_page: int
    data: List[TrackingOut]
