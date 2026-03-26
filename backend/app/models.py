import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, DateTime, Date, Integer, Text, ForeignKey, Enum
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from .database import Base

import enum


class CarrierEnum(str, enum.Enum):
    UPS = "UPS"
    FEDEX = "FEDEX"
    DAYROSS = "DAYROSS"
    POLARIS = "POLARIS"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    tracking_numbers = relationship(
        "TrackingNumber", back_populates="user", cascade="all, delete-orphan"
    )


class TrackingNumber(Base):
    __tablename__ = "tracking_numbers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tracking_number = Column(String(100), nullable=False, index=True)
    carrier = Column(
        Enum(CarrierEnum, name="carrierenum"), nullable=False
    )
    status = Column(String(50), default="Pending")
    current_location = Column(String(255), nullable=True)
    estimated_delivery = Column(Date, nullable=True)
    delivered_date = Column(Date, nullable=True)
    last_updated = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    delete_at = Column(DateTime, nullable=True, index=True)
    raw_data = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    user = relationship("User", back_populates="tracking_numbers")
    events = relationship(
        "TrackingEvent", back_populates="tracking", cascade="all, delete-orphan",
        order_by="TrackingEvent.timestamp.desc()"
    )


class TrackingEvent(Base):
    __tablename__ = "tracking_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tracking_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tracking_numbers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    timestamp = Column(DateTime, nullable=False)
    location = Column(String(255), nullable=True)
    status = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    tracking = relationship("TrackingNumber", back_populates="events")
