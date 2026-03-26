import sys
import asyncio

# Windows: SelectorEventLoop doesn't support subprocess creation (needed by Playwright).
# Force ProactorEventLoop before uvicorn starts so Playwright can launch browsers.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from .config import get_settings
from .database import engine, get_db, Base, SessionLocal
from .models import User
from .auth.routes import router as auth_router
from .tracking.routes import router as tracking_router
from .tracking.scheduler import start_scheduler, shutdown_scheduler

import uuid
_FIXED_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

settings = get_settings()

# ─── Rate Limiter ─────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


# ─── App Lifespan ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Shipment Tracker API (env=%s)", settings.environment)

    # Create tables if they don't exist (migrations handle schema changes)
    Base.metadata.create_all(bind=engine)

    # Seed the single fixed app user so the FK constraint on tracking_numbers is satisfied
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.id == _FIXED_USER_ID).first():
            db.add(User(
                id=_FIXED_USER_ID,
                email="amico@tracking.local",
                username=settings.app_username,
                hashed_password="not-used",
                is_admin=True,
            ))
            db.commit()
            logger.info("Seeded app user into DB")
    except Exception as e:
        logger.warning("Could not seed app user: %s", e)
        db.rollback()
    finally:
        db.close()

    # Start background scheduler
    start_scheduler()

    yield  # Application runs here

    # Shutdown
    shutdown_scheduler()
    logger.info("Shipment Tracker API stopped")


# ─── FastAPI App ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Shipment Tracker API",
    description="Multi-carrier shipment tracking — UPS, FedEx, Day & Ross, Polaris",
    version="1.0.0",
    lifespan=lifespan,
    # Hide docs in production
    docs_url="/api/docs" if settings.environment != "production" else None,
    redoc_url="/api/redoc" if settings.environment != "production" else None,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — allow frontend origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Compress responses > 1KB
app.add_middleware(GZipMiddleware, minimum_size=1000)


# ─── Global Exception Handlers ────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred. Please try again.",
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": detail.get("error", "error"),
                "message": detail.get("message", str(detail)),
            },
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "error", "message": str(detail)},
    )


# ─── Health Check ─────────────────────────────────────────────────────────────
@app.get("/api/health", tags=["system"])
def health_check():
    """
    Health check endpoint used by Render.
    Returns 200 when the service is ready, 503 if the DB is unreachable.
    """
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as exc:
        logger.error("Health check DB failure: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "database": "disconnected"},
        )
    finally:
        db.close()


# ─── Routes ───────────────────────────────────────────────────────────────────
app.include_router(auth_router, prefix="/api")
app.include_router(tracking_router, prefix="/api")


@app.get("/", include_in_schema=False)
def root():
    return {"message": "Shipment Tracker API — see /api/docs for documentation"}
