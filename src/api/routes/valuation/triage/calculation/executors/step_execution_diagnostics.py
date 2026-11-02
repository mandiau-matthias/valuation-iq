"""Diagnostic logging and recovery helpers for step execution."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from src.api.routes.valuation.steps.base_step import CalculationStep, StepOutput, StepStatus

if TYPE_CHECKING:
    from src.api.schemas import ValuationRequest


StepResults = dict[int, StepOutput]
ExecutionContext = dict[str, object]
LogPayload = dict[str, object]


def assign_execution_time(output: StepOutput, step_start: float, now: float) -> None:
    execution_time = (now - step_start) * 1000
    output.execution_time_ms = Decimal(str(round(execution_time, 2)))


def log_step_entry(
    logger: object,
    step: CalculationStep,
    request: ValuationRequest,
    previous_results: StepResults,
    context: ExecutionContext,
) -> None:
    if step.step_number == 0:
        logger.debug(
            "🔍 DIAGNOSTIC: Step 0 execution entry point in execute",
            extra={
                "step_number": 0,
                "step_name": step.step_name,
                "step_class": step.__class__.__name__,
                "has_request": request is not None,
                "request_type": type(request).__name__ if request else None,
                "previous_results_count": len(previous_results),
                "correlation_id": context.get("correlation_id"),
            },
        )
    elif step.step_number == 2:
        logger.debug(
            "🔍 DIAGNOSTIC: Step 2 execution entry point",
            extra={
                "step_number": 2,
                "step_name": step.step_name,
                "available_previous_steps": list(previous_results.keys()),
                "step_0_exists": 0 in previous_results,
                "step_0_status": _previous_step_status(previous_results, 0),
                "step_1_exists": 1 in previous_results,
                "step_1_status": _previous_step_status(previous_results, 1),
                "correlation_id": context.get("correlation_id"),
            },
        )


def log_pre_storage_snapshot(
    logger: object,
    step: CalculationStep,
    output: StepOutput,
) -> None:
    if step.step_number not in {2, 4, 5, 6}:
        return

    result_dict = output.result if isinstance(getattr(output, "result", None), dict) else {}
    logger.debug(
        f"🔍 DIAGNOSTIC Step {step.step_number} - StepOutput received before storage",
        extra={
            "step_number": step.step_number,
            "step_name": step.step_name,
            "status": output.status.value if hasattr(output, "status") else None,
            "result_type": type(output.result).__name__ if hasattr(output, "result") else None,
            "result_is_dict": (
                isinstance(output.result, dict) if hasattr(output, "result") else False
            ),
            "result_keys": list(result_dict.keys()),
            "result_size": len(result_dict),
            "key_fields": _key_fields_for_step(step.step_number, result_dict),
            "has_metadata": hasattr(output, "metadata") and bool(output.metadata),
            "metadata_keys": (
                list(output.metadata.keys())
                if hasattr(output, "metadata") and isinstance(output.metadata, dict)
                else []
            ),
        },
    )


def log_optional_dependency_status(
    logger: object,
    step: CalculationStep,
    output: StepOutput,
    previous_results: StepResults,
) -> None:
    if not step.optional_dependencies or output.status != StepStatus.COMPLETED:
        return

    missing_optional = step.get_missing_optional_dependencies(previous_results)
    available_optional = step.get_available_optional_dependencies(previous_results)
    skipped_optional = [
        dep
        for dep in step.optional_dependencies
        if dep in previous_results and previous_results[dep].status == StepStatus.SKIPPED
    ]
    degraded_optional = [dep for dep in missing_optional if dep not in skipped_optional]

    if degraded_optional:
        logger.info(
            f"Step {step.step_number} completed with optional dependencies unavailable",
            extra={
                "step_number": step.step_number,
                "step_name": step.step_name,
                "optional_dependencies": step.optional_dependencies,
                "available_optional": available_optional,
                "missing_optional": degraded_optional,
                "skipped_optional": skipped_optional,
                "impact": "Reduced transparency or detail only; calculation output completed successfully",
            },
        )
    elif skipped_optional:
        logger.debug(
            f"Step {step.step_number} optional dependency skipped by design",
            extra={
                "step_number": step.step_number,
                "step_name": step.step_name,
                "optional_dependencies": step.optional_dependencies,
                "available_optional": available_optional,
                "skipped_optional": skipped_optional,
            },
        )
    else:
        logger.info(
            f"✅ Step {step.step_number} executed with full optional dependencies",
            extra={
                "step_number": step.step_number,
                "step_name": step.step_name,
                "optional_dependencies": step.optional_dependencies,
                "all_optional_available": True,
            },
        )


def log_step_completion(
    logger: object,
    result_sanitizer: object,
    value_chain_logger: object,
    business_type_triage: object,
    step: CalculationStep,
    request: ValuationRequest,
    previous_results: StepResults,
    context: ExecutionContext,
    output: StepOutput,
) -> None:
    log_extra = _completion_log_extra(business_type_triage, step, request, output)
    calculation_summary = _result_summary(output.result) if output.result else {}

    if calculation_summary:
        log_extra.update(
            {
                key: value
                for key, value in calculation_summary.items()
                if value and key in {"calculation_values", "adjustments", "multiples", "metadata"}
            }
        )
        _add_legacy_midpoint_fields(log_extra, output.result)
        value_chain_logger.log_value_chain_transformation(step, previous_results, output)
        logger.debug(
            f"📊 Step {step.step_number}: {step.step_name} - Calculation Complete",
            extra={
                "step_number": step.step_number,
                "step_name": step.step_name,
                "status": output.status.value,
                "execution_time_ms": output.execution_time_ms,
                "calculation_values": calculation_summary.get("calculation_values", {}),
                "adjustments": calculation_summary.get("adjustments", {}),
                "multiples": calculation_summary.get("multiples", {}),
                "metadata": calculation_summary.get("metadata", {}),
                "company": request.company_name,
                "correlation_id": context.get("correlation_id"),
            },
        )

    logger.debug(
        f"📤 Step {step.step_number} output data",
        extra={
            "step_number": step.step_number,
            "step_name": step.step_name,
            "output_result": result_sanitizer.sanitize_output_data(output.result),
            "output_metadata": output.metadata,
            "output_status": output.status.value,
        },
    )
    logger.debug(f"✓ Step {step.step_number} completed", extra=log_extra)


def preserve_step_2_result_before_return(
    logger: object,
    step: CalculationStep,
    output: StepOutput,
    context: ExecutionContext,
) -> StepOutput:
    if step.step_number != 2:
        return output

    correlation_id = context.get("correlation_id") if context else None
    _log_step_2_validation_state(logger, step, output, correlation_id, "before_validation")

    result_is_dict = isinstance(getattr(output, "result", None), dict)
    if not result_is_dict:
        logger.error(
            "❌ [DIAG-VALIDATE] CRITICAL: Step 2 output.result is missing or not a dict before return",
            extra={
                "step_number": 2,
                "step_name": step.step_name,
                "correlation_id": correlation_id,
                "operation": "validation_missing_result",
                "has_result": hasattr(output, "result"),
                "result_type": type(output.result).__name__ if hasattr(output, "result") else None,
                "has_metadata": hasattr(output, "metadata"),
                "metadata_keys": _metadata_keys(output),
            },
        )
        recovery = _recover_step_2_result(output, require_non_empty_dict=False)
        _log_recovery(logger, correlation_id, recovery, empty_case=False)
    elif len(output.result) == 0:
        logger.warning(
            "⚠️ [DIAG-VALIDATE] CRITICAL: Step 2 output.result is empty before return",
            extra={
                "step_number": 2,
                "step_name": step.step_name,
                "correlation_id": correlation_id,
                "operation": "validation_empty_result",
                "has_metadata": hasattr(output, "metadata"),
                "metadata_keys": _metadata_keys(output),
            },
        )
        recovery = _recover_step_2_result(output, require_non_empty_dict=True)
        _log_recovery(logger, correlation_id, recovery, empty_case=True)

    _log_step_2_validation_state(logger, step, output, correlation_id, "after_validation")
    return output


def _previous_step_status(previous_results: StepResults, step_number: int) -> object:
    if step_number not in previous_results or not hasattr(previous_results[step_number], "status"):
        return None
    return previous_results[step_number].status.value


def _key_fields_for_step(step_number: int, result_dict: LogPayload) -> LogPayload:
    if step_number == 2:
        return {
            "ev_ebitda_multiple": result_dict.get("ev_ebitda_multiple"),
            "ev_revenue_multiple": result_dict.get("ev_revenue_multiple"),
            "primary_method": result_dict.get("primary_method"),
        }
    if step_number == 4:
        return {
            "owner_concentration_adjustment": result_dict.get("owner_concentration_adjustment"),
            "adjustment_percentage": result_dict.get("adjustment_percentage"),
            "risk_level": result_dict.get("risk_level"),
            "owner_employee_ratio": result_dict.get("owner_employee_ratio"),
        }
    if step_number == 5:
        return {
            "size_discount_percentage": result_dict.get("size_discount_percentage"),
            "revenue_tier": result_dict.get("revenue_tier"),
            "base_discount": result_dict.get("base_discount"),
        }
    return {
        "total_discount_percentage": result_dict.get("total_discount_percentage"),
        "base_discount": result_dict.get("base_discount"),
        "margin_bonus": result_dict.get("margin_bonus"),
    }


def _completion_log_extra(
    business_type_triage: object,
    step: CalculationStep,
    request: ValuationRequest,
    output: StepOutput,
) -> LogPayload:
    log_extra: LogPayload = {
        "step_number": step.step_number,
        "step_name": step.step_name,
        "execution_time_ms": output.execution_time_ms,
        "status": output.status.value,
        "company": request.company_name,
    }
    try:
        log_extra["business_category"] = business_type_triage.get_business_type_category(
            getattr(request, "business_type_id", None),
            getattr(request, "business_model", None),
            getattr(request, "industry", None),
            category_id=getattr(request, "category_id", None),
        ).value
    except (ValueError, TypeError, AttributeError, KeyError):
        pass
    return log_extra


def _result_summary(result: LogPayload) -> dict[str, LogPayload]:
    return {
        "calculation_values": _calculation_values(result),
        "adjustments": _adjustments(result),
        "multiples": _multiples(result),
        "metadata": _metadata(result),
    }


def _calculation_values(result: LogPayload) -> LogPayload:
    values: LogPayload = {}
    for prefix in (
        "enterprise_value",
        "equity_value",
        "ownership_adjusted_equity",
        "valuation",
    ):
        mid_key = f"{prefix}_mid"
        if mid_key in result:
            values[mid_key] = result.get(mid_key)
            values[f"{prefix}_low"] = result.get(f"{prefix}_low")
            values[f"{prefix}_high"] = result.get(f"{prefix}_high")
    return values


def _adjustments(result: LogPayload) -> LogPayload:
    mapping = {
        "size_discount_percentage": "size_discount_pct",
        "liquidity_discount_percentage": "liquidity_discount_pct",
        "owner_concentration_adjustment": "owner_concentration_pct",
        "ownership_adjustment_percentage": "ownership_adjustment_pct",
    }
    return {target: result.get(source) for source, target in mapping.items() if source in result}


def _multiples(result: LogPayload) -> LogPayload:
    return {
        key: result.get(key)
        for key in ("ev_ebitda_multiple", "ev_revenue_multiple", "primary_method")
        if key in result
    }


def _metadata(result: LogPayload) -> LogPayload:
    return {
        key: result.get(key)
        for key in ("confidence_score", "data_quality_score", "comparables_count")
        if key in result
    }


def _add_legacy_midpoint_fields(log_extra: LogPayload, result: LogPayload) -> None:
    if "enterprise_value_mid" in result:
        log_extra["ev_mid"] = result.get("enterprise_value_mid")
    if "equity_value_mid" in result:
        log_extra["equity_mid"] = result.get("equity_value_mid")
    if "ownership_adjusted_equity_mid" in result:
        log_extra["ownership_adjusted_equity_mid"] = result.get("ownership_adjusted_equity_mid")


def _metadata_keys(output: StepOutput) -> list[str]:
    if hasattr(output, "metadata") and isinstance(output.metadata, dict):
        return list(output.metadata.keys())
    return []


def _recover_step_2_result(
    output: StepOutput,
    *,
    require_non_empty_dict: bool,
) -> tuple[bool, str | None]:
    metadata = output.metadata if isinstance(getattr(output, "metadata", None), dict) else {}
    for key in ("result_backup", "multiples_backup"):
        backup = metadata.get(key)
        if require_non_empty_dict and (not isinstance(backup, dict) or not backup):
            continue
        if backup is None:
            continue
        output.result = (
            backup.copy() if key == "multiples_backup" and isinstance(backup, dict) else backup
        )
        return True, f"metadata.{key}"
    return False, None


def _log_recovery(
    logger: object,
    correlation_id: object,
    recovery: tuple[bool, str | None],
    *,
    empty_case: bool,
) -> None:
    recovery_attempted, recovery_source = recovery
    if recovery_attempted:
        suffix = " (empty case)" if empty_case else ""
        logger.warning(
            f"✅ [DIAG-VALIDATE] Recovered Step 2 result from metadata{suffix}",
            extra={
                "step_number": 2,
                "correlation_id": correlation_id,
                "recovery_source": recovery_source,
            },
        )

    operation = "after_recovery_empty" if empty_case else "after_recovery"
    logger.debug(
        "🔍 [DIAG-VALIDATE] After recovery attempt"
        + (" (empty result case)" if empty_case else ""),
        extra={
            "step_number": 2,
            "correlation_id": correlation_id,
            "operation": operation,
            "recovery_attempted": recovery_attempted,
            "recovery_source": recovery_source,
        },
    )


def _log_step_2_validation_state(
    logger: object,
    step: CalculationStep,
    output: StepOutput,
    correlation_id: object,
    operation: str,
) -> None:
    result = output.result if isinstance(getattr(output, "result", None), dict) else {}
    logger.debug(
        f"🔍 [DIAG-VALIDATE] {'Before Step 2 validation' if operation == 'before_validation' else 'After Step 2 validation'}",
        extra={
            "step_number": 2,
            "step_name": step.step_name,
            "correlation_id": correlation_id,
            "operation": operation,
            "has_result": hasattr(output, "result"),
            "result_type": type(output.result).__name__ if hasattr(output, "result") else None,
            "result_is_dict": (
                isinstance(output.result, dict) if hasattr(output, "result") else False
            ),
            "result_keys": list(result.keys()),
            "result_size": len(result),
            "has_ev_ebitda_multiple": "ev_ebitda_multiple" in result,
            "has_ev_revenue_multiple": "ev_revenue_multiple" in result,
            "ev_ebitda_multiple_value": result.get("ev_ebitda_multiple"),
            "ev_revenue_multiple_value": result.get("ev_revenue_multiple"),
        },
    )
