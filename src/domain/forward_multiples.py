"""Legacy forward-multiple heuristic prototype.

This module is not the authoritative prognose-cone engine. BET-640 routes
production forward valuation through `forward_method_registry` plus
method-specific adapters so every horizon is re-gated by evidence, pricing
inputs, uncertainty, and valuation-date convention before any blend is drawn.
"""

from src.errors.error_types import MarketDataError
from src.utils.exceptions import CalculationError, MultiplesCalculationError

"""
Forward Multiples Engine

Forward-looking multiples with predictive analytics.
Based on Valuation_Trends_2026.md research requirements.

Features:
- Project future multiples based on growth trajectory
- Market cycle positioning
- Competitive dynamics analysis
- Growth-adjusted multiple calculation

Author: Senior CTO
Version: 1.0.0
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MarketConditions:
    """Market conditions for forward multiple calculation."""

    market_cycle: str  # "expansion", "peak", "contraction", "trough"
    interest_rates: Decimal  # Current interest rate environment
    market_sentiment: Decimal  # Decimal('0.0') to Decimal('1.0') (bearish to bullish)
    sector_performance: Decimal  # Sector performance vs market


@dataclass
class CompanyMetrics:
    """Company metrics for forward multiple calculation."""

    current_revenue: Decimal
    projected_growth_rate: Decimal
    current_margin: Decimal
    margin_trend: Decimal  # Margin expansion/contraction rate
    market_share: Optional[Decimal] = None
    competitive_position: Optional[str] = None  # "leader", "challenger", "follower"


class ForwardMultiplesEngine:
    """
    Forward-looking multiples with predictive analytics.

    Adjusts current multiples based on:
    - Projected growth rates
    - Margin expansion/contraction
    - Market cycle positioning
    - Competitive dynamics
    """

    def __init__(self):
        """Initialize Forward Multiples Engine."""
        self.logger = get_logger(__name__)

        # Growth-multiple relationship coefficients
        self.growth_multiple_coefficients = {
            "revenue": {
                "intercept": Decimal("1.0"),
                "growth_coef": Decimal("0.3"),
                "margin_coef": 0.2,
            },
            "ebitda": {
                "intercept": Decimal("1.0"),
                "growth_coef": Decimal("0.4"),
                "margin_coef": 0.3,
            },
        }

        # Market cycle adjustments
        self.market_cycle_adjustments = {
            "expansion": Decimal("1.1"),  # 10% premium
            "peak": Decimal("1.0"),  # No adjustment
            "contraction": Decimal("0.85"),  # 15% discount
            "trough": Decimal("0.9"),  # 10% discount
        }

    def calculate_forward_multiple(
        self,
        current_multiple: Decimal,
        growth_rate: Decimal,
        margin_trend: Decimal,
        years_forward: int = 1,
        market_conditions: Optional[MarketConditions] = None,
        company_metrics: Optional[CompanyMetrics] = None,
    ) -> Decimal:
        """
        Project multiple forward based on growth trajectory.

        Research basis: High-growth companies command premium multiples
        Example: 50% growth → 1.3x current multiple
                 10% growth → 0.9x current multiple

        Args:
            current_multiple: Current market multiple
            growth_rate: Projected growth rate (annual)
            margin_trend: Margin expansion/contraction rate
            years_forward: Number of years to project forward
            market_conditions: Market conditions (optional)
            company_metrics: Company-specific metrics (optional)

        Returns:
            Forward-adjusted multiple
        """
        try:
            # Base forward multiple calculation
            forward_multiple = self._calculate_base_forward_multiple(
                current_multiple, growth_rate, margin_trend, years_forward
            )

            # Apply market cycle adjustments
            if market_conditions:
                forward_multiple = self._apply_market_cycle_adjustment(
                    forward_multiple, market_conditions
                )

            # Apply company-specific adjustments
            if company_metrics:
                forward_multiple = self._apply_company_adjustments(
                    forward_multiple, company_metrics
                )

            # Apply bounds to prevent extreme values
            forward_multiple = max(Decimal("0.1"), min(Decimal("10.0"), forward_multiple))

            self.logger.info(
                f"Forward multiple calculated",
                current_multiple=current_multiple,
                forward_multiple=forward_multiple,
                growth_rate=growth_rate,
                years_forward=years_forward,
            )

            return forward_multiple

        except MultiplesCalculationError as e:
            self.logger.error(f"Error calculating forward multiple: {e}")
            return current_multiple  # Fallback to current multiple

    def _calculate_base_forward_multiple(
        self,
        current_multiple: Decimal,
        growth_rate: Decimal,
        margin_trend: Decimal,
        years_forward: int,
    ) -> Decimal:
        """Calculate base forward multiple using growth and margin trends."""
        try:
            # Convert to Decimal for calculations
            growth_rate_decimal = to_decimal(str(growth_rate))
            margin_trend_decimal = to_decimal(str(margin_trend))
            years_forward_decimal = to_decimal(str(years_forward))
            current_multiple_decimal = to_decimal(str(current_multiple))

            # Growth adjustment factor
            # High growth companies get premium multiples
            if growth_rate > 0.3:  # >30% growth
                # Formula: 1.0 + (growth_rate - 0.1) * 0.5
                growth_factor = to_decimal("1.0") + (
                    growth_rate_decimal - to_decimal("0.1")
                ) * to_decimal("0.5")
            elif growth_rate > 0.1:  # 10-30% growth
                # Formula: 1.0 + (growth_rate - 0.1) * 0.3
                growth_factor = to_decimal("1.0") + (
                    growth_rate_decimal - to_decimal("0.1")
                ) * to_decimal("0.3")
            else:  # <10% growth
                # Formula: 0.9 + growth_rate * 1.0
                growth_factor = to_decimal("0.9") + growth_rate_decimal * to_decimal("1.0")

            # Margin trend adjustment
            # Expanding margins get premium, contracting margins get discount
            # Formula: 1.0 + margin_trend * 0.2
            margin_factor = to_decimal("1.0") + margin_trend_decimal * to_decimal("0.2")

            # Time decay factor (multiples tend to converge over time)
            # Formula: 1.0 - (years_forward - 1) * 0.05
            time_factor = to_decimal("1.0") - (
                years_forward_decimal - to_decimal("1")
            ) * to_decimal("0.05")

            # Combine factors using Decimal
            forward_multiple_decimal = (
                current_multiple_decimal * growth_factor * margin_factor * time_factor
            )

            return to_decimal(forward_multiple_decimal)

        except (ValueError, TypeError) as e:
            self.logger.error(
                f"Error calculating base forward multiple: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise CalculationError(
                f"Failed to calculate forward multiple: {e}",
                calculation_type="Forward Multiple",
                context={"current_multiple": current_multiple, "growth_rate": growth_rate},
            ) from e
        except MultiplesCalculationError as e:
            self.logger.error(
                f"Unexpected error calculating base forward multiple: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise MultiplesCalculationError(
                f"Unexpected error in base forward multiple calculation: {e}",
                step="base_forward_multiple",
                calculation_type="Forward Multiple",
                context={
                    "current_multiple": (
                        from_decimal(current_multiple) if "current_multiple" in locals() else None
                    ),
                    "growth_rate": from_decimal(growth_rate) if "growth_rate" in locals() else None,
                    "error_type": type(e).__name__,
                },
            ) from e

    def _apply_market_cycle_adjustment(
        self, forward_multiple: Decimal, market_conditions: MarketConditions
    ) -> Decimal:
        """Apply market cycle adjustments to forward multiple."""
        try:
            cycle_adjustment = self.market_cycle_adjustments.get(
                market_conditions.market_cycle, Decimal("1.0")
            )

            # Interest rate adjustment
            # Higher rates typically compress multiples
            interest_rate_adjustment = Decimal("1.0") - (
                market_conditions.interest_rates - Decimal("0.03")
            ) * Decimal("0.1")

            # Market sentiment adjustment
            sentiment_adjustment = Decimal("0.8") + market_conditions.market_sentiment * Decimal(
                "0.4"
            )

            # Sector performance adjustment
            sector_adjustment = Decimal("0.9") + market_conditions.sector_performance * Decimal(
                "0.2"
            )

            adjusted_multiple = (
                forward_multiple
                * cycle_adjustment
                * interest_rate_adjustment
                * sentiment_adjustment
                * sector_adjustment
            )

            return adjusted_multiple

        except (ValueError, TypeError) as e:
            self.logger.error(
                f"Error applying market cycle adjustment: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise CalculationError(
                f"Failed to apply market cycle adjustment: {e}",
                calculation_type="Forward Multiple",
                context={"forward_multiple": forward_multiple},
            ) from e
        except MultiplesCalculationError as e:
            self.logger.error(
                f"Unexpected error applying market cycle adjustment: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise MultiplesCalculationError(
                f"Unexpected error in market cycle adjustment: {e}",
                step="market_cycle_adjustment",
                calculation_type="Forward Multiple",
                context={
                    "forward_multiple": (
                        from_decimal(forward_multiple) if "forward_multiple" in locals() else None
                    ),
                    "error_type": type(e).__name__,
                },
            ) from e

    def _apply_company_adjustments(
        self, forward_multiple: Decimal, company_metrics: CompanyMetrics
    ) -> Decimal:
        """Apply company-specific adjustments to forward multiple."""
        try:
            # Market share adjustment
            market_share_factor = Decimal("1.0")
            if company_metrics.market_share is not None:
                if company_metrics.market_share > 0.2:  # >20% market share
                    market_share_factor = Decimal("1.1")  # Premium for market leaders
                elif company_metrics.market_share < 0.05:  # <5% market share
                    market_share_factor = Decimal("0.95")  # Discount for small players

            # Competitive position adjustment
            competitive_factor = Decimal("1.0")
            if company_metrics.competitive_position:
                if company_metrics.competitive_position == "leader":
                    competitive_factor = Decimal("1.15")  # 15% premium for leaders
                elif company_metrics.competitive_position == "challenger":
                    competitive_factor = Decimal("1.05")  # 5% premium for challengers
                elif company_metrics.competitive_position == "follower":
                    competitive_factor = Decimal("0.9")  # 10% discount for followers

            # Growth consistency adjustment
            # More consistent growth gets premium
            growth_consistency_factor = Decimal("1.0")
            if company_metrics.projected_growth_rate > 0.2:
                # High growth companies get additional premium if growth is sustainable
                growth_consistency_factor = Decimal("1.05")

            adjusted_multiple = (
                forward_multiple
                * market_share_factor
                * competitive_factor
                * growth_consistency_factor
            )

            return adjusted_multiple

        except (ValueError, TypeError) as e:
            self.logger.error(
                f"Error applying company adjustments: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise CalculationError(
                f"Failed to apply company adjustments: {e}",
                calculation_type="Forward Multiple",
                context={"forward_multiple": forward_multiple},
            ) from e
        except MultiplesCalculationError as e:
            self.logger.error(
                f"Unexpected error applying company adjustments: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise MultiplesCalculationError(
                f"Unexpected error in company adjustment: {e}",
                step="company_adjustment",
                calculation_type="Forward Multiple",
                context={
                    "forward_multiple": (
                        from_decimal(forward_multiple) if "forward_multiple" in locals() else None
                    ),
                    "error_type": type(e).__name__,
                },
            ) from e

    def calculate_industry_forward_multiples(
        self,
        industry: str,
        current_multiples: Dict[str, Decimal],
        market_conditions: MarketConditions,
    ) -> Dict[str, Decimal]:
        """
        Calculate forward multiples for an entire industry.

        Args:
            industry: Industry name
            current_multiples: Current industry multiples
            market_conditions: Market conditions

        Returns:
            Dict with forward-adjusted multiples
        """
        try:
            forward_multiples = {}

            # Industry-specific growth expectations
            industry_growth_expectations = {
                "technology": Decimal("0.15"),  # 15% expected growth
                "saas": Decimal("0.20"),  # 20% expected growth
                "software": Decimal("0.12"),  # 12% expected growth
                "services": Decimal("0.05"),  # 5% expected growth
                "manufacturing": Decimal("0.03"),  # 3% expected growth
                "retail": Decimal("0.02"),  # 2% expected growth
                "healthcare": Decimal("0.08"),  # 8% expected growth
                "pharma": Decimal("0.06"),  # 6% expected growth
                "biotech": Decimal("0.25"),  # 25% expected growth
                "default": Decimal("0.05"),  # 5% default
            }

            expected_growth = industry_growth_expectations.get(industry.lower(), Decimal("0.05"))

            # Calculate forward multiples for each metric
            for metric, current_multiple in current_multiples.items():
                if metric.lower() in ["revenue", "sales"]:
                    # Revenue multiples: growth-focused
                    forward_multiple = self.calculate_forward_multiple(
                        current_multiple=current_multiple,
                        growth_rate=expected_growth,
                        margin_trend=Decimal("0.0"),  # Neutral margin trend
                        years_forward=1,
                        market_conditions=market_conditions,
                    )
                elif metric.lower() in ["ebitda", "ebit"]:
                    # EBITDA multiples: profitability-focused
                    forward_multiple = self.calculate_forward_multiple(
                        current_multiple=current_multiple,
                        growth_rate=expected_growth
                        * Decimal("0.8"),  # Slightly lower growth expectation
                        margin_trend=Decimal("0.01"),  # Slight margin expansion
                        years_forward=1,
                        market_conditions=market_conditions,
                    )
                else:
                    # Other metrics: use default calculation
                    forward_multiple = self.calculate_forward_multiple(
                        current_multiple=current_multiple,
                        growth_rate=expected_growth,
                        margin_trend=Decimal("0.0"),
                        years_forward=1,
                        market_conditions=market_conditions,
                    )

                forward_multiples[metric] = forward_multiple

            return forward_multiples

        except MultiplesCalculationError as e:
            self.logger.error(f"Error calculating industry forward multiples: {e}")
            return current_multiples  # Fallback to current multiples

    def calculate_multiple_sensitivity(
        self, base_multiple: Decimal, growth_rate: Decimal, margin_trend: Decimal
    ) -> Dict[str, Dict[str, Decimal]]:
        """
        Calculate sensitivity of forward multiple to key parameters.

        Args:
            base_multiple: Base multiple
            growth_rate: Base growth rate
            margin_trend: Base margin trend

        Returns:
            Sensitivity analysis results
        """
        try:
            sensitivity_results = {}

            # Growth rate sensitivity
            growth_scenarios = [
                Decimal("0.0"),
                Decimal("0.1"),
                Decimal("0.2"),
                Decimal("0.3"),
                Decimal("0.5"),
            ]
            growth_sensitivity = {}
            for scenario_growth in growth_scenarios:
                forward_multiple = self.calculate_forward_multiple(
                    current_multiple=base_multiple,
                    growth_rate=scenario_growth,
                    margin_trend=margin_trend,
                    years_forward=1,
                )
                growth_sensitivity[f"{scenario_growth:.1%}"] = forward_multiple

            sensitivity_results["growth_rate"] = growth_sensitivity

            # Margin trend sensitivity
            margin_scenarios = [
                -Decimal("0.05"),
                -Decimal("0.02"),
                Decimal("0.0"),
                Decimal("0.02"),
                Decimal("0.05"),
            ]
            margin_sensitivity = {}
            for scenario_margin in margin_scenarios:
                forward_multiple = self.calculate_forward_multiple(
                    current_multiple=base_multiple,
                    growth_rate=growth_rate,
                    margin_trend=scenario_margin,
                    years_forward=1,
                )
                margin_sensitivity[f"{scenario_margin:+.1%}"] = forward_multiple

            sensitivity_results["margin_trend"] = margin_sensitivity

            # Time horizon sensitivity
            time_scenarios = [1, 2, 3, 5]
            time_sensitivity = {}
            for scenario_years in time_scenarios:
                forward_multiple = self.calculate_forward_multiple(
                    current_multiple=base_multiple,
                    growth_rate=growth_rate,
                    margin_trend=margin_trend,
                    years_forward=scenario_years,
                )
                time_sensitivity[f"{scenario_years}y"] = forward_multiple

            sensitivity_results["time_horizon"] = time_sensitivity

            return sensitivity_results

        except MultiplesCalculationError as e:
            self.logger.error(f"Error calculating multiple sensitivity: {e}")
            return {}

    def get_forward_multiple_rationale(
        self,
        current_multiple: Decimal,
        forward_multiple: Decimal,
        growth_rate: Decimal,
        margin_trend: Decimal,
        market_conditions: Optional[MarketConditions] = None,
    ) -> Dict[str, str]:
        """
        Get human-readable rationale for forward multiple calculation.

        Args:
            current_multiple: Original multiple
            forward_multiple: Calculated forward multiple
            growth_rate: Growth rate used
            margin_trend: Margin trend used
            market_conditions: Market conditions (optional)

        Returns:
            Dict with rationale explanations
        """
        try:
            rationale = {}

            # Growth rationale
            if growth_rate > 0.2:
                rationale["growth"] = (
                    f"High growth rate ({growth_rate:.1%}) commands premium multiple"
                )
            elif growth_rate > 0.1:
                rationale["growth"] = (
                    f"Moderate growth rate ({growth_rate:.1%}) supports current multiple"
                )
            else:
                rationale["growth"] = f"Low growth rate ({growth_rate:.1%}) may compress multiple"

            # Margin trend rationale
            if margin_trend > 0.02:
                rationale["margin"] = (
                    f"Margin expansion ({margin_trend:+.1%}) adds premium to multiple"
                )
            elif margin_trend < -0.02:
                rationale["margin"] = f"Margin contraction ({margin_trend:+.1%}) reduces multiple"
            else:
                rationale["margin"] = f"Stable margins ({margin_trend:+.1%}) maintain multiple"

            # Market conditions rationale
            if market_conditions:
                if market_conditions.market_cycle == "expansion":
                    rationale["market"] = "Expansionary market cycle supports higher multiples"
                elif market_conditions.market_cycle == "contraction":
                    rationale["market"] = "Contractionary market cycle compresses multiples"
                else:
                    rationale["market"] = (
                        f"Market cycle ({market_conditions.market_cycle}) has neutral impact"
                    )

            # Overall change rationale
            change_pct = (forward_multiple - current_multiple) / current_multiple * 100
            if change_pct > 5:
                rationale["overall"] = (
                    f"Forward multiple {change_pct:+.1f}% higher due to growth and market factors"
                )
            elif change_pct < -5:
                rationale["overall"] = (
                    f"Forward multiple {change_pct:+.1f}% lower due to growth and market factors"
                )
            else:
                rationale["overall"] = (
                    f"Forward multiple {change_pct:+.1f}% change - relatively stable"
                )

            return rationale

        except MultiplesCalculationError as e:
            self.logger.error(f"Error generating rationale: {e}")
            return {"error": "Unable to generate rationale"}
