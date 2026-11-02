"""
Step 6 Orchestrator

Orchestrates the main execution flow for Step 6 liquidity discount.
"""

from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from src.api.routes.valuation.triage.business_type_triage import BusinessTypeTriageEngine
from src.domain.liquidity_discount_adjuster import LiquidityDiscountAdjuster
from src.services.academic.calculation_provenance_tracker import record_calculation_safe
from src.utils.decimal_helpers import bank_round, from_decimal, to_decimal
from src.utils.logging import get_logger
from src.utils.multiple_helpers import apply_discount_to_multiple, calculate_ev_from_multiple
from src.utils.sole_trader_detector import SoleTraderDetector

from ...base_step import StepStatus
from ...strength_factor_discount_adjustments import (
    annotate_strength_factor_discount_result,
    apply_priced_strength_factor_adjustment,
    strength_factor_discount_adjustment_for_request,
)

logger = get_logger(__name__)


class Step6Orchestrator:
    """Orchestrates the main execution flow for Step 6."""

    def __init__(
        self,
        liquidity_adjuster: LiquidityDiscountAdjuster,
        business_type_triage: BusinessTypeTriageEngine,
        calculator,
        result_builder,
        error_handler,
        step_name: str,
    ):
        """
        Initialize the orchestrator.

        Args:
            liquidity_adjuster: Liquidity discount adjuster
            business_type_triage: Business type triage engine
            calculator: Step 6 discount calculator instance
            result_builder: Step 6 result builder instance
            error_handler: Step 6 error handler instance
            step_name: Step name for logging
        """
        self.liquidity_adjuster = liquidity_adjuster
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
        step3_result: Dict[str, Any],
        ev_data: Dict[str, Any],
        base_step: int,
        correlation_id: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Orchestrate the main execution flow.

        Args:
            request: The valuation request
            step1: Step 1 result dictionary
            step2_result: Step 2 result dictionary (optional)
            step3_result: Step 3 result dictionary
            ev_data: EV data from Step 3, 4, or 5
            base_step: Base step number (3, 4, or 5)
            correlation_id: Correlation ID for logging

        Returns:
            Tuple of (result_dict, metadata_dict)
        """
        # Extract financial metrics
        # Avoid `or 0` on Decimal values: Decimal('0') is falsy, so `Decimal('0') or 0`
        # returns the int 0, which then breaks from_decimal() in calculate_discount.
        _raw_margin = step1.get("ebitda_margin")
        ebitda_margin = to_decimal(_raw_margin) if _raw_margin is not None else Decimal("0")
        _raw_revenue = step1.get("revenue")
        revenue = to_decimal(_raw_revenue) if _raw_revenue is not None else Decimal("0")

        # Get business category
        business_category = self.business_type_triage.get_business_type_category(
            getattr(request, "business_type_id", None),
            getattr(request, "business_model", None),
            getattr(request, "industry", None),
            category_id=getattr(request, "category_id", None),
        )

        # Calculate growth rate and recurring revenue
        growth_rate = self.calculator.calculate_growth_rate(request)
        recurring_revenue_pct = self.calculator.extract_recurring_revenue_pct(
            request, to_decimal(revenue)
        )
        customer_concentration_pct = self.calculator.extract_customer_concentration_pct(
            request, to_decimal(revenue)
        )
        contract_backlog_months = self.calculator.extract_contract_backlog_months(
            request, to_decimal(revenue)
        )

        # Check SME calibration
        sme_calibration_applied, sme_calibration_factor = self.calculator.check_sme_calibration(
            step2_result
        )
        step6_skipped_for_sme = self.calculator.should_skip_for_sme(
            sme_calibration_applied, revenue
        )
        sme_discount_reduction = self.calculator.get_sme_discount_reduction_factor(
            sme_calibration_applied, revenue
        )

        # Calculate discount (only if not skipped)
        business_type_id = getattr(request, "business_type_id", None)
        valuation_preferences = getattr(request, "valuation_preferences", None)
        total_discount = self.liquidity_adjuster.calculate_discount(
            business_category=business_category,
            ebitda_margin=ebitda_margin,
            growth_rate=growth_rate,
            recurring_revenue_pct=recurring_revenue_pct,
            customer_concentration_pct=customer_concentration_pct,
            contract_backlog_months=contract_backlog_months,
            revenue=revenue,
            business_type_id=business_type_id,
            valuation_preferences=valuation_preferences,
        )

        # Clamp discount then apply SME reduction factor (25% residual for
        # SME/private-comp-calibrated runs < €5M; most illiquidity is already
        # priced into the private-transaction multiple)
        total_discount = self.calculator.clamp_discount(total_discount, step6_skipped_for_sme)
        if sme_discount_reduction < Decimal("1.0"):
            total_discount = total_discount * sme_discount_reduction
            logger.debug(
                "SME liquidity discount reduced",
                extra={
                    "reduction_factor": float(sme_discount_reduction),
                    "discount_after_reduction": float(total_discount),
                    "academic_basis": "Koeplin et al. (2000): residual illiquidity after SME calibration",
                },
            )
        discount_before_strength_factor = total_discount
        (
            strength_factor_adjustment,
            strength_factor_evidence,
        ) = strength_factor_discount_adjustment_for_request(request, "liquidity_discount")
        total_discount = apply_priced_strength_factor_adjustment(
            total_discount,
            strength_factor_adjustment,
            floor=Decimal("-0.30"),
        )

        # Academic provenance: rule `liquidity_discount_range` enforces
        # 20% - 40% per Longstaff (1995) / Silber (1991). SME-calibrated
        # runs skip the discount (already illiquid), and the rule's own
        # warning_message acknowledges that case — only record when an
        # actual discount applies.
        if (
            total_discount is not None
            and total_discount > 0
            and not step6_skipped_for_sme
            and sme_discount_reduction >= Decimal("1.0")
        ):
            record_calculation_safe(
                "liquidity_discount",
                float(total_discount),
                step_number=6,
                section_name="Liquidity Discount",
                inputs={
                    "business_category": (business_category.value if business_category else None),
                    "revenue": float(revenue) if revenue else None,
                    "ebitda_margin": float(ebitda_margin) if ebitda_margin else None,
                    "growth_rate": float(growth_rate) if growth_rate else None,
                    "customer_concentration_pct": (
                        float(customer_concentration_pct)
                        if customer_concentration_pct is not None
                        else None
                    ),
                    "contract_backlog_months": (
                        float(contract_backlog_months)
                        if contract_backlog_months is not None
                        else None
                    ),
                },
            )

        # Get adjustment breakdown
        adjustment_breakdown = self.liquidity_adjuster.get_adjustment_breakdown(
            business_category=business_category,
            ebitda_margin=ebitda_margin,
            growth_rate=growth_rate,
            recurring_revenue_pct=recurring_revenue_pct,
            customer_concentration_pct=customer_concentration_pct,
            contract_backlog_months=contract_backlog_months,
            revenue=revenue,
            business_type_id=business_type_id,
            valuation_preferences=valuation_preferences,
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
        discount_pct_float = to_decimal(total_discount * 100)
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

        # Ensure values remain positive
        ev_low_after = max(to_decimal("0"), ev_low_after)
        ev_mid_after = max(to_decimal("0"), ev_mid_after)
        ev_high_after = max(to_decimal("0"), ev_high_after)

        # Validate and correct range
        ev_low_after, ev_mid_after, ev_high_after = self._validate_and_correct_range(
            ev_low_after, ev_mid_after, ev_high_after, total_discount
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
        total_discount_float = to_decimal(total_discount)
        total_discount_pct = total_discount_float * 100

        # Build result and metadata
        result_dict = self.result_builder.build_result_dict(
            ev_low_float=ev_low_float,
            ev_mid_float=ev_mid_float,
            ev_high_float=ev_high_float,
            ev_low_before_float=ev_low_before_float,
            ev_mid_before_float=ev_mid_before_float,
            ev_high_before_float=ev_high_before_float,
            adjustment_breakdown=adjustment_breakdown,
            total_discount_float=total_discount_float,
            total_discount_pct=total_discount_pct,
            business_category=business_category,
            base_step=base_step,
            sme_calibration_applied=sme_calibration_applied,
            sme_calibration_factor=sme_calibration_factor,
            revenue=revenue,
            step6_skipped_for_sme=step6_skipped_for_sme,
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
            total_discount_pct=total_discount_pct,
            base_step=base_step,
        )
        annotate_strength_factor_discount_result(
            result_dict,
            metadata_dict,
            discount_key="liquidity_discount",
            evidence_rows=strength_factor_evidence,
            adjustment=strength_factor_adjustment,
            discount_before=discount_before_strength_factor,
            discount_after=total_discount,
        )

        return result_dict, metadata_dict

    def _validate_and_correct_range(
        self,
        ev_low_after: Decimal,
        ev_mid_after: Decimal,
        ev_high_after: Decimal,
        total_discount: Decimal,
    ) -> Tuple[Decimal, Decimal, Decimal]:
        """
        Validate and correct EV range ordering.

        Args:
            ev_low_after: EV low after adjustment
            ev_mid_after: EV mid after adjustment
            ev_high_after: EV high after adjustment
            total_discount: Discount value

        Returns:
            Tuple of (corrected_ev_low, corrected_ev_mid, corrected_ev_high)
        """
        if ev_low_after >= ev_mid_after or ev_mid_after >= ev_high_after:
            logger.warning(
                "⚠️ Invalid EV range detected after liquidity discount, auto-correcting",
                extra={
                    "ev_low": to_decimal(ev_low_after),
                    "ev_mid": to_decimal(ev_mid_after),
                    "ev_high": to_decimal(ev_high_after),
                    "total_discount": to_decimal(total_discount),
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
                    "✓ Auto-corrected EV range after liquidity discount",
                    extra={
                        "ev_low": to_decimal(ev_low_after),
                        "ev_mid": to_decimal(ev_mid_after),
                        "ev_high": to_decimal(ev_high_after),
                    },
                )
        return ev_low_after, ev_mid_after, ev_high_after

    def extract_ev_source(
        self,
        step5_result: Optional[Dict[str, Any]],
        step4_result: Optional[Dict[str, Any]],
        step3_result: Optional[Dict[str, Any]],
        step5_available: bool,
        step4_available: bool,
        step3_available: bool,
    ) -> Tuple[Optional[int], Optional[Dict[str, Any]]]:
        """
        Extract EV source from previous steps (priority: Step 5 > Step 4 > Step 3).

        Args:
            step5_result: Step 5 result dictionary
            step4_result: Step 4 result dictionary
            step3_result: Step 3 result dictionary
            step5_available: Whether Step 5 is available
            step4_available: Whether Step 4 is available
            step3_available: Whether Step 3 is available

        Returns:
            Tuple of (base_step, ev_data)
        """
        if step5_available and step5_result and "enterprise_value_mid" in step5_result:
            logger.debug(
                "✅ Using Step 5 (size discount) result as base for liquidity discount",
                extra={"step_number": 6, "base_step": 5},
            )
            return 5, step5_result
        elif step4_available and step4_result and "enterprise_value_mid" in step4_result:
            logger.info(
                "✅ Using Step 4 (owner concentration) result as base for liquidity discount",
                extra={"step_number": 6, "base_step": 4},
            )
            return 4, step4_result
        elif step3_available and step3_result and "enterprise_value_mid" in step3_result:
            logger.info(
                "✅ Using Step 3 (base EV) result as base for liquidity discount",
                extra={"step_number": 6, "base_step": 3},
            )
            return 3, step3_result
        else:
            return None, None
