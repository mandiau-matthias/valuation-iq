"""Compatibility hooks for removed report-to-calculation mutations.

A report is a projection of a saved result. Neither missing balance data nor
presentation flags authorize a new equity value, method range or asking price.
The two legacy entry points remain import-compatible and deliberately read-only;
active report generation no longer calls them. Corrected prices require a new run.
"""

from collections.abc import Mapping
from decimal import Decimal


def sync_final_report_presentation_fields(response: object, context: Mapping[str, object]) -> None:
    """Deprecated: preserve saved financial fields and report context unchanged."""


def sync_api_response_headline_with_report(
    *,
    response: object,
    phantom_bridge_suppressed: bool,
    enterprise_value_low: Decimal,
    enterprise_value_mid: Decimal,
    enterprise_value_high: Decimal,
    ev_band_is_meaningful: bool,
    aligned_recommended_asking_price: Decimal,
    asking_price_realigned: bool,
    logger: object | None = None,
) -> bool:
    """Deprecated: report alignment cannot mutate a calculation; always False."""
    return False
