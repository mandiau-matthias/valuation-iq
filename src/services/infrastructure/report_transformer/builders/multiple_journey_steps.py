"""
Step assembly helpers for the multiple journey builder.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Protocol

from src.utils.core.data_extraction_helpers import extract_step_result
from src.utils.decimal_helpers import from_decimal, to_decimal

MULTIPLE_AFTER_FIELDS = (
    "multiple_after_mid",
    "multiple_after",
    "current_multiple_mid",
    "final_multiple",
)
MULTIPLE_BEFORE_FIELDS = (
    "multiple_before_mid",
    "multiple_before",
    "previous_multiple",
)


StepResult = dict[str, object]
StepResults = dict[object, object]
JourneyRow = dict[str, object]
Journey = list[JourneyRow]


class ResponseLike(Protocol):
    company_name: str


class LoggerLike(Protocol):
    def error(self, message: str, *args: object, **kwargs: object) -> object: ...


@dataclass(frozen=True)
class DiscountStepSpec:
    engine_step: int
    display_step: str
    name: str
    source: str
    default_reason: str
    extraction_label: str
    calculation_label: str
    failure_label: str
    missing_label: str
    reason_field: str | None = None
    reason_suffix: str = ""
    treat_empty_multiple_as_missing: bool = False


OWNER_CONCENTRATION_STEP = DiscountStepSpec(
    engine_step=4,
    display_step="3",
    name="Owner Concentration Discount",
    source="Owner dependency analysis",
    default_reason="Owner dependency risk",
    extraction_label="Step 4 owner concentration multiple extraction",
    calculation_label="Calculated Step 4 multiple from EV/EBITDA",
    failure_label="Failed to calculate Step 4 multiple from EV/EBITDA",
    missing_label="Step 4 multiple fields not found",
    reason_field="risk_level",
    reason_suffix=" owner dependency risk",
    treat_empty_multiple_as_missing=True,
)

SIZE_DISCOUNT_STEP = DiscountStepSpec(
    engine_step=5,
    display_step="4",
    name="Size Discount",
    source="Company size analysis",
    default_reason="Small company risk premium",
    extraction_label="Step 5 size discount multiple extraction",
    calculation_label="Calculated Step 5 multiple from EV/EBITDA",
    failure_label="Failed to calculate Step 5 multiple from EV/EBITDA",
    missing_label="Step 5 multiple fields not found",
)

LIQUIDITY_DISCOUNT_STEP = DiscountStepSpec(
    engine_step=6,
    display_step="5",
    name="Liquidity Discount",
    source="Liquidity analysis",
    default_reason="Private company illiquidity",
    extraction_label="Step 6 liquidity discount multiple extraction",
    calculation_label="Calculated Step 6 multiple from EV/EBITDA",
    failure_label="Failed to calculate Step 6 multiple from EV/EBITDA",
    missing_label="Step 6 multiple fields not found",
)


def append_base_multiple_step(
    *,
    journey: Journey,
    step_result: StepResult | None,
    response: ResponseLike,
    logger: LoggerLike,
) -> object | None:
    base_multiple = None
    correlation_id = getattr(response, "correlation_id", None)

    if step_result:
        base_multiple = pick_first_present(
            step_result,
            (
                "final_ebitda_multiple",
                "ev_ebitda_multiple",
                "ev_ebitda_p50",
            ),
        )
        logger.error(
            "[MULTIPLE-JOURNEY-BUILDER] Step 2 base multiple extraction",
            extra={
                "company_name": response.company_name,
                "correlation_id": correlation_id,
                "base_multiple": str(base_multiple) if is_present(base_multiple) else None,
                "step_2_fields": list(step_result.keys()),
                "found_in": _field_with_present_value(
                    step_result,
                    (
                        "final_ebitda_multiple",
                        "ev_ebitda_multiple",
                        "ev_ebitda_p50",
                    ),
                )
                or "none",
                "will_add_to_journey": is_present(base_multiple),
            },
        )

        if is_present(base_multiple):
            logger.error(
                "[MULTIPLE-JOURNEY-BUILDER] Adding Step 2 base multiple to journey",
                extra={
                    "company_name": response.company_name,
                    "correlation_id": correlation_id,
                    "base_multiple": str(base_multiple),
                    "journey_length_after": len(journey) + 1,
                },
            )
            _append_journey_row(
                journey=journey,
                multiple=base_multiple,
                adjustment=None,
                row={
                    "step": "1",
                    "name": "Base Multiple Selection",
                    "source": "P50 from comparables",
                    "reason": "Median multiple from comparable company analysis",
                },
                response=response,
                logger=logger,
                failure_message="Failed to convert base multiple to Decimal",
            )
        return base_multiple

    logger.error(
        "[MULTIPLE-JOURNEY-BUILDER] Step 2 not found or invalid",
        extra={
            "company_name": response.company_name,
            "correlation_id": correlation_id,
            "has_step_2": False,
            "step_2_type": None,
        },
    )
    return base_multiple


def append_quality_calibration_step(
    *,
    journey: Journey,
    step_result: StepResult | None,
    response: ResponseLike,
    logger: LoggerLike,
) -> None:
    if not step_result:
        return

    correlation_id = getattr(response, "correlation_id", None)
    multiple_after = pick_first_present(
        step_result,
        (
            "multiple_after",
            "multiple_after_mid",
            "current_multiple_mid",
            "final_multiple",
            "multiple",
        ),
    )
    multiple_before = pick_first_present(
        step_result,
        (
            "multiple_before",
            "multiple_before_mid",
            "previous_multiple",
        ),
    )
    logger.error(
        "[MULTIPLE-JOURNEY-BUILDER] Step 2.5 multiple extraction attempt",
        extra={
            "company_name": response.company_name,
            "correlation_id": correlation_id,
            "multiple_after": str(multiple_after) if is_present(multiple_after) else None,
            "multiple_before": str(multiple_before) if is_present(multiple_before) else None,
            "available_fields": list(step_result.keys()),
            "has_multiple_after": is_present(multiple_after),
            "has_multiple_before": is_present(multiple_before),
        },
    )

    prev_multiple = journey[-1]["multiple"] if journey else None
    if not is_present(multiple_after) and prev_multiple is not None:
        multiple_after = prev_multiple
        logger.error(
            "[MULTIPLE-JOURNEY-BUILDER] Step 2.5 multiple_after is missing, using previous step's multiple for audit trail",
            extra={
                "company_name": response.company_name,
                "correlation_id": correlation_id,
                "prev_multiple": str(prev_multiple),
                "will_use_prev_multiple": True,
            },
        )

    if not is_present(multiple_after):
        logger.error(
            "[MULTIPLE-JOURNEY-BUILDER] Step 2.5 multiple fields not found and no previous step available",
            extra={
                "company_name": response.company_name,
                "correlation_id": correlation_id,
                "available_fields": list(step_result.keys()),
                "step_2_5_result_type": type(step_result).__name__,
                "has_prev_multiple": prev_multiple is not None,
            },
        )
        return

    adjustment = _quality_adjustment(
        multiple_after=multiple_after,
        multiple_before=multiple_before,
        prev_multiple=prev_multiple,
        step_result=step_result,
    )
    margin_analysis = step_result.get("margin_analysis")
    reason = (
        margin_analysis.get("volatility_level", "Earnings quality adjustment")
        if isinstance(margin_analysis, dict)
        else "Earnings quality adjustment"
    )
    if _append_journey_row(
        journey=journey,
        multiple=multiple_after,
        adjustment=adjustment,
        row={
            "step": "2.5",
            "name": "Multiple Calibration",
            "source": "Quality analysis",
            "reason": reason,
        },
        response=response,
        logger=logger,
        failure_message="Failed to convert Step 2.5 multiple to Decimal",
    ):
        logger.error(
            "[MULTIPLE-JOURNEY-BUILDER] Adding Step 2.5 to journey",
            extra={
                "company_name": response.company_name,
                "correlation_id": correlation_id,
                "multiple_after": str(multiple_after),
                "adjustment": str(adjustment),
                "journey_length_after": len(journey),
                "used_fallback": (
                    prev_multiple is not None and not is_present(step_result.get("multiple_after"))
                ),
            },
        )


def append_discount_step(
    *,
    journey: Journey,
    step_results: StepResults,
    spec: DiscountStepSpec,
    response: ResponseLike,
    logger: LoggerLike,
) -> None:
    step_result = extract_step_result(step_results.get(spec.engine_step))
    if not step_result:
        return

    correlation_id = getattr(response, "correlation_id", None)
    multiple_after = pick_first_present(step_result, MULTIPLE_AFTER_FIELDS)
    if spec.treat_empty_multiple_as_missing and _is_blank_string(multiple_after):
        multiple_after = None
    multiple_before = pick_first_present(step_result, MULTIPLE_BEFORE_FIELDS)

    if not is_present(multiple_after):
        multiple_after = calculate_multiple_from_ev_ebitda(
            step_results=step_results,
            step_result=step_result,
            response=response,
            logger=logger,
            calculation_label=spec.calculation_label,
            failure_label=spec.failure_label,
        )

    logger.error(
        f"[MULTIPLE-JOURNEY-BUILDER] {spec.extraction_label}",
        extra={
            "company_name": response.company_name,
            "correlation_id": correlation_id,
            "multiple_after": str(multiple_after) if is_present(multiple_after) else None,
            "multiple_before": str(multiple_before) if is_present(multiple_before) else None,
            "available_fields": list(step_result.keys()),
            "will_add_to_journey": is_present(multiple_after),
            "journey_length_before": len(journey),
        },
    )

    if not is_present(multiple_after):
        logger.error(
            f"[MULTIPLE-JOURNEY-BUILDER] {spec.missing_label}",
            extra={
                "company_name": response.company_name,
                "correlation_id": correlation_id,
                "multiple_after": str(multiple_after) if is_present(multiple_after) else None,
                "multiple_before": str(multiple_before) if is_present(multiple_before) else None,
                "available_fields": list(step_result.keys()),
            },
        )
        return

    adjustment = calculate_adjustment(
        multiple_after=multiple_after,
        multiple_before=multiple_before,
        journey=journey,
    )
    if _append_journey_row(
        journey=journey,
        multiple=multiple_after,
        adjustment=adjustment,
        row={
            "step": spec.display_step,
            "name": spec.name,
            "source": spec.source,
            "reason": _discount_reason(step_result, spec),
        },
        response=response,
        logger=logger,
        failure_message=f"Failed to convert Step {spec.engine_step} multiple to Decimal",
    ):
        logger.error(
            f"[MULTIPLE-JOURNEY-BUILDER] Adding Step {spec.engine_step} to journey",
            extra={
                "company_name": response.company_name,
                "correlation_id": correlation_id,
                "multiple_after": str(multiple_after),
                "adjustment": str(adjustment),
                "journey_length_after": len(journey),
            },
        )


def pick_first_present(source: StepResult, fields: tuple[str, ...]) -> object | None:
    for field in fields:
        value = source.get(field)
        if is_present(value):
            return value
    return None


def is_present(value: object | None) -> bool:
    return value is not None and not _is_blank_string(value)


def calculate_multiple_from_ev_ebitda(
    *,
    step_results: StepResults,
    step_result: StepResult,
    response: ResponseLike,
    logger: LoggerLike,
    calculation_label: str,
    failure_label: str,
) -> object | None:
    ev_mid = step_result.get("enterprise_value_mid")
    if not is_present(ev_mid):
        return None

    ebitda = _get_step_one_ebitda(step_results)
    if not is_present(ebitda):
        return None

    try:
        ebitda_decimal = to_decimal(ebitda)
        if ebitda_decimal <= 0:
            return None
        calculated_multiple = to_decimal(ev_mid) / ebitda_decimal
        multiple_after = from_decimal(calculated_multiple)
        logger.error(
            f"[MULTIPLE-JOURNEY-BUILDER] {calculation_label}",
            extra={
                "company_name": response.company_name,
                "correlation_id": getattr(response, "correlation_id", None),
                "ev_mid": str(ev_mid),
                "ebitda": str(ebitda),
                "calculated_multiple": str(multiple_after),
            },
        )
        return multiple_after
    except (ValueError, TypeError, InvalidOperation, ZeroDivisionError) as error:
        logger.error(
            f"[MULTIPLE-JOURNEY-BUILDER] {failure_label}",
            extra={
                "company_name": response.company_name,
                "correlation_id": getattr(response, "correlation_id", None),
                "error": str(error),
                "ev_mid": str(ev_mid) if is_present(ev_mid) else None,
                "ebitda": str(ebitda) if is_present(ebitda) else None,
            },
        )
        return None


def calculate_adjustment(
    *,
    multiple_after: object,
    multiple_before: object | None,
    journey: Journey,
) -> object:
    if is_present(multiple_before):
        return from_decimal(to_decimal(multiple_after) - to_decimal(multiple_before))
    if journey:
        prev_multiple = journey[-1]["multiple"]
        return from_decimal(to_decimal(multiple_after) - to_decimal(str(prev_multiple)))
    return Decimal("0")


def _append_journey_row(
    *,
    journey: Journey,
    multiple: object,
    adjustment: object | None,
    row: JourneyRow,
    response: ResponseLike,
    logger: LoggerLike,
    failure_message: str,
) -> bool:
    try:
        multiple_float = float(from_decimal(to_decimal(multiple)))
        adjustment_float = (
            None
            if adjustment is None
            else float(adjustment) if isinstance(adjustment, Decimal) else adjustment
        )
        journey.append(
            {
                **row,
                "multiple": multiple_float,
                "adjustment": adjustment_float,
            }
        )
        return True
    except (ValueError, TypeError, InvalidOperation) as error:
        logger.error(
            f"[MULTIPLE-JOURNEY-BUILDER] {failure_message}",
            extra={
                "company_name": response.company_name,
                "correlation_id": getattr(response, "correlation_id", None),
                "multiple_after": str(multiple),
                "multiple_after_type": type(multiple).__name__,
                "error": str(error),
            },
            exc_info=True,
        )
        return False


def _quality_adjustment(
    *,
    multiple_after: object,
    multiple_before: object | None,
    prev_multiple: object | None,
    step_result: StepResult,
) -> object:
    if prev_multiple is not None and is_present(multiple_before):
        return from_decimal(to_decimal(multiple_after) - to_decimal(multiple_before))
    if prev_multiple is not None:
        return from_decimal(to_decimal(multiple_after) - to_decimal(str(prev_multiple)))
    quality_adjustment = step_result.get("quality_multiple_adjustment")
    if is_present(quality_adjustment):
        return from_decimal(to_decimal(quality_adjustment))
    return Decimal("0")


def _get_step_one_ebitda(step_results: StepResults) -> object | None:
    step_1_result = extract_step_result(step_results.get(1))
    if not step_1_result:
        return None
    ebitda = step_1_result.get("ebitda")
    if ebitda is None:
        ebitda = step_1_result.get("normalized_ebitda")
    return ebitda


def _discount_reason(step_result: StepResult, spec: DiscountStepSpec) -> str:
    if spec.reason_field:
        reason_value = step_result.get(spec.reason_field, "")
        if reason_value:
            return f"{reason_value}{spec.reason_suffix}"
    return spec.default_reason


def _field_with_present_value(source: StepResult, fields: tuple[str, ...]) -> str | None:
    for field in fields:
        if is_present(source.get(field)):
            return field
    return None


def _is_blank_string(value: object | None) -> bool:
    return isinstance(value, str) and value.strip() == ""
