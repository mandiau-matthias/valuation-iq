"""Transformer and accountant core report copy."""

from __future__ import annotations


def build_english_accountant_core_translations() -> dict[str, object]:
    return {
        # Transformer strings — English overrides
        "transformer_method_label_market_multiples": "Market Multiples",
        "transformer_method_label_dcf": "Discounted Cash Flow (DCF)",
        "transformer_method_label_ebitda_multiple": "EV/EBITDA Multiple",
        "transformer_method_label_revenue_multiple": "EV/Revenue Multiple",
        "transformer_method_label_asset_based": "Adjusted Net Asset Value",
        "transformer_method_label_hybrid": "Hybrid Valuation",
        "transformer_methodology_desc_multiples": "Market multiples valuation",
        "transformer_methodology_desc_dcf": "Discounted cash flow valuation",
        "transformer_methodology_desc_hybrid": (
            "Hybrid valuation using {multiples_pct}% multiples and {dcf_pct}% DCF"
        ),
        "transformer_methodology_desc_default": "Valuation using market multiples methodology",
        "transformer_primary_ebitda_with_value": (
            "EV/EBITDA Multiple selected based on positive EBITDA of €{value}"
        ),
        "transformer_primary_ebitda_no_value": (
            "EV/EBITDA Multiple selected based on positive EBITDA"
        ),
        "transformer_primary_revenue": (
            "EV/Revenue Multiple selected due to negative or zero EBITDA"
        ),
        "transformer_primary_dcf": ("DCF method selected based on available financial projections"),
        "transformer_primary_method_default": (
            "{method} selected based on available financial metrics"
        ),
        "transformer_sme_calibration_notice": (
            "SME multiple calibration applied to adjust for company size"
        ),
        "transformer_range_methodology_dispersion": (
            "Valuation range based on P25/P50/P75 percentiles from comparable companies"
        ),
        "transformer_range_methodology_confidence": (
            "Valuation range based on confidence-adjusted spread around midpoint "
            "(±{spread}% range)"
        ),
        "transformer_range_methodology_dispersion_short": (
            "Valuation range based on comparable company analysis"
        ),
        "transformer_range_methodology_confidence_short": (
            "Valuation range based on confidence-adjusted spread"
        ),
        "transformer_range_methodology_dispersion_note": (
            "Range reflects market comparables dispersion"
        ),
        "transformer_range_methodology_confidence_note": (
            "Range reflects confidence-based uncertainty"
        ),
        "transformer_range_methodology_percentile_short": (
            "Range based on P25/P50/P75 percentiles from comparables"
        ),
        "transformer_range_methodology_confidence_only": (
            "Range based on confidence-adjusted spread"
        ),
        "transformer_company_overview_template": (
            "{company} is a {industry} operating in the {country} market."
        ),
        "transformer_company_overview_industry_default": "business",
        "transformer_company_overview_country_default": "local",
        "transformer_fin_highlights_range": (
            "Valuation range: €{low} - €{high} (midpoint: €{mid})"
        ),
        "transformer_fin_highlights_range_unavailable": "Valuation range: Not available",
        "transformer_fin_highlights_ebitda_suffix": ". Current year EBITDA: €{value}",
        "transformer_fin_highlights_revenue_suffix": ". Current year revenue: €{value}",
        "transformer_waterfall_step_default": "{step_name} adjustment applied",
        "transformer_comparables_count_note": ("Analysis based on {count} comparable companies"),
        "transformer_info_source_financial_desc": (
            "Current year financial data for {company} including revenue, EBITDA, "
            "and other key metrics"
        ),
        "transformer_info_source_current_year_statements": (
            "Current year financial statements as of {date}"
        ),
        "methodology_notes_dcf": (
            "Discounted Cash Flow methodology projects future cash flows and discounts "
            "them to present value."
        ),
        "methodology_notes_multiples": (
            "Market multiples methodology uses comparable company valuations and "
            "industry benchmarks."
        ),
        "methodology_notes_asset_based": (
            "Asset-based methodology values the company based on net asset value."
        ),
        "methodology_notes_market": (
            "Market approach uses recent transaction data and market comparables."
        ),
        "methodology_notes_income": (
            "Income approach capitalizes normalized earnings at an appropriate rate."
        ),
        "methodology_notes_cost": (
            "Cost approach values the business based on the cost to recreate similar " "operations."
        ),
        "methodology_notes_hybrid": (
            "Hybrid methodology combines multiple valuation approaches for "
            "comprehensive analysis."
        ),
        "methodology_notes_default": "Professional valuation methodology applied.",
        "transformer_confidence_low_industry": "Low (industry averages)",
        "transformer_confidence_medium_industry": "Medium (industry averages)",
        "transformer_confidence_medium_high_industry": "Medium-High (industry analysis)",
        "report_validation_missing_recommended": "Missing recommended: {field}",
        "report_validation_required_zero": "{field} (zero value — pipeline produced no result)",
        "report_validation_registry_unavailable": "{registry} data not available ({field})",
        "report_validation_no_comparables": "No comparables found",
        "report_validation_no_benchmark": "No industry benchmark multiples",
        "report_validation_no_dcf_provenance": (
            "Missing resolved market-data provenance for DCF or hybrid report output"
        ),
        # Accountant view (PDF) — English overrides
        "accountant_cover_report_type": "Business Valuation Report",
        "accountant_cover_business_default": "Strategic Valuation Assessment",
        "accountant_cover_disclaimer_label": "Disclaimer:",
        "accountant_cover_disclaimer_text": (
            "This report provides an indicative valuation based on the financial data provided. "
            "In accordance with Belgian and European financial reporting standards, this document "
            "serves as a strategic tool for internal review and does not constitute a statutory "
            'audit ("controle legal"), a formal fairness opinion, or binding financial advice '
            "under the scope of certified auditor regulations unless explicitly signed and ratified "
            'by a certified auditor ("reviseur d\'entreprises" / "bedrijfsrevisor") or chartered '
            'accountant ("expert-comptable" / "accountant"). The valuation methods applied '
            "follow standard IVS and AICPA frameworks but should not be the sole basis for "
            "investment or divestment decisions. Upswitch Valuation Services accepts no liability "
            "for decisions based solely on this strategic report."
        ),
        "accountant_cover_strictly_confidential": "Strictly Private & Confidential",
        "accountant_cover_generated_on": "Generated on",
        "accountant_cover_date_pending": "Date Pending",
        "accountant_cover_reference_id": "Reference ID",
        "accountant_toc_title": "Contents",
        "accountant_toc_section_1": "Executive Summary",
        "accountant_toc_section_1_1": "1.1: Strategic Assessment & Optimization",
        "accountant_toc_section_2": "Economic Reality (Normalization)",
        "accountant_toc_section_3": "Valuation Chaining (Waterfall)",
        "accountant_toc_section_4": "Operational Resilience & Risk",
        "accountant_toc_section_4_1": "4.1: Business Vitality Dashboard",
        "accountant_toc_section_4_2": "4.2: Data Quality & Compliance",
        "accountant_toc_section_5": "Strategic Value Roadmap",
        "accountant_toc_section_6": "Technical Appendices",
        "accountant_toc_appendix_a": "A: Financial Performance Detail",
        "accountant_toc_appendix_b": "B: Description of Assignment",
        "accountant_toc_appendix_d": "D: Methodology Matrix",
        "accountant_toc_appendix_f": "F: Standards & Conditions",
        "accountant_toc_appendix_c": "Appendix C: Information Sources & Data Reliability",
        "accountant_toc_appendix_e": "Appendix E: Algorithmic Defensibility",
        "accountant_section_executive_summary": "Section 1 — Executive Summary",
        "accountant_exec_intro": (
            "Upswitch Valuation Services was engaged to estimate the <strong>Fair Market Value (FMV)</strong> "
            'of {company_name} ("the Company") as of {valuation_date}. '
            "This valuation provides an independent, objective assessment of enterprise value for "
            "strategic planning and internal decision-making purposes."
        ),
        "accountant_exec_box_title": "Executive Summary",
        "accountant_exec_business_value_label": "Your Business Value",
        "accountant_exec_range_label": "Range",
        "accountant_exec_valuation_basis_label": "Valuation Basis",
        "accountant_exec_basis_explanation": (
            "Adjusted for company size, market conditions, and business-specific risks"
        ),
        "accountant_exec_plain_language_label": "In Plain Language:",
        "accountant_exec_plain_language_text": (
            "Based on market transaction data from similar businesses and standard valuation methods, "
            "{company_name} is worth approximately {value}. This assessment follows professional standards "
            "(USPAP, IVS) and can be used for strategic planning, sale negotiations, or internal "
            "decision-making."
        ),
        "accountant_exec_range_chart_title": "Valuation Range Visualization",
        "accountant_exec_estimated_fmv_label": "Estimated Fair Market Value",
        "accountant_exec_suggested_listing_price_label": "Suggested Listing Price:",
        "accountant_exec_strategic_buffer": "Strategic buffer included",
        "accountant_exec_implied_multiple_label": "Implied Multiple",
        "accountant_exec_fair_market_value_label": "Fair Market Value",
        "accountant_section_operational_resilience": "Section 4 — Operational Resilience & Risk Assessment",
        "accountant_fa_intro": (
            "This section evaluates the Company's structural health and risk profile through systematic "
            "analysis of historical performance, financial stability, and operational metrics. Our "
            "assessment framework adheres to <strong>IVS 105</strong> and <strong>USPAP Standard 9</strong> "
            "to quantify operational risks that influence valuation multiples, providing buyers with a "
            "defensible assessment of sustainable earning power and enterprise-level risk factors."
        ),
        "accountant_fa_market_context_label": "Market Context:",
        "accountant_fa_market_context_text": (
            "Empirical research indicates that institutional buyers systematically apply 0.3x-0.7x "
            "multiple discounts for companies exhibiting performance volatility or weak financial "
            "health. This section identifies specific risk factors that due diligence teams prioritize "
            "when assessing acquisition targets."
        ),
        "accountant_fa_critical_alerts_title": "Critical Risk Alerts",
        "accountant_fa_historical_performance_title": "4.1 Historical Performance Summary",
        "accountant_fa_historical_intro": (
            "Historical performance analysis establishes the empirical foundation for valuation by "
            "quantifying growth trends and profitability stability. Compound Annual Growth Rate (CAGR) "
            "measures sustainable expansion velocity, while EBITDA margin assesses operational efficiency "
            "and pricing power. These metrics serve as leading indicators for future cash flow "
            "predictability and enterprise risk."
        ),
        "accountant_fa_valuation_impact_label": "Valuation Impact:",
        "accountant_fa_valuation_impact_text": (
            "Consistent 15-25% CAGR supports premium multiples (1.2x baseline), while stable 10-15% "
            "EBITDA margins indicate sustainable profitability. Deviations trigger risk adjustments "
            "per <strong>AICPA BVS-VII</strong> frameworks."
        ),
        "accountant_fa_data_limitation_title": "Data Limitation Notice",
        "accountant_fa_data_limitation_text": (
            "Analysis is based on {years} year(s) of historical data. Standard valuation practice "
            "recommends 3-5 years for trend analysis."
        ),
        "accountant_fa_revenue_cagr_label": "Revenue CAGR",
        "accountant_fa_revenue_cagr_caption": "Annualized growth rate.",
        "accountant_fa_avg_ebitda_margin_label": "Avg. EBITDA Margin",
        "accountant_fa_avg_ebitda_margin_caption": "Operational efficiency.",
        "accountant_fa_performance_visualization_title": "Performance Visualization",
        "accountant_section_valuation_waterfall": "Section 3 — Valuation Waterfall (Multiple Calibration)",
        "accountant_wf_intro": (
            "This audit trail demonstrates the <strong>Multiple-First Methodology</strong> used to "
            "derive the intrinsic value. We calibrate the market multiple sequentially to account for "
            "company-specific risk factors (alpha), ensuring a defensible and transparent transition "
            "from market benchmarks to fair market value."
        ),
        "accountant_wf_bridge_title": "The Mathematical Bridge",
        "accountant_wf_bridge_text": (
            "In compliance with <strong>IVS 105</strong> and <strong>USPAP Standard 10</strong>, this "
            "schedule provides the mathematical derivation of value. By adjusting the multiple rather "
            "than EBITDA, we isolate risk factors like size effect and illiquidity as distinct variables."
        ),
        "accountant_wf_col_component": "Component / Step",
        "accountant_wf_col_equity_value": "Equity Value",
        "accountant_wf_col_multiple": "Multiple",
        "accountant_wf_col_ref": "Ref",
        "accountant_wf_col_methodology": "Methodology",
        "accountant_wf_section_normalization_bridge": "Normalization Bridge",
        "accountant_wf_reported_earnings": "Reported Earnings (EBITDA)",
        "accountant_wf_as_documented": "As documented in financial records",
        "accountant_wf_normalized_ebitda": "Normalized EBITDA",
        "accountant_wf_representative_earnings": "Representative earnings",
        "accountant_wf_margin_suffix": "Margin",
        "accountant_wf_section_calibration": "Valuation Calibration (Alpha Factors)",
        "accountant_wf_section_structural": "Structural Adjustments",
        "accountant_wf_step_market_consensus": "Market Consensus (P50 Median)",
        "accountant_wf_step_market_consensus_reason": (
            "Unadjusted trading multiple derived from transaction data."
        ),
        "accountant_wf_step_sme_calibration": "SME Market Calibration",
        "accountant_wf_step_sme_calibration_reason": (
            "Calibration for small firm risk and lack of institutional liquidity."
        ),
        "accountant_wf_step_quality": "Earnings Quality calibration",
        "accountant_wf_step_quality_reason": (
            "Multiple adjusted for earnings volatility and normalization quality."
        ),
        "accountant_wf_step_owner": "Unsystematic Risk: Key Person",
        "accountant_wf_step_owner_reason": "Adjustment for dependency on owner-operator.",
        "accountant_wf_step_revenue_trend": "Revenue Trend Adjustment",
        "accountant_wf_step_revenue_trend_reason": (
            "Discount for declining revenue with correlation-aware calibration. Methodology accounts "
            "for size × revenue trend interaction to prevent over-discounting (r ≈ 0.40)."
        ),
        "accountant_wf_step_size": "Size Effect Premium",
        "accountant_wf_step_size_reason": "Premium for smaller market capitalization risks (Fama-French).",
        "accountant_wf_step_liquidity": "Illiquidity Discount (DLOM)",
        "accountant_wf_step_liquidity_reason": "Adjustment for lack of immediate marketability.",
        "accountant_wf_conclusion_label": "Conclusion",
        "accountant_wf_final_synthesized": "Final synthesized value",
        "accountant_wf_impact_label": "Impact",
        "accountant_wf_risk_discount": "Risk Discount",
        "accountant_wf_strength_premium": "Strength Premium",
        "accountant_wf_earnings_label": "Earnings",
        "accountant_wf_final_multiple_label": "Final Multiple",
        "accountant_wf_intrinsic_value_label": "Intrinsic Value",
        "accountant_wf_source_registry_title": "Source Registry & Academic Citations",
        "accountant_wf_footnote_market_consensus_label": "Market Consensus:",
        "accountant_wf_footnote_market_consensus_body": (
            "VFB Belgium (2024), Vlerick Business School (2023), Trugman (2017) AICPA."
        ),
        "accountant_wf_footnote_unsystematic_label": "Unsystematic Risk:",
        "accountant_wf_footnote_unsystematic_body": (
            "Damodaran (2012) Key Person Risk, PwC (2024) Valuation Guidelines."
        ),
        "accountant_wf_footnote_size_label": "Size Effect:",
        "accountant_wf_footnote_size_body": (
            "Ibbotson SBBI (2024), Duff & Phelps (2024), Fama & French (1992). "
            "Updated 2025-12-20 for enhanced academic defensibility."
        ),
        "accountant_wf_footnote_illiquidity_label": "Illiquidity:",
        "accountant_wf_footnote_illiquidity_body": (
            "Koeplin (2000), Officer (2007) Journal of Financial Economics."
        ),
        "accountant_wf_footnote_normalization_label": "Normalization:",
        "accountant_wf_footnote_normalization_body": (
            "Trugman (2017) p. 287, Pratt & Niculita (2008) Valuing a Business."
        ),
        "accountant_wf_footnote_revenue_trend_label": "Revenue Trend (Correlation-Aware):",
        "accountant_wf_footnote_revenue_trend_body": (
            "Damodaran (2012) distressed asset adjustments, McKinsey (2015) Ch. 11 growth/decline "
            "impact on multiples. Correlation-aware calibration accounts for size × revenue trend "
            "interaction (r ≈ 0.40) per McKinsey (2015) guidance on correlated risk adjustments. "
            "Prevents over-discounting when multiple risk factors present. Enhanced 2025-12-20."
        ),
        "accountant_wf_methodology_note_label": "Methodology Note:",
        "accountant_wf_methodology_note_body": (
            "This report follows the Multiple-First derivation per AICPA SSVS No. 1 and IVS 105. "
            "Multiples are calibrated sequentially to isolate alpha risk factors from systematic "
            "market risk. Enhanced 2025-12-20: Added revenue trend adjustment and increased size "
            "discount for improved academic defensibility."
        ),
        "accountant_wf_no_schedule_title": "Detailed Schedule Not Available",
        "accountant_wf_no_schedule_text": "Please ensure all calculation steps completed successfully.",
        "accountant_section_appendices": "Section 6 — Technical Appendices & Supporting Schedules",
        "accountant_app_a_title": "Appendix A — Historical Financial Performance Detail",
        "accountant_app_a_caption": "Historical Income Statement Detail (€ thousands)",
        "accountant_app_a_metric": "Metric",
        "accountant_app_a_revenue": "Revenue",
        "accountant_app_a_ebitda": "EBITDA",
        "accountant_app_a_ebitda_margin": "EBITDA Margin %",
        "accountant_app_a_net_income": "Net Income",
        "accountant_app_a_no_data": "Detailed financial history not provided for this assessment.",
        "accountant_app_b_title": "Appendix B: Description of Assignment",
        "accountant_app_b_purpose_label": "Purpose:",
        "accountant_app_b_scope_label": "Scope:",
        "accountant_app_b_standard_of_value": "Standard of Value",
        "accountant_app_b_premise_of_value": "Premise of Value",
        "accountant_app_b_intended_users_label": "Intended Users:",
        "accountant_app_d_title": "Appendix D: Methodology Matrix",
        "accountant_app_d_col_criteria": "Criteria",
        "accountant_app_d_col_assessment": "Assessment",
        "accountant_app_d_col_impact": "Impact",
        "accountant_app_d_cash_flow_visibility": "Cash Flow Visibility",
        "accountant_app_d_cash_flow_assessment": "Low/Moderate",
        "accountant_app_d_cash_flow_impact": "Income approach weighted at {weight}",
        "accountant_app_d_market_comparability": "Market Comparability",
        "accountant_app_d_market_assessment": "High",
        "accountant_app_d_market_impact": "Market approach weighted at {weight}",
        "accountant_app_d_synthesis_title": "Synthesis & Weighting Rationale",
        "accountant_app_d_synthesis_default": (
            "The valuation synthesis prioritizes the Market Approach (Multiples) to ensure alignment "
            "with current SME transaction realities and to minimize the speculative forecasting risks "
            "inherent in the Income Approach for businesses of this scale. In accordance with "
            "fiduciary-grade requirements, the Income Approach (DCF) is utilized as a secondary "
            "verification or weighted accordingly based on the stability and auditability of "
            "projected cash flows (Koller et al., 2020; Hitchner, 2017)."
        ),
        "accountant_app_f_title": "Appendix F: Standards & Conditions",
        "accountant_app_f_callout": (
            "This valuation is performed in accordance with <strong>AICPA BVS-VII</strong> "
            "(Comprehensive Valuations), <strong>ASA BVS-III</strong> (Quality of Earnings), and "
            "<strong>IVS 105/200</strong> (Valuation Approaches)."
        ),
        "accountant_app_f_key_assumptions_title": "Key Assumptions",
        "accountant_app_f_key_assumption_1": "Financial records provided are accurate and complete.",
        "accountant_app_f_key_assumption_2": (
            "Management is competent and intends to continue operations."
        ),
        "accountant_app_f_key_assumption_3": "No significant undisclosed liabilities or litigation.",
        "accountant_app_f_limiting_conditions_title": "Limiting Conditions",
        "accountant_app_f_limiting_condition_1": "Valuation is valid only as of the effective date.",
        "accountant_app_f_limiting_condition_2": "No independent audit of financial data was performed.",
        "accountant_app_f_limiting_condition_3": "Future events may impact value materially.",
        "accountant_app_compliance_title": "Professional Disclaimer & Compliance",
        "accountant_app_methodology_title": "Data-Driven Valuation Methodology",
        "accountant_app_calculation_integrity_label": "Calculation Integrity:",
        "accountant_app_calculation_integrity_text": (
            "This valuation report presents calculated values derived exclusively from financial data "
            "and empirically validated market multiples. All figures are computed using academically "
            "recognized methodologies:"
        ),
        "accountant_app_method_uspap": "Business Appraisal Development & Reporting",
        "accountant_app_method_ivs": (
            "Valuation Approaches and Methods (International Valuation Standards)"
        ),
        "accountant_app_method_aicpa": "Statement on Standards for Valuation Services",
        "accountant_app_method_damodaran": "Investment Valuation: Tools and Techniques",
        "accountant_app_methodology_footer": (
            "Value drivers and risk factors shown in this report are extracted from actual financial "
            "data analysis. Strategic recommendations have been intentionally excluded to ensure "
            "accuracy — all content is data-derived rather than advisory in nature."
        ),
        # Phase 2: EBITDA Normalization
        "accountant_ebitda_section_title": "Section 2 — Economic Reality (EBITDA Normalization)",
        "accountant_ebitda_ivs_badge": "IVS 105 Compliant",
        "accountant_ebitda_intro": (
            "SME financial statements are frequently structured for tax optimization rather than "
            "accurate economic representation. This section applies the "
            "<strong>EBITDA Normalization Bridge</strong> to reconstruct sustainable earning power "
            "by systematically reversing non-recurring items, owner-specific benefits, and "
            "tax-motivated accounting treatments that obscure true operational performance."
        ),
        "accountant_ebitda_primitive_title": "Primitive 1: Economic Reality Framework",
        "accountant_ebitda_primitive_body": (
            "<strong>Methodological Foundation:</strong> We reconstruct the Company's sustainable "
            "earning power through systematic reversal of discretionary expenses, non-recurring "
            "items, and tax-optimized accounting treatments. This transformation establishes the "
            '"normalized baseline" for valuation, ensuring all subsequent risk adjustments are '
            "applied to a defensible, market-representative EBITDA foundation in accordance with "
            "<strong>ASA BVS-III</strong> standards."
        ),
        "accountant_ebitda_schedule_title": "EBITDA Normalization Schedule",
        "accountant_ebitda_bridge_caption_user": "EBITDA Bridge (Reported to Normalized) — Year",
        "accountant_ebitda_col_item": "Normalization Item",
        "accountant_ebitda_col_adjustment": "Adjustment",
        "accountant_ebitda_col_rationale": "Rationale",
        "accountant_ebitda_reported_ebitda_year": "Reported EBITDA",
        "accountant_ebitda_baseline_from_records": "Baseline from financial records",
        "accountant_ebitda_user_defined_adjustment": "User-defined adjustment",
        "accountant_ebitda_custom_adjustment": "Custom adjustment",
        "accountant_ebitda_no_adjustments": "No adjustments applied",
        "accountant_ebitda_used_as_reported": "EBITDA used as reported",
        "accountant_ebitda_normalized_year": "Normalized EBITDA",
        "accountant_ebitda_used_in_valuation": "Used in Valuation",
        "accountant_ebitda_transformation_impact": "Transformation Impact",
        "accountant_ebitda_net_adjustment_caption": "Net adjustment to reported earnings.",
        "accountant_ebitda_adjustment_count": "Adjustment Count",
        "accountant_ebitda_categories_adjusted_year": "Categories adjusted for this year.",
        "accountant_ebitda_years_normalized": "Years Normalized",
        "accountant_ebitda_total_years_caption": "Total years with EBITDA adjustments.",
        "accountant_ebitda_documentation_quality": "Documentation Quality",
        "accountant_ebitda_quality_enhanced": "Enhanced",
        "accountant_ebitda_quality_standard": "Standard",
        "accountant_ebitda_includes_custom": "Includes custom adjustments.",
        "accountant_ebitda_based_on_standard": "Based on standard categories.",
        "accountant_ebitda_weighted_callout_title": "Weighted EBITDA Methodology",
        "accountant_ebitda_weighted_callout_body": (
            "<strong>McKinsey Academic Standard:</strong> This valuation uses <strong>weighted "
            "average EBITDA</strong> from historical years (not single-year current EBITDA) to "
            "smooth earnings volatility and capture sustainable earning power. The current year "
            "({year}) EBITDA of <strong>{current_ebitda}</strong> has been weighted with "
            "historical performance per McKinsey Valuation (2015, Chapter 7)."
        ),
        "accountant_ebitda_weighted_rationale_label": "Rationale:",
        "accountant_ebitda_weighted_default_rationale": (
            "Weighted averaging reduces impact of year-to-year volatility and provides more "
            "stable baseline for valuation."
        ),
        "accountant_ebitda_bridge_caption_weighted": "EBITDA Bridge (Weighted to Normalized)",
        "accountant_ebitda_bridge_caption_reported": "EBITDA Bridge (Reported to Normalized)",
        "accountant_ebitda_current_year_ebitda": "Current Year EBITDA",
        "accountant_ebitda_single_year_not_used": "Single year performance (not used)",
        "accountant_ebitda_weighted_historical": "Weighted Historical EBITDA",
        "accountant_ebitda_multi_year_weighted": "Multi-year weighted average baseline",
        "accountant_ebitda_owner_compensation": "Owner Compensation",
        "accountant_ebitda_market_replacement_rate": "At market replacement rate",
        "accountant_ebitda_discretionary_expenses": "Discretionary Expenses",
        "accountant_ebitda_no_non_operating": "No non-operating items identified",
        "accountant_ebitda_normalized_label": "Normalized EBITDA",
        "accountant_ebitda_representative_earning": "Representative Earning Power",
        "accountant_ebitda_avg_adjustment": "Average adjustment across {count} years.",
        "accountant_ebitda_net_adjustment": "Net adjustment to reported earnings.",
        "accountant_ebitda_bridge_reliability": "Bridge Reliability",
        "accountant_ebitda_quality_high": "High",
        "accountant_ebitda_based_on_documentation": "Based on documentation quality.",
        "accountant_ebitda_quality_assessment_title": "Earnings Quality Assessment",
        "accountant_ebitda_quality_assessment_intro": (
            "Sustainable valuation requires stable margins. We analyze historical margin volatility "
            "to assess the reliability of normalized earnings as a predictor of future performance."
        ),
        "accountant_ebitda_metric_label": "Metric",
        "accountant_ebitda_value_label": "Value",
        "accountant_ebitda_assessment_label": "Assessment",
        "accountant_ebitda_current_margin": "Current EBITDA Margin",
        "accountant_ebitda_current_margin_caption": "Latest reported performance",
        "accountant_ebitda_historical_mean": "Historical Mean Margin",
        "accountant_ebitda_historical_mean_caption": "Mean over available data history",
        "accountant_ebitda_margin_volatility": "Margin Volatility (σ)",
        "accountant_ebitda_volatility_high": "HIGH VOLATILITY",
        "accountant_ebitda_volatility_moderate": "MODERATE",
        "accountant_ebitda_volatility_low": "LOW / STABLE",
        "accountant_ebitda_sustainability_flag_title": "Sustainability Flag",
        "accountant_ebitda_sustainability_flag_body": (
            "<strong>Margin volatility detected.</strong> The historical variance suggests "
            "earnings may be subject to non-recurring fluctuations or sensitivity to external "
            "market cycles. This risk is factored into the multiple calibration."
        ),
        "accountant_ebitda_compliance_title": "Professional Compliance",
        "accountant_ebitda_compliance_asa": "<strong>ASA BVS-III:</strong> Quality of Earnings assessment required for fiduciary-grade valuation.",
        "accountant_ebitda_compliance_aicpa": "<strong>AICPA BVS-VII:</strong> Normalization schedule required for comprehensive SME reporting.",
        "accountant_ebitda_compliance_trugman": "<strong>Trugman (2017):</strong> Framework for owner benefit add-backs and tax-optimization reversal.",
        "accountant_ebitda_limited_data_badge": "Limited Data Assessment",
        "accountant_ebitda_limited_intro": (
            "SME financial statements often require normalization to isolate sustainable earning "
            "power from owner-specific benefits and non-recurring items. However, a detailed "
            "normalization bridge requires multi-year financial data and comprehensive disclosure "
            "of discretionary expenses."
        ),
        "accountant_ebitda_limited_notice_title": "Data Limitation Notice",
        "accountant_ebitda_limited_notice_body": (
            "<strong>Normalization Analysis Not Performed:</strong> Comprehensive EBITDA "
            "normalization requires historical financial statements (minimum 2-3 years) and "
            "detailed expense categorization. The current assessment utilizes reported EBITDA "
            "figures directly, subject to standard quality adjustments in the valuation multiple "
            "calibration (Step 2.5: Quality Calibration)."
        ),
        "accountant_ebitda_earning_power_framework": "Earning Power Assessment Framework",
        "accountant_ebitda_earning_power_body": (
            "In the absence of detailed normalization data, the valuation methodology applies "
            "<strong>conservative quality adjustments</strong> directly to the valuation multiple "
            "rather than adjusting EBITDA. This Multiple-First approach prevents overstatement of "
            "earning power while maintaining professional defensibility."
        ),
        "accountant_ebitda_current_year_baseline_caption": "Current Year Financial Baseline",
        "accountant_ebitda_status_label": "Status",
        "accountant_ebitda_revenue": "Revenue",
        "accountant_ebitda_status_reported": "Reported",
        "accountant_ebitda_reported_label": "EBITDA (Reported)",
        "accountant_ebitda_status_used_as_reported": "Used as-reported",
        "accountant_ebitda_margin_label": "EBITDA Margin",
        "accountant_ebitda_profitability_indicator": "Profitability indicator",
        "accountant_ebitda_alt_methodology_title": "Alternative Assessment Methodology",
        "accountant_ebitda_alt_methodology_body": (
            "<strong>Multiple-First Risk Adjustment:</strong> Rather than performing EBITDA "
            "normalization with limited data visibility, this valuation applies earnings quality "
            "adjustments directly to the valuation multiple during Step 2.5 (Quality Calibration). "
            "This approach follows AICPA BVS-VII guidelines for valuations with limited financial "
            "disclosure."
        ),
        "accountant_ebitda_quality_adjustments_title": "Quality Adjustments Applied",
        "accountant_ebitda_quality_adj_data": (
            "<strong>Data Quality Premium/Discount:</strong> Applied to multiple based on "
            "financial statement reliability assessment"
        ),
        "accountant_ebitda_quality_adj_earnings": (
            "<strong>Earnings Quality Calibration:</strong> Conservative adjustment for potential "
            "owner benefits and discretionary expenses"
        ),
        "accountant_ebitda_quality_adj_size": (
            "<strong>Small Company Risk:</strong> Size-related adjustments account for limited "
            "historical data and documentation depth"
        ),
        "accountant_ebitda_valuation_impact_title": "Valuation Impact Assessment",
        "accountant_ebitda_quality_approach_label": "Quality Adjustment Approach",
        "accountant_ebitda_multiple_first": "Multiple-First",
        "accountant_ebitda_quality_approach_caption": "Risk adjustments applied to valuation multiple",
        "accountant_ebitda_methodology_confidence_label": "Methodology Confidence",
        "accountant_ebitda_confidence_moderate": "Moderate",
        "accountant_ebitda_limited_visibility": "Limited normalization visibility",
        "accountant_ebitda_pro_standards_title": "Professional Standards Compliance",
        "accountant_ebitda_pro_standards_body": (
            "<strong>AICPA BVS-VII:</strong> When comprehensive normalization is not feasible due "
            "to data limitations, valuation professionals should apply conservative quality "
            "adjustments to ensure the valuation does not overstate earning power. This approach "
            "maintains professional skepticism and ensures defensibility in limited-information "
            "scenarios."
        ),
    }
