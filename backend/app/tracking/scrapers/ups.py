import asyncio
import random
import re
import sys
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from playwright.sync_api import sync_playwright

try:
    from playwright_stealth import stealth_sync
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False

from .base import BaseScraper

logger = logging.getLogger(__name__)

UPS_TRACK_URL = "https://www.ups.com/track?tracknum={tracking_number}&requester=WT/trackdetails"
TIMEOUT_MS = 45_000


class UPSScraper(BaseScraper):
    """
    Scrapes UPS tracking.
    Primary: non-headless real Chrome (Windows) — bypasses UPS bot detection.
    Fallback: headless Playwright with page-text parsing.
    """

    async def scrape(self, tracking_number: str) -> Dict[str, Any]:
        # Try non-headless Chrome first (bypasses Akamai bot detection).
        # On Windows: uses real display. On Linux: uses Xvfb via pyvirtualdisplay.
        try:
            result = await asyncio.to_thread(self._chrome_scrape, tracking_number)
            if result.get("error") is None:
                logger.info("UPS: Chrome scrape succeeded for %s", tracking_number)
                return result
            logger.info("UPS Chrome scrape failed (%s), falling back", result["error"])
        except Exception as exc:
            logger.warning("UPS Chrome scrape exception for %s: %s", tracking_number, exc)

        # Headless fallback with retries
        last_error = None
        for attempt in range(1, 4):
            try:
                result = await asyncio.to_thread(self._sync_scrape, tracking_number)
                if result.get("error") is None:
                    return result
                last_error = result["error"]
                if "unable to complete" in (last_error or "").lower() or "try again" in (last_error or "").lower():
                    if attempt < 3:
                        await asyncio.sleep(15 + random.uniform(5, 10))
                        continue
            except Exception as exc:
                last_error = str(exc)
                logger.warning("UPS attempt %d/3 failed for %s: %s", attempt, tracking_number, last_error)
            if attempt < 3:
                await asyncio.sleep(3 ** attempt + random.uniform(2, 5))
        return self._empty_result(f"UPS scrape failed after 3 attempts: {last_error}")

    # ── Non-headless Chrome (bypasses bot detection) ─────────────────────────

    def _chrome_scrape(self, tracking_number: str) -> Dict[str, Any]:
        # On Linux (Docker/production) start a virtual framebuffer so non-headless Chrome has a display.
        display = None
        if sys.platform != "win32":
            try:
                from pyvirtualdisplay import Display
                display = Display(visible=False, size=(1280, 800))
                display.start()
            except Exception as exc:
                logger.warning("UPS: virtual display unavailable: %s", exc)
                return self._empty_result("Virtual display unavailable — xvfb/pyvirtualdisplay not installed")

        intercepted: List[dict] = []
        try:
            with sync_playwright() as p:
                try:
                    browser = p.chromium.launch(
                        channel="chrome",
                        headless=False,
                        args=[
                            "--no-sandbox",
                            "--disable-blink-features=AutomationControlled",
                        ],
                    )
                except Exception:
                    return self._empty_result("Chrome not installed")

                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1280, "height": 800},
                    locale="en-US",
                    timezone_id="America/Toronto",
                )
                page = context.new_page()

                def handle_response(response):
                    try:
                        url = response.url
                        if (
                            "ups.com" in url
                            and response.status == 200
                            and ("GetStatus" in url or "/track/api/" in url)
                            and "json" in response.headers.get("content-type", "")
                        ):
                            intercepted.append(response.json())
                            logger.debug("UPS Chrome: intercepted %s", url)
                    except Exception:
                        pass

                page.on("response", handle_response)

                try:
                    url = UPS_TRACK_URL.format(tracking_number=tracking_number)
                    page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
                    page.wait_for_timeout(random.randint(8000, 12000))

                    for data in reversed(intercepted):
                        result = self._parse_api_response(data)
                        if result:
                            logger.info("UPS Chrome: parsed from API for %s", tracking_number)
                            return result

                    # Fall back to page text in the same Chrome session
                    body_text = page.inner_text("body") or ""
                    return self._parse_page_text(body_text, tracking_number)

                except Exception as exc:
                    return self._empty_result(f"UPS Chrome error: {exc}")
                finally:
                    browser.close()
        finally:
            if display:
                try:
                    display.stop()
                except Exception:
                    pass

    # ── Headless fallback ─────────────────────────────────────────────────────

    def _sync_scrape(self, tracking_number: str) -> Dict[str, Any]:
        intercepted: List[dict] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": random.randint(1280, 1920), "height": random.randint(800, 1080)},
                locale="en-US",
                timezone_id="America/Toronto",
            )
            page = context.new_page()

            if STEALTH_AVAILABLE:
                stealth_sync(page)

            def handle_response(response):
                try:
                    url = response.url
                    if (
                        "ups.com" in url
                        and response.status == 200
                        and ("GetStatus" in url or "/track/api/" in url)
                        and "json" in response.headers.get("content-type", "")
                    ):
                        intercepted.append(response.json())
                        logger.debug("UPS: intercepted %s", url)
                except Exception:
                    pass

            page.on("response", handle_response)

            try:
                url = UPS_TRACK_URL.format(tracking_number=tracking_number)
                page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
                page.wait_for_timeout(random.randint(7000, 10000))

                for data in reversed(intercepted):
                    result = self._parse_api_response(data)
                    if result:
                        logger.info("UPS: parsed from API for %s", tracking_number)
                        return result

                body_text = page.inner_text("body") or ""
                logger.info("UPS: parsing page text for %s", tracking_number)
                return self._parse_page_text(body_text, tracking_number)

            except Exception as exc:
                return self._empty_result(f"UPS page error: {exc}")
            finally:
                browser.close()

    # ── Parsers ───────────────────────────────────────────────────────────────

    def _parse_api_response(self, data: dict) -> Optional[Dict[str, Any]]:
        """
        Parse UPS GetStatus API response.
        Shape: { "trackDetails": [{ "packageStatus": "Delivered",
                                    "shipToAddress": {"city":..., "state":...},
                                    "shipmentProgressActivities": [...] }] }
        """
        try:
            track_list = data.get("trackDetails") or data.get("TrackDetails") or []
            if not track_list:
                return None
            td = track_list[0]

            if td.get("errorCode") and td.get("errorCode") not in ("", "0", 0):
                return None

            status_raw = (
                td.get("packageStatus")
                or td.get("currentPackageStatus")
                or td.get("packageStatusDescription")
                or ""
            )
            if not status_raw:
                return None

            # Location: use shipToAddress or deliveryAddress from the td
            ship_to = td.get("shipToAddress") or {}
            loc_parts = [
                ship_to.get("city", ""),
                ship_to.get("state", "") or ship_to.get("province", ""),
            ]
            location = ", ".join(p for p in loc_parts if p) or None

            # Events from shipmentProgressActivities
            events: List[dict] = []
            for act in td.get("shipmentProgressActivities", []) or []:
                date_str = act.get("date", "")
                time_str = act.get("time", "")
                dt = self._parse_datetime(f"{date_str} {time_str}".strip())
                desc = (act.get("activityScan") or act.get("description") or "").strip()
                loc = act.get("location") or act.get("activityLocation") or None
                if desc or dt:
                    events.append({
                        "timestamp": dt or datetime.now(),
                        "location": loc,
                        "status": desc[:100],
                        "description": desc,
                    })

            status = self._normalize_status(status_raw)

            # Delivery date: find first "DELIVERED" activity
            delivered_date = None
            if status == "Delivered":
                for ev in events:
                    if "deliver" in (ev.get("description") or "").lower():
                        ts = ev["timestamp"]
                        delivered_date = ts.date() if isinstance(ts, datetime) else None
                        break

            return {
                "status": status,
                "current_location": location,
                "estimated_delivery": None,  # UPS API doesn't expose this in basic response
                "delivered_date": delivered_date,
                "events": events,
                "error": None,
            }
        except Exception as exc:
            logger.debug("UPS API parse error: %s", exc)
            return None

    def _parse_page_text(self, body_text: str, tracking_number: str) -> Dict[str, Any]:
        text_lower = body_text.lower()

        if "unable to complete your tracking request" in text_lower:
            return self._empty_result("UPS temporarily unavailable — rate limited, try again later")

        not_found_phrases = [
            "we've identified a problem with the tracking number",
            "could not locate the shipment",
            "no tracking information available",
            "tracking number cannot be found",
        ]
        if any(p in text_lower for p in not_found_phrases):
            return self._empty_result("Tracking number not found on UPS")

        status = None
        if "delivered" in text_lower:
            status = "Delivered"
        elif "out for delivery" in text_lower:
            status = "Out for Delivery"
        elif "in transit" in text_lower or "on the way" in text_lower:
            status = "In Transit"
        elif "departed" in text_lower or "arrived" in text_lower or "we have your package" in text_lower:
            status = "In Transit"
        elif "exception" in text_lower or "delivery attempt" in text_lower:
            status = "Exception"

        if not status:
            logger.debug("UPS page text preview: %s", body_text[:300])
            return self._empty_result("UPS: could not parse status from page — check logs")

        location = None
        lines = [l.strip() for l in body_text.splitlines() if l.strip()]
        for i, line in enumerate(lines):
            if "delivered to" in line.lower() and i + 1 < len(lines):
                location = lines[i + 1]
                break

        events = self._parse_text_events(lines)

        delivered_date = None
        if status == "Delivered" and events:
            ts = events[0]["timestamp"]
            delivered_date = ts.date() if isinstance(ts, datetime) else None

        return {
            "status": status,
            "current_location": location,
            "estimated_delivery": None,
            "delivered_date": delivered_date,
            "events": events,
            "error": None,
        }

    def _parse_text_events(self, lines: list) -> list:
        events = []
        event_keywords = [
            "delivered", "out for delivery", "on the way", "in transit",
            "departed", "arrived", "we have your package", "label created",
            "picked up", "accepted", "package transferred",
        ]
        date_pattern = re.compile(r'\d{2}/\d{2}/\d{4}')

        for i, line in enumerate(lines):
            if date_pattern.search(line):
                for j in range(max(0, i - 2), min(len(lines), i + 3)):
                    if any(kw in lines[j].lower() for kw in event_keywords):
                        ts = self._parse_datetime(line.strip()) or datetime.now()
                        desc = lines[j].strip()
                        loc = lines[j + 1].strip() if j + 1 < len(lines) and "," in lines[j + 1] else None
                        events.append({
                            "timestamp": ts,
                            "location": loc,
                            "status": desc[:100],
                            "description": desc,
                        })
                        break
        return events

    def _parse_datetime(self, raw: str) -> Optional[datetime]:
        if not raw:
            return None
        # Normalize "9:51 A.M." → "9:51 AM" for strptime %p
        normalized = re.sub(r'([AP])\.M\.', r'\1M', raw.strip(), flags=re.IGNORECASE)
        for fmt in (
            "%m/%d/%Y %I:%M:%S %p",
            "%m/%d/%Y %I:%M %p",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M",
            "%B %d, %Y %H:%M",
            "%Y-%m-%dT%H:%M:%S",
        ):
            try:
                return datetime.strptime(normalized, fmt)
            except (ValueError, AttributeError):
                continue
        return None

    def _parse_date_str(self, raw: str) -> Optional[object]:
        if not raw:
            return None
        for fmt in ("%m/%d/%Y", "%B %d, %Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw.strip(), fmt).date()
            except (ValueError, AttributeError):
                continue
        return None
