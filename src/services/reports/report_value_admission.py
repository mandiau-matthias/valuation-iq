"""Admission for monetary evidence in legacy report projections.

Unlike display coercion, this boundary must never turn unknown evidence into
zero or repair a reversed range. Existing snapshots are not changed.
"""

import re
from decimal import Decimal

from src.domain.financial_arithmetic import decimal_number

_DECIMAL = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z")
EVBand = tuple[Decimal, Decimal, Decimal]


def report_decimal(value: object, field: str) -> Decimal:
    if isinstance(value, str) and (len(value) > 128 or not _DECIMAL.fullmatch(value)):
        raise ValueError(f"{field} must be a finite decimal number")
    result = decimal_number(value, field)
    if len(result.as_tuple().digits) > 50 or abs(result.adjusted()) > 40:
        raise ValueError(f"{field} exceeds the supported monetary precision")
    return result


def admitted_band(low: object, mid: object, high: object) -> EVBand:
    band = (
        report_decimal(low, "lower bound"),
        report_decimal(mid, "point value"),
        report_decimal(high, "upper bound"),
    )
    if not band[0] <= band[1] <= band[2]:
        raise ValueError("Report valuation bounds must be ordered: low <= point <= high")
    return band


def admitted_point_or_band(low: object, mid: object, high: object) -> EVBand:
    """Keep a point as a degenerate tuple for the legacy numeric adapter.

    A single missing bound is incomplete evidence, not permission to substitute
    the point. Consumers suppress the range only when both bounds equal it.
    """
    if low is None and high is None:
        point = report_decimal(mid, "point value")
        return point, point, point
    return admitted_band(low, mid, high)


def admitted_optional_equity_band(
    low: object, mid: object, high: object
) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    """An absent equity conclusion stays absent; partial bands remain invalid."""
    if low is None and mid is None and high is None:
        return None, None, None
    return admitted_band(low, mid, high)
