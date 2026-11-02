"""DCF valuation-page foundation translation fields."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReportTranslationFoundationDcfFields:
    # =========================================================================
    # DCF VALUATION PAGE (~20 strings)
    # =========================================================================

    dcf_page_title: str
    dcf_page_subtitle: str
    dcf_projection_table_title: str
    dcf_wacc_buildup_title: str
    dcf_wacc_buildup_fallback_title: str
    dcf_wacc_buildup_fallback_body: str
    dcf_wacc_buildup_fallback_applied_label: str
    dcf_wacc_buildup_override_note: str
    dcf_wacc_capm_buildup_label: str
    dcf_wacc_applied_in_wacc_label: str
    dcf_wacc_rounded_label: str
    dcf_row_revenue: str
    dcf_row_growth: str
    dcf_row_ebitda: str
    dcf_row_ebitda_margin: str
    dcf_row_ebit: str
    dcf_row_taxes: str
    dcf_row_nopat: str
    dcf_row_da_addback: str
    dcf_row_capex: str
    dcf_row_nwc: str
    dcf_row_fcff: str
    dcf_row_discount_factor: str
    dcf_row_pv_fcff: str
    dcf_terminal_value_header: str
    dcf_ev_summary_header: str
    dcf_pv_explicit_label: str
    dcf_pv_terminal_label: str
    dcf_enterprise_value_label: str
    dcf_sensitivity_matrix_title: str
    dcf_assumptions_note: str
    dcf_wacc_formula_label: str
    dcf_cost_of_equity_label: str
    dcf_cost_of_debt_label: str
    dcf_equity_weight_label: str
    dcf_debt_weight_label: str
    dcf_tax_rate_label: str
    dcf_risk_free_rate_label: str
    dcf_beta_label: str
    dcf_erp_label: str
    dcf_size_premium_label: str
    dcf_csr_label: str

    calib_multiple_waterfall_title: str
    calib_multiple_waterfall_intro: str
    calib_value_waterfall_title: str
    calib_value_waterfall_intro: str
    calib_value_waterfall_intro_ev_focus: str
    calib_value_waterfall_intro_balance_provided: str
    saas_appendix_title: str
    saas_appendix_intro: str
    saas_appendix_metrics_title: str
    saas_appendix_adjustments_title: str
    saas_appendix_no_adjustments: str
    saas_appendix_factor_label: str
    saas_appendix_impact_label: str
    saas_appendix_note_label: str
    saas_appendix_arr_growth_label: str
    saas_appendix_gross_margin_label: str
    saas_appendix_customer_concentration_label: str
    saas_appendix_cac_payback_label: str
    saas_appendix_customer_churn_label: str
    saas_appendix_nrr_expansion_spread_label: str
    saas_appendix_arr_label: str
    saas_appendix_ltv_cac_label: str
    saas_appendix_magic_number_label: str
    saas_quality_score_label: str
    saas_quality_score_caption: str  # B6 — methodology disclosure
    saas_appendix_ebitda_crosscheck_label: str  # B10 — EBITDA × multiple cross-check on hero
    saas_quality_strong: str
    saas_quality_healthy: str
    saas_quality_developing: str
    saas_quality_at_risk: str
    saas_waterfall_title: str
    saas_waterfall_base: str
    saas_waterfall_final: str
    saas_waterfall_benchmark_note: str
    saas_waterfall_clamp_note: str
    saas_arr_bridge_title: str
    saas_arr_bridge_source: str
    saas_expansion_revenue_label: str

