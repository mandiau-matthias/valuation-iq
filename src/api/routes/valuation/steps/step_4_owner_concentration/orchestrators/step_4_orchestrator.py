"""
Step 4 Orchestrator

Orchestrates the main execution flow for Step 4 owner concentration adjustment.
"""

from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from src.domain.owner_concentration_adjuster import OwnerConcentrationAdjuster
from src.services.academic.calculation_provenance_tracker import record_calculation_safe
from src.utils.core.data_extraction_helpers import extract_owner_employee_counts_from_request
from src.utils.decimal_helpers import bank_round, from_decimal, to_decimal
from src.utils.logging import get_logger
from src.utils.multiple_helpers import apply_discount_to_multiple, calculate_ev_from_multiple
from src.utils.sole_trader_detector import SoleTraderDetector

logger = get_logger(__name__)


def _headcount_corroborated(request: Any) -> bool:
    """True when the FTE count driving Step 4 was confirmed by a human.

    Two accepted proofs, in order:
      1. The 9-question Owner Profile was completed — ``request.owner_dependency``
         (or ``owner_dependency_factors``) carries an operator-supplied
         ``number_of_employees`` / ``owner_fte_ratio``.
      2. An explicit confirmation flag (``headcount_confirmed``) on the request
         or its ``business_context``, set by the intake flow when the seller
         accepts or edits the prefilled registry figure.

    Anything else — notably a ``company_info.number_of_employees`` registry
    prefill nobody looked at (see
    ``request_builder/ai_guided_normalization.py`` ``employee_count_from_sources``)
    — is UNCORROBORATED. The value carries no provenance marker of its own, so
    absence of a confirmation is the only signal available here.
    """
    for attr in ("owner_dependency", "owner_dependency_factors"):
        profile = getattr(request, attr, None)
        if profile is None:
            continue
        if (
            getattr(profile, "number_of_employees", None) is not None
            or getattr(profile, "owner_fte_ratio", None) is not None
        ):
            return True

    if getattr(request, "headcount_confirmed", None) is True:
        return True

    business_context = getattr(request, "business_context", None) or {}
    if isinstance(business_context, dict) and business_context.get("headcount_confirmed") is True:
        return True

    return False


