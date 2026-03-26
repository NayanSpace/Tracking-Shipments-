import logging
import re

logger = logging.getLogger(__name__)


def detect_carrier(tracking_number: str) -> str | None:
    """
    Attempt to auto-detect carrier from tracking number format.
    Returns carrier string or None if undetectable.
    """
    tn = tracking_number.strip().upper()

    # UPS: starts with 1Z, 18 characters
    if re.match(r"^1Z[A-Z0-9]{16}$", tn):
        return "UPS"

    # FedEx: 12, 15, or 20 digits
    if re.match(r"^\d{12}$", tn) or re.match(r"^\d{15}$", tn) or re.match(r"^\d{20}$", tn):
        return "FEDEX"

    return None
