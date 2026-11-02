"""Recovery scenarios must reconcile to an authenticated company cash-flow schedule."""

from decimal import Decimal, localcontext

from src.api.schemas.stateless_api import CalculateRequest
from src.services.reports.forecast_admission import (
    ForecastEvidenceError,
    require_committed_forecast,
)


def recovery_forecasts_are_source_verified(request: CalculateRequest) -> bool:
    try:
        forecast = require_committed_forecast(request)
    except ForecastEvidenceError:
        return False
    recovery = request.recovery_inputs
    if recovery is None or forecast.discount_timing != "year_end":
        return False
    # v1 authenticates one company schedule. A different scenario schedule
    # remains diagnostic until a source contract commits that schedule too.
    with localcontext() as context:
        context.prec = 60
        for scenario in recovery.scenarios:
            if len(scenario.forecast_years) != len(forecast.periods):
                return False
            nol_carry = Decimal(0)
            for index, (row, source) in enumerate(zip(scenario.forecast_years, forecast.periods)):
                if (
                    source.start_date.isoformat() != f"{row.year}-01-01"
                    or source.end_date.isoformat() != f"{row.year}-12-31"
                    or row.year <= request.current_year.year
                ):
                    return False
                ebitda = row.revenue - row.operating_expenses_excluding_da
                ebit = ebitda - row.depreciation_and_amortization
                nol_available = row.nol_opening if index == 0 else nol_carry
                taxable = max(ebit, Decimal(0))
                nol_used = min(nol_available, taxable)
                cash_taxes = (taxable - nol_used) * row.tax_rate
                nol_carry = nol_available - nol_used + max(-ebit, Decimal(0))
                comparisons = (
                    (row.revenue, source.revenue),
                    (ebitda, source.ebitda),
                    (
                        row.depreciation_and_amortization,
                        Decimal(source.depreciation) + Decimal(source.amortization),
                    ),
                    (row.capex, source.capex),
                    (row.delta_nwc, source.change_in_operating_nwc),
                    (cash_taxes, source.cash_taxes),
                    (ebitda - cash_taxes - row.capex - row.delta_nwc, source.free_cash_flow),
                )
                if any(actual != Decimal(expected) for actual, expected in comparisons):
                    return False
    return True
