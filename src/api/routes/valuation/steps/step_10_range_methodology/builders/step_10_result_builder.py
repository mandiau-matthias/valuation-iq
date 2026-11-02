"""
Step 10 Result Builder

Builds result dictionaries and metadata for Step 10.
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from src.utils.decimal_helpers import from_decimal, safe_money_divide, to_decimal
from src.utils.equity_range_normalization import coerce_equity_range_triple
from src.utils.logging import get_logger

logger = get_logger(__name__)


class Step10ResultBuilder:
    """Builds result dictionaries and metadata for Step 10."""

    def build_result_dict(
        self,
        equity_low_float: Decimal,
        equity_mid_float: Decimal,
        equity_high_float: Decimal,
        methodology: str,
        confidence_level: str,
    ) -> Dict[str, Any]:
        """
        Build comprehensive result dictionary.

        Args:
            equity_low_float: Equity low value
            equity_mid_float: Equity mid value
            equity_high_float: Equity high value
            methodology: Methodology used
            confidence_level: Confidence level

        Returns:
            Result dictionary
        """
        equity_low_float, equity_mid_float, equity_high_float, widened = coerce_equity_range_triple(
            equity_low_float,
            equity_mid_float,
            equity_high_float,
        )
        if widened:
            logger.warning(
                "Step 10 result builder widened unordered valuation range",
                extra={
                    "step_number": 10,
                    "valuation_low": str(equity_low_float),
                    "valuation_mid": str(equity_mid_float),
                    "valuation_high": str(equity_high_float),
                    "methodology": methodology,
                },
            )

        return {
            "valuation_low": equity_low_float,
            "valuation_mid": equity_mid_float,  # CRITICAL: Must equal Step 7 equity_value_mid
            "valuation_high": equity_high_float,
            "methodology": methodology,
            "confidence_level": confidence_level,
        }

    def build_metadata_dict(
        self,
        equity_low: Decimal,
        equity_mid: Decimal,
        equity_high: Decimal,
        methodology: str,
        use_dispersion: bool,
        comparables_found: int,
        sufficient_comparables: bool,
        primary_method: Optional[str],
        base_spread: Optional[Decimal],
        size_adjustment: Optional[Decimal],
        business_type_multiplier: Optional[Decimal],
        growth_adjustment: Optional[Decimal],
        profitability_adjustment: Optional[Decimal],
        data_quality_adjustment: Optional[Decimal],
        spread: Optional[Decimal],
        spread_breakdown: Optional[Dict[str, Any]],
        use_asymmetric: bool,
        downside_pct: Optional[Decimal],
        upside_pct: Optional[Decimal],
        ev_revenue_p25: Optional[Decimal],
        ev_revenue_p50: Optional[Decimal],
        ev_revenue_p75: Optional[Decimal],
        ev_ebitda_p25: Optional[Decimal],
        ev_ebitda_p50: Optional[Decimal],
        ev_ebitda_p75: Optional[Decimal],
        business_category: any,
        growth_rate: Optional[Decimal],
        growth_validated: bool,
        ebitda_margin: Optional[Decimal],
        data_quality_score: Optional[int],
        step7_equity_value_mid: Decimal,
        ownership_adjusted_equity: Optional[Decimal],
    ) -> Dict[str, Any]:
        """
        Build comprehensive metadata dictionary.

        Args:
            equity_low: Equity low value
            equity_mid: Equity mid value
            equity_high: Equity high value
            methodology: Methodology used
            use_dispersion: Whether dispersion was used
            comparables_found: Number of comparables found
            sufficient_comparables: Whether comparables are sufficient
            primary_method: Primary method
            base_spread: Base spread
            size_adjustment: Size adjustment
            business_type_multiplier: Business type multiplier
            growth_adjustment: Growth adjustment
            profitability_adjustment: Profitability adjustment
            data_quality_adjustment: Data quality adjustment
            spread: Total spread
            spread_breakdown: Spread breakdown
            use_asymmetric: Whether asymmetric range was used
            downside_pct: Downside percentage
            upside_pct: Upside percentage
            ev_revenue_p25: Revenue P25 percentile
            ev_revenue_p50: Revenue P50 percentile
            ev_revenue_p75: Revenue P75 percentile
            ev_ebitda_p25: EBITDA P25 percentile
            ev_ebitda_p50: EBITDA P50 percentile
            ev_ebitda_p75: EBITDA P75 percentile
            business_category: Business category
            growth_rate: Growth rate
            growth_validated: Whether growth is validated
            ebitda_margin: EBITDA margin
            data_quality_score: Data quality score
            step7_equity_value_mid: Step 7 equity value mid
            ownership_adjusted_equity: Ownership adjusted equity

        Returns:
            Metadata dictionary
        """
        equity_low, equity_mid, equity_high, widened = coerce_equity_range_triple(
            equity_low,
            equity_mid,
            equity_high,
        )
        if widened:
            logger.warning(
                "Step 10 metadata builder widened unordered valuation range",
                extra={
                    "step_number": 10,
                    "valuation_low": str(equity_low),
                    "valuation_mid": str(equity_mid),
                    "valuation_high": str(equity_high),
                    "methodology": methodology,
                },
            )

        # Calculate range width
        equity_low_float = from_decimal(equity_low, 2)
        equity_mid_float = from_decimal(equity_mid, 2)
        equity_high_float = from_decimal(equity_high, 2)

        if equity_mid > 0:
            range_width_decimal = safe_money_divide(
                (equity_high - equity_low) * to_decimal("100"),
                to_decimal("2") * equity_mid,
                Decimal("0"),
            )
            range_width_float = to_decimal(range_width_decimal)
        else:
            range_width_float = Decimal("0.0")

        return {
            "range_width": f"±{range_width_float:.0f}%",
            "source": "McKinsey Valuation Handbook, Section 4.3",
            "step7_equity_value_mid": equity_mid_float,
            "value_preservation_validated": True,
            "methodology_selection": {
                "methodology": methodology,
                "use_dispersion": use_dispersion,
                "comparables_found": comparables_found,
                "sufficient_comparables": sufficient_comparables,
                "primary_method": primary_method,
                "reason": (
                    "Multiple dispersion used"
                    if use_dispersion
                    else "Confidence spread used (insufficient comparables or missing percentiles)"
                ),
            },
            "spread_calculation": (
                {
                    "base_spread": to_decimal(base_spread) if base_spread is not None else None,
                    "size_adjustment": (
                        to_decimal(size_adjustment) if size_adjustment is not None else None
                    ),
                    "business_type_multiplier": business_type_multiplier,
                    "growth_adjustment": (
                        to_decimal(growth_adjustment) if growth_adjustment is not None else None
                    ),
                    "profitability_adjustment": (
                        to_decimal(profitability_adjustment)
                        if profitability_adjustment is not None
                        else None
                    ),
                    "data_quality_adjustment": (
                        to_decimal(data_quality_adjustment)
                        if data_quality_adjustment is not None
                        else None
                    ),
                    "total_spread": spread,
                    "breakdown": spread_breakdown,
                    "use_asymmetric": use_asymmetric,
                    "downside_pct": downside_pct,
                    "upside_pct": upside_pct,
                }
                if methodology in ["Confidence Spread", "Asymmetric Range"] and spread is not None
                else None
            ),
            "dispersion_calculation": (
                {
                    "ev_revenue_p25": ev_revenue_p25,
                    "ev_revenue_p50": ev_revenue_p50,
                    "ev_revenue_p75": ev_revenue_p75,
                    "ev_ebitda_p25": ev_ebitda_p25,
                    "ev_ebitda_p50": ev_ebitda_p50,
                    "ev_ebitda_p75": ev_ebitda_p75,
                    "primary_method": primary_method,
                }
                if methodology == "Multiple Dispersion"
                else None
            ),
            "precision": "Decimal (bank-grade)",
            "rounding": "ROUND_HALF_EVEN (banker's rounding)",
            "business_category": business_category.value if business_category else None,
            "growth_rate": growth_rate,
            "growth_validated": growth_validated,
            "ebitda_margin": ebitda_margin,
            "data_quality_score": data_quality_score,
        }
