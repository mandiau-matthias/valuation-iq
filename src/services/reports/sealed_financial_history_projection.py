"""Bind displayed actuals to an immutable run; preserve historical readers."""

from collections.abc import Mapping
from decimal import Decimal
from typing import TYPE_CHECKING

from src.api.schemas.financial_history import (
    assert_supplied_year_matches,
    financial_history_from_lineage,
)

if TYPE_CHECKING:
    from src.api.schemas.stateless_report_schemas import GenerateReportRequest


def bind_sealed_report_history(request: "GenerateReportRequest") -> bool:
    run = request.valuation_result.valuation_run
    if run is None:
        return False
    history = financial_history_from_lineage(run.calculation_lineage)
    if history is None:
        return False
    if history.currency != run.currency:
        raise ValueError("report financial history currency differs from sealed run")
    if request.reporting_year is not None and request.reporting_year != history.current_year:
        raise ValueError("report reporting_year differs from sealed financial history")
    rows = {row.year: row.to_year_data() for row in history.actual_years}
    if request.current_year_data is not None:
        assert_supplied_year_matches(request.current_year_data, rows[history.current_year])
    elif request.historical_years_data:
        raise ValueError("historical_years_data requires current_year_data")
    prior_years = set(rows) - {history.current_year}
    if request.historical_years_data:
        supplied_years = [row.year for row in request.historical_years_data]
        if len(supplied_years) != len(set(supplied_years)) or set(supplied_years) != prior_years:
            raise ValueError("report financial-history years differ from sealed actual years")
        for row in request.historical_years_data:
            assert_supplied_year_matches(row, rows[row.year])
    request.reporting_year = history.current_year
    request.current_year_data = rows[history.current_year]
    request.historical_years_data = [rows[year] for year in sorted(prior_years)]
    return True


def bind_report_financial_history(
    request: "GenerateReportRequest",
) -> "GenerateReportRequest":
    """Fail closed when report-visible actuals diverge from the calculation.

    The current year is tied field-by-field to the immutable calculation
    response.  Prior-year membership is tied to the actual-only valuation
    timeline when that timeline was requested.  Source hashes and filing
    identifiers remain sealed in the valuation run/report manifest.
    """

    run = request.valuation_result.valuation_run
    if run is not None:
        if bind_sealed_report_history(request):
            return request
    current = request.current_year_data
    history = request.historical_years_data
    if current is None and not history:
        return request
    if current is None:
        raise ValueError("historical_years_data requires current_year_data")
    if current.is_forecast:
        raise ValueError("current_year_data for a report must be an actual fiscal year")
    if request.reporting_year is not None and current.year != request.reporting_year:
        raise ValueError("report current_year_data does not match reporting_year")

    seen: set[int] = set()
    for row in history:
        if row.is_forecast:
            raise ValueError("report historical_years_data must contain actual years only")
        if row.year >= current.year:
            raise ValueError("report historical years must precede current_year_data")
        if row.year in seen:
            raise ValueError("report historical_years_data contains duplicate fiscal years")
        seen.add(row.year)

    metrics = request.valuation_result.financial_metrics or {}
    from src.services.reports.report_annual_earnings import annual_earnings_for_report

    ledger = run.response_snapshot.get("earnings_basis_ledger") if run else None
    annual = annual_earnings_for_report(metrics, ledger)
    annual_bindings = {
        "reported_ebitda": annual["reported_ebitda"],
        "ebitda": annual["normalized_ebitda" if current.ebitda_normalized else "reported_ebitda"],
    }
    current_bindings = {
        "revenue": current.revenue,
        "ebitda": current.ebitda,
        "reported_ebitda": current.reported_ebitda,
        "cash": current.cash,
        "total_debt": current.total_debt,
        "total_assets": current.total_assets,
        "total_equity": current.total_equity,
    }
    metric_aliases = {"total_equity": "equity"}
    tolerance = Decimal("0.01")
    for field, supplied in current_bindings.items():
        metric_key = metric_aliases.get(field, field)
        calculated = annual_bindings.get(field, metrics.get(metric_key))
        if field in annual_bindings and supplied is not None:
            if calculated is None or Decimal(str(supplied)) != calculated:
                raise ValueError(
                    f"report current_year_data.{field} does not match calculated financial_metrics"
                )
            continue
        if supplied is None or calculated is None:
            continue
        if abs(Decimal(str(supplied)) - Decimal(str(calculated))) > tolerance:
            raise ValueError(
                f"report current_year_data.{field} does not match calculated financial_metrics"
            )

    actual_timeline_years: set[int] = set()
    for point in request.valuation_result.valuation_timeline or []:
        point_year = point.get("fiscal_year") if isinstance(point, Mapping) else point.fiscal_year
        point_is_forecast = (
            point.get("is_forecast", False) if isinstance(point, Mapping) else point.is_forecast
        )
        if not point_is_forecast:
            if point_year is None:
                raise ValueError("report valuation timeline requires a fiscal year")
            actual_timeline_years.add(int(point_year))
    if actual_timeline_years:
        supplied_years = {*seen, current.year}
        if supplied_years != actual_timeline_years:
            raise ValueError(
                "report financial-history years do not match the actual valuation timeline"
            )
    return request
