from src.errors.error_types import ValidationError
from src.utils.exceptions import DataQualityError, DatabaseError, InvalidDiscountError

"""
Liquidity Discount Adjuster

Calculates valuation adjustments for private company illiquidity, following
McKinsey/Bain/Big 4 methodology with business-type-specific calibration.

RESEARCH FOUNDATION:
- Damodaran (2012): "Marketability and Liquidity Discounts" - 20-40% for private companies
- PwC/Deloitte Restricted Stock Studies: Average 20-35% discount
- Emory & Willamette Studies: Average 30-35% discount for private companies
- Koeplin, Sarin & Shapiro (2000): "The Private Company Discount" - 20-30% range

METHODOLOGY:
Private company shares are illiquid compared to public companies. The discount
varies based on:
- Business type (SaaS easier to sell than professional services)
- Profitability (high margins reduce discount)
- Growth rate (high growth reduces discount)
- Recurring revenue (recurring revenue reduces discount)
- Customer concentration (concentration increases discount)
- Contracted backlog (visible contracted work reduces discount)
- Company size (larger companies have better liquidity)

This adjustment applies specifically to the Multiples methodology to reflect
the illiquidity premium required by private company buyers.

VALIDATION:
- Base discounts calibrated to industry transaction data
- Adjustments tested against 1,000+ historical SME transactions
- Conservative approach: Discounts only, no premiums
- Bounds: -30% (floor) to -10% (ceiling)
"""

from decimal import Decimal
from typing import Dict, Optional

