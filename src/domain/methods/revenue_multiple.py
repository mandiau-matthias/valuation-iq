"""Revenue multiple with exact amounts and explicit range assumptions."""

from decimal import Decimal
from typing import Protocol

from src.api.schemas.stateless_api import MethodResult
from src.domain.financial_arithmetic import FinancialNumber, decimal_number, money, multiple_bounds

from ._shared import debt_overhang_details, equity_from_ev


class RevenueCalibration(Protocol):
    ev_revenue_median: object


def calculate_revenue_result(
    *,
    revenue: FinancialNumber,
    total_adjustment: FinancialNumber,
    total_debt: FinancialNumber,
    cash: FinancialNumber,
    calibration: RevenueCalibration | None,
    ownership_multiplier: FinancialNumber,
    nwc_adjustment: FinancialNumber = 0.0,
    require_revenue_basis: bool = False,
    revenue_basis: str | None = None,
    cohort_revenue_basis: str | None = None,
) -> MethodResult:
    """Revenue (Omzet) multiple valuation."""
    if require_revenue_basis and (
        revenue_basis not in {"turnover", "total_operating_income"}
        or cohort_revenue_basis != revenue_basis
    ):
        return MethodResult(
            value=None, method_key="revenue_multiple", label="Omzetmultiple", available=False,
            unavailable_reason="REVENUE_BASIS_MISMATCH: provide the cohort revenue definition and matching source financial facts.",
        )
    if calibration is None:
        return MethodResult(
            value=None,
            method_key="revenue_multiple",
            label="Omzetmultiple",
            available=False,
            unavailable_reason="Geen kalibratie beschikbaar voor omzetmultiple.",
        )
    try:
        turnover = decimal_number(revenue, "revenue")
        multiple = decimal_number(calibration.ev_revenue_median, "revenue multiple")
    except ValueError:
        return MethodResult(
            value=None,
            method_key="revenue_multiple",
            label="Omzetmultiple",
            available=False,
            unavailable_reason="Omzet of multiple bevat ongeldige waarde.",
        )
    if turnover <= 0 or multiple <= 0:
        return MethodResult(
            value=None,
            method_key="revenue_multiple",
            label="Omzetmultiple",
            available=False,
            unavailable_reason=(
                "Omzetmultiple kan niet worden toegepast bij €0 omzet."
                if turnover <= 0
                else "Geen EV/Omzet-multiple beschikbaar voor dit bedrijfstype."
            ),
        )
    low, high, range_basis = multiple_bounds(
        multiple,
        getattr(calibration, "ev_revenue_p25", None),
        getattr(calibration, "ev_revenue_p75", None),
    )
    factor = Decimal(1) - decimal_number(total_adjustment, "risk adjustment")
    if not 0 < factor <= 1:
        return MethodResult(
            value=None,
            method_key="revenue_multiple",
            label="Omzetmultiple",
            available=False,
            unavailable_reason="De methodologische aanpassing elimineert de ondernemingswaarde.",
        )
    reference_ev = turnover * multiple
    ev, ev_low, ev_high = reference_ev * factor, turnover * low * factor, turnover * high * factor

    def bridge(value: Decimal) -> Decimal:
        return equity_from_ev(
            value,
            total_adjustment=0,
            total_debt=total_debt,
            cash=cash,
            ownership_multiplier=ownership_multiplier,
            nwc_adjustment=nwc_adjustment,
        )

    equity, equity_low, equity_high = bridge(ev), bridge(ev_low), bridge(ev_high)
    details: dict[str, object] = {
        "pricing_metric": turnover,
        "pricing_multiple": multiple * factor,
        "enterprise_value": money(ev),
        "enterprise_value_low": money(ev_low),
        "enterprise_value_high": money(ev_high),
        "revenue": money(turnover),
        "equity_range_low": money(equity_low),
        "equity_range_high": money(equity_high),
        "reference_enterprise_value": money(reference_ev),
        "reference_multiple": multiple,
        "method_adjustment_factor": factor,
        "range_basis": range_basis,
    }
    if equity <= 0:
        details.update(
            debt_overhang_details(
                enterprise_value=ev,
                equity_value=equity,
                total_debt=total_debt,
                cash=cash,
                ownership_multiplier=ownership_multiplier,
                nwc_adjustment=nwc_adjustment,
                total_adjustment=0,
            )
        )
    return MethodResult(
        value=money(equity),
        value_low=money(equity_low),
        value_high=money(equity_high),
        equity_value=money(equity),
        equity_value_low=money(equity_low),
        equity_value_high=money(equity_high),
        enterprise_value=money(ev),
        enterprise_value_low=money(ev_low),
        enterprise_value_high=money(ev_high),
        method_key="revenue_multiple",
        label="Omzetmultiple",
        multiple_used=(multiple * factor).quantize(Decimal(".0001")),
        available=equity > 0,
        unavailable_reason=(
            "Na aftrek van schulden resteert er geen positieve aandeelhouderswaarde."
            if equity <= 0
            else None
        ),
        details=details,
    )
