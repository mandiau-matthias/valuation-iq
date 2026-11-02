"""
Range Methodology Calculator

World-class range methodology calculation following McKinsey/Bain standards with:
- Business-type-specific spread adjustments
- Growth rate integration
- Profitability adjustments
- Data quality integration
- Multi-tier size adjustments
- Asymmetric range options for SMEs

RESEARCH FOUNDATION:
- McKinsey Valuation Handbook, Section Decimal('4.3') (Multiple Dispersion Analysis)
- McKinsey Valuation Handbook, Section Decimal('4.2') (Size-Adjusted Confidence Spreads)
- Bain & Company: "Valuation Uncertainty in Private Markets"
- Damodaran (2018): "The Dark Side of Valuation", Chapter 6
- PwC Valuation Handbook 2024, Section Decimal('4.2')
- Big 4 Standards: Asymmetric risk assessment for SMEs

METHODOLOGY:
The calculator determines valuation ranges using either:
1. Multiple Dispersion (preferred): Uses P25/P50/P75 from comparables
2. Confidence Spread (fallback): Uses confidence score with enhancements

Enhanced Confidence Spread Formula:
Total Spread = Base Spread × Business Type Multiplier + Size Adjustment + Growth Adjustment + Profitability Adjustment - Data Quality Adjustment
"""

