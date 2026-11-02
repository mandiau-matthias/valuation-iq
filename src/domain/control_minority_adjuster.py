"""
Control Premium & Minority Discount Adjuster

Calculates ownership-based valuation adjustments following McKinsey and Bain standards.
Applies control premiums for majority stakes (>50%) and minority discounts for minority
stakes (<50%), with special handling for 50% ownership deadlock scenarios.

RESEARCH FOUNDATION:
- McKinsey Valuation (2015): Control premium 10-30% for >50% stakes
- McKinsey Valuation (2015): Minority discount 15-30% for <50% stakes
- Bain Private Equity Guide (2020): Deadlock risk discount 5-10% for 50% ownership
- Mergerstat Review (2020): Average control premium 15-25%
- Pratt & Niculita (2008): Minority discount 15-30% for <50% stakes

METHODOLOGY:
Control Premium (>50% ownership):
- 51-75%: +10% to +20% premium (majority control, operational control)
- 76-99%: +15% to +25% premium (strong majority, near-full control)
- 100%: +20% to +30% premium (full control, strategic premium potential)

Minority Discount (<50% ownership):
- <25%: -25% to -30% discount (pure minority, no control)
- 25-49%: -15% to -25% discount (minority with blocking rights, varies by jurisdiction)
- Exactly 50%: -5% to -10% discount (equal control, deadlock risk)

Business-Type Calibration:
- Professional Services: +25-30% premium, -25-30% discount (high owner dependency)
- Manufacturing/Asset-Heavy: +10-15% premium, -15-20% discount (low owner dependency)
- SaaS/Technology: +15-20% premium, -20-25% discount (moderate owner dependency)

Revenue-Based Adjustments:
- <€5M: Apply 100% of adjustments (higher impact for smaller companies)
- €5M-€25M: Apply 90% of adjustments
- >€25M: Apply 80% of adjustments (less impact for larger companies)

VALIDATION:
- Tier boundaries based on McKinsey/Bain standards
- Business-type calibration uses owner_dependency_impact from database
- Revenue-based adjustments follow McKinsey SME standards
"""

