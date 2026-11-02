"""Rounding and ordering invariants for Step 11 synthesis."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional, Protocol

from src.config import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ValuationRounder(Protocol):
    def round_valuation(self, value: Decimal) -> Decimal: ...


class PercentageValidator(Protocol):
    def safe_percentage_calculation(
        self,
        numerator: Decimal,
        denominator: Decimal,
        default: Decimal,
    ) -> Decimal: ...


class IncrementableMetric(Protocol):
    def inc(self) -> None: ...


class OrderingClampMetric(Protocol):
    def labels(self, *, bound: str) -> IncrementableMetric: ...


def granularity_for(value: Decimal) -> Decimal:
    """Mirror RangeCalculator.round_valuation granularity tiers."""
    if value >= Decimal("10000000"):
        return Decimal("100000")
    if value >= Decimal("1000000"):
        return Decimal("10000")
    if value >= Decimal("100000"):
        return Decimal("1000")
    return Decimal("100")


def apply_rounding(
    *,
    range_calculator: ValuationRounder,
    validator: PercentageValidator,
    valuation_low: Decimal,
    valuation_mid: Decimal,
    valuation_high: Decimal,
    equity_value_mid: Optional[Decimal],
    ordering_clamps_total: OrderingClampMetric,
) -> tuple[Decimal, Decimal, Decimal, dict[str, object]]:
    """
    Apply final Step 11 rounding while preserving ``low <= mid <= high``.

    The central estimate stays at full precision; low/high are rounded to
    user-facing granularity and clamped back into order if rounding crosses the
    exact midpoint.
    """
    for name, value in (
        ("valuation_low", valuation_low),
        ("valuation_mid", valuation_mid),
        ("valuation_high", valuation_high),
    ):
        if value is None:
            raise ValueError(
                f"apply_rounding received {name}=None - Step 11 must always pass numeric Decimals"
            )
        try:
            if isinstance(value, Decimal) and value.is_nan():
                raise ValueError(f"apply_rounding received {name}=NaN - degenerate input rejected")
            if isinstance(value, Decimal) and value.is_infinite():
                infinity_label = "Infinity" if value > 0 else "-Infinity"
                raise ValueError(
                    f"apply_rounding received {name}={infinity_label} - degenerate input rejected"
                )
        except (AttributeError, TypeError):
            pass

    if valuation_mid <= 0:
        raise ValueError(
            f"apply_rounding received non-positive valuation_mid={valuation_mid} - "
            f"Step 11 cannot synthesize a valid band around a zero/negative central estimate"
        )

    original_low = valuation_low
    original_mid = valuation_mid
    original_high = valuation_high

    valuation_low_rounded = range_calculator.round_valuation(valuation_low)
    valuation_mid_rounded = valuation_mid
    valuation_high_rounded = range_calculator.round_valuation(valuation_high)

    ordering_clamps: dict[str, object] = {}
    if valuation_mid_rounded > 0:
        granularity_for_mid = granularity_for(valuation_mid_rounded)

        if valuation_low_rounded > valuation_mid_rounded:
            snapped_low = (valuation_mid_rounded // granularity_for_mid) * granularity_for_mid
            logger.warning(
                "Step 11: Rounded low > mid - snapping low down to ordered granular value",
                extra={
                    "step_number": 11,
                    "rounded_low_before_clamp": valuation_low_rounded,
                    "valuation_mid": valuation_mid_rounded,
                    "rounded_high": valuation_high_rounded,
                    "snapped_low": snapped_low,
                    "granularity": granularity_for_mid,
                },
            )
            ordering_clamps["low_clamped_from"] = valuation_low_rounded
            valuation_low_rounded = snapped_low
            ordering_clamps["low_clamped_to"] = snapped_low
            try:
                ordering_clamps_total.labels(bound="low").inc()
            except Exception:
                pass

        if valuation_high_rounded < valuation_mid_rounded:
            granularity = granularity_for_mid
            ratio = valuation_mid_rounded / granularity
            snapped_high = (
                valuation_mid_rounded if ratio == int(ratio) else (int(ratio) + 1) * granularity
            )
            logger.warning(
                "Step 11: Rounded high < mid - snapping high up to ordered granular value",
                extra={
                    "step_number": 11,
                    "rounded_high_before_clamp": valuation_high_rounded,
                    "valuation_mid": valuation_mid_rounded,
                    "rounded_low": valuation_low_rounded,
                    "snapped_high": snapped_high,
                    "granularity": granularity,
                },
            )
            ordering_clamps["high_clamped_from"] = valuation_high_rounded
            valuation_high_rounded = snapped_high
            ordering_clamps["high_clamped_to"] = snapped_high
            try:
                ordering_clamps_total.labels(bound="high").inc()
            except Exception:
                pass

    rounding_impact_mid = (
        abs(valuation_mid_rounded - original_mid) / original_mid * 100 if original_mid > 0 else 0
    )
    rounding_impact_low = (
        abs(valuation_low_rounded - original_low) / original_low * 100 if original_low > 0 else 0
    )
    rounding_impact_high = (
        abs(valuation_high_rounded - original_high) / original_high * 100
        if original_high > 0
        else 0
    )

    rounding_details: dict[str, object] = {
        "original_low": original_low,
        "original_mid": original_mid,
        "original_high": original_high,
        "rounded_low": valuation_low_rounded,
        "rounded_mid": valuation_mid_rounded,
        "rounded_high": valuation_high_rounded,
        "rounding_impact_mid_pct": rounding_impact_mid,
        "rounding_impact_low_pct": rounding_impact_low,
        "rounding_impact_high_pct": rounding_impact_high,
        "ordering_clamps": ordering_clamps or None,
    }

    if equity_value_mid is not None:
        settings = get_settings()
        rounding_tolerance = max(
            Decimal("0.01"),
            abs(equity_value_mid) * (settings.value_chain_tolerance_percent / 100),
        )
        post_rounding_difference = abs(valuation_mid_rounded - equity_value_mid)
        post_rounding_difference_percent = validator.safe_percentage_calculation(
            post_rounding_difference, equity_value_mid, Decimal("0.0")
        )

        if post_rounding_difference > rounding_tolerance:
            logger.warning(
                "Step 11: Post-rounding value chain discrepancy detected",
                extra={
                    "step_number": 11,
                    "step7_8_equity_value_mid": equity_value_mid,
                    "step11_rounded_valuation_mid": valuation_mid_rounded,
                    "post_rounding_difference": post_rounding_difference,
                    "post_rounding_difference_percent": post_rounding_difference_percent,
                    "rounding_tolerance": rounding_tolerance,
                },
            )

    return (
        valuation_low_rounded,
        valuation_mid_rounded,
        valuation_high_rounded,
        rounding_details,
    )
