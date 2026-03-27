import asyncio
import random
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from playwright.sync_api import sync_playwright

from .base import BaseScraper

logger = logging.getLogger(__name__)

# Day & Ross tracking form (new URL after their 2026 site refresh)
DAYROSS_TRACK_URL = "https://www.dayross.com/track-shipments"
# Their internal TruckMate API endpoint (intercepted from network)
DAYROSS_API_PATTERN = "ece.dayrossgroup.com/TruckMateAPI/api/ManageOrders/TrackOrders"
TIMEOUT_MS = 35_000


class DayRossScraper(BaseScraper):
    """
    Scrapes Day & Ross tracking.
    Strategy: navigate to /track-shipments, fill the shipmentNumbers form,
    then intercept the TruckMateAPI JSON response.
    """

    async def scrape(self, tracking_number: str) -> Dict[str, Any]:
        last_error = None
        for attempt in range(1, 4):
            try:
                result = await asyncio.to_thread(self._sync_scrape, tracking_number)
                if result.get("error") is None:
                    return result
                last_error = result["error"]
            except Exception as exc:
                last_error = str(exc)
                logger.warning("Day & Ross attempt %d/3 failed for %s: %s", attempt, tracking_number, last_error)
            if attempt < 3:
                await asyncio.sleep(2 ** attempt + random.uniform(1, 2))
        return self._empty_result(f"Day & Ross scrape failed after 3 attempts: {last_error}")

    def _sync_scrape(self, tracking_number: str) -> Dict[str, Any]:
        intercepted: List[dict] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
                locale="en-CA",
            )
            page = context.new_page()

            def handle_response(response):
                try:
                    if response.status != 200:
                        return
                    if DAYROSS_API_PATTERN in response.url:
                        body = response.json()
                        intercepted.append(body)
                        logger.debug("Day & Ross: intercepted TruckMateAPI from %s", response.url)
                except Exception:
                    pass

            page.on("response", handle_response)

            try:
                page.goto(DAYROSS_TRACK_URL, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
                page.wait_for_timeout(3000)

                # Fill the shipmentNumbers textarea and submit
                try:
                    page.wait_for_selector('textarea[name="shipmentNumbers"]', timeout=10_000)
                    page.fill('textarea[name="shipmentNumbers"]', tracking_number)
                    page.wait_for_timeout(500)
                    page.click('input[type="submit"], button[type="submit"]')
                    logger.debug("Day & Ross: submitted form for %s", tracking_number)
                except Exception as e:
                    logger.warning("Day & Ross: form submission failed: %s", e)
                    return self._empty_result(f"Day & Ross form submission failed: {e}")

                # Wait for the API response
                page.wait_for_timeout(random.randint(5000, 8000))

                # Try API response first
                for data in reversed(intercepted):
                    result = self._parse_api_response(data)
                    if result:
                        logger.info("Day & Ross: parsed from TruckMateAPI for %s", tracking_number)
                        return result

                # If no API data, check page text for errors
                page_text = (page.inner_text("body") or "").lower()
                if any(w in page_text for w in ["not found", "no results", "no shipment"]):
                    return self._empty_result("Tracking number not found on Day & Ross")

                return self._empty_result("Day & Ross: no tracking data returned from API")

            except Exception as exc:
                return self._empty_result(f"Day & Ross page error: {exc}")
            finally:
                browser.close()

    def _parse_api_response(self, data: dict) -> Optional[Dict[str, Any]]:
        """
        Parse Day & Ross TruckMateAPI response.
        Shape: { "orderItems": [{ "status": "...", "statusCode": "...", ... }], "total": 1 }
        Note: detailed event history requires a logged-in Day & Ross account session.
        The public API returns summary data only.
        """
        try:
            order_items = data.get("orderItems", [])
            if not order_items:
                return None

            item = order_items[0]
            status_raw = item.get("status", "") or ""
            status_code = item.get("statusCode", "") or ""
            if not status_raw and not status_code:
                return None

            from_info = item.get("from", {}) or {}
            to_info = item.get("to", {}) or {}

            origin_parts = [from_info.get("city", ""), from_info.get("provinceCode", ""), from_info.get("countryCode", "")]
            origin = ", ".join(p for p in origin_parts if p) or None

            dest_parts = [to_info.get("city", ""), to_info.get("provinceCode", ""), to_info.get("countryCode", "")]
            destination = ", ".join(p for p in dest_parts if p) or None

            delivered_raw = item.get("deliveryDate") or ""
            est_raw = item.get("estimatedDeliveryDate") or ""

            # Status mapping — use statusCode first for precision, fall back to status text
            status_code_upper = status_code.upper()
            if status_code_upper in ("COMPLETE", "DELIVERED"):
                status = "Delivered"
            elif status_code_upper in ("SVCFAILURE", "EXCEPTION", "DAMAGED", "REFUSED"):
                status = "Exception"
            elif status_code_upper in ("INTRANSIT", "IN_TRANSIT", "PICKED_UP", "DISPATCHED"):
                status = "In Transit"
            elif status_code_upper in ("PENDING", "BOOKED", "CREATED"):
                status = "Pending"
            else:
                status = self._normalize_status(status_raw)

            # Synthesize events from available summary fields
            # (Full event history requires Day & Ross account login — not available via public API)
            events: List[dict] = []

            # 1. Shipment created
            created_raw = item.get("createdTime") or item.get("shipDate") or ""
            if created_raw:
                events.append({
                    "timestamp": self._parse_datetime(created_raw) or datetime.now(),
                    "location": origin,
                    "status": "Shipment Created",
                    "description": "Shipment Created",
                })

            # 2. Pickup done (if true and we have a ship date hint)
            if item.get("pickupDone") and created_raw:
                # pickupDone=true but no exact pickup timestamp — note it after creation
                events.append({
                    "timestamp": self._parse_datetime(created_raw) or datetime.now(),
                    "location": origin,
                    "status": "Picked Up",
                    "description": "Picked Up by carrier",
                })

            # 3. Delivered event — takes priority over generic status event
            if delivered_raw and status == "Delivered":
                events.insert(0, {
                    "timestamp": self._parse_datetime(delivered_raw) or datetime.now(),
                    "location": destination,
                    "status": "Delivered",
                    "description": "Delivered",
                })
            elif status_raw and status_raw.lower() not in ("shipment created",):
                # Add current status as an event (not for delivered — handled above)
                events.append({
                    "timestamp": self._parse_datetime(est_raw or created_raw) or datetime.now(),
                    "location": destination,
                    "status": status_raw,
                    "description": status_raw,
                })

            # Sort: most recent first
            events.sort(key=lambda e: e["timestamp"] or datetime.min, reverse=True)

            delivered_date = None
            if status == "Delivered" and delivered_raw:
                dt = self._parse_datetime(delivered_raw)
                delivered_date = dt.date() if dt else None

            # Current location: show destination for delivered, None otherwise
            # (real in-transit location is not available from the public TruckMateAPI)
            current_location = destination if status == "Delivered" else None

            return {
                "status": status,
                "current_location": current_location,
                "estimated_delivery": self._parse_date(est_raw),
                "delivered_date": delivered_date,
                "events": events,
                "error": None,
            }
        except Exception as exc:
            logger.debug("Day & Ross API parse error: %s", exc)
            return None

    def _parse_datetime(self, raw: str) -> Optional[datetime]:
        if not raw:
            return None
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%m/%d/%Y",
        ):
            try:
                dt = datetime.strptime(raw[:26].strip(), fmt)
                return dt.replace(tzinfo=None)  # strip tzinfo for consistency
            except (ValueError, AttributeError):
                continue
        return None

    def _parse_date(self, raw: str) -> Optional[object]:
        if not raw:
            return None
        try:
            from datetime import date
            return date.fromisoformat(raw[:10])
        except (ValueError, AttributeError):
            pass
        dt = self._parse_datetime(raw)
        return dt.date() if dt else None
