"""Step result sanitization helpers."""

from __future__ import annotations

from collections.abc import Mapping

from src.api.routes.valuation.steps.base_step import CalculationStep, StepOutput, StepStatus
from src.utils.exceptions import DataQualityError


def sanitize_step_output(
    logger: object,
    step: CalculationStep,
    output: StepOutput,
    context: Mapping[str, object] | None,
) -> StepOutput:
    correlation_id = context.get("correlation_id") if context else None
    original_result = getattr(output, "result", None)

    if not isinstance(original_result, dict):
        return output

    try:
        sanitized_result = step.sanitize_step_result(original_result)
    except (
        DataQualityError,
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
    ) as sanitize_error:
        _log_sanitization_exception(logger, step, output, correlation_id, sanitize_error)
        sanitized_result = original_result

    if not isinstance(sanitized_result, dict):
        return _rebuild_output_if_modified(logger, step, output, sanitized_result)

    if not sanitized_result and original_result:
        _log_empty_preserved(logger, step, output, correlation_id)
        return output

    if not sanitized_result:
        _log_empty_result_once(logger, step, output, correlation_id)
        return output

    if sanitized_result != original_result:
        _log_sanitization_modified(logger, step, sanitized_result, correlation_id)
        return _rebuild_output_if_modified(logger, step, output, sanitized_result)

    return output


def _log_empty_preserved(
    logger: object,
    step: CalculationStep,
    output: StepOutput,
    correlation_id: object,
) -> None:
    logger.error(
        "❌ [DIAG-SANITIZE] Result became empty after sanitization - preserving original",
        extra={
            "step_number": step.step_number,
            "step_name": step.step_name,
            "correlation_id": correlation_id,
            "operation": "sanitization_empty_result_preserved",
            "original_result_keys": list(output.result.keys()),
            "original_result_size": len(output.result),
        },
    )


def _log_empty_result_once(
    logger: object,
    step: CalculationStep,
    output: StepOutput,
    correlation_id: object,
) -> None:
    if output.status == StepStatus.SKIPPED and len(output.result) == 0:
        return
    logger.warning(
        "⚠️ [DIAG-SANITIZE] Result became empty after sanitization",
        extra={
            "step_number": step.step_number,
            "step_name": step.step_name,
            "correlation_id": correlation_id,
            "operation": "sanitization_empty_result",
            "original_result_keys": list(output.result.keys()),
            "original_result_size": len(output.result),
        },
    )


def _log_sanitization_modified(
    logger: object,
    step: CalculationStep,
    sanitized_result: dict[str, object],
    correlation_id: object,
) -> None:
    logger.info(
        "⚠️ [DIAG-SANITIZE] Result modified during sanitization (NaN/Infinity values replaced)",
        extra={
            "step_number": step.step_number,
            "step_name": step.step_name,
            "correlation_id": correlation_id,
            "operation": "after_sanitization",
            "sanitized_result_size": len(sanitized_result),
            "result_modified": True,
        },
    )


def _log_sanitization_exception(
    logger: object,
    step: CalculationStep,
    output: StepOutput,
    correlation_id: object,
    sanitize_error: Exception,
) -> None:
    logger.error(
        "❌ [DIAG-SANITIZE] Sanitization failed with exception",
        extra={
            "step_number": step.step_number,
            "step_name": step.step_name,
            "correlation_id": correlation_id,
            "operation": "sanitization_exception",
            "error_type": type(sanitize_error).__name__,
            "error_message": str(sanitize_error),
            "result_keys": list(output.result.keys()),
            "result_size": len(output.result),
        },
        exc_info=True,
    )


def _rebuild_output_if_modified(
    logger: object,
    step: CalculationStep,
    output: StepOutput,
    sanitized_result: object,
) -> StepOutput:
    if sanitized_result == output.result:
        return output

    sanitized_keys = list(sanitized_result.keys()) if isinstance(sanitized_result, dict) else []
    logger.warning(
        f"⚠️ Step {step.step_number} output contained NaN/Infinity values, sanitized",
        extra={
            "step_number": step.step_number,
            "step_name": step.step_name,
            "original_result_keys": list(output.result.keys()),
            "sanitized_result_keys": sanitized_keys,
        },
    )
    return StepOutput(
        step_number=output.step_number,
        step_name=output.step_name,
        status=output.status,
        result=sanitized_result,
        metadata=output.metadata,
        error=output.error,
        execution_time_ms=output.execution_time_ms,
    )
