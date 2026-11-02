"""Single-year FCFF component resolution for DCF cash-flow projection."""

from __future__ import annotations

from decimal import Decimal
from typing import NamedTuple, Optional

from src.utils.decimal_helpers import to_decimal

from .models import IndustryBenchmarks, YearData


class FCFBreakdown(NamedTuple):
    """Intermediate values from a single-year FCFF computation."""

    ebit: Decimal
    d_and_a: Decimal
    taxes: Decimal
    capex: Decimal
    nwc_change: Decimal
    fcf: Decimal


def zero_fcf_breakdown() -> FCFBreakdown:
    return FCFBreakdown(
        ebit=Decimal("0"),
        d_and_a=Decimal("0"),
        taxes=Decimal("0"),
        capex=Decimal("0"),
        nwc_change=Decimal("0"),
        fcf=Decimal("0"),
    )


def reported_d_and_a(year_data: YearData) -> Decimal:
    depreciation = to_decimal(year_data.depreciation or 0)
    amortization = to_decimal(year_data.amortization or 0)
    return depreciation + amortization


def benchmark_d_and_a(
    year_data: YearData,
    industry_benchmarks: IndustryBenchmarks,
) -> Decimal | None:
    avg_da_to_revenue = getattr(industry_benchmarks, "avg_da_to_revenue", None)
    if avg_da_to_revenue is not None and year_data.revenue is not None and year_data.revenue > 0:
        return to_decimal(year_data.revenue) * to_decimal(avg_da_to_revenue)
    return None


def resolve_d_and_a_and_ebit(
    year_data: YearData,
    industry_benchmarks: IndustryBenchmarks,
) -> tuple[Decimal, Decimal]:
    d_and_a = reported_d_and_a(year_data)
    if year_data.ebit is not None:
        return d_and_a, to_decimal(year_data.ebit)

    ebitda = to_decimal(year_data.ebitda)
    if d_and_a > 0:
        return d_and_a, ebitda - d_and_a

    benchmark_value = benchmark_d_and_a(year_data, industry_benchmarks)
    if benchmark_value is not None:
        return benchmark_value, ebitda - benchmark_value

    fallback_d_and_a = ebitda * Decimal("0.15")
    return fallback_d_and_a, ebitda - fallback_d_and_a


def resolve_unlevered_tax(year_data: YearData, ebit: Decimal) -> Optional[Decimal]:
    if year_data.tax_expense is None or year_data.ebit is None or year_data.ebit <= 0:
        return None

    imported_tax = to_decimal(year_data.tax_expense)
    interest = to_decimal(year_data.interest_expense or 0)
    if interest > 0:
        ebt = ebit - interest
        if ebt > 0:
            return ebit * (imported_tax / ebt)
    return imported_tax


def resolve_capex(
    year_data: YearData,
    industry_benchmarks: IndustryBenchmarks,
) -> Decimal:
    if year_data.capex is not None:
        return to_decimal(year_data.capex)
    return to_decimal(year_data.revenue) * to_decimal(industry_benchmarks.avg_capex_to_revenue)


def resolve_nwc_change(
    year_data: YearData,
    industry_benchmarks: IndustryBenchmarks,
    previous_revenue: Optional[Decimal],
) -> Decimal:
    if year_data.nwc_change is not None:
        return to_decimal(year_data.nwc_change)
    if previous_revenue is None:
        return Decimal("0")
    nwc_ratio = to_decimal(getattr(industry_benchmarks, "avg_nwc_to_revenue", Decimal("0")))
    return nwc_ratio * (to_decimal(year_data.revenue) - previous_revenue)


def resolve_taxes(
    *,
    ebit: Decimal,
    tax_rate: Decimal,
    unlevered_tax: Optional[Decimal],
) -> Decimal:
    if unlevered_tax is not None:
        return unlevered_tax
    return max(Decimal("0"), ebit) * tax_rate


def fcf_breakdown_from_components(
    *,
    ebit: Decimal,
    d_and_a: Decimal,
    taxes: Decimal,
    capex: Decimal,
    nwc_change: Decimal,
) -> FCFBreakdown:
    nopat = ebit - taxes
    fcf = nopat + d_and_a - capex - nwc_change
    return FCFBreakdown(
        ebit=ebit,
        d_and_a=d_and_a,
        taxes=taxes,
        capex=capex,
        nwc_change=nwc_change,
        fcf=fcf,
    )
