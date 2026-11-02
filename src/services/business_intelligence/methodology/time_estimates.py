"""
Shared valuation-time estimates for business-intelligence methodology selection.
"""

from decimal import Decimal

BASE_TIME_ESTIMATES = {
    "multiples": "1-2 hours",
    "asset_based": "1-2 hours",
    "dcf": "2-4 hours",
    "arr_multiples": "2-3 hours",
    "hybrid": "3-5 hours",
}
DEFAULT_TIME_ESTIMATE = "2-3 hours"


def methodology_time_estimate(methodology: object, revenue: Decimal | None) -> str:
    """
    Return the valuation time estimate for a methodology and company size.

    Business-intelligence modules currently define parallel methodology enums;
    keying on ``.value`` keeps the time policy shared without coupling those
    enum classes together.
    """
    methodology_key = getattr(methodology, "value", methodology)
    base_time = BASE_TIME_ESTIMATES.get(str(methodology_key), DEFAULT_TIME_ESTIMATE)

    if revenue and revenue > 5_000_000:
        if "1-2" in base_time:
            return base_time.replace("1-2", "2-3")
        if "2-3" in base_time:
            return base_time.replace("2-3", "3-4")
        if "2-4" in base_time:
            return base_time.replace("2-4", "3-5")

    return base_time
