"""Balance-sheet presence and Step 7 extraction helpers for main reports."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal, InvalidOperation

from src.services.reports.protocol_adapter import DictWrapper, _attr
from src.utils.decimal_helpers import safe_decimal_or_zero as safe_decimal

BalanceMetadataResolver = Callable[[object | None, str, bool], bool]
StepResult = dict[str, object] | DictWrapper

BALANCE_SHEET_DEBT_ATTRS = ("total_debt", "debt", "total_debt_amount")
BALANCE_SHEET_CASH_ATTRS = ("cash", "cash_and_equivalents", "cash_amount")
BALANCE_SHEET_ATTRS = BALANCE_SHEET_DEBT_ATTRS + BALANCE_SHEET_CASH_ATTRS


def _has_get(obj: object | None) -> bool:
    getter = getattr(obj, "get", None)
    return callable(getter)


def _get(obj: object | None, key: object, default: object = None) -> object:
    getter = getattr(obj, "get", None)
    if not callable(getter):
        return default
    return getter(key, default)


def is_meaningful_balance_value(value: object) -> bool:
    """A balance-sheet value qualifies only when present and non-zero."""
    if value is None:
        return False
    try:
        return abs(safe_decimal(value)) > Decimal("0")
    except (InvalidOperation, TypeError, ValueError):
        return False


def request_has_balance_inputs(request: object | None) -> bool:
    """Detect genuinely-provided debt/cash values on the request payload."""
    current_year_data = _attr(request, "current_year_data")
    if not current_year_data:
        return False

    for attr in BALANCE_SHEET_ATTRS:
        if not hasattr(current_year_data, attr):
            continue
        if is_meaningful_balance_value(_attr(current_year_data, attr)):
            return True
    return False


def get_detailed_step_result_result(
    response: object,
    step_number: int,
) -> StepResult | None:
    """Return a step result dict from detailed_results or legacy step caches."""
    dr = getattr(response, "detailed_results", None)
    if not _has_get(dr):
        return None

    step_results = _resolve_step_results(dr)
    if not _has_get(step_results):
        return None

    return _extract_step_result(_lookup_step_output(step_results, step_number))


def _resolve_step_results(detailed_results: object) -> object | None:
    step_results = _get(detailed_results, "step_results")
    if _has_get(step_results):
        return step_results

    multiples_valuation = _get(detailed_results, "multiples_valuation")
    if not _has_get(multiples_valuation):
        return None
    return _get(multiples_valuation, "_step_results")


def _lookup_step_output(step_results: object, step_number: int) -> object | None:
    for key in (step_number, float(step_number), str(step_number)):
        step_output = _get(step_results, key)
        if step_output is not None:
            return step_output
    return None


def _extract_step_result(step_output: object | None) -> StepResult | None:
    if not step_output:
        return None

    result = getattr(step_output, "result", None)
    if result is None and _has_get(step_output):
        result = _get(step_output, "result")
    if not result or not (isinstance(result, dict) or isinstance(result, DictWrapper)):
        return None

    return result


def step_results_have_balance_inputs(response: object) -> bool:
    """Detect explicit Step 7 balance inputs persisted into detailed results."""
    result = get_detailed_step_result_result(response, 7)
    if not result:
        return False

    inputs = result.get("inputs")
    if _has_get(inputs):
        for attr in BALANCE_SHEET_ATTRS:
            if is_meaningful_balance_value(_get(inputs, attr)):
                return True

    for attr in BALANCE_SHEET_ATTRS:
        if is_meaningful_balance_value(result.get(attr)):
            return True

    return False


def step7_extraction_diagnostics(response: object) -> dict[str, object]:
    """Build diagnostic info for Step 7 extraction failures."""
    dr = getattr(response, "detailed_results", None)
    info: dict[str, object] = {"has_detailed_results": dr is not None}
    if not dr:
        return info

    info["detailed_results_type"] = type(dr).__name__
    info["detailed_results_is_dict"] = _has_get(dr)

    if not _has_get(dr):
        return info

    step_results = _get(dr, "step_results")
    info["has_step_results"] = step_results is not None
    if step_results and hasattr(step_results, "keys") and callable(step_results.keys):
        keys = list(step_results.keys())
        info["step_results_keys"] = [str(k) for k in keys]
        info["step_7_in_keys"] = any(k == 7 or k == 7.0 or str(k) == "7" for k in keys)

    multiples_valuation = _get(dr, "multiples_valuation")
    info["has_multiples_valuation"] = multiples_valuation is not None
    if _has_get(multiples_valuation):
        inner_step_results = _get(multiples_valuation, "_step_results")
        info["has_inner_step_results"] = inner_step_results is not None
        if (
            inner_step_results
            and hasattr(inner_step_results, "keys")
            and callable(inner_step_results.keys)
        ):
            info["inner_step_results_keys"] = [str(k) for k in inner_step_results.keys()]

    return info


def has_balance_data(
    response: object,
    request: object | None,
    metadata_bool_resolver: BalanceMetadataResolver,
) -> bool:
    """Strictly check whether the seller actually provided balance-sheet inputs."""
    if metadata_bool_resolver(request, "balance_sheet_provided", False):
        return True

    dr = getattr(response, "detailed_results", None)
    if _has_get(dr):
        if _get(dr, "balance_sheet"):
            return True
        if _get(dr, "debt_cash"):
            return True

    if step_results_have_balance_inputs(response):
        return True
    if request_has_balance_inputs(request):
        return True
    return False
