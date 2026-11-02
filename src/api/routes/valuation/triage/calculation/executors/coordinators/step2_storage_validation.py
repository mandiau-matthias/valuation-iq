"""Post-storage validation helpers for Step 2 foundation output."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from src.api.routes.valuation.steps.base_step import StepOutput

STEP_2_EXPECTED_KEYS = (
    "ev_revenue_multiple",
    "ev_ebitda_multiple",
    "primary_method",
    "data_source",
)
STEP_1_PAYLOAD_KEYS = (
    "revenue",
    "ebitda",
    "ebitda_margin",
    "company_info",
    "using_weighted_metrics",
    "weighting_method",
)
STEP_1_STORAGE_OVERWRITE_KEYS = ("revenue", "ebitda")


@dataclass(frozen=True)
class Step2StorageSnapshot:
    result: Mapping[str, object] | None
    result_keys: list[str]
    missing_keys: list[str]
    status_value: object
    result_type: str | None

    @property
    def result_is_dict(self) -> bool:
        return self.result is not None

    @property
    def result_size(self) -> int:
        return len(self.result_keys)

    @property
    def result_is_empty(self) -> bool:
        return self.result_size == 0

    @property
    def has_all_required_fields(self) -> bool:
        return not self.missing_keys

    @property
    def has_storage_overwrite_keys(self) -> bool:
        return any(key in self.result_keys for key in STEP_1_STORAGE_OVERWRITE_KEYS)


def validate_step_2_storage(
    logger: object,
    output: StepOutput,
    context: Mapping[str, object] | None,
) -> None:
    correlation_id = context.get("correlation_id") if context else None
    snapshot = _snapshot(output)

    _log_storage_verification(logger, snapshot, correlation_id)
    if _log_shape_issue(logger, output, snapshot, correlation_id):
        return
    _log_required_fields(logger, output, snapshot, correlation_id)


def _snapshot(output: StepOutput) -> Step2StorageSnapshot:
    result = output.result if isinstance(getattr(output, "result", None), dict) else None
    result_keys = list(result.keys()) if result is not None else []
    missing_keys = [key for key in STEP_2_EXPECTED_KEYS if key not in result_keys]
    status = getattr(output, "status", None)
    return Step2StorageSnapshot(
        result=result,
        result_keys=result_keys,
        missing_keys=missing_keys,
        status_value=status.value if hasattr(status, "value") else None,
        result_type=type(output.result).__name__ if hasattr(output, "result") else None,
    )


def _log_storage_verification(
    logger: object,
    snapshot: Step2StorageSnapshot,
    correlation_id: object,
) -> None:
    if snapshot.has_all_required_fields and not snapshot.has_storage_overwrite_keys:
        logger.debug(
            "✅ Step 2 storage verification passed",
            extra={
                "step_number": 2,
                "correlation_id": correlation_id,
                "all_keys_present": True,
            },
        )
        return

    if _debug_enabled():
        logger.debug(
            "🔍 [DIAG-STORAGE] Step 2 storage verification (issues detected)",
            extra={
                "step_number": 2,
                "correlation_id": correlation_id,
                "missing_keys": snapshot.missing_keys,
                "has_wrong_keys": snapshot.has_storage_overwrite_keys,
            },
        )


def _log_shape_issue(
    logger: object,
    output: StepOutput,
    snapshot: Step2StorageSnapshot,
    correlation_id: object,
) -> bool:
    if snapshot.result_is_dict and not snapshot.result_is_empty:
        return False

    logger.error(
        "❌ [DIAG-STORAGE] Step 2 result is empty or missing after storage",
        extra={
            "step_number": 2,
            "correlation_id": correlation_id,
            "operation": "storage_empty_result",
            "has_result": hasattr(output, "result"),
            "result_type": snapshot.result_type,
            "result_size": snapshot.result_size,
            "step_2_status": snapshot.status_value,
            "result_keys": snapshot.result_keys,
            "step_output_id": id(output),
        },
    )
    return True


def _log_required_fields(
    logger: object,
    output: StepOutput,
    snapshot: Step2StorageSnapshot,
    correlation_id: object,
) -> None:
    if snapshot.missing_keys:
        logger.warning(
            f"⚠️ [DIAG-STORAGE] Step 2 result missing expected keys: {snapshot.missing_keys}",
            extra={
                "step_number": 2,
                "correlation_id": correlation_id,
                "operation": "storage_missing_keys",
                "missing_keys": snapshot.missing_keys,
                "actual_keys": snapshot.result_keys,
            },
        )
        logger.error(
            "❌ CRITICAL: Step 2 result missing required fields",
            extra={
                "has_revenue_multiple": "ev_revenue_multiple" in output.result,
                "has_ebitda_multiple": "ev_ebitda_multiple" in output.result,
                "has_data_source": "data_source" in output.result,
                "has_primary_method": "primary_method" in output.result,
                "result_keys": snapshot.result_keys,
                "result_size": snapshot.result_size,
                "correlation_id": correlation_id,
                "step_2_status": snapshot.status_value,
            },
        )
        return

    if snapshot.has_storage_overwrite_keys:
        logger.warning(
            "⚠️ [DIAG-STORAGE] Step 2 result contains Step 1 keys (revenue, ebitda) - possible overwrite",
            extra={
                "step_number": 2,
                "correlation_id": correlation_id,
                "operation": "storage_wrong_keys",
                "actual_keys": snapshot.result_keys,
            },
        )
        return

    logger.debug(
        "✅ Step 2 result validation passed - all required fields present",
        extra={
            "ev_revenue_multiple": output.result.get("ev_revenue_multiple"),
            "ev_ebitda_multiple": output.result.get("ev_ebitda_multiple"),
            "data_source": output.result.get("data_source"),
            "primary_method": output.result.get("primary_method"),
            "multiples_source": output.result.get("multiples_source"),
            "correlation_id": correlation_id,
        },
    )


def _debug_enabled() -> bool:
    from src.config import get_settings

    return bool(get_settings().debug)
