"""Executive-summary foundation translation fields."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReportTranslationFoundationExecutiveSummaryFields:
    # =========================================================================
    # EXECUTIVE SUMMARY (~25 strings)
    # =========================================================================

    exec_summary_title: str
    exec_indicative_label: str
    # Pass-4 high-severity callout (Page 1 above the headline EV)
    high_severity_callout_title: str
    high_severity_callout_lead_singular: str
    high_severity_callout_lead_plural: str
    # Pass-5 working-capital disclosure on the EV→Equity bridge
    nwc_disclosure_surplus: str  # "+€NN K release of working-capital surplus"
    nwc_disclosure_deficit: str  # "−€NN K working-capital normalization shortfall"
    nwc_disclosure_neutral: (
        str  # "Working capital was within the normalized band; no adjustment applied."
    )
    nwc_disclosure_unavailable: str  # legacy "no balance data" line
    # Pass-6: localized strings for the HIGH-severity warning rows on the
    # Page 1 callout. Keyed by warning `type` so the engine keeps emitting
    # English telemetry while the report displays NL/EN copy to advisors.
    warning_thin_comparables_proxy_message: str
    warning_thin_comparables_proxy_recommendation: str
    warning_owner_concentration_skip_message: str
    warning_owner_concentration_skip_recommendation: str
    warning_ebitda_divergence_message: str
    warning_ebitda_divergence_recommendation: str
    # Pass-8: launch-readiness "report integrity" warnings — methodological
    # disclosures that ALWAYS surface (not data-quality nudges). Each flag
    # represents a knowable limitation in the calculation pipeline that the
    # report must communicate to be defensible against a sophisticated reader.
    warning_method_substitution_message: str
    warning_method_substitution_recommendation: str
    warning_net_debt_unavailable_message: str
    warning_net_debt_unavailable_recommendation: str
    warning_owner_comp_estimated_message: str
    warning_owner_comp_estimated_recommendation: str
    warning_ebitda_benchmark_deviation_message: str
    warning_ebitda_benchmark_deviation_recommendation: str
    warning_book_equity_unavailable_message: str
    warning_book_equity_unavailable_recommendation: str
    exec_confidence_score: str
    exec_comparable_transactions: str
    exec_ev_label: str
    exec_range_label: str
    exec_normalized_label: str
    exec_revenue_label: str
    exec_employee_singular: str
    exec_employee_plural: str
    exec_industry_comparison: str
    exec_median_multiple: str
    exec_single_reference: str
    exec_sample_label: str
    exec_transactions: str
    #: 2026-05-27: singular form rendered when ``benchmark_sample_size == 1``
    #: so the report stops reading "1 transacties / 1 transactions".
    exec_transactions_singular: str
    exec_limited_data: str
    exec_insufficient_data_warning: str
    exec_benchmark_source_note: str
    exec_benchmark_applied_vs_reference: str
    exec_thin_benchmark_seller_escalation: str
    exec_thin_benchmark_advisor_escalation: str
    adaptive_intro_multiples_only_seller: str
    adaptive_intro_hybrid_seller: str
    adaptive_intro_multiples_only_advisor: str
    adaptive_intro_hybrid_advisor: str
    adaptive_footnote_multiples_only_seller: str
    adaptive_footnote_hybrid_seller: str
    adaptive_footnote_multiples_only_advisor: str
    adaptive_footnote_hybrid_advisor: str
    seller_limited_scope_title: str
    seller_limited_scope_intro: str
    seller_limited_scope_li_year: str
    seller_limited_scope_li_balance: str
    seller_limited_scope_li_advisor: str
    advisor_limited_scope_title: str
    advisor_limited_scope_intro: str
    advisor_limited_scope_li_year: str
    advisor_limited_scope_li_balance: str
    advisor_limited_scope_li_client: str
    seller_margin_diligence_note: str
    advisor_margin_diligence_note: str
    seller_multiple_bridge_title: str
    seller_multiple_bridge_reference: str
    seller_multiple_bridge_base: str
    seller_multiple_bridge_applied: str
    advisor_multiple_bridge_title: str
    advisor_multiple_bridge_reference: str
    advisor_multiple_bridge_base: str
    advisor_multiple_bridge_applied: str
    advisor_controls_audit_title: str
    advisor_controls_multiple_calibration_title: str
    advisor_controls_sector_average_label: str
    advisor_controls_risk_quality_premium_label: str
    advisor_controls_calibrated_label: str
    advisor_controls_effective_override_title: str
    advisor_controls_model_effective_multiple_label: str
    advisor_controls_advisor_effective_multiple_label: str
    advisor_controls_delta_multiple_label: str
    advisor_controls_note_label: str
    advisor_controls_historical_ebitda_weighting_title: str
    advisor_controls_weighted_ebitda_label: str
    advisor_controls_real_estate_treatment_title: str
    advisor_controls_real_estate_included_label: str
    advisor_controls_real_estate_carve_out_label: str
    advisor_controls_market_value_label: str
    advisor_controls_book_value_label: str
    advisor_controls_surplus_value_label: str
    advisor_controls_market_rent_label: str
    seller_advisor_cta_title: str
    seller_advisor_cta_lead: str
    seller_advisor_cta_button: str
    exec_methodology_hybrid: str
    exec_methodology_dcf: str
    exec_methodology_sde: str
    exec_methodology_multiples: str
    exec_methodology_asset: str
    exec_methodology_yield: str
    exec_methodology_badge_hybrid: str
    exec_methodology_badge_dcf: str
    exec_methodology_badge_sde: str
    exec_methodology_badge_multiples: str
    exec_methodology_badge_asset: str
    exec_methodology_badge_yield: str
    # Pass-10: user picked Upswitch Adaptive — engine still blends multiples+DCF
    # internally; report copy uses this lens instead of "EBITDA + DCF hybrid".
    exec_methodology_badge_adaptive: str
    exec_methodology_adaptive: str
    # 2026-05-27 (VAL-2026-35A4): when Adaptive runs on a sub-€5M profile DCF
    # is excluded and the headline is multiples-only; these variants disclose
    # the lens so the cover/exec/calib copy stops contradicting the
    # substitution banner ("Aangevraagd: Hybride → Uitgevoerd: Marktmultiples").
    exec_methodology_badge_adaptive_multiples_only: str
    exec_methodology_adaptive_multiples_only: str
    exec_goal_label: str
    exec_description_intro: str
    exec_as_of: str
    exec_description_calculated_via: str
    exec_npv_calculation: str
    exec_fcf_terminal_value: str
    exec_market_median: str
    exec_ev_equity_note_title: str
    exec_ev_equity_note_text: str
    exec_ev_equity_line2: str
    exec_ev_equity_with_balance: str
    exec_ev_equity_no_balance: str
    exec_sde_note: str
    # Owner-led micro-SME SDE cross-check (P1-5): rendered alongside the
    # EBITDA headline so a sophisticated reader can sanity-check the value
    # against the second-most-likely method buyers will use for this profile.
    exec_sde_cross_check_title: str
    exec_sde_cross_check_intro: str
    exec_sde_cross_check_sde_label: str
    exec_sde_cross_check_multiple_label: str
    exec_sde_cross_check_ev_label: str
    exec_sde_cross_check_footnote: str
    exec_implied_ebitda_multiple: str
    exec_pre_blend_label: str
    exec_blended_headline_note: str
    exec_ev_bridge_title: str
    exec_ev_bridge_ev_label: str
    exec_ev_bridge_net_debt_label: str
    exec_ev_bridge_net_cash_label: str
    exec_ev_bridge_equity_label: str
    exec_ev_bridge_nwc_label: str
    exec_ev_bridge_residual_label: str
    exec_nav_bridge_title: str
    exec_nav_bridge_book_equity: str
    exec_nav_bridge_gross_corrections: str
    exec_nav_bridge_tax_latency: str
    exec_nav_bridge_off_balance: str
    exec_nav_bridge_corrected_nav: str
    exec_asking_price_label: str
    exec_asking_price_note: str
    market_provenance_source_managed_dataset: str
    exec_narrative_basis: str
    exec_narrative_basis_dcf: str
    exec_narrative_basis_hybrid: str
    exec_narrative_basis_asset: str
    exec_narrative_basis_yield: str
    exec_narrative_ev_note: str
    exec_official_registry_head: str
    exec_official_filing_year_label: str
    exec_official_source_staatsblad: str
    exec_dd_accountant_vs_official_title: str
    exec_dd_col_accountant: str
    exec_official_dd_line_item: str
    exec_official_dd_col_official: str
    exec_official_dd_delta_pct: str
    exec_official_variance_title: str
    exec_official_explanation_required: str
    exec_official_variance_hard_note: str
    exec_official_trust_match_verified: str
    exec_official_total_assets_label: str
    exec_official_equity_label: str
    exec_saas_anchor_label: str
    exec_saas_quality_title: str
    exec_saas_nrr_label: str
    exec_saas_rule_of_40_label: str
    exec_saas_churn_label: str
    exec_saas_arr_growth_label: str

