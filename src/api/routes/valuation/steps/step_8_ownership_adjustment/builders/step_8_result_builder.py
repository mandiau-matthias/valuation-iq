"""
Step 8 Result Builder

Builds result dictionaries and metadata for Step 8.
"""

from decimal import Decimal
from typing import Any, Dict

from src.utils.decimal_helpers import from_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class Step8ResultBuilder:
    """Builds result dictionaries and metadata for Step 8."""

    def __init__(self, step_name: str):
        """
        Initialize the result builder.

        Args:
            step_name: Step name for StepOutput
        """
        self.step_name = step_name

    def build_result_dict(
        self,
        adjusted_equity_low_float: Decimal,
        adjusted_equity_mid_float: Decimal,
        adjusted_equity_high_float: Decimal,
        equity_low_float: Decimal,
        equity_mid_float: Decimal,
        equity_high_float: Decimal,
        shares_for_sale: Decimal,
        adjustment_type: str,
        adjustment_percentage: Decimal,
        adjustment_factor: Decimal,
        ownership_multiplier: Decimal,
    ) -> Dict[str, Any]:
        """
        Build comprehensive result dictionary.

        Args:
            adjusted_equity_low_float: Adjusted equity low value
            adjusted_equity_mid_float: Adjusted equity mid value
            adjusted_equity_high_float: Adjusted equity high value
            equity_low_float: Original equity low value
            equity_mid_float: Original equity mid value
            equity_high_float: Original equity high value
            shares_for_sale: Shares for sale percentage
            adjustment_type: Adjustment type
            adjustment_percentage: Adjustment percentage
            adjustment_factor: Adjustment factor
            ownership_multiplier: Ownership multiplier

        Returns:
            Result dictionary
        """
        return {
            "ownership_adjusted_equity_low": adjusted_equity_low_float,
            "ownership_adjusted_equity_mid": adjusted_equity_mid_float,
            "ownership_adjusted_equity_high": adjusted_equity_high_float,
            "equity_value_low": equity_low_float,  # Original equity (for reference)
            "equity_value_mid": equity_mid_float,  # Original equity (for reference)
            "equity_value_high": equity_high_float,  # Original equity (for reference)
            "ownership_percentage": shares_for_sale,
            "adjustment_type": adjustment_type,
            "adjustment_percentage": adjustment_percentage,
            "adjustment_factor": adjustment_factor,
            "ownership_multiplier": ownership_multiplier,
        }

    def build_metadata_dict(
        self,
        equity_low_float: Decimal,
        equity_mid_float: Decimal,
        equity_high_float: Decimal,
        adjusted_equity_low_float: Decimal,
        adjusted_equity_mid_float: Decimal,
        adjusted_equity_high_float: Decimal,
        shares_for_sale: Decimal,
        ownership_percentage: Decimal,
        ownership_multiplier: Decimal,
        adjustment_type: str,
        adjustment_percentage: Decimal,
        adjustment_factor: Decimal,
        adjustment_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Build metadata dictionary.

        Args:
            equity_low_float: Original equity low value
            equity_mid_float: Original equity mid value
            equity_high_float: Original equity high value
            adjusted_equity_low_float: Adjusted equity low value
            adjusted_equity_mid_float: Adjusted equity mid value
            adjusted_equity_high_float: Adjusted equity high value
            shares_for_sale: Shares for sale percentage
            ownership_percentage: Ownership percentage
            ownership_multiplier: Ownership multiplier
            adjustment_type: Adjustment type
            adjustment_percentage: Adjustment percentage
            adjustment_factor: Adjustment factor
            adjustment_result: Full adjustment result dictionary

        Returns:
            Metadata dictionary
        """
        return {
            "formula": "Adjusted Equity = Equity × Ownership % × (1 + Adjustment)",
            "ownership_percentage": shares_for_sale,
            "ownership_multiplier": ownership_multiplier,
            "adjustment_type": adjustment_type,
            "adjustment_percentage": adjustment_percentage,
            "adjustment_factor": adjustment_factor,
            "base_adjustment": adjustment_result["base_adjustment"],
            "base_adjustment_pct": adjustment_result["base_adjustment_pct"],
            "business_type_multiplier": adjustment_result["business_type_multiplier"],
            "revenue_multiplier": adjustment_result["revenue_multiplier"],
            "rationale": adjustment_result["rationale"],
            "tier_description": adjustment_result["tier_description"],
            "calculation_low": f"{equity_low_float:,.0f} × {ownership_percentage:.2%} × {adjustment_factor:.4f} = {adjusted_equity_low_float:,.0f}",
            "calculation_mid": f"{equity_mid_float:,.0f} × {ownership_percentage:.2%} × {adjustment_factor:.4f} = {adjusted_equity_mid_float:,.0f}",
            "calculation_high": f"{equity_high_float:,.0f} × {ownership_percentage:.2%} × {adjustment_factor:.4f} = {adjusted_equity_high_float:,.0f}",
            "equity_low_before": equity_low_float,
            "equity_mid_before": equity_mid_float,
            "equity_high_before": equity_high_float,
            "equity_low_after": adjusted_equity_low_float,
            "equity_mid_after": adjusted_equity_mid_float,
            "equity_high_after": adjusted_equity_high_float,
            "note": f"Ownership adjustment applied: {adjustment_type} of {adjustment_percentage:.2f}% "
            f'({adjustment_result["tier_description"]}). '
            f'Business-type calibration: {adjustment_result["business_type_multiplier"]:.2f}x, '
            f'Revenue calibration: {adjustment_result["revenue_multiplier"]:.2f}x.',
            "source": "McKinsey Valuation (2015), Chapter Decimal('8.3'): Ownership Adjustments; "
            "Bain Private Equity Guide (2020), Chapter 5: Ownership Structures; "
            "Mergerstat Review (2020): Control Premiums; "
            "Pratt & Niculita (2008): Minority Discounts",
            "precision": "Decimal (bank-grade)",
            "rounding": "ROUND_HALF_EVEN (banker's rounding)",
        }
