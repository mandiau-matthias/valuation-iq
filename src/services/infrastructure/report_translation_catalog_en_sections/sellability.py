"""Sellability, transferability, and value-method display copy."""

from __future__ import annotations

from src.services.infrastructure.report_step_names import CALC_STEP_NAMES_EN as _CALC_STEP_NAMES_EN


def build_english_sellability_translations() -> dict[str, object]:
    return {
        # SELLABILITY-MVP — EN parity. Caregiver-tone per A0 baseline.
        "sellability_section_title": "Sellability",
        "sellability_section_subtitle": (
            "What would lift your value — concrete actions, sized in € "
            "against today's sector multiples."
        ),
        "sellability_score_label": "Sellability score",
        "sellability_confidence_high": "High confidence",
        "sellability_confidence_med": "Medium confidence",
        "sellability_confidence_low": "Low confidence",
        "sellability_band_significant_label": "Significant work to do",
        "sellability_band_significant_advice": (
            "A buyer would see real risks today. The good news: each "
            "one is actionable in a 12 to 18 month preparation window."
        ),
        "sellability_band_foundations_label": "Foundations in place",
        "sellability_band_foundations_advice": (
            "The basics are there. A focused effort on a few areas "
            "would lift this materially before a sale."
        ),
        "sellability_band_sale_ready_in_most_label": "Sale-ready in most ways",
        "sellability_band_sale_ready_in_most_advice": (
            "You're close. The lifts below are the gap between today's "
            "number and what a thoughtful buyer would pay."
        ),
        "sellability_band_sale_ready_today_label": "Sale-ready today",
        "sellability_band_sale_ready_today_advice": (
            "Your business presents well. If timing is right, you could " "begin a process now."
        ),
        "sellability_factor_owner_dependence": "Owner dependence",
        "sellability_factor_customer_concentration": "Customer concentration",
        "sellability_factor_revenue_quality": "Revenue quality",
        "sellability_factor_financial_cleanliness": "Financial cleanliness",
        "sellability_factor_growth_trend": "Growth trend",
        "sellability_factor_transferability": "Transferability",
        "sellability_factor_breakdown_heading": "How your business scores",
        "sellability_factor_breakdown_subheading": ("Six factors a buyer weighs, at a glance."),
        "sellability_factor_owner_dependence_explanation": (
            "How well the business runs without you — keys, " "client relationships, and know-how."
        ),
        "sellability_factor_customer_concentration_explanation": (
            "What buyers see as concentration risk on your top-3 clients."
        ),
        "sellability_factor_revenue_quality_explanation": (
            "How much of your revenue comes back each year without " "having to win it again."
        ),
        "sellability_factor_financial_cleanliness_explanation": (
            "Whether a buyer can trust the books without forensic work."
        ),
        "sellability_factor_growth_trend_explanation": (
            "Whether the business is moving forward — revenue and margin "
            "over the last few years."
        ),
        "sellability_factor_transferability_explanation": (
            "How easily the business can change hands — licences, " "contracts, processes."
        ),
        "sellability_top_lifts_heading": "What would lift your value",
        "sellability_top_lifts_subheading": (
            "Three things that move the number, sized in € against " "today's sector multiples."
        ),
        "sellability_tertiary_lifts_heading": "Other potential lifts",
        "sellability_tertiary_lifts_subheading": (
            "Worth attention, but we need more data on your business "
            "to size them in € accurately."
        ),
        "sellability_skipped_title": "Sellability score not yet computed",
        "sellability_skipped_body": (
            "Complete your owner profile to unlock your Sellability "
            "score. That grounds the valuation and clarifies transferability risk. "
            "The score shows what a buyer would concretely want "
            "to see before a sale, and sizes each improvement in €."
        ),
        "sellability_low_confidence_heading": ("Tell us a bit more about your business"),
        "sellability_low_confidence_body": (
            "Complete your owner profile and run a full valuation. "
            "That anchors the valuation and clarifies transferability — "
            "your Sellability lifts will be sized in € against your "
            "sector multiples once we have enough to defend the numbers."
        ),
        "sellability_sale_ready_empty_heading": "Your business is in great shape.",
        "sellability_sale_ready_empty_body": (
            "There's nothing material to fix on the score. When you're "
            "ready, we can prepare the sale process — that's a "
            "different kind of work, and we can guide you through it."
        ),
        "sellability_provenance_native": ("Sized against your country's sector multiples."),
        "sellability_provenance_aggregate_clone": (
            "Sized against a closely-related sector in your country."
        ),
        "sellability_provenance_aggregate": (
            "Sized against a broader sector benchmark — local data is " "still being collected."
        ),
        "sellability_close_caregiver": (
            "This is a snapshot. Real value comes from the work between " "today and your exit."
        ),
        "sellability_invite_accountant_heading": ("Loop your accountant in"),
        "sellability_invite_accountant_body": (
            "Your accountant knows the business and can calibrate this "
            "score with you. One click and they're in."
        ),
        "sellability_invite_accountant_cta": "Invite my accountant",
        "owner_profiling_post_deal_section_title": "Pre-Deal vs. Post-Deal Equity",
        "owner_profiling_post_deal_section_subtitle": (
            "Effect of replacing current owner compensation with a " "market-rate manager."
        ),
        "owner_profiling_post_deal_pre_label": "Pre-Deal equity",
        "owner_profiling_post_deal_post_label": "Post-Deal equity",
        "owner_profiling_post_deal_delta_label": "Delta",
        "owner_profiling_post_deal_owner_comp_label": "Current owner compensation",
        "owner_profiling_post_deal_market_label": "Market replacement cost",
        "owner_profiling_post_deal_multiple_label": "Applied multiple",
        "owner_profiling_post_deal_estimated_caveat": (
            "Owner compensation estimated from revenue heuristics; "
            "provide actual figures for higher-confidence numbers."
        ),
        "owner_profiling_post_deal_not_applicable_title": (
            "Post-Deal view: not applicable to this methodology"
        ),
        "owner_profiling_post_deal_not_applicable_body": (
            "Asset-based and startup valuations do not derive value "
            "from owner-replaceable earnings. A Pre-Deal/Post-Deal "
            "swap is not meaningful here."
        ),
        "owner_profiling_transferability_v2_title": ("Transferability — decomposed"),
        "owner_profiling_transferability_v2_subtitle": (
            "The 12-factor analysis broken into 5 advisor-visible "
            "drivers plus the likely buyer profile."
        ),
        "owner_profiling_subfactor_planning_continuity": "Planning & continuity",
        "owner_profiling_subfactor_relationship_transferability": ("Relationship transferability"),
        "owner_profiling_subfactor_operational_independence": ("Operational independence"),
        "owner_profiling_subfactor_knowledge_codification": ("Knowledge codification"),
        "owner_profiling_subfactor_brand_independence": "Brand independence",
        "owner_profiling_buyer_block_title": "Likely buyer",
        "owner_profiling_buyer_archetype_individual_operator": ("Individual operator"),
        "owner_profiling_buyer_archetype_search_fund": "Search-fund principal",
        "owner_profiling_buyer_archetype_pe_add_on": "PE add-on",
        "owner_profiling_buyer_archetype_strategic": "Strategic acquirer",
        "owner_profiling_buyer_archetype_family_office": "Family office",
        "owner_profiling_buyer_hours_label": "Expected commitment",
        "owner_profiling_buyer_skill_label": "Sector skill match",
        "owner_profiling_cascade_title": "How this discount is built",
        "owner_profiling_method_incidence_title": "Per-method impact",
        "owner_profiling_method_incidence_subtitle": (
            "Different methods absorb owner dependency differently."
        ),
        "owner_profiling_method_col_method": "Method",
        "owner_profiling_method_col_coefficient": "Coefficient",
        "owner_profiling_method_col_applied": "Applied",
        "owner_profiling_method_col_rationale": "Rationale",
        "owner_profiling_method_skips_label": "n/a",
        "owner_profiling_blended_label": "Blended impact across methods",
        "owner_profiling_severity_minimal": "Minimal",
        "owner_profiling_severity_moderate": "Moderate",
        "owner_profiling_severity_severe": "Severe",
        "owner_profiling_severity_extreme": "Extreme",
        "owner_profiling_severity_tier_label": "Tier {tier} / 4",
        "owner_profiling_confidence_label": "Confidence",
        "owner_profiling_confidence_high": "High",
        "owner_profiling_confidence_medium": "Medium",
        "owner_profiling_confidence_low": "Low",
        "owner_profiling_confidence_coverage_template": "{coverage}% factor coverage",
        "owner_profiling_hero_kicker": "Transferability story",
        "owner_profiling_hero_subtitle": (
            "How this valuation reflects the owner's transition to a new buyer."
        ),
        "owner_profiling_methodology_title": "Methodology & sources",
        "owner_profiling_methodology_subtitle": (
            "Every layer of the model is documented against the published "
            "M&A literature and accepted market standards."
        ),
        "owner_profiling_methodology_layer_decomposition": ("Dependency decomposition"),
        "owner_profiling_methodology_layer_buyer_profile": "Buyer profile",
        "owner_profiling_methodology_layer_incidence": "Per-method incidence",
        "owner_profiling_methodology_layer_severity": "Severity & raw discount",
        "owner_profiling_methodology_source_language_note": (
            "Citations preserved in the original publication language "
            "(typically English) for academic verifiability."
        ),
        "owner_profiling_sme_segment_label": "EU SME segment",
        "owner_profiling_sme_segment_individual_operator": (
            "Micro (EU 2003/361: <10 employees, ≤€2M turnover)"
        ),
        "owner_profiling_sme_segment_search_fund": (
            "Small (EU 2003/361: <50 employees, ≤€10M turnover)"
        ),
        "owner_profiling_sme_segment_pe_add_on": (
            "Small / Medium (EU 2003/361: <250 employees, ≤€50M turnover)"
        ),
        "owner_profiling_sme_segment_strategic": ("Lower mid-market (above EU SME ceiling)"),
        "owner_profiling_sme_segment_family_office": (
            "Cross-band (segment depends on platform fit)"
        ),
        "owner_profiling_buyer_rationale_individual_operator": (
            "At {eur} mid equity, the realistic buyer pool is "
            "individual operators buying themselves an owner-operator "
            "role (40 hrs/wk, limited sector skill)."
        ),
        "owner_profiling_buyer_rationale_search_fund": (
            "At {eur} mid equity, the realistic buyer pool is "
            "search-fund principals — first-time operators with high "
            "effort but limited sector depth (50 hrs/wk, mid skill match)."
        ),
        "owner_profiling_buyer_rationale_pe_add_on": (
            "At {eur} mid equity, the realistic buyer is a PE add-on "
            "with operating infrastructure already in place (30 hrs/wk "
            "effective, high skill match via portfolio playbooks)."
        ),
        "owner_profiling_buyer_rationale_strategic": (
            "At {eur} mid equity, the realistic buyer is a strategic "
            "acquirer slotting the asset onto an existing platform "
            "(15 hrs/wk effective, very high skill match)."
        ),
        "owner_profiling_buyer_rationale_family_office": (
            "Family office assumption applied; check with advisor."
        ),
        "owner_profiling_buyer_rationale_unknown": (
            "Deal size unavailable; defaulting to a search-fund buyer "
            "(50 hrs/wk, mid sector skill) as the median SMB assumption "
            "per Pepperdine PCMI."
        ),
        "owner_profiling_method_label_ebitda_multiple": "EBITDA multiple",
        "owner_profiling_method_label_dcf": "DCF",
        "owner_profiling_method_label_sde": "SDE multiple",
        "owner_profiling_method_label_revenue_multiple": "Revenue multiple",
        "owner_profiling_method_label_arr_multiple": "ARR multiple",
        "owner_profiling_method_label_adaptive": "Adaptive (blended)",
        "owner_profiling_method_label_adjusted_nav": "Adjusted NAV",
        "owner_profiling_method_label_fiscal_4x": "Fiscal 4×",
        "owner_profiling_method_label_startup": "Startup / VC",
        "owner_profiling_method_rationale_ebitda_multiple": (
            "Comps are managed businesses; full owner-transition " "discount applies."
        ),
        "owner_profiling_method_rationale_dcf": (
            "Cash-flow projections assume continuity; full discount applies."
        ),
        "owner_profiling_method_rationale_sde": (
            "SDE already captures owner comp; only the residual "
            "transferability haircut on the multiple applies (~0.7×)."
        ),
        "owner_profiling_method_rationale_revenue_multiple": (
            "Revenue multiples lean on customer stickiness; partial " "discount (~0.6×)."
        ),
        "owner_profiling_method_rationale_arr_multiple": (
            "ARR multiples already discount owner-led customer-success; " "partial (~0.5×)."
        ),
        "owner_profiling_method_rationale_adaptive": (
            "Adaptive blends multiple lenses; near-full discount (~0.85×)."
        ),
        "owner_profiling_method_rationale_adjusted_nav": (
            "NAV transfers with the assets; owner-dependency does not apply."
        ),
        "owner_profiling_method_rationale_fiscal_4x": (
            "Fiscal 4× is a regulatory floor; owner-dependency does not " "adjust it."
        ),
        "owner_profiling_method_rationale_startup": (
            "Startup valuation is forward-looking on team / market; "
            "owner-dep adjustment is captured elsewhere."
        ),
        "owner_profiling_gap_inline_title": "Transferability gap",
        "owner_profiling_weakest_pill": "↓ weakest",
        "owner_profiling_strongest_pill": "↑ strongest",
        "owner_profiling_hero_applied_label": "Applied",
        "owner_profiling_hero_blended_label": "Blended",
        "owner_profiling_hours_per_week_unit": "hrs/wk",
        "owner_profiling_gap_summary_template": (
            "Owner runs ~{owner_hours} hrs/wk vs. buyer assumption "
            "~{buyer_hours} hrs/wk (gap: {hours_gap} hrs); "
            "skill gap {skill_gap}/100. "
            "Severity: {severity_localised}; raw discount {raw_pct}."
        ),
        "owner_profiling_cascade_owner_template": (
            "Owner profile: ~{owner_hours} hrs/week, weakest sub-factor "
            "is {weakest_label_lower} (score {weakest_score}/100)."
        ),
        "owner_profiling_cascade_buyer_template": (
            "Likely buyer ({buyer_archetype}): ~{buyer_hours} hrs/week, "
            "sector skill match {buyer_skill}/100."
        ),
        "owner_profiling_cascade_gap_template": (
            "Transferability gap is {severity_localised}: {hours_gap} "
            "hrs/week + {skill_gap}/100 skill. Raw model correction {raw_pct}."
        ),
        "owner_profiling_cascade_applied_template": (
            "Headline applied {headline_pct}, blended across eligible "
            "methods at {blended_pct} effective."
        ),
        "omni_methodology_statement_dcf": (
            "The valuation is based on a DCF analysis using the present value "
            "of future free cash flows, including terminal value and WACC as the "
            "discount rate."
        ),
        "omni_methodology_statement_adjusted_nav": (
            "The valuation is based on adjusted net asset value, using "
            "adjusted assets, liabilities, and latent charges as the primary "
            "value drivers instead of market multiples."
        ),
        "omni_methodology_statement_fiscal_4x": (
            "The historical Belgian tax reference uses book equity plus four "
            "times EBITDA from the last financial year closed before 1 January "
            "2026. It determines a value for 31 December 2025 and is not a sale, "
            "succession, or internal transfer valuation."
        ),
        "dcf_readiness_note_imported_ready": (
            "Historical DCF coverage: actual CapEx in {capex_years} years, tax expense in "
            "{tax_years} years, and annual ΔNWC in {nwc_years} years."
        ),
        "dcf_readiness_note_partial": (
            "DCF uses imported inputs for CapEx ({capex_years}), taxes ({tax_years}), and working capital "
            "({nwc_years}), but still falls back on assumptions where history is incomplete."
        ),
        "dcf_readiness_note_manual_fallback": (
            "DCF is primarily running on fallback assumptions because historical free-cash-flow detail is still limited."
        ),
        "dcf_readiness_note_explicit_fcff": (
            "DCF uses {forecast_years} explicitly supplied FCFF forecast years committed "
            "in the sealed run. Historical CapEx, tax and working-capital inputs are not "
            "substituted into these cash flows."
        ),
        "dcf_missing_field_label_capex": "CapEx",
        "dcf_missing_field_label_tax": "tax expense",
        "dcf_missing_field_label_nwc": "working-capital movement",
        "anomaly_summary_template": (
            "Statistical anomaly detected in account {account} for {year}{direction_clause}."
        ),
        "wf_compact_database_p50": "Database P50",
        "wf_compact_market_median": "Market median",
        "wf_compact_sme_calib": "SME calib.",
        "wf_compact_key_person": "Key person",
        "wf_compact_size": "Size",
        "wf_compact_other_adj": "Other adj.",
        "wf_bs_debt": "Debt adj.",
        "wf_bs_asset": "Asset adj.",
        "wf_bs_provision": "Prov.",
        "wf_bs_tax": "Tax adj.",
        "wf_bs_cash": "Cash adj.",
        "wf_bs_working_capital": "WC adj.",
        "wf_bs_other": "B/S adj.",
        "wf_basis_revenue": "Revenue",
        "wf_basis_sde": "Weighted SDE",
        "wf_basis_sde_short": "SDE",
        "wf_basis_ebitda": "Normalized EBITDA",
        "wf_basis_ebitda_short": "Norm. EBITDA",
        "wf_applied_multiple": "Applied multiple",
        "wf_applied_multiple_short": "Applied",
        "wf_bridge_multiple_short": "Multiple",
        "wf_enterprise_value": "Enterprise value",
        "wf_excess_cash": "Excess cash",
        "wf_excess_cash_short": "Excess cash",
        "wf_cash_equivalents": "Cash & cash equivalents",
        "wf_cash_short": "Cash",
        "wf_financial_debt": "Financial debt",
        "wf_debt_short": "Debt",
        "wf_net_cash": "Net cash",
        "wf_net_debt": "Net debt",
        "wf_balance_sheet_fallback": "Balance-sheet adj.",
        "wf_equity_value": "Equity value",
        "wf_equity_short": "Equity",
        "wf_tax_latency_short": "Tax",
        "calib_wf_market_median_db_p50": "Market Median (Database P50)",
        "calib_wf_gross_multiple_before_sme": "Gross multiple from market data before SME calibration",
        "calib_wf_sme_calibration": "SME Calibration",
        "calib_wf_sme_calibration_desc": "Adjustment for small company (−{pct}% per Koller et al.)",
        "calib_wf_market_consensus_p50": "Market Consensus (P50 Median)",
        "calib_wf_not_applicable": "Not applicable",
        "calib_wf_not_applicable_desc": "Break-even or zero revenue",
        "calib_wf_assessment_label": "Assessment",
        "calib_wf_size_discount_suffix": "Discount",
        "calib_wf_size_discount_desc": "Limited documentation, execution risk",
        "calib_wf_other_adjustment": "Other Adjustment",
        "calib_wf_other_adjustment_desc": "Rounding to applied multiple",
        "adj_reported_ebitda_year": "Reported EBITDA ({year})",
        "adj_normalized_ebitda_year": "Normalized EBITDA ({year})",
        "adj_fallback_label": "Adjustment",
        "adj_submitted_metadata": "Submitted metadata",
        "adj_total_normalization_label": "Total normalization adjustments",
        "adj_auto_desc_count_template": "{count} normalization(s) from submitted metadata",
        "adj_auto_desc_aggregate": "Normalization delta from submitted metadata",
        "report_unknown_stage_label": "Unknown",
        "calc_step_names": _CALC_STEP_NAMES_EN,
        "calc_step_generic": "Step {n}",
        "val_method_display_hybrid": "Hybrid (Multiples + DCF)",
        "val_method_display_dcf": "DCF Analysis",
        "val_method_display_multiples_ebitda": "Market Multiples (EV/EBITDA)",
        "val_method_display_multiples_revenue": "Market Multiples (EV/Revenue)",
        "val_method_display_asset": "Asset-based valuation (NAV)",
        "val_method_display_yield": "Real-estate yield (rent ÷ cap-rate)",
        # STAGE-AWARE BREAKDOWN (BET-463) — transparent calculation breakdown.
        "stage_breakdown_section_title": "Transparent calculation",
        "stage_breakdown_section_subtitle": (
            "How this value is built — the methods used, their weight and "
            "contribution, and what this number does and does not say at this "
            "stage."
        ),
        "stage_breakdown_stage_label": "Stage",
        "stage_breakdown_tier_label": "Tier",
        "stage_breakdown_methods_heading": "Method",
        "stage_breakdown_weight_heading": "Weight",
        "stage_breakdown_contribution_heading": "Contribution",
        "stage_breakdown_rationale_label": "Why these methods",
        "stage_breakdown_caveats_label": "What this number does and does not say",
        "stage_breakdown_provenance_label": "Benchmark provenance",
        "stage_breakdown_reconciles_note": (
            "The weighted methods above re-derive the value indication shown."
        ),
        "stage_breakdown_indicative_blend_note": (
            "The methods below form an indicative blend; at this stage we show "
            "a range, not a point estimate."
        ),
        "stage_breakdown_no_data": "Not available",
    }
