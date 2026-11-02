"""
Valuation Range Calculator

Legacy illustrative range policies and supplied simulation/comparable ranges.
Heuristic widths are not empirical confidence intervals or professional standards.

Key Principles:
- Mid-point is the supplied or weighted model conclusion
- Range width depends on confidence and methodology agreement
- Follows synthesizer logic from synthesizer.py lines 336-412

Author: Senior CTO
Version: 1.0.0
"""

from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from functools import wraps
from typing import Callable, Dict, Optional, ParamSpec, TypeVar

from src.constants.valuation_constants import get_confidence_spread
from src.domain.range_calculator.multiples_dispersion_calculator import InputConverter
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.exceptions import ValidationError
from src.utils.logging import get_logger

logger = get_logger(__name__)


P = ParamSpec("P")
T = TypeVar("T")


def _financial_context(function: Callable[P, T]) -> Callable[P, T]:
    """Keep range arithmetic independent of another request's Decimal context."""

    @wraps(function)
    def calculate(*args: P.args, **kwargs: P.kwargs) -> T:
        with localcontext() as context:
            context.prec = 50
            context.rounding = ROUND_HALF_EVEN
            return function(*args, **kwargs)

    return calculate


class ValuationRangeCalculator:
    """
    Calculate illustrative ranges using the existing versioned policy inputs.

    Implements confidence-based spreads:
    - High confidence: ±12% (24% total spread)
    - Medium confidence: ±18% (36% total spread)
    - Low confidence: ±22% (44% total spread)
    """

    @staticmethod
    @_financial_context
    def calculate_range(
        equity_value: Decimal,
        confidence_level: str = "medium",
        methodology_variance: Optional[Decimal] = None,
        revenue: Optional[Decimal] = None,
        use_enhanced_spread: bool = False,
    ) -> Dict[str, Decimal]:
        """Apply the existing illustrative spread policy to a supplied value.

        Legacy confidence labels select a heuristic, not empirical coverage.
        Invalid inputs and calculation failures propagate to method admission;
        they must never be replaced by a successful narrower fallback range.
        """
        value = InputConverter.convert_to_decimal(equity_value)
        if confidence_level not in ("high", "medium", "low"):
            raise ValidationError("Unknown illustrative range policy")
        variance = InputConverter.convert_optional_to_decimal(methodology_variance)
        if variance is not None and variance < 0:
            raise ValidationError("Method dispersion cannot be negative")
        sales = InputConverter.convert_optional_to_decimal(revenue)
        if sales is not None and sales < 0:
            raise ValidationError("Range sizing revenue cannot be negative")
        spread = (
            ValuationRangeCalculator._calculate_enhanced_confidence_spread(confidence_level, sales)
            if use_enhanced_spread and sales is not None
            else ValuationRangeCalculator._calculate_range_percentage(confidence_level, variance)
        )
        spread = InputConverter.convert_to_decimal(spread)
        if spread < 0 or spread > 1:
            raise ValidationError("Invalid illustrative range spread")
        offset = abs(value) * spread
        return {
            "equity_value_low": value - offset,
            "equity_value_mid": value,
            "equity_value_high": value + offset,
        }

    @staticmethod
    def _calculate_range_percentage(
        confidence_level: str, methodology_variance: Optional[Decimal] = None
    ) -> Decimal:
        """
        Calculate range percentage based on confidence and methodology agreement.

        Legacy illustrative policy:
        - High confidence/agreement: ±12% (24% total spread)
        - Medium confidence/agreement: ±18% (36% total spread)
        - Low confidence/disagreement: ±22% (44% total spread)
        """

        if methodology_variance is not None:
            # Convert to Decimal if needed
            if isinstance(methodology_variance, float):
                methodology_variance = to_decimal(str(methodology_variance))
            elif not isinstance(methodology_variance, Decimal):
                methodology_variance = to_decimal(str(methodology_variance))

            # Multi-methodology scenario - assess agreement
            if methodology_variance < to_decimal("0.15"):  # Strong agreement (<15% difference)
                range_pct = to_decimal(str(get_confidence_spread("high")))  # ±12% → 1.27x spread
            elif methodology_variance < to_decimal("0.30"):  # Moderate agreement (<30% difference)
                range_pct = to_decimal(str(get_confidence_spread("medium")))  # ±18% → 1.44x spread
            else:  # Significant divergence (>30% difference)
                range_pct = to_decimal(str(get_confidence_spread("low")))  # ±22% → 1.56x spread
        else:
            # Single methodology - use confidence level from configuration
            range_pct = to_decimal(str(get_confidence_spread(confidence_level)))

        return range_pct

    @staticmethod
    @_financial_context
    def calculate_multiples_dispersion_range(
        ebitda: Decimal,
        revenue: Decimal,
        p25_ebitda_multiple: Optional[Decimal],
        p50_ebitda_multiple: Optional[Decimal],
        p75_ebitda_multiple: Optional[Decimal],
        revenue_multiple_p25: Optional[Decimal],
        revenue_multiple_p50: Optional[Decimal],
        revenue_multiple_p75: Optional[Decimal],
        total_adjustment_factor: Decimal,
        net_debt: Decimal = to_decimal("0.0"),
        cash: Decimal = to_decimal("0.0"),
        primary_method: str = "ebitda_multiple",
    ) -> Dict[str, Decimal]:
        """
        Calculate range using multiple dispersion (P25/P50/P75).

        Delegates to MultiplesDispersionCalculator for improved maintainability.

        Formula:
            Low = P25 Multiple × Financial Metric × Adjustment Factor - Net Debt
            Mid = P50 Multiple × Financial Metric × Adjustment Factor - Net Debt (current valuation)
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
            total_adjustment_factor: Combined adjustment factor (Decimal('1.0') + size_discount + liquidity_discount + ...)
            net_debt: Net debt (total_debt - cash)
            cash: Cash balance
            primary_method: "ebitda_multiple" or "revenue_multiple"

        Returns:
            Dict with equity_value_low, equity_value_mid, equity_value_high, and range_methodology

        Supplied percentile evidence is identified separately from assumed bounds.
        """
        from src.domain.range_calculator.multiples_dispersion_calculator import (
            MultiplesDispersionCalculator,
        )

        return MultiplesDispersionCalculator.calculate(
            ebitda=ebitda,
            revenue=revenue,
            p25_ebitda_multiple=p25_ebitda_multiple,
            p50_ebitda_multiple=p50_ebitda_multiple,
            p75_ebitda_multiple=p75_ebitda_multiple,
            revenue_multiple_p25=revenue_multiple_p25,
            revenue_multiple_p50=revenue_multiple_p50,
            revenue_multiple_p75=revenue_multiple_p75,
            total_adjustment_factor=total_adjustment_factor,
            net_debt=net_debt,
            cash=cash,
            primary_method=primary_method,
        )

    @staticmethod
    def _calculate_enhanced_confidence_spread(confidence_level: str, revenue: Decimal) -> Decimal:
        """
        Enhanced confidence spread with size adjustments.

        Small companies (<€5M): Wider spreads (±25%) due to higher uncertainty
        Medium companies (€5M-€25M): Standard spreads (±18%)
        Large companies (>€25M): Tighter spreads (±12%)

        Args:
            confidence_level: "high", "medium", or "low"
            revenue: Company revenue in EUR

        Returns:
            Spread percentage (Decimal('0.12') to Decimal('0.30'))

        These size modifiers are legacy assumptions, not calibrated coverage.
        """
        # Convert revenue to Decimal if needed
        if isinstance(revenue, float):
            revenue = to_decimal(str(revenue))
        elif not isinstance(revenue, Decimal):
            revenue = to_decimal(str(revenue))

        base_spread = to_decimal(str(get_confidence_spread(confidence_level)))

        # Adjust for company size
        if revenue < to_decimal("5000000"):
            # Small companies: wider spread (more uncertainty)
            enhanced_spread = min(to_decimal("0.30"), base_spread * to_decimal("1.4"))  # Max 30%
            logger.info(
                f"Enhanced spread for small company: {from_decimal(base_spread * to_decimal('100'), precision=1):.1f}% → {from_decimal(enhanced_spread * to_decimal('100'), precision=1):.1f}%"
            )
        elif revenue < to_decimal("25000000"):
            # Medium companies: standard spread
            enhanced_spread = base_spread
        else:
            # Large companies: tighter spread
            enhanced_spread = max(to_decimal("0.12"), base_spread * to_decimal("0.9"))  # Min 12%
            logger.info(
                f"Enhanced spread for large company: {from_decimal(base_spread * to_decimal('100'), precision=1):.1f}% → {from_decimal(enhanced_spread * to_decimal('100'), precision=1):.1f}%"
            )

        return enhanced_spread

    @staticmethod
    @_financial_context
    def calculate_probabilistic_range(
        equity_value: Decimal, monte_carlo_results: Dict, confidence_level: str = "medium"
    ) -> Dict:
        """Project supplied simulation percentiles, never repair broken output.

        These are modelled percentiles, not demonstrated transaction coverage.
        The legacy confidence_interval key remains for reader compatibility.
        """
        InputConverter.convert_to_decimal(equity_value)
        if not isinstance(monte_carlo_results, dict) or not all(
            key in monte_carlo_results for key in ("p10", "p50", "p90")
        ):
            raise ValidationError("Simulation requires P10, P50 and P90")
        low, mid, high = (
            InputConverter.convert_to_decimal(monte_carlo_results[key])
            for key in ("p10", "p50", "p90")
        )
        if not low <= mid <= high:
            raise ValidationError("Simulation percentiles are not ordered")
        interval = monte_carlo_results.get("confidence_interval_80")
        if interval is not None:
            if not isinstance(interval, (tuple, list)) or len(interval) != 2:
                raise ValidationError("Simulation interval requires two bounds")
            bounds = tuple(InputConverter.convert_to_decimal(value) for value in interval)
            if bounds != (low, high):
                raise ValidationError("Simulation interval conflicts with P10/P90")
        deviation = InputConverter.convert_optional_to_decimal(monte_carlo_results.get("std_dev"))
        if deviation is not None and deviation < 0:
            raise ValidationError("Simulation standard deviation cannot be negative")
        return {
            "equity_value_low": low,
            "equity_value_mid": mid,
            "equity_value_high": high,
            "confidence_interval": (low, high),
            "standard_deviation": deviation,
        }

    @staticmethod
    @_financial_context
    def calculate_asymmetric_range(
        equity_value: Decimal, confidence_level: str, company_size: str = "sme"
    ) -> Dict[str, Decimal]:
        """Apply the legacy asymmetric scenario policy; preserve signed values."""
        value = InputConverter.convert_to_decimal(equity_value)
        if confidence_level not in ("high", "medium", "low"):
            raise ValidationError("Unknown illustrative range policy")
        factors = {
            "sme": (Decimal("0.20"), Decimal("0.15")),
            "mid_market": (Decimal("0.18"), Decimal("0.18")),
            "enterprise": (Decimal("0.15"), Decimal("0.20")),
        }
        if company_size not in factors:
            raise ValidationError("Unknown company size for illustrative range")
        downside, upside = factors[company_size]
        scale = {"high": Decimal("0.8"), "medium": Decimal("1"), "low": Decimal("1.2")}[
            confidence_level
        ]
        downside, upside = downside * scale, upside * scale
        return {
            "equity_value_low": value - abs(value) * downside,
            "equity_value_mid": value,
            "equity_value_high": value + abs(value) * upside,
            "downside_risk": downside,
            "upside_potential": upside,
        }

    @staticmethod
    @_financial_context
    def calculate_multi_methodology_range(
        dcf_value: Optional[Decimal],
        multiples_value: Optional[Decimal],
        dcf_weight: Decimal = Decimal("0.5"),
        multiples_weight: Decimal = Decimal("0.5"),
    ) -> Dict[str, Decimal]:
        """Combine admitted values of the same basis, including zero/deficits.

        The caller owns method eligibility and EV/equity compatibility. Only
        absent or explicitly zero-weight methods are excluded here.
        """
        values = []
        for amount, weight in ((dcf_value, dcf_weight), (multiples_value, multiples_weight)):
            admitted_weight = InputConverter.convert_to_decimal(weight)
            if not Decimal("0") <= admitted_weight <= Decimal("1"):
                raise ValidationError("Method weights must be between zero and one")
            admitted = InputConverter.convert_optional_to_decimal(amount)
            if admitted is not None and admitted_weight > 0:
                values.append((admitted, admitted_weight))
        if not values:
            raise ValidationError("No weighted valuation methods are available")
        total_weight = sum(weight for _, weight in values)
        midpoint = sum(value * weight for value, weight in values) / total_weight
        if len(values) == 1:
            return ValuationRangeCalculator.calculate_range(midpoint, "medium")
        low_value, high_value = min(v for v, _ in values), max(v for v, _ in values)
        scale = max(abs(low_value), abs(high_value))
        dispersion = (high_value - low_value) / scale if scale else Decimal("0")
        result = ValuationRangeCalculator.calculate_range(midpoint, "medium", dispersion)
        # A synthesis interval must not hide disagreement between its methods.
        result["equity_value_low"] = min(result["equity_value_low"], low_value)
        result["equity_value_high"] = max(result["equity_value_high"], high_value)
        return result
