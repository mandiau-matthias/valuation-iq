"""
Owner Concentration Calibration Module

Calibrates owner concentration tiers and discounts based on business type characteristics.
Uses owner_dependency_impact (Decimal('0.0')-Decimal('1.0')) from business_types database to adjust:
  1. Tier thresholds (when risk kicks in)
  2. Discount magnitudes (how much risk matters)

Example: Professional services (high dependency) get stricter thresholds and larger discounts
         Manufacturing (low dependency) gets relaxed thresholds and smaller discounts
"""

from decimal import Decimal
from typing import Any, Dict, List

from src.utils.decimal_helpers import bank_round, from_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class OwnerConcentrationCalibrator:
    """
    Calibrates owner concentration tiers based on business type characteristics.

    Uses owner_dependency_impact (Decimal('0.0')-Decimal('1.0')) to adjust:
      1. Tier thresholds (when risk kicks in)
      2. Discount magnitudes (how much risk matters)
    """

    # Base configuration (universal defaults)
    BASE_TIERS = [
        {"min_ratio": Decimal("0.50"), "adjustment": Decimal("-0.20"), "risk_level": "CRITICAL"},
        {"min_ratio": Decimal("0.25"), "adjustment": Decimal("-0.12"), "risk_level": "HIGH"},
        {"min_ratio": Decimal("0.10"), "adjustment": Decimal("-0.07"), "risk_level": "MEDIUM"},
        {"min_ratio": Decimal("0.00"), "adjustment": Decimal("-0.03"), "risk_level": "LOW"},
    ]

    # Calibration bounds (prevent extreme adjustments)
    MIN_CRITICAL_THRESHOLD = Decimal("0.35")  # Never go below 35%
    MAX_CRITICAL_THRESHOLD = Decimal("0.65")  # Never go above 65%
    MIN_DISCOUNT_MULTIPLIER = Decimal("0.70")  # Max 30% reduction in discounts
    MAX_DISCOUNT_MULTIPLIER = Decimal("1.40")  # Max 40% increase in discounts

    @staticmethod
    def calibrate_tiers(owner_dependency_impact: Decimal) -> List[Dict[str, Any]]:
        """
        Calibrate tier thresholds and discounts based on owner dependency.

        Args:
            owner_dependency_impact: Decimal('0.0') to Decimal('1.0') (from database)
                - 0.0: No dependency (asset-based business)
                - 0.5: Medium dependency (standard operations)
                - 1.0: Complete dependency (expert-driven services)

        Returns:
            Calibrated tier configuration with adjusted thresholds and discounts

        Examples:
            >>> # Professional Services (high dependency = Decimal('0.85'))
            >>> tiers = OwnerConcentrationCalibrator.calibrate_tiers(Decimal('0.85'))
            >>> # Returns stricter thresholds (e.g., CRITICAL at 42% vs 50%)
            >>> # and larger discounts (e.g., -22% vs -20%)

            >>> # Manufacturing (low dependency = Decimal('0.30'))
            >>> tiers = OwnerConcentrationCalibrator.calibrate_tiers(Decimal('0.30'))
            >>> # Returns relaxed thresholds (e.g., CRITICAL at 58% vs 50%)
            >>> # and smaller discounts (e.g., -16% vs -20%)
        """
        owner_dependency_impact_decimal = to_decimal(owner_dependency_impact)
        # Clamp input to valid range
        owner_dependency_impact_decimal = max(
            Decimal("0.0"), min(Decimal("1.0"), owner_dependency_impact_decimal)
        )

        # Threshold calibration (inverse relationship)
        # High dependency (0.85) → Lower thresholds (more sensitive)
        # Low dependency (0.30) → Higher thresholds (less sensitive)
        threshold_factor = Decimal("1.0") + (Decimal("0.5") - owner_dependency_impact_decimal)
        threshold_factor = max(
            Decimal("0.70"), min(Decimal("1.30"), threshold_factor)
        )  # Clamp to ±30%

        # Discount calibration (direct relationship)
        # High dependency (0.85) → Larger discounts
        # Low dependency (0.30) → Smaller discounts
        discount_factor = Decimal("0.5") + (owner_dependency_impact_decimal * Decimal("1.0"))
        discount_factor = max(
            OwnerConcentrationCalibrator.MIN_DISCOUNT_MULTIPLIER,
            min(OwnerConcentrationCalibrator.MAX_DISCOUNT_MULTIPLIER, discount_factor),
        )

        logger.info(
            "Calibrating owner concentration tiers",
            owner_dependency_impact=from_decimal(bank_round(owner_dependency_impact_decimal, 2)),
            threshold_factor=from_decimal(bank_round(threshold_factor, 2)),
            discount_factor=from_decimal(bank_round(discount_factor, 2)),
        )

        # Apply calibration to base tiers
        calibrated_tiers = []
        for base_tier in OwnerConcentrationCalibrator.BASE_TIERS:
            calibrated_tier = {
                "min_ratio": base_tier["min_ratio"] * threshold_factor,
                "adjustment": base_tier["adjustment"] * discount_factor,
                "risk_level": base_tier["risk_level"],
            }
            # Clamp thresholds to reasonable bounds [0.0, 1.0]
            calibrated_tier["min_ratio"] = max(
                Decimal("0.0"), min(Decimal("1.0"), calibrated_tier["min_ratio"])
            )

            # Round for readability
            calibrated_tier["min_ratio"] = bank_round(calibrated_tier["min_ratio"], 3)
            calibrated_tier["adjustment"] = bank_round(calibrated_tier["adjustment"], 4)

            calibrated_tiers.append(calibrated_tier)

        logger.debug(
            "Calibrated tiers generated",
            critical_threshold=from_decimal(calibrated_tiers[0]["min_ratio"]),
            critical_discount=from_decimal(calibrated_tiers[0]["adjustment"]),
        )

        return calibrated_tiers

    @staticmethod
    def get_tier_description(
        owner_dependency_impact: Decimal, business_type_name: str = "this business type"
    ) -> str:
        """
        Generate human-readable description of calibration.

        Args:
            owner_dependency_impact: Decimal('0.0') to Decimal('1.0')
            business_type_name: Name of business type for description

        Returns:
            Human-readable calibration description
        """
        owner_dependency_impact_decimal = to_decimal(owner_dependency_impact)
        impact_pct = from_decimal(owner_dependency_impact_decimal * Decimal("100"))

        if owner_dependency_impact_decimal >= Decimal("0.8"):
            return (
                f"{business_type_name} has very high owner dependency (impact: {impact_pct:.1f}%). "
                f"Valuation adjustments use stricter thresholds and larger discounts to reflect "
                f"critical expertise and relationship dependency."
            )
        elif owner_dependency_impact_decimal >= Decimal("0.6"):
            return (
                f"{business_type_name} has high owner dependency (impact: {impact_pct:.1f}%). "
                f"Valuation adjustments use moderately stricter thresholds to reflect "
                f"significant operational and client relationship dependency."
            )
        elif owner_dependency_impact_decimal >= Decimal("0.4"):
            return (
                f"{business_type_name} has medium owner dependency (impact: {impact_pct:.1f}%). "
                f"Valuation adjustments use standard thresholds similar to universal defaults."
            )
        elif owner_dependency_impact_decimal >= Decimal("0.2"):
            return (
                f"{business_type_name} has low owner dependency (impact: {impact_pct:.1f}%). "
                f"Valuation adjustments use relaxed thresholds to reflect "
                f"operational independence and process-driven business model."
            )
        else:
            return (
                f"{business_type_name} has very low owner dependency (impact: {impact_pct:.1f}%). "
                f"Valuation adjustments use significantly relaxed thresholds to reflect "
                f"asset-based or highly systematized operations."
            )
