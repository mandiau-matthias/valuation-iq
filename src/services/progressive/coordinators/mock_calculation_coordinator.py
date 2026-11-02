"""
Mock Calculation Coordinator

Coordinates mock calculations for development and testing purposes.
"""

from decimal import Decimal
import logging
from typing import Any, Dict, Tuple

from src.utils.decimal_helpers import to_decimal, from_decimal

logger = logging.getLogger(__name__)


class MockCalculationCoordinator:
    """
    Coordinates mock calculations for progressive valuation service.
    Used when real calculation services are unavailable.
    """

    def __init__(self) -> None:
        """Initialize the mock calculation coordinator."""
        self.logger = logger

    def get_industry_multiples_mock(self, industry: str) -> Tuple[Decimal, Decimal]:
        """
        Get mock industry multiples.

        Args:
            industry: Industry name

        Returns:
            Tuple of (low_multiple, high_multiple)
        """
        multiples_map = {
            "technology": (Decimal("2.5"), Decimal("4.5")),
            "manufacturing": (Decimal("1.5"), Decimal("3.0")),
            "retail": (Decimal("1.0"), Decimal("2.5")),
            "services": (Decimal("1.2"), Decimal("2.8")),
            "healthcare": (Decimal("2.0"), Decimal("4.0")),
            "default": (Decimal("1.5"), Decimal("3.0")),
        }
        return multiples_map.get(industry.lower(), multiples_map["default"])

    def calculate_mock_dcf(
        self, revenue: Decimal, ebitda: Decimal, growth_rate: Decimal
    ) -> Dict[str, Any]:
        """
        Calculate mock DCF valuation.

        Args:
            revenue: Revenue amount
            ebitda: EBITDA amount
            growth_rate: Growth rate

        Returns:
            Dictionary with DCF calculation results
        """
        # Convert inputs to Decimal for precision
        revenue_decimal = to_decimal(revenue)
        ebitda_decimal = to_decimal(ebitda)
        growth_rate_decimal = to_decimal(growth_rate)
        terminal_growth_decimal = Decimal("0.02")
        discount_rate_decimal = Decimal("0.10")

        # Project cash flows
        cash_flows_decimal = []
        for year in range(1, 6):
            year_decimal = Decimal(str(year))
            growth_factor_decimal = (Decimal("1") + growth_rate_decimal) ** year_decimal
            projected_ebitda_decimal = ebitda_decimal * growth_factor_decimal
            cash_flow_decimal = projected_ebitda_decimal * Decimal(
                "0.8"
            )  # Assume 80% cash conversion
            discount_factor_decimal = (Decimal("1") + discount_rate_decimal) ** year_decimal
            cash_flow_pv_decimal = cash_flow_decimal / discount_factor_decimal
            cash_flows_decimal.append(cash_flow_pv_decimal)

        # Terminal value
        terminal_value_numerator_decimal = cash_flows_decimal[-1] * (
            Decimal("1") + terminal_growth_decimal
        )
        terminal_value_denominator_decimal = discount_rate_decimal - terminal_growth_decimal
        if terminal_value_denominator_decimal > Decimal("0"):
            terminal_value_decimal = (
                terminal_value_numerator_decimal / terminal_value_denominator_decimal
            )
        else:
            terminal_value_decimal = Decimal("0")
        terminal_discount_factor_decimal = (Decimal("1") + discount_rate_decimal) ** Decimal("5")
        terminal_value_pv_decimal = terminal_value_decimal / terminal_discount_factor_decimal

        # Total DCF value
        dcf_value_decimal = sum(cash_flows_decimal) + terminal_value_pv_decimal
        dcf_value = from_decimal(dcf_value_decimal)

        return {
            "value_low": from_decimal(dcf_value_decimal * Decimal("0.85")),
            "value_mid": dcf_value,
            "value_high": from_decimal(dcf_value_decimal * Decimal("1.15")),
            "discount_rate": from_decimal(discount_rate_decimal),
            "terminal_growth": from_decimal(terminal_growth_decimal),
            "projected_cash_flows": [from_decimal(cf) for cf in cash_flows_decimal],
        }

    def calculate_mock_multiples(
        self, revenue: Decimal, ebitda: Decimal, industry: str
    ) -> Dict[str, Any]:
        """
        Calculate mock multiples valuation.

        Args:
            revenue: Revenue amount
            ebitda: EBITDA amount
            industry: Industry name

        Returns:
            Dictionary with multiples calculation results
        """
        multiple_low, multiple_high = self.get_industry_multiples_mock(industry)
        multiple_low_decimal = to_decimal(multiple_low)
        multiple_high_decimal = to_decimal(multiple_high)
        revenue_decimal = to_decimal(revenue)
        ebitda_decimal = to_decimal(ebitda)

        # Revenue multiple
        avg_multiple_decimal = (multiple_low_decimal + multiple_high_decimal) / Decimal("2")
        revenue_value_decimal = revenue_decimal * avg_multiple_decimal

        # EBITDA multiple (assume 8-12x)
        ebitda_multiple_decimal = Decimal("10.0")
        ebitda_value_decimal = ebitda_decimal * ebitda_multiple_decimal

        # Average of both methods
        avg_value_decimal = (revenue_value_decimal + ebitda_value_decimal) / Decimal("2")

        return {
            "value_low": from_decimal(avg_value_decimal * Decimal("0.85")),
            "value_mid": from_decimal(avg_value_decimal),
            "value_high": from_decimal(avg_value_decimal * Decimal("1.15")),
            "revenue_multiple": from_decimal(avg_multiple_decimal),
            "ebitda_multiple": from_decimal(ebitda_multiple_decimal),
        }

    def calculate_mock_full_dcf(
        self,
        revenue: Decimal,
        ebitda: Decimal,
        growth_rate: Decimal,
        total_assets: Decimal,
        total_debt: Decimal,
        cash: Decimal,
    ) -> Dict[str, Any]:
        """
        Calculate mock full DCF with asset adjustments.

        Args:
            revenue: Revenue amount
            ebitda: EBITDA amount
            growth_rate: Growth rate
            total_assets: Total assets
            total_debt: Total debt
            cash: Cash amount

        Returns:
            Dictionary with full DCF calculation results
        """
        # Use the simplified DCF as base
        dcf_data = self.calculate_mock_dcf(revenue, ebitda, growth_rate)

        # Add asset-based adjustments
        total_assets_decimal = to_decimal(total_assets)
        total_debt_decimal = to_decimal(total_debt)
        cash_decimal = to_decimal(cash)
        net_assets_decimal = total_assets_decimal - total_debt_decimal
        asset_value_decimal = net_assets_decimal + cash_decimal

        # Blend DCF with asset value
        dcf_value_mid_decimal = to_decimal(dcf_data["value_mid"])
        blended_value_decimal = (dcf_value_mid_decimal * Decimal("0.7")) + (
            asset_value_decimal * Decimal("0.3")
        )

        return {
            "value_low": from_decimal(blended_value_decimal * Decimal("0.85")),
            "value_mid": from_decimal(blended_value_decimal),
            "value_high": from_decimal(blended_value_decimal * Decimal("1.15")),
            "asset_value": from_decimal(asset_value_decimal),
            "net_assets": from_decimal(net_assets_decimal),
            "cash": from_decimal(cash_decimal),
        }

    def calculate_mock_adjustments(
        self,
        revenue: Decimal,
        ebitda: Decimal,
        industry: str,
        total_assets: Decimal,
        total_debt: Decimal,
    ) -> Dict[str, Any]:
        """
        Calculate mock adjustments for size and liquidity.

        Args:
            revenue: Revenue amount
            ebitda: EBITDA amount
            industry: Industry name
            total_assets: Total assets
            total_debt: Total debt

        Returns:
            Dictionary with adjustment factors and risk factors
        """
        revenue_decimal = to_decimal(revenue)
        total_assets_decimal = to_decimal(total_assets)
        total_debt_decimal = to_decimal(total_debt)

        # Size adjustment based on revenue
        if revenue_decimal < Decimal("1000000"):
            size_adjustment_decimal = Decimal("-0.20")  # 20% discount for small companies
        elif revenue_decimal < Decimal("5000000"):
            size_adjustment_decimal = Decimal("-0.10")  # 10% discount for medium companies
        else:
            size_adjustment_decimal = Decimal("0.0")  # No discount for large companies

        # Liquidity adjustment based on debt ratio
        if total_assets_decimal > Decimal("0"):
            debt_ratio_decimal = total_debt_decimal / total_assets_decimal
        else:
            debt_ratio_decimal = Decimal("0")

        if debt_ratio_decimal > Decimal("0.5"):
            liquidity_adjustment_decimal = Decimal("-0.15")  # 15% discount for high debt
        elif debt_ratio_decimal > Decimal("0.3"):
            liquidity_adjustment_decimal = Decimal("-0.05")  # 5% discount for medium debt
        else:
            liquidity_adjustment_decimal = Decimal("0.0")  # No discount for low debt

        return {
            "size_adjustment": from_decimal(size_adjustment_decimal),
            "liquidity_adjustment": from_decimal(liquidity_adjustment_decimal),
            "risk_factors": ["Market volatility", "Industry competition", "Economic conditions"],
        }

    def calculate_mock_owner_analysis(self, owner_profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate mock owner dependency analysis.

        Args:
            owner_profile: Dictionary with owner profile data

        Returns:
            Dictionary with owner analysis results
        """
        # Calculate dependency score based on owner profile
        hours_per_week = owner_profile.get("hours_per_week", 40)
        delegation_capability = owner_profile.get("delegation_capability", 5)

        # Higher hours + lower delegation = higher dependency
        dependency_score = (hours_per_week / 40) * (10 - delegation_capability) / 10

        # Owner adjustment: -40% to 0% based on dependency
        owner_adjustment = -Decimal("0.4") * dependency_score

        return {
            "dependency_score": dependency_score,
            "owner_adjustment": owner_adjustment,
            "transferability_risk": (
                "High"
                if dependency_score > Decimal("0.7")
                else "Medium" if dependency_score > Decimal("0.4") else "Low"
            ),
            "succession_readiness": (
                "Low"
                if dependency_score > Decimal("0.7")
                else "Medium" if dependency_score > Decimal("0.4") else "High"
            ),
        }

    def calculate_mock_final_valuation(
        self, data: Dict[str, Any], owner_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate mock final valuation with owner factor.

        Args:
            data: Dictionary with valuation data
            owner_analysis: Dictionary with owner analysis results

        Returns:
            Dictionary with final valuation results
        """
        # Get base valuation from Phase 3
        base_value = 1_000_000  # Mock base value

        # Apply owner adjustment
        owner_adjustment = owner_analysis.get("owner_adjustment", 0)
        final_value = base_value * (1 + owner_adjustment)

        return {
            "value_low": final_value * Decimal("0.85"),
            "value_mid": final_value,
            "value_high": final_value * Decimal("1.15"),
            "owner_adjustment": owner_adjustment,
            "confidence_score": Decimal("90.0"),
        }