class Step4Orchestrator:
    """Orchestrates the main execution flow for Step 4."""

    def __init__(
        self,
        owner_adjuster: OwnerConcentrationAdjuster,
        validator,
        calculator,
        result_builder,
        error_handler,
        step_name: str,
    ):
        """
        Initialize the orchestrator.

        Args:
            owner_adjuster: Owner concentration adjuster domain class
            validator: Step 4 validator instance
            calculator: Step 4 calculator instance
            result_builder: Step 4 result builder instance
            error_handler: Step 4 error handler instance
            step_name: Step name for logging
        """
        self.owner_adjuster = owner_adjuster
        self.validator = validator
        self.calculator = calculator
        self.result_builder = result_builder
        self.error_handler = error_handler
        self.step_name = step_name

    async def orchestrate_execution(
        self, request: any, step3: Dict[str, Any], correlation_id: Optional[str] = None
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Orchestrate the main execution flow.

        Args:
            request: The valuation request
            step3: Step 3 result dictionary
            correlation_id: Correlation ID for logging

        Returns:
            Tuple of (result_dict, metadata_dict)
        """
        # Extract owner/employee counts using unified utility
        num_owners_from_request, num_employees_from_request = extract_owner_employee_counts_from_request(request)
        
        # Detect sole trader
        is_sole_trader = SoleTraderDetector.detect(
            business_structure=getattr(request, "business_type", None),
            business_type=getattr(request, "business_type", None),
            number_of_owners=num_owners_from_request,
            number_of_employees=num_employees_from_request,
            is_sole_trader=getattr(request, "is_sole_trader", None),
            business_context=getattr(request, "business_context", None),
        )

        # Extract and validate owner/employee data
        num_owners, num_employees, error_msg = (
            self.validator.extract_and_validate_owner_employee_data(request, is_sole_trader)
        )
        if error_msg:
            return None, {"error": error_msg}

        # Validate types
        num_owners, num_employees, error_msg = self.validator.validate_owner_employee_types(
            num_owners, num_employees
        )
        if error_msg:
            return None, {"error": error_msg}

        # Validate non-negative
        is_valid, error_msg = self.validator.validate_owner_employee_non_negative(
            num_owners, num_employees
        )
        if not is_valid:
            return None, {"error": error_msg}

        # Calculate ratio
        raw_ratio, ratio_warning = self.calculator.calculate_owner_employee_ratio(
            num_owners, num_employees
        )

        # Determine if true sole trader
        business_structure = getattr(request, "business_structure", None) or getattr(
            request, "business_type", None
        )
        business_structure_lower = str(business_structure).lower() if business_structure else ""
        is_true_sole_trader = (
            num_owners == 1 and num_employees <= 1
        ) and business_structure_lower in [
            "sole-trader",
            "sole_trader",
            "soletrader",
            "sole trader",
        ]

        # Normalize ratio
        normalized_ratio = self.calculator.normalize_ratio(
            raw_ratio, num_owners, is_true_sole_trader
        )

        # Get business type ID
        business_type_id = getattr(request, "business_type_id", None)

        # Calculate adjustment using domain class
        try:
            adjustment = self.owner_adjuster.calculate_multiple_adjustment(
                owner_fte_ratio=normalized_ratio,
                business_type_id=business_type_id,
                number_of_owners=num_owners,
                business_structure=business_structure,
            )
        except Exception as e:
            self.error_handler.handle_adjuster_error(
                e, normalized_ratio, business_type_id, num_owners, num_employees
            )
            raise

        # ── Headcount corroboration gate ─────────────────────────────────────
        # `num_employees` may be an unread registry prefill rather than an FTE
        # count the seller confirmed. A -20% structural haircut off that input
        # is not defensible, so cap it at the provenance floor and disclose the
        # full tier value as a band instead of booking it as a point discount.
        # NOTE: called on the CLASS (not `self.owner_adjuster`) so unit tests
        # that inject a Mock adjuster still exercise the real cap.
        uncapped_adjustment = adjustment
        headcount_corroborated = _headcount_corroborated(request)
        adjustment, adjustment_was_capped = (
            OwnerConcentrationAdjuster.cap_uncorroborated_adjustment(
                adjustment, headcount_corroborated=headcount_corroborated
            )
        )
        if adjustment_was_capped:
            logger.warning(
                "Step 4: structural owner-concentration capped — headcount not corroborated",
                num_owners=num_owners,
                num_employees=num_employees,
                normalized_ratio=float(normalized_ratio),
                uncapped_adjustment=float(to_decimal(uncapped_adjustment)),
                capped_adjustment=float(adjustment),
            )

        # Get risk level. Pass-9: demoted bracketing diagnostic logs from
        # warning → debug — they were producing `[wrn]` entries on every
        # Step 4 run for what is a normal happy-path trace.
        logger.debug(
            "[ORCHESTRATOR] About to call get_risk_level()",
            normalized_ratio=float(normalized_ratio),
            raw_ratio=float(raw_ratio),
            num_owners=num_owners,
            num_employees=num_employees,
            business_structure=business_structure,
            is_true_sole_trader=is_true_sole_trader,
        )

        risk_level = self.owner_adjuster.get_risk_level(
            normalized_ratio, number_of_owners=num_owners, business_structure=business_structure
        )

        logger.debug(
            "[ORCHESTRATOR] get_risk_level() returned",
            risk_level_returned=risk_level,
            normalized_ratio=float(normalized_ratio),
            num_owners=num_owners,
        )

        # Get calibration info
        tiers = self.owner_adjuster.get_calibrated_tiers(business_type_id)
        calibration_used = (
            "industry-specific"
            if business_type_id and tiers != self.owner_adjuster.ADJUSTMENT_TIERS
            else "universal"
        )

        # Validate and normalize adjustment
        adjustment, risk_level_from_calc = self.calculator.validate_and_normalize_adjustment(
            adjustment, normalized_ratio, num_owners, num_employees
        )
        
        # Diagnostic trace — demoted to debug (Pass-9). The override
        # branch below stays at warning since an actual override is the
        # signal worth flagging.
        logger.debug(
            "[ORCHESTRATOR] After validate_and_normalize_adjustment()",
            risk_level_from_domain=risk_level,
            risk_level_from_calc=risk_level_from_calc,
            adjustment=float(adjustment),
            will_override=risk_level_from_calc is not None,
        )
        
        if risk_level_from_calc:
            logger.warning(
                "⚠️ [ORCHESTRATOR] OVERRIDING risk_level from domain class",
                original_risk_level=risk_level,
                override_risk_level=risk_level_from_calc,
                note="This override may be causing incorrect classification",
            )
            risk_level = risk_level_from_calc

        # A tier name asserts a *measured* concentration. When the headcount
        # behind the ratio was never confirmed there is nothing to measure, so
        # the row is relabelled here — at the single point where `risk_level`
        # is finalised — rather than in each renderer downstream.
        if not headcount_corroborated:
            risk_level = OwnerConcentrationAdjuster.UNCORROBORATED_RISK_LABEL

        # Calculate adjustment percentage
        adjustment_pct = self.calculator.calculate_adjustment_percentage(adjustment)

        # Academic provenance: rule `owner_dependency_discount_range`
        # checks the resulting discount sits within 5% - 40% per McKinsey
        # (2020) / Big 4 guidance. `adjustment` is the decimal discount.
        if adjustment is not None and adjustment > 0:
            record_calculation_safe(
                "owner_dependency_discount",
                float(adjustment),
                step_number=4,
                section_name="Owner Concentration",
                inputs={
                    "num_owners": num_owners,
                    "num_employees": num_employees,
                    "normalized_ratio": float(normalized_ratio),
                    "risk_level": risk_level,
                },
            )

        # Apply multiple-first discounting
        current_multiple_low = to_decimal(step3.get("current_multiple_low", 0))
        current_multiple_mid = to_decimal(step3.get("current_multiple_mid", 0))
        current_multiple_high = to_decimal(step3.get("current_multiple_high", 0))
        metric_value = to_decimal(step3.get("primary_metric_value", 0))
        metric_type = step3.get("primary_metric", "EBITDA")

        # Validate multiples and metric
        if current_multiple_mid <= 0 or metric_value <= 0:
            return None, {
                "error": f"Invalid multiple ({current_multiple_mid}) or metric ({metric_value}) from Step 3"
            }

        # Get EV values from Step 3
        ev_low_before = to_decimal(step3.get("enterprise_value_low", 0))
        ev_mid_before = to_decimal(step3.get("enterprise_value_mid", 0))
        ev_high_before = to_decimal(step3.get("enterprise_value_high", 0))

        # Apply discount to multiples
        adjustment_pct_float = to_decimal(adjustment * 100)
        multiple_before_low, multiple_after_low = apply_discount_to_multiple(
            current_multiple_low, adjustment_pct_float
        )
        multiple_before_mid, multiple_after_mid = apply_discount_to_multiple(
            current_multiple_mid, adjustment_pct_float
        )
        multiple_before_high, multiple_after_high = apply_discount_to_multiple(
            current_multiple_high, adjustment_pct_float
        )

        # Recalculate EV from adjusted multiples
        ev_low_after = calculate_ev_from_multiple(metric_value, multiple_after_low)
        ev_mid_after = calculate_ev_from_multiple(metric_value, multiple_after_mid)
        ev_high_after = calculate_ev_from_multiple(metric_value, multiple_after_high)

        # Validate and correct range
        ev_low_after, ev_mid_after, ev_high_after = self._validate_and_correct_range(
            ev_low_after, ev_mid_after, ev_high_after
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

        # Build result and metadata
        result_dict = self.result_builder.build_result_dict(
            ev_low_float=ev_low_float,
            ev_mid_float=ev_mid_float,
            ev_high_float=ev_high_float,
            ev_low_before_float=ev_low_before_float,
            ev_mid_before_float=ev_mid_before_float,
            ev_high_before_float=ev_high_before_float,
            raw_ratio=raw_ratio,
            normalized_ratio=normalized_ratio,
            risk_level=risk_level,
            adjustment_pct=adjustment_pct,
            adjustment=adjustment,
            num_owners=num_owners,
            num_employees=num_employees,
            calibration_used=calibration_used,
            business_type_id=business_type_id,
            multiple_before_low=multiple_before_low,
            multiple_before_mid=multiple_before_mid,
            multiple_before_high=multiple_before_high,
            multiple_after_low=multiple_after_low,
            multiple_after_mid=multiple_after_mid,
            multiple_after_high=multiple_after_high,
            metric_value=metric_value,
            is_true_sole_trader=is_true_sole_trader,
            headcount_corroborated=headcount_corroborated,
            uncapped_adjustment_pct=to_decimal(uncapped_adjustment) * Decimal("100"),
            headcount_source=(
                "owner_profile" if headcount_corroborated else "registry_prefill_unverified"
            ),
        )

        metadata_dict = self.result_builder.build_metadata_dict(
            ev_low_before_float=ev_low_before_float,
            ev_mid_before_float=ev_mid_before_float,
            ev_high_before_float=ev_high_before_float,
            ev_low_float=ev_low_float,
            ev_mid_float=ev_mid_float,
            ev_high_float=ev_high_float,
            adjustment_pct=adjustment_pct,
            calibration_used=calibration_used,
            business_type_id=business_type_id,
            raw_ratio=raw_ratio,
            normalized_ratio=normalized_ratio,
        )

        return result_dict, metadata_dict

    def _validate_and_correct_range(
        self, ev_low_after: Decimal, ev_mid_after: Decimal, ev_high_after: Decimal
    ) -> Tuple[Decimal, Decimal, Decimal]:
        """
        Validate and correct EV range ordering.

        Args:
            ev_low_after: EV low after adjustment
            ev_mid_after: EV mid after adjustment
            ev_high_after: EV high after adjustment

        Returns:
            Tuple of (corrected_ev_low, corrected_ev_mid, corrected_ev_high)
        """
        if ev_low_after >= ev_mid_after or ev_mid_after >= ev_high_after:
            logger.warning(
                "⚠️ Invalid EV range detected after owner concentration adjustment, auto-correcting",
                extra={
                    "ev_low": to_decimal(ev_low_after),
                    "ev_mid": to_decimal(ev_mid_after),
                    "ev_high": to_decimal(ev_high_after),
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
                    "✓ Auto-corrected EV range after owner concentration adjustment",
                    extra={
                        "ev_low": to_decimal(ev_low_after),
                        "ev_mid": to_decimal(ev_mid_after),
                        "ev_high": to_decimal(ev_high_after),
                    },
                )
        return ev_low_after, ev_mid_after, ev_high_after
