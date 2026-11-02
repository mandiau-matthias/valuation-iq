"""Cover, executive-summary, warning, adaptive, and advisor CTA copy."""

from __future__ import annotations

COVER_AND_EXECUTIVE_TRANSLATIONS: dict[str, object] = {'cover_estimate_label': 'Business Valuation',
 'cover_estimate_label_seller': 'Your business valuation',
 'cover_ev_label': 'Indicative Enterprise Value (EV)',
 'cover_equity_label': 'Indicative Equity Value',
 'cover_equity_note': 'Equity after netting interest-bearing debt and excess cash — what the '
                      'seller indicatively nets.',
 'equity_adjusted_label': 'Adjusted NAV (Intrinsic Value)',
 'equity_adjusted_note': 'Equity value adjusted for net cash/debt and deferred taxes.',
 'cover_ebitda_label': 'Normalized EBITDA (weighted)',
 'cover_sde_label': 'Sustainable SDE (weighted)',
 'cover_multiple_label': 'Applied Multiple',
 'cover_adaptive_blend_label': 'Adaptive blend',
 'cover_wacc_label': 'WACC',
 'cover_date_label': 'Date',
 'cover_confidential': 'Confidential',
 'cover_founded': 'Founded',
 'cover_year_suffix': 'year',
 'cover_years_suffix': 'years',
 'cover_ev_note_dcf': 'Indicative enterprise value via DCF analysis, on a cash and debt-free basis',
 'cover_ev_note_hybrid': 'Indicative enterprise value via weighted EBITDA Multiples + DCF, on a '
                         'cash and debt-free basis',
 'cover_ev_note_adaptive': 'Indicative enterprise value via the Upswitch adaptive market approach, '
                           'on a cash and debt-free basis',
 'cover_ev_note_adaptive_multiples_only': 'Indicative enterprise value via Upswitch Adaptive · '
                                          'market approach, on a cash and debt-free basis',
 'cover_ev_note_default': 'Indicative enterprise value on a cash and debt-free basis. Net proceeds '
                          'depend on debt, cash and working capital at transaction date.',
 'cover_statutory_currency_label': 'Statutory currency',
 'cover_statutory_currency_note': 'valuation expressed in EUR',
 'cover_owner_profiling_summary': 'Owner profiling — transferability index {tri}/100 · '
                                  '{risk_level} · multiple impact {adj_pct}% vs benchmark',
 'exec_summary_title': 'Summary',
 'exec_indicative_label': 'Indicative',
 'high_severity_callout_title': 'Valuation flags',
 'high_severity_callout_lead_singular': 'This valuation contains 1 high-severity signal. Verify '
                                        'the underlying data before sharing the report.',
 'high_severity_callout_lead_plural': 'This valuation contains {count} high-severity signals. '
                                      'Verify the underlying data before sharing the report.',
 'nwc_disclosure_surplus': 'Working capital adjustment: +{amount} surplus above the normalized '
                           'band ({actual_pct}% vs. target {target_pct}%) — accrues to the seller '
                           'at transfer.',
 'nwc_disclosure_deficit': 'Working capital adjustment: −{amount} shortfall below the normalized '
                           'band ({actual_pct}% vs. target {target_pct}%) — typically deducted '
                           'from equity at transfer.',
 'nwc_disclosure_neutral': 'Working capital is within the normalized band ({actual_pct}% vs. '
                           'target {target_pct}%); no adjustment applied.',
 'nwc_disclosure_unavailable': 'No balance sheet data provided — working capital not assessed. '
                               'Transaction structure affects net proceeds.',
 'warning_thin_comparables_proxy_message': 'Industry multiple is derived from thin or proxy-sector '
                                           'data. The headline multiple is not statistically '
                                           'robust on its own.',
 'warning_thin_comparables_proxy_recommendation': 'Confirm the business_type_id matches the actual '
                                                  'operating model and, if the company is in a '
                                                  'different sector than the proxy, override the '
                                                  'multiple manually or request a deeper '
                                                  'benchmarks pull.',
 'warning_owner_concentration_skip_message': 'Owner-concentration adjustment was skipped — '
                                             'number_of_owners and/or number_of_employees were not '
                                             'provided. For owner-led SMEs this is a material gap.',
 'warning_owner_concentration_skip_recommendation': 'Capture number_of_owners and '
                                                    'number_of_employees on the request (top-level '
                                                    'fields, business_context, or '
                                                    'current_year_data) and re-run, or apply the '
                                                    'discount manually before delivery.',
 'warning_ebitda_divergence_message': 'The EBITDA field disagrees with the normalized EBITDA '
                                      'metadata — the report bridge and the underlying calculation '
                                      'record may show different numbers.',
 'warning_ebitda_divergence_recommendation': 'Fix the request builder to write the post-adjustment '
                                             'value into both current_year_data.ebitda AND '
                                             'ebitda_normalization_metadata.normalized_ebitda.',
 'warning_method_substitution_message': 'The requested valuation method could not be executed; the '
                                        'report uses a substitute method (see methodology block).',
 'warning_method_substitution_recommendation': 'Provide the missing inputs for the original method '
                                               '(typically balance-sheet data for NAV) and re-run, '
                                               'or explicitly confirm the substitute.',
 'warning_net_debt_unavailable_message': 'No balance-sheet data available — net debt was not '
                                         'independently computed. The EV→Equity bridge uses a '
                                         'proxy and is not audit-defensible.',
 'warning_net_debt_unavailable_recommendation': 'Add total debt and cash positions (or import the '
                                                'filed accounts) before sharing this report '
                                                'externally.',
 'warning_owner_comp_estimated_message': 'Owner compensation was not provided and has been '
                                         'auto-estimated. For owner-led businesses this is '
                                         'typically the #1 normalization item.',
 'warning_owner_comp_estimated_recommendation': 'Enter the actual owner salary paid (or the market '
                                                'replacement cost) so normalized EBITDA is '
                                                'defensible.',
 'warning_ebitda_benchmark_deviation_message': 'EBITDA margin deviates materially from the sector '
                                               'median. This can indicate normalization headroom '
                                               'or a fundamental margin gap.',
 'warning_ebitda_benchmark_deviation_recommendation': 'Document the reason for the deviation '
                                                      '(owner salary, one-offs, structural '
                                                      'difference) or add a normalization line.',
 'warning_book_equity_unavailable_message': 'Book equity not provided — fiscal reference value is '
                                            'incomplete. The EBITDA component is shown separately; '
                                            'the full statutory formula cannot close.',
 'warning_book_equity_unavailable_recommendation': 'Add total_equity (or total_assets and '
                                                   'total_debt) from the latest filed accounts so '
                                                   'the statutory formula can render fully.',
 'exec_confidence_score': 'Confidence Score',
 'exec_comparable_transactions': 'comparable transactions',
 'exec_ev_label': 'Indicative Equity Value',
 'exec_range_label': 'Range',
 'exec_normalized_label': 'Normalized',
 'exec_revenue_label': 'Revenue',
 'exec_employee_singular': 'employee',
 'exec_employee_plural': 'employees',
 'exec_industry_comparison': 'Industry Comparison',
 'exec_median_multiple': 'Median Multiple',
 'exec_single_reference': 'Single reference',
 'exec_sample_label': 'Sample',
 'exec_transactions': 'transactions',
 'exec_transactions_singular': 'transaction',
 'exec_limited_data': 'limited dataset',
 'exec_insufficient_data_warning': 'Limited reference set — indicative market approach',
 'exec_benchmark_source_note': 'Reference industry (not the same source as valuation basis)',
 'exec_benchmark_applied_vs_reference': 'The applied multiple (after calibration and risk '
                                        'adjustments) differs from the reference median; this is a '
                                        'transaction-specific estimate, not a universal market '
                                        'premium or discount.',
 'exec_thin_benchmark_seller_escalation': 'Strengthen the basis with more fiscal years and sector '
                                          'transactions before a deal — your advisor can sharpen '
                                          'the file further.',
 'exec_thin_benchmark_advisor_escalation': 'Strengthen the client file with more fiscal years and '
                                           'sector transactions before marketing or diligence.',
 'adaptive_intro_multiples_only_seller': 'This valuation uses calibrated market multiples. DCF does not contribute to this estimate. This page shows <em>how</em> your indicative value is built.',
 'adaptive_intro_hybrid_seller': 'Upswitch Adaptive blends market multiples with a discounted '
                                 'cash-flow view when your profile supports it. This page shows '
                                 '<em>how</em> your indicative value was built.',
 'adaptive_intro_multiples_only_advisor': 'This valuation uses calibrated market multiples. DCF does not contribute; see the method eligibility assessment for the reasons. Use this page to explain <em>how</em> the headline range is built for your client.',
 'adaptive_intro_hybrid_advisor': 'Upswitch Adaptive combines market-based multiples with a '
                                  'discounted cash-flow view when the business profile supports '
                                  'it. Use this page to explain <em>how</em> the headline range '
                                  "was assembled for your client's transaction context.",
 'adaptive_footnote_multiples_only_seller': '<strong>Your estimate.</strong> This valuation uses market multiples; DCF does not contribute. The range reflects sensitivity to EBITDA and the multiple.',
 'adaptive_footnote_hybrid_seller': '<strong>Your estimate.</strong> This approach combines market '
                                    'anchors with forecasts where appropriate. Method detail '
                                    'appears elsewhere in this report.',
 'adaptive_footnote_multiples_only_advisor': '<strong>For your client file.</strong> This valuation uses calibrated market multiples; DCF does not contribute. The headline range reflects multiples sensitivity. See the method eligibility assessment for the reasons.',
 'adaptive_footnote_hybrid_advisor': '<strong>For your client file.</strong> This approach is '
                                     'tailored to mid-market situations where forecasts are '
                                     'informative but multiples remain a market anchor. The '
                                     'combined results and key assumptions are shown elsewhere in '
                                     'this report.',
 'seller_limited_scope_title': 'Next steps to strengthen your valuation',
 'seller_limited_scope_intro': 'This estimate provides a usable indicative basis. For a '
                               'transaction or diligence we recommend the following steps:',
 'seller_limited_scope_li_year': 'Add a second fiscal year (e.g. 2024) for trend and reliability.',
 'seller_limited_scope_li_balance': 'Connect accounting (Yuki, Exact, …) or enter a balance sheet '
                                    'for net debt and working capital.',
 'seller_limited_scope_li_advisor': 'Share the report with your advisor for normalisation and '
                                    'sector benchmarks.',
 'advisor_limited_scope_title': 'Next steps to strengthen the client file',
 'advisor_limited_scope_intro': 'This estimate provides a usable indicative basis for the client '
                                'dossier. Before a transaction or diligence we recommend the '
                                'following steps:',
 'advisor_limited_scope_li_year': 'Add a second fiscal year for the client (e.g. 2024) for trend '
                                  'and reliability.',
 'advisor_limited_scope_li_balance': "Connect the client's accounting (Yuki, Exact, …) or enter a "
                                     'balance sheet for net debt and working capital.',
 'advisor_limited_scope_li_client': 'Share the report with your client and align on normalisations '
                                    'before buyer discussions.',
 'seller_margin_diligence_note': 'Your EBITDA margin ({reported_pct}%) is below the sector typical '
                                 '(~{typical_pct}%). Buyers may read this as multiple pressure or '
                                 'a need for normalisation — discuss with your advisor.',
 'advisor_margin_diligence_note': 'Reported EBITDA margin ({reported_pct}%) is below the sector '
                                  'typical (~{typical_pct}%). Flag normalisation and buyer '
                                  'narrative in the client dossier.',
 'seller_multiple_bridge_title': 'From sector reference to applied multiple',
 'seller_multiple_bridge_reference': 'Sector reference (DB median)',
 'seller_multiple_bridge_base': 'Calibrated contract basis (size/margin)',
 'seller_multiple_bridge_applied': 'Applied to your EBITDA',
 'advisor_multiple_bridge_title': 'From sector reference to applied multiple (client dossier)',
 'advisor_multiple_bridge_reference': 'Sector reference (DB median)',
 'advisor_multiple_bridge_base': 'Calibrated contract basis (size/margin)',
 'advisor_multiple_bridge_applied': 'Applied to client EBITDA',
 'advisor_controls_audit_title': 'Advisor override audit trail',
 'advisor_controls_multiple_calibration_title': 'Multiple calibration',
 'advisor_controls_sector_average_label': 'Sector average',
 'advisor_controls_risk_quality_premium_label': 'risk/quality premium',
 'advisor_controls_calibrated_label': 'calibrated',
 'advisor_controls_effective_override_title': 'Final effective multiple override',
 'advisor_controls_model_effective_multiple_label': 'model effective',
 'advisor_controls_advisor_effective_multiple_label': 'advisor effective',
 'advisor_controls_delta_multiple_label': 'delta',
 'advisor_controls_note_label': 'Note',
 'advisor_controls_historical_ebitda_weighting_title': 'Historical year weighting',
 'advisor_controls_weighted_ebitda_label': 'weighted EBITDA',
 'advisor_controls_real_estate_treatment_title': 'Real estate treatment',
 'advisor_controls_real_estate_included_label': 'Included in transaction',
 'advisor_controls_real_estate_carve_out_label': 'Carve-out from transaction',
 'advisor_controls_market_value_label': 'market value',
 'advisor_controls_book_value_label': 'book value',
 'advisor_controls_surplus_value_label': 'surplus',
 'advisor_controls_market_rent_label': 'market rent',
 'seller_advisor_cta_title': 'Share with your advisor',
 'seller_advisor_cta_lead': 'Your accountant or M&A advisor can refine normalisations, sector '
                            'benchmarks and deal structure — and use this file in real sale '
                            'preparation.',
 'seller_advisor_cta_button': 'Share with your advisor',
 'exec_methodology_hybrid': 'hybrid market approach (EV/EBITDA multiple + DCF)',
 'exec_methodology_dcf': 'income approach (Discounted Cash Flow)',
 'exec_methodology_sde': 'market approach with SDE multiples',
 'exec_methodology_multiples': 'market approach using the selected market multiple',
 'exec_methodology_asset': 'asset-based valuation (NAV)',
 'exec_methodology_yield': 'real-estate yield approach (rent ÷ cap-rate)',
 'exec_methodology_badge_hybrid': 'EBITDA Multiples + DCF',
 'exec_methodology_badge_dcf': 'DCF Analysis',
 'exec_methodology_badge_sde': 'SDE Multiples',
 'exec_methodology_badge_multiples': 'Market Multiples',
 'exec_methodology_badge_asset': 'Asset-based valuation (NAV)',
 'exec_methodology_badge_yield': 'Real-estate yield',
 'exec_methodology_badge_adaptive': 'Upswitch adaptive market approach',
 'exec_methodology_adaptive': 'Upswitch adaptive market approach',
 'exec_methodology_badge_adaptive_multiples_only': 'Upswitch Adaptive · Market Approach',
 'exec_methodology_adaptive_multiples_only': 'Upswitch Adaptive · market approach',
 'exec_goal_label': 'Purpose of the Valuation',
 'exec_description_intro': 'This business valuation provides the indicative enterprise value of',
 'exec_as_of': 'as of',
 'exec_description_calculated_via': 'calculated via the',
 'exec_npv_calculation': 'NPV of',
 'exec_fcf_terminal_value': 'years FCF + Terminal Value',
 'exec_market_median': 'Market median',
 'exec_ev_equity_note_title': 'Valuation and net proceeds',
 'exec_ev_equity_note_text': 'The value above represents Enterprise Value (EV). Estimated '
                             'shareholder value follows from: Enterprise Value (EV) - Net Debt = '
                             'Equity Value. Net proceeds to the seller depend on outstanding debt, '
                             'excess cash and working capital adjustments at transaction date.',
 'exec_ev_equity_line2': 'Net proceeds depend on: debt, cash, and working capital adjustments at '
                         'transfer.',
 'exec_ev_equity_with_balance': 'Balance sheet data provided — the net-debt bridge is computed on '
                                'the balance-sheet positions. Working capital and net debt are '
                                'settled at transfer under the agreed price mechanism, for '
                                'example completion accounts or a locked box.',
 'exec_ev_equity_no_balance': 'No balance sheet data provided — working capital not assessed. '
                              'Transaction structure affects final proceeds.',
 'exec_sde_note': 'Note: For owner-operated micro-businesses, buyers may apply SDE multiples '
                  "(Seller's Discretionary Earnings). This report uses EBITDA-based EV in "
                  'accordance with standard M&A practice.',
 'exec_sde_cross_check_title': 'SDE cross-check (owner-led micro-business)',
 'exec_sde_cross_check_intro': 'For this profile buyers also commonly apply an SDE multiple '
                               "(Seller's Discretionary Earnings). The indicative SDE-based "
                               'valuation is shown next to the EBITDA headline as a convergence '
                               'check, not as a replacement method.',
 'exec_sde_cross_check_sde_label': 'SDE',
 'exec_sde_cross_check_multiple_label': 'SDE multiple',
 'exec_sde_cross_check_ev_label': 'Indicative EV on SDE basis',
 'exec_sde_cross_check_footnote': 'SDE = EBITDA + market-rate owner compensation addback. Multiple '
                                  'from the micro-SME benchmark set; have an M&A adviser confirm '
                                  'before external distribution.',
 'exec_implied_ebitda_multiple': 'Implied EBITDA multiple',
 'exec_pre_blend_label': 'Pre-blend cross-check',
 'exec_blended_headline_note': 'headline after SDE / synthesis blending',
 'exec_ev_bridge_title': 'EV-to-Equity Bridge',
 'exec_ev_bridge_ev_label': 'Enterprise Value (EV)',
 'exec_ev_bridge_net_debt_label': 'Net Debt',
 'exec_ev_bridge_net_cash_label': 'Net Cash',
 'exec_ev_bridge_equity_label': 'Equity Value',
 'exec_ev_bridge_nwc_label': 'Net working capital adjustment',
 'exec_ev_bridge_residual_label': 'Reconciling difference',
 'exec_nav_bridge_title': 'Bridge to Adjusted NAV (Intrinsic Value)',
 'exec_nav_bridge_book_equity': 'Book Equity',
 'exec_nav_bridge_gross_corrections': 'Total corrections (gross)',
 'exec_nav_bridge_tax_latency': 'Tax latencies on capital gains',
 'exec_nav_bridge_off_balance': 'Off-balance sheet obligations',
 'exec_nav_bridge_corrected_nav': 'Adjusted NAV (Intrinsic Value)',
 'exec_asking_price_label': 'Suggested Listing Price',
 'exec_asking_price_note': 'Strategic buffer for negotiation',
 'exec_asking_price_note_below_basis': 'Market anchor — no negotiation buffer',
 'exec_asking_price_note_suppressed': 'Limited scope — no negotiation buffer added',
 'exec_data_coverage_chip_label': 'Data coverage',
 'exec_engine_confidence_chip_label': 'Model confidence',
 'exec_volatility_chip_label': 'Volatile EBITDA',
 'exec_volatility_chip_note_template': 'Normalised EBITDA ranges {min} ({min_year}) – {max} '
                                       '({max_year}) across the displayed years.',
 'exec_volatility_chip_note_loss_year_template': 'One or more years carry a loss EBITDA ({min} in '
                                                 '{min_year} → {max} in {max_year}); a single '
                                                 'multiple does not represent this.',
 'exec_volatility_chip_note_normalization_template': 'Peak/trough on reported EBITDA; {max_year} '
                                                     'includes material normalisation.',
 'sensitivity_provenance_note_template': 'Grid = scenario corners at P25/P75 multiples. Headline '
                                         'valuation range: {engine_low} — {engine_high}.',
 'cover_warning_count_chip_singular': '{count} signal to review',
 'cover_warning_count_chip_plural': '{count} signals to review',
 'warning_impossible_margin_message': 'One or more years show a normalised EBITDA margin ≥ 100%; '
                                      'this is mathematically impossible for an operating entity.',
 'warning_impossible_margin_recommendation': 'Verify the EBITDA mapping for the year. Common '
                                             'causes: over-aggressive normalisations, non-revenue '
                                             'income (rental, intercompany) or an operating entity '
                                             'that holds its property inside the same NV — '
                                             'consider a property carve-out.',
 'market_provenance_source_managed_dataset': 'Upswitch economic dataset',
 'exec_narrative_basis': 'Based on the normalised earnings capacity and market-conform valuation '
                         'multiples, the indicative enterprise value amounts to',
 'exec_narrative_basis_dcf': 'Based on the present value of projected free cash flows (DCF), the '
                             'indicative enterprise value amounts to',
 'exec_narrative_basis_hybrid': 'Based on the weighted synthesis of the market approach and DCF, '
                                'the indicative enterprise value amounts to',
 'exec_narrative_basis_asset': 'Based on balance-sheet substance, the NAV approach, and relevant '
                               'balance-sheet adjustments, the indicative value amounts to',
 'exec_narrative_basis_yield': 'Based on sustainable net rental income, a market-conform cap rate, '
                               'and the NAV floor, the indicative value amounts to',
 'exec_narrative_ev_note': 'This value represents the Enterprise Value on a cash-free, debt-free '
                           'basis, before any adjustments for net debt, working capital, or '
                           'transaction structure.',
 'exec_official_registry_head': 'Official registry check (NBB)',
 'exec_official_filing_year_label': 'Filing year',
 'exec_official_source_staatsblad': 'Source: Staatsbladmonitor',
 'exec_dd_accountant_vs_official_title': 'Advisor inputs vs. official figures',
 'exec_dd_col_accountant': 'Advisor inputs',
 'exec_official_dd_line_item': 'Line item',
 'exec_official_dd_col_official': 'Official',
 'exec_official_dd_delta_pct': 'Δ %',
 'exec_official_variance_title': 'Variance analysis',
 'exec_official_explanation_required': 'Explanation required',
 'exec_official_variance_hard_note': 'Large deviation vs. official filing (at or above hard '
                                     'threshold).',
 'exec_official_trust_match_verified': 'Figures entered by the advisor have been checked against '
                                       'the official NBB annual accounts (source: '
                                       'Staatsbladmonitor).',
 'exec_official_total_assets_label': 'Total assets',
 'exec_official_equity_label': 'Equity',
 'exec_saas_anchor_label': 'SaaS anchor',
 'exec_saas_quality_title': 'SaaS quality signals',
 'exec_saas_nrr_label': 'NRR',
 'exec_saas_rule_of_40_label': 'Rule of 40',
 'exec_saas_churn_label': 'Gross churn',
 'exec_saas_arr_growth_label': 'ARR growth (annual)',
 'warning_indicative_dcf_message': 'Indicative DCF based on supplied or modeled cash-flow assumptions. The company forecast has not been source-verified.',
 'warning_indicative_dcf_recommendation': 'Review cash flows, taxes, reinvestment and terminal assumptions against company evidence before relying on this estimate.',
}
