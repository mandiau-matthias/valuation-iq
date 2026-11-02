"""Comparable fiscal-revenue growth, with explicit horizon and missingness.

Rates are decimal ratios, never percentages. Undated inputs follow the annual
YearData contract; supplied dates must describe comparable full fiscal years.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from typing import Literal, cast


def _field(row: object, name: str) -> object:
    if isinstance(row, Mapping):
        return row.get(name)
    return cast(object, getattr(row, name, None))


def _amount(row: object) -> Decimal | None:
    observations = _field(row, "financial_observations")
    if isinstance(observations, Mapping) and observations.get("revenue") in {
        "missing",
        "unknown",
        "placeholder",
    }:
        return None
    raw = _field(row, "revenue")
    if isinstance(raw, bool) or not isinstance(raw, (Decimal, str, int, float)):
        return None
    try:
        value = Decimal(str(raw))
    except InvalidOperation:
        return None
    return value if value.is_finite() and value >= 0 else None


def _year(row: object) -> int | None:
    value = _field(row, "year")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _period_issue(previous: object, current: object, years: int) -> str | None:
    ends: list[date] = []
    for row in (previous, current):
        start_raw, end_raw = _field(row, "period_start"), _field(row, "period_end")
        if start_raw is None and end_raw is None:
            continue
        start, end = _date(start_raw), _date(end_raw)
        if start is None or end is None or end.year != _year(row):
            return "incomplete_or_invalid_period_dates"
        # Accommodate calendar, leap and 52/53-week fiscal years, not stubs.
        if not 364 <= (end - start).days + 1 <= 371:
            return "non_annual_accounting_period"
        ends.append(end)
    if len(ends) == 1:
        return "incomplete_comparative_period_dates"
    if len(ends) == 2 and abs((ends[1] - ends[0]).days - years * 365.2425) > 8:
        return "changed_fiscal_year_end"
    for field in ("source_currency", "currency_basis"):
        left, right = _field(previous, field), _field(current, field)
        if left and right and str(left).strip().lower() != str(right).strip().lower():
            return "currency_lineage_changed"
    return None


@dataclass(frozen=True)
class RevenueGrowth:
    rate: Decimal | None
    start_year: int | None
    end_year: int | None
    elapsed_years: int | None
    reason: str | None = None
    period_basis: str = "annual_fiscal_input_contract"

    def to_payload(self) -> dict[str, object]:
        return {
            "rate": self.rate,
            "unit": "decimal_ratio",
            "available": self.rate is not None,
            "start_year": self.start_year,
            "end_year": self.end_year,
            "elapsed_years": self.elapsed_years,
            "basis": (
                "unavailable"
                if self.rate is None
                else "year_over_year" if self.elapsed_years == 1 else "compound_annual_growth"
            ),
            "period_basis": self.period_basis,
            "unavailable_reason": self.reason,
        }


def revenue_growth(
    current: object,
    history: Sequence[object],
    *,
    horizon: Literal["latest", "three_year"] = "latest",
) -> RevenueGrowth:
    """Annualize comparable endpoints using elapsed fiscal years, not row count."""
    end_year = _year(current)
    by_year: dict[int, object] = {}
    for row in history:
        year = _year(row)
        if year is None or end_year is None or year >= end_year:
            continue
        if _field(row, "is_forecast") is True:
            continue
        if year in by_year and any(
            _field(by_year[year], field) != _field(row, field)
            for field in (
                "revenue",
                "financial_observations",
                "period_start",
                "period_end",
                "source_currency",
                "currency_basis",
            )
        ):
            return RevenueGrowth(None, year, end_year, end_year - year, "conflicting_fiscal_year")
        by_year[year] = row
    if end_year is None or not by_year:
        return RevenueGrowth(None, None, end_year, None, "no_prior_actual_revenue")
    start_year = end_year - 3 if horizon == "three_year" else max(by_year)
    previous = by_year.get(start_year)
    years = end_year - start_year
    if previous is None:
        return RevenueGrowth(None, start_year, end_year, years, "three_year_endpoint_missing")
    if _field(current, "is_forecast") is True:
        return RevenueGrowth(None, start_year, end_year, years, "current_period_is_forecast")
    issue = _period_issue(previous, current, years)
    if issue:
        return RevenueGrowth(None, start_year, end_year, years, issue)
    start, end = _amount(previous), _amount(current)
    if start is None or end is None:
        return RevenueGrowth(None, start_year, end_year, years, "revenue_observation_unavailable")
    if start <= 0:
        return RevenueGrowth(None, start_year, end_year, years, "non_positive_base_revenue")
    with localcontext() as context:
        context.prec = 28 if years == 1 else 50 + max(0, end.adjusted() - start.adjusted())
        if years == 1:
            rate = (end - start) / start
        else:
            rate = (
                Decimal("-1")
                if end == 0
                else (end / start) ** (Decimal("1") / Decimal(years)) - Decimal("1")
            )
            # Stable thresholds: an exact 20% root must not price >20%.
            rate = rate.quantize(Decimal("0.000000000000000001"))
    basis = (
        "comparable_full_fiscal_periods"
        if _field(current, "period_end") is not None
        else "annual_fiscal_input_contract"
    )
    return RevenueGrowth(rate, start_year, end_year, years, period_basis=basis)
