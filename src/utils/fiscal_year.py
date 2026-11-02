"""
Fiscal year utilities for determining the default filing-safe year and
the newest explicit year we can safely accept in reports/validation.
"""

from datetime import date
from typing import Any, List, Optional


def get_current_filing_year(now: date | None = None) -> int:
    """Return the latest fiscal year whose books are realistically closed.

    Jan–Mar: prior year books still being closed → return current_year − 2
    Apr–Dec: prior year books published → return current_year − 1
    """
    now = now or date.today()
    return now.year - 2 if now.month < 4 else now.year - 1


def get_max_confirmable_year(now: date | None = None) -> int:
    """Return the newest explicit year we ever accept from upstream clients."""
    now = now or date.today()
    return now.year - 1


def get_filing_year_historical_offset(year: int | str, base_filing_year: int) -> int | None:
    """How many years before the filing base (0 = base year). Mirrors TS `getFilingYearHistoricalOffset`."""
    try:
        y = int(year)
    except (TypeError, ValueError):
        return None
    offset = base_filing_year - y
    return offset if offset >= 0 else None


def resolve_display_current_year(
    request: Any = None,
    response: Any = None,
) -> int:
    """Resolve report-facing year labels while preserving explicit upstream year choices."""
    filing_year = get_current_filing_year()
    max_confirmable_year = get_max_confirmable_year()
    candidates: List[Any] = []
    if request is not None and getattr(request, "current_year_data", None) is not None:
        candidates.append(getattr(request.current_year_data, "year", None))
    if response is not None and getattr(response, "current_year_data", None) is not None:
        candidates.append(getattr(response.current_year_data, "year", None))
    for candidate in candidates:
        try:
            year = int(candidate)
        except (TypeError, ValueError):
            continue
        return min(year, max_confirmable_year)
    return filing_year


def primary_filing_year_for_report_data(
    *,
    request: Any = None,
    response: Any = None,
    multi_year: Optional[List[Any]] = None,
) -> int:
    """Year for React ValuationReportTemplate EBITDA headings; mirrors Mercury `getPrimaryFilingYearForReport`.

    Priority: effective session year from request/response; else max multi-year row year;
    else filing-safe default.
    """
    filing_year = get_current_filing_year()
    max_confirmable_year = get_max_confirmable_year()
    candidates: List[Any] = []
    if request is not None and getattr(request, "current_year_data", None) is not None:
        candidates.append(getattr(request.current_year_data, "year", None))
    if response is not None and getattr(response, "current_year_data", None) is not None:
        candidates.append(getattr(response.current_year_data, "year", None))
    for candidate in candidates:
        try:
            year = int(candidate)
        except (TypeError, ValueError):
            continue
        return min(year, max_confirmable_year)
    if multi_year:
        years: List[int] = []
        for row in multi_year:
            y = getattr(row, "year", None)
            if y is None:
                continue
            try:
                yi = int(y)
            except (TypeError, ValueError):
                continue
            if yi >= 1900:
                years.append(yi)
        if years:
            return min(max(years), max_confirmable_year)
    return filing_year
