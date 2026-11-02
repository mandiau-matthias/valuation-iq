"""Finite numeric projection of immutable benchmark values for report templates."""

from collections.abc import Mapping
from math import isfinite

from src.domain.financial_arithmetic import decimal_number


def metric_band(payload: Mapping[str, object]) -> dict[str, object] | None:
    def first(*keys: str) -> object:
        return next((payload[key] for key in keys if payload.get(key) is not None), None)

    median = first("median", "p50", "p50_multiple")
    if median is None:
        return None
    p25 = first("p25", "low", "p25_multiple")
    p75 = first("p75", "high", "p75_multiple")
    try:
        mid = decimal_number(median)
        low = decimal_number(p25) if p25 is not None else None
        high = decimal_number(p75) if p75 is not None else None
    except ValueError:
        return None
    if mid <= 0 or (low is not None and not 0 <= low <= mid) or (high is not None and high < mid):
        return None
    # The existing report arithmetic uses floats. Convert only this display
    # projection; the original strings in the sealed contract remain untouched.
    band = {
        key: float(value)
        for key, value in (("median", mid), ("p25", low), ("p75", high))
        if value is not None
    }
    return dict(band) if all(isfinite(value) for value in band.values()) else None
