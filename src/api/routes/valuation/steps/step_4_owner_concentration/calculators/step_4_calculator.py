"""
Step 4 Calculator

Calculates owner/employee ratios and adjustments.
"""

import math
from decimal import Decimal
from typing import Optional, Tuple

from src.api.routes.valuation.steps.step_4_owner_concentration.number_guards import (
    is_infinite_number,
)
from src.config.decimal_constants import DecimalConstants
from src.utils.decimal_helpers import to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class Step4Calculator:
    """Calculates ratios and adjustments for Step 4."""

    def calculate_owner_employee_ratio(
        self, num_owners: int, num_employees: int
    ) -> Tuple[Decimal, Optional[str]]:
        """
        Calculate owner/employee ratio.

        Args:
            num_owners: Number of owners
            num_employees: Number of employees

        Returns:
            Tuple of (raw_ratio, warning_message) - raw_ratio is Decimal for bank-grade precision
        """
        if num_employees == 0:
            # Cap at 10.0 instead of Infinity to prevent NaN issues
            raw_ratio = Decimal("10.0")
            logger.warning(
                "⚠️ Zero employees detected: Capping ratio at Decimal('10.0') (maximum risk)",
                extra={
                    "num_owners": num_owners,
                    "num_employees": num_employees,
                    "raw_ratio": raw_ratio,
                },
            )
            return raw_ratio, "Zero employees - ratio capped at 10.0"
        elif num_employees > 0 and num_owners > 0:
            raw_ratio = num_owners / num_employees
            # Validate result
            if math.isnan(raw_ratio) or math.isinf(raw_ratio):
                logger.error(
                    "❌ Division produced invalid result (NaN/Infinity), capping at 10.0",
                    extra={
                        "num_owners": num_owners,
                        "num_employees": num_employees,
                        "raw_ratio": raw_ratio,
                    },
                )
                return Decimal("10.0"), "Invalid ratio - capped at 10.0"
            logger.debug(
                "✅ Owner concentration ratio calculated",
                extra={
                    "raw_ratio": raw_ratio,
                    "calculation": f"{num_owners} / {num_employees} = {raw_ratio}",
                },
            )
            return raw_ratio, None
        else:
            # Invalid: negative or zero owners with positive employees
            raw_ratio = Decimal("0.0")
            logger.warning(
                "⚠️ Invalid owner/employee data: Zero or negative owners",
                extra={
                    "num_owners": num_owners,
                    "num_employees": num_employees,
                    "raw_ratio": raw_ratio,
                },
            )
            return raw_ratio, "Invalid data - zero or negative owners"

    def normalize_ratio(
        self, raw_ratio: Decimal, num_owners: int, is_true_sole_trader: bool
    ) -> Decimal:
        """
        Normalize ratio for domain class tier lookup.

        Args:
            raw_ratio: Raw owner/employee ratio
            num_owners: Number of owners
            is_true_sole_trader: Whether this is a true sole trader

        Returns:
            Normalized ratio
        """
        if is_infinite_number(raw_ratio) or is_true_sole_trader:
            normalized_ratio = Decimal("1.0")
            logger.debug(
                "📊 Ratio normalized (infinite ratio or sole trader)",
                extra={
                    "raw_ratio": str(raw_ratio),
                    "normalized_ratio": normalized_ratio,
                    "is_true_sole_trader": is_true_sole_trader,
                    "num_owners": num_owners,
                },
            )
        elif raw_ratio > Decimal("1.0"):
            # Partnership with ratio > 1.0 - pass through to domain class
            normalized_ratio = raw_ratio
            logger.warning(
                "🔍 [CALCULATOR] Ratio kept as-is for partnership (ratio > 1.0)",
                raw_ratio=float(raw_ratio),
                normalized_ratio=float(normalized_ratio),
                is_true_sole_trader=is_true_sole_trader,
                num_owners=num_owners,
                note="This should trigger CRITICAL tier in domain class",
            )
        else:
            # Normal ratio (≤1.0) - use as-is
            normalized_ratio = min(Decimal("1.0"), max(Decimal("0.0"), raw_ratio))
            logger.debug(
                "📊 Ratio normalized for tier lookup",
                extra={
                    "raw_ratio": float(raw_ratio),
                    "normalized_ratio": float(normalized_ratio),
                    "is_true_sole_trader": is_true_sole_trader,
                },
            )

        # Diagnostic trace — promoted from `logger.warning` to `debug`
        # (Pass-9 cleanup). Was producing `[wrn]` entries on every Step 4
        # run despite being a non-actionable "I'm about to return" trace,
        # cluttering production audit feeds. Kept structured for replay.
        logger.debug(
            "[CALCULATOR] normalize_ratio() returning",
            raw_ratio=float(raw_ratio),
            normalized_ratio_final=float(normalized_ratio),
            num_owners=num_owners,
        )
        return normalized_ratio

    def validate_and_normalize_adjustment(
        self, adjustment: any, normalized_ratio: Decimal, num_owners: int, num_employees: int
    ) -> Tuple[float, str]:
        """
        Validate and normalize adjustment from domain class.

        Args:
            adjustment: Adjustment value from domain class
            normalized_ratio: Normalized owner/employee ratio
            num_owners: Number of owners
            num_employees: Number of employees

        Returns:
            Tuple of (validated_adjustment, risk_level)
        """
        # Diagnostic trace — Pass-9 demoted from warning to debug.
        logger.debug(
            "[CALCULATOR] validate_and_normalize_adjustment() ENTRY",
            adjustment_input=float(adjustment) if adjustment is not None else None,
            adjustment_type=type(adjustment).__name__,
            normalized_ratio=float(normalized_ratio),
            num_owners=num_owners,
            num_employees=num_employees,
        )

        # DEFENSIVE CHECK: Validate adjustment is not None and is a valid number
        if adjustment is None:
            logger.error(
                "CRITICAL: Owner concentration adjustment is None, using minimum discount",
                normalized_ratio=float(normalized_ratio),
                num_owners=num_owners,
                num_employees=num_employees,
            )
            return to_decimal(DecimalConstants.OWNER_CONCENTRATION_MINIMUM), "LOW"
        elif not isinstance(adjustment, (int, float, Decimal)):
            logger.error(
                "CRITICAL: Owner concentration adjustment is not a number, using minimum discount",
                normalized_ratio=float(normalized_ratio),
                adjustment_type=type(adjustment).__name__,
                num_owners=num_owners,
                num_employees=num_employees,
            )
            return to_decimal(DecimalConstants.OWNER_CONCENTRATION_MINIMUM), "LOW"
        elif isinstance(adjustment, float) and math.isnan(adjustment):
            logger.error(
                "CRITICAL: Owner concentration adjustment is NaN, using minimum discount",
                normalized_ratio=float(normalized_ratio),
                num_owners=num_owners,
                num_employees=num_employees,
            )
            return to_decimal(DecimalConstants.OWNER_CONCENTRATION_MINIMUM), "LOW"
        elif isinstance(adjustment, float) and math.isinf(adjustment):
            logger.error(
                "CRITICAL: Owner concentration adjustment is infinite, using minimum discount",
                normalized_ratio=float(normalized_ratio),
                num_owners=num_owners,
                num_employees=num_employees,
            )
            return to_decimal(DecimalConstants.OWNER_CONCENTRATION_MINIMUM), "LOW"

        # Normalize adjustment to decimal format if it's a percentage
        if adjustment < -Decimal("1.0") or adjustment > 0.0:
            logger.warning(
                "⚠️ Adjustment appears to be a percentage instead of decimal, normalizing",
                adjustment_before_normalization=float(adjustment),
                normalized_ratio=float(normalized_ratio),
            )
            adjustment = adjustment / Decimal("100.0")

        # Validate adjustment is in valid decimal range
        if adjustment < -Decimal("1.0") or adjustment > 0.0:
            logger.error(
                "CRITICAL: Adjustment still invalid after normalization, using minimum discount",
                adjustment=float(adjustment),
                normalized_ratio=float(normalized_ratio),
            )
            return to_decimal(DecimalConstants.OWNER_CONCENTRATION_MINIMUM), "LOW"

        # Ensure adjustment is never 0 for valid ratios
        try:
            minimum_discount = to_decimal(DecimalConstants.OWNER_CONCENTRATION_MINIMUM)
        except (AttributeError, ValueError, TypeError):
            minimum_discount = -Decimal("0.03")  # Fallback to hardcoded -3%

        if normalized_ratio > Decimal("0.05") and (
            adjustment == 0 or abs(adjustment) < Decimal("0.001")
        ):
            logger.warning(
                "⚠️ Owner concentration adjustment is 0 for ratio > 5%, applying minimum -3% discount",
                normalized_ratio=float(normalized_ratio),
                original_adjustment=float(adjustment),
                applied_minimum=float(minimum_discount),
            )
            adjustment = minimum_discount
            # CRITICAL FIX: Never override risk_level here - let domain class determine it
            # The domain class (OwnerConcentrationAdjuster) correctly classifies risk based on
            # partnership status, business structure, and tier logic. Hardcoding "LOW" here
            # causes inverted risk classification for high ratios (e.g., 2.0 ratio = 200% = CRITICAL, not LOW)
            risk_level = None  # Will be determined by domain class
        else:
            risk_level = None  # Will be determined by domain class

        # Diagnostic trace — Pass-9 demoted from warning to debug.
        logger.debug(
            "[CALCULATOR] validate_and_normalize_adjustment() RETURNING",
            adjustment_final=float(adjustment),
            risk_level_override=risk_level,
            note="risk_level=None means domain class classification should be used",
        )

        return adjustment, risk_level

    def calculate_adjustment_percentage(self, adjustment: Decimal) -> Decimal:
        """
        Calculate adjustment percentage from decimal adjustment.

        Args:
            adjustment: Decimal adjustment (e.g., -Decimal('0.20') for -20%)

        Returns:
            Adjustment percentage (e.g., -Decimal('20.0'))
        """
        try:
            import math

            if adjustment is None:
                logger.error(
                    "CRITICAL: adjustment is None when calculating adjustment_pct, using 0"
                )
                return Decimal("0.0")
            elif isinstance(adjustment, float) and (
                math.isnan(adjustment) or math.isinf(adjustment)
            ):
                logger.error(
                    f"CRITICAL: adjustment is invalid ({adjustment}) when calculating adjustment_pct, using 0"
                )
                return Decimal("0.0")
            else:
                # Ensure adjustment is in valid decimal range
                if adjustment < -Decimal("1.0") or adjustment > 0.0:
                    logger.error(
                        "CRITICAL: Adjustment outside valid range when calculating adjustment_pct, clamping",
                        extra={"adjustment": adjustment},
                    )
                    if adjustment < -1.0:
                        adjustment = adjustment / Decimal("100.0")
                    elif adjustment > Decimal("0.0"):
                        adjustment = Decimal("0.0")
                    if adjustment < -Decimal("1.0") or adjustment > 0.0:
                        adjustment = to_decimal(DecimalConstants.OWNER_CONCENTRATION_MINIMUM)

                adjustment_pct = to_decimal(adjustment * 100)
                if isinstance(adjustment_pct, Decimal) and (
                    adjustment_pct.is_nan() or adjustment_pct.is_infinite()
                ):
                    logger.error(
                        f"CRITICAL: adjustment_pct calculation resulted in non-finite value ({adjustment_pct}), using 0"
                    )
                    return Decimal("0.0")
                elif adjustment_pct < -Decimal("100.0") or adjustment_pct > 0.0:
                    logger.error(
                        f"CRITICAL: adjustment_pct is outside valid range ({adjustment_pct}%), clamping",
                        extra={"adjustment_pct_before_clamp": adjustment_pct},
                    )
                    adjustment_pct = max(-Decimal("100.0"), min(Decimal("0.0"), adjustment_pct))
                return adjustment_pct
        except (TypeError, ValueError, OverflowError) as calc_error:
            logger.error(
                "CRITICAL: Failed to calculate adjustment_pct",
                extra={"adjustment": adjustment, "error": str(calc_error)},
            )
            return Decimal("0.0")
