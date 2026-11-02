"""
Adjustment Helpers

Helper functions for generating adjustment reasons and methodology rationales.
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from src.api.schemas import ValuationRequest
from src.domain.revenue_growth import revenue_growth
from src.utils.core import format_currency
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.valuation_logger import ValuationLogger


class AdjustmentHelpers:
    """
    Helper functions for adjustments and methodology explanations.

    Responsibilities:
    - Generate size discount reasons
    - Generate growth premium reasons
    - Build small firm adjustments
    - Generate methodology rationales
    """

    def __init__(self, logger: Optional[ValuationLogger] = None):
        """
        Initialize adjustment helpers.

        Args:
            logger: Optional logger instance
        """
        self.logger = logger or ValuationLogger(self.__class__.__name__)
        self.logger.debug("✅ AdjustmentHelpers initialized")

    def get_size_discount_reason(self, revenue: Decimal) -> str:
        """
        Get explanation for size discount based on McKinsey valuation standards.

        Args:
            revenue: Company revenue

        Returns:
            Size discount reason string
        """
        if revenue < 1_000_000:
            return f"Companies with {format_currency(revenue, currency='EUR', precision=0)} revenue trade at 30% lower multiples (micro business - highest risk tier, Duff & Phelps 2024)"
        elif revenue < 2_000_000:
            return f"Companies with {format_currency(revenue, currency='EUR', precision=0)} revenue trade at 20% lower multiples (very small business tier, Duff & Phelps 2024)"
        elif revenue < 3_000_000:
            return f"Companies with {format_currency(revenue, currency='EUR', precision=0)} revenue trade at 15% lower multiples (small business tier, Duff & Phelps 2024)"
        elif revenue < 5_000_000:
            return f"Companies with {format_currency(revenue, currency='EUR', precision=0)} revenue trade at 10% lower multiples (small-medium business tier, Duff & Phelps 2024)"
        else:
            return f"No size discount - multiples from databases are already correct for companies ≥€5M revenue (McKinsey standard)"

    def get_growth_premium_reason(self, request: ValuationRequest) -> str:
        """
        Get explanation for growth premium.

        Args:
            request: Valuation request

        Returns:
            Growth premium reason string
        """
        growth = revenue_growth(
            request.current_year_data, getattr(request, "historical_years_data", []) or []
        )
        if growth.rate is None:
            return "Comparable annual revenue growth is unavailable; no growth premium applied"
        growth_rate = growth.rate

        if growth_rate > 0.50:
            return f"Exceptional annualized revenue growth of {growth_rate:.1%} earns 15% valuation premium"
        elif growth_rate > 0.30:
            return (
                f"Strong annualized revenue growth of {growth_rate:.1%} earns 10% valuation premium"
            )
        elif growth_rate > 0.20:
            return f"Above-average annualized revenue growth of {growth_rate:.1%} earns 5% valuation premium"
        else:
            return f"Annualized revenue growth of {growth_rate:.1%} does not qualify for premium (needs >20%)"

    def build_small_firm_adjustments(
        self, multiples_results: Optional[Dict[str, Any]], request: ValuationRequest
    ) -> Optional[Dict[str, Any]]:
        """
        Extract and format small firm adjustments for transparency.

        Args:
            multiples_results: Multiples calculation results
            request: Valuation request

        Returns:
            Dictionary with adjustment details or None
        """
        if not multiples_results:
            return None

        # Extract adjustments from multiples_results
        size_discount = multiples_results.get("size_discount", Decimal("0.0"))
        liquidity_discount = multiples_results.get("liquidity_discount", Decimal("0.0"))
        country_adjustment = multiples_results.get("country_adjustment", Decimal("0.0"))
        growth_premium = multiples_results.get("growth_premium", Decimal("0.0"))

        combined_effect = size_discount + liquidity_discount + country_adjustment + growth_premium

        revenue = request.current_year_data.revenue
        base_value = multiples_results.get("enterprise_value", Decimal("0.0"))
        adjusted_value = multiples_results.get(
            "adjusted_equity_value", multiples_results.get("equity_value", Decimal("0.0"))
        )

        # If enterprise_value not available, back-calculate it from adjusted_value
        if base_value == Decimal("0.0") and adjusted_value > 0:
            total_adjustment_factor = Decimal("1.0") + combined_effect
            if total_adjustment_factor != 0:
                base_value = adjusted_value / total_adjustment_factor

        return {
            "size_discount": size_discount,
            "size_discount_reason": self.get_size_discount_reason(revenue),
            "liquidity_discount": liquidity_discount,
            "liquidity_discount_reason": "Private company liquidity discount adjusted for recurring revenue and profitability",
            "country_adjustment": country_adjustment,
            "country_adjustment_reason": f"Country risk adjustment for {request.country_code}",
            "growth_premium": growth_premium,
            "growth_premium_reason": self.get_growth_premium_reason(request),
            "combined_effect": combined_effect,
            "base_value_before_adjustments": base_value,
            "adjusted_value_after_adjustments": adjusted_value,
        }

    def generate_methodology_rationale(
        self,
        request: ValuationRequest,
        dcf_included: bool,
        dcf_exclusion_reason: Optional[str],
        dcf_weight: Decimal,
        multiples_weight: Decimal,
        requested_methodology: Optional[str] = None,
    ) -> str:
        """
        Generate user-friendly explanation of methodology selection.

        Args:
            request: Valuation request
            dcf_included: Whether DCF was included
            dcf_exclusion_reason: Reason DCF was excluded (if applicable)
            dcf_weight: DCF weight in hybrid methodology
            multiples_weight: Multiples weight in hybrid methodology
            requested_methodology: Methodology that was requested (if different from actual)

        Returns:
            Methodology rationale string
        """
        revenue = request.current_year_data.revenue

        # Add transparency when HYBRID was requested but downgraded
        if requested_methodology and requested_methodology.upper() == "HYBRID" and not dcf_included:
            return (
                f"For your company (revenue: {format_currency(revenue, currency='EUR', precision=0)}), "
                f"HYBRID methodology was requested, but DCF was excluded. {dcf_exclusion_reason}. "
                f"We used Market Multiples methodology only. This approach is more reliable for small businesses "
                f"and aligns with Big 4 and NACVA valuation standards."
            )
        elif not dcf_included:
            return (
                f"For your company (revenue: {format_currency(revenue, currency='EUR', precision=0)}), "
                f"we used Market Multiples methodology only. {dcf_exclusion_reason}. "
                f"This approach is more reliable for small businesses and aligns with "
                f"Big 4 and NACVA valuation standards."
            )
        elif dcf_weight > multiples_weight:
            return "DCF methodology weighted higher due to stable cash flows and growth visibility."
        else:
            return "Market Multiples weighted higher due to strong comparable company data."
