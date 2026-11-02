"""
Business Type Adjuster Module

Applies business type-specific adjustments to valuations.

RESPONSIBILITIES:
- Apply business type multipliers
- Handle industry-specific adjustments
- Calculate risk adjustments based on business characteristics

REFACTORING NOTE:
Extracted from valuation_orchestrator.py to isolate adjustment logic.
"""

from decimal import Decimal
from typing import Any, Dict

from src.errors import CalculationError, ValidationError
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

from ..valuation_types import BusinessType

logger = get_logger(__name__)


class BusinessTypeAdjuster:
    """
    Applies business type-specific valuation adjustments

    Features:
    - Business type multipliers
    - Industry adjustments
    - Risk-based adjustments
    """

    def __init__(self, business_rules: Dict[str, Any]):
        """
        Initialize business type adjuster

        Args:
            business_rules: Business rules configuration
        """
        self.logger = logger
        self.business_rules = business_rules
        self.logger.debug("✅ BusinessTypeAdjuster initialized")

    async def apply_adjustments(
        self, base_valuation: Decimal, business_type: BusinessType, industry: str
    ) -> Decimal:
        """
        Apply business type and industry adjustments

        Args:
            base_valuation: Base valuation amount
            business_type: Business type
            industry: Industry category

        Returns:
            Adjusted valuation amount
        """
        try:
            self.logger.info(
                "🎨 Applying business type adjustments",
                extra={
                    "base_valuation": base_valuation,
                    "business_type": (
                        business_type.value
                        if hasattr(business_type, "value")
                        else str(business_type)
                    ),
                    "industry": industry,
                },
            )

            # Get business type adjustment factor
            adjustment_factors = self.business_rules.get("business_type_adjustments", {})
            business_factor = adjustment_factors.get(
                getattr(business_type, "value", str(business_type)), Decimal("1.0")
            )

            self.logger.info(
                f"📊 Business type factor: {business_factor}",
                extra={
                    "business_type": (
                        business_type.value
                        if hasattr(business_type, "value")
                        else str(business_type)
                    ),
                    "factor": business_factor,
                },
            )

            # Get industry adjustment factor
            industry_adjustments = self.business_rules.get("industry_adjustments", {})
            industry_factor = industry_adjustments.get(industry, Decimal("1.0"))

            self.logger.info(
                f"📊 Industry factor: {industry_factor}",
                extra={"industry": industry, "factor": industry_factor},
            )

            # Calculate adjusted valuation
            adjusted_valuation = base_valuation * business_factor * industry_factor

            adjustment_percentage = (adjusted_valuation / base_valuation - 1) * 100

            self.logger.info(
                "✅ Adjustments applied",
                extra={
                    "base_valuation": base_valuation,
                    "adjusted_valuation": adjusted_valuation,
                    "business_factor": business_factor,
                    "industry_factor": industry_factor,
                    "total_adjustment_pct": f"{adjustment_percentage:+.1f}%",
                },
            )

            return adjusted_valuation

        except (CalculationError, ValidationError, ValueError, TypeError, AttributeError) as e:
            self.logger.error(
                "❌ Error applying adjustments",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "base_valuation": base_valuation,
                },
                exc_info=True,
            )

            # Return unadjusted value on error
            self.logger.warning("⚠️ Returning unadjusted valuation due to error")
            return base_valuation
