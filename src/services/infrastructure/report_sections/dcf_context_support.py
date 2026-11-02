"""
Shared helpers for DCF report-section context assembly.

Keep these helpers free of report-template orchestration so the DCF section
builder can stay focused on assembling context keys.
"""

import logging
import math
from collections.abc import Mapping, Sequence
from typing import TypeAlias, cast

logger = logging.getLogger(__name__)

JsonMap: TypeAlias = dict[str, object]


def attr(obj: object, name: str, default: object = None) -> object:
    val = getattr(obj, name, default)
    return default if val is None else val


def unwrap(val: object) -> object:
    if val is None:
        return None
    wrapped_data = getattr(val, "_data", None)
    if isinstance(wrapped_data, dict):
        return wrapped_data
    return val


def is_non_string_sequence(value: object) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def sequence_or_empty(value: object) -> Sequence[object]:
    if is_non_string_sequence(value):
        return cast(Sequence[object], value)
    return ()


def wacc_buildup_display(wb: object) -> object:
    """Round displayed beta so the printed CAPM equation foots at 2 decimals."""
    if not isinstance(wb, dict):
        return wb
    display_beta = _display_beta(wb)
    beta = wb.get("beta")
    raw_beta = _float_or_none(beta)
    if display_beta is not None and raw_beta is not None and display_beta != raw_beta:
        wb = dict(wb)
        wb["beta"] = display_beta
    return wb


def _float_or_none(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _display_beta(wb: dict[object, object]) -> float | None:
    try:
        beta = wb.get("beta")
        if beta is None:
            return None
        coe = wb.get("cost_of_equity")
        erp = float(wb.get("equity_risk_premium") or 0)
        if coe is not None and erp > 0:
            rf = float(wb.get("risk_free_rate") or 0)
            size = float(wb.get("size_premium") or 0)
            spec = float(wb.get("company_specific_risk") or 0)
            return round((float(coe) - rf - size - spec) / erp, 2)
        return round(float(beta), 2)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def detect_flat_projections(projection_detail: object) -> bool:
    """True when forecast years look suspiciously flat enough to warn reviewers."""
    if not projection_detail or not is_non_string_sequence(projection_detail):
        return False
    projections = cast(Sequence[object], projection_detail)
    if len(projections) < 3:
        return False
    growth_rates, margins = _projection_growth_and_margins(projections)
    return _flat_projection_warning_needed(growth_rates=growth_rates, margins=margins)


def _projection_growth_and_margins(
    projections: Sequence[object],
) -> tuple[list[float], list[float]]:
    growth_rates: list[float] = []
    margins: list[float] = []
    for row in projections:
        growth, margin = _projection_growth_and_margin(row)
        if growth is not None:
            growth_rates.append(growth)
        if margin is not None:
            margins.append(margin)
    return growth_rates, margins


def _projection_growth_and_margin(row: object) -> tuple[float | None, float | None]:
    gr = getattr(row, "growth_rate", None)
    rev = getattr(row, "revenue", None)
    ebitda = getattr(row, "ebitda", None)
    try:
        growth = float(gr) if gr is not None else None
        margin = float(ebitda) / float(rev) if rev is not None and float(rev) > 0 else None
    except (TypeError, ValueError):
        return None, None
    return growth, margin


def _flat_projection_warning_needed(
    *,
    growth_rates: Sequence[float],
    margins: Sequence[float],
) -> bool:
    if len(growth_rates) < 3 or len(margins) < 3:
        return False
    is_flat = (max(growth_rates) - min(growth_rates)) < 0.01 and (
        max(margins) - min(margins)
    ) < 0.01
    if not is_flat:
        return False
    avg_growth = sum(growth_rates) / len(growth_rates)
    return avg_growth >= 0.05


def transform_2d_sensitivity_matrix(raw: object) -> JsonMap | None:
    """Transform the coordinator's 2D sensitivity output into template format."""
    if not raw or not isinstance(raw, Mapping):
        return None
    raw_map = cast(Mapping[str, object], raw)

    wacc_values = sequence_or_empty(raw_map.get("wacc_values", ()))
    secondary_values = sequence_or_empty(
        raw_map.get("secondary_values") or raw_map.get("growth_values", ())
    )
    ev_matrix = sequence_or_empty(raw_map.get("ev_matrix", ()))

    if not wacc_values or not secondary_values or not ev_matrix:
        return None

    def number_or_none(value: object) -> float | None:
        if isinstance(value, bool):
            return None
        try:
            number = _float_or_none(value)
            return number if number is not None and math.isfinite(number) else None
        except OverflowError:
            return None

    # Reject a corrupt axis as a whole: filtering it would shift its cells under
    # different assumptions. Missing cells retain their original coordinates.
    primary = [number_or_none(value) for value in wacc_values]
    secondary = [number_or_none(value) for value in secondary_values]
    if any(value is None for value in primary + secondary):
        return None

    try:
        nested: dict[str, dict[str, float | None]] = {}
        for i, wacc in enumerate(primary):
            # Axis values are exposed to Jinja as floats.  Key the grid by the
            # exact same canonical float string so a high-precision Decimal
            # input does not become an unreachable key (and render every cell
            # as zero).
            wacc_str = str(wacc)
            row = sequence_or_empty(ev_matrix[i]) if i < len(ev_matrix) else ()
            nested[wacc_str] = {
                str(sv): (number_or_none(row[j]) if j < len(row) else None)
                for j, sv in enumerate(secondary)
            }

        return {
            "primary_axis_values": primary,
            "secondary_axis_values": secondary,
            "secondary_axis_key": raw_map.get("secondary_axis_key", "terminal_growth"),
            "matrix": nested,
            "value_basis": raw_map.get("value_basis", "operating_enterprise_value"),
            "apv_discount_rate_source": raw_map.get("apv_discount_rate_source"),
            "has_unavailable_cells": any(
                cell is None for row in nested.values() for cell in row.values()
            ),
        }
    except (TypeError, ValueError, IndexError) as exc:
        logger.warning(
            "DCF sensitivity matrix transform failed; falling back to 1D view. "
            "shape: wacc_values_len=%s, secondary_values_len=%s, ev_matrix_len=%s, error=%s",
            len(wacc_values) if hasattr(wacc_values, "__len__") else "n/a",
            len(secondary_values) if hasattr(secondary_values, "__len__") else "n/a",
            len(ev_matrix) if hasattr(ev_matrix, "__len__") else "n/a",
            exc,
        )
        return None
