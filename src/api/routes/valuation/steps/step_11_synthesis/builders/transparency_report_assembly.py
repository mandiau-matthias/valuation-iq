"""
Transparency report assembly helpers.

Keeps the Step 11 builder focused on orchestration while preserving the
public 0-11 transparency contract and optional sub-step rendering.
"""

from decimal import Decimal

from src.errors import DataQualityError, ValidationError
from src.utils.logging import get_logger

from ...base_step import StepStatus
from .coordinators.validation import BankGradeValidator

logger = get_logger(__name__)

INTEGER_STEPS = set(range(12))
STEP_DESCRIPTIONS = {
    0: "Data Quality Assessment: Validated input data completeness and quality",
    1: "Input Data & Business Profile: Collected company financials and business information",
    2: "Industry Benchmarking: Selected {primary_method} multiple from comparable companies",
    3: "Base Enterprise Value: Calculated enterprise value using industry multiples",
    4: "Owner Concentration: Applied {adjustment}% adjustment for key person risk",
    5: "Size Discount: Applied {adjustment}% for company size",
    6: "Liquidity Discount: Applied {adjustment}% for private company illiquidity",
    7: "EV to Equity Conversion: Converted enterprise value to equity value",
    8: "Ownership Adjustment: Applied {adjustment_pct}% {adjustment_type} for {ownership_pct}% ownership",
    9: "Confidence Analysis: Scored data quality at {confidence_score}%",
    10: "Range Methodology: Used {methodology} approach",
    11: "Final Result: Arrived at valuation range of €{low}K - €{high}K",
}
KEY_OUTPUT_EXCEPTIONS = (
    DataQualityError,
    ValidationError,
    ValueError,
    TypeError,
    AttributeError,
    KeyError,
)


def log_transparency_generation_start(
    previous_results: dict[object, object],
    *,
    methodologies: object,
    methodology_statement: object,
    academic_sources: object,
    professional_review_ready: object,
) -> None:
    steps_received = list(previous_results.keys())
    logger.debug(
        "🔍 _generate_transparency_report: Starting generation (bank-grade audit trail)",
        extra={
            "step_number": 11,
            "previous_results_count": len(previous_results),
            "steps_received": steps_received,
            "missing_steps": [i for i in range(12) if i not in steps_received],
            "step_statuses": {
                step_num: result.status.value for step_num, result in previous_results.items()
            },
            "has_methodologies": methodologies is not None,
            "has_methodology_statement": methodology_statement is not None,
            "has_academic_sources": academic_sources is not None,
            "has_professional_review_ready": professional_review_ready is not None,
        },
    )
    BankGradeValidator.log_calculation_provenance(
        "Transparency Report Generation",
        {
            "previous_results_count": len(previous_results),
            "steps_received": steps_received,
        },
        {
            "expected_steps": 12,
            "has_methodologies": methodologies is not None,
        },
        11,
    )


