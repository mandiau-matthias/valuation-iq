"""Step 2 result validation and recovery helpers."""

from __future__ import annotations

from collections.abc import Mapping

from src.api.routes.valuation.steps.base_step import StepOutput

STEP_2_EXPECTED_KEYS = (
    "ev_revenue_multiple",
    "ev_ebitda_multiple",
    "primary_method",
    "data_source",
)


def validate_step_2_result(
    logger: object,
    output: StepOutput,
    context: Mapping[str, object] | None,
) -> StepOutput:
    correlation_id = context.get("correlation_id") if context else None

    if not isinstance(getattr(output, "result", None), dict):
        _log_missing_result(logger, output, correlation_id)
        return output

    if _needs_recovery(output.result):
        recovered, recovery_source = _recover_from_metadata(output)
        if recovered:
            _log_recovery(logger, output, correlation_id, recovery_source)
        else:
            _log_unrecovered_result(logger, output, correlation_id)

    _log_validation_state(logger, output, correlation_id)
    return output


def _needs_recovery(result: dict[str, object]) -> bool:
    return not result or not all(key in result for key in STEP_2_EXPECTED_KEYS)


def _recover_from_metadata(output: StepOutput) -> tuple[bool, str | None]:
    metadata = output.metadata if isinstance(getattr(output, "metadata", None), dict) else {}

    result_backup = metadata.get("result_backup")
    if isinstance(result_backup, dict) and result_backup:
        output.result = result_backup
        return True, "metadata.result_backup"

    multiples_backup = metadata.get("multiples_backup")
    if isinstance(multiples_backup, dict):
        output.result = multiples_backup.copy()
        return True, "metadata.multiples_backup"

    return False, None


def _log_missing_result(
    logger: object,
    output: StepOutput,
    correlation_id: object,
) -> None:
    logger.error(
        "❌ CRITICAL: Step 2 output missing result attribute or result is not a dict",
        extra={
            "step_number": 2,
            "correlation_id": correlation_id,
            "has_result": hasattr(output, "result"),
            "result_type": type(output.result).__name__ if hasattr(output, "result") else None,
        },
    )


def _log_recovery(
    logger: object,
    output: StepOutput,
    correlation_id: object,
    recovery_source: str | None,
) -> None:
    logger.warning(
        "✅ Recovered Step 2 result from metadata",
        extra={
            "step_number": 2,
            "correlation_id": correlation_id,
            "recovery_source": recovery_source,
            "recovered_size": len(output.result),
        },
    )


def _log_unrecovered_result(
    logger: object,
    output: StepOutput,
    correlation_id: object,
) -> None:
    logger.warning(
        "⚠️ CRITICAL: Step 2 output.result is empty before return",
        extra={
            "step_number": 2,
            "correlation_id": correlation_id,
            "has_metadata": hasattr(output, "metadata"),
            "metadata_keys": (
                list(output.metadata.keys())
                if isinstance(getattr(output, "metadata", None), dict)
                else []
            ),
        },
    )


def _log_validation_state(
    logger: object,
    output: StepOutput,
    correlation_id: object,
) -> None:
    result = output.result if isinstance(getattr(output, "result", None), dict) else {}
    logger.debug(
        "🔍 [DIAG-VALIDATE] After Step 2 validation",
        extra={
            "step_number": 2,
            "correlation_id": correlation_id,
            "result_keys": list(result.keys()),
            "result_size": len(result),
            "has_ev_ebitda_multiple": "ev_ebitda_multiple" in result,
            "has_ev_revenue_multiple": "ev_revenue_multiple" in result,
        },
    )
