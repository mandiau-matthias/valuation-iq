"""DCF method-detail schema and builder."""

from typing import Optional, TypedDict


class DcfDetails(TypedDict, total=False):
    enterprise_value: float
    terminal_value: object
    terminal_growth_rate: object
    terminal_value_methodology: str
    terminal_exit_multiple: object
    cost_of_equity: object
    sensitivity_matrix_2d: object
    dcf_enterprise_value_before_apv: object
    dcf_equity_value_before_apv: object
    apv_contract_version: object
    apv_tax_shield_projections: object
    apv_tax_shield_pv: object
    apv_methodology: str
    apv_discount_rate: object
    apv_discounting_convention: str
    apv_tax_shield_value: object
    apv_tax_shield_pct_of_total: object
    apv_enterprise_value: object
    apv_equity_value: object
    apv_tax_shield_projections_5y: object
    apv_tax_shield_pv_5y: object
    apv_bridge_provenance: object
    apv_benchmark_reconciliation: object


def build_dcf_details(
    *,
    enterprise_value: float,
    terminal_value: object | None = None,
    terminal_growth_rate: object | None = None,
    terminal_value_methodology: Optional[str] = None,
    terminal_exit_multiple: object | None = None,
    cost_of_equity: object | None = None,
    sensitivity_matrix_2d: object | None = None,
    dcf_enterprise_value_before_apv: object | None = None,
    dcf_equity_value_before_apv: object | None = None,
    apv_contract_version: object | None = None,
    apv_tax_shield_projections: object | None = None,
    apv_tax_shield_pv: object | None = None,
    apv_methodology: Optional[str] = None,
    apv_discount_rate: object | None = None,
    apv_discounting_convention: Optional[str] = None,
    apv_tax_shield_value: object | None = None,
    apv_tax_shield_pct_of_total: object | None = None,
    apv_enterprise_value: object | None = None,
    apv_equity_value: object | None = None,
    apv_tax_shield_projections_5y: object | None = None,
    apv_tax_shield_pv_5y: object | None = None,
    apv_bridge_provenance: object | None = None,
    apv_benchmark_reconciliation: object | None = None,
) -> DcfDetails:
    d: DcfDetails = {"enterprise_value": enterprise_value}
    optional_fields = {
        "terminal_value": terminal_value,
        "terminal_growth_rate": terminal_growth_rate,
        "terminal_value_methodology": terminal_value_methodology,
        "terminal_exit_multiple": terminal_exit_multiple,
        "cost_of_equity": cost_of_equity,
        "sensitivity_matrix_2d": sensitivity_matrix_2d,
        "dcf_enterprise_value_before_apv": dcf_enterprise_value_before_apv,
        "dcf_equity_value_before_apv": dcf_equity_value_before_apv,
        "apv_contract_version": apv_contract_version,
        "apv_tax_shield_projections": apv_tax_shield_projections,
        "apv_tax_shield_pv": apv_tax_shield_pv,
        "apv_methodology": apv_methodology,
        "apv_discount_rate": apv_discount_rate,
        "apv_discounting_convention": apv_discounting_convention,
        "apv_tax_shield_value": apv_tax_shield_value,
        "apv_tax_shield_pct_of_total": apv_tax_shield_pct_of_total,
        "apv_enterprise_value": apv_enterprise_value,
        "apv_equity_value": apv_equity_value,
        "apv_tax_shield_projections_5y": apv_tax_shield_projections_5y,
        "apv_tax_shield_pv_5y": apv_tax_shield_pv_5y,
        "apv_bridge_provenance": apv_bridge_provenance,
        "apv_benchmark_reconciliation": apv_benchmark_reconciliation,
    }
    for key, value in optional_fields.items():
        if value is not None:
            d[key] = value
    return d