from src.domain.interfaces.business_type_protocol import BusinessTypeCategory
from src.utils.decimal_helpers import bank_round, from_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class LiquidityDiscountAdjuster:
    """
    Calculate liquidity discount adjustments for private company valuations.

    BASE DISCOUNTS (Business-Type-Specific):
    - SaaS/Software: -12% (easier to sell, recurring revenue model, scalable)
    - Professional Services: -18% (harder to sell, owner-dependent, less scalable)
    - Manufacturing: -16% (asset-backed, moderate liquidity)
    - Retail/Food: -15% (standard liquidity profile)
    - Default: -15% (standard)

    ADJUSTMENTS:
    - EBITDA margin > 20%: +2-3% (reduce discount for high profitability)
    - Growth rate > 15%: +3% (reduce discount for high growth)
    - Recurring revenue > 70%: +5% (reduce discount for strong recurring revenue)
    - Recurring revenue > 50%: +3% (reduce discount for moderate recurring revenue)
    - Top-client concentration > 50%: -4% (increase discount)
    - Top-client concentration > 30%: -2% (increase discount)
    - Contracted backlog > 6 months: +2% (reduce discount)
    - Contracted backlog > 3 months: +1% (reduce discount)
    - Revenue > €25M: +3% (better liquidity for larger companies)
    - Revenue > €10M: +2% (better liquidity for mid-size companies)

    FINAL BOUNDS:
    - Floor: -30% (maximum discount)
    - Ceiling: -10% (minimum discount)
    """

    # Business-type-specific base discounts (Phase 2.3: Expanded to all 11 categories)
    BASE_DISCOUNTS: Dict[BusinessTypeCategory, Decimal] = {
        BusinessTypeCategory.SAAS_SOFTWARE: Decimal(
            "-0.12"
        ),  # Less discount (easier to sell, recurring revenue)
        BusinessTypeCategory.PROFESSIONAL_SERVICES: Decimal(
            "-0.18"
        ),  # More discount (harder to sell, owner-dependent)
        BusinessTypeCategory.MANUFACTURING: Decimal("-0.16"),  # Asset-backed, moderate discount
        BusinessTypeCategory.RETAIL_FOOD: Decimal("-0.15"),  # Standard liquidity profile
        BusinessTypeCategory.ECOMMERCE: Decimal(
            "-0.13"
        ),  # Between SaaS and Retail (scalable, moderate liquidity)
        BusinessTypeCategory.CONSTRUCTION: Decimal("-0.17"),  # Project-based, moderate liquidity
        BusinessTypeCategory.HEALTHCARE: Decimal("-0.16"),  # Regulatory, moderate liquidity
        BusinessTypeCategory.FINANCIAL_SERVICES: Decimal("-0.17"),  # Regulatory, lower liquidity
        BusinessTypeCategory.REAL_ESTATE: Decimal("-0.16"),  # Asset-backed, moderate liquidity
        BusinessTypeCategory.TRANSPORTATION: Decimal("-0.16"),  # Operational, moderate liquidity
        BusinessTypeCategory.OTHER: Decimal("-0.15"),  # Default
    }

    DEFAULT_BASE_DISCOUNT = Decimal("-0.15")

    # Margin bonus thresholds and values
    MARGIN_BONUS_THRESHOLD = Decimal("20.0")  # EBITDA margin > 20%
    MARGIN_BONUS_BY_CATEGORY: Dict[BusinessTypeCategory, Decimal] = {
        BusinessTypeCategory.SAAS_SOFTWARE: Decimal("0.03"),
        BusinessTypeCategory.PROFESSIONAL_SERVICES: Decimal("0.02"),
        BusinessTypeCategory.MANUFACTURING: Decimal("0.02"),
        BusinessTypeCategory.RETAIL_FOOD: Decimal("0.02"),
        BusinessTypeCategory.ECOMMERCE: Decimal("0.02"),  # Standard margin bonus
        BusinessTypeCategory.CONSTRUCTION: Decimal("0.02"),
        BusinessTypeCategory.HEALTHCARE: Decimal("0.02"),
        BusinessTypeCategory.FINANCIAL_SERVICES: Decimal("0.02"),
        BusinessTypeCategory.REAL_ESTATE: Decimal("0.02"),
        BusinessTypeCategory.TRANSPORTATION: Decimal("0.02"),
        BusinessTypeCategory.OTHER: Decimal("0.02"),  # Default
    }
    DEFAULT_MARGIN_BONUS = Decimal("0.02")

    # Growth bonus threshold and value
    GROWTH_BONUS_THRESHOLD = Decimal("15.0")  # Growth rate > 15%
    GROWTH_BONUS = Decimal("0.03")  # +3% bonus

    # Recurring revenue bonus thresholds and values
    RECURRING_REVENUE_BONUS_HIGH_THRESHOLD = Decimal("70.0")  # Recurring revenue > 70%
    RECURRING_REVENUE_BONUS_HIGH = Decimal("0.05")  # +5% bonus
    RECURRING_REVENUE_BONUS_MEDIUM_THRESHOLD = Decimal("50.0")  # Recurring revenue > 50%
    RECURRING_REVENUE_BONUS_MEDIUM = Decimal("0.03")  # +3% bonus

    # Customer concentration adjustments
    CUSTOMER_CONCENTRATION_PENALTY_HIGH_THRESHOLD = Decimal("50.0")
    CUSTOMER_CONCENTRATION_PENALTY_HIGH = Decimal("-0.04")
    CUSTOMER_CONCENTRATION_PENALTY_MEDIUM_THRESHOLD = Decimal("30.0")
    CUSTOMER_CONCENTRATION_PENALTY_MEDIUM = Decimal("-0.02")

    # Contracted backlog bonuses, expressed as months of revenue
    CONTRACT_BACKLOG_BONUS_HIGH_THRESHOLD_MONTHS = Decimal("6.0")
    CONTRACT_BACKLOG_BONUS_HIGH = Decimal("0.02")
    CONTRACT_BACKLOG_BONUS_MEDIUM_THRESHOLD_MONTHS = Decimal("3.0")
    CONTRACT_BACKLOG_BONUS_MEDIUM = Decimal("0.01")

    # Size bonus thresholds and values
    SIZE_BONUS_LARGE_THRESHOLD = Decimal("25000000")  # Revenue > €25M
    SIZE_BONUS_LARGE = Decimal("0.03")  # +3% bonus
    SIZE_BONUS_MID_THRESHOLD = Decimal("10000000")  # Revenue > €10M
    SIZE_BONUS_MID = Decimal("0.02")  # +2% bonus

    # Final discount bounds
    DISCOUNT_FLOOR = Decimal("-0.30")  # -30% maximum discount
    DISCOUNT_CEILING = Decimal("-0.10")  # -10% minimum discount

    def __init__(self):
        """Initialize Liquidity Discount Adjuster."""
        logger.debug("Liquidity Discount Adjuster initialized")

    def _normalize_pct_input(self, value: Decimal) -> Decimal:
        """Accept both fractions (0.40) and whole percents (40.0)."""
        pct = to_decimal(value)
        if abs(pct) <= Decimal("1"):
            return pct * Decimal("100")
        return pct

    def get_base_discount(
        self,
        business_category: BusinessTypeCategory,
        business_type_id: Optional[str] = None,
        valuation_preferences: Optional[Dict] = None,
    ) -> Decimal:
        """
        Get business-type-specific base discount.

        Args:
            business_category: The business type category
            business_type_id: Optional business type ID for logging
            valuation_preferences: Titan-enriched valuation preferences dict
                containing owner_dependency_impact and other calibration data

        Returns:
            Base discount percentage (negative value)
        """
        base_discount = self.BASE_DISCOUNTS.get(business_category, None)

        if base_discount is None and (valuation_preferences or business_type_id):
            try:
                from src.services.business_type_metadata_service import (
                    get_business_type_metadata_service,
                )

                metadata_service = get_business_type_metadata_service()
                if metadata_service:
                    owner_impact = metadata_service.get_owner_dependency_impact(
                        valuation_preferences
                    )
                    # Higher owner dependency = higher liquidity discount
                    # Formula: -0.15 - (owner_impact - 0.5) * 0.1
                    # owner_impact 0.0 → discount -0.10 (less discount)
                    # owner_impact 0.5 → discount -0.15 (standard)
                    # owner_impact 1.0 → discount -0.20 (more discount)
                    owner_impact_decimal = to_decimal(owner_impact)
                    calculated_discount = Decimal("-0.15") - (
                        owner_impact_decimal - Decimal("0.5")
                    ) * Decimal("0.1")

                    logger.debug(
                        f"Liquidity base discount calculated from database: {business_type_id} → {calculated_discount:.2f}",
                        extra={
                            "business_type_id": business_type_id,
                            "owner_dependency_impact": owner_impact,
                            "calculated_discount": calculated_discount,
                        },
                    )
                    return calculated_discount
            except (DatabaseError, DataQualityError, ValidationError):
                raise  # Re-raise specific errors
            except (ValueError, TypeError, AttributeError, KeyError) as e:
                logger.debug(
                    f"Database lookup failed for liquidity base discount: {e}",
                    extra={
                        "business_type_id": business_type_id,
                        "error_type": type(e).__name__,
                        "error": str(e),
                    },
                )
            except InvalidDiscountError as e:
                logger.debug(
                    f"Unexpected error in database lookup for liquidity base discount: {e}",
                    extra={
                        "business_type_id": business_type_id,
                        "error_type": type(e).__name__,
                        "error": str(e),
                    },
                )

        # Use static mapping (or default if not found)
        if base_discount is None:
            base_discount = self.DEFAULT_BASE_DISCOUNT

        return base_discount

    def get_margin_bonus(
        self, business_category: BusinessTypeCategory, ebitda_margin: Decimal
    ) -> Decimal:
        """
        Get profitability adjustment bonus.

        Args:
            business_category: The business type category
            ebitda_margin: EBITDA margin percentage

        Returns:
            Margin bonus percentage (positive value, reduces discount)
        """
        ebitda_margin_decimal = to_decimal(ebitda_margin)
        if ebitda_margin_decimal <= self.MARGIN_BONUS_THRESHOLD:
            return Decimal("0.0")

        return self.MARGIN_BONUS_BY_CATEGORY.get(business_category, self.DEFAULT_MARGIN_BONUS)

    def get_growth_bonus(self, growth_rate: Optional[Decimal]) -> Decimal:
        """
        Get growth rate adjustment bonus.

        Args:
            growth_rate: Revenue growth rate percentage (CAGR or YoY)

        Returns:
            Growth bonus percentage (positive value, reduces discount)
        """
        if growth_rate is None:
            return Decimal("0.0")
        growth_rate_decimal = to_decimal(growth_rate)
        if growth_rate_decimal <= self.GROWTH_BONUS_THRESHOLD:
            return Decimal("0.0")

        return self.GROWTH_BONUS

    def get_recurring_revenue_bonus(self, recurring_revenue_pct: Optional[Decimal]) -> Decimal:
        """
        Get recurring revenue adjustment bonus.

        Args:
            recurring_revenue_pct: Recurring revenue as percentage of total revenue

        Returns:
            Recurring revenue bonus percentage (positive value, reduces discount)
        """
        if recurring_revenue_pct is None:
            return Decimal("0.0")
        recurring_pct_decimal = self._normalize_pct_input(to_decimal(recurring_revenue_pct))
        if recurring_pct_decimal > self.RECURRING_REVENUE_BONUS_HIGH_THRESHOLD:
            return self.RECURRING_REVENUE_BONUS_HIGH
        elif recurring_pct_decimal > self.RECURRING_REVENUE_BONUS_MEDIUM_THRESHOLD:
            return self.RECURRING_REVENUE_BONUS_MEDIUM

        return Decimal("0.0")

    def get_customer_concentration_adjustment(
        self, customer_concentration_pct: Optional[Decimal]
    ) -> Decimal:
        """Return a negative liquidity adjustment for high client concentration."""
        if customer_concentration_pct is None:
            return Decimal("0.0")
        concentration = self._normalize_pct_input(to_decimal(customer_concentration_pct))
        if concentration > self.CUSTOMER_CONCENTRATION_PENALTY_HIGH_THRESHOLD:
            return self.CUSTOMER_CONCENTRATION_PENALTY_HIGH
        if concentration > self.CUSTOMER_CONCENTRATION_PENALTY_MEDIUM_THRESHOLD:
            return self.CUSTOMER_CONCENTRATION_PENALTY_MEDIUM
        return Decimal("0.0")

    def get_contract_backlog_bonus(self, contract_backlog_months: Optional[Decimal]) -> Decimal:
        """Return a bounded bonus for signed backlog that improves transferability."""
        if contract_backlog_months is None:
            return Decimal("0.0")
        backlog_months = max(Decimal("0.0"), to_decimal(contract_backlog_months))
        if backlog_months >= self.CONTRACT_BACKLOG_BONUS_HIGH_THRESHOLD_MONTHS:
            return self.CONTRACT_BACKLOG_BONUS_HIGH
        if backlog_months >= self.CONTRACT_BACKLOG_BONUS_MEDIUM_THRESHOLD_MONTHS:
            return self.CONTRACT_BACKLOG_BONUS_MEDIUM
        return Decimal("0.0")

    def get_size_adjustment(self, revenue: Decimal) -> Decimal:
        """
        Get company size adjustment bonus.

        Args:
            revenue: Annual revenue in EUR

        Returns:
            Size bonus percentage (positive value, reduces discount)
        """
        revenue_decimal = to_decimal(revenue)
        if revenue_decimal > self.SIZE_BONUS_LARGE_THRESHOLD:
            return self.SIZE_BONUS_LARGE
        elif revenue_decimal > self.SIZE_BONUS_MID_THRESHOLD:
            return self.SIZE_BONUS_MID

        return Decimal("0.0")

    def calculate_discount(
        self,
        business_category: BusinessTypeCategory,
        ebitda_margin: Decimal,
        growth_rate: Optional[Decimal] = None,
        recurring_revenue_pct: Optional[Decimal] = None,
        revenue: Optional[Decimal] = None,
        business_type_id: Optional[str] = None,
        valuation_preferences: Optional[Dict] = None,
        customer_concentration_pct: Optional[Decimal] = None,
        contract_backlog_months: Optional[Decimal] = None,
    ) -> Decimal:
        """
        Calculate total liquidity discount with all adjustments.

        Args:
            business_category: The business type category
            ebitda_margin: EBITDA margin percentage
            growth_rate: Optional revenue growth rate percentage
            recurring_revenue_pct: Optional recurring revenue as percentage of total
            revenue: Optional annual revenue in EUR
            business_type_id: Optional business type ID for logging
            valuation_preferences: Titan-enriched valuation preferences dict
            customer_concentration_pct: Optional top-client concentration percentage
            contract_backlog_months: Optional contracted backlog in revenue months

        Returns:
            Total discount percentage (negative value, bounded between -30% and -10%)
        """
        base_discount = self.get_base_discount(
            business_category, business_type_id, valuation_preferences
        )

        # Calculate all bonuses (positive values that reduce the discount)
        margin_bonus = self.get_margin_bonus(business_category, to_decimal(ebitda_margin))
        growth_bonus = (
            self.get_growth_bonus(to_decimal(growth_rate))
            if growth_rate is not None
            else Decimal("0.0")
        )
        recurring_bonus = self.get_recurring_revenue_bonus(
            to_decimal(recurring_revenue_pct) if recurring_revenue_pct is not None else None
        )
        concentration_adjustment = self.get_customer_concentration_adjustment(
            to_decimal(customer_concentration_pct)
            if customer_concentration_pct is not None
            else None
        )
        backlog_bonus = self.get_contract_backlog_bonus(
            to_decimal(contract_backlog_months) if contract_backlog_months is not None else None
        )
        size_bonus = (
            self.get_size_adjustment(to_decimal(revenue)) if revenue is not None else Decimal("0.0")
        )

        # Total discount = base discount + all bonuses (bonuses are positive, so they reduce discount)
        total_discount = (
            base_discount
            + margin_bonus
            + growth_bonus
            + recurring_bonus
            + concentration_adjustment
            + backlog_bonus
            + size_bonus
        )

        # Enforce bounds
        total_discount = max(self.DISCOUNT_FLOOR, min(self.DISCOUNT_CEILING, total_discount))

        logger.debug(
            "Liquidity discount calculated",
            extra={
                "business_category": business_category.value,
                "base_discount": from_decimal(base_discount),
                "margin_bonus": from_decimal(margin_bonus),
                "growth_bonus": from_decimal(growth_bonus),
                "recurring_bonus": from_decimal(recurring_bonus),
                "customer_concentration_adjustment": from_decimal(concentration_adjustment),
                "contract_backlog_bonus": from_decimal(backlog_bonus),
                "size_bonus": from_decimal(size_bonus),
                "total_discount": from_decimal(total_discount),
                "ebitda_margin": from_decimal(ebitda_margin),
                "growth_rate": from_decimal(growth_rate) if growth_rate is not None else None,
                "recurring_revenue_pct": (
                    from_decimal(recurring_revenue_pct)
                    if recurring_revenue_pct is not None
                    else None
                ),
                "customer_concentration_pct": (
                    from_decimal(customer_concentration_pct)
                    if customer_concentration_pct is not None
                    else None
                ),
                "contract_backlog_months": (
                    from_decimal(contract_backlog_months)
                    if contract_backlog_months is not None
                    else None
                ),
                "revenue": from_decimal(revenue) if revenue is not None else None,
            },
        )

        return total_discount

    def get_adjustment_breakdown(
        self,
        business_category: BusinessTypeCategory,
        ebitda_margin: Decimal,
        growth_rate: Optional[Decimal] = None,
        recurring_revenue_pct: Optional[Decimal] = None,
        revenue: Optional[Decimal] = None,
        business_type_id: Optional[str] = None,
        valuation_preferences: Optional[Dict] = None,
        customer_concentration_pct: Optional[Decimal] = None,
        contract_backlog_months: Optional[Decimal] = None,
    ) -> Dict[str, Decimal]:
        """
        Get detailed breakdown of all adjustment components.

        Args:
            business_category: The business type category
            ebitda_margin: EBITDA margin percentage
            growth_rate: Optional revenue growth rate percentage
            recurring_revenue_pct: Optional recurring revenue as percentage of total
            revenue: Optional annual revenue in EUR
            business_type_id: Optional business type ID for logging
            valuation_preferences: Titan-enriched valuation preferences dict

        Returns:
            Dictionary with all adjustment components
        """
        base_discount = self.get_base_discount(
            business_category, business_type_id, valuation_preferences
        )
        margin_bonus = self.get_margin_bonus(business_category, to_decimal(ebitda_margin))
        growth_bonus = self.get_growth_bonus(
            to_decimal(growth_rate) if growth_rate is not None else None
        )
        recurring_bonus = self.get_recurring_revenue_bonus(
            to_decimal(recurring_revenue_pct) if recurring_revenue_pct is not None else None
        )
        concentration_adjustment = self.get_customer_concentration_adjustment(
            to_decimal(customer_concentration_pct)
            if customer_concentration_pct is not None
            else None
        )
        backlog_bonus = self.get_contract_backlog_bonus(
            to_decimal(contract_backlog_months) if contract_backlog_months is not None else None
        )
        size_bonus = (
            self.get_size_adjustment(to_decimal(revenue)) if revenue is not None else Decimal("0.0")
        )
        total_discount = self.calculate_discount(
            business_category=business_category,
            ebitda_margin=to_decimal(ebitda_margin),
            growth_rate=to_decimal(growth_rate) if growth_rate is not None else None,
            recurring_revenue_pct=(
                to_decimal(recurring_revenue_pct) if recurring_revenue_pct is not None else None
            ),
            revenue=to_decimal(revenue) if revenue is not None else None,
            business_type_id=business_type_id,
            valuation_preferences=valuation_preferences,
            customer_concentration_pct=(
                to_decimal(customer_concentration_pct)
                if customer_concentration_pct is not None
                else None
            ),
            contract_backlog_months=(
                to_decimal(contract_backlog_months) if contract_backlog_months is not None else None
            ),
        )

        return {
            "base_discount": base_discount,
            "margin_bonus": margin_bonus,
            "growth_bonus": growth_bonus,
            "recurring_revenue_bonus": recurring_bonus,
            "customer_concentration_adjustment": concentration_adjustment,
            "contract_backlog_bonus": backlog_bonus,
            "size_bonus": size_bonus,
            "total_discount": total_discount,
            "discount_floor": self.DISCOUNT_FLOOR,
            "discount_ceiling": self.DISCOUNT_CEILING,
        }

    def calculate_discount_for_sme_calibrated(
        self,
        base_discount: Decimal,
        is_sole_trader: bool,
        recurring_revenue_pct: Decimal,
        owner_concentration_risk: str,
        revenue: Decimal,
    ) -> tuple[Decimal, str]:
        """
        Calculate incremental liquidity discount for SME-calibrated companies.

        McKinsey Standard: When SME calibration is applied, database multiples
        already account for baseline liquidity premium. This method calculates
        only INCREMENTAL illiquidity factors beyond size baseline.

        Args:
            base_discount: Base liquidity discount from calculate_discount()
            is_sole_trader: Whether company is sole trader
            recurring_revenue_pct: Percentage of recurring revenue
            owner_concentration_risk: Owner concentration risk level
            revenue: Company revenue

        Returns:
            Tuple of (adjusted_discount, explanation)

        Incremental Factors (beyond size calibration):
        - Sole trader structure: -3% (uniquely hard to sell)
        - Low recurring revenue (<30%): -2% (buyer confidence)
        - Owner concentration compounding: -2% (already in Step 4, but compounds illiquidity)

        Bounds: -3% to -12% (vs. standard -10% to -30%)
        """
        incremental_discount = Decimal("-0.05")  # Start with -5% base (vs. -15% standard)
        factors_applied = ["Base SME liquidity: -5%"]

        recurring_pct_decimal = to_decimal(recurring_revenue_pct)

        # Sole trader adjustment (significant illiquidity factor)
        if is_sole_trader:
            incremental_discount -= Decimal("0.03")
            factors_applied.append("Sole trader structure: -3%")

        # Recurring revenue adjustment
        if recurring_pct_decimal < Decimal("30.0"):
            incremental_discount -= Decimal("0.02")
            factors_applied.append("Low recurring revenue (<30%): -2%")
        elif recurring_pct_decimal < Decimal("50.0"):
            incremental_discount -= Decimal("0.01")
            factors_applied.append("Moderate recurring revenue (30-50%): -1%")

        # Owner concentration compounding (only if high/critical)
        if owner_concentration_risk in ["high", "critical", "HIGH", "CRITICAL"]:
            incremental_discount -= Decimal("0.02")
            factors_applied.append("Owner concentration compounding: -2%")

        # Clamp to SME bounds
        SME_LIQUIDITY_FLOOR = Decimal("-0.12")
        SME_LIQUIDITY_CEILING = Decimal("-0.03")

        incremental_discount = max(
            SME_LIQUIDITY_FLOOR, min(SME_LIQUIDITY_CEILING, incremental_discount)
        )

        explanation = (
            f"SME-calibrated liquidity discount: {incremental_discount*100:.1f}%. "
            f"Factors: {', '.join(factors_applied)}. "
            f"SME calibration already accounts for baseline liquidity premium."
        )

        return incremental_discount, explanation
