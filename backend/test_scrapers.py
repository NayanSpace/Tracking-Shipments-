"""
Run from the backend directory:
    python test_scrapers.py

Tests all 4 scrapers and saves debug HTML + screenshots.
"""
import asyncio
import sys
import os
import logging

# Fix Windows event loop issue
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Show INFO logs
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Make sure 'app' package is importable
sys.path.insert(0, os.path.dirname(__file__))

from app.tracking.scrapers.ups import UPSScraper
from app.tracking.scrapers.fedex import FedExScraper
from app.tracking.scrapers.dayross import DayRossScraper
from app.tracking.scrapers.polaris import PolarisScraper

# Override via environment variables, e.g.:
#   set TEST_UPS=1Z...  TEST_FEDEX=...  TEST_DAYROSS=...  TEST_POLARIS=...
TESTS = [
    (UPSScraper(),      os.getenv("TEST_UPS",      "1ZXXXXXXXXXXXXXXXXXX"), "UPS",       "Delivered"),
    (FedExScraper(),    os.getenv("TEST_FEDEX",    "000000000000"),         "FedEx",     "In Transit"),
    (DayRossScraper(),  os.getenv("TEST_DAYROSS",  "XXXXXXXXX"),            "Day & Ross","Delivered"),
    (PolarisScraper(),  os.getenv("TEST_POLARIS",  "PXXXXXXX"),             "Polaris",   "In Transit"),
]


async def run_tests():
    print("\n" + "="*70)
    print("SCRAPER TESTS")
    print("="*70)

    passed = 0
    failed = 0

    for scraper, tracking_num, carrier, expected in TESTS:
        print(f"\n[{carrier}] {tracking_num}  (expected: {expected})")
        print("-" * 50)
        try:
            result = await scraper.scrape(tracking_num)

            print(f"  status          : {result['status']}")
            print(f"  current_location: {result['current_location']}")
            print(f"  est_delivery    : {result['estimated_delivery']}")
            print(f"  delivered_date  : {result['delivered_date']}")
            print(f"  error           : {result['error']}")
            print(f"  events          : {len(result['events'])}")
            for ev in result["events"][:3]:
                print(f"    - [{ev.get('timestamp')}] {ev.get('description', '')[:80]}")

            if result["error"]:
                print(f"  RESULT: FAIL (error returned)")
                failed += 1
            elif result["status"].lower() == expected.lower():
                print(f"  RESULT: PASS")
                passed += 1
            else:
                print(f"  RESULT: WRONG STATUS (expected '{expected}', got '{result['status']}')")
                failed += 1

        except Exception as exc:
            print(f"  EXCEPTION: {exc}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "="*70)
    print(f"SUMMARY: {passed} passed, {failed} failed out of {len(TESTS)} tests")
    print("="*70)


async def debug_single(carrier_name: str, tracking_number: str):
    """
    Debug a single carrier — saves page HTML and screenshot to debug/ folder.
    Example: await debug_single("ups", "1Z7X39176773570612")
    """
    from playwright.sync_api import sync_playwright
    import json

    os.makedirs("debug", exist_ok=True)
    safe_name = carrier_name.lower().replace(" ", "_").replace("&", "and")
    html_path = f"debug/{safe_name}_{tracking_number}.html"
    screenshot_path = f"debug/{safe_name}_{tracking_number}.png"
    text_path = f"debug/{safe_name}_{tracking_number}.txt"
    network_path = f"debug/{safe_name}_{tracking_number}_network.json"

    carrier_urls = {
        "ups": f"https://www.ups.com/track?tracknum={tracking_number}&requester=WT/trackdetails",
        "fedex": f"https://www.fedex.com/fedextrack/?tracknumbers={tracking_number}",
        "dayross": f"https://www.dayross.com/en/tracking?proNumbers={tracking_number}",
        "polaris": f"https://www.polaristransport.com/track/?proNumber={tracking_number}",
    }

    url = carrier_urls.get(safe_name)
    if not url:
        print(f"Unknown carrier: {carrier_name}")
        return

    print(f"\nDebug: opening {url}")
    network_calls = []

    def run():
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,  # visible so you can see what's happening
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="en-US",
                timezone_id="America/Toronto",
            )
            page = context.new_page()

            def on_response(resp):
                try:
                    ct = resp.headers.get("content-type", "")
                    if "json" in ct and resp.status == 200:
                        try:
                            body = resp.json()
                            network_calls.append({"url": resp.url, "body": body})
                            print(f"  [JSON] {resp.url[:80]}")
                        except Exception:
                            pass
                except Exception:
                    pass

            page.on("response", on_response)

            page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(8000)  # wait for SPA to load

            html = page.content()
            text = page.inner_text("body") or ""
            page.screenshot(path=screenshot_path, full_page=True)

            browser.close()
            return html, text

    import threading
    result_holder = {}
    def thread_fn():
        result_holder["html"], result_holder["text"] = run()

    t = threading.Thread(target=thread_fn)
    t.start()
    t.join(timeout=60)

    if "html" in result_holder:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(result_holder["html"])
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(result_holder["text"])
        with open(network_path, "w", encoding="utf-8") as f:
            json.dump(network_calls, f, indent=2, default=str)

        print(f"\nSaved:")
        print(f"  HTML       : {html_path}")
        print(f"  Screenshot : {screenshot_path}")
        print(f"  Page text  : {text_path}")
        print(f"  Network    : {network_path}")
        print(f"\nPage text preview (first 500 chars):")
        print(result_holder["text"][:500])
        print(f"\nJSON API calls captured: {len(network_calls)}")
        for nc in network_calls[:5]:
            print(f"  {nc['url'][:80]}")
    else:
        print("Thread timed out or failed")


if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 2 and sys.argv[1] == "debug":
        # Usage: python test_scrapers.py debug ups 1Z7X39176773570612
        carrier = sys.argv[2] if len(sys.argv) > 2 else "ups"
        number = sys.argv[3] if len(sys.argv) > 3 else "1Z7X39176773570612"
        asyncio.run(debug_single(carrier, number))
    else:
        asyncio.run(run_tests())
