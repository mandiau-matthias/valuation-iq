"""Exact, explicitly illustrative metric/multiple scenarios for method pages.

Axes remain Decimal through cell calculation. Supplied bounds are preserved;
invalid or incomplete evidence never becomes an assumed band. Label rounding
is presentation only. A content identity binds the source and assumptions.
"""

import hashlib
import json
from decimal import Decimal, localcontext
from typing import TypedDict

from src.domain.financial_arithmetic import money
from src.services.reports.report_value_admission import report_decimal

_PRIMARY_FACTORS = tuple(Decimal(v) for v in (".85", ".90", ".95", "1", "1.05", "1.10", "1.15"))
_SECONDARY_FACTORS = tuple(Decimal(v) for v in (".8", ".9", "1", "1.1", "1.2"))


class MultipleSensitivityMatrix(TypedDict):
    schema_version: str
    kind: str
    value_basis: str
    statistical_coverage: None
    primary_axis_values: list[Decimal]
    secondary_axis_values: list[Decimal]
    matrix: dict[str, dict[str, Decimal]]
    metric_base: Decimal
    multiple_base: Decimal
    multiple_axis_source: str
    metric_factors: list[str]
    held_assumptions: str
    source_run_id: str | None
    source_run_hash: str | None
    method_key: str | None
    currency: str | None
    valuation_date: str | None
    saved_enterprise_value: Decimal | None
    metric_label_decimals: int
    multiple_label_decimals: int
    calculation_id: str


def compute_multiple_sensitivity_matrix_2d(
    *,
    metric_base: object,
    multiple_base: object,
    multiple_low: object = None,
    multiple_high: object = None,
    preserve_anchor: bool = True,
    metric_decimals: int = 0,
    multiple_decimals: int = 2,
    source_run_id: str | None = None,
    source_run_hash: str | None = None,
    method_key: str | None = None,
    currency: str | None = None,
    valuation_date: str | None = None,
    saved_enterprise_value: object = None,
) -> MultipleSensitivityMatrix | None:
    """Build a 7×5 scenario; monetary rounding applies only to final cells.

    With no supplied bounds, ±20% multiple assumptions are explicit. A saved
    method point, when supplied, must reconcile at the declared cents boundary.
    Caller-provided identity/currency/date are retained, never invented.
    """
    try:
        metric = report_decimal(metric_base, "pricing metric")
        multiple = report_decimal(multiple_base, "applied multiple")
        saved_ev = (
            report_decimal(saved_enterprise_value, "saved enterprise value")
            if saved_enterprise_value is not None
            else None
        )
        if metric <= 0 or multiple <= 0:
            return None
        supplied = multiple_low is not None or multiple_high is not None
        lower = report_decimal(multiple_low, "lower multiple") if supplied else None
        upper = report_decimal(multiple_high, "upper multiple") if supplied else None
        if supplied and not (
            lower is not None and upper is not None and 0 <= lower <= multiple <= upper
        ):
            return None
    except ValueError:
        return None
    with localcontext() as arithmetic:
        arithmetic.prec = 100
        if saved_ev is not None and money(metric * multiple) != money(saved_ev):
            return None
        primary = [metric * factor for factor in _PRIMARY_FACTORS]
        if lower is not None and upper is not None:
            secondary = [lower, (lower + multiple) / 2, multiple, (multiple + upper) / 2, upper]
        else:
            secondary = [multiple * factor for factor in _SECONDARY_FACTORS]
        primary, secondary = list(dict.fromkeys(primary)), list(dict.fromkeys(secondary))
        matrix = {str(p): {str(s): money(p * s) for s in secondary} for p in primary}
    result: MultipleSensitivityMatrix = {
        "schema_version": "report_method_multiple_sensitivity.v2",
        "kind": "illustrative_sensitivity",
        "value_basis": "enterprise_value",
        "statistical_coverage": None,
        "primary_axis_values": primary,
        "secondary_axis_values": secondary,
        "matrix": matrix,
        "metric_base": metric,
        "multiple_base": multiple,
        "multiple_axis_source": (
            "supplied_multiple_bounds" if supplied else "assumed_plus_minus_20_percent"
        ),
        "metric_factors": [str(v) for v in _PRIMARY_FACTORS],
        "held_assumptions": "All other method assumptions; no EV-to-equity bridge or ownership adjustment",
        "source_run_id": source_run_id,
        "source_run_hash": source_run_hash,
        "method_key": method_key,
        "currency": currency,
        "valuation_date": valuation_date,
        "saved_enterprise_value": saved_ev,
        "metric_label_decimals": metric_decimals,
        "multiple_label_decimals": multiple_decimals,
        "calculation_id": "",
    }
    encoded = json.dumps(
        {k: v for k, v in result.items() if k != "calculation_id"},
        default=str,
        sort_keys=True,
        separators=(",", ":"),
    )
    result["calculation_id"] = hashlib.sha256(encoded.encode()).hexdigest()
    return result
