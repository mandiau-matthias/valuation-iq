"""
Template context assembly for the DCF report section.
"""

from src.services.infrastructure.report_sections.dcf_context_support import (
    JsonMap,
    attr,
    detect_flat_projections,
    unwrap,
    wacc_buildup_display,
)
from src.services.infrastructure.report_sections.dcf_readiness import DcfReadinessContext
from src.services.infrastructure.report_sections.dcf_reconciliation import DcfDisplayReconciliation
from src.utils.decimal_helpers import safe_float as _to_float


def assemble_dcf_context(
    *,
    dcf: object,
    dcf_method: object,
    display: DcfDisplayReconciliation,
    readiness: DcfReadinessContext,
    audit_trail: object,
    projection_detail: object,
) -> JsonMap:
    context: JsonMap = {"has_dcf": True, "dcf_method": dcf_method}
    context.update(_valuation_context(dcf=dcf, display=display))
    context.update(_apv_context(dcf))
    context["dcf_sensitivity_range_policy"] = unwrap(attr(dcf, "sensitivity_range_policy", None))
    assumptions = unwrap(attr(dcf, "market_assumptions", None))
    context["dcf_cash_tax_provenance"] = (
        assumptions.get("tax_rate_provenance") if isinstance(assumptions, dict) else None
    )
    context.update(_horizon_context(dcf=dcf, display=display))
    context.update(_projection_context(dcf=dcf, display=display))
    context.update(
        _readiness_context(
            readiness=readiness,
            audit_trail=audit_trail,
            projection_detail=projection_detail,
        )
    )
    return context


def _valuation_context(*, dcf: object, display: DcfDisplayReconciliation) -> JsonMap:
    return {
        "dcf_enterprise_value": display.enterprise_value,
        "dcf_enterprise_value_low": _to_float(attr(dcf, "enterprise_value_low", 0)),
        "dcf_enterprise_value_mid": _to_float(attr(dcf, "enterprise_value_mid", 0)),
        "dcf_enterprise_value_high": _to_float(attr(dcf, "enterprise_value_high", 0)),
        "dcf_equity_value": display.equity_value,
        "dcf_wacc": _to_float(attr(dcf, "wacc", 0)),
        "dcf_cost_of_equity": _to_float(attr(dcf, "cost_of_equity", 0)),
        "dcf_cost_of_debt": _to_float(attr(dcf, "cost_of_debt", 0)),
        "dcf_debt_weight": _to_float(attr(dcf, "debt_weight", 0)),
        "dcf_equity_weight": _to_float(attr(dcf, "equity_weight", 0)),
        "dcf_terminal_growth_rate": _to_float(attr(dcf, "terminal_growth_rate", 0)),
        "dcf_terminal_value": display.terminal_value,
        "dcf_terminal_value_methodology": attr(dcf, "terminal_value_methodology", None),
        "dcf_terminal_exit_multiple": _to_float(attr(dcf, "terminal_exit_multiple", 0)),
        "dcf_pv_terminal_value": display.pv_terminal_value,
        "dcf_mid_year_discounting": bool(attr(dcf, "mid_year_discounting", True)),
        "dcf_discount_periods_note": attr(dcf, "discount_periods_note", None),
        "dcf_academic_cost_of_equity_formula": attr(
            dcf,
            "academic_cost_of_equity_formula",
            None,
        ),
        "dcf_wacc_buildup": wacc_buildup_display(unwrap(attr(dcf, "wacc_buildup", None))),
        "dcf_terminal_value_pct_of_total": display.terminal_value_pct_of_total,
        "dcf_explicit_forecast_pct_of_total": display.explicit_forecast_pct_of_total,
        "dcf_implied_ev_ebitda": _to_float(attr(dcf, "implied_ev_ebitda", 0)),
        "dcf_terminal_value_steady_state": unwrap(attr(dcf, "terminal_value_steady_state", None)),
    }


