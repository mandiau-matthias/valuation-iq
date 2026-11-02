"""
Domain-level chronology helpers for valuation historical-year inputs.
"""

from collections.abc import Sequence
from typing import TypeVar

HistoricalYearT = TypeVar("HistoricalYearT")


def _historical_year_value(historical_year: object) -> object:
    if isinstance(historical_year, dict):
        return historical_year.get("year")
    return getattr(historical_year, "year", None)


def _dated_historical_years(
    historical_years_data: Sequence[HistoricalYearT],
) -> list[tuple[int, int, HistoricalYearT]]:
    dated_years: list[tuple[int, int, HistoricalYearT]] = []
    for index, historical_year in enumerate(historical_years_data):
        year_value = _historical_year_value(historical_year)
        try:
            dated_years.append((int(year_value), index, historical_year))
        except (TypeError, ValueError):
            continue
    return dated_years


def oldest_historical_year(
    historical_years_data: Sequence[HistoricalYearT] | None,
) -> HistoricalYearT | None:
    """
    Return the earliest historical year by its parseable ``year`` attribute.
    """
    if not historical_years_data:
        return None

    dated_years = _dated_historical_years(historical_years_data)
    if dated_years:
        return min(dated_years, key=lambda item: (item[0], item[1]))[2]

    return historical_years_data[0]


def newest_historical_year(
    historical_years_data: Sequence[HistoricalYearT] | None,
) -> HistoricalYearT | None:
    """
    Return the latest historical year by its parseable ``year`` attribute.
    """
    if not historical_years_data:
        return None

    dated_years = _dated_historical_years(historical_years_data)
    if dated_years:
        return max(dated_years, key=lambda item: (item[0], item[1]))[2]

    return historical_years_data[-1]


def oldest_and_newest_historical_years(
    historical_years_data: Sequence[HistoricalYearT] | None,
) -> tuple[HistoricalYearT | None, HistoricalYearT | None]:
    """
    Return chronological bounds by parseable ``year`` while preserving fallback order.
    """
    return (
        oldest_historical_year(historical_years_data),
        newest_historical_year(historical_years_data),
    )


def historical_years_in_chronological_order(
    historical_years_data: Sequence[HistoricalYearT] | None,
) -> list[HistoricalYearT]:
    """
    Return historical rows sorted oldest-to-newest when parseable years exist.
    """
    if not historical_years_data:
        return []

    dated_years = _dated_historical_years(historical_years_data)
    if dated_years:
        return [item[2] for item in sorted(dated_years, key=lambda item: (item[0], item[1]))]

    return list(historical_years_data)
