"""
Range Calculator for Step 11 Synthesis

Handles range generation, rounding, and ordering validation.
"""

from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.equity_range_normalization import coerce_equity_range_triple
from src.utils.logging import get_logger

from ...base_step import StepStatus

logger = get_logger(__name__)


class RangeCalculator:
    """
    Calculator for valuation range operations.

    Responsibilities:
    - Generate fallback ranges when Step 10 is unavailable
    - Round valuations to meaningful precision
    - Validate and fix range ordering (low <= mid <= high)
    """

    def __init__(self):
        """Initialize range calculator."""
        pass

    def generate_fallback_range(
        self, previous_results: Dict[int, Any], request: Any
    ) -> Tuple[float, float, float]:
        """
        Generate fallback valuation range when Step 10 is unavailable.

        Uses Step 7/8 equity values and confidence score to create a simple range.

        Args:
            previous_results: Results from previous steps
            request: Valuation request

        Returns:
            Tuple of (valuation_low, valuation_mid, valuation_high)
        """
        logger.info("🔄 Generating fallback valuation range", extra={"step_number": 11})

        # Get equity value with priority: Step 8 > Step 7 > Step 6 EV (fallback)
        step8_output = previous_results.get(8)
        step7_output = previous_results.get(7)
        step6_output = previous_results.get(6)

        equity_value_mid = None
        equity_source = None

        if step8_output and step8_output.status == StepStatus.COMPLETED:
            equity_value_mid = step8_output.result.get("ownership_adjusted_equity_mid")
            if equity_value_mid is not None:
                equity_source = "Step 8 (ownership-adjusted)"
                logger.debug("Using Step 8 equity for fallback", extra={"equity": equity_value_mid})

        if (
            equity_value_mid is None
            and step7_output
            and step7_output.status == StepStatus.COMPLETED
        ):
            equity_value_mid = step7_output.result.get("equity_value_mid")
            if equity_value_mid is not None:
                equity_source = "Step 7 (equity)"
                logger.debug("Using Step 7 equity for fallback", extra={"equity": equity_value_mid})

        # CRITICAL FIX: Use Step 6 EV values when Step 7 fails
        if (
            equity_value_mid is None
            and step6_output
            and step6_output.status == StepStatus.COMPLETED
        ):
            ev_mid = step6_output.result.get("enterprise_value_mid")
            # BANK-GRADE: Use is not None check to preserve zero values (zero is a valid valuation)
            if ev_mid is not None:
                equity_value_mid = ev_mid
                equity_source = "Step 6 (EV approximation - Step 7 failed)"
                logger.info(
                    "⚠️ Using Step 6 EV as equity approximation for fallback (Step 7 unavailable)",
                    extra={
                        "step6_ev_mid": ev_mid,
                        "step7_status": step7_output.status.value if step7_output else "not_found",
                    },
                )

        if not equity_value_mid or equity_value_mid <= 0:
            logger.warning(
                "⚠️ No valid equity value found for fallback, using minimal values",
                extra={
                    "step_number": 11,
                    "step6_available": step6_output is not None,
                    "step7_available": step7_output is not None,
                    "step8_available": step8_output is not None,
                },
            )
            return (Decimal("0.0"), Decimal("0.01"), Decimal("0.01"))

        # Get confidence score from Step 9 (or use default)
        step9_output = previous_results.get(9)
        confidence_score = 66  # Default medium confidence
        if step9_output and step9_output.status == StepStatus.COMPLETED:
            confidence_score = step9_output.result.get("overall_confidence_score", 66)

        # Calculate spread based on confidence score
        # Higher confidence = tighter spread, lower confidence = wider spread
        # Spread ranges from ±15% (high confidence) to ±30% (low confidence)
        if confidence_score >= 80:
            spread_pct = Decimal("0.15")  # ±15% for high confidence
        elif confidence_score >= 60:
            spread_pct = Decimal("0.20")  # ±20% for medium confidence
        else:
            spread_pct = Decimal("0.30")  # ±30% for low confidence

        # Calculate range
        valuation_mid = to_decimal(equity_value_mid)
        valuation_low = valuation_mid * (1 - spread_pct)
        valuation_high = valuation_mid * (1 + spread_pct)

        logger.info(
            "✅ Fallback range generated",
            extra={
                "step_number": 11,
                "equity_value_mid": equity_value_mid,
                "confidence_score": confidence_score,
                "spread_pct": spread_pct * 100,
                "valuation_low": valuation_low,
                "valuation_mid": valuation_mid,
                "valuation_high": valuation_high,
            },
        )

        return (valuation_low, valuation_mid, valuation_high)

    def round_valuation(self, value: Decimal) -> Decimal:
        """
        Round valuation to meaningful precision.

        Args:
            value: Value to round

        Returns:
            Rounded value
        """
        if value >= 10_000_000:
            # Round to nearest 100K
            granularity = 100_000
            rounded = round(value / granularity) * granularity
            return rounded
        elif value >= 1_000_000:
            # Round to nearest 10K
            granularity = 10_000
            rounded = round(value / granularity) * granularity
            return rounded
        elif value >= 100_000:
            # Round to nearest 1K
            granularity = 1_000
            rounded = round(value / granularity) * granularity
            return rounded
        else:
            # Round to nearest 100
            granularity = 100
            rounded = round(value / granularity) * granularity
            return rounded

    def validate_and_fix_ordering(
        self,
        valuation_low: Decimal,
        valuation_mid: Decimal,
        valuation_high: Decimal,
        step10_result: Optional[Dict[str, Any]] = None,
        use_fallback: bool = False,
    ) -> Tuple[float, float, float]:
        """
        Validate and fix range ordering to ensure low <= mid <= high.

        Args:
            valuation_low: Low valuation
            valuation_mid: Mid valuation
            valuation_high: High valuation
            step10_result: Optional Step 10 result for preserving spreads
            use_fallback: Whether using fallback mode

        Returns:
            Tuple of (corrected_low, corrected_mid, corrected_high)
        """
        original_low = valuation_low
        original_high = valuation_high

        def sane_spread(spread: Decimal, default: Decimal, bound_name: str) -> Decimal:
            max_spread = Decimal("0.95") if bound_name == "low" else Decimal("2.5")
            if Decimal("0") < spread <= max_spread:
                return spread
            logger.warning(
                "Ignored invalid Step 10 spread while repairing range ordering",
                extra={
                    "step_number": 11,
                    "bound": bound_name,
                    "invalid_spread": str(spread),
                    "fallback_spread": str(default),
                },
            )
            return default

        if valuation_low > valuation_mid:
            # CRITICAL FIX: If Step 10 values exist, preserve Step 10's spread instead of using fixed 80%
            if not use_fallback and step10_result:
                _rc_low = step10_result.get("valuation_low")
                step10_original_low = _rc_low if _rc_low is not None else 0
                _rc_mid = step10_result.get("valuation_mid")
                step10_original_mid = _rc_mid if _rc_mid is not None else 0
                if step10_original_mid > 0:
                    step10_low_spread = (
                        (step10_original_mid - step10_original_low) / step10_original_mid
                        if step10_original_mid > 0
                        else Decimal("0.2")
                    )
                    step10_low_spread = sane_spread(
                        to_decimal(step10_low_spread),
                        Decimal("0.2"),
                        "low",
                    )
                    valuation_low = valuation_mid * (1 - step10_low_spread)
                    logger.warning(
                        "Invalid range ordering (low > mid), adjusted low using Step 10 spread",
                        extra={
                            "original_low": original_low,
                            "adjusted_low": valuation_low,
                            "step10_spread_used": step10_low_spread,
                        },
                    )
                else:
                    valuation_low = valuation_mid * Decimal("0.8")  # Fallback to 80% of mid
                    logger.warning(
                        "Invalid range ordering (low > mid), adjusted low value",
                        extra={"original_low": original_low, "adjusted_low": valuation_low},
                    )
            else:
                valuation_low = valuation_mid * Decimal("0.8")  # Adjust to 80% of mid
                logger.warning(
                    "Invalid range ordering (low > mid), adjusted low value",
                    extra={"original_low": original_low, "adjusted_low": valuation_low},
                )

        if valuation_high < valuation_mid:
            # CRITICAL FIX: If Step 10 values exist, preserve Step 10's spread instead of using fixed 120%
            if not use_fallback and step10_result:
                _rc_mid_h = step10_result.get("valuation_mid")
                step10_original_mid = _rc_mid_h if _rc_mid_h is not None else 0
                _rc_high = step10_result.get("valuation_high")
                step10_original_high = _rc_high if _rc_high is not None else 0
                if step10_original_mid > 0:
                    step10_high_spread = (
                        (step10_original_high - step10_original_mid) / step10_original_mid
                        if step10_original_mid > 0
                        else Decimal("0.2")
                    )
                    step10_high_spread = sane_spread(
                        to_decimal(step10_high_spread),
                        Decimal("0.2"),
                        "high",
                    )
                    valuation_high = valuation_mid * (1 + step10_high_spread)
                    logger.warning(
                        "Invalid range ordering (high < mid), adjusted high using Step 10 spread",
                        extra={
                            "original_high": original_high,
                            "adjusted_high": valuation_high,
                            "step10_spread_used": step10_high_spread,
                        },
                    )
                else:
                    valuation_high = valuation_mid * Decimal("1.2")  # Fallback to 120% of mid
                    logger.warning(
                        "Invalid range ordering (high < mid), adjusted high value",
                        extra={"original_high": original_high, "adjusted_high": valuation_high},
                    )
            else:
                valuation_high = valuation_mid * Decimal("1.2")  # Adjust to 120% of mid
                logger.warning(
                    "Invalid range ordering (high < mid), adjusted high value",
                    extra={"original_high": original_high, "adjusted_high": valuation_high},
                )

        valuation_low, valuation_mid, valuation_high, widened = coerce_equity_range_triple(
            valuation_low,
            valuation_mid,
            valuation_high,
        )
        if widened:
            logger.warning(
                "Step 11 range calculator widened bounds after spread-based correction",
                extra={
                    "step_number": 11,
                    "valuation_low": str(valuation_low),
                    "valuation_mid": str(valuation_mid),
                    "valuation_high": str(valuation_high),
                },
            )

        return (valuation_low, valuation_mid, valuation_high)
