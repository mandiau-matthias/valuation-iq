"""Canonical equity extraction for Step 10 range methodology."""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional, Tuple

from src.utils.decimal_helpers import to_decimal
from src.utils.logging import get_logger

from ...base_step import StepStatus

logger = get_logger(__name__)

EQUITY_VALUE_FIELD_NAMES = ("equity_value_mid", "equity_mid", "calculated_equity_mid")


@dataclass(frozen=True)
class Step10CompletionSnapshot:
    step8_completed: bool
    step7_completed: bool
    step6_completed: bool


@dataclass(frozen=True)
class EquityStepSelection:
    output: Any | None
    source: str | None


@dataclass(frozen=True)
class EquityFieldSnapshot:
    ownership_adjusted_equity: Any | None
    step7_equity: Any | None


def extract_equity_value(
    step7_output: Any, step8_output: Optional[Any], step6_output: Optional[Any] = None
) -> Tuple[Optional[Decimal], Optional[str], Any | None, Any | None]:
    """Extract canonical equity from Step 8 or Step 7; never substitute Step 6 EV."""
    _log_equity_extraction_entry(step7_output, step8_output, step6_output)

    completion = _completion_snapshot(step7_output, step8_output, step6_output)
    _log_completion_snapshot(completion)

    selection = _select_equity_step(step7_output, step8_output, completion)
    if selection.output is None:
        _log_missing_canonical_equity(step6_output)
        return None, None, None, None

    equity_result = _step_result_mapping(selection.output)
    _log_equity_result_shape(selection.output, equity_result)

    fields = EquityFieldSnapshot(
        ownership_adjusted_equity=equity_result.get("ownership_adjusted_equity_mid"),
        step7_equity=equity_result.get("equity_value_mid", 0),
    )
    _log_initial_equity_fields(fields, equity_result)

    equity_mid, equity_source = _extract_primary_equity(fields)
    if equity_mid is None:
        equity_mid, equity_source = _extract_direct_step7_equity(step7_output, step6_output, fields)

    step7_equity_for_validation = _extract_step7_equity_for_validation(step7_output)
    _log_equity_extraction_return(
        equity_mid,
        equity_source,
        fields.ownership_adjusted_equity,
        step7_equity_for_validation,
    )
    return (
        equity_mid,
        equity_source,
        fields.ownership_adjusted_equity,
        step7_equity_for_validation,
    )


def _is_completed_step(step_output: Any | None) -> bool:
    if step_output is None:
        return False
    if isinstance(step_output, dict):
        status = step_output.get("status")
        return status == "completed" or status == StepStatus.COMPLETED
    if hasattr(step_output, "status"):
        return step_output.status == StepStatus.COMPLETED
    return False


def _step_result_mapping(step_output: Any | None) -> Mapping[str, Any]:
    if step_output is None:
        return {}
    if isinstance(step_output, dict):
        result = step_output.get("result", step_output)
    else:
        result = getattr(step_output, "result", {})
    if isinstance(result, Mapping):
        return result
    return {}


def _first_present_equity_value(result: Mapping[str, Any]) -> Any | None:
    for field_name in EQUITY_VALUE_FIELD_NAMES:
        value = result.get(field_name)
        if value is not None:
            return value
    return None


def _is_positive_value(value: Any | None) -> bool:
    if value is None:
        return False
    try:
        return to_decimal(value) > 0
    except (TypeError, ValueError):
        return False


def _log_equity_extraction_entry(
    step7_output: Any, step8_output: Optional[Any], step6_output: Optional[Any]
) -> None:
    # DEBUG: lifecycle breadcrumb for extract_equity_value(); the Step 10
    # entry/exit pair at the orchestrator level is the canonical INFO.
    logger.debug(
        "🔍 Step 10: _extract_equity_value() ENTRY POINT",
        extra={
            "step_number": 10,
            "step8_output_is_none": step8_output is None,
            "step8_output_type": type(step8_output).__name__ if step8_output else "None",
            "step7_output_is_none": step7_output is None,
            "step7_output_type": type(step7_output).__name__ if step7_output else "None",
            "step6_output_is_none": step6_output is None,
            "step6_output_type": type(step6_output).__name__ if step6_output else "None",
        },
    )


def _completion_snapshot(
    step7_output: Any, step8_output: Optional[Any], step6_output: Optional[Any]
) -> Step10CompletionSnapshot:
    return Step10CompletionSnapshot(
        step8_completed=_is_completed_step(step8_output),
        step7_completed=_is_completed_step(step7_output),
        step6_completed=_is_completed_step(step6_output) if step6_output else False,
    )