def build_transparency_steps(
    previous_results: dict[object, object],
    *,
    description_formatter: object,
    output_extractor: object,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    state = _new_step_state()
    calculation_steps = _build_public_steps(
        previous_results,
        description_formatter=description_formatter,
        output_extractor=output_extractor,
        state=state,
    )
    calculation_steps = _ensure_public_step_completeness(calculation_steps)
    sub_steps = _build_sub_steps(previous_results, output_extractor)
    calculation_steps = sorted(calculation_steps, key=lambda x: x.get("step", 999))
    _log_step_assembly(calculation_steps, sub_steps, state)
    return calculation_steps, sub_steps


def build_transparency_payload(
    *,
    calculation_steps: list[dict[str, object]],
    sub_steps: list[dict[str, object]],
    data_sources: object,
    adjustments_applied: object,
    confidence_breakdown: object,
) -> dict[str, object]:
    return {
        "calculation_steps": calculation_steps,
        "sub_steps": sub_steps,
        "data_sources": data_sources,
        "adjustments_applied": adjustments_applied,
        "confidence_breakdown": confidence_breakdown,
        "standards_compliance": ["IFRS 13", "IVS 2017"],
    }


def log_final_transparency_assembly(
    transparency: dict[str, object],
    *,
    data_sources: object,
    adjustments_applied: object,
) -> None:
    logger.debug(
        "📊 Transparency report components extracted (bank-grade validation)",
        extra={
            "step_number": 11,
            "data_sources_count": len(data_sources),
            "adjustments_count": len(adjustments_applied),
            "has_confidence_breakdown": transparency["confidence_breakdown"] is not None,
        },
    )
    BankGradeValidator.log_calculation_provenance(
        "Transparency Report Final Assembly",
        {
            "calculation_steps_count": len(transparency["calculation_steps"]),
            "data_sources_count": len(data_sources),
            "adjustments_count": len(adjustments_applied),
        },
        {
            "standards_compliance": transparency["standards_compliance"],
            "report_complete": True,
        },
        11,
    )


def add_optional_methodology_sections(
    transparency: dict[str, object],
    *,
    methodology_statement: object,
    academic_sources: object,
    professional_review_ready: object,
) -> None:
    if methodology_statement:
        transparency["methodology_statement"] = methodology_statement
    if academic_sources:
        transparency["academic_sources"] = academic_sources
    if professional_review_ready:
        transparency["professional_review_ready"] = professional_review_ready


def _new_step_state() -> dict[str, list[object]]:
    return {
        "steps_included": [],
        "steps_missing": [],
        "steps_with_outputs": [],
    }


def _build_public_steps(
    previous_results: dict[object, object],
    *,
    description_formatter: object,
    output_extractor: object,
    state: dict[str, list[object]],
) -> list[dict[str, object]]:
    calculation_steps = []
    for step_num in range(12):
        if step_num in previous_results:
            calculation_steps.append(
                _existing_step_data(
                    step_num,
                    previous_results[step_num],
                    previous_results,
                    description_formatter,
                    output_extractor,
                    state,
                )
            )
        else:
            calculation_steps.append(_missing_step_data(step_num))
            state["steps_missing"].append(step_num)
    return calculation_steps


def _existing_step_data(
    step_num: int,
    result: object,
    previous_results: dict[object, object],
    description_formatter: object,
    output_extractor: object,
    state: dict[str, list[object]],
) -> dict[str, object]:
    description_template = STEP_DESCRIPTIONS.get(step_num, f"Step {step_num}")
    description = description_formatter.format_step_description(
        description_template, step_num, result, previous_results
    )
    key_outputs = _extract_key_outputs(step_num, result, output_extractor)
    if key_outputs:
        state["steps_with_outputs"].append(step_num)

    step_data = {
        "step": result.step_number,
        "name": result.step_name,
        "description": description,
        "status": result.status.value,
        "execution_time_ms": getattr(result, "execution_time_ms", Decimal("0.0")),
        "key_outputs": key_outputs,
        "reason": result.metadata.get("reason") if result.status == StepStatus.SKIPPED else None,
        "error": result.error if result.status == StepStatus.FAILED else None,
    }
    _add_methodology_note(step_num, result, step_data)
    state["steps_included"].append(step_num)
    return step_data


def _extract_key_outputs(
    step_num: object,
    result: object,
    output_extractor: object,
) -> dict[str, object]:
    if result.status != StepStatus.COMPLETED:
        return {}

    try:
        return output_extractor.extract_key_outputs(result) or {}
    except KEY_OUTPUT_EXCEPTIONS as extract_error:
        logger.warning(
            f"⚠️ Failed to extract key_outputs for Step {step_num}",
            extra={
                "step_number": step_num,
                "error": str(extract_error),
                "error_type": type(extract_error).__name__,
            },
        )
        return {}


def _add_methodology_note(
    step_num: int,
    result: object,
    step_data: dict[str, object],
) -> None:
    if result.status != StepStatus.COMPLETED:
        return
    if step_num == 2:
        step_data["methodology_note"] = (
            f"Primary method: {result.result.get('primary_method', 'N/A')}"
        )
    elif step_num == 10:
        step_data["methodology_note"] = (
            f"Range methodology: {result.result.get('methodology', 'N/A')}"
        )


def _missing_step_data(step_num: object) -> dict[str, object]:
    return {
        "step": step_num,
        "name": f"Step {step_num}",
        "description": f"Step {step_num} not executed",
        "status": "not_executed",
        "execution_time_ms": Decimal("0.0"),
        "key_outputs": {},
        "reason": "Step not executed",
        "error": None,
    }


def _ensure_public_step_completeness(
    calculation_steps: list[dict[str, object]],
) -> list[dict[str, object]]:
    expected_steps = set(range(12))
    actual_steps = {step.get("step") for step in calculation_steps}
    missing_steps = expected_steps - actual_steps
    if not missing_steps:
        return calculation_steps

    logger.error(
        "❌ CRITICAL: Transparency report missing steps!",
        extra={
            "step_number": 11,
            "expected_steps": sorted(expected_steps),
            "actual_steps": sorted(actual_steps),
            "missing_steps": sorted(missing_steps),
            "total_steps_included": len(calculation_steps),
        },
    )
    calculation_steps.extend(_missing_step_data(step) for step in missing_steps)
    logger.warning(
        "⚠️ Added missing steps to transparency report",
        extra={
            "added_steps": sorted(missing_steps),
            "final_step_count": len(calculation_steps),
        },
    )
    return calculation_steps


def _build_sub_steps(
    previous_results: dict[object, object],
    output_extractor: object,
) -> list[dict[str, object]]:
    sub_steps = []
    for step_key, result in previous_results.items():
        if step_key in INTEGER_STEPS:
            continue
        sub_steps.append(_sub_step_data(step_key, result, output_extractor))
    sub_steps.sort(key=lambda x: float(x.get("step", 999)))
    return sub_steps


def _sub_step_data(
    step_key: object,
    result: object,
    output_extractor: object,
) -> dict[str, object]:
    sub_step_data = {
        "step": step_key,
        "name": getattr(result, "step_name", f"Sub-step {step_key}"),
        "status": result.status.value if hasattr(result, "status") else "unknown",
        "parent_step": int(step_key) if isinstance(step_key, float) else None,
        "execution_time_ms": getattr(result, "execution_time_ms", Decimal("0.0")),
    }
    if getattr(result, "status", None) == StepStatus.COMPLETED:
        key_outputs = _extract_sub_step_key_outputs(result, output_extractor)
        if key_outputs:
            sub_step_data["key_outputs"] = key_outputs
    return sub_step_data


def _extract_sub_step_key_outputs(
    result: object,
    output_extractor: object,
) -> dict[str, object]:
    try:
        return output_extractor.extract_key_outputs(result) or {}
    except KEY_OUTPUT_EXCEPTIONS:
        return {}


def _log_step_assembly(
    calculation_steps: list[dict[str, object]],
    sub_steps: list[dict[str, object]],
    state: dict[str, list[object]],
) -> None:
    steps_included = state["steps_included"]
    steps_with_outputs = state["steps_with_outputs"]
    logger.debug(
        "✅ _generate_transparency_report: Calculation steps built (bank-grade audit trail)",
        extra={
            "step_number": 11,
            "total_steps_included": len(calculation_steps),
            "sub_steps_included": len(sub_steps),
            "sub_step_ids": [s["step"] for s in sub_steps],
            "expected_steps_count": 12,
            "steps_included": sorted([step.get("step") for step in calculation_steps]),
            "steps_missing": state["steps_missing"],
            "steps_with_outputs": steps_with_outputs,
            "steps_without_outputs": [
                step for step in steps_included if step not in steps_with_outputs
            ],
            "all_steps_present": len(calculation_steps) == 12,
            "calculation_steps_validated": True,
        },
    )
    if len(calculation_steps) != 12:
        logger.warning(
            "⚠️ Transparency report has unexpected step count (expected 12)",
            extra={
                "step_number": 11,
                "expected_steps": 12,
                "actual_steps": len(calculation_steps),
                "missing_steps": [
                    i for i in range(12) if i not in [s.get("step") for s in calculation_steps]
                ],
            },
        )
