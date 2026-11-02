from src.utils.exceptions import MultiplesCalculationError

"""
Step 2 Insights Generator

Generates market insights and context for valuation.
"""

from typing import Any, Dict

from src.api.routes.valuation.triage.business_type_triage import BusinessTypeCategory
from src.utils.valuation_logger import ValuationLogger


class Step2InsightsGenerator:
    """Generates market insights and context."""

    def __init__(self, logger: ValuationLogger):
        """
        Initialize the insights generator.

        Args:
            logger: Logger instance
        """
        self.logger = logger

    def generate_market_insights(
        self,
        request: Any,
        business_category: BusinessTypeCategory,
        comparables_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate market insights and context (Phase 5 - Basic implementation).

        This is a basic implementation. Full version will:
        - Fetch industry trends from APIs
        - Get economic indicators (OECD, ECB)
        - Calculate market adjustments
        - Provide regional context

        Args:
            request: The valuation request
            business_category: Business type category
            comparables_data: Comparable companies data

        Returns:
            Dict with market insights
        """
        insights = {
            "industry_trend": None,
            "market_conditions": None,
            "economic_context": None,
            "regional_adjustment": None,
        }

        # Basic insights based on comparables and business category
        if comparables_data.get("count", 0) > 0:
            insights["market_conditions"] = (
                f"Found {comparables_data['count']} comparable companies"
            )

        # Category-specific insights
        if business_category == BusinessTypeCategory.SAAS_SOFTWARE:
            insights["industry_trend"] = (
                "SaaS sector typically trades at higher multiples (10-15x EBITDA)"
            )
        elif business_category == BusinessTypeCategory.PROFESSIONAL_SERVICES:
            insights["industry_trend"] = (
                "Professional services focus on owner dependency and recurring revenue"
            )

        # Regional adjustment placeholder
        country_code = getattr(request, "country_code", "BE") or "BE"
        if country_code == "BE":
            insights["regional_adjustment"] = "Belgian market multiples may vary from EU average"

        return insights

    def generate_market_insights_safe(
        self,
        request: Any,
        business_category: BusinessTypeCategory,
        comparables_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Safe wrapper for generate_market_insights that never throws exceptions.

        CRITICAL FIX: This ensures market insights generation doesn't cause Step 2 to fail.

        Args:
            request: The valuation request
            business_category: Business type category
            comparables_data: Comparable companies data

        Returns:
            Dict with market insights (empty dict with error message if generation fails)
        """
        try:
            return self.generate_market_insights(request, business_category, comparables_data)
        except Exception as e:
            self.logger.warning(
                "⚠️ Step 2: Market insights generation failed, using empty insights",
                extra={"step_number": 2, "error_type": type(e).__name__, "error_message": str(e)},
            )
            return {
                "industry_trend": None,
                "market_conditions": None,
                "economic_context": None,
                "regional_adjustment": None,
                "error": f"Market insights generation failed: {str(e)}",
            }
