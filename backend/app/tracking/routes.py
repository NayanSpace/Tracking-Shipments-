import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request, status
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import or_

from ..database import get_db, SessionLocal
from ..models import TrackingNumber, TrackingEvent, CarrierEnum
from ..schemas import AddTrackingRequest, TrackingOut, TrackingListResponse
from ..auth.dependencies import get_current_user, get_current_admin, AppUser
from .scrapers import get_scraper

# Single fixed user ID — all tracking records belong to this user
_USER_ID = "00000000-0000-0000-0000-000000000001"

router = APIRouter(prefix="/tracking", tags=["tracking"])
logger = logging.getLogger(__name__)


# ─── Add Tracking ─────────────────────────────────────────────────────────────

@router.post("/add", status_code=202)
def add_tracking(
    data: AddTrackingRequest,
    background_tasks: BackgroundTasks,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Add one or more tracking numbers.
    Records are created immediately (status=Pending), scraping is queued in background.
    """
    tracking_ids = []
    for number in data.tracking_numbers:
        # Avoid duplicate tracking numbers for same user+carrier combo
        existing = db.query(TrackingNumber).filter(
            TrackingNumber.user_id == _USER_ID,
            TrackingNumber.tracking_number == number,
            TrackingNumber.carrier == data.carrier,
            or_(TrackingNumber.delete_at.is_(None), TrackingNumber.delete_at > datetime.utcnow()),
        ).first()

        if existing:
            tracking_ids.append(str(existing.id))
            continue

        tracking = TrackingNumber(
            user_id=_USER_ID,
            tracking_number=number,
            carrier=data.carrier,
            status="Pending",
            last_updated=datetime.utcnow(),
        )
        db.add(tracking)
        db.flush()  # get the ID without committing
        tracking_ids.append(str(tracking.id))

    db.commit()

    # Queue background scraping — runs after response is sent
    background_tasks.add_task(scrape_multiple, tracking_ids)

    return {
        "message": f"Added {len(tracking_ids)} tracking number(s). Scraping in progress.",
        "ids": tracking_ids,
    }


# ─── List Tracking ────────────────────────────────────────────────────────────

@router.get("/list", response_model=TrackingListResponse)
def list_tracking(
    page: int = 1,
    per_page: int = 20,
    status_filter: Optional[str] = None,
    carrier_filter: Optional[str] = None,
    search: Optional[str] = None,
    background_tasks: BackgroundTasks = None,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all tracking numbers for the current user.
    Also triggers stale-data refresh (Render free tier sleep mitigation).
    """
    query = (
        db.query(TrackingNumber)
        .options(selectinload(TrackingNumber.events))
        .filter(
            TrackingNumber.user_id == _USER_ID,
            or_(
                TrackingNumber.delete_at.is_(None),
                TrackingNumber.delete_at > datetime.utcnow(),
            ),
        )
    )

    if status_filter:
        query = query.filter(TrackingNumber.status == status_filter)
    if carrier_filter:
        query = query.filter(TrackingNumber.carrier == carrier_filter)
    if search:
        query = query.filter(TrackingNumber.tracking_number.ilike(f"%{search}%"))

    total = query.count()
    items = (
        query.order_by(TrackingNumber.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    # Render free tier mitigation: refresh stale undelivered shipments when user loads the page
    if background_tasks:
        three_hours_ago = datetime.utcnow() - timedelta(hours=3)
        stale_ids = [
            str(t.id)
            for t in items
            if t.status not in ("Delivered", "Failed")
            and (t.last_updated is None or t.last_updated < three_hours_ago)
        ]
        if stale_ids:
            background_tasks.add_task(scrape_multiple, stale_ids)

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "data": [TrackingOut.model_validate(t) for t in items],
    }


# ─── Get Single Tracking ──────────────────────────────────────────────────────

@router.get("/{tracking_id}", response_model=TrackingOut)
def get_tracking(
    tracking_id: UUID,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tracking = (
        db.query(TrackingNumber)
        .options(selectinload(TrackingNumber.events))
        .filter(
            TrackingNumber.id == tracking_id,
            TrackingNumber.user_id == _USER_ID,
        )
        .first()
    )

    if not tracking:
        raise HTTPException(status_code=404, detail="Tracking not found")

    return TrackingOut.model_validate(tracking)


# ─── Manual Refresh ───────────────────────────────────────────────────────────

@router.post("/{tracking_id}/refresh")
def refresh_tracking(
    tracking_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tracking = db.query(TrackingNumber).filter(
        TrackingNumber.id == tracking_id,
        TrackingNumber.user_id == _USER_ID,
    ).first()

    if not tracking:
        raise HTTPException(status_code=404, detail="Tracking not found")

    background_tasks.add_task(scrape_and_update, str(tracking_id))
    return {"message": "Refresh queued — check back in a few seconds"}


# ─── Delete Tracking ──────────────────────────────────────────────────────────

@router.delete("/{tracking_id}")
def delete_tracking(
    tracking_id: UUID,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tracking = db.query(TrackingNumber).filter(
        TrackingNumber.id == tracking_id,
        TrackingNumber.user_id == _USER_ID,
    ).first()

    if not tracking:
        raise HTTPException(status_code=404, detail="Tracking not found")

    # Soft delete — set delete_at to now so cleanup job removes it
    tracking.delete_at = datetime.utcnow()
    db.commit()
    return {"message": "Tracking removed"}


# ─── Admin Endpoints ──────────────────────────────────────────────────────────

@router.get("/admin/jobs/status")
def get_job_status(current_user: AppUser = Depends(get_current_admin)):
    from ..tracking.scheduler import scheduler
    jobs = [
        {
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
        }
        for job in scheduler.get_jobs()
    ]
    return {"running": scheduler.running, "jobs": jobs}


@router.post("/admin/jobs/trigger-refresh")
async def trigger_refresh(current_user: AppUser = Depends(get_current_admin)):
    from ..tracking.scheduler import auto_refresh_tracking
    await auto_refresh_tracking()
    return {"message": "Auto-refresh job triggered"}


@router.post("/admin/jobs/trigger-cleanup")
async def trigger_cleanup(current_user: AppUser = Depends(get_current_admin)):
    from ..tracking.scheduler import cleanup_old_tracking
    await cleanup_old_tracking()
    return {"message": "Cleanup job triggered"}


# ─── Scraping Logic (background tasks) ───────────────────────────────────────

async def scrape_and_update(tracking_id: str):
    """Scrape a single tracking number and update the database."""
    db = SessionLocal()
    try:
        tracking = db.query(TrackingNumber).filter(
            TrackingNumber.id == tracking_id
        ).first()

        if not tracking:
            return

        logger.info("Scraping %s %s", tracking.carrier, tracking.tracking_number)
        scraper = get_scraper(tracking.carrier.value if hasattr(tracking.carrier, "value") else tracking.carrier)
        result = await scraper.scrape(tracking.tracking_number)

        if result.get("error"):
            tracking.error_message = result["error"]
            tracking.retry_count = (tracking.retry_count or 0) + 1
            if tracking.retry_count >= 5:
                tracking.status = "Failed"
            logger.warning(
                "Scrape error for %s: %s (retry %d)",
                tracking.tracking_number, result["error"], tracking.retry_count,
            )
        else:
            tracking.status = result.get("status", "Unknown")
            tracking.current_location = result.get("current_location")
            tracking.estimated_delivery = result.get("estimated_delivery")
            tracking.delivered_date = result.get("delivered_date")
            tracking.raw_data = {k: str(v) for k, v in result.items() if k != "events"}
            tracking.error_message = None
            tracking.retry_count = 0

            # Schedule auto-delete 3 days after delivery
            if tracking.status == "Delivered" and result.get("delivered_date"):
                tracking.delete_at = datetime.combine(
                    result["delivered_date"], datetime.min.time()
                ) + timedelta(days=3)

            # Upsert tracking events (avoid duplicates)
            for event in result.get("events", []):
                ts = event.get("timestamp")
                desc = event.get("description", "")
                if not ts:
                    continue

                existing = db.query(TrackingEvent).filter(
                    TrackingEvent.tracking_id == tracking_id,
                    TrackingEvent.timestamp == ts,
                    TrackingEvent.description == desc,
                ).first()

                if not existing:
                    db.add(TrackingEvent(
                        tracking_id=tracking_id,
                        timestamp=ts,
                        location=event.get("location"),
                        status=event.get("status"),
                        description=desc,
                    ))

            logger.info(
                "Updated %s %s → %s",
                tracking.carrier, tracking.tracking_number, tracking.status,
            )

        tracking.last_updated = datetime.utcnow()
        db.commit()

    except Exception as exc:
        logger.error("scrape_and_update crashed for %s: %s", tracking_id, exc, exc_info=True)
        db.rollback()
    finally:
        db.close()


async def scrape_multiple(tracking_ids: List[str]):
    """
    Scrape multiple tracking numbers.
    Groups by carrier and processes each carrier sequentially
    (to respect rate limits), but different carriers run in parallel.
    """
    if not tracking_ids:
        return

    db = SessionLocal()
    try:
        trackings = db.query(TrackingNumber).filter(
            TrackingNumber.id.in_(tracking_ids)
        ).all()

        by_carrier: dict[str, list[str]] = {}
        for t in trackings:
            carrier = t.carrier.value if hasattr(t.carrier, "value") else t.carrier
            by_carrier.setdefault(carrier, []).append(str(t.id))
    finally:
        db.close()

    # Run carriers in parallel, sequential within each carrier
    tasks = [_scrape_carrier_batch(carrier, ids) for carrier, ids in by_carrier.items()]
    await asyncio.gather(*tasks)


async def _scrape_carrier_batch(carrier: str, tracking_ids: List[str]):
    """Process tracking IDs for one carrier sequentially with delays."""
    for tracking_id in tracking_ids:
        await scrape_and_update(tracking_id)
        # Delay between requests to avoid rate limiting
        delay = 30 if carrier == "FEDEX" else random.uniform(5, 10)
        await asyncio.sleep(delay)
