"""Discounted Cash Flow (DCF) valuation method."""

from collections.abc import Mapping
from decimal import Decimal
from typing import Optional, Sequence, SupportsFloat, SupportsIndex

from src.api.schemas.method_details import build_dcf_details
from src.api.schemas.stateless_api import MethodResult
from src.domain.financial_arithmetic import FinancialNumber, decimal_number, money

from ._shared import dcf_equity_from_ev, debt_overhang_details

Floatable = str | bytes | SupportsFloat | SupportsIndex


def _payload_decimal(value: object) -> Decimal:
    return decimal_number(value)


def _payload_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _sensitivity_enterprise_range(
    dcf_results: Mapping[str, object],
) -> tuple[Decimal, Decimal] | None:
    raw_low, raw_high = dcf_results.get("enterprise_value_low"), dcf_results.get(
        "enterprise_value_high"
    )
    if raw_low is not None or raw_high is not None:
        if raw_low is None or raw_high is None:
            raise ValueError("DCF bounds must be supplied together")
        low, high = decimal_number(raw_low), decimal_number(raw_high)
        if low > high:
            raise ValueError("DCF lower bound exceeds upper bound")
        return low, high
    matrix_payload = dcf_results.get("sensitivity_matrix_2d")
    if not isinstance(matrix_payload, Mapping):
        return None
    matrix = matrix_payload.get("ev_matrix")
    if not isinstance(matrix, Sequence) or isinstance(matrix, (str, bytes)):
        return None
    values: list[Decimal] = []
    for row in matrix:
        if not isinstance(row, Sequence) or isinstance(row, (str, bytes)):
            raise ValueError("Malformed DCF sensitivity row")
        for cell in row:
            if cell is not None:  # unavailable cells remain unavailable; zero is observed
                values.append(decimal_number(cell, "DCF sensitivity cell"))
    return (min(values), max(values)) if values else None


