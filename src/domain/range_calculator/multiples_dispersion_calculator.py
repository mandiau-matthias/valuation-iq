"""
Multiples Dispersion Calculator

Handles calculation of valuation ranges using multiple dispersion (P25/P50/P75).
Refactored from ValuationRangeCalculator.calculate_multiples_dispersion_range
to reduce complexity from 30 to <10.
"""

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

from src.utils.decimal_helpers import from_decimal
from src.utils.exceptions import (
    CalculationError,
    DataQualityError,
    MultiplesCalculationError,
    ValidationError,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


class InputConverter:
    """Converts and validates inputs for multiples dispersion calculation."""

    @staticmethod
    def convert_to_decimal(value: Any) -> Decimal:
        """Admit finite machine decimals without stripping financial syntax."""
        if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
            raise ValidationError("Dispersion inputs must use finite decimal notation")
        if (
            isinstance(value, str)
            and re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", value.strip())
            is None
        ):
            raise ValidationError("Dispersion inputs must use finite decimal notation")
        try:
            result = Decimal(str(value).strip())
        except InvalidOperation as exc:
            raise ValidationError("Dispersion inputs must use finite decimal notation") from exc
        if not result.is_finite():
            raise ValidationError("Dispersion inputs must be finite")
        return result

    @staticmethod
    def convert_optional_to_decimal(value: Optional[Any]) -> Optional[Decimal]:
        """Convert optional numeric value to Decimal."""
        if value is None:
            return None
        return InputConverter.convert_to_decimal(value)

    @staticmethod
    def validate_adjustment_factor(adjustment_factor: Decimal) -> None:
        """Validate that adjustment factor is positive."""
        if adjustment_factor <= Decimal("0"):
            logger.error(f"Invalid total_adjustment_factor: {adjustment_factor}")
            raise ValidationError(
                f"Total adjustment factor must be positive, got: {adjustment_factor}"
            )

    @staticmethod
    def validate_financial_metric(metric: Decimal, metric_name: str) -> None:
        """Validate that financial metric is positive."""
        if metric <= Decimal("0"):
            logger.error(f"Invalid {metric_name} for dispersion range: {metric}")
            raise ValidationError(
                f"{metric_name} (EBITDA or Revenue) must be positive, got: {metric}"
            )


class MultipleSelector:
    """Selects appropriate multiples (revenue vs EBITDA) for calculation."""

    @staticmethod
    def select_multiples(
        primary_method: str,
        revenue_multiple_p25: Optional[Decimal],
        revenue_multiple_p50: Optional[Decimal],
        revenue_multiple_p75: Optional[Decimal],
        p25_ebitda_multiple: Optional[Decimal],
        p50_ebitda_multiple: Optional[Decimal],
        p75_ebitda_multiple: Optional[Decimal],
        revenue: Decimal,
        ebitda: Decimal,
    ) -> tuple[Decimal, Decimal, Decimal, Decimal]:
        """
        Select multiples and financial metric based on primary method and availability.

        Returns:
            Tuple of (p25_multiple, p50_multiple, p75_multiple, financial_metric)
        """
        # Try revenue multiples first if primary method is revenue_multiple
        if primary_method not in {"revenue_multiple", "ebitda_multiple"}:
            raise ValidationError(f"Unsupported dispersion method: {primary_method}")
        if (
            primary_method == "revenue_multiple"
            and revenue_multiple_p25 is not None
            and revenue_multiple_p50 is not None
            and revenue_multiple_p75 is not None
        ):
            logger.info("Using revenue multiples for dispersion range")
            return (
                revenue_multiple_p25,
                revenue_multiple_p50,
                revenue_multiple_p75,
                revenue,
            )

        # Try EBITDA multiples
        if (
            primary_method == "ebitda_multiple"
            and p25_ebitda_multiple is not None
            and p50_ebitda_multiple is not None
            and p75_ebitda_multiple is not None
        ):
            logger.info("Using EBITDA multiples for dispersion range")
            return (
                p25_ebitda_multiple,
                p50_ebitda_multiple,
                p75_ebitda_multiple,
                ebitda,
            )

        # Fallback: use available P50 and estimate P25/P75
        return MultipleSelector._fallback_multiples(
            primary_method,
            revenue_multiple_p50,
            p50_ebitda_multiple,
            revenue,
            ebitda,
            revenue_multiple_p25 if primary_method == "revenue_multiple" else p25_ebitda_multiple,
            revenue_multiple_p75 if primary_method == "revenue_multiple" else p75_ebitda_multiple,
        )

    @staticmethod
    def _fallback_multiples(
        primary_method: str,
        revenue_multiple_p50: Optional[Decimal],
        p50_ebitda_multiple: Optional[Decimal],
        revenue: Decimal,
        ebitda: Decimal,
        supplied_lower: Optional[Decimal] = None,
        supplied_upper: Optional[Decimal] = None,
    ) -> tuple[Decimal, Decimal, Decimal, Decimal]:
        """Fallback: use available P50 and estimate P25/P75 as ±20%."""
        if primary_method == "revenue_multiple" and revenue_multiple_p50 is not None:
            p50_multiple = revenue_multiple_p50
            financial_metric = revenue
        elif primary_method == "ebitda_multiple" and p50_ebitda_multiple is not None:
            p50_multiple = p50_ebitda_multiple
            financial_metric = ebitda
        else:
            raise ValidationError("No valid multiples available for dispersion range calculation")

        # Estimate P25/P75 as ±20% of P50
        p25_multiple = (
            supplied_lower if supplied_lower is not None else p50_multiple * Decimal("0.80")
        )
        p75_multiple = (
            supplied_upper if supplied_upper is not None else p50_multiple * Decimal("1.20")
        )
        logger.warning("Using estimated P25/P75 multiples (±20% of P50) - insufficient comparables")

        return (p25_multiple, p50_multiple, p75_multiple, financial_metric)


class RangeCalculator:
    """Calculates equity value range from enterprise values."""

    @staticmethod
    def calculate_range(
        financial_metric: Decimal,
        p25_multiple: Decimal,
        p50_multiple: Decimal,
        p75_multiple: Decimal,
        total_adjustment_factor: Decimal,
        net_debt: Decimal,
        cash: Decimal,
    ) -> Dict[str, Decimal]:
        """
        Calculate equity value range from multiples and financial metric.

        Formula:
            EV = Financial Metric × Multiple × Adjustment Factor
            Equity = EV - Net Debt (cash is already included in net debt)

        Returns:
            Dict with equity_value_low, equity_value_mid, equity_value_high
        """
        # Calculate enterprise values using each percentile
        ev_low = financial_metric * p25_multiple * total_adjustment_factor
        ev_mid = financial_metric * p50_multiple * total_adjustment_factor
        ev_high = financial_metric * p75_multiple * total_adjustment_factor

        # Net debt = gross financial debt - cash. Adding cash here again
        # overstates every bound by the cash balance. The cash parameter is
        # retained for existing callers, but must not enter the bridge twice.
        equity_value_low = ev_low - net_debt
        equity_value_mid = ev_mid - net_debt
        equity_value_high = ev_high - net_debt

        # Ensure logical ordering
        if not (equity_value_low <= equity_value_mid <= equity_value_high):
            raise ValidationError("Multiple percentiles must produce ordered equity bounds")

        return {
            "equity_value_low": equity_value_low,
            "equity_value_mid": equity_value_mid,
            "equity_value_high": equity_value_high,
        }


class MultiplesDispersionCalculator:
    """
    Calculate valuation range using multiple dispersion (P25/P50/P75).

    Refactored from ValuationRangeCalculator.calculate_multiples_dispersion_range
    to reduce complexity from 30 to ~5.
    """

    @staticmethod
    def calculate(
        ebitda: Decimal,
        revenue: Decimal,
        p25_ebitda_multiple: Optional[Decimal],
        p50_ebitda_multiple: Optional[Decimal],
        p75_ebitda_multiple: Optional[Decimal],
        revenue_multiple_p25: Optional[Decimal],
        revenue_multiple_p50: Optional[Decimal],
        revenue_multiple_p75: Optional[Decimal],
        total_adjustment_factor: Decimal,
        net_debt: Decimal = Decimal("0.0"),
        cash: Decimal = Decimal("0.0"),
        primary_method: str = "ebitda_multiple",
    ) -> Dict[str, Any]:
        """
        Calculate range using multiple dispersion (P25/P50/P75).

        Formula:
            Low = P25 Multiple × Financial Metric × Adjustment Factor - Net Debt
            Mid = P50 Multiple × Financial Metric × Adjustment Factor - Net Debt
            High = P75 Multiple × Financial Metric × Adjustment Factor - Net Debt

        Args:
            ebitda: EBITDA value
            revenue: Revenue value
            p25_ebitda_multiple: 25th percentile EBITDA multiple
            p50_ebitda_multiple: 50th percentile (median) EBITDA multiple
            p75_ebitda_multiple: 75th percentile EBITDA multiple
            revenue_multiple_p25: 25th percentile revenue multiple
            revenue_multiple_p50: 50th percentile (median) revenue multiple
            revenue_multiple_p75: 75th percentile revenue multiple
            total_adjustment_factor: Combined adjustment factor
            net_debt: Net debt (total_debt - cash)
            cash: Cash balance
            primary_method: "ebitda_multiple" or "revenue_multiple"

        Returns:
            Dict with equity_value_low, equity_value_mid, equity_value_high, and range_methodology

        Policy: supplied bounds require separate comparable-data provenance.
        Missing bounds use a disclosed 20% spread assumption, not an empirical
        confidence interval.
        """
        try:
            # Convert inputs to Decimal
            ebitda_decimal = InputConverter.convert_to_decimal(ebitda)
            revenue_decimal = InputConverter.convert_to_decimal(revenue)
            total_adjustment_factor_decimal = InputConverter.convert_to_decimal(
                total_adjustment_factor
            )
            net_debt_decimal = InputConverter.convert_to_decimal(net_debt)
            cash_decimal = InputConverter.convert_to_decimal(cash)

            # Convert optional multiples
            p25_ebitda = InputConverter.convert_optional_to_decimal(p25_ebitda_multiple)
            p50_ebitda = InputConverter.convert_optional_to_decimal(p50_ebitda_multiple)
            p75_ebitda = InputConverter.convert_optional_to_decimal(p75_ebitda_multiple)
            rev_p25 = InputConverter.convert_optional_to_decimal(revenue_multiple_p25)
            rev_p50 = InputConverter.convert_optional_to_decimal(revenue_multiple_p50)
            rev_p75 = InputConverter.convert_optional_to_decimal(revenue_multiple_p75)

            if not all(
                value.is_finite()
                for value in (
                    ebitda_decimal,
                    revenue_decimal,
                    total_adjustment_factor_decimal,
                    net_debt_decimal,
                    cash_decimal,
                )
            ):
                raise ValidationError("Dispersion financial inputs must be finite")

            supplied_percentiles = (
                (rev_p25, rev_p50, rev_p75)
                if primary_method == "revenue_multiple"
                else (p25_ebitda, p50_ebitda, p75_ebitda)
            )
            if any(
                value is not None and (not value.is_finite() or value < 0)
                for value in supplied_percentiles
            ):
                raise ValidationError("Multiple percentiles must be finite and nonnegative")
            for lower, upper in zip(supplied_percentiles, supplied_percentiles[1:]):
                if lower is not None and upper is not None and lower > upper:
                    raise ValidationError("Multiple percentiles must be ordered P25 <= P50 <= P75")

            # Validate inputs
            InputConverter.validate_adjustment_factor(total_adjustment_factor_decimal)

            # Select multiples and financial metric
            p25_multiple, p50_multiple, p75_multiple, financial_metric = (
                MultipleSelector.select_multiples(
                    primary_method,
                    rev_p25,
                    rev_p50,
                    rev_p75,
                    p25_ebitda,
                    p50_ebitda,
                    p75_ebitda,
                    revenue_decimal,
                    ebitda_decimal,
                )
            )

            # Validate financial metric
            InputConverter.validate_financial_metric(financial_metric, "Financial metric")

            if p50_multiple <= 0:
                raise ValidationError("The selected median multiple must be positive")

            # Calculate range
            range_result = RangeCalculator.calculate_range(
                financial_metric,
                p25_multiple,
                p50_multiple,
                p75_multiple,
                total_adjustment_factor_decimal,
                net_debt_decimal,
                cash_decimal,
            )

            # Add methodology
            percentiles_supplied = all(value is not None for value in supplied_percentiles)
            result = {
                **range_result,
                "range_methodology": (
                    "multiple_dispersion" if percentiles_supplied else "assumed_multiple_spread"
                ),
                "range_basis": {
                    # Numeric arguments alone do not establish empirical
                    # provenance or calibrated transaction-price coverage.
                    "empirical_percentiles": None if percentiles_supplied else False,
                    "bounds_source": (
                        "supplied_percentiles" if percentiles_supplied else "assumed_spread"
                    ),
                    "assumed_spread": None if percentiles_supplied else Decimal("0.20"),
                    "assumed_bounds": [
                        name
                        for name, value in zip(
                            ("low", "high"), (supplied_percentiles[0], supplied_percentiles[2])
                        )
                        if value is None
                    ],
                    "primary_method": primary_method,
                },
            }

            # Log result
            logger.info(
                "Multiple dispersion range calculated",
                p25_multiple=from_decimal(p25_multiple, precision=2),
                p50_multiple=from_decimal(p50_multiple, precision=2),
                p75_multiple=from_decimal(p75_multiple, precision=2),
                equity_value_low=from_decimal(range_result["equity_value_low"], precision=2),
                equity_value_mid=from_decimal(range_result["equity_value_mid"], precision=2),
                equity_value_high=from_decimal(range_result["equity_value_high"], precision=2),
            )

            return result

        except (CalculationError, DataQualityError, ValidationError):
            raise  # Re-raise specific errors
        except (ValueError, TypeError, ZeroDivisionError, AttributeError) as e:
            logger.error(
                f"Error calculating multiple dispersion range: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
                exc_info=True,
            )
            # Fallback to confidence-based range
            # Import here to avoid circular dependency
            from src.domain.range_calculator import ValuationRangeCalculator

            fallback_value = Decimal("0")
            return ValuationRangeCalculator._fallback_range(fallback_value)
        except MultiplesCalculationError as e:
            logger.error(
                f"Unexpected error calculating multiple dispersion range: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
                exc_info=True,
            )
            raise CalculationError(
                f"Unexpected error in multiple dispersion range calculation: {e}"
            ) from e
