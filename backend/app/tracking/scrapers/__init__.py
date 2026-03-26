from typing import Dict
from .base import BaseScraper
from .ups import UPSScraper
from .fedex import FedExScraper
from .dayross import DayRossScraper
from .polaris import PolarisScraper

_scrapers: Dict[str, BaseScraper] = {
    "UPS": UPSScraper(),
    "FEDEX": FedExScraper(),
    "DAYROSS": DayRossScraper(),
    "POLARIS": PolarisScraper(),
}


def get_scraper(carrier: str) -> BaseScraper:
    """Return the scraper instance for the given carrier name."""
    carrier = carrier.upper()
    if carrier not in _scrapers:
        raise ValueError(f"Unknown carrier: {carrier}. Must be one of {list(_scrapers.keys())}")
    return _scrapers[carrier]
