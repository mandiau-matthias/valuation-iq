"""Per-method foundation translation fields."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReportTranslationFoundationPerMethodFields:
    # =========================================================================
    # PER-METHOD DEDICATED PAGES — EBITDA / SDE / Revenue (~12 strings)
    # =========================================================================

    # EBITDA-Multiple dedicated page
    ebitda_multiple_methodology_intro: str
    ebitda_multiple_assumptions_note: str
    ebitda_multiple_cross_check_title: str
    ebitda_multiple_cross_check_intro: str
    ebitda_multiple_implied_ev_sales_label: str
    ebitda_multiple_implied_pe_label: str
    ebitda_multiple_dloc_dlom_title: str
    ebitda_multiple_dloc_dlom_body: str
    ebitda_multiple_provenance_label: str
    ebitda_multiple_provenance_n: str
    ebitda_multiple_provenance_window: str
    ebitda_multiple_provenance_refresh: str
    # Comparable-deals table (rendered on the EV/EBITDA dossier
    # whenever the engine surfaces a non-empty `comparables` list).
    comparables_table_title: str
    comparables_table_subtitle: str
    comparables_table_col_name: str
    comparables_table_col_ev_ebitda: str
    comparables_table_col_ev_revenue: str
    comparables_table_col_pe: str
    comparables_table_empty: str
    # Driver-impact tornado on the EV/EBITDA dossier.
    driver_tornado_title: str
    driver_tornado_subtitle: str
    driver_tornado_axis_label: str
    driver_tornado_basis_label: str
    # Cross-reference from the EV/EBITDA dossier to the consolidated
    # calibration ledger on the following page (audit trail anchor).
    ebitda_multiple_calibration_xref: str

    # SDE dedicated page
    sde_dedicated_page_title: str
    sde_methodology_intro: str
    sde_business_size_label: str
    sde_business_size_intro: str
    sde_assumptions_note: str
    sde_summary_title: str
    sde_summary_row_sde: str
    sde_summary_row_multiple: str
    sde_enterprise_value_label: str
    sde_p25_p75_band_label: str
    sde_size_band_label: str
    sde_buyer_pool_label: str
    method_label_adjusted_nav: str
    method_label_ebitda_multiple: str
    method_label_sde: str
    method_label_revenue_multiple: str
    method_label_dcf: str

    # SDE bridge ladder partial (Net income → SDE)
    sde_bridge_title: str
    sde_bridge_net_income: str
    sde_bridge_interest: str
    sde_bridge_taxes: str
    sde_bridge_depreciation: str
    sde_bridge_owner_comp: str
    sde_bridge_other: str
    sde_bridge_total: str
    sde_bridge_footnote: str
    # Cross-reference link from the SDE page back to the EBITDA-
    # normalization dossier (intra-PDF anchor #ebitda-normalization-page).
    sde_see_normalization_link: str

    # Revenue-Multiple dedicated page
    revenue_multiple_methodology_intro: str
    revenue_multiple_summary_title: str
    revenue_multiple_operating_revenue_label: str
    revenue_multiple_revenue_label: str
    revenue_multiple_multiple_label: str
    revenue_multiple_range_label: str
    revenue_multiple_metric_label: str
    revenue_multiple_axis_label: str
    revenue_multiple_growth_band_label: str
    revenue_multiple_growth_band_intro: str
    revenue_multiple_growth_cagr_label: str
    revenue_multiple_implied_peg_label: str
    revenue_multiple_growth_band_stretched: str
    revenue_multiple_assumptions_note: str

    # Generic multiple sensitivity matrix component (re-used across pages)
    multiple_sensitivity_matrix_title: str
    multiple_sensitivity_caption: str

    # Calibration per-method navigator (Aurora visual breadcrumb)
    calib_per_method_nav_label: str
    calib_per_method_nav_caption: str

    # Calibration multiple-waterfall cross-reference (dedupe-2026-05-03)
    calib_waterfall_xref_label: str
    calib_waterfall_xref_caption: str

    # Executive summary NAV bridge cross-reference (dedupe-2026-05-03)
    exec_nav_bridge_xref_label: str
    exec_nav_bridge_xref_caption: str