def _apv_context(dcf: object) -> JsonMap:
    provenance = unwrap(attr(dcf, "apv_bridge_provenance", None))
    included_in_value = bool(
        isinstance(provenance, dict) and provenance.get("included_in_dcf_value") is True
    )
    versioned = attr(dcf, "apv_contract_version", None) == "apv_tax_shield.v2"
    has_schedule = (
        bool(attr(dcf, "apv_tax_shield_projections", None))
        if versioned
        else bool(_to_float(attr(dcf, "apv_tax_shield_value", 0)))
    )
    return {
        "dcf_enterprise_value_before_apv": _to_float(
            attr(dcf, "dcf_enterprise_value_before_apv", 0)
        ),
        "dcf_equity_value_before_apv": _to_float(attr(dcf, "dcf_equity_value_before_apv", 0)),
        "dcf_apv_contract_version": attr(dcf, "apv_contract_version", None),
        "dcf_apv_discount_rate_source": (
            provenance.get("discount_rate_source") if isinstance(provenance, dict) else None
        ),
        "dcf_apv_methodology": attr(dcf, "apv_methodology", None),
        "dcf_apv_discount_rate": _to_float(attr(dcf, "apv_discount_rate", 0)),
        "dcf_apv_discounting_convention": attr(dcf, "apv_discounting_convention", None),
        "dcf_apv_tax_shield_value": _to_float(attr(dcf, "apv_tax_shield_value", 0)),
        "dcf_apv_tax_shield_pct_of_total": _to_float(attr(dcf, "apv_tax_shield_pct_of_total", 0)),
        "dcf_apv_enterprise_value": _to_float(attr(dcf, "apv_enterprise_value", 0)),
        "dcf_apv_equity_value": _to_float(attr(dcf, "apv_equity_value", 0)),
        "dcf_apv_bridge_provenance": provenance,
        "dcf_apv_benchmark_reconciliation": unwrap(attr(dcf, "apv_benchmark_reconciliation", None)),
        "dcf_standard_benchmark_reconciliation": unwrap(
            attr(dcf, "dcf_benchmark_reconciliation", None)
        ),
        "dcf_apv_tax_shield_projections": (
            attr(dcf, "apv_tax_shield_projections", None)
            if versioned
            else (attr(dcf, "apv_tax_shield_projections_5y", None) or [])
        ),
        "dcf_apv_tax_shield_pv": (
            attr(dcf, "apv_tax_shield_pv", None)
            if versioned
            else (attr(dcf, "apv_tax_shield_pv_5y", None) or [])
        ),
        "dcf_has_apv_tax_shield": has_schedule and included_in_value,
        "dcf_has_unpriced_tax_shield_schedule": has_schedule and not included_in_value,
    }


def _horizon_context(*, dcf: object, display: DcfDisplayReconciliation) -> JsonMap:
    return {
        "dcf_projection_years": display.horizon_years or attr(dcf, "projection_years", 5),
        "dcf_displayed_projection_years": len(display.pv_fcf_clean_list) or None,
        "dcf_pv_explicit_tail": display.horizon_tail_pv,
        "dcf_has_horizon_tail": (
            display.horizon_years is not None and display.horizon_tail_pv != 0
        ),
        "dcf_explicit_horizon_years": display.horizon_years,
        "dcf_ev_band_low": display.band_low,
        "dcf_ev_band_high": display.band_high,
    }


def _projection_context(*, dcf: object, display: DcfDisplayReconciliation) -> JsonMap:
    return {
        "dcf_fcf_projections": attr(dcf, "fcf_projections_5y", None)
        or attr(dcf, "fcf_projections", []),
        "dcf_pv_fcf_projections": attr(dcf, "pv_fcf_projections_5y", None)
        or attr(dcf, "pv_fcf_projections", []),
        # Dict-backed stateless responses reach this layer through DictWrapper.
        # Templates iterate these values with ``.items()``; expose JSON mappings,
        # not the attribute-only protocol carrier whose missing ``items`` lookup
        # deliberately resolves to None.
        "dcf_sensitivity_wacc": unwrap(attr(dcf, "sensitivity_wacc", [])),
        "dcf_sensitivity_growth": unwrap(attr(dcf, "sensitivity_growth", [])),
        "dcf_sensitivity_matrix_2d": display.matrix_payload,
        "dcf_ebitda_margin_sensitivity": unwrap(attr(dcf, "ebitda_margin_sensitivity", {})),
        "dcf_sensitivity_range_policy": unwrap(attr(dcf, "sensitivity_range_policy", None)),
    }


def _readiness_context(
    *,
    readiness: DcfReadinessContext,
    audit_trail: object,
    projection_detail: object,
) -> JsonMap:
    return {
        "dcf_historical_fcf_readiness": readiness.raw,
        "dcf_historical_fcf_status": readiness.status,
        "dcf_historical_fcf_years": readiness.years,
        "dcf_actual_capex_years": readiness.capex_years,
        "dcf_actual_tax_years": readiness.tax_years,
        "dcf_actual_nwc_years": readiness.nwc_years,
        "dcf_forecast_fcff_years": readiness.forecast_fcff_years,
        "dcf_historical_fcf_missing_fields": readiness.missing_fields,
        "dcf_historical_fcf_note": readiness.note,
        "dcf_audit_trail": unwrap(audit_trail) if audit_trail is not None else None,
        "dcf_projection_detail": projection_detail,
        "dcf_flat_projection_warning": detect_flat_projections(projection_detail),
    }
