import asyncio
import json
import random
import logging
import sys
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

FEDEX_TRACK_URL = "https://www.fedex.com/fedextrack/?tracknumbers={tracking_number}"
TIMEOUT_MS = 45_000


class FedExScraper(BaseScraper):
    """
    Scrapes FedEx tracking.
    Primary: POST to trackingCal/track (server-side, no Akamai JS challenge).
    Fallback: Playwright with network interception + text-mine.
    """

    async def scrape(self, tracking_number: str) -> Dict[str, Any]:
        # Try fast HTTP API first
        try:
            result = await asyncio.to_thread(self._http_scrape, tracking_number)
            if result.get("error") is None:
                logger.info("FedEx: HTTP API succeeded for %s", tracking_number)
                return result
            logger.info("FedEx HTTP API failed (%s), falling back to Playwright", result["error"])
        except Exception as exc:
            logger.warning("FedEx HTTP API exception for %s: %s", tracking_number, exc)

        # Playwright fallback with retries
        last_error = None
        for attempt in range(1, 4):
            try:
                result = await asyncio.to_thread(self._sync_scrape, tracking_number)
                if result.get("error") is None:
                    return result
                last_error = result["error"]
            except Exception as exc:
                last_error = str(exc)
                logger.warning("FedEx Playwright attempt %d/3 failed for %s: %s", attempt, tracking_number, last_error)
            if attempt < 3:
                await asyncio.sleep(15 + random.uniform(5, 10))
        return self._empty_result(f"FedEx scrape failed after 3 attempts: {last_error}")

    # ── Non-headless Chrome approach (bypasses Akamai JS challenge) ───────────

    def _http_scrape(self, tracking_number: str) -> Dict[str, Any]:
        """
        FedEx uses Akamai which blocks headless browsers. Real (non-headless)
        Chrome passes the Akamai challenge and lets the FedEx SPA call the
        actual tracking API. We intercept that API call.
        On Windows: uses real display. On Linux: uses Xvfb via pyvirtualdisplay.
        """
        display = None
        if sys.platform != "win32":
            try:
                from pyvirtualdisplay import Display
                display = Display(visible=False, size=(1280, 800))
                display.start()
            except Exception as exc:
                logger.warning("FedEx: virtual display unavailable: %s", exc)
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
                    return self._empty_result("Chrome not installed, skipping non-headless")

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
                        if response.status != 200:
                            return
                        url = response.url
                        ct = response.headers.get("content-type", "")
                        if "json" not in ct:
                            return
                        if "track/v2/shipments" in url or "track/v1/trackingdocuments" in url or "trackingresults" in url:
                            body = response.json()
                            intercepted.append(body)
                            logger.debug("FedEx non-headless: intercepted %s", url)
                    except Exception:
                        pass

                page.on("response", handle_response)

                try:
                    url = FEDEX_TRACK_URL.format(tracking_number=tracking_number)
                    page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
                    page.wait_for_timeout(random.randint(8000, 12000))

                    for data in reversed(intercepted):
                        result = self._parse_api_response(data)
                        if result:
                            logger.info("FedEx non-headless: parsed for %s", tracking_number)
                            return result

                    return self._empty_result("FedEx non-headless: no API data intercepted")
                except Exception as exc:
                    return self._empty_result(f"FedEx non-headless error: {exc}")
                finally:
                    browser.close()
        finally:
            if display:
                try:
                    display.stop()
                except Exception:
                    pass

    # ── Playwright headless fallback ─────────────────────────────────────────

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
                viewport={"width": random.randint(1366, 1920), "height": random.randint(768, 1080)},
                locale="en-US",
                timezone_id="America/Toronto",
            )
            page = context.new_page()

            if STEALTH_AVAILABLE:
                stealth_sync(page)

            def handle_response(response):
                try:
                    if response.status != 200:
                        return
                    url = response.url
                    ct = response.headers.get("content-type", "")
                    if "json" not in ct:
                        return
                    if any(kw in url for kw in [
                        "trackingdocuments", "trackingresults", "trackcal",
                        "track/v1", "track/v2", "fedex.com/api/",
                    ]):
                        body = response.json()
                        intercepted.append(body)
                        logger.debug("FedEx: intercepted API from %s", url)
                except Exception:
                    pass

            page.on("response", handle_response)

            try:
                url = FEDEX_TRACK_URL.format(tracking_number=tracking_number)
                page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
                page.wait_for_timeout(random.randint(5000, 9000))
                page.evaluate("window.scrollBy(0, 300)")
                page.wait_for_timeout(random.randint(2000, 4000))

                page_text = (page.inner_text("body") or "").lower()

                for data in reversed(intercepted):
                    result = self._parse_api_response(data)
                    if result:
                        logger.info("FedEx: parsed from API for %s", tracking_number)
                        return result

                logger.info("FedEx: falling back to text-mine for %s", tracking_number)
                return self._text_mine(page_text)

            except Exception as exc:
                return self._empty_result(f"FedEx page error: {exc}")
            finally:
                browser.close()

    def _parse_api_response(self, data: dict) -> Optional[Dict[str, Any]]:
        """
        Handles both FedEx API response shapes:
        - v2 (track/v2/shipments):  output.packages[0]  — keyStatus, subStatus, scanEventList, etc.
        - v1 (older endpoints):     output.completeTrackResults[0].trackResults[0] — latestStatusDetail, scanEvents
        """
        try:
            output = data.get("output", data)

            # ── v2 format: output.packages ────────────────────────────────────
            packages = output.get("packages", [])
            if packages:
                return self._parse_v2_package(packages[0])

            # ── v1 format: output.completeTrackResults ────────────────────────
            complete_results = output.get("completeTrackResults", [])
            if not complete_results:
                return None
            track_results = complete_results[0].get("trackResults", [])
            if not track_results:
                return None

            pkg = track_results[0]
            latest = pkg.get("latestStatusDetail", {})
            status_desc = (
                latest.get("description", "")
                or latest.get("statusByLocale", "")
                or latest.get("status", "")
            )
            location = self._format_location(latest.get("scanLocation", {}))

            est_raw = (
                pkg.get("estimatedDeliveryTimeWindow", {}).get("window", {}).get("ends", "")
                or pkg.get("estimatedDeliveryTimeWindow", {}).get("ends", "")
            )
            delivered_raw = pkg.get("actualDeliveryTime", "") or ""

            events = []
            for scan in pkg.get("scanEvents", []):
                ts_raw = scan.get("date", "") or scan.get("eventTime", "") or scan.get("dateLocal", "")
                ts = self._parse_iso_datetime(ts_raw)
                desc = scan.get("eventDescription", "") or scan.get("description", "")
                events.append({
                    "timestamp": ts or datetime.now(),
                    "location": self._format_location(scan.get("scanLocation", {})),
                    "status": desc[:100],
                    "description": desc,
                })

            if not status_desc and not events:
                return None

            status = self._normalize_status(status_desc) if status_desc else (
                "Delivered" if any("deliver" in (e["description"] or "").lower() for e in events)
                else "In Transit" if events else "Unknown"
            )
            return {
                "status": status,
                "current_location": location,
                "estimated_delivery": self._parse_iso_date(est_raw),
                "delivered_date": self._parse_iso_date(delivered_raw),
                "events": events,
                "error": None,
            }
        except Exception as exc:
            logger.debug("FedEx API parse error: %s", exc)
            return None

    def _parse_v2_package(self, pkg: dict) -> Optional[Dict[str, Any]]:
        """
        Parse a package object from the FedEx track/v2/shipments response.
        Key fields: keyStatus, keyStatusCD, subStatus, estDeliveryDt, actDeliveryDt,
                    scanEventList, statusLocationAddress, delivered (bool), etc.
        """
        try:
            if pkg.get("notFound") or pkg.get("invalid"):
                return self._empty_result("Tracking number not found on FedEx")

            status_raw = pkg.get("keyStatus", "") or pkg.get("lastScanStatus", "") or ""
            if not status_raw:
                return None

            # Boolean flags take priority for status mapping
            if pkg.get("delivered"):
                status = "Delivered"
            elif pkg.get("hal"):  # Hold at location
                status = "Out for Delivery"
            elif pkg.get("delException") or pkg.get("shipmentException") or pkg.get("clearanceDelay"):
                status = "Exception"
            elif pkg.get("inTransit") or pkg.get("inProgress") or pkg.get("pickup") or pkg.get("inFedExPossession"):
                status = "In Transit"
            elif pkg.get("prePickup"):
                status = "Pending"
            else:
                # Fall back to normalizing the status text
                status = self._normalize_status(status_raw)
                # Extra mappings for FedEx v2 status strings
                sl = status_raw.lower()
                if "delivery updated" in sl or "estimated delivery" in sl or "clearance" in sl:
                    status = "In Transit"
                elif "out for delivery" in sl:
                    status = "Out for Delivery"

            # Current location from statusLocationAddress or subStatus
            loc_addr = pkg.get("statusLocationAddress") or {}
            location = self._format_location(loc_addr) or pkg.get("subStatus") or None

            # Dates
            est_raw = pkg.get("estDeliveryDt", "") or pkg.get("displayEstDeliveryDt", "") or ""
            delivered_raw = pkg.get("actDeliveryDt", "") or ""

            # Scan events
            events: List[dict] = []
            for scan in pkg.get("scanEventList", []) or []:
                date_str = scan.get("date", "")
                time_str = scan.get("time", "")
                combined = f"{date_str}T{time_str}" if date_str and time_str else date_str
                ts = self._parse_iso_datetime(combined)
                desc = scan.get("scanDetails", "") or scan.get("status", "")
                loc = scan.get("scanLocation", "")
                events.append({
                    "timestamp": ts or datetime.now(),
                    "location": loc or None,
                    "status": (scan.get("status", "") or desc)[:100],
                    "description": desc,
                })

            delivered_date = None
            if status == "Delivered" and delivered_raw:
                dt = self._parse_iso_datetime(delivered_raw[:19])
                delivered_date = dt.date() if dt else None

            return {
                "status": status,
                "current_location": location,
                "estimated_delivery": self._parse_iso_date(est_raw),
                "delivered_date": delivered_date,
                "events": events,
                "error": None,
            }
        except Exception as exc:
            logger.debug("FedEx v2 parse error: %s", exc)
            return None

    def _text_mine(self, page_text: str) -> Dict[str, Any]:
        # Akamai bot-block response (FedEx uses curly apostrophe \u2019 in "can't")
        if "find that tracking number" in page_text or "can\u2019t find" in page_text or "can't find" in page_text:
            return self._empty_result(
                "FedEx bot detection blocked tracking — FedEx uses Akamai security "
                "which blocks automated requests. Please check fedex.com directly."
            )
        if "delivered" in page_text:
            status = "Delivered"
        elif "out for delivery" in page_text:
            status = "Out for Delivery"
        elif "in transit" in page_text or "departed" in page_text or "picked up" in page_text:
            status = "In Transit"
        elif "not found" in page_text or "unable to track" in page_text:
            return self._empty_result("Tracking number not found on FedEx")
        else:
            return self._empty_result("FedEx: could not parse tracking data from page")
        return {
            "status": status,
            "current_location": None,
            "estimated_delivery": None,
            "delivered_date": None,
            "events": [],
            "error": None,
        }

    def _format_location(self, loc: dict) -> Optional[str]:
        if not loc:
            return None
        parts = [loc.get("city", ""), loc.get("stateOrProvinceCode", ""), loc.get("countryCode", "")]
        return ", ".join(p for p in parts if p) or None

    def _parse_iso_date(self, raw: str) -> Optional[object]:
        if not raw:
            return None
        try:
            return datetime.strptime(raw[:10], "%Y-%m-%d").date()
        except (ValueError, AttributeError):
            pass
        # Try MM/DD/YYYY
        try:
            return datetime.strptime(raw.strip(), "%m/%d/%Y").date()
        except (ValueError, AttributeError):
            return None

    def _parse_iso_datetime(self, raw: str) -> Optional[datetime]:
        if not raw:
            return None
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M"):
            try:
                return datetime.strptime(raw[:19], fmt)
            except (ValueError, AttributeError):
                continue
        return None

    def _parse_datetime(self, raw: str) -> Optional[datetime]:
        if not raw:
            return None
        for fmt in (
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%m/%d/%Y %I:%M %p",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y",
            "%Y-%m-%d",
        ):
            try:
                return datetime.strptime(raw.strip(), fmt)
            except (ValueError, AttributeError):
                continue
        return None
