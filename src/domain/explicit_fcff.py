"""Decimal PV for an explicitly supplied annual unlevered cash-flow scenario.

This path does not infer earnings, taxes or reinvestment from missing history.
Year indices are annual intervals from the measurement date, with end-period
discounting. It is a supplied scenario, not an independently verified forecast.
"""

from decimal import Decimal

from src.api.schemas.partial_valuation import ExplicitFcffForecast
from src.domain.financial_arithmetic import money


def explicit_fcff_payload(forecast: ExplicitFcffForecast) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    present_value = Decimal(0)
    final_fcff = Decimal(0)
    for year in sorted(forecast.years, key=lambda row: row.year_index):
        final_fcff = (
            year.ebit
            - year.cash_taxes
            + year.depreciation_amortization
            - year.capex
            - year.change_in_nwc
        )
        pv = final_fcff / (1 + forecast.discount_rate) ** year.year_index
        present_value += pv
        rows.append(
            {
                "year_index": year.year_index,
                "ebit": year.ebit,
                "cash_taxes": year.cash_taxes,
                "depreciation_amortization": year.depreciation_amortization,
                "capex": year.capex,
                "change_in_nwc": year.change_in_nwc,
                "fcff": final_fcff,
                "present_value": pv,
            }
        )
    terminal = Decimal(0)
    terminal_pv = Decimal(0)
    if forecast.terminal_growth is not None:
        if final_fcff <= 0:
            raise ValueError("Gordon growth requires a positive sustainable final FCFF")
        terminal = (
            final_fcff
            * (1 + forecast.terminal_growth)
            / (forecast.discount_rate - forecast.terminal_growth)
        )
        terminal_pv = terminal / (1 + forecast.discount_rate) ** len(rows)
    return {
        "enterprise_value": present_value + terminal_pv,
        "wacc": forecast.discount_rate,
        "terminal_value": money(terminal),
        "terminal_growth_rate": forecast.terminal_growth,
        "terminal_value_methodology": (
            "gordon_growth" if forecast.terminal_growth is not None else "no_terminal_value"
        ),
        "explicit_fcff_ledger": rows,
        "terminal_present_value": terminal_pv,
        "discount_timing": "end_of_annual_interval_from_valuation_date",
        "forecast_source": forecast.source_reference,
        "forecast_evidence_status": forecast.evidence_status,
        "financing_tax_shield": "not_included_in_fcff_or_terminal_value",
    }
