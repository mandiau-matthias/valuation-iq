"""
Discount Calculation Coordinator

Orchestrates discount and adjustment calculations for the multiples engine.
Handles size discounts, liquidity discounts, country adjustments, and growth premiums.

RESPONSIBILITIES:
- Calculate size-based discounts
- Calculate liquidity discounts
- Calculate country adjustments
- Calculate growth premiums
- Return all adjustments as a dictionary

ARCHITECTURE:
This coordinator acts as a thin orchestration layer that:
1. Calculates individual adjustments
2. Combines adjustments into total adjustment factor
3. Handles transparency tracking for adjustments

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive error handling
- Detailed logging
- No code duplication
"""

from decimal import Decimal
from typing import Dict, Mapping

from src.domain.models import FinancialData, MarketContext
from src.domain.revenue_growth import revenue_growth
from src.domain.multiples.advisor_controls import (
    DEFAULT_DISCOUNT_FLOOR_FACTOR,
    compose_discount_stack,
)
from src.domain.multiples.strength_factor_discount_evidence import (
    annotate_discount_stack_with_strength_factor_evidence,
    apply_strength_factor_discount_adjustments,
)
from src.utils.decimal_helpers import to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class DiscountCalculationCoordinator:
    """
    Coordinates discount and adjustment calculations for the multiples engine.

    This coordinator handles:
    1. Size discount calculation
    2. Liquidity discount calculation
    3. Country adjustment calculation
    4. Growth premium calculation
    """

    def __init__(
        self,
        financial_data: FinancialData,
        market_context: MarketContext,
    ) -> None:
        """
        Initialize discount calculation coordinator.

        Args:
            financial_data: Company financial data
            market_context: Market and economic context
        """
        self.financial_data = financial_data
        self.market_context = market_context
        self.logger = logger

    def calculate_all_adjustments(
        self,
        *,
        advisor_discount_weights: Mapping[str, object] | None = None,
        risk_analysis_enabled: bool = True,
        discount_floor_factor: object = DEFAULT_DISCOUNT_FLOOR_FACTOR,
        strength_factor_discount_adjustments: object = None,
    ) -> Dict[str, object]:
        """
        Calculate all adjustments and return as dictionary.

        Returns:
            Dictionary with size_discount, liquidity_discount, country_adjustment,
            growth_premium, and total_adjustment
        """
        size_discount = self.calculate_size_discount()
        liquidity_discount = self.calculate_liquidity_discount()
        country_adjustment = self.calculate_country_adjustment()
        growth_premium = self.calculate_growth_premium()

        adjustments, strength_factor_evidence = apply_strength_factor_discount_adjustments(
            {
                "size_discount": size_discount,
                "liquidity_discount": liquidity_discount,
                "country_adjustment": country_adjustment,
                "growth_premium": growth_premium,
            },
            strength_factor_discount_adjustments,
        )

        discount_stack = compose_discount_stack(
            adjustments,
            raw_weights=advisor_discount_weights,
            enabled=risk_analysis_enabled,
            floor_factor=discount_floor_factor,
        )
        discount_stack = annotate_discount_stack_with_strength_factor_evidence(
            discount_stack,
            strength_factor_evidence,
        )
        total_adjustment = discount_stack["total_adjustment_factor"]

        return {
            "size_discount": adjustments.get("size_discount", size_discount),
            "liquidity_discount": adjustments.get("liquidity_discount", liquidity_discount),
            "country_adjustment": adjustments.get("country_adjustment", country_adjustment),
            "growth_premium": adjustments.get("growth_premium", growth_premium),
            "total_adjustment": total_adjustment,
            "discount_stack": discount_stack,
            "risk_analysis_enabled": risk_analysis_enabled,
            "discount_floor_factor": discount_stack["floor_factor"],
            "strength_factor_evidence": strength_factor_evidence,
        }

    def get_size_tier(self, revenue: Decimal = None) -> str:
        """
        Determine size tier based on revenue.

        ADDED 2025-12-20: Expose size tier for correlation-aware calibration.

        Args:
            revenue: Company revenue (optional, uses latest_revenue if not provided)

        Returns:
            Size tier name: "micro_cap", "very_small", "small", "small_medium",
                           "mid_market", or "large"
        """
        if revenue is None:
            revenue = to_decimal(self.financial_data.latest_revenue)
        else:
            revenue = to_decimal(revenue)

        # Defensive check for invalid revenue
        if revenue <= 0:
            logger.warning(f"Invalid revenue: {revenue}. Defaulting to micro_cap tier.")
            return "micro_cap"

        revenue_decimal = to_decimal(revenue)

        # Size tiers matching calculate_size_discount logic
        if revenue_decimal < Decimal("1000000"):  # < €1M
            return "micro_cap"
        elif revenue_decimal < Decimal("2000000"):  # €1M-€2M
            return "very_small"
        elif revenue_decimal < Decimal("3000000"):  # €2M-€3M
            return "small"
        elif revenue_decimal < Decimal("5000000"):  # €3M-€5M
            return "small_medium"
        elif revenue_decimal < Decimal("50000000"):  # €5M-€50M
            return "mid_market"
        else:  # ≥€50M
            return "large"

    def calculate_size_discount(self) -> Decimal:
        """
        Calculate size discount based on Fama-French (1992), Ibbotson SBBI (2024).

        UPDATED 2025-12-20: Enhanced academic defensibility per comprehensive audit.

        Academic Support:
        - Fama-French (1992): "The Cross-Section of Expected Stock Returns"
          Size factor yields 3-5% annual return premium → 15-25% valuation discount
        - Ibbotson SBBI (2024): Micro-cap premium 5-7% → 20-30% valuation discount
        - Duff & Phelps (2024): Size premium for sub-€1M companies: 20-25%
        - McKinsey (2015): "Valuation", Chapter 8 - Graduated discounts for micro-cap SMEs

        The size premium reflects systematic risk factors including:
        - Higher information asymmetry in micro-cap companies
        - Lower trading liquidity and higher transaction costs
        - Greater sensitivity to economic shocks
        - Limited access to capital markets

        Multiples from databases become "correct" (no correction needed) at €5M+ revenue.

        Returns negative value (discount)
        """
        revenue = to_decimal(self.financial_data.latest_revenue)

        # Defensive check for invalid revenue
        if revenue <= 0:
            logger.warning(f"Invalid revenue: {revenue}. Using default -22% discount (micro-cap).")
            return Decimal("-0.22")

        revenue_decimal = to_decimal(revenue)

        # Size discount tiers based on academic research
        if revenue_decimal < Decimal("1000000"):  # < €1M (Micro-cap)
            discount = Decimal("-0.22")  # 22% discount
            logger.info(
                f"Applied -22% micro-cap size discount for revenue €{float(revenue_decimal):,.0f}"
            )
            return discount
        elif revenue_decimal < Decimal("2000000"):  # €1M-€2M (Very Small)
            discount = Decimal("-0.18")  # 18% discount
            logger.info(
                f"Applied -18% very small size discount for revenue €{float(revenue_decimal):,.0f}"
            )
            return discount
        elif revenue_decimal < Decimal("3000000"):  # €2M-€3M (Small)
            discount = Decimal("-0.14")  # 14% discount
            logger.info(
                f"Applied -14% small size discount for revenue €{float(revenue_decimal):,.0f}"
            )
            return discount
        elif revenue_decimal < Decimal("5000000"):  # €3M-€5M (Small-Medium)
            discount = Decimal("-0.10")  # 10% discount
            logger.info(
                f"Applied -10% small-medium size discount for revenue €{float(revenue_decimal):,.0f}"
            )
            return discount
        else:  # ≥€5M (Multiples are correct)
            logger.info(
                f"No size discount for revenue €{float(revenue_decimal):,.0f} (≥€5M threshold)"
            )
            return Decimal("0.0")  # No discount - multiples from database are already correct

    def calculate_liquidity_discount(self) -> Decimal:
        """
        Calculate liquidity discount for private companies.

        Private company shares are illiquid compared to public companies.
        Standard discount: 20-35% for private companies.

        Returns negative value (discount)
        """
        # Standard private company liquidity discount
        base_discount = Decimal("-0.25")  # 25% base discount

        # Adjust based on company characteristics
        # More attractive companies get smaller discounts

        # Strong recurring revenue reduces discount
        recurring_revenue_pct = to_decimal(self.financial_data.recurring_revenue_percentage)
        if recurring_revenue_pct > Decimal("0.70"):
            base_discount += Decimal("0.05")  # Reduce discount by 5%
        elif recurring_revenue_pct > Decimal("0.50"):
            base_discount += Decimal("0.03")  # Reduce discount by 3%

        # Strong profitability reduces discount
        current_year = self.financial_data.current_year
        ebitda = to_decimal(current_year.ebitda)
        revenue = to_decimal(current_year.revenue)
        if revenue > 0:
            ebitda_margin = ebitda / revenue
            if ebitda_margin > Decimal("0.25"):
                base_discount += Decimal("0.03")  # Reduce discount by 3%
            elif ebitda_margin > Decimal("0.15"):
                base_discount += Decimal("0.02")  # Reduce discount by 2%

        return base_discount

    def calculate_country_adjustment(self) -> Decimal:
        """
        Calculate country/geography adjustment.

        Different markets have different risk profiles and multiples.
        """
        country = self.financial_data.country_code

        # Country risk premiums (relative to Germany/Northern Europe)
        country_adjustments = {
            "DE": Decimal("0.0"),  # Germany (baseline)
            "NL": Decimal("0.0"),  # Netherlands
            "AT": Decimal("0.0"),  # Austria
            "CH": Decimal("0.02"),  # Switzerland (premium for stability)
            "FR": Decimal("-0.02"),  # France (slight discount)
            "BE": Decimal("0.0"),  # Belgium
            "LU": Decimal("0.02"),  # Luxembourg (premium)
            "ES": Decimal("-0.05"),  # Spain (discount)
            "IT": Decimal("-0.08"),  # Italy (higher discount)
            "PT": Decimal("-0.08"),  # Portugal
            "GR": Decimal("-0.15"),  # Greece (significant discount)
            "PL": Decimal("-0.05"),  # Poland
            "CZ": Decimal("-0.03"),  # Czech Republic
        }

        return country_adjustments.get(
            country, Decimal("-0.10")
        )  # Default discount for unlisted countries

    def calculate_growth_premium(self) -> Decimal:
        """
        Calculate growth premium for high-growth companies.

        Fast-growing companies command higher multiples.

        Returns positive value (premium)
        """
        growth = revenue_growth(
            self.financial_data.current_year, self.financial_data.historical_years
        ).rate
        if growth is None:
            return Decimal("0.0")

        # Growth premium based on annualized comparable revenue growth
        if growth > Decimal("0.50"):  # >50% growth
            return Decimal("0.15")  # 15% premium
        elif growth > Decimal("0.30"):  # >30% growth
            return Decimal("0.10")  # 10% premium
        elif growth > Decimal("0.20"):  # >20% growth
            return Decimal("0.05")  # 5% premium
        else:
            return Decimal("0.0")  # No premium for slower growth
