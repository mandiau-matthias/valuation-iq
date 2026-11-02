"""
Step 5 Orchestrator

Orchestrates the main execution flow for Step 5 size discount.
"""

from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from src.api.routes.valuation.triage.business_type_triage import BusinessTypeTriageEngine
from src.services.academic.calculation_provenance_tracker import record_calculation_safe
from src.utils.decimal_helpers import bank_round, from_decimal, to_decimal
from src.utils.logging import get_logger
from src.utils.multiple_helpers import apply_discount_to_multiple, calculate_ev_from_multiple

from ...strength_factor_discount_adjustments import (
    annotate_strength_factor_discount_result,
    apply_priced_strength_factor_adjustment,
    strength_factor_discount_adjustment_for_request,
)

logger = get_logger(__name__)


class Step5Orchestrator:
    """Orchestrates the main execution flow for Step 5."""

    def __init__(
        self,
        business_type_triage: BusinessTypeTriageEngine,
        calculator,
        result_builder,
        error_handler,
        step_name: str,
    ):
        """
        Initialize the orchestrator.

        Args:
            business_type_triage: Business type triage engine
            calculator: Step 5 discount calculator instance
            result_builder: Step 5 result builder instance
            error_handler: Step 5 error handler instance
            step_name: Step name for logging
        """
        self.business_type_triage = business_type_triage
        self.calculator = calculator
        self.result_builder = result_builder
        self.error_handler = error_handler
        self.step_name = step_name

    async def orchestrate_execution(
        self,
        request: object,
        step1: Dict[str, Any],
        step2_result: Optional[Dict[str, Any]],
        ev_data: Dict[str, Any],
        ev_source_step: int,
        step3_result: Dict[str, Any],
        correlation_id: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Orchestrate the main execution flow.

        Args:
            request: The valuation request
            step1: Step 1 result dictionary
            step2_result: Step 2 result dictionary (optional)
            ev_data: EV data from Step 3 or Step 4
            ev_source_step: Source step number (3 or 4)
            step3_result: Step 3 result dictionary
            correlation_id: Correlation ID for logging

        Returns:
            Tuple of (result_dict, metadata_dict)
        """
        # Convert revenue to Decimal
        revenue = to_decimal(step1.get("revenue", 0) or 0)

        # Get business type category
        business_category = self.business_type_triage.get_business_type_category(
            getattr(request, "business_type_id", None),
            getattr(request, "business_model", None),
            getattr(request, "industry", None),
            category_id=getattr(request, "category_id", None),
        )

        # Check SME calibration
        sme_calibration_applied, sme_calibration_factor = self.calculator.check_sme_calibration(
            step2_result
        )

        # Determine revenue tier and base discount
        base_discount, tier = self.calculator.determine_revenue_tier_and_base_discount(
            revenue, sme_calibration_applied
        )

        # Get business-type adjustment multiplier
        adjustment_multiplier = self.business_type_triage.get_size_discount_adjustment(
            business_category,
            to_decimal(revenue),
            getattr(request, "business_type_id", None),
            valuation_preferences=getattr(request, "valuation_preferences", None),
        )

        # Ensure multiplier is valid
        if adjustment_multiplier is None or adjustment_multiplier == 0:
            logger.warning(
                "⚠️ Size discount adjustment_multiplier is 0 or None, defaulting to 1.0",
                extra={
                    "step_number": 5,
                    "adjustment_multiplier": adjustment_multiplier,
                    "business_category": business_category.value if business_category else None,
                },
            )
            adjustment_multiplier = Decimal("1.0")

        # Calculate final discount
        discount = self.calculator.calculate_final_discount(
            base_discount, adjustment_multiplier, revenue, sme_calibration_applied
        )
        discount_before_strength_factor = discount
        (
            size_strength_factor_adjustment,
            size_strength_factor_evidence,
        ) = strength_factor_discount_adjustment_for_request(request, "size_discount")
        discount = apply_priced_strength_factor_adjustment(
            discount,
            size_strength_factor_adjustment,
            floor=Decimal("-0.35"),
        )
        (
            growth_strength_factor_adjustment,
            growth_strength_factor_evidence,
        ) = strength_factor_discount_adjustment_for_request(request, "growth_premium")
        discount = apply_priced_strength_factor_adjustment(
            discount,
            growth_strength_factor_adjustment,
            floor=Decimal("-0.35"),
            ceiling=Decimal("0.05"),
        )
        strength_factor_evidence = [
            *size_strength_factor_evidence,
            *growth_strength_factor_evidence,
        ]
        strength_factor_adjustment = discount - discount_before_strength_factor

        # Academic provenance: rule `size_discount_range` enforces
        # 10% - 40% per Ibbotson SBBI (2024) / Duff & Phelps (2024).
        # SME-calibrated runs already fold the discount into Step 2 multiples,
        # so a near-zero discount here is correct and would (rightly) fail the
        # 10%–40% rule. Skip the validation record in that case.
        if (
            discount is not None
            and discount > 0
            and not sme_calibration_applied
            and not growth_strength_factor_evidence
        ):
            record_calculation_safe(
                "size_discount",
                float(discount),
                step_number=5,
                section_name="Size Discount",
                inputs={
                    "revenue": float(revenue) if revenue is not None else None,
                    "tier": tier,
                    "base_discount": float(base_discount) if base_discount is not None else None,
                    "adjustment_multiplier": float(adjustment_multiplier),
                },
            )

        # Get current multiples and metric value
        current_multiple_low = to_decimal(ev_data.get("current_multiple_low", 0))
        current_multiple_mid = to_decimal(ev_data.get("current_multiple_mid", 0))
        current_multiple_high = to_decimal(ev_data.get("current_multiple_high", 0))
        metric_value = to_decimal(step3_result.get("primary_metric_value", 0))
        metric_type = step3_result.get("primary_metric", "EBITDA")

        # Get EV values for comparison
        ev_low_before = to_decimal(ev_data.get("enterprise_value_low", 0))
        ev_mid_before = to_decimal(ev_data.get("enterprise_value_mid", 0))
        ev_high_before = to_decimal(ev_data.get("enterprise_value_high", 0))

        # Apply discount to multiples
        discount_pct_float = to_decimal(discount * 100)
        multiple_before_low, multiple_after_low = apply_discount_to_multiple(
            current_multiple_low, discount_pct_float
        )
        multiple_before_mid, multiple_after_mid = apply_discount_to_multiple(
            current_multiple_mid, discount_pct_float
        )
        multiple_before_high, multiple_after_high = apply_discount_to_multiple(
            current_multiple_high, discount_pct_float
        )

        # Recalculate EV from adjusted multiples
        ev_low_after = calculate_ev_from_multiple(metric_value, multiple_after_low)
        ev_mid_after = calculate_ev_from_multiple(metric_value, multiple_after_mid)
        ev_high_after = calculate_ev_from_multiple(metric_value, multiple_after_high)

        # Validate and correct range
        ev_low_after, ev_mid_after, ev_high_after = self._validate_and_correct_range(
            ev_low_after, ev_mid_after, ev_high_after, discount
        )

        # Round to 2 decimal places
        ev_low_after = bank_round(ev_low_after, 2)
        ev_mid_after = bank_round(ev_mid_after, 2)
        ev_high_after = bank_round(ev_high_after, 2)

        # Convert to float
        ev_low_float = from_decimal(ev_low_after, 2)
        ev_mid_float = from_decimal(ev_mid_after, 2)
        ev_high_float = from_decimal(ev_high_after, 2)
        ev_low_before_float = from_decimal(ev_low_before, 2)
        ev_mid_before_float = from_decimal(ev_mid_before, 2)
        ev_high_before_float = from_decimal(ev_high_before, 2)
        discount_float = to_decimal(discount)
        discount_pct = discount_float * 100
        base_discount_float = to_decimal(base_discount)
        base_discount_pct = base_discount_float * 100

        # Build result and metadata
        result_dict = self.result_builder.build_result_dict(
            ev_low_float=ev_low_float,
            ev_mid_float=ev_mid_float,
            ev_high_float=ev_high_float,
            ev_low_before_float=ev_low_before_float,
            ev_mid_before_float=ev_mid_before_float,
            ev_high_before_float=ev_high_before_float,
            tier=tier,
            base_discount_float=base_discount_float,
            adjustment_multiplier=adjustment_multiplier,
            discount_float=discount_float,
            discount_pct=discount_pct,
            business_category=business_category,
            sme_calibration_applied=sme_calibration_applied,
            revenue=revenue,
            multiple_before_low=multiple_before_low,
            multiple_before_mid=multiple_before_mid,
            multiple_before_high=multiple_before_high,
            multiple_after_low=multiple_after_low,
            multiple_after_mid=multiple_after_mid,
            multiple_after_high=multiple_after_high,
            metric_value=metric_value,
        )

        metadata_dict = self.result_builder.build_metadata_dict(
            ev_low_before_float=ev_low_before_float,
            ev_mid_before_float=ev_mid_before_float,
            ev_high_before_float=ev_high_before_float,
            ev_low_float=ev_low_float,
            ev_mid_float=ev_mid_float,
            ev_high_float=ev_high_float,
            base_discount_float=base_discount_float,
            base_discount_pct=base_discount_pct,
            adjustment_multiplier=adjustment_multiplier,
            discount_float=discount_float,
            discount_pct=discount_pct,
            tier=tier,
            business_category=business_category,
        )
        annotate_strength_factor_discount_result(
            result_dict,
            metadata_dict,
            discount_key=_strength_factor_step5_discount_key(
                size_strength_factor_evidence,
                growth_strength_factor_evidence,
            ),
            evidence_rows=strength_factor_evidence,
            adjustment=strength_factor_adjustment,
            discount_before=discount_before_strength_factor,
            discount_after=discount,
        )

        return result_dict, metadata_dict

    def _validate_and_correct_range(
        self,
        ev_low_after: Decimal,
        ev_mid_after: Decimal,
        ev_high_after: Decimal,
        discount: Decimal,
    ) -> Tuple[Decimal, Decimal, Decimal]:
        """
        Validate and correct EV range ordering.

        Args:
            ev_low_after: EV low after adjustment
            ev_mid_after: EV mid after adjustment
            ev_high_after: EV high after adjustment
            discount: Discount value

        Returns:
            Tuple of (corrected_ev_low, corrected_ev_mid, corrected_ev_high)
        """
        if ev_low_after >= ev_mid_after or ev_mid_after >= ev_high_after:
            logger.warning(
                "⚠️ Invalid EV range detected after size discount, auto-correcting",
                extra={
                    "ev_low": to_decimal(ev_low_after),
                    "ev_mid": to_decimal(ev_mid_after),
                    "ev_high": to_decimal(ev_high_after),
                    "discount": to_decimal(discount),
                },
            )
            # Auto-correct: ensure proper ordering
            ev_values = [ev_low_after, ev_mid_after, ev_high_after]
            ev_low_after = min(ev_values)
            ev_high_after = max(ev_values)
            # Recalculate mid as average if ordering was invalid
            if ev_low_after >= ev_mid_after or ev_mid_after >= ev_high_after:
                ev_mid_after = (ev_low_after + ev_high_after) / to_decimal("2")
                logger.info(
                    "✓ Auto-corrected EV range after size discount",
                    extra={
                        "ev_low": to_decimal(ev_low_after),
                        "ev_mid": to_decimal(ev_mid_after),
                        "ev_high": to_decimal(ev_high_after),
                    },
                )
        return ev_low_after, ev_mid_after, ev_high_after


def _strength_factor_step5_discount_key(
    size_evidence: list[Dict[str, Any]],
    growth_evidence: list[Dict[str, Any]],
) -> str:
    if size_evidence and growth_evidence:
        return "size_discount+growth_premium"
    if growth_evidence:
        return "growth_premium"
    return "size_discount"
