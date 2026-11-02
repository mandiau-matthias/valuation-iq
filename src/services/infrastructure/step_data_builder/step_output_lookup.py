"""
Lookup helpers for transparency calculation-step output.

The public import stays at ``src.services.infrastructure.step_data_builder``;
this module keeps the package initializer from becoming the lookup engine.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Optional, Union

from src.services.infrastructure.exceptions import StepDataError
from src.services.interfaces.request_response_protocol import ValuationResponseProtocol
from src.utils.decimal_helpers import to_decimal
from src.utils.exceptions import ExternalServiceError
from src.utils.logging import get_logger

logger = get_logger(__name__)

StepNumber = Union[int, float, Decimal]

_STEP_MIN = Decimal("0")
_STEP_MAX = Decimal("11")
_STEP_COLLECTIONS = ("multiples", "dcf")


@dataclass(frozen=True)
class StepLookupSpec:
    raw_step_number: StepNumber
    decimal_step_number: Decimal
    is_decimal_step: bool
    integer_index: Optional[int]


def _as_step_dict(step_item: object) -> Optional[Dict[str, Any]]:
    if isinstance(step_item, dict):
        return step_item
    if hasattr(step_item, "model_dump"):
        return step_item.model_dump()
    if hasattr(step_item, "dict"):
        return step_item.dict()
    return None


def _step_lookup_spec(step_number: StepNumber) -> Optional[StepLookupSpec]:
    try:
        decimal_step_number = to_decimal(step_number)
    except ValueError:
        logger.warning(
            f"Invalid step number: {step_number}",
            extra={"step_number": step_number, "valid_range": "0-11"},
        )
        return None

    is_decimal_step = decimal_step_number != decimal_step_number.to_integral_value()
    if decimal_step_number < _STEP_MIN or decimal_step_number > _STEP_MAX:
        logger.warning(
            f"Invalid {'decimal ' if is_decimal_step else ''}step number: {step_number} (must be 0-11)",
            extra={
                "step_number": step_number,
                "valid_range": "0-11",
                "is_decimal": is_decimal_step,
            },
        )
        return None

    return StepLookupSpec(
        raw_step_number=step_number,
        decimal_step_number=decimal_step_number,
        is_decimal_step=is_decimal_step,
        integer_index=None if is_decimal_step else int(decimal_step_number),
    )


def _calculation_steps(
    response: ValuationResponseProtocol,
    spec: StepLookupSpec,
) -> Optional[Dict[str, Any]]:
    transparency = getattr(response, "transparency", None)
    if not transparency:
        return None

    steps = getattr(transparency, "calculation_steps", None)
    if not steps:
        logger.debug(
            f"transparency.calculation_steps not available for step {spec.raw_step_number}",
            extra={
                "step_number": spec.raw_step_number,
                "has_transparency": True,
                "has_calculation_steps_attr": hasattr(transparency, "calculation_steps"),
            },
        )
        return None

    step_dict = _as_step_dict(steps)
    if not isinstance(step_dict, dict):
        logger.warning(
            f"Unexpected calculation_steps type: {type(steps)}, expected dict",
            extra={
                "step_number": spec.raw_step_number,
                "steps_type": type(steps).__name__,
                "steps_value": str(steps)[:200],
            },
        )
        return None

    if spec.decimal_step_number == _STEP_MIN:
        logger.debug(
            f"Step extraction: calculation_steps keys: {list(step_dict.keys())}",
            extra={
                "step_number": spec.raw_step_number,
                "has_multiples": "multiples" in step_dict,
                "has_dcf": "dcf" in step_dict,
            },
        )
    return step_dict


def _step_field_matches(step_dict: Dict[str, Any], spec: StepLookupSpec) -> bool:
    step_num_field = step_dict.get("step_number")
    if step_num_field is None:
        return False
    try:
        return to_decimal(step_num_field) == spec.decimal_step_number
    except ValueError:
        return False


def _find_decimal_step(
    step_items: list[object],
    spec: StepLookupSpec,
    *,
    source_name: str,
) -> Optional[Dict[str, Any]]:
    logger.debug(
        f"Searching for decimal step {spec.raw_step_number} by step_number field",
        extra={
            "step_number": spec.raw_step_number,
            "list_length": len(step_items),
            "is_decimal": True,
            "source": source_name,
        },
    )
    for idx, step_item in enumerate(step_items):
        step_dict = _as_step_dict(step_item)
        if step_dict is None or not _step_field_matches(step_dict, spec):
            continue
        logger.debug(
            f"Found decimal step {spec.raw_step_number} at list index {idx}",
            extra={
                "step_number": spec.raw_step_number,
                "list_index": idx,
                "is_decimal": True,
                "source": source_name,
            },
        )
        return step_dict
    logger.debug(
        f"Decimal step {spec.raw_step_number} not found in {source_name}_steps",
        extra={
            "step_number": spec.raw_step_number,
            "list_length": len(step_items),
            "is_decimal": True,
            "source": source_name,
        },
    )
    return None


def _find_indexed_step(
    step_items: list[object],
    spec: StepLookupSpec,
    *,
    source_name: str,
) -> Optional[Dict[str, Any]]:
    assert spec.integer_index is not None
    if spec.integer_index < len(step_items):
        return _as_step_dict(step_items[spec.integer_index])

    if spec.integer_index >= 10:
        logger.warning(
            f"Step {spec.integer_index} not found in {source_name}_steps list "
            f"(length: {len(step_items)}, expected >= {spec.integer_index + 1})",
            extra={
                "step_number": spec.integer_index,
                f"{source_name}_steps_len": len(step_items),
                "expected_min_length": spec.integer_index + 1,
                "available_steps": list(range(len(step_items))),
            },
        )
    return None


def _lookup_in_step_collection(
    steps: Dict[str, Any],
    source_name: str,
    spec: StepLookupSpec,
) -> Optional[Dict[str, Any]]:
    step_items = steps.get(source_name)
    if not isinstance(step_items, list):
        if spec.integer_index is not None and spec.integer_index >= 10:
            logger.debug(
                f"Step extraction: {source_name}_steps type mismatch (not a list)",
                extra={
                    "step_number": spec.raw_step_number,
                    f"{source_name}_steps_type": (
                        type(step_items).__name__ if step_items else None
                    ),
                },
            )
        return None

    if spec.is_decimal_step:
        return _find_decimal_step(step_items, spec, source_name=source_name)
    return _find_indexed_step(step_items, spec, source_name=source_name)


def get_step_output(
    response: ValuationResponseProtocol,
    step_number: StepNumber,
) -> Optional[Dict[str, Any]]:
    """
    Extract step output from transparency data.

    Supports integer step numbers (0-11) by list index and decimal step numbers
    (for example 4.5) by matching the step item's ``step_number`` field.
    """
    if not response:
        logger.warning(
            "get_step_output called with None response",
            extra={"step_number": step_number},
        )
        return None

    try:
        spec = _step_lookup_spec(step_number)
        if spec is None:
            return None

        steps = _calculation_steps(response, spec)
        if steps is None:
            return None

        for source_name in _STEP_COLLECTIONS:
            step_output = _lookup_in_step_collection(steps, source_name, spec)
            if step_output is not None:
                return step_output

        if spec.decimal_step_number < Decimal("3"):
            logger.debug(
                f"Step {spec.raw_step_number} not found in calculation_steps",
                extra={
                    "step_number": spec.raw_step_number,
                    "available_keys": list(steps.keys()),
                },
            )
        return None
    except (KeyError, AttributeError, TypeError) as e:
        logger.warning(
            f"Data structure error extracting step {step_number}: {e}",
            extra={"step_number": step_number, "error_type": type(e).__name__},
        )
        return None
    except ExternalServiceError as e:
        logger.error(
            f"Unexpected error extracting step {step_number} from transparency data: {e}",
            extra={"step_number": step_number, "error_type": type(e).__name__},
            exc_info=True,
        )
        raise StepDataError(
            f"Failed to extract step {step_number} from transparency data: {e}"
        ) from e
