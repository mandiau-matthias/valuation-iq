"""DCF forecast working-capital compatibility helpers."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from src.utils.decimal_helpers import to_decimal


def _close_decimal(a: Decimal, b: Decimal) -> bool:
    tolerance = max(Decimal("1"), b.copy_abs() * Decimal("0.000001"))
    return (a - b).copy_abs() <= tolerance


def repair_legacy_full_revenue_nwc_change(
    *,
    supplied_nwc_change: object,
    revenue: object,
    previous_revenue: object,
    nwc_ratio: object,
) -> Optional[Decimal]:
    """Return corrected ΔNWC when a forecast row has the old auto-fill pattern.

    Venus briefly persisted DCF forecast rows where ``dcf_nwc_pct`` was applied to
    full forecast revenue. The intended model is an NWC ratio applied to the
    year-over-year revenue movement. Only rows matching the old formula are
    repaired; arbitrary row-level advisor overrides are preserved.
    """

    if supplied_nwc_change is None:
        return None

    revenue_decimal = to_decimal(revenue or 0)
    previous_revenue_decimal = to_decimal(previous_revenue or 0)
    nwc_ratio_decimal = to_decimal(nwc_ratio or 0)
    if revenue_decimal <= 0 or previous_revenue_decimal <= 0 or nwc_ratio_decimal == 0:
        return None

    supplied_decimal = to_decimal(supplied_nwc_change)
    legacy_full_revenue = revenue_decimal * nwc_ratio_decimal
    corrected_growth_based = (revenue_decimal - previous_revenue_decimal) * nwc_ratio_decimal

    if _close_decimal(supplied_decimal, legacy_full_revenue) and not _close_decimal(
        supplied_decimal, corrected_growth_based
    ):
        return corrected_growth_based
    return None
