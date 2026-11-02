"""Degraded dependency execution policies for calculation steps."""

from __future__ import annotations

from src.api.routes.valuation.steps.base_step import CalculationStep, StepOutput, StepStatus

StepResults = dict[int, StepOutput]
ExecutionContext = dict[str, object]


def can_execute_with_degraded_dependencies(
    logger: object,
    step: CalculationStep,
    previous_results: StepResults,
    context: ExecutionContext,
) -> bool:
    if step.step_number == 2:
        return _can_execute_step_2(logger, step, previous_results, context)
    if step.step_number in {8, 9}:
        return _can_execute_steps_8_or_9(logger, step, previous_results, context)
    return False


def _can_execute_step_2(
    logger: object,
    step: CalculationStep,
    previous_results: StepResults,
    context: ExecutionContext,
) -> bool:
    step_1_output = previous_results.get(1)
    step_0_output = previous_results.get(0)

    if not _is_completed(step_1_output) or step_0_output is None:
        return False

    if not _is_completed(step_0_output):
        logger.warning(
            "⚠️ Step 2 executing with degraded dependencies (Step 0 failed)",
            extra={
                "step_number": 2,
                "step_0_status": _status_value(step_0_output),
                "step_1_status": _status_value(step_1_output),
                "note": "Step 2 will use fallback quality score",
                "correlation_id": context.get("correlation_id"),
            },
        )
    return True


def _can_execute_steps_8_or_9(
    logger: object,
    step: CalculationStep,
    previous_results: StepResults,
    context: ExecutionContext,
) -> bool:
    step_7_output = previous_results.get(7)
    step_6_output = previous_results.get(6)
    step_6_ev_mid = _enterprise_value_mid(step_6_output)

    if _is_completed(step_7_output) or not step_6_ev_mid:
        return False

    logger.warning(
        f"⚠️ Step {step.step_number} executing with degraded dependencies (Step 7 failed, using Step 6 EV as fallback)",
        extra={
            "step_number": step.step_number,
            "step_7_status": _status_value(step_7_output) if step_7_output else "missing",
            "step_6_available": True,
            "step_6_ev_mid": step_6_ev_mid,
            "note": f"Step {step.step_number} will use Step 6 EV as equity approximation",
            "correlation_id": context.get("correlation_id"),
        },
    )
    return True


def _is_completed(output: StepOutput | None) -> bool:
    return output is not None and getattr(output, "status", None) == StepStatus.COMPLETED


def _status_value(output: StepOutput | None) -> str | None:
    status = getattr(output, "status", None)
    return status.value if hasattr(status, "value") else None


def _enterprise_value_mid(output: StepOutput | None) -> object:
    if not _is_completed(output):
        return None
    result = getattr(output, "result", None)
    if not isinstance(result, dict):
        return None
    return result.get("enterprise_value_mid")
