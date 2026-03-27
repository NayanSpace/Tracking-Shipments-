import logging
from datetime import datetime, timedelta
from sqlalchemy import or_

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ..database import SessionLocal
from ..models import TrackingNumber

logger = logging.getLogger(__name__)

# Module-level scheduler instance — started/stopped by main.py lifespan
scheduler = AsyncIOScheduler()


def start_scheduler():
    """Initialize background jobs and start the scheduler."""
    scheduler.add_job(
        auto_refresh_tracking,
        trigger=IntervalTrigger(hours=6),
        id="auto_refresh",
        name="Auto-refresh undelivered shipments every 3 hours",
        replace_existing=True,
        misfire_grace_time=600,   # Allow up to 10 min late start
    )

    scheduler.add_job(
        cleanup_old_tracking,
        trigger=CronTrigger(hour=2, minute=0),  # 2 AM UTC daily
        id="cleanup",
        name="Delete tracking data 3+ days after delivery",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    scheduler.start()
    logger.info("APScheduler started — 2 jobs registered")


def shutdown_scheduler():
    """Gracefully stop the scheduler on app shutdown."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")


async def auto_refresh_tracking():
    """
    Background job: re-scrape all undelivered shipments that haven't been
    updated in the last 3 hours. Runs every 3 hours.
    """
    logger.info("auto_refresh_tracking: starting")
    db = SessionLocal()
    try:
        three_hours_ago = datetime.utcnow() - timedelta(hours=6)
        to_refresh = db.query(TrackingNumber).filter(
            TrackingNumber.status.notin_(["Delivered", "Failed"]),
            or_(
                TrackingNumber.last_updated.is_(None),
                TrackingNumber.last_updated < three_hours_ago,
            ),
            or_(
                TrackingNumber.delete_at.is_(None),
                TrackingNumber.delete_at > datetime.utcnow(),
            ),
        ).all()

        ids = [str(t.id) for t in to_refresh]
        logger.info("auto_refresh_tracking: %d shipments to refresh", len(ids))
    finally:
        db.close()

    if ids:
        # Import here to avoid circular imports
        from .routes import scrape_multiple
        await scrape_multiple(ids)

    logger.info("auto_refresh_tracking: done")


async def cleanup_old_tracking():
    """
    Background job: hard-delete tracking numbers and their events when
    delete_at has passed (3 days after delivery). Runs daily at 2 AM UTC.
    """
    logger.info("cleanup_old_tracking: starting")
    db = SessionLocal()
    try:
        to_delete = db.query(TrackingNumber).filter(
            TrackingNumber.delete_at < datetime.utcnow(),
            TrackingNumber.delete_at.isnot(None),
        ).all()

        count = len(to_delete)
        for tracking in to_delete:
            db.delete(tracking)  # cascade deletes events

        db.commit()
        logger.info("cleanup_old_tracking: deleted %d records", count)
    except Exception as exc:
        logger.error("cleanup_old_tracking failed: %s", exc, exc_info=True)
        db.rollback()
    finally:
        db.close()