from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from src.domain.interfaces.business_type_protocol import BusinessTypeCategory
from src.errors.error_types import DatabaseError, DataQualityError
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ControlMinorityAdjuster:
    """
    Calculate ownership-based valuation adjustments (control premium and minority discount).

    ADJUSTMENT TIERS (based on McKinsey/Bain standards):
    - >50% ownership: Control premium (+10% to +30%)
    - <50% ownership: Minority discount (-15% to -30%)
    - Exactly 50%: Deadlock risk discount (-5% to -10%)

    BUSINESS RATIONALE:
    A 75% stake provides majority control and operational control, justifying a 15-25%
    premium over the pro-rata value. A 25% stake provides no control and limited influence,
    justifying a 25-30% discount. A 50% stake creates deadlock risk, justifying a 5-10%
    discount.
    """

    # Minority discount tiers (<50% ownership)
    MINORITY_DISCOUNT_TIERS: List[Dict[str, Any]] = [
        {
            "max_shares": Decimal("25.0"),
            "discount_range": (-Decimal("0.30"), -Decimal("0.25")),
            "description": "Pure minority (no control)",
            "rationale": "No voting control, limited influence on strategic decisions",
        },
        {
            "max_shares": Decimal("49.9"),
            "discount_range": (-Decimal("0.25"), -Decimal("0.15")),
            "description": "Minority with blocking rights",
            "rationale": "May have blocking rights on major decisions (varies by jurisdiction)",
        },
        {
            "max_shares": Decimal("50.0"),
            "discount_range": (-Decimal("0.10"), -Decimal("0.05")),
            "description": "Equal control (deadlock risk)",
            "rationale": "Equal control creates deadlock risk, reduces strategic value",
        },
    ]

    # Control premium tiers (>50% ownership)
    CONTROL_PREMIUM_TIERS: List[Dict[str, Any]] = [
        {
            "min_shares": Decimal("51.0"),
            "max_shares": Decimal("75.0"),
            "premium_range": (Decimal("0.10"), Decimal("0.20")),
            "description": "Majority control",
            "rationale": "Operational control, can make strategic decisions",
        },
        {
            "min_shares": Decimal("76.0"),
            "max_shares": Decimal("99.9"),
            "premium_range": (Decimal("0.15"), Decimal("0.25")),
            "description": "Strong majority",
            "rationale": "Near-full control, can make all strategic decisions",
        },
        {
            "min_shares": Decimal("100.0"),
            "premium_range": (Decimal("0.0"), Decimal("0.0")),
            "description": "Full ownership (no adjustment)",
            "rationale": "100% sale: valuation already reflects full value, no premium needed",
        },
    ]

    # Business-type calibration multipliers
    # Higher owner dependency = higher control premium, higher minority discount
    BUSINESS_TYPE_MULTIPLIERS: Dict[BusinessTypeCategory, Tuple[float, float]] = {
        # (control_premium_multiplier, minority_discount_multiplier)
        "professional_services": (
            Decimal("1.2"),
            Decimal("1.2"),
        ),  # +20% for both
        "manufacturing": (Decimal("0.8"), Decimal("0.8")),  # -20% for both
        "saas_software": (Decimal("1.0"), Decimal("1.0")),  # Standard
        "ecommerce": (Decimal("0.9"), Decimal("0.9")),  # -10% for both
        "retail_food": (Decimal("0.9"), Decimal("0.9")),  # -10% for both
        "construction": (Decimal("0.85"), Decimal("0.85")),  # -15% for both
        "healthcare": (Decimal("1.1"), Decimal("1.1")),  # +10% for both
        "financial_services": (Decimal("1.1"), Decimal("1.1")),  # +10% for both
        "real_estate": (
            Decimal("0.8"),
            Decimal("0.8"),
        ),  # -20% for both (asset-based)
        "transportation": (Decimal("0.9"), Decimal("0.9")),  # -10% for both
        "other": (Decimal("1.0"), Decimal("1.0")),  # Standard
    }

    # Revenue-based adjustment multipliers
    # Use Decimal for max_revenue to avoid to_decimal('inf')
    REVENUE_ADJUSTMENT_MULTIPLIERS: List[Dict[str, Any]] = [
        {
            "max_revenue": to_decimal("5000000"),
            "multiplier": to_decimal("1.0"),
            "description": "<€5M: Full adjustment",
        },
        {
            "max_revenue": to_decimal("25000000"),
            "multiplier": to_decimal("0.9"),
            "description": "€5M-€25M: 90% adjustment",
        },
        {
            "max_revenue": None,
            "multiplier": to_decimal("0.8"),
            "description": ">€25M: 80% adjustment",
        },  # None means no upper limit
    ]

    def __init__(self, business_types_repo: Optional[object] = None):
        """
        Initialize Control/Minority Adjuster

        Args:
            business_types_repo: Repository for fetching business type metadata
        """
        self.business_types_repo = business_types_repo
        self._calibration_cache: Dict[str, Decimal] = {}  # Cache for owner_dependency_impact values
        logger.debug(
            "Control/Minority Adjuster initialized",
            calibration_enabled=business_types_repo is not None,
        )

    def calculate_ownership_adjustment(
        self,
        shares_for_sale: Decimal,
        business_type_id: Optional[str] = None,
        revenue: Optional[Decimal] = None,
        number_of_owners: Optional[int] = None,
        business_category: Optional["BusinessTypeCategory"] = None,
        valuation_preferences: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Calculate ownership adjustment (control premium or minority discount).

        Args:
            shares_for_sale: Percentage of shares for sale (0-100)
            business_type_id: Optional business type ID for logging
            revenue: Optional revenue for revenue-based adjustments
            number_of_owners: Optional number of owners for deadlock risk assessment
            business_category: Optional business category for static calibration
            valuation_preferences: Titan-enriched valuation preferences dict

        Returns:
            Dict with adjustment details:
            - adjustment_type: "control_premium" or "minority_discount" or "deadlock_discount"
            - adjustment_percentage: Applied adjustment percentage
            - adjustment_factor: Multiplier to apply (Decimal('1.0') + adjustment_percentage)
            - base_adjustment: Base adjustment before calibration
            - business_type_multiplier: Business-type calibration multiplier
            - revenue_multiplier: Revenue-based adjustment multiplier
            - rationale: Explanation of adjustment
            - tier_description: Description of tier used
        """
        logger.info(
            "🎯 Starting ownership adjustment calculation",
            extra={
                "shares_for_sale": shares_for_sale,
                "business_type_id": business_type_id,
                "revenue": from_decimal(revenue, precision=2) if revenue else None,
                "number_of_owners": number_of_owners,
                "business_category": business_category.value if business_category else None,
            },
        )

        # Validate shares_for_sale
        if shares_for_sale is None:
            shares_for_sale = Decimal("100.0")
        if shares_for_sale < 0 or shares_for_sale > 100:
            logger.warning(
                "⚠️  Invalid shares_for_sale, clamping to valid range",
                extra={
                    "shares_for_sale_original": shares_for_sale,
                    "shares_for_sale_clamped": max(0.0, min(Decimal("100.0"), shares_for_sale)),
                    "action": "Clamping to 0-100 range",
                },
            )
            shares_for_sale = max(Decimal("0.0"), min(Decimal("100.0"), shares_for_sale))

        # Handle 100% ownership: no adjustment needed (valuation already reflects full value)
        if shares_for_sale >= Decimal("100.0"):
            logger.info(
                "✅ 100%% ownership: No adjustment applied (full value already captured)",
                extra={
                    "shares_for_sale": shares_for_sale,
                    "note": "Valuation reflects 100% enterprise/equity value, no premium or discount needed",
                },
            )
            return {
                "adjustment_type": "no_adjustment",
                "adjustment_percentage": Decimal("0"),
                "adjustment_factor": Decimal("1.0"),
                "base_adjustment": Decimal("0"),
                "base_adjustment_pct": Decimal("0"),
                "business_type_multiplier": Decimal("1.0"),
                "revenue_multiplier": Decimal("1.0"),
                "rationale": "100% ownership: valuation already reflects full enterprise value",
                "tier_description": "Full ownership (no adjustment)",
            }

        # Handle exactly 50% ownership (deadlock risk)
        if abs(shares_for_sale - Decimal("50.0")) < 0.01:
            logger.info(
                "🔍 50% ownership detected: Calculating deadlock risk discount",
                extra={
                    "shares_for_sale": shares_for_sale,
                    "number_of_owners": number_of_owners,
                    "note": "50% ownership creates deadlock risk (Bain/McKinsey standard)",
                },
            )
            return self._calculate_deadlock_adjustment(
                number_of_owners=number_of_owners,
                business_type_id=business_type_id,
                business_category=business_category,
                revenue=revenue,
                valuation_preferences=valuation_preferences,
            )

        # Calculate base adjustment
        logger.debug(
            "📊 Determining adjustment type and base value",
            extra={
                "shares_for_sale": shares_for_sale,
                "threshold": Decimal("50.0"),
                "is_majority": shares_for_sale > Decimal("50.0"),
            },
        )

        if shares_for_sale < 50.0:
            # Minority discount
            logger.debug(
                "📉 Minority stake detected: Calculating minority discount",
                extra={
                    "shares_for_sale": shares_for_sale,
                    "note": "Minority stakes (<50%) receive discount (McKinsey: 15-30%)",
                },
            )
            base_adjustment_float, tier_description, rationale = self._get_minority_discount(
                shares_for_sale
            )
            adjustment_type = "minority_discount"
        else:
            # Control premium
            logger.debug(
                "📈 Majority stake detected: Calculating control premium",
                extra={
                    "shares_for_sale": shares_for_sale,
                    "note": "Majority stakes (>50%) receive premium (McKinsey: 10-30%)",
                },
            )
            base_adjustment_float, tier_description, rationale = self._get_control_premium(
                shares_for_sale
            )
            adjustment_type = "control_premium"

        # Convert to Decimal for calculations
        base_adjustment = to_decimal(str(base_adjustment_float))

        logger.info(
            "✅ Base adjustment determined",
            extra={
                "adjustment_type": adjustment_type,
                "base_adjustment": from_decimal(base_adjustment, precision=4),
                "base_adjustment_pct": from_decimal(
                    base_adjustment * to_decimal("100"), precision=2
                ),
                "tier_description": tier_description,
                "rationale": rationale,
            },
        )

        # Apply business-type calibration
        logger.debug(
            "🏢 Applying business-type calibration",
            extra={
                "business_category": business_category.value if business_category else None,
                "business_type_id": business_type_id,
                "note": "Business-type multipliers adjust base adjustment (higher owner dependency = higher adjustment)",
            },
        )

        business_type_multiplier = self._get_business_type_multiplier(
            adjustment_type=adjustment_type,
            business_category=business_category,
            business_type_id=business_type_id,
            valuation_preferences=valuation_preferences,
        )

        logger.debug(
            "✅ Business-type multiplier determined",
            extra={
                "business_type_multiplier": from_decimal(business_type_multiplier, precision=2),
                "adjustment_after_business_type": from_decimal(
                    base_adjustment * business_type_multiplier, precision=4
                ),
            },
        )

        # Apply revenue-based adjustment
        logger.debug(
            "💰 Applying revenue-based adjustment",
            extra={
                "revenue": from_decimal(revenue, precision=2) if revenue else None,
                "note": "Revenue-based multipliers: <€5M: 100%, €5M-€25M: 90%, >€25M: 80%",
            },
        )

        revenue_multiplier = self._get_revenue_multiplier(revenue)

        logger.debug(
            "✅ Revenue multiplier determined",
            extra={
                "revenue_multiplier": from_decimal(revenue_multiplier, precision=2),
                "adjustment_after_revenue": from_decimal(
                    base_adjustment * business_type_multiplier * revenue_multiplier, precision=4
                ),
            },
        )

        # Calculate final adjustment using Decimal
        logger.debug(
            "🧮 Calculating final calibrated adjustment",
            extra={
                "formula": "Final = Base × Business Type Multiplier × Revenue Multiplier",
                "calculation": f"{from_decimal(base_adjustment, precision=4)} × {from_decimal(business_type_multiplier, precision=2)} × {from_decimal(revenue_multiplier, precision=2)}",
            },
        )

        calibrated_adjustment = base_adjustment * business_type_multiplier * revenue_multiplier

        # Ensure adjustment is within reasonable bounds
        calibrated_adjustment_before_bounds = calibrated_adjustment
        if adjustment_type == "control_premium":
            calibrated_adjustment = min(calibrated_adjustment, to_decimal("0.35"))  # Cap at +35%
        else:
            calibrated_adjustment = max(calibrated_adjustment, to_decimal("-0.35"))  # Cap at -35%

        if calibrated_adjustment != calibrated_adjustment_before_bounds:
            logger.debug(
                "📐 Adjustment bounded to reasonable limits",
                extra={
                    "adjustment_before_bounds": from_decimal(
                        calibrated_adjustment_before_bounds, precision=4
                    ),
                    "adjustment_after_bounds": from_decimal(calibrated_adjustment, precision=4),
                    "bound": "+35%" if adjustment_type == "control_premium" else "-35%",
                },
            )

        adjustment_factor = to_decimal("1.0") + calibrated_adjustment

        logger.info(
            "✅ Ownership adjustment calculated",
            extra={
                "shares_for_sale": shares_for_sale,
                "adjustment_type": adjustment_type,
                "base_adjustment": from_decimal(base_adjustment, precision=4),
                "base_adjustment_pct": from_decimal(
                    base_adjustment * to_decimal("100"), precision=2
                ),
                "business_type_multiplier": from_decimal(business_type_multiplier, precision=2),
                "revenue_multiplier": from_decimal(revenue_multiplier, precision=2),
                "calibrated_adjustment": from_decimal(calibrated_adjustment, precision=4),
                "calibrated_adjustment_pct": from_decimal(
                    calibrated_adjustment * to_decimal("100"), precision=2
                ),
                "adjustment_factor": from_decimal(adjustment_factor, precision=4),
                "tier_description": tier_description,
                "rationale": rationale,
                "formula": f"Adjustment Factor = 1.0 + {from_decimal(calibrated_adjustment, precision=4)} = {from_decimal(adjustment_factor, precision=4)}",
            },
        )

        return {
            "adjustment_type": adjustment_type,
            "adjustment_percentage": from_decimal(
                calibrated_adjustment * to_decimal("100"), precision=2
            ),
            "adjustment_factor": from_decimal(adjustment_factor, precision=4),
            "base_adjustment": from_decimal(base_adjustment, precision=4),
            "base_adjustment_pct": from_decimal(base_adjustment * to_decimal("100"), precision=2),
            "business_type_multiplier": from_decimal(business_type_multiplier, precision=2),
            "revenue_multiplier": from_decimal(revenue_multiplier, precision=2),
            "rationale": rationale,
            "tier_description": tier_description,
            "shares_for_sale": shares_for_sale,
        }

    def _get_minority_discount(self, shares_for_sale: Decimal) -> Tuple[Decimal, str, str]:
        """
        Get minority discount for <50% ownership.

        Returns:
            (discount, tier_description, rationale)
        """
        # Use midpoint of range for simplicity (can be enhanced with more sophisticated logic)
        for tier in self.MINORITY_DISCOUNT_TIERS:
            if shares_for_sale <= tier["max_shares"]:
                discount_range = tier["discount_range"]
                discount = (discount_range[0] + discount_range[1]) / 2  # Midpoint
                return discount, tier["description"], tier["rationale"]

        # Fallback (should not happen)
        return -Decimal("0.20"), "Standard minority discount", "Minority stake discount"

    def _get_control_premium(self, shares_for_sale: Decimal) -> Tuple[Decimal, str, str]:
        """
        Get control premium for >50% ownership.

        Returns:
            (premium, tier_description, rationale)
        """
        for tier in self.CONTROL_PREMIUM_TIERS:
            min_shares = tier.get("min_shares", 0)
            max_shares = tier.get("max_shares", 100)

            if min_shares <= shares_for_sale <= max_shares:
                premium_range = tier["premium_range"]
                # Convert both values to Decimal to avoid float/Decimal mixing
                premium_min = to_decimal(premium_range[0])
                premium_max = to_decimal(premium_range[1])
                premium = (premium_min + premium_max) / Decimal("2.0")  # Midpoint
                return premium, tier["description"], tier["rationale"]

        # Fallback (should not happen)
        return Decimal("0.15"), "Standard control premium", "Majority control premium"

    def _calculate_deadlock_adjustment(
        self,
        number_of_owners: Optional[int],
        business_type_id: Optional[str],
        business_category: Optional[BusinessTypeCategory],
        revenue: Optional[Decimal],
        valuation_preferences: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Calculate deadlock risk discount for exactly 50% ownership.

        Args:
            number_of_owners: Number of owners (affects deadlock risk)
            business_type_id: Business type ID for logging
            business_category: Business category for calibration
            revenue: Revenue for revenue-based adjustments
            valuation_preferences: Titan-enriched valuation preferences dict

        Returns:
            Dict with deadlock adjustment details
        """
        # Base deadlock discount: -5% to -10%
        # Higher if 2 owners (high deadlock risk), lower if 3+ owners
        if number_of_owners == 2:
            base_discount = to_decimal("-0.10")  # -10% (maximum deadlock risk)
            rationale = "50% ownership with 2 owners creates maximum deadlock risk"
        elif number_of_owners and number_of_owners > 2:
            base_discount = to_decimal("-0.05")  # -5% (moderate deadlock risk)
            rationale = "50% ownership with 3+ owners creates moderate deadlock risk"
        else:
            # Default: assume 2 owners (conservative)
            base_discount = to_decimal("-0.10")
            rationale = "50% ownership creates deadlock risk (assuming 2 owners)"

        # Apply business-type calibration (professional services have higher deadlock risk)
        business_type_multiplier_decimal = to_decimal(
            str(
                self._get_business_type_multiplier(
                    adjustment_type="deadlock_discount",
                    business_category=business_category,
                    business_type_id=business_type_id,
                    valuation_preferences=valuation_preferences,
                )
            )
        )

        # Apply revenue-based adjustment
        revenue_multiplier = self._get_revenue_multiplier(revenue)

        # Calculate final discount using Decimal
        calibrated_discount = base_discount * business_type_multiplier_decimal * revenue_multiplier
        calibrated_discount = max(calibrated_discount, to_decimal("-0.15"))  # Cap at -15%

        adjustment_factor = to_decimal("1.0") + calibrated_discount

        logger.info(
            "Deadlock adjustment calculated",
            number_of_owners=number_of_owners,
            base_discount=from_decimal(base_discount, precision=4),
            business_type_multiplier=from_decimal(business_type_multiplier_decimal, precision=2),
            revenue_multiplier=from_decimal(revenue_multiplier, precision=2),
            calibrated_discount=from_decimal(calibrated_discount, precision=4),
            adjustment_factor=from_decimal(adjustment_factor, precision=4),
        )

        return {
            "adjustment_type": "deadlock_discount",
            "adjustment_percentage": from_decimal(
                calibrated_discount * to_decimal("100"), precision=2
            ),
            "adjustment_factor": from_decimal(adjustment_factor, precision=4),
            "base_adjustment": from_decimal(base_discount, precision=4),
            "base_adjustment_pct": from_decimal(base_discount * to_decimal("100"), precision=2),
            "business_type_multiplier": from_decimal(business_type_multiplier_decimal, precision=2),
            "revenue_multiplier": from_decimal(revenue_multiplier, precision=2),
            "rationale": rationale,
            "tier_description": "Equal control (deadlock risk)",
            "shares_for_sale": Decimal("50.0"),
            "number_of_owners": number_of_owners,
        }

    def _get_business_type_multiplier(
        self,
        adjustment_type: str,
        business_category: Optional["BusinessTypeCategory"],
        business_type_id: Optional[str],
        valuation_preferences: Optional[Dict] = None,
    ) -> Decimal:
        """
        Get business-type-specific calibration multiplier.

        Args:
            adjustment_type: "control_premium", "minority_discount", or "deadlock_discount"
            business_category: Business category for static mapping
            business_type_id: Business type ID for logging
            valuation_preferences: Titan-enriched valuation preferences dict

        Returns:
            Multiplier (typically Decimal('0.8')-Decimal('1.2'))
        """
        # Try static mapping first
        if business_category:
            # Handle both enum and string values
            category_key = business_category.value if hasattr(business_category, 'value') else str(business_category)
            if category_key in self.BUSINESS_TYPE_MULTIPLIERS:
                multipliers = self.BUSINESS_TYPE_MULTIPLIERS[category_key]
                if adjustment_type == "control_premium":
                    multiplier = multipliers[0]  # Control premium multiplier
                else:
                    multiplier = multipliers[1]  # Minority discount or deadlock multiplier

                logger.debug(
                    f"Business-type multiplier from static mapping: {category_key} → {multiplier:.2f}",
                    extra={
                        "business_category": category_key,
                        "adjustment_type": adjustment_type,
                        "multiplier": multiplier,
                    },
                )
                return multiplier

        # Use Titan-enriched valuation_preferences if available, otherwise fall back to defaults
        if valuation_preferences or business_type_id:
            try:
                from src.services.business_type_metadata_service import (
                    get_business_type_metadata_service,
                )

                metadata_service = get_business_type_metadata_service()
                if metadata_service:
                    owner_impact = metadata_service.get_owner_dependency_impact(valuation_preferences)
                    # Higher owner dependency = higher control premium, higher minority discount
                    # Formula: 1.0 + (owner_impact - 0.5) * 0.4
                    # owner_impact 0.0 → multiplier 0.8 (lower adjustments)
                    # owner_impact 0.5 → multiplier 1.0 (standard)
                    # owner_impact 1.0 → multiplier 1.2 (higher adjustments)
                    # Use Decimal for calculation to avoid float precision issues
                    owner_impact_decimal = to_decimal(str(owner_impact))
                    calculated_multiplier_decimal = to_decimal("1.0") + (
                        owner_impact_decimal - to_decimal("0.5")
                    ) * to_decimal("0.4")
                    calculated_multiplier = to_decimal(calculated_multiplier_decimal)

                    logger.debug(
                        f"Business-type multiplier calculated from database: {business_type_id} → {calculated_multiplier:.2f}",
                        extra={
                            "business_type_id": business_type_id,
                            "owner_dependency_impact": owner_impact,
                            "calculated_multiplier": calculated_multiplier,
                            "adjustment_type": adjustment_type,
                        },
                    )
                    return calculated_multiplier
            except (DatabaseError, DataQualityError) as e:
                logger.debug(
                    f"Database lookup failed for business-type multiplier due to data or DB error: {e}",
                    extra={"business_type_id": business_type_id, "error": str(e)},
                )
            except (ValueError, TypeError, AttributeError, KeyError) as e:
                logger.debug(
                    f"An unexpected error occurred during database lookup for business-type multiplier: {e}",
                    extra={
                        "business_type_id": business_type_id,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )

        # Default: standard multiplier
        return Decimal("1.0")

    def _get_revenue_multiplier(self, revenue: Optional[Decimal]) -> Decimal:
        """
        Get revenue-based adjustment multiplier.

        Args:
            revenue: Company revenue

        Returns:
            Multiplier as Decimal (Decimal('0.8')-Decimal('1.0'))
        """
        if revenue is None:
            return to_decimal("1.0")  # Default: full adjustment

        revenue_decimal = to_decimal(revenue) if not isinstance(revenue, Decimal) else revenue

        for tier in self.REVENUE_ADJUSTMENT_MULTIPLIERS:
            max_revenue = tier["max_revenue"]
            if max_revenue is None:
                # This is the last tier (>€25M)
                multiplier = tier["multiplier"]
                logger.debug(
                    f"Revenue multiplier: {from_decimal(revenue_decimal, precision=0):,.0f} → {from_decimal(multiplier, precision=2):.2f}",
                    extra={
                        "revenue": from_decimal(revenue_decimal, precision=2),
                        "multiplier": from_decimal(multiplier, precision=2),
                        "description": tier["description"],
                    },
                )
                return multiplier
            elif revenue_decimal <= max_revenue:
                multiplier = tier["multiplier"]
                logger.debug(
                    f"Revenue multiplier: {from_decimal(revenue_decimal, precision=0):,.0f} → {from_decimal(multiplier, precision=2):.2f}",
                    extra={
                        "revenue": from_decimal(revenue_decimal, precision=2),
                        "multiplier": from_decimal(multiplier, precision=2),
                        "description": tier["description"],
                    },
                )
                return multiplier

        # Fallback (should not happen)
        return to_decimal("1.0")

    def get_adjustment_breakdown(
        self,
        shares_for_sale: Decimal,
        business_type_id: Optional[str] = None,
        revenue: Optional[Decimal] = None,
        number_of_owners: Optional[int] = None,
        business_category: Optional["BusinessTypeCategory"] = None,
    ) -> Dict[str, Any]:
        """
        Get detailed breakdown of ownership adjustment calculation.

        Returns:
            Dict with full calculation breakdown for transparency
        """
        adjustment = self.calculate_ownership_adjustment(
            shares_for_sale=shares_for_sale,
            business_type_id=business_type_id,
            revenue=revenue,
            number_of_owners=number_of_owners,
            business_category=business_category,
        )

        return {
            **adjustment,
            "calculation_steps": {
                "shares_for_sale": shares_for_sale,
                "base_adjustment": adjustment["base_adjustment"],
                "business_type_calibration": adjustment["business_type_multiplier"],
                "revenue_calibration": adjustment["revenue_multiplier"],
                "final_adjustment": adjustment["adjustment_percentage"],
            },
        }
