from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """
    Abstract base class for all carrier scrapers.

    Every scraper must implement `scrape()` and return a normalized dict.
    The returned dict always has the same shape so the rest of the app
    doesn't need to know which carrier it is talking to.
    """

    @abstractmethod
    async def scrape(self, tracking_number: str) -> Dict[str, Any]:
        """
        Scrape tracking data from the carrier website.

        Returns:
        {
            'status':            str  — 'In Transit' | 'Delivered' | 'Out for Delivery'
                                        | 'Exception' | 'Pending' | 'Unknown'
            'current_location':  str | None
            'estimated_delivery': date | None
            'delivered_date':    date | None
            'events': [
                {
                    'timestamp':   datetime,
                    'location':    str | None,
                    'status':      str | None,
                    'description': str | None,
                }
            ],
            'error': str | None   — populated when scraping failed
        }
        """
        ...

    def _empty_result(self, error: Optional[str] = None) -> Dict[str, Any]:
        """Return a blank result dict (used on failure)."""
        return {
            "status": "Unknown",
            "current_location": None,
            "estimated_delivery": None,
            "delivered_date": None,
            "events": [],
            "error": error,
        }

    def _normalize_status(self, raw: str) -> str:
        """Map raw carrier status strings to our internal status vocabulary."""
        raw_lower = raw.lower()
        if any(w in raw_lower for w in ["delivered", "delivery complete"]):
            return "Delivered"
        if any(w in raw_lower for w in ["out for delivery", "on vehicle for delivery"]):
            return "Out for Delivery"
        if any(w in raw_lower for w in ["exception", "alert", "problem", "delay", "held"]):
            return "Exception"
        if any(w in raw_lower for w in ["in transit", "transit", "departed", "arrived", "picked up", "accepted"]):
            return "In Transit"
        return raw.title() if raw else "Unknown"
