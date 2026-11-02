"""
Owner Compensation Adjuster

Adjusts owner compensation to market rate for replacement manager.
Academic Source: Trugman (2017, p. 287), Pratt & Niculita (2008)
"""

from decimal import Decimal
from typing import Dict, Optional, Tuple

from src.config.belgian_salary_benchmarks import INDUSTRY_MULTIPLIERS as _INDUSTRY_MULTIPLIERS
from src.config.belgian_salary_benchmarks import LOCATION_MULTIPLIERS as _LOCATION_MULTIPLIERS
from src.config.belgian_salary_benchmarks import MARKET_RATES_BY_REVENUE as _MARKET_RATES_BY_REVENUE
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class OwnerCompensationAdjuster:
    """
    Calculates owner compensation normalization adjustment.

    Formula: adjustment = owner_compensation - market_rate
    - Positive adjustment = add-back (owner overpaid)
    - Negative adjustment = subtract (owner underpaid, need replacement cost)
    """

    MARKET_RATES = _MARKET_RATES_BY_REVENUE
    INDUSTRY_MULTIPLIERS = _INDUSTRY_MULTIPLIERS
    LOCATION_MULTIPLIERS = _LOCATION_MULTIPLIERS

    def get_market_rate(
        self, revenue: Decimal, business_category: Optional[str] = None, location: str = "Belgium"
    ) -> Decimal:
        """
        Determine market rate for owner/CEO replacement.

        Args:
            revenue: Annual revenue
            business_category: Business category (construction, professional_services, etc.)
            location: Geographic location

        Returns:
            Market rate salary for replacement manager
        """
        # Determine base rate by revenue tier
        if revenue < Decimal("500000"):
            base_rate = self.MARKET_RATES["under_500k"]
            tier = "under_500k"
        elif revenue < Decimal("1000000"):
            base_rate = self.MARKET_RATES["500k_to_1m"]
            tier = "500k_to_1m"
        elif revenue < Decimal("2000000"):
            base_rate = self.MARKET_RATES["1m_to_2m"]
            tier = "1m_to_2m"
        elif revenue < Decimal("5000000"):
            base_rate = self.MARKET_RATES["2m_to_5m"]
            tier = "2m_to_5m"
        else:
            base_rate = self.MARKET_RATES["over_5m"]
            tier = "over_5m"

        # Apply industry multiplier
        industry_mult = self.INDUSTRY_MULTIPLIERS.get(
            business_category or "construction", Decimal("1.0")
        )

        # Apply location multiplier
        location_mult = self.LOCATION_MULTIPLIERS.get(location, Decimal("1.0"))

        market_rate = base_rate * industry_mult * location_mult

        logger.debug(
            "📊 Market rate determined for owner replacement",
            extra={
                "revenue": from_decimal(revenue),
                "tier": tier,
                "base_rate": from_decimal(base_rate),
                "business_category": business_category,
                "industry_multiplier": from_decimal(industry_mult),
                "location": location,
                "location_multiplier": from_decimal(location_mult),
                "final_market_rate": from_decimal(market_rate),
            },
        )

        return market_rate

    def calculate_adjustment(
        self,
        owner_compensation: Optional[Decimal],
        revenue: Decimal,
        business_category: Optional[str] = None,
        location: str = "Belgium",
    ) -> Tuple[Decimal, str, Dict]:
        """
        Calculate owner compensation normalization adjustment.

        Args:
            owner_compensation: Reported owner compensation (if provided)
            revenue: Annual revenue
            business_category: Business category
            location: Geographic location

        Returns:
            Tuple of (adjustment_amount, explanation, metadata)
        """
        market_rate = self.get_market_rate(revenue, business_category, location)

        # If owner compensation not provided, estimate from typical patterns
        if owner_compensation is None:
            # Estimate: For SMEs, owner typically takes 8-12% of revenue or €50k minimum
            estimated_comp = max(
                revenue * Decimal("0.10"), Decimal("50000")  # 10% of revenue  # Minimum €50k
            )
            # Cap at reasonable maximum
            estimated_comp = min(estimated_comp, Decimal("200000"))

            logger.info(
                "Owner compensation not provided, using estimated value",
                extra={
                    "revenue": from_decimal(revenue),
                    "estimated_compensation": from_decimal(estimated_comp),
                    "estimation_method": "10% of revenue, min €50k",
                },
            )

            owner_compensation = estimated_comp
            data_quality = "estimated"
        else:
            data_quality = "provided"

        # Calculate adjustment
        adjustment = owner_compensation - market_rate

        # Determine explanation
        if adjustment > market_rate * Decimal("0.3"):  # >30% above market
            explanation = f"Owner compensation (€{from_decimal(owner_compensation):,.0f}) significantly exceeds market rate (€{from_decimal(market_rate):,.0f}) for replacement manager. Add-back: €{from_decimal(adjustment):,.0f}"
            severity = "high"
        elif adjustment > market_rate * Decimal("0.1"):  # 10-30% above market
            explanation = f"Owner compensation moderately above market rate. Add-back: €{from_decimal(adjustment):,.0f}"
            severity = "medium"
        elif adjustment < -market_rate * Decimal("0.2"):  # >20% below market
            explanation = f"Owner underpaid vs. replacement cost (€{from_decimal(market_rate):,.0f}). Subtract replacement cost difference: €{from_decimal(abs(adjustment)):,.0f}"
            severity = "medium"
        elif abs(adjustment) < market_rate * Decimal("0.1"):  # Within 10%
            explanation = f"Owner compensation approximately at market rate. Minimal adjustment: €{from_decimal(adjustment):,.0f}"
            severity = "low"
        else:
            explanation = f"Owner compensation adjustment: €{from_decimal(adjustment):,.0f}"
            severity = "low"

        metadata = {
            "owner_compensation": from_decimal(owner_compensation),
            "market_rate": from_decimal(market_rate),
            "adjustment": from_decimal(adjustment),
            "adjustment_percentage": from_decimal(
                (adjustment / owner_compensation * 100) if owner_compensation > 0 else Decimal("0")
            ),
            "severity": severity,
            "data_quality": data_quality,
            "revenue_tier": self._get_revenue_tier(revenue),
        }

        logger.info(
            "✅ Owner compensation adjustment calculated",
            extra={
                "adjustment": from_decimal(adjustment),
                "owner_comp": from_decimal(owner_compensation),
                "market_rate": from_decimal(market_rate),
                "severity": severity,
                "data_quality": data_quality,
            },
        )

        return adjustment, explanation, metadata

    def _get_revenue_tier(self, revenue: Decimal) -> str:
        """Get revenue tier label."""
        if revenue < Decimal("500000"):
            return "under_500k"
        elif revenue < Decimal("1000000"):
            return "500k_to_1m"
        elif revenue < Decimal("2000000"):
            return "1m_to_2m"
        elif revenue < Decimal("5000000"):
            return "2m_to_5m"
        else:
            return "over_5m"
