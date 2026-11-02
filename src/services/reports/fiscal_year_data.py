"""Fiscal-year selection helpers for report builders."""

from collections.abc import Callable
from typing import cast

from src.services.reports.protocol_adapter import _attr
from src.utils.fiscal_year import resolve_display_current_year

DisplayCurrentYearResolver = Callable[[object | None], int]


def _default_display_current_year(request: object | None) -> int:
    return cast(int, resolve_display_current_year(request=request))


def _year_sort_key(year_data: object) -> int:
    year = _attr(year_data, "year", 0)
    return year if isinstance(year, int) else 0


def latest_closed_fiscal_year_data(
    request: object | None,
    display_current_year_resolver: DisplayCurrentYearResolver | None = None,
) -> object | None:
    """Return the most recent closed fiscal year candidate from a valuation request.

    Venus sends the base year as ``current_year_data`` and older periods as
    ``historical_years_data``. The current year is eligible only when it is at or
    before the display/filing-safe year selected for the report.
    """
    if not request:
        return None

    candidate_years: list[object] = []
    historical_years = list(_attr(request, "historical_years_data", []) or [])
    candidate_years.extend(historical_years)

    resolver = display_current_year_resolver or _default_display_current_year
    latest_allowed_year = resolver(request)
    current_year_data = _attr(request, "current_year_data", None)
    if current_year_data is not None:
        current_year = _attr(current_year_data, "year", None)
        if isinstance(current_year, int) and current_year <= latest_allowed_year:
            already_in = any(
                _attr(year_data, "year", None) == current_year for year_data in candidate_years
            )
            if not already_in:
                candidate_years.append(current_year_data)

    if not candidate_years:
        return None

    candidate_years.sort(key=_year_sort_key, reverse=True)
    return candidate_years[0]
