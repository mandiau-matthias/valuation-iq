"""EBITDA multiple: one Decimal earnings basis, band and equity bridge."""

from decimal import Decimal
from typing import Optional

from src.api.schemas.stateless_api import MethodResult
from src.domain.financial_arithmetic import FinancialNumber, decimal_number, money, multiple_bounds
from src.domain.saas_valuation_adjuster import SaasAdjustmentResult

from ._shared import debt_overhang_details, equity_from_ev


def calculate_ebitda_result(
    *,
    ebitda: FinancialNumber,
    ev_ebitda_multiple: FinancialNumber,
    p25_multiple: FinancialNumber | None,
    p75_multiple: FinancialNumber | None,
    total_adjustment: FinancialNumber,
    total_debt: FinancialNumber,
    cash: FinancialNumber,
    ownership_multiplier: FinancialNumber,
    nwc_adjustment: FinancialNumber,
    saas_adjustment: Optional[SaasAdjustmentResult],
) -> MethodResult:
    """Price one earnings basis with a validated band and exact equity bridge."""
    try:
        earnings = decimal_number(ebitda, "EBITDA")
        reference_multiple = decimal_number(ev_ebitda_multiple, "EBITDA multiple")
    except ValueError:
        return MethodResult(
            value=None,
            method_key="ebitda_multiple",
            label="EBITDA-multiple",
            available=False,
            unavailable_reason="EBITDA of multiple bevat ongeldige waarde.",
        )
    if earnings <= 0 or reference_multiple <= 0:
        return MethodResult(
            value=None,
            method_key="ebitda_multiple",
            label="EBITDA-multiple",
            available=False,
            unavailable_reason=(
                "EBITDA is nul of negatief — multiples-methode vereist positieve EBITDA."
                if earnings <= 0
                else "Geen EV/EBITDA-multiple beschikbaar voor dit bedrijfstype."
            ),
        )
    low, high, range_basis = multiple_bounds(reference_multiple, p25_multiple, p75_multiple)
    saas_factor = (
        decimal_number(saas_adjustment.ebitda_adjustment_factor) if saas_adjustment else Decimal(1)
    )
    multiple = reference_multiple * saas_factor
    low *= saas_factor
    high *= saas_factor
    factor = Decimal(1) - decimal_number(total_adjustment, "risk adjustment")
    if not 0 < factor <= 1 or saas_factor <= 0:
        return MethodResult(
            value=None,
            method_key="ebitda_multiple",
            label="EBITDA-multiple",
            available=False,
            unavailable_reason="De methodologische aanpassing elimineert de ondernemingswaarde.",
        )
    reference_ev = earnings * multiple
    ev = reference_ev * factor
    ev_low, ev_high = earnings * low * factor, earnings * high * factor

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
        "pricing_metric": earnings,
        "pricing_multiple": multiple * factor,
        "enterprise_value": money(ev),
        "enterprise_value_low": money(ev_low),
        "enterprise_value_high": money(ev_high),
        "p25_multiple": low,
        "p75_multiple": high,
        "equity_range_low": money(equity_low),
        "equity_range_high": money(equity_high),
        "reference_enterprise_value": money(reference_ev),
        "reference_multiple": multiple,
        "method_adjustment_factor": factor,
        "range_basis": range_basis,
    }
    if saas_adjustment:
        details.update(
            saas_metrics=saas_adjustment.computed_metrics, saas_adjustment_factor=saas_factor
        )
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
        method_key="ebitda_multiple",
        label="EBITDA-multiple",
        multiple_used=(multiple * factor).quantize(Decimal(".0001")),
        available=equity > 0,
        unavailable_reason=(
            "Na aftrek van schulden resteert er geen positieve aandeelhouderswaarde."
            if equity <= 0
            else None
        ),
        details=details,
    )