def calculate_dcf_result(
    *,
    dcf_results: Optional[Mapping[str, object]],
    dcf_exclusion_reason: Optional[str],
    total_debt: FinancialNumber,
    cash: FinancialNumber,
    ownership_multiplier: FinancialNumber,
    nwc_adjustment: FinancialNumber,
) -> MethodResult:
    """DCF equity — uses ``dcf_equity_from_ev`` (no total_adjustment)."""
    if dcf_results and not dcf_exclusion_reason:
        try:
            dcf_ev = _payload_decimal(dcf_results.get("enterprise_value"))
            wacc_safe = _payload_decimal(dcf_results.get("wacc"))
        except ValueError:
            return MethodResult(
                value=None,
                method_key="dcf",
                label="Discounted Cash Flow (DCF)",
                available=False,
                unavailable_reason="DCF waarde of disconteringsvoet ontbreekt of is ongeldig.",
            )
        if wacc_safe <= 0:
            return MethodResult(
                value=None,
                method_key="dcf",
                label="Discounted Cash Flow (DCF)",
                available=False,
                unavailable_reason="DCF vereist een positieve disconteringsvoet.",
            )
        dcf_equity = dcf_equity_from_ev(
            dcf_ev,
            total_debt=total_debt,
            cash=cash,
            ownership_multiplier=ownership_multiplier,
            nwc_adjustment=nwc_adjustment,
        )
        ev_range = _sensitivity_enterprise_range(dcf_results)
        if ev_range is not None:
            ev_low, ev_high = ev_range
            if not ev_low <= dcf_ev <= ev_high:
                raise ValueError("DCF base must lie within its supplied sensitivity range")
            equity_low = dcf_equity_from_ev(
                ev_low,
                total_debt=total_debt,
                cash=cash,
                ownership_multiplier=ownership_multiplier,
                nwc_adjustment=nwc_adjustment,
            )
            equity_high = dcf_equity_from_ev(
                ev_high,
                total_debt=total_debt,
                cash=cash,
                ownership_multiplier=ownership_multiplier,
                nwc_adjustment=nwc_adjustment,
            )
        else:
            ev_low = ev_high = dcf_ev
            equity_low = equity_high = dcf_equity
        details = build_dcf_details(
            enterprise_value=round(dcf_ev, 2),
            terminal_value=dcf_results.get("terminal_value"),
            terminal_growth_rate=dcf_results.get("terminal_growth_rate"),
            terminal_value_methodology=_payload_str(dcf_results.get("terminal_value_methodology")),
            terminal_exit_multiple=dcf_results.get("terminal_exit_multiple"),
            cost_of_equity=dcf_results.get("cost_of_equity"),
            sensitivity_matrix_2d=dcf_results.get("sensitivity_matrix_2d"),
            dcf_enterprise_value_before_apv=dcf_results.get("dcf_enterprise_value_before_apv"),
            dcf_equity_value_before_apv=dcf_results.get("dcf_equity_value_before_apv"),
            apv_contract_version=dcf_results.get("apv_contract_version"),
            apv_tax_shield_projections=dcf_results.get("apv_tax_shield_projections"),
            apv_tax_shield_pv=dcf_results.get("apv_tax_shield_pv"),
            apv_methodology=_payload_str(dcf_results.get("apv_methodology")),
            apv_discount_rate=dcf_results.get("apv_discount_rate"),
            apv_discounting_convention=_payload_str(dcf_results.get("apv_discounting_convention")),
            apv_tax_shield_value=dcf_results.get("apv_tax_shield_value"),
            apv_tax_shield_pct_of_total=dcf_results.get("apv_tax_shield_pct_of_total"),
            apv_enterprise_value=dcf_results.get("apv_enterprise_value"),
            apv_equity_value=dcf_results.get("apv_equity_value"),
            apv_tax_shield_projections_5y=dcf_results.get("apv_tax_shield_projections_5y"),
            apv_tax_shield_pv_5y=dcf_results.get("apv_tax_shield_pv_5y"),
            apv_bridge_provenance=dcf_results.get("apv_bridge_provenance"),
            apv_benchmark_reconciliation=dcf_results.get("apv_benchmark_reconciliation"),
        )
        details["range_basis"] = {
            "schema_version": "valuation_range_basis.v1",
            "kind": (
                "supplied_sensitivity_bounds"
                if dcf_results.get("enterprise_value_low") is not None
                else "sensitivity_grid_extrema" if ev_range is not None else "point_only"
            ),
            "statistical_coverage": None,
            "empirical_percentiles": False,
        }
        if dcf_equity <= 0:
            details.update(
                debt_overhang_details(
                    enterprise_value=dcf_ev,
                    equity_value=dcf_equity,
                    total_debt=total_debt,
                    cash=cash,
                    ownership_multiplier=ownership_multiplier,
                    nwc_adjustment=nwc_adjustment,
                )
            )
        return MethodResult(
            value=Decimal(str(round(dcf_equity, 2))),
            value_low=Decimal(str(round(min(equity_low, equity_high), 2))),
            value_high=Decimal(str(round(max(equity_low, equity_high), 2))),
            equity_value=Decimal(str(round(dcf_equity, 2))),
            equity_value_low=Decimal(str(round(min(equity_low, equity_high), 2))),
            equity_value_high=Decimal(str(round(max(equity_low, equity_high), 2))),
            enterprise_value=Decimal(str(round(dcf_ev, 2))),
            enterprise_value_low=Decimal(str(round(min(ev_low, ev_high), 2))),
            enterprise_value_high=Decimal(str(round(max(ev_low, ev_high), 2))),
            method_key="dcf",
            label="Discounted Cash Flow (DCF)",
            wacc=Decimal(str(round(wacc_safe, 4))),
            available=dcf_equity > 0 and dcf_ev > 0,
            unavailable_reason=(
                None
                if dcf_equity > 0 and dcf_ev > 0
                else "No positive standalone shareholder value; raw values retain the debt overhang."
            ),
            details=details,
        )

    return MethodResult(
        value=None,
        method_key="dcf",
        label="Discounted Cash Flow (DCF)",
        available=False,
        unavailable_reason=dcf_exclusion_reason or "ontbrekende prognosedata",
    )
