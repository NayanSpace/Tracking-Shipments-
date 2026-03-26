from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import get_settings

settings = get_settings()

# psycopg3 requires the dialect prefix "postgresql+psycopg://" in the URL.
# Neon provides "postgresql://..." so we swap it here transparently.
_db_url = settings.database_url.replace(
    "postgresql://", "postgresql+psycopg://", 1
).replace(
    "postgres://", "postgresql+psycopg://", 1
)

# Neon free tier: max 10 connections. pool_pre_ping re-establishes connections
# after Neon wakes from its 5-minute idle sleep.
engine = create_engine(
    _db_url,
    pool_pre_ping=True,
    pool_size=3,
    max_overflow=2,
    pool_recycle=300,
    connect_args={
        "connect_timeout": 10,
        "application_name": "shipment-tracker",
    },
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency — yields a database session and closes it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