from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from src.domain.interfaces.business_type_protocol import BusinessTypeCategory
from src.errors.error_types import DatabaseError, DataQualityError
from src.utils.decimal_helpers import Money, from_decimal, safe_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class RangeMethodologyCalculator:
    """
    World-class range methodology calculator with business-type-specific adjustments.

    Implements enhanced confidence spread calculation with:
    - Business-type multipliers (SaaS vs Manufacturing vs Services)
    - Growth rate adjustments (validated vs unvalidated growth)
    - Profitability adjustments (profitable vs unprofitable)
    - Data quality integration (higher quality = tighter spreads)
    - Multi-tier size adjustments (beyond simple <€5M)
    - Asymmetric ranges for SMEs (downside risk > upside potential)
    """

    # Base spread by confidence level (as Decimal)
    BASE_SPREAD_HIGH = to_decimal("0.12")  # ±12% for high confidence (≥80%)
    BASE_SPREAD_MEDIUM = to_decimal("0.18")  # ±18% for medium confidence (60-79%)
    BASE_SPREAD_LOW = to_decimal("0.22")  # ±22% for low confidence (<60%)

    # Size tier adjustments (as Decimal percentages)
    SIZE_ADJUSTMENT_MICRO = to_decimal("0.10")  # +10% for <€1M
    SIZE_ADJUSTMENT_SMALL = to_decimal("0.07")  # +7% for €1M-€5M
    SIZE_ADJUSTMENT_MEDIUM = to_decimal("0.00")  # +0% for €5M-€25M
    SIZE_ADJUSTMENT_LARGE = to_decimal("-0.02")  # -2% for €25M-€100M
    SIZE_ADJUSTMENT_ENTERPRISE = to_decimal("-0.04")  # -4% for ≥€100M

    # Business-type multipliers (affect base spread)
    # Using string keys to avoid circular import
    BUSINESS_TYPE_MULTIPLIERS = {
        "saas_software": to_decimal("0.85"),  # Tighter spreads - validated business model
        "ecommerce": to_decimal("0.95"),  # Tighter spreads - scalable
        "professional_services": to_decimal("1.15"),  # Wider spreads - owner dependency
        "manufacturing": to_decimal("1.10"),  # Wider spreads - asset intensity
        "retail_food": to_decimal("1.05"),  # Moderate spreads - location dependent
        "construction": to_decimal("1.12"),  # Wider spreads - project volatility
        "healthcare": to_decimal("1.08"),  # Moderate spreads - regulatory risk
        "financial_services": to_decimal("1.10"),  # Wider spreads - regulatory risk
        "real_estate": to_decimal("1.05"),  # Moderate spreads - market dependent
        "transportation": to_decimal("1.08"),  # Moderate spreads - operational risk
        "other": to_decimal("1.00"),  # Default - no adjustment
    }

    # Growth rate adjustments (as Decimal percentages)
    GROWTH_ADJUSTMENT_HIGH_VALIDATED = to_decimal(
        "-0.02"
    )  # -2% for high growth (>30%) if validated
    GROWTH_ADJUSTMENT_HIGH_UNVALIDATED = to_decimal(
        "0.03"
    )  # +3% for high growth (>30%) if unvalidated
    GROWTH_ADJUSTMENT_MEDIUM_VALIDATED = to_decimal(
        "-0.01"
    )  # -1% for medium growth (15-30%) if validated
    GROWTH_ADJUSTMENT_MEDIUM_UNVALIDATED = to_decimal(
        "0.01"
    )  # +1% for medium growth (15-30%) if unvalidated
    GROWTH_ADJUSTMENT_LOW = to_decimal("0.00")  # +0% for low growth (<15%)

    # Profitability adjustments (as Decimal percentages)
    PROFITABILITY_ADJUSTMENT_PROFITABLE = to_decimal("-0.01")  # -1% for EBITDA margin >10%
    PROFITABILITY_ADJUSTMENT_BREAKEVEN = to_decimal("0.00")  # +0% for EBITDA margin 0-10%
    PROFITABILITY_ADJUSTMENT_UNPROFITABLE = to_decimal("0.03")  # +3% for EBITDA margin <0%

    # Data quality adjustments (as Decimal percentages, subtracted from spread)
    DATA_QUALITY_ADJUSTMENT_HIGH = to_decimal("0.02")  # -2% for quality ≥80
    DATA_QUALITY_ADJUSTMENT_MEDIUM = to_decimal("0.01")  # -1% for quality 60-79
    DATA_QUALITY_ADJUSTMENT_LOW = to_decimal("0.00")  # +0% for quality <60

    # Asymmetric range parameters for SMEs
    ASYMMETRIC_DOWNSIDE_SME = to_decimal("0.22")  # -22% downside for SMEs
    ASYMMETRIC_UPSIDE_SME = to_decimal("0.16")  # +16% upside for SMEs

    def __init__(self):
        """Initialize the range methodology calculator."""
        self.logger = logger

    def calculate_confidence_spread(
        self,
        confidence_score: int,
        revenue: Money,
        business_category: Optional[BusinessTypeCategory] = None,
        growth_rate: Optional[Decimal] = None,
        growth_validated: bool = False,
        ebitda_margin: Optional[Decimal] = None,
        data_quality_score: Optional[int] = None,
        business_type_id: Optional[str] = None,
        valuation_preferences: Optional[Dict] = None,
        min_band_half_width: Optional[Decimal] = None,
    ) -> Dict[str, Any]:
        """
        Calculate enhanced confidence spread with all adjustment factors.

        Formula:
        Total Spread = Base Spread × Business Type Multiplier + Size Adjustment + Growth Adjustment + Profitability Adjustment - Data Quality Adjustment

        Args:
            confidence_score: Confidence score (0-100)
            revenue: Company revenue (Decimal)
            business_category: Business type category (optional)
            growth_rate: Revenue growth rate as decimal (e.g., Decimal('0.30') for 30%)
            growth_validated: Whether growth is validated by historical data
            ebitda_margin: EBITDA margin as decimal (e.g., Decimal('0.15') for 15%)
            data_quality_score: Data quality score (0-100)
            business_type_id: Optional business type ID for logging
            valuation_preferences: Titan-enriched valuation preferences dict
            min_band_half_width: Optional lifecycle-stage honest floor (fraction of the
                base). The "watch the band tighten" ladder is owned by titan
                (``BAND_FLOOR_BY_STAGE``); when the caller knows the company's stage it
                passes that stage's minimum here so the RAW emitted band is never tighter
                than the stage warrants (keeping the report band consistent with the
                stage-floored card). Widen-only — it never tightens a wider, more-uncertain
                band — and bounded by the 0.35 ceiling. ``None`` ⇒ no-op (current behaviour).

        Returns:
            Dict with:
            - total_spread: Total spread as Decimal
            - base_spread: Base spread from confidence
            - size_adjustment: Size tier adjustment
            - business_type_multiplier: Business type multiplier
            - growth_adjustment: Growth rate adjustment
            - profitability_adjustment: Profitability adjustment
            - data_quality_adjustment: Data quality adjustment (subtracted)
            - breakdown: Detailed breakdown for transparency
        """
        # Calculate base spread from confidence score
        base_spread = self._calculate_base_spread(confidence_score)

        # Calculate size adjustment
        size_adjustment = self.calculate_size_adjustment(revenue)

        business_type_multiplier = self.calculate_business_type_multiplier(
            business_category, business_type_id, valuation_preferences
        )

        # Apply business type multiplier to base spread
        adjusted_base_spread = base_spread * business_type_multiplier

        # Calculate growth adjustment
        growth_adjustment = self.calculate_growth_adjustment(growth_rate, growth_validated)

        # Calculate profitability adjustment
        profitability_adjustment = self.calculate_profitability_adjustment(ebitda_margin)

        # Calculate data quality adjustment (subtracted from spread)
        data_quality_adjustment = self.calculate_data_quality_adjustment(data_quality_score)

        # Calculate total spread
        total_spread = (
            adjusted_base_spread
            + size_adjustment
            + growth_adjustment
            + profitability_adjustment
            - data_quality_adjustment
        )

        # Ensure spread is within reasonable bounds (0.05 to 0.35)
        total_spread = max(to_decimal("0.05"), min(to_decimal("0.35"), total_spread))

        # Lifecycle-stage honest floor (the SSOT "watch the band tighten" ladder, owned
        # by titan ``BAND_FLOOR_BY_STAGE``). Widen-only and bounded by the 0.35 ceiling,
        # so it can only make an early-stage band MORE conservative — never tighter than
        # the measured uncertainty. Default None ⇒ byte-identical to today.
        stage_floor_applied: Optional[Decimal] = None
        if min_band_half_width is not None:
            stage_floor = min(to_decimal("0.35"), to_decimal(str(min_band_half_width)))
            if stage_floor > total_spread:
                total_spread = stage_floor
                stage_floor_applied = stage_floor

        # Use from_decimal for JSON serialization in breakdown dict
        breakdown = {
            "base_spread": from_decimal(base_spread, precision=4),
            "business_type_multiplier": from_decimal(business_type_multiplier, precision=4),
            "adjusted_base_spread": from_decimal(adjusted_base_spread, precision=4),
            "size_adjustment": from_decimal(size_adjustment, precision=4),
            "growth_adjustment": from_decimal(growth_adjustment, precision=4),
            "profitability_adjustment": from_decimal(profitability_adjustment, precision=4),
            "data_quality_adjustment": from_decimal(data_quality_adjustment, precision=4),
            "total_spread": from_decimal(total_spread, precision=4),
            "total_spread_percentage": f'±{from_decimal(total_spread * Decimal("100"), precision=0):.0f}%',
            "stage_floor_applied": (
                from_decimal(stage_floor_applied, precision=4)
                if stage_floor_applied is not None
                else None
            ),
        }

        # DEBUG: per-spread diagnostic; the Step 10 / Step 11 exit logs
        # carry the final low/mid/high range.
        self.logger.debug(
            "Enhanced confidence spread calculated",
            extra={
                "confidence_score": confidence_score,
                "total_spread": from_decimal(total_spread, precision=4),
                "breakdown": breakdown,
            },
        )

        return {
            "total_spread": total_spread,
            "base_spread": base_spread,
            "size_adjustment": size_adjustment,
            "business_type_multiplier": business_type_multiplier,
            "growth_adjustment": growth_adjustment,
            "profitability_adjustment": profitability_adjustment,
            "data_quality_adjustment": data_quality_adjustment,
            "breakdown": breakdown,
        }

    def _calculate_base_spread(self, confidence_score: int) -> Decimal:
        """
        Calculate base spread from confidence score.

        Args:
            confidence_score: Confidence score (0-100)

        Returns:
            Base spread as Decimal
        """
        if confidence_score >= 80:
            return self.BASE_SPREAD_HIGH
        elif confidence_score >= 60:
            return self.BASE_SPREAD_MEDIUM
        else:
            return self.BASE_SPREAD_LOW

    def calculate_size_adjustment(self, revenue: Money) -> Decimal:
        """
        Calculate size adjustment based on revenue tier.

        Size Tiers:
        - Micro (<€1M): +10%
        - Small (€1M-€5M): +7%
        - Medium (€5M-€25M): +0%
        - Large (€25M-€100M): -2%
        - Enterprise (≥€100M): -4%

        Args:
            revenue: Company revenue (Decimal)

        Returns:
            Size adjustment as Decimal
        """
        revenue_decimal = to_decimal(revenue) if not isinstance(revenue, Decimal) else revenue

        if revenue_decimal < to_decimal("1000000"):
            return self.SIZE_ADJUSTMENT_MICRO
        elif revenue_decimal < to_decimal("5000000"):
            return self.SIZE_ADJUSTMENT_SMALL
        elif revenue_decimal < to_decimal("25000000"):
            return self.SIZE_ADJUSTMENT_MEDIUM
        elif revenue_decimal < to_decimal("100000000"):
            return self.SIZE_ADJUSTMENT_LARGE
        else:
            return self.SIZE_ADJUSTMENT_ENTERPRISE

    def calculate_business_type_multiplier(
        self,
        business_category: Optional[BusinessTypeCategory],
        business_type_id: Optional[str] = None,
        valuation_preferences: Optional[Dict] = None,
    ) -> Decimal:
        """
        Calculate business type multiplier.

        Business-Type Multipliers:
        - SaaS/Software: 0.85x (tighter spreads)
        - Professional Services: 1.15x (wider spreads)
        - Manufacturing: 1.10x (wider spreads)
        - Retail/Food: 1.05x (moderate spreads)
        - E-commerce: 0.95x (tighter spreads)
        - Default: 1.0x

        Args:
            business_category: Business type category (optional)
            business_type_id: Optional business type ID for logging
            valuation_preferences: Titan-enriched valuation preferences dict

        Returns:
            Business type multiplier as Decimal
        """
        if business_category is None:
            return to_decimal("1.0")

        # Handle both enum and string values
        category_key = business_category.value if hasattr(business_category, 'value') else str(business_category)
        multiplier = self.BUSINESS_TYPE_MULTIPLIERS.get(category_key, None)

        # Use Titan-enriched valuation_preferences if available, otherwise fall back to defaults
        if multiplier is None and (valuation_preferences or business_type_id):
            try:
                from src.services.business_type_metadata_service import (
                    get_business_type_metadata_service,
                )

                metadata_service = get_business_type_metadata_service()
                if metadata_service:
                    owner_impact = metadata_service.get_owner_dependency_impact(valuation_preferences)
                    # Higher owner dependency = wider spreads (higher multiplier)
                    # Formula: 1.0 + (owner_impact - 0.5) * 0.3
                    # owner_impact 0.0 → multiplier 0.85 (tighter spreads)
                    # owner_impact 0.5 → multiplier 1.0 (standard)
                    # owner_impact 1.0 → multiplier 1.15 (wider spreads)
                    # Use Decimal for calculation to avoid float precision issues
                    owner_impact_decimal = to_decimal(str(owner_impact))
                    calculated_multiplier_decimal = to_decimal("1.0") + (
                        owner_impact_decimal - to_decimal("0.5")
                    ) * to_decimal("0.3")
                    calculated_multiplier = to_decimal(calculated_multiplier_decimal)

                    logger.debug(
                        f"Range methodology multiplier calculated from database: {business_type_id} → {calculated_multiplier:.2f}",
                        extra={
                            "business_type_id": business_type_id,
                            "owner_dependency_impact": owner_impact,
                            "calculated_multiplier": calculated_multiplier,
                        },
                    )
                    return to_decimal(str(calculated_multiplier))
            except (DatabaseError, DataQualityError) as e:
                logger.debug(
                    f"Database lookup failed for range methodology multiplier due to data or DB error: {e}",
                    extra={"business_type_id": business_type_id, "error": str(e)},
                )
            except (ValueError, TypeError, AttributeError, KeyError) as e:
                logger.debug(
                    f"An unexpected error occurred during database lookup for range methodology multiplier: {e}",
                    extra={
                        "business_type_id": business_type_id,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )

        # Use static mapping (or default if not found)
        if multiplier is None:
            multiplier = to_decimal("1.0")

        return multiplier

    def calculate_growth_adjustment(
        self, growth_rate: Optional[Decimal], growth_validated: bool = False
    ) -> Decimal:
        """
        Calculate growth rate adjustment.

        Growth Rate Adjustments:
        - High growth (>30%): -2% if validated, +3% if unvalidated
        - Medium growth (15-30%): -1% if validated, +1% if unvalidated
        - Low growth (<15%): +0%
        - Declining revenue (<-20% CAGR): +15% (wider spreads for declining businesses)
        - Moderate decline (-10% to -20%): +8% (moderate spread increase)

        Args:
            growth_rate: Revenue growth rate as decimal (e.g., Decimal('0.30') for 30%, -Decimal('0.26') for -26%)
            growth_validated: Whether growth is validated by historical data

        Returns:
            Growth adjustment as Decimal
        """
        if growth_rate is None:
            return to_decimal("0.00")

        growth_decimal = to_decimal(str(growth_rate))

        # Handle declining revenue scenarios (negative growth)
        # Academic Source: McKinsey (2015, "Valuation", Ch. 10, p. 312-340)
        # Declining businesses require wider ranges due to higher uncertainty
        if growth_decimal < to_decimal("-0.20"):  # CAGR < -20%
            # Significant decline: Apply +15% spread adjustment for ±33.3% total range
            return to_decimal("0.15")
        elif growth_decimal < to_decimal("-0.10"):  # CAGR -10% to -20%
            # Moderate decline: Apply +8% spread adjustment
            return to_decimal("0.08")

        # Handle positive growth scenarios
        if growth_decimal > to_decimal("0.30"):  # >30%
            if growth_validated:
                return self.GROWTH_ADJUSTMENT_HIGH_VALIDATED
            else:
                return self.GROWTH_ADJUSTMENT_HIGH_UNVALIDATED
        elif growth_decimal >= to_decimal("0.15"):  # 15-30%
            if growth_validated:
                return self.GROWTH_ADJUSTMENT_MEDIUM_VALIDATED
            else:
                return self.GROWTH_ADJUSTMENT_MEDIUM_UNVALIDATED
        else:  # <15% (including 0% to -10%)
            return self.GROWTH_ADJUSTMENT_LOW

    def calculate_profitability_adjustment(self, ebitda_margin: Optional[Decimal]) -> Decimal:
        """
        Calculate profitability adjustment.

        Profitability Adjustments:
        - Profitable (EBITDA margin >10%): -1%
        - Break-even (0-10%): +0%
        - Unprofitable (<0%): +3%

        Args:
            ebitda_margin: EBITDA margin as decimal (e.g., Decimal('0.15') for 15%)

        Returns:
            Profitability adjustment as Decimal
        """
        if ebitda_margin is None:
            return to_decimal("0.00")

        margin_decimal = to_decimal(str(ebitda_margin))

        if margin_decimal > to_decimal("0.10"):  # >10%
            return self.PROFITABILITY_ADJUSTMENT_PROFITABLE
        elif margin_decimal >= to_decimal("0.00"):  # 0-10%
            return self.PROFITABILITY_ADJUSTMENT_BREAKEVEN
        else:  # <0%
            return self.PROFITABILITY_ADJUSTMENT_UNPROFITABLE

    def calculate_data_quality_adjustment(self, data_quality_score: Optional[int]) -> Decimal:
        """
        Calculate data quality adjustment (subtracted from spread).

        Data Quality Adjustments:
        - High quality (≥80): -2%
        - Medium quality (60-79): -1%
        - Low quality (<60): +0%

        Args:
            data_quality_score: Data quality score (0-100)

        Returns:
            Data quality adjustment as Decimal (to be subtracted)
        """
        if data_quality_score is None:
            return to_decimal("0.00")

        if data_quality_score >= 80:
            return self.DATA_QUALITY_ADJUSTMENT_HIGH
        elif data_quality_score >= 60:
            return self.DATA_QUALITY_ADJUSTMENT_MEDIUM
        else:
            return self.DATA_QUALITY_ADJUSTMENT_LOW

    def should_use_asymmetric_range(
        self,
        revenue: Money,
        business_category: Optional[BusinessTypeCategory],
        ebitda_margin: Optional[Decimal],
    ) -> bool:
        """
        Determine if asymmetric range should be used.

        Decision Logic:
        - Use asymmetric if: SME (<€5M) + Unprofitable + Professional Services
        - Otherwise use symmetric spread

        Args:
            revenue: Company revenue (Decimal)
            business_category: Business type category (optional)
            ebitda_margin: EBITDA margin as decimal (optional)

        Returns:
            True if asymmetric range should be used, False otherwise
        """
        revenue_decimal = to_decimal(revenue) if not isinstance(revenue, Decimal) else revenue

        # Must be SME (<€5M)
        if revenue_decimal >= to_decimal("5000000"):
            return False

        # Must be unprofitable
        if ebitda_margin is not None:
            margin_decimal = to_decimal(str(ebitda_margin))
            if margin_decimal >= to_decimal("0.00"):
                return False

        # Prefer asymmetric for Professional Services (owner dependency risk)
        if business_category == BusinessTypeCategory.PROFESSIONAL_SERVICES:
            return True

        # Also use for other business types if unprofitable SME
        return True

    def calculate_asymmetric_range(
        self, equity_mid: Money, business_category: Optional["BusinessTypeCategory"] = None
    ) -> Dict[str, Any]:
        """
        Calculate asymmetric range for SMEs reflecting higher downside risk.

        Asymmetric Spreads:
        - Downside: -20% to -25% (higher risk)
        - Upside: +15% to +18% (lower potential)

        Args:
            equity_mid: Mid-point equity value (Decimal)
            business_category: Business type category (optional)

        Returns:
            Dict with:
            - equity_low: Low estimate (Decimal)
            - equity_mid: Mid-point (preserved)
            - equity_high: High estimate (Decimal)
            - downside_percentage: Downside percentage
            - upside_percentage: Upside percentage
            - methodology: "Asymmetric Range"
        """
        equity_mid_decimal = (
            to_decimal(equity_mid) if not isinstance(equity_mid, Decimal) else equity_mid
        )

        # Adjust downside/upside based on business type
        if business_category:
            category_key = business_category.value if hasattr(business_category, 'value') else str(business_category)
            if category_key == "professional_services":
                downside_pct = to_decimal("0.25")  # -25% for professional services
                upside_pct = to_decimal("0.15")  # +15% for professional services
            else:
                downside_pct = self.ASYMMETRIC_DOWNSIDE_SME  # -22%
                upside_pct = self.ASYMMETRIC_UPSIDE_SME  # +16%
        else:
            downside_pct = self.ASYMMETRIC_DOWNSIDE_SME  # -22%
            upside_pct = self.ASYMMETRIC_UPSIDE_SME  # +16%

        # Calculate range
        equity_low = equity_mid_decimal * (to_decimal("1") - downside_pct)
        equity_high = equity_mid_decimal * (to_decimal("1") + upside_pct)

        self.logger.debug(
            "Asymmetric range calculated for SME",
            extra={
                "equity_mid": from_decimal(equity_mid_decimal, precision=2),
                "equity_low": from_decimal(equity_low, precision=2),
                "equity_high": from_decimal(equity_high, precision=2),
                "downside_pct": from_decimal(downside_pct, precision=4),
                "upside_pct": from_decimal(upside_pct, precision=4),
                "business_category": business_category.value if business_category else None,
            },
        )

        return {
            "equity_low": equity_low,
            "equity_mid": equity_mid_decimal,
            "equity_high": equity_high,
            "downside_percentage": from_decimal(downside_pct, precision=4),
            "upside_percentage": from_decimal(upside_pct, precision=4),
            "methodology": "Asymmetric Range",
        }

    def calculate_symmetric_range(self, equity_mid: Money, total_spread: Decimal) -> Dict[str, Any]:
        """
        Calculate symmetric range using total spread.

        Args:
            equity_mid: Mid-point equity value (Decimal)
            total_spread: Total spread as Decimal

        Returns:
            Dict with:
            - equity_low: Low estimate (Decimal)
            - equity_mid: Mid-point (preserved)
            - equity_high: High estimate (Decimal)
            - methodology: "Confidence Spread"
        """
        equity_mid_decimal = (
            to_decimal(equity_mid) if not isinstance(equity_mid, Decimal) else equity_mid
        )

        # Calculate range
        one_minus_spread = to_decimal("1") - total_spread
        one_plus_spread = to_decimal("1") + total_spread

        equity_low = equity_mid_decimal * one_minus_spread
        equity_high = equity_mid_decimal * one_plus_spread

        return {
            "equity_low": equity_low,
            "equity_mid": equity_mid_decimal,
            "equity_high": equity_high,
            "methodology": "Confidence Spread",
        }