def _log_completion_snapshot(completion: Step10CompletionSnapshot) -> None:
    logger.debug(
        "🔍 Step 10: Completion status check",
        extra={
            "step_number": 10,
            "step8_completed": completion.step8_completed,
            "step7_completed": completion.step7_completed,
            "step6_completed": completion.step6_completed,
        },
    )


def _select_equity_step(
    step7_output: Any,
    step8_output: Optional[Any],
    completion: Step10CompletionSnapshot,
) -> EquityStepSelection:
    if completion.step8_completed:
        logger.debug(
            "✅ Step 10: Selected Step 8 (ownership-adjusted equity) for range calculation",
            extra={"step_number": 10, "equity_source": "Step 8 (ownership-adjusted)"},
        )
        return EquityStepSelection(step8_output, "Step 8 (ownership-adjusted)")
    if completion.step7_completed:
        logger.debug(
            "✅ Step 10: Selected Step 7 (equity) for range calculation (Step 8 not available)",
            extra={"step_number": 10, "equity_source": "Step 7 (equity)"},
        )
        return EquityStepSelection(step7_output, "Step 7 (equity)")
    return EquityStepSelection(None, None)


def _log_missing_canonical_equity(step6_output: Optional[Any]) -> None:
    logger.error(
        "❌ No canonical equity value available from Step 7/8; refusing EV approximation fallback",
        extra={
            "step_number": 10,
            "step6_available": step6_output is not None,
            "degraded_mode": False,
        },
    )


def _log_equity_result_shape(equity_step: Any, equity_result: Mapping[str, Any]) -> None:
    logger.debug(
        "🔍 Step 10: get_result() returned equity_result",
        extra={
            "step_number": 10,
            "equity_step_type": type(equity_step).__name__,
            "equity_result_type": type(equity_result).__name__,
            "equity_result_is_dict": isinstance(equity_result, dict),
            "equity_result_keys": list(equity_result.keys()),
            "equity_result_length": len(equity_result),
        },
    )


def _log_initial_equity_fields(
    fields: EquityFieldSnapshot, equity_result: Mapping[str, Any]
) -> None:
    logger.debug(
        "🔍 Step 10: Initial equity field extraction attempt",
        extra={
            "step_number": 10,
            "has_ownership_adjusted_equity": fields.ownership_adjusted_equity is not None,
            "ownership_adjusted_equity_value": (
                str(fields.ownership_adjusted_equity) if fields.ownership_adjusted_equity else None
            ),
            "ownership_adjusted_equity_gt_zero": _is_positive_value(
                fields.ownership_adjusted_equity
            ),
            "has_step7_equity": fields.step7_equity is not None and fields.step7_equity != 0,
            "step7_equity_value": str(fields.step7_equity) if fields.step7_equity else None,
            "step7_equity_gt_zero": _is_positive_value(fields.step7_equity),
            "all_equity_result_values": {k: str(v) for k, v in equity_result.items()},
        },
    )


def _extract_primary_equity(fields: EquityFieldSnapshot) -> Tuple[Optional[Decimal], Optional[str]]:
    if _is_positive_value(fields.ownership_adjusted_equity):
        equity_mid = to_decimal(fields.ownership_adjusted_equity)
        equity_source = "Step 8 (ownership-adjusted)"
        logger.debug(
            "✅ Step 10: Successfully extracted from ownership_adjusted_equity_mid",
            extra={
                "step_number": 10,
                "equity_mid": str(equity_mid),
                "equity_source": equity_source,
            },
        )
        return equity_mid, equity_source

    if _is_positive_value(fields.step7_equity):
        equity_mid = to_decimal(fields.step7_equity)
        equity_source = "Step 7 (equity)"
        logger.debug(
            "✅ Step 10: Successfully extracted from equity_value_mid",
            extra={
                "step_number": 10,
                "equity_mid": str(equity_mid),
                "equity_source": equity_source,
            },
        )
        return equity_mid, equity_source

    return None, None


