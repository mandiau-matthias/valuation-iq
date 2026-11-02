"""Valuation-band and headline consistency helpers.

These helpers guard the report headline contract: valuation bands must be
monotone, meaningful ranges must survive compact display rounding, and the
asking price must not fall below a no-balance-data EV floor realignment.
They live outside ``decimal_helpers`` so core Decimal coercion stays small,
while the older import path can keep re-exporting these names.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional, Tuple


def pin_band_monotone(
    low: Decimal,
    mid: Decimal,
    high: Decimal,
) -> Tuple[Decimal, Decimal, Decimal]:
    """Pin a ``(low, mid, high)`` band so ``low <= mid <= high``.

    ``mid`` is the authoritative central estimate used by the cover headline
    and EV-to-equity bridge. Non-positive bounds are treated as missing and
    pass through unchanged so downstream fallback render paths still work.
    """
    if mid is None or mid <= Decimal("0"):
        return (low, mid, high)
    pinned_low = low
    pinned_high = high
    if low is not None and low > Decimal("0") and low > mid:
        pinned_low = mid
    if high is not None and high > Decimal("0") and high < mid:
        pinned_high = mid
    return (pinned_low, mid, pinned_high)


# Under this half-spread the range renders as the same compact amount on both
# bounds, so templates should suppress the range and show the headline value.
BAND_MEANINGFUL_HALF_SPREAD_THRESHOLD = Decimal("0.02")


def band_is_meaningful(
    low: Optional[Decimal],
    mid: Optional[Decimal],
    high: Optional[Decimal],
    threshold: Decimal = BAND_MEANINGFUL_HALF_SPREAD_THRESHOLD,
) -> bool:
    """True when the band spread is wide enough to survive display rounding."""
    if low is None or mid is None or high is None:
        return False
    if mid <= Decimal("0") or low <= Decimal("0") or high <= Decimal("0"):
        return False
    if high <= low:
        return False
    half_spread = max(high - mid, mid - low) / mid
    return half_spread >= threshold


def reconcile_asking_price_after_phantom_bridge(
    engine_asking: Decimal,
    equity_value_before: Decimal,
    equity_value_after: Decimal,
) -> Tuple[Decimal, bool]:
    """Realign asking price after the no-balance-data EV floor mutation.

    The engine computes asking price from the pre-bridge equity value. When
    an aggregator later raises equity to the EV floor for no-balance-data
    reports, the asking price must preserve the original buffer ratio or at
    least pin to the displayed equity floor.
    """
    if (
        engine_asking <= Decimal("0")
        or equity_value_before <= Decimal("0")
        or equity_value_after <= Decimal("0")
    ):
        return engine_asking, False
    if engine_asking >= equity_value_after:
        return engine_asking, False
    buffer_ratio = engine_asking / equity_value_before
    aligned = equity_value_after * buffer_ratio
    if aligned < equity_value_after:
        aligned = equity_value_after
    return aligned, True


# Shared source labels used by the aggregator and templates.
EV_BAND_SOURCE_PIPELINE = "multiple_pipeline"
EV_BAND_SOURCE_ENGINE_EQUITY = "engine_equity_band"


def select_ev_band(
    pipeline_low: Decimal,
    pipeline_mid: Decimal,
    pipeline_high: Decimal,
    engine_low: Decimal,
    engine_mid: Decimal,
    engine_high: Decimal,
) -> Tuple[Decimal, Decimal, Decimal, str]:
    """Choose between pipeline-derived and engine-equity-derived EV bands.

    Prefer the multiple-pipeline band unless it collapses below the display
    threshold while the engine-equity band remains meaningful, or both bands
    are meaningful and their midpoints already agree.
    """
    pipeline_meaningful = band_is_meaningful(pipeline_low, pipeline_mid, pipeline_high)
    engine_meaningful = band_is_meaningful(engine_low, engine_mid, engine_high)
    if not pipeline_meaningful and engine_meaningful:
        return engine_low, engine_mid, engine_high, EV_BAND_SOURCE_ENGINE_EQUITY
    if pipeline_meaningful and engine_meaningful and pipeline_mid > Decimal("0"):
        mid_diff = abs(pipeline_mid - engine_mid) / pipeline_mid
        if mid_diff <= Decimal("0.01"):
            return engine_low, engine_mid, engine_high, EV_BAND_SOURCE_ENGINE_EQUITY
    return pipeline_low, pipeline_mid, pipeline_high, EV_BAND_SOURCE_PIPELINE
