"""Company metric extraction helpers for main report aggregation."""

from __future__ import annotations

from decimal import Decimal

from src.services.reports.protocol_adapter import _attr
from src.utils.decimal_helpers import safe_decimal_or_zero as safe_decimal


def _title_case_label(value: object) -> str:
    return str(value).title().replace("_", " ").replace("-", " ")


def _mapping_get(obj: object | None, key: str) -> object | None:
    getter = getattr(obj, "get", None)
    if not callable(getter):
        return None
    return getter(key)


def _safe_int(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def get_industry(response: object, request: object | None) -> str | None:
    """Get display-ready industry from request or response."""
    industry = _attr(request, "industry", None)
    if industry:
        return _title_case_label(industry)

    detailed_results = getattr(response, "detailed_results", None)
    industry = _mapping_get(detailed_results, "industry")
    if industry:
        return _title_case_label(industry)

    return None


def get_revenue(response: object, request: object | None) -> Decimal:
    """Get revenue from response or request."""
    response_current_year = _attr(response, "current_year_data", None)
    response_revenue = _attr(response_current_year, "revenue", None)
    if response_revenue:
        return safe_decimal(response_revenue)

    request_current_year = _attr(request, "current_year_data", None)
    request_revenue = _attr(request_current_year, "revenue", None)
    if request_revenue:
        return safe_decimal(request_revenue)

    return Decimal("0")


def get_employee_count(response: object, request: object | None) -> int | None:
    """Extract employee count from request or response."""
    for attr in (
        "number_of_employees",
        "employee_count",
        "employees",
        "fte_count",
        "total_employees",
    ):
        raw = _attr(request, attr, None)
        if raw is not None and raw != "":
            parsed = _safe_int(raw)
            if parsed is not None:
                return parsed

    detailed_results = getattr(response, "detailed_results", None)
    for key in (
        "number_of_employees",
        "employee_count",
        "employees",
        "fte_count",
        "total_employees",
        "num_employees",
    ):
        raw = _mapping_get(detailed_results, key)
        if raw is not None and raw != "":
            parsed = _safe_int(raw)
            if parsed is not None:
                return parsed

    return None
