"""Compare a standard Gordon-growth DCF with independently supplied local workbook totals."""

from __future__ import annotations

from src.config.local_reference_data import reference_table
from decimal import Decimal
from typing import Optional

from src.utils.adaptive_input_helpers import get_business_context
from src.utils.decimal_helpers import to_decimal

# 1 cent — the standard DCF flows through the engine's float-exponentiation
# discount path, so reconcile at M&A precision rather than the APV bridge's
# pure-Decimal 1e-6. "Matched within tolerance" stays an honest claim.
_BENCHMARK_TOLERANCE = Decimal("0.01")
_STANDARD_BENCHMARK_REFERENCE = "local_dcf_standard"

_USER_BENCHMARK_EXPECTED = {k: Decimal(str(v)) for k, v in reference_table("dcf-standard").items()}

# Bilingual row labels so the report can render the table without a
# metric -> label switch in the template.
_ROW_LABELS: dict[str, tuple[str, str]] = {
    "sum_pv_fcf": ("PV of explicit free cash flows", "CW van expliciete vrije kasstromen"),
    "terminal_value": ("Terminal value", "Restwaarde"),
    "pv_terminal_value": ("PV of terminal value", "CW van restwaarde"),
    "enterprise_value": ("Enterprise value", "Ondernemingswaarde"),
}

# Order the rows the way the workbook builds them up.
_ROW_ORDER: tuple[str, ...] = (
    "sum_pv_fcf",
    "terminal_value",
    "pv_terminal_value",
    "enterprise_value",
)


def _clean_string(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_decimal(value: object) -> Optional[Decimal]:
    if not isinstance(value, (str, int, float, Decimal)):
        return None
    try:
        result = to_decimal(value)
    except (ValueError, TypeError, ArithmeticError):
        return None
    return result if isinstance(result, Decimal) else None


def resolve_standard_benchmark_reference(request: object) -> Optional[str]:
    """Return the standard-DCF benchmark reference when the request opts in.

    Only an explicit ``business_context`` key counts — there is deliberately no
    convention-based auto-detection, so a normal customer run is never compared
    against the supplied workbook.
    """
    context = get_business_context(request)
    if not isinstance(context, dict):
        return None
    for key in (
        "dcf_benchmark_case",
        "dcf_benchmark_reference",
        "dcf_standard_benchmark_reference",
    ):
        value = _clean_string(context.get(key))
        if value and value.lower() == _STANDARD_BENCHMARK_REFERENCE:
            return _STANDARD_BENCHMARK_REFERENCE
    return None


def _benchmark_row(metric: str, actual: Optional[Decimal]) -> dict[str, object]:
    expected = _USER_BENCHMARK_EXPECTED[metric]
    label_en, label_nl = _ROW_LABELS[metric]
    if actual is None:
        return {
            "metric": metric,
            "label_en": label_en,
            "label_nl": label_nl,
            "expected": expected,
            "actual": None,
            "delta": None,
            "tolerance": _BENCHMARK_TOLERANCE,
            "passed": False,
        }
    delta = actual - expected
    return {
        "metric": metric,
        "label_en": label_en,
        "label_nl": label_nl,
        "expected": expected,
        "actual": actual,
        "delta": delta,
        "tolerance": _BENCHMARK_TOLERANCE,
        "passed": abs(delta) <= _BENCHMARK_TOLERANCE,
    }


def build_dcf_standard_benchmark_reconciliation(
    request: object,
    *,
    enterprise_value: object,
    sum_pv_fcf: object,
    terminal_value: object,
    pv_terminal_value: object,
) -> Optional[dict[str, object]]:
    """Reconcile a standard-DCF run against the supplied workbook when opted in.

    Returns ``None`` unless the request explicitly references the standard
    benchmark. Otherwise returns a structured reconciliation: per-line expected
    vs actual with delta, tolerance and pass/fail, plus an overall
    matched/drift status — the same shape as ``apv_benchmark_reconciliation``.
    """
    benchmark_reference = resolve_standard_benchmark_reference(request)
    if benchmark_reference is None:
        return None

    actuals = {
        "sum_pv_fcf": _safe_decimal(sum_pv_fcf),
        "terminal_value": _safe_decimal(terminal_value),
        "pv_terminal_value": _safe_decimal(pv_terminal_value),
        "enterprise_value": _safe_decimal(enterprise_value),
    }
    rows = [_benchmark_row(metric, actuals[metric]) for metric in _ROW_ORDER]
    matched = all(bool(row["passed"]) for row in rows)
    deltas = [d for d in (row.get("delta") for row in rows) if isinstance(d, Decimal)]
    max_abs_delta = max((abs(d) for d in deltas), default=Decimal("0"))
    return {
        "benchmark_reference": benchmark_reference,
        "benchmark_name": "User-supplied DCF reference (standard DCF)",
        "status": "matched" if matched else "drift",
        "tolerance": _BENCHMARK_TOLERANCE,
        "max_abs_delta": max_abs_delta,
        "rows": rows,
    }


def maybe_build_dcf_standard_benchmark_reconciliation(
    request: object,
    *,
    apv_bridge: object,
    enterprise_value: object,
    sum_pv_fcf: object,
    terminal_value: object,
    pv_terminal_value: object,
) -> Optional[dict[str, object]]:
    """Skip standard-DCF benchmark reconciliation when the APV bridge is armed."""
    if apv_bridge is not None:
        return None
    return build_dcf_standard_benchmark_reconciliation(
        request,
        enterprise_value=enterprise_value,
        sum_pv_fcf=sum_pv_fcf,
        terminal_value=terminal_value,
        pv_terminal_value=pv_terminal_value,
    )
