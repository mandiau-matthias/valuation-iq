"""
Step 5 Discount Calculator

Calculates size discounts based on revenue tiers.
"""

from decimal import Decimal
from typing import Optional, Tuple

from src.config.decimal_constants import DecimalConstants
from src.utils.decimal_helpers import to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class Step5DiscountCalculator:
    """Calculates size discounts for Step 5."""

    def check_sme_calibration(self, step2_result: Optional[dict]) -> Tuple[bool, Decimal]:
        """
        Check if Step 2 SME calibration was applied.

        Resolved Upswitch Index benchmark contracts use local or borrowed SME
        evidence and may already carry partial size-risk calibration. Legacy
        cache/default/fallback lanes must not receive that trust automatically.

        Args:
            step2_result: Step 2 result dictionary

        Returns:
            Tuple of (sme_calibration_applied, sme_calibration_factor) - factor is Decimal for bank-grade precision
        """
        if not step2_result:
            return False, Decimal("1.0")

        sme_calibration_data = step2_result.get("sme_calibration", {})
        sme_calibration_applied = sme_calibration_data.get("applied", False)

        data_source = step2_result.get("data_source", "")
        benchmark_contract = step2_result.get("benchmark_provenance") or step2_result.get(
            "benchmark_contract"
        )
        if data_source in ("titan_enrichment", "delphi-resolved-benchmark") or isinstance(
            benchmark_contract, dict
        ):
            sme_calibration_applied = True
            logger.debug(
                "SME calibration detected via resolved benchmark contract",
                extra={
                    "data_source": data_source,
                    "reason": "resolved Upswitch Index benchmark contract includes SME evidence",
                    "step_5_action": "Reduce discount 50% — SME multiples capture partial size risk",
                },
            )

        # Get calibration factor from EBITDA multiple (primary method)
        ebitda_calibration = sme_calibration_data.get("ebitda_multiple", {})
        if ebitda_calibration:
            sme_calibration_factor = ebitda_calibration.get("calibration_factor", Decimal("1.0"))
        # Fallback to revenue multiple if EBITDA calibration not available
        elif sme_calibration_data.get("revenue_multiple"):
            revenue_calibration = sme_calibration_data.get("revenue_multiple", {})
            sme_calibration_factor = revenue_calibration.get("calibration_factor", Decimal("1.0"))
        else:
            sme_calibration_factor = Decimal("1.0")

        return sme_calibration_applied, sme_calibration_factor

    # Retention factor for SME size discounts. De-stack (2026-05): when the base
    # multiple is SME/private-comp-calibrated (Benelux SME 2.0 / resolved micro-
    # KMO benchmark), the size premium is already priced into the comp multiple,
    # so stacking a separate size discount double-counts. We retain none of it
    # (0.00) for SME-calibrated multiples; owner-concentration (Step 4) and DLOM
    # (Step 6) carry company-specific and marketability risk on their own.
    SME_SIZE_DISCOUNT_REDUCTION = Decimal("0.00")

    def determine_revenue_tier_and_base_discount(
        self, revenue: Decimal, sme_calibration_applied: bool
    ) -> Tuple[Decimal, str]:
        """
        Determine revenue tier and base discount.

        When the base multiple is SME/private-comp-calibrated (companies < €5M),
        the size premium is already embedded in the comp multiple, so the size
        discount is removed entirely to avoid double-counting.

        Academic basis: private micro-KMO transaction multiples already trade at
        a size-adjusted level; layering an Ibbotson/Duff & Phelps size premium on
        top would charge the same risk twice.
        """
        revenue_decimal = to_decimal(revenue)

        # Graduated size discount scale (monotonically decreasing)
        if revenue_decimal < Decimal("250000"):
            base_discount, tier = Decimal("-0.225"), "Micro-cap (€0-€250K)"
        elif revenue_decimal < Decimal("500000"):
            base_discount, tier = Decimal("-0.15"), "Small micro-cap (€250K-€500K)"
        elif revenue_decimal < Decimal("1000000"):
            base_discount, tier = Decimal("-0.10"), "Small (€500K-€1M)"
        elif revenue_decimal < Decimal("2000000"):
            base_discount, tier = Decimal("-0.05"), "Small-medium (€1M-€2M)"
        elif revenue_decimal < Decimal("3000000"):
            base_discount, tier = Decimal("-0.035"), "Medium-small (€2M-€3M)"
        elif revenue_decimal < Decimal("10000000"):
            base_discount, tier = Decimal("-0.025"), "Lower mid-market (€3M-€10M)"
        elif revenue_decimal < Decimal("25000000"):
            base_discount, tier = Decimal("-0.015"), "Mid-market (€10M-€25M)"
        elif revenue_decimal < DecimalConstants.MID_CAP_THRESHOLD:
            base_discount, tier = Decimal("-0.01"), "Upper mid-market (€25M-€50M)"
        else:
            base_discount, tier = Decimal("0.00"), "Large (> €50M)"

        if sme_calibration_applied and revenue_decimal < Decimal("5000000"):
            reduced = base_discount * self.SME_SIZE_DISCOUNT_REDUCTION
            logger.debug(
                "Size discount removed for SME-calibrated multiple (size risk already priced into comp)",
                extra={
                    "original_discount": float(base_discount),
                    "reduced_discount": float(reduced),
                    "retention_factor": float(self.SME_SIZE_DISCOUNT_REDUCTION),
                },
            )
            return reduced, f"{tier} (size risk already priced into SME-calibrated multiple)"

        return base_discount, tier

    def calculate_final_discount(
        self,
        base_discount: Decimal,
        adjustment_multiplier: Decimal,
        revenue: Decimal,
        sme_calibration_applied: bool,
    ) -> Decimal:
        """
        Calculate final discount with business-type adjustment and bounds checking.

        Args:
            base_discount: Base discount from revenue tier
            adjustment_multiplier: Business-type adjustment multiplier
            revenue: Revenue value
            sme_calibration_applied: Whether Step 2 SME calibration was applied

        Returns:
            Final discount value
        """
        # Calculate discount with multiplier
        discount = base_discount * to_decimal(adjustment_multiplier)

        # Ensure discount stays within reasonable bounds (-35% floor)
        discount = max(to_decimal("-0.35"), discount)

        # Additional minimum check for small companies without calibration
        if revenue < DecimalConstants.SMALL_CAP_THRESHOLD and not sme_calibration_applied:
            discount_decimal = to_decimal(discount)
            if discount_decimal >= Decimal("0") or discount_decimal > Decimal(
                "-0.01"
            ):  # 0% or less than -1%
                logger.warning(
                    "⚠️ Size discount is 0% or effectively 0% for small company, applying minimum -2% discount",
                    extra={
                        "revenue": to_decimal(revenue),
                        "original_discount": float(
                            discount_decimal
                        ),  # Convert to float only for logging
                        "applied_minimum": -Decimal("0.02"),
                    },
                )
                discount = DecimalConstants.SIZE_DISCOUNT_MINIMUM
            elif discount_decimal > Decimal("-0.02"):
                # If discount is negative but less than -2%, ensure it's at least -2%
                discount = DecimalConstants.SIZE_DISCOUNT_MINIMUM

        return discount
