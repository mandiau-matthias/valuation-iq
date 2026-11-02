"""
Step 8 Adjustment Calculator

Calculates ownership adjustments and applies them to equity values.
"""

from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from src.api.routes.valuation.triage.business_type_triage import BusinessTypeTriageEngine
from src.domain.control_minority_adjuster import ControlMinorityAdjuster
from src.utils.core.data_extraction_helpers import (
    extract_owner_employee_counts_from_request,
    extract_revenue_from_request,
)
from src.utils.decimal_helpers import bank_round, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class Step8AdjustmentCalculator:
    """Calculates ownership adjustments for Step 8."""

    def __init__(self, business_types_repo: Optional[object] = None):
        """
        Initialize the adjustment calculator.

        Args:
            business_types_repo: Business types repository (optional)
        """
        self.business_type_triage = BusinessTypeTriageEngine()
        self.ownership_adjuster = ControlMinorityAdjuster(business_types_repo=business_types_repo)

    def extract_equity_values(
        self, step7_result: Dict[str, Any]
    ) -> Tuple[Decimal, Decimal, Decimal]:
        """
        Extract equity values from Step 7 result.

        Args:
            step7_result: Step 7 result dictionary

        Returns:
            Tuple of (equity_low, equity_mid, equity_high)
        """
        equity_low = to_decimal(step7_result.get("equity_value_low", 0))
        equity_mid = to_decimal(step7_result.get("equity_value_mid", 0))
        equity_high = to_decimal(step7_result.get("equity_value_high", 0))

        return equity_low, equity_mid, equity_high

    def extract_ownership_data(self, request: any) -> Dict[str, Any]:
        """
        Extract ownership data from request.

        Args:
            request: Valuation request

        Returns:
            Dictionary with ownership data
        """
        shares_for_sale = getattr(request, "shares_for_sale", None)
        if shares_for_sale is None:
            shares_for_sale = Decimal("100.0")
        # Use unified utility for owner extraction
        number_of_owners, _ = extract_owner_employee_counts_from_request(request)
        business_type_id = getattr(request, "business_type_id", None)

        # Extract revenue for revenue-based adjustments using unified utility
        revenue_decimal = extract_revenue_from_request(request)
        revenue = to_decimal(revenue_decimal) if revenue_decimal is not None else None

        return {
            "shares_for_sale": shares_for_sale,
            "number_of_owners": number_of_owners,
            "business_type_id": business_type_id,
            "revenue": revenue,
        }

    def calculate_adjustment(
        self,
        shares_for_sale: Decimal,
        business_type_id: Optional[int],
        revenue: Optional[Decimal],
        number_of_owners: Optional[int],
        request: any,
    ) -> Dict[str, Any]:
        """
        Calculate ownership adjustment using domain class.

        Args:
            shares_for_sale: Percentage of shares for sale
            business_type_id: Business type ID
            revenue: Revenue value (optional)
            number_of_owners: Number of owners (optional)
            request: Valuation request

        Returns:
            Dictionary with adjustment details
        """
        # Get business category for calibration
        business_category = self.business_type_triage.get_business_type_category(
            business_type_id=business_type_id,
            business_model=getattr(request, "business_model", None),
            industry=getattr(request, "industry", None),
            category_id=getattr(request, "category_id", None),
        )

        logger.info(
            "🔍 Calculating ownership adjustment",
            extra={
                "step_number": 8,
                "shares_for_sale_pct": shares_for_sale,
                "business_type_id": business_type_id,
                "business_category": business_category.value if business_category else None,
                "revenue": to_decimal(revenue) if revenue is not None else None,
                "number_of_owners": number_of_owners,
                "adjuster_class": self.ownership_adjuster.__class__.__name__,
            },
        )

        valuation_preferences = getattr(request, "valuation_preferences", None)
        adjustment_result = self.ownership_adjuster.calculate_ownership_adjustment(
            shares_for_sale=shares_for_sale,
            business_type_id=business_type_id,
            revenue=revenue,
            number_of_owners=number_of_owners,
            business_category=business_category,
            valuation_preferences=valuation_preferences,
        )

        logger.info(
            "✅ Ownership adjustment calculated",
            extra={
                "step_number": 8,
                "adjustment_type": adjustment_result["adjustment_type"],
                "adjustment_factor": adjustment_result["adjustment_factor"],
                "adjustment_percentage": adjustment_result.get("adjustment_percentage", 0),
                "tier_selected": adjustment_result.get("tier", "N/A"),
                "business_type_calibration": adjustment_result.get("business_type_calibration", {}),
                "revenue_adjustment": adjustment_result.get("revenue_adjustment", {}),
                "formula_explanation": f'{adjustment_result["adjustment_type"]} of {adjustment_result.get("adjustment_percentage", 0)}% applied',
            },
        )

        return adjustment_result

    def apply_adjustments(
        self,
        equity_low: Decimal,
        equity_mid: Decimal,
        equity_high: Decimal,
        ownership_percentage: Decimal,
        adjustment_factor: Decimal,
    ) -> Tuple[Decimal, Decimal, Decimal]:
        """
        Apply ownership adjustments to equity values.

        Args:
            equity_low: Equity low value
            equity_mid: Equity mid value
            equity_high: Equity high value
            ownership_percentage: Ownership percentage (0-100)
            adjustment_factor: Adjustment factor

        Returns:
            Tuple of (adjusted_equity_low, adjusted_equity_mid, adjusted_equity_high)
        """
        ownership_multiplier = to_decimal(str(ownership_percentage / Decimal("100.0")))

        logger.info(
            "🧮 Applying ownership adjustment to equity values",
            extra={
                "step_number": 8,
                "formula": "Adjusted Equity = Equity × (Shares % / 100) × (1 + Adjustment %)",
                "ownership_percentage": ownership_percentage,
                "ownership_multiplier": to_decimal(ownership_multiplier),
                "adjustment_factor": to_decimal(adjustment_factor),
                "calculation_breakdown": {
                    "equity_mid": to_decimal(equity_mid),
                    "ownership_multiplier": to_decimal(ownership_multiplier),
                    "adjustment_factor": to_decimal(adjustment_factor),
                    "intermediate": to_decimal(equity_mid * ownership_multiplier),
                    "final": to_decimal(equity_mid * ownership_multiplier * adjustment_factor),
                },
            },
        )

        # Apply adjustments: Adjusted Equity = Equity × Ownership % × Adjustment Factor
        adjusted_equity_low = equity_low * ownership_multiplier * adjustment_factor
        adjusted_equity_mid = equity_mid * ownership_multiplier * adjustment_factor
        adjusted_equity_high = equity_high * ownership_multiplier * adjustment_factor

        logger.debug(
            "🧮 Ownership-adjusted equity values calculated (before rounding)",
            extra={
                "step_number": 8,
                "equity_low_before": to_decimal(equity_low),
                "equity_mid_before": to_decimal(equity_mid),
                "equity_high_before": to_decimal(equity_high),
                "adjusted_equity_low_raw": to_decimal(adjusted_equity_low),
                "adjusted_equity_mid_raw": to_decimal(adjusted_equity_mid),
                "adjusted_equity_high_raw": to_decimal(adjusted_equity_high),
                "calculation_low": f"{to_decimal(equity_low):,.0f} × {to_decimal(ownership_multiplier):.4f} × {to_decimal(adjustment_factor):.4f} = {to_decimal(adjusted_equity_low):,.0f}",
                "calculation_mid": f"{to_decimal(equity_mid):,.0f} × {to_decimal(ownership_multiplier):.4f} × {to_decimal(adjustment_factor):.4f} = {to_decimal(adjusted_equity_mid):,.0f}",
                "calculation_high": f"{to_decimal(equity_high):,.0f} × {to_decimal(ownership_multiplier):.4f} × {to_decimal(adjustment_factor):.4f} = {to_decimal(adjusted_equity_high):,.0f}",
            },
        )

        # Floor at 0 (negative equity not allowed after ownership adjustment)
        adjusted_equity_low = max(to_decimal("0"), adjusted_equity_low)
        adjusted_equity_mid = max(to_decimal("0"), adjusted_equity_mid)
        adjusted_equity_high = max(to_decimal("0"), adjusted_equity_high)

        # Round to 2 decimal places for currency precision
        adjusted_equity_low = bank_round(adjusted_equity_low, 2)
        adjusted_equity_mid = bank_round(adjusted_equity_mid, 2)
        adjusted_equity_high = bank_round(adjusted_equity_high, 2)

        return adjusted_equity_low, adjusted_equity_mid, adjusted_equity_high
