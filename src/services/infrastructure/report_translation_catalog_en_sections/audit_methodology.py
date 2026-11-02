"""Audit-trail, deal-structure, calibration, fiscal, and defensibility copy."""

from __future__ import annotations


def build_english_audit_methodology_translations() -> dict[str, object]:
    return {
        # Audit-trail (round-4 — moved from FE BelgianSmeAuditPanel to report)
        "nav_audit_trail_title": "Audit trail — revaluation & deferred tax",
        "nav_audit_trail_subtitle": (
            "Defensible dossier for the buyer: per-asset revaluation, deferred tax per asset "
            "class and the corporate-tax rate applied (Art. 215 WIB 92)."
        ),
        "nav_audit_trail_re_card_title": "Real estate — book → appraisal",
        "nav_audit_trail_re_book": "Book value",
        "nav_audit_trail_re_appraisal": "Appraisal",
        "nav_audit_trail_re_meerwaarde": "Uplift",
        "nav_audit_trail_eq_card_title": "Equipment — economic lifespan",
        "nav_audit_trail_eq_subtitle_user": "User-supplied economic book value.",
        "nav_audit_trail_eq_subtitle_straight_line": "Straight-line economic depreciation",
        "nav_audit_trail_eq_age_label": "age",
        "nav_audit_trail_eq_life_label": "life",
        "nav_audit_trail_eq_original_cost": "Original cost",
        "nav_audit_trail_eq_tax_book": "Tax book",
        "nav_audit_trail_eq_economic_book": "Economic book",
        "nav_audit_trail_eq_meerwaarde": "Uplift",
        "nav_audit_trail_dtb_title": "Deferred tax per asset class",
        "nav_audit_trail_dtb_asset_class": "Asset class",
        "nav_audit_trail_dtb_meerwaarde": "Uplift",
        "nav_audit_trail_dtb_rate": "Rate",
        "nav_audit_trail_dtb_deferred_tax": "Deferred tax",
        "nav_audit_trail_dtb_source": "Source",
        "nav_audit_trail_dtb_total": "Total deferred tax",
        "nav_audit_trail_dtb_effective_label": "effective",
        "nav_audit_trail_sme_title": "Resolved CIT rate (Art. 215 WIB 92)",
        "nav_audit_trail_sme_eligible": "SME",
        "nav_audit_trail_sme_standard": "standard",
        "nav_rate_source_user_override": "User override",
        "nav_rate_source_global_user_rate": "Global user rate",
        "nav_rate_source_engine_default_per_asset": "Default per asset class",
        "nav_rate_source_engine_default_global": "Resolved CIT rate",
        "nav_asset_class_real_estate": "Real estate",
        "nav_asset_class_inventory": "Inventory",
        "nav_asset_class_receivables": "Receivables",
        "nav_asset_class_hidden_reserves": "Hidden reserves",
        "nav_asset_class_other_revaluations": "Other revaluations",
        # Deal-structure (Share deal vs. Asset deal)
        "nav_deal_structure_title": "Deal structure — Share deal vs. Asset deal",
        "nav_deal_structure_subtitle": (
            "Comparison of a share deal vs. an asset deal economics, including the goodwill "
            "amortisation tax shield (Art. 61 WIB 92) and private-shareholder capital-gains tax "
            "(Art. 90 WIB 92; rate and conditions to be confirmed with a tax advisor)."
        ),
        "nav_deal_headline_price": "Headline price",
        "nav_deal_seller_tax": "Seller tax",
        "nav_deal_seller_net_proceeds": "Seller net proceeds",
        "nav_deal_buyer_tax_shield": "Buyer tax shield (NPV)",
        "nav_deal_buyer_net_cost": "Buyer net cost",
        "nav_deal_indifference_premium": "Indifference premium",
        "nav_deal_indifference_caption": (
            "How much higher the asset-deal price must be than the share-deal price for the buyer "
            "to be indifferent (given the tax shield)."
        ),
        # EBITDA-Multiple dedicated page
        "ebitda_multiple_methodology_intro": (
            "The EV/EBITDA multiple is anchored on a peer set of comparable Belgian SME transactions "
            "(sector, revenue band, region). The base case is then calibrated for entity-specific "
            "risks (key-person, customer concentration, scale, liquidity) — every step is traceable "
            "in the calibration ledger below."
        ),
        "ebitda_multiple_assumptions_note": (
            "Multiple source: peer set of comparable Belgian SME transactions (sector, revenue band, region); "
            "annual refresh. Calibrated steps follow the Damodaran structure (size discount, control / "
            "liquidity premia). EBITDA is normalized through the bridge — owner compensation, non-recurring "
            "items and one-off gains are explicitly reported on the EBITDA Normalization page."
        ),
        "ebitda_multiple_cross_check_title": "Implied cross-checks",
        "ebitda_multiple_cross_check_intro": (
            "The applied EV/EBITDA multiple implies other multiples too. "
            "These cross-checks place the headline figure in absolute economic terms."
        ),
        "ebitda_multiple_implied_ev_sales_label": "Implied EV/Sales",
        "ebitda_multiple_implied_pe_label": "Implied price/earnings (after tax)",
        "ebitda_multiple_dloc_dlom_title": "Control basis & marketability note",
        "ebitda_multiple_dloc_dlom_body": (
            "Reported on a 100% control, marketable basis. Discount for Lack of Control (DLOC) "
            "and Discount for Lack of Marketability (DLOM) have not been applied — a formal "
            "minority-stake valuation requires additional analysis. Typical M&amp;A reference "
            "ranges: DLOC 10–25%, DLOM 15–35% (Mercer Capital 2017; Pratt &amp; Niculita 2008, "
            "Chapter 13). Under those typical haircuts, a 100% equity value of €X would imply a "
            "minority-stake value of approximately €X × (1 − DLOC) × (1 − DLOM)."
        ),
        "ebitda_multiple_provenance_label": "Peer-set provenance",
        "ebitda_multiple_provenance_n": "N = {count} transactions",
        "ebitda_multiple_provenance_window": "Window: {months} months",
        "ebitda_multiple_provenance_refresh": "Last refresh: {date}",
        "comparables_table_title": "Comparable transactions",
        "comparables_table_subtitle": (
            "M&A comparables the peer-set is anchored on. Identifiers anonymised where NDA-protected."
        ),
        "comparables_table_col_name": "Company",
        "comparables_table_col_ev_ebitda": "EV/EBITDA",
        "comparables_table_col_ev_revenue": "EV/Sales",
        "comparables_table_col_pe": "P/E",
        "comparables_table_empty": "No comparables disclosed for this dossier.",
        "driver_tornado_title": "Multiple impact by step (€)",
        "driver_tornado_subtitle": (
            "Model adjustments ranked by €-impact relative to the base multiple. "
            "The largest bars dominate the headline enterprise value."
        ),
        "driver_tornado_axis_label": "€-impact on EV",
        "driver_tornado_basis_label": "basis",
        "ebitda_multiple_calibration_xref": (
            "The full step-by-step calibration ledger (P25/P75 → discounts → applied multiple) "
            "is on the next page — Calibration. Academic footnotes (Damodaran, Pratt) are "
            "anchored per step there."
        ),
        # SDE dedicated page
        "sde_dedicated_page_title": "SDE Valuation",
        "sde_methodology_intro": (
            "SDE (Seller's Discretionary Earnings) is the standard lens for owner-operator businesses where "
            "the owner works full-time in the company. We start from whichever earnings anchor the data supports — "
            "Net Income (full reconciliation) or Normalized EBITDA (when interest / taxes / D&A are already "
            "absorbed) — and add the owner's compensation. The resulting SDE is multiplied by a buyer-comparable "
            "multiple from a calibrated transaction base (BizBuySell / EBA databases for BE / EU). This is the "
            "most-used lens for SMB transfers under €1M."
        ),
        "sde_business_size_label": "Size band & buyer-comparable range",
        "sde_business_size_intro": (
            "The P25–P75 band is fitted on comparable transactions within the same size category. "
            "Further from the median = greater uncertainty on the applicable multiple."
        ),
        "sde_assumptions_note": (
            "Multiple source: buyer-comparable transaction database (BizBuySell US, EBA for BE/EU), grouped by "
            "revenue band and sector. Owner compensation is normalized to a market-equivalent manager salary. "
            "SDE is reported for one full-time-working owner; with multiple active owners the second and "
            "subsequent should be reclassified as a personnel cost before the bridge."
        ),
        "sde_summary_title": "SDE × Multiple — summary",
        "sde_summary_row_sde": "SDE (Seller's Discretionary Earnings)",
        "sde_summary_row_multiple": "SDE multiple",
        "sde_enterprise_value_label": "Enterprise Value (SDE)",
        "sde_p25_p75_band_label": "Buyer-comparable range (P25–P75)",
        "sde_size_band_label": "Size band",
        "sde_buyer_pool_label": "buyer pool",
        "method_label_adjusted_nav": "Adjusted NAV",
        "method_label_ebitda_multiple": "EV/EBITDA",
        "method_label_sde": "SDE",
        "method_label_revenue_multiple": "EV/Sales",
        "method_label_dcf": "DCF",
        # SDE bridge ladder
        "sde_bridge_title": "Bridge — Reported earnings → SDE",
        "sde_bridge_net_income": "Net income (fiscal year)",
        "sde_bridge_interest": "Interest expense",
        "sde_bridge_taxes": "Income taxes",
        "sde_bridge_depreciation": "Depreciation & amortization",
        "sde_bridge_owner_comp": "Owner compensation (normalized)",
        "sde_bridge_other": "Other non-recurring items",
        "sde_bridge_total": "Seller's Discretionary Earnings (SDE)",
        "sde_bridge_footnote": (
            "SDE is reported for one full-time-working owner; with multiple active owners the second and "
            "subsequent should be reclassified as a personnel cost (manual adjustment)."
        ),
        "sde_see_normalization_link": "See the EBITDA Normalization page ↗",
        # Revenue-Multiple dedicated page
        "revenue_multiple_methodology_intro": (
            "The EV/Sales multiple is the right lens when EBITDA is not representative of the earning model: "
            "high-growth pre-profit, negative-EBITDA recovery, asset-light operators, or early seasonal/project "
            "phases. The base case is fitted on a peer set with comparable revenue band and growth profile; "
            "strong growth justifies a higher multiple, weak growth pulls the band down (PEG correction below)."
        ),
        "revenue_multiple_summary_title": "EV / Sales — summary",
        "revenue_multiple_operating_revenue_label": "Operating revenue",
        "revenue_multiple_revenue_label": "Revenue",
        "revenue_multiple_multiple_label": "EV/Sales multiple",
        "revenue_multiple_range_label": "Range",
        "revenue_multiple_metric_label": "Revenue",
        "revenue_multiple_axis_label": "EV/Sales",
        "revenue_multiple_growth_band_label": "Growth-adjusted band (PEG-style)",
        "revenue_multiple_growth_band_intro": (
            "Implied PEG = applied EV/Sales multiple ÷ revenue-CAGR (3y). Industry: <0.5 = under-priced, "
            "0.5–1.5 = fair, >1.5 = stretched."
        ),
        "revenue_multiple_growth_cagr_label": "3-year revenue CAGR",
        "revenue_multiple_implied_peg_label": "Implied PEG",
        "revenue_multiple_growth_band_stretched": "Multiple stretched relative to growth — consider DCF cross-check.",
        "revenue_multiple_assumptions_note": (
            "The revenue method uses the earnings definition and pricing inputs committed by the saved run. "
            "Market evidence, where available, is disclosed separately with its source and date. "
            "Unavailable evidence does not establish a transaction comparable set. "
            "This method result contributes to the conclusion only when admitted in the saved synthesis."
        ),
        # Generic multiple sensitivity matrix
        "multiple_sensitivity_matrix_title": "Sensitivity analysis",
        "multiple_sensitivity_caption": (
            "Enterprise value (€) at varying base metric (rows) and applied multiple (columns). "
            "The highlighted center is the base case."
        ),
        # Calibration per-method navigator
        "calib_per_method_nav_label": "Per-method dossiers in this report",
        "calib_per_method_nav_caption": "below: the consolidated calibration ledger.",
        "calib_waterfall_xref_label": "Multiple buildup",
        "calib_waterfall_xref_caption": "see the dedicated dossier above for the per-method multiple buildup and all calibration steps.",
        "exec_nav_bridge_xref_label": "Adjusted NAV",
        "exec_nav_bridge_xref_caption": "see the dedicated NAV dossier later in this report for the full book-equity-to-intrinsic-value bridge, deferred-tax latencies and off-balance corrections.",
        # Fallback Messages
        "adj_no_adjustments": "No adjustments entered in this normalization bridge.",
        "exec_no_benchmarks": "Industry benchmarks not available for this business type.",
        "exec_reference_without_benchmark_table": "Detailed benchmark provenance was not provided as a separate sector table; the reference multiple used is reflected in the multiple calibration above.",
        "ebitda_single_year_note": "Valuation based on single-year EBITDA. Multi-year data increases reliability.",
        "ebitda_no_multi_year": "Insufficient historical data for multi-year analysis.",
        "warning_zero_ebitda": "Normalized EBITDA is zero or negative. Valuation requires manual review by an advisor.",
        "warning_missing_revenue": "Revenue not available. Some market benchmarks cannot be applied.",
        # Calibration Ledger Component
        "ledger_step_column": "Step",
        "ledger_multiple_column": "Multiple",
        "ledger_impact_column": "Impact",
        "ledger_ev_column": "EV",
        "ledger_ref_column": "Ref",
        "ledger_market_consensus": "Market Consensus (P50 Median)",
        "ledger_market_consensus_desc": "Baseline from comparable transactions",
        "ledger_key_person_risk": "Key Person Risk",
        "ledger_micro_sme_discount": "Micro-SME Discount",
        "ledger_tier_label": "Tier",
        "ledger_dlom": "Illiquidity Discount (DLOM)",
        "ledger_dlom_desc": "Private companies sell slower",
        "ledger_conclusion": "Conclusion",
        "ledger_enterprise_value": "Enterprise Value (EV)",
        "ledger_multiple_label": "Multiple",
        "ledger_ev_short": "EV",
        # Panel MAJOR (D1/D2): substance/property value is not an enterprise value.
        "ledger_substance_short": "Substance value (gross / NAV)",
        "ledger_property_value_short": "Property market value (income)",
        "ledger_net_cash_short": "Net cash",
        "ledger_net_debt_short": "Net debt",
        "ledger_equity_short": "Equity",
        "ledger_equity_adjusted_parenthetical": "Adjusted NAV",
        "ledger_value_label": "Value",
        "ledger_no_steps": "Full calibration steps not available — consult advisor for detailed multiple derivation.",
        "ledger_risk_low": "diversified client base, delegated operations",
        "ledger_risk_medium": "some owner dependency, partial delegation",
        "ledger_risk_high": "owner-centric, key relationships at risk",
        "ledger_risk_label_low": "LOW",
        "ledger_risk_label_medium": "MEDIUM",
        "ledger_risk_label_high": "HIGH",
        "ledger_tier_micro": "Micro-SME",
        "ledger_tier_small": "Small",
        "ledger_tier_medium": "Medium",
        "ledger_dw_base_multiple_step3": "Base multiple (step 3)",
        "ledger_dw_initial_multiple_desc_ebitda": (
            "Initial EV/EBITDA multiple from sector benchmarks and comparable transactions."
        ),
        "ledger_dw_initial_multiple_desc_revenue": (
            "Initial EV/revenue multiple from sector benchmarks and comparable transactions."
        ),
        "ledger_dw_initial_multiple_desc_sde": (
            "Initial SDE multiple from sector benchmarks and comparable transactions."
        ),
        "ledger_dw_size_discount": "Size discount",
        "ledger_dw_liquidity_discount": "Illiquidity discount",
        "ledger_dw_revenue_trend": "Revenue trend",
        "ledger_dw_revenue_trend_desc": (
            "Adjustment linked to revenue development between fiscal years."
        ),
        "ledger_dw_revenue_trend_adjust_template": (
            "Revenue trend adjustment: {pct}% applied to the multiple."
        ),
        "ledger_dw_owner_concentration": "Owner concentration",
        "ledger_dw_owner_concentration_note": (
            "Adjustment for owner concentration / key-person risk — see the owner profile for detail."
        ),
        "ledger_dw_size_discount_note_zero": (
            "No incremental size discount at this step (partly reflected in SME calibration)."
        ),
        "ledger_dw_liquidity_discount_note_zero": (
            "No incremental illiquidity discount at this step (partly reflected in earlier steps)."
        ),
        "ledger_dw_size_discount_segment_template": "Size discount — {tier} segment{suffix}.",
        "ledger_dw_size_discount_halved_suffix_template": (
            " (reduced by {reduction}% — owner concentration already absorbs part of the size risk)"
        ),
        "ledger_dw_liquidity_discount_private_desc": (
            "Illiquidity discount (DLOM) for non-listed companies, in line with restricted-stock studies."
        ),
        "adaptive_ev_band_card_title": "Enterprise value (EV) — point estimate",
        "adaptive_ev_band_card_subtitle": (
            "The central row is the main point estimate. With no material net debt adjustment, "
            "this typically equals shareholder value for this dossier."
        ),
        # Fiscal Reference Page
        "fiscal_title": "Fiscal Reference Value",
        "fiscal_subtitle": "Belgian capital gains tax working note",
        "fiscal_scope_disclaimer": "Informational calculation reference for Belgian tax contexts; not legal, tax, or accounting advice and not a substitute for an independent valuation report.",
        "fiscal_calc_title": "Notional value calculation",
        "fiscal_normalized_ebitda_label": "EBITDA used",
        "fiscal_forfaitaire_multiple_label": "Notional multiple",
        "fiscal_ebitda_component_label": "EBITDA component ({n}× EBITDA)",
        "fiscal_book_equity_label": "Book equity",
        "fiscal_not_provided": "Not provided",
        "fiscal_reference_value_label": "Notional value",
        "fiscal_excl_equity": "(excl. equity)",
        "fiscal_ma_market_value": "M&A Market Value",
        "fiscal_indicative_share_value": "Indicative share value",
        "fiscal_reference_value_short": "Fiscal Reference Value",
        "fiscal_equity_plus_multiple": "Equity + {n}× EBITDA",
        "fiscal_legal_basis_title": "Tax reference framework",
        "fiscal_legal_intro": "For the historical value on 31/12/2025, Belgian law provides these routes:",
        "fiscal_legal_item_1": "Equity + 4 × EBITDA of the last closed fiscal year (statutory notional formula)",
        "fiscal_legal_item_2": "Value according to an existing valuation formula in a valid contract or shareholders' agreement",
        "fiscal_legal_item_3": "Value based on an arm's length market transaction with independent third parties in 2025",
        "fiscal_legal_item_4": "Value in a report completed by 31/12/2027 by a certified accountant or statutory auditor who is not the company's usual adviser",
        "fiscal_legal_paragraph": "For internal capital gains (transfer to a company in which the transferor or close family members exercise control), a separate 33% rate may apply. Confirm the conditions, including any anti-abuse rules around financing and EBITDA limits, with a tax advisor.",
        "fiscal_legal_footer": "This is a calculation note, not a legal or tax conclusion. The formula uses statutory EBITDA from the last financial year closed before 1 January 2026. It is not a market valuation. Ask a qualified professional to confirm the final tax treatment.",
        "fiscal_warning_equity_missing": "Book equity has not been provided in this calculation. The full notional value according to the statutory formula is: Equity + 4 × EBITDA. Consult your advisor or the financial statements for book equity.",
        "fiscal_warning_equity_negative": "Book equity is negative ({amount}). The result is lower than the EBITDA component alone. Ask a qualified professional whether the formula is suitable for this company.",
        "fiscal_warning_prefix": "Note:",
        # --- Defensibility extensions (EN) ---
        "fiscal_peildatum_label": "Reference date",
        "fiscal_ebitda_source_label_caption": "EBITDA source",
        "fiscal_reported_ebitda_label": "Statutory EBITDA (last closed fiscal year)",
        "fiscal_ebitda_used_label": "EBITDA applied (last closed fiscal year)",
        "fiscal_statutory_ebitda_caution_title": "EBITDA-basis checkpoint",
        "fiscal_statutory_ebitda_caution_body": "Use statutory/tax EBITDA from the last closed fiscal year here. If this amount comes from normalized or manual input, reconcile it to the annual accounts before sharing the fiscal reference value.",
        "fiscal_reported_ebitda_compare_label": "Statutory EBITDA (annual accounts)",
        "fiscal_reference_value_incomplete_label": "Notional value (incomplete)",
        "fiscal_value_incomplete_token": "Not determinable",
        "fiscal_value_incomplete_caption": "EBITDA component (excl. equity)",
        "fiscal_value_incomplete_help": "Provide book equity to compute the full notional value. Until then this report only shows the EBITDA component, not the statutory reference value.",
        "fiscal_ebitda_component_only_label": "{amount} (4× EBITDA)",
        "fiscal_internal_transfer_title": "Internal transfer flagged —",
        "fiscal_internal_transfer_body": "for transfers to a company in which the transferor or close family members exercise control, a 33% rate may apply. The acquiring company's total debt may not exceed 4× EBITDA of the operating subsidiary (anti-abuse rule). Validate with a tax advisor.",
        "fiscal_holding_role_warning": "This company is a holding. The formula uses the holding's own accounts and may miss the value of underlying companies. Do not replace it with group or operating company EBITDA. Ask a qualified professional whether an independent valuation is more suitable.",
        "fiscal_carve_out_title": "Real estate carve-out applied.",
        "fiscal_carve_out_body": "EBITDA and book equity shown have been adjusted for excluded real estate (property's book value removed from equity, estimated market rent subtracted from EBITDA). The notional value reflects this carve-out.",
        "fiscal_anchors_acknowledged_text": "The available statutory methods have been reviewed.",
        "fiscal_anchors_unacknowledged_text": "Check whether a qualifying 2025 transaction, contractual formula or professional report applies before using this value.",
        "fiscal_anchors_worksheet_title": "Ways to support the value",
        "fiscal_anchors_worksheet_intro": (
            "The formula is calculated automatically. A professional report "
            "can replace it. Use only methods supported by evidence."
        ),
        "fiscal_anchors_col_anchor": "Method",
        "fiscal_anchors_col_basis": "Statutory basis",
        "fiscal_anchors_col_value": "Value",
        "fiscal_anchor_1_name": "Statutory formula",
        "fiscal_anchor_1_basis": "Equity + 4 × EBITDA (Art. 102, § 4 WIB 92)",
        "fiscal_anchor_2_name": "Contractual formula",
        "fiscal_anchor_2_basis": "Documented formula in a shareholders' agreement as of 31/12/2025",
        "fiscal_anchor_3_name": "Qualifying 2025 transaction",
        "fiscal_anchor_3_basis": "Arm's-length transaction with independent third parties in 2025",
        "fiscal_anchor_4_name": "Professional report",
        "fiscal_anchor_4_basis": "Certified accountant or statutory auditor who is not the company's usual adviser, by 31/12/2027",
        "fiscal_anchor_not_applicable": "n/a",
        "fiscal_max_anchor_label": "Proposed acquisition value 31/12/2025",
        "fiscal_max_anchor_caption": "Highest supported method after any professional report substitution",
        "fiscal_acquisition_cost_label": "Higher proven historical cost",
        "fiscal_acquisition_cost_caption": (
            "Used only when it is higher than the supported method value"
        ),
        "fiscal_anchor_winner_chip": "Highest",
        "fiscal_tax_impact_title": "Indicative capital-gains tax impact",
        "fiscal_tax_impact_intro": (
            "On a future realisation above the acquisition value {acq}, the "
            "gross capital gain may be taxed at 10% (ordinary shares) or 33% "
            "(internal capital gain), subject to the applicable conditions."
        ),
        "fiscal_tax_impact_rate_standard": "10% — ordinary shares",
        "fiscal_tax_impact_rate_internal": "33% — internal capital gain",
        "fiscal_tax_impact_disclaimer": (
            "Indicative. The effective tax depends on the applicable regime "
            "(exemption, family transfer, anti-abuse rules). Consult a tax advisor "
            "for the final calculation."
        ),
        "fiscal_ebitda_basis_advisor_chip_statutair": "Statutory EBITDA basis",
        "fiscal_ebitda_basis_advisor_chip_genormaliseerd": (
            "Applied EBITDA basis — reconcile to statutory accounts"
        ),
        # ---- Cover-page meerwaarde-tax variant (EN) ----
        "cover_fiscal_label": "Statutory reference value",
        "cover_fiscal_note": (
            "Capital gains tax reference under Art. 102, § 4 WIB 92. Reference date {date}"
        ),
        "cover_fiscal_market_chip": "M&A market reference",
        "synthesis_title": "Valuation Synthesis",
        "synthesis_intro": "The table below shows the advisor's chosen weighting of multiple valuation methods into a single blended value.",
        "synthesis_col_method": "Method",
        "synthesis_col_value": "Calculated Value",
        "synthesis_col_weight": "Weight",
        "synthesis_col_contribution": "Weighted Contribution",
        "synthesis_total": "Blended Value",
        "synthesis_formula_label": "Formula",
        "synthesis_justification_label": "Advisor's rationale",
        "synthesis_benchmark_label": "Upswitch Benchmark",
        "synthesis_benchmark_label_weighted": "Model reconciliation",
        "synthesis_benchmark_note": "The Upswitch market approach is an independent reference not influenced by the advisor's weighting. Both are preserved for marketplace integrity.",
        "synthesis_benchmark_note_weighted": "This model reference reflects the reconciliation for the selected method mix. When advisor weights are accepted as the calculation basis, it may equal the advisor synthesis.",
        "disc_academic_review_title": "Academic cross-check — review before external distribution",
        "synthesis_subtitle": "Weighted blend based on the selected valuation methods",
        "synthesis_info_banner": (
            "The advisor selected multiple valuation methods and applied custom weights. "
            "The result is a weighted average reflecting the advisor's professional judgment."
        ),
        "synthesis_section_composition": "Composition",
        "synthesis_table_footer_total": "Total",
        "synthesis_adaptive_label": "Upswitch Adaptive",
        "synthesis_engine_reference_label": "Model reference",
        "synthesis_accountant_blend_label": "Advisor synthesis",
        "synthesis_disclaimer_title": "Note",
        "synthesis_disclaimer_body": (
            "The weighted synthesis reflects the advisor's professional judgment and may differ from "
            "the Upswitch Adaptive result. Individual method values are indicative and depend on the input data available."
        ),
        "synthesis_disclaimer_body_weighted": (
            "The weighted synthesis reflects the advisor's professional judgment. "
            "The model reference is retained separately when available; individual method values are indicative and depend on the input data available."
        ),
        "synthesis_weight_total_percent": "100%",
        "synthesis_formula_term_template": "({amount} × {pct}%)",
        "synthesis_formula_plus": " + ",
        "synthesis_formula_result_template": " = {amount}",
        "synthesis_method_ebitda_multiple": "EBITDA multiple",
        "synthesis_method_dcf": "Discounted Cash Flow (DCF)",
        "synthesis_method_sde": "SDE multiple",
        "synthesis_method_revenue": "Revenue multiple",
        "synthesis_method_arr": "SaaS market approach (EV/ARR)",
        "synthesis_method_adjusted_nav": "Adjusted NAV (Intrinsic Value)",
        "synthesis_method_fiscal_4x": "Fiscal reference value (4× EBITDA)",
        "synthesis_method_upswitch_adaptive": "Upswitch Adaptive",
        "synthesis_method_upswitch_adaptive_balance_sheet": "Upswitch Adaptive (balance sheet primary)",
        "synthesis_apv_value_basis": "APV bridge",
        "synthesis_apv_bridge_label": "PV debt tax shields",
        "synthesis_apv_bridge_note": "DCF includes the separately discounted APV tax shields from the customer template.",
        "synthesis_apv_bridge_generic_note": "DCF includes separately discounted APV tax shields from explicit inputs.",
        "synthesis_net_engine_value_basis": "Net model value",
        "synthesis_net_engine_note": "This contribution uses the calibrated net multiples value after standard risk and liquidity adjustments.",
        "method_override_title": "Valuation based on manual method selection",
        "method_override_subtitle_screen": "The advisor manually selected a valuation method.",
        "method_override_subtitle_pdf": "The advisor manually selected a valuation method instead of the Upswitch Adaptive result.",
        "method_override_info_banner": "This report shows the valuation method chosen by the advisor. The Upswitch Adaptive value is shown for comparison.",
        "method_override_selected_method_heading": "Selected method",
        "method_override_col_method": "Method",
        "method_override_col_manual_value": "Manual value",
        "method_override_row_adaptive_reference": "Upswitch Adaptive value",
        "method_override_adaptive_subcaption": "Model-selected method",
        "method_override_label_manual_choice": "Manual selection",
        "method_override_delta_label": "Delta vs Upswitch Adaptive",
        "method_override_delta_premium": "+{percent}% above adaptive reference",
        "method_override_delta_discount": "−{percent}% below adaptive reference",
        "method_override_delta_match": "within 0.5% of the adaptive reference",
        "cover_manual_override_badge": "Manual method override",
        "method_override_section_rationale": "Rationale",
        "method_override_reason_label": "Reason:",
        "method_override_note_label": "Note:",
        "method_override_recorded_on": "Recorded on:",
        "method_override_disclaimer_screen": (
            "The manual selection reflects the advisor's professional judgment and may differ from "
            "the Upswitch Adaptive result."
        ),
        "method_override_disclaimer_pdf": (
            "The manual selection reflects the advisor's professional judgment and may differ from "
            "the Upswitch Adaptive result. Both values are calculated from the same normalized inputs."
        ),
        "method_override_reason_fiscal_compliance": "Fiscal compliance",
        "method_override_reason_asset_heavy_business": "Asset-heavy business",
        "method_override_reason_internal_transfer": "Internal transfer",
        "method_override_reason_conservative_anchor": "Conservative anchor",
        "method_override_reason_client_preference": "Client preference",
        "method_override_reason_regulatory_requirement": "Regulatory requirement",
        "method_override_reason_other": "Other",
        "dcf_flat_projection_note": (
            "The projections use a constant growth rate and a constant EBITDA margin "
            "across the entire projection period. For a maturing business, it is common "
            "for revenue growth to taper gradually while profit margins improve through economies of scale."
        ),
        "dcf_historical_fcf_missing_fields_prefix": "Missing:",
        "dcf_historical_fcf_readiness_heading": "Historical FCF readiness",
        "nwc_normalization_title": "Working capital normalization",
        "nwc_normalization_explanation_fallback": (
            "Historical working capital ratios were compared with the latest balance sheet to identify "
            "surplus or deficit working capital."
        ),
        "nwc_label_target_nwc": "Target NWC",
        "nwc_label_actual_nwc": "Actual NWC",
        "nwc_label_bridge_impact": "Bridge impact",
        "nwc_label_years_analyzed": "Years analyzed",
        "market_provenance_title": "Market data provenance",
        "market_label_risk_free_rate": "Risk-free rate",
        "market_label_source": "Source",
        "market_label_manual_override": "Override",
        "market_label_applied": "Applied",
        "market_label_equity_risk_premium": "Equity risk premium",
        "market_label_erp_source": "ERP source",
        "market_label_gdp_growth": "GDP growth",
        "market_label_as_of": "As of",
        "anomaly_detection_title": "Statistical anomaly detection",
        "anomaly_label_account": "Account",
        "anomaly_label_year": "Year",
        "anomaly_label_z_score": "Z-score",
        "anomaly_label_confidence": "Confidence",
        "anomaly_label_suggested_normalization": "Suggested normalization",
        "anomaly_scan_payload_missing": (
            "The anomaly scan was available in the valuation workflow, but the final report payload did "
            "not contain a usable anomaly flag."
        ),
        "anomaly_label_severity": "Severity",
        "anomaly_severity_critical": "Critical",
        "anomaly_severity_severe": "Severe",
        "anomaly_severity_moderate": "Moderate",
        "anomaly_severity_low": "Low",
        "dcf_sensitivity_matrix_caption_terminal": (
            "Enterprise value, displayed compactly, at variations of WACC and terminal growth rate."
        ),
        "dcf_sensitivity_matrix_caption_exit_multiple": (
            "Enterprise value, displayed compactly, at variations of WACC and exit multiple."
        ),
        "saas_appendix_spread_points_suffix": "pts",
        "sde_component_owner_salary_label": "Owner salary adjustment",
        "sde_component_total_label": "SDE Total",
        "data_inputs_normalizations_label": "Normalizations",
        "data_inputs_comparable_transactions_label": "Comparable transactions",
        "data_quality_band_high": "High",
        "data_quality_band_medium": "Medium",
        "data_quality_band_low": "Low",
        "data_quality_band_critical": "Critical",
        "report_benchmark_source_neutral": "Industry benchmarks",
        "report_benchmark_source_request_payload": "Request payload",
        "report_benchmark_source_valuation_response": "Valuation response",
        "report_registry_short_kvk": "KVK",
        "report_registry_short_kbo": "KBO",
        "report_registration_number_label_kvk": "KVK number",
        "report_registration_number_label_kbo": "KBO number",
        "report_company_name_unknown": "Unknown company",
        "report_multiple_label_prefix_hybrid": "Multiples component",
        "report_multiple_suffix_ev_revenue": "EV/Revenue",
        "report_multiple_suffix_ev_ebitda": "EV/EBITDA",
        "report_benchmark_median_ev_revenue": "Market median (EV/Revenue)",
        "report_benchmark_median_ev_ebitda": "Market median (EV/EBITDA)",
        "methodology_narrative_multiples": (
            "The enterprise value has been calculated using the market approach "
            "based on comparable transaction multiples ({metric})."
        ),
        "methodology_narrative_asset": (
            "The valuation is asset-led: book equity is the starting point for the "
            "NAV approach, with room for documented balance-sheet adjustments and "
            "deferred tax effects."
        ),
        "methodology_narrative_yield": (
            "The valuation is real-estate-led: sustainable net rental income is "
            "capitalised using a market-conform cap rate, with a NAV floor where "
            "book value is higher."
        ),
        "methodology_narrative_dcf_addon": (
            "Additionally, a Discounted Cash Flow (DCF) analysis has been performed "
            "to validate the intrinsic value."
        ),
        "methodology_narrative_dcf_weighted": (
            "The Discounted Cash Flow (DCF) analysis is included as a separate "
            "weighted component in the valuation synthesis."
        ),
        "methodology_narrative_dcf_primary": (
            "The enterprise value has been calculated using the income approach "
            "(Discounted Cash Flow), based on the present value of projected "
            "free cash flows."
        ),
        "methodology_narrative_normalization": (
            "Reported EBITDA has been normalized for non-recurring "
            "and owner-specific costs to determine sustainable earnings capacity."
        ),
        "methodology_narrative_owner_dependency": (
            "Risk factors such as owner dependency have been quantified "
            "and reflected in the applied multiple."
        ),
        "methodology_narrative_fallback": (
            "The valuation is based on the market approach using {metric} multiples."
        ),
        "owner_profiling_section_title": "Owner Dependency",
        "owner_profiling_section_subtitle": (
            "Quantitative transferability assessment based on the " "9-question owner profile."
        ),
        "owner_profiling_score_label": "Transferability score",
        "owner_profiling_transferability_label": "Transferability index",
        "owner_profiling_risk_label": "Risk level",
        "owner_profiling_adjustment_label": "Applied valuation adjustment",
        "owner_profiling_raw_adjustment_label": "Pre-cap adjustment",
        "owner_profiling_cap_applied_note": "{cap_pct}% cap applied",
        "owner_profiling_key_risks_title": "Key transition risks",
        "owner_profiling_recommendations_title": "Actions that lift transferability",
        "owner_profiling_explanation_title": "Assessment summary",
        "owner_profiling_disclaimer": (
            "Owner profiling is a quantitative model of owner dependency. "
            "Recommendations are illustrative — execution timing varies "
            "by sector and context."
        ),
        "owner_profiling_risk_minimal": "Minimal",
        "owner_profiling_risk_low": "Low",
        "owner_profiling_risk_medium": "Medium",
        "owner_profiling_risk_high": "High",
        "owner_profiling_risk_critical": "Critical",
        "owner_profiling_skipped_title": "Owner profiling skipped",
        "owner_profiling_skipped_body": (
            "The 9-question profile was not completed. The valuation "
            "shows the indicative range without an owner-dependency "
            "adjustment. Complete the profile to refine this number."
        ),
        "owner_profiling_skipped_cta_label": "Send the 9-question questionnaire",
        "owner_profiling_skipped_cta_action": "send_owner_profiling_invite",
        "owner_profiling_skipped_cta_subtext": (
            "Unlocks the behavioural owner-dependency discount "
            "(Damodaran 12-factor) on the equity bridge and makes the "
            "dossier defensible for M&A due diligence."
        ),
        "owner_risk_ledger_title": "Owner Risk Reconciliation",
        "owner_risk_ledger_subtitle": (
            "A single audit trail of every owner-related discount — "
            "structural (on the multiple) and behavioural (on the "
            "equity bridge)."
        ),
        "owner_risk_ledger_side_multiple": "On the multiple",
        "owner_risk_ledger_side_equity": "On the equity bridge",
        "owner_risk_ledger_item_label": "Item",
        "owner_risk_ledger_total_label": "Total owner-related impact",
        "owner_risk_ledger_audit_quality_label": "Audit quality",
        "owner_risk_ledger_audit_defensible": "Defensible (M&A-grade)",
        "owner_risk_ledger_audit_heuristic": "Heuristic only",
        "owner_risk_ledger_heuristic_marker_title": "Heuristic (no profile)",
        "owner_risk_ledger_profile_marker_title": "Profile-derived",
        "owner_risk_ledger_methodology_title": "Methodology",
        "owner_risk_ledger_no_double_count_title": "No double-count",
        "owner_risk_ledger_basis_label": "Basis",
        "owner_risk_ledger_unverified_input": "Unverified input",
    }