def _extract_direct_step7_equity(
    step7_output: Any,
    step6_output: Optional[Any],
    fields: EquityFieldSnapshot,
) -> Tuple[Optional[Decimal], str]:
    logger.warning(
        "⚠️ Step 10: Primary extraction failed, attempting direct Step 7 extraction",
        extra={
            "step_number": 10,
            "ownership_adjusted_equity": (
                str(fields.ownership_adjusted_equity)
                if fields.ownership_adjusted_equity is not None
                else "None"
            ),
            "step7_equity": str(fields.step7_equity) if fields.step7_equity else "None or 0",
        },
    )

    if not _is_completed_step(step7_output):
        logger.error(
            "❌ Step 10: Direct Step 7 extraction NOT ATTEMPTED - Step 7 not completed",
            extra={"step_number": 10, "step7_completed": _is_completed_step(step7_output)},
        )
        return None, "NONE (Step 7 not available)"

    step7_result = _step_result_mapping(step7_output)
    logger.info(
        "🔍 Step 10: Direct Step 7 extraction - got result",
        extra={
            "step_number": 10,
            "step7_result_type": type(step7_result).__name__,
            "step7_result_is_dict": isinstance(step7_result, dict),
            "step7_result_keys": list(step7_result.keys()),
            "all_step7_result_values": {k: str(v) for k, v in step7_result.items()},
        },
    )

    step7_equity_direct = _first_present_equity_value(step7_result)
    _log_step7_alternative_equity_fields(step7_result, step7_equity_direct)

    if _is_positive_value(step7_equity_direct):
        equity_mid = to_decimal(step7_equity_direct)
        equity_source = "Step 7 (direct extraction)"
        logger.info(
            "✅ Step 10: Successfully extracted via direct Step 7 extraction",
            extra={
                "step_number": 10,
                "equity_mid": str(equity_mid),
                "equity_source": equity_source,
            },
        )
        return equity_mid, equity_source

    _log_step7_direct_extraction_failure(step7_equity_direct, step6_output)
    return None, "NONE (Step 7 extraction failed; EV fallback disabled)"


def _log_step7_alternative_equity_fields(
    step7_result: Mapping[str, Any], step7_equity_direct: Any | None
) -> None:
    logger.info(
        "🔍 Step 10: Alternative field name extraction results",
        extra={
            "step_number": 10,
            "equity_value_mid": (
                str(step7_result.get("equity_value_mid"))
                if step7_result.get("equity_value_mid") is not None
                else None
            ),
            "equity_mid": (
                str(step7_result.get("equity_mid"))
                if step7_result.get("equity_mid") is not None
                else None
            ),
            "calculated_equity_mid": (
                str(step7_result.get("calculated_equity_mid"))
                if step7_result.get("calculated_equity_mid") is not None
                else None
            ),
            "step7_equity_direct_final": (
                str(step7_equity_direct) if step7_equity_direct is not None else None
            ),
        },
    )


def _log_step7_direct_extraction_failure(
    step7_equity_direct: Any | None, step6_output: Optional[Any]
) -> None:
    logger.error(
        "❌ Step 10: Direct Step 7 extraction FAILED - all equity fields are None or 0",
        extra={
            "step_number": 10,
            "step7_equity_direct": str(step7_equity_direct) if step7_equity_direct else "None or 0",
        },
    )
    logger.error(
        "❌ Step 10: Refusing Step 6 EV fallback after Step 7 extraction failure",
        extra={
            "step_number": 10,
            "step6_output_is_none": step6_output is None,
            "step6_completed": _is_completed_step(step6_output) if step6_output else False,
            "degraded_mode": False,
        },
    )


def _extract_step7_equity_for_validation(step7_output: Any) -> Any | None:
    if not _is_completed_step(step7_output):
        return None
    return _first_present_equity_value(_step_result_mapping(step7_output))


def _log_equity_extraction_return(
    equity_mid: Optional[Decimal],
    equity_source: Optional[str],
    ownership_adjusted_equity: Any | None,
    step7_equity_for_validation: Any | None,
) -> None:
    # DEBUG: return-state diagnostic; Step 10's canonical INFO summary
    # carries the final equity_mid + spread + sources.
    logger.debug(
        "🔍 Step 10: _extract_equity_value() RETURNING",
        extra={
            "step_number": 10,
            "equity_mid": str(equity_mid) if equity_mid is not None else "None",
            "equity_mid_is_none": equity_mid is None,
            "equity_mid_gt_zero": _is_positive_value(equity_mid),
            "equity_source": equity_source,
            "ownership_adjusted_equity": (
                str(ownership_adjusted_equity) if ownership_adjusted_equity is not None else "None"
            ),
            "step7_equity_for_validation": (
                str(step7_equity_for_validation)
                if step7_equity_for_validation is not None
                else "None"
            ),
        },
    )
