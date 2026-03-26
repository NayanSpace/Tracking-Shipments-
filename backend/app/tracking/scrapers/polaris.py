import asyncio
import random
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from playwright.sync_api import sync_playwright

from .base import BaseScraper

logger = logging.getLogger(__name__)

# Polaris tracking page — form posts to trace-polaris.php with ?pro=<number>
POLARIS_TRACK_URL = "https://www.polaristransport.com/en/trace-polaris.php?pro={tracking_number}"
# Their REST API (intercepted from network)
POLARIS_API_PATTERN = "api.polaristransport.com"
TIMEOUT_MS = 35_000


class PolarisScraper(BaseScraper):
    """
    Scrapes Polaris Transportation tracking.
    Strategy: navigate to trace-polaris.php?pro=<number>, intercept the
    TraceAPI JSON response from api.polaristransport.com:1984.
    Parses TRACE_API_Response for status, location, and delivery dates.
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
                logger.warning("Polaris attempt %d/3 failed for %s: %s", attempt, tracking_number, last_error)
            if attempt < 3:
                await asyncio.sleep(2 ** attempt + random.uniform(1, 3))
        return self._empty_result(f"Polaris scrape failed after 3 attempts: {last_error}")

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
                    if POLARIS_API_PATTERN in response.url:
                        ct = response.headers.get("content-type", "")
                        if "json" in ct or "javascript" in ct or len(ct) == 0:
                            try:
                                body = response.json()
                            except Exception:
                                body = response.text()
                            intercepted.append({"url": response.url, "body": body})
                            logger.debug("Polaris: intercepted API from %s", response.url)
                except Exception:
                    pass

            page.on("response", handle_response)

            try:
                url = POLARIS_TRACK_URL.format(tracking_number=tracking_number)
                logger.info("Polaris: navigating to %s", url)
                page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
                page.wait_for_timeout(random.randint(5000, 8000))

                # Try the API response first
                for item in reversed(intercepted):
                    result = self._parse_api_response(item.get("body"))
                    if result:
                        logger.info("Polaris: parsed from TraceAPI for %s", tracking_number)
                        return result

                # Fall back to page text
                page_text = (page.inner_text("body") or "")
                logger.debug("Polaris page text (first 300): %s", page_text[:300])

                if any(w in page_text.lower() for w in ["not found", "no results", "invalid pro"]):
                    return self._empty_result("Tracking number not found on Polaris")

                result = self._parse_page_text(page_text)
                if result:
                    logger.info("Polaris: parsed from page text for %s", tracking_number)
                    return result

                return self._empty_result("Polaris: could not extract tracking data")

            except Exception as exc:
                return self._empty_result(f"Polaris page error: {exc}")
            finally:
                browser.close()

    def _parse_api_response(self, data) -> Optional[Dict[str, Any]]:
        """
        Parse Polaris TraceAPI response.
        Shape: { "TRACE_API_Response": { "Current_Status": "IN TRANSIT/DR", ... } }
        """
        try:
            if isinstance(data, str):
                import json
                data = json.loads(data)
            if not isinstance(data, dict):
                return None

            trace = data.get("TRACE_API_Response")
            if not trace or not isinstance(trace, dict):
                return None

            # Check for API errors
            if trace.get("Error", "N") != "N":
                return None

            status_raw = trace.get("Current_Status", "")
            if not status_raw:
                return None

            location = trace.get("Current_Location") or None
            origin = trace.get("Origin") or None
            destination = trace.get("Destination") or None

            # Parse dates
            pickup_raw = trace.get("Actual_Pickup") or ""
            delivery_raw = trace.get("Actual_Delivery") or ""
            est_raw = trace.get("Deliver_by") or trace.get("Deliver_by_end") or ""

            # Build events
            events: List[dict] = []
            if pickup_raw:
                events.append({
                    "timestamp": self._parse_datetime(pickup_raw) or datetime.now(),
                    "location": origin or location,
                    "status": "Picked Up",
                    "description": "Shipment picked up",
                })
            if delivery_raw:
                events.insert(0, {
                    "timestamp": self._parse_datetime(delivery_raw) or datetime.now(),
                    "location": destination or location,
                    "status": "Delivered",
                    "description": "Delivered",
                })

            # Normalize status
            status_upper = status_raw.upper()
            if "DELIVERED" in status_upper or "COMPLETE" in status_upper:
                status = "Delivered"
            elif "OUT FOR DELIVERY" in status_upper or "OUT_FOR_DELIVERY" in status_upper:
                status = "Out for Delivery"
            elif "IN TRANSIT" in status_upper or "INTRANSIT" in status_upper or "/DR" in status_upper or "IN TRNS" in status_upper or "INTRANS" in status_upper:
                status = "In Transit"
            elif "PICKED UP" in status_upper or "PICKUP" in status_upper:
                status = "In Transit"
            elif "EXCEPTION" in status_upper or "PROBLEM" in status_upper:
                status = "Exception"
            else:
                status = self._normalize_status(status_raw)

            delivered_date = None
            if status == "Delivered" and delivery_raw:
                dt = self._parse_datetime(delivery_raw)
                delivered_date = dt.date() if dt else None

            return {
                "status": status,
                "current_location": location,
                "estimated_delivery": self._parse_date(est_raw),
                "delivered_date": delivered_date,
                "events": events,
                "error": None,
            }
        except Exception as exc:
            logger.debug("Polaris API parse error: %s", exc)
            return None

    def _parse_page_text(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Fallback: parse the tracking info from the rendered page text.
        The Polaris trace page renders data like:
          STATUS    IN TRANSIT
          LAST RECORDED LOCATION    RICHMOND HILL, ON
          ESTIMATED DELIVERY    MARCH 31 2026, 8:00AM – 1:00PM
        """
        text_lower = text.lower()

        status = None
        if "delivered" in text_lower:
            status = "Delivered"
        elif "out for delivery" in text_lower:
            status = "Out for Delivery"
        elif "in transit" in text_lower:
            status = "In Transit"
        elif "picked up" in text_lower:
            status = "In Transit"

        if not status:
            return None

        # Extract location
        location = None
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        for i, line in enumerate(lines):
            if "last recorded location" in line.lower() and i + 1 < len(lines):
                location = lines[i + 1]
                break

        # Extract estimated delivery
        est_delivery = None
        for i, line in enumerate(lines):
            if "estimated delivery" in line.lower() and i + 1 < len(lines):
                est_str = lines[i + 1]
                est_delivery = self._parse_date_from_text(est_str)
                break

        events = []
        # Look for "PICKED UP" section
        for i, line in enumerate(lines):
            if "picked up:" in line.lower() or "picked up" in line.lower():
                if i + 1 < len(lines):
                    ts = self._parse_datetime(lines[i + 1]) if i + 1 < len(lines) else None
                    loc = lines[i + 2] if i + 2 < len(lines) else None
                    events.append({
                        "timestamp": ts or datetime.now(),
                        "location": loc,
                        "status": "Picked Up",
                        "description": "Shipment picked up",
                    })
                break

        return {
            "status": status,
            "current_location": location,
            "estimated_delivery": est_delivery,
            "delivered_date": None,
            "events": events,
            "error": None,
        }

    def _parse_date_from_text(self, raw: str) -> Optional[object]:
        """Parse dates like 'MARCH 31 2026, 8:00AM – 1:00PM'"""
        if not raw:
            return None
        # Extract just the date part
        import re
        m = re.search(r'([A-Za-z]+ \d{1,2} \d{4})', raw)
        if m:
            try:
                return datetime.strptime(m.group(1), "%B %d %Y").date()
            except ValueError:
                pass
        return None

    def _parse_datetime(self, raw: str) -> Optional[datetime]:
        if not raw:
            return None
        # Normalize timezone offset (e.g. "-04:00" -> "-0400") for strptime
        import re
        normalized = re.sub(r'([+-])(\d{2}):(\d{2})$', r'\1\2\3', raw.strip())
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ):
            try:
                dt = datetime.strptime(normalized, fmt)
                return dt.replace(tzinfo=None)
            except (ValueError, AttributeError):
                continue
        return None

    def _parse_date(self, raw: str) -> Optional[object]:
        if not raw:
            return None
        # Fast path: extract date from ISO string directly
        try:
            from datetime import date
            return date.fromisoformat(raw[:10])
        except (ValueError, AttributeError):
            pass
        dt = self._parse_datetime(raw)
        return dt.date() if dt else None
