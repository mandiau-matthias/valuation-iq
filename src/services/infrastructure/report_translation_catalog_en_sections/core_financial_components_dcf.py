"""Shared components, calibration, tax-latency, and DCF copy."""

from __future__ import annotations

COMPONENTS_CALIBRATION_AND_DCF_TRANSLATIONS: dict[str, object] = {'footer_indicative_estimate': 'Indicative estimate',
 'footer_confidential': 'Confidential',
 'footer_page': 'Page',
 'footer_of': 'of',
 'header_confidential': 'Confidential',
 'header_powered_by': 'Powered by Upswitch',
 'sensitivity_title': 'Sensitivity Analysis',
 'sensitivity_description': 'Enterprise value at different EBITDA and multiple scenarios (€ '
                            'thousands)',
 'sensitivity_ebitda_multiple_header': 'EBITDA ↓ / Multiple →',
 'sensitivity_low': 'Low',
 'sensitivity_base': 'Base',
 'sensitivity_high': 'High',
 'sensitivity_range': 'Range',
 'sensitivity_illustrative_note': '(±20% illustrative band — model multiple range not available '
                                  'for this report.)',
 'sensitivity_corner_label': 'Scenario corners (low × low → high × high)',
 'adj_description': 'Description',
 'adj_source': 'Source',
 'adj_category': 'Category',
 'adj_status': 'Status',
 'adj_amount': 'Amount (€)',
 'adj_result': 'Result',
 'adj_base': 'Base',
 'adj_owner': 'Owner',
 'adj_non_recurring': 'Non-recurring',
 'adj_personal': 'Personal',
 'adj_related_party': 'Related party',
 'adj_depreciation': 'Depreciation',
 'adj_tax': 'Tax',
 'adj_discretionary': 'Discretionary',
 'adj_accounting': 'Accounting',
 'adj_real_estate': 'Real estate',
 'adj_other': 'Other',
 'adj_approved': 'Approved',
 'adj_pending': 'Pending',
 'adj_rejected': 'Rejected',
 'adj_manual': 'Manual',
 'waterfall_title': 'EBITDA Normalization Bridge',
 'waterfall_reported': 'Reported',
 'waterfall_normalized': 'Normalized',
 'waterfall_adjustment': 'Adjustment',
 'waterfall_no_data': 'EBITDA normalization chart not available — insufficient data',
 'adj_by': 'by',
 'tax_latency_title': 'Tax Latencies',
 'tax_latency_description': 'Deferred tax assets and liabilities affecting the equity position. '
                            'These adjustments determine the Adjusted NAV (Intrinsic Value).',
 'tax_latency_type': 'Type',
 'tax_latency_desc_column': 'Description',
 'tax_latency_temp_diff': 'Temporary difference (€)',
 'tax_latency_rate': 'Rate',
 'tax_latency_amount': 'Amount (€)',
 'tax_latency_active': 'Active',
 'tax_latency_passive': 'Passive',
 'tax_latency_net_impact': 'Net impact on equity value',
 'tax_latency_account_code': 'Ledger',
 'tax_latency_equity_bridge_qualifier': ' (net)',
 'calib_title': 'Valuation Calibration',
 'calib_sde_intro': "For owner-operated micro-businesses, we apply SDE multiples (Seller's "
                    'Discretionary Earnings). SDE includes EBITDA plus owner salary and benefits, '
                    'reflecting the true earnings of an owner-operator.',
 'calib_dcf_intro': 'DCF analysis (Discounted Cash Flow) values the business based on the present '
                    'value of future cash flows. This method is appropriate when detailed '
                    'financial projections are available.',
 'calib_hybrid_intro': 'A hybrid approach combines market multiples and DCF as separate valuation '
                       'methods. The final value is the selected weighted synthesis of both '
                       'components.',
 'calib_asset_intro': 'This valuation starts from balance-sheet substance. Book equity, documented '
                      'balance-sheet adjustments, and deferred tax effects determine the NAV '
                      'anchor; EBITDA is shown only as an operating cross-check.',
 'calib_yield_intro': 'This valuation starts from the real-estate yield. Sustainable net rent is '
                      'capitalised using a market-conform cap rate and checked against a NAV '
                      'floor; EBITDA multiples are not the primary valuation driver here.',
 'calib_adaptive_lens_intro': 'The Upswitch adaptive market approach uses a transaction-calibrated '
                              'EBITDA multiple as the primary lens. A condensed DCF cross-check '
                              'supports the range internally; see the adaptive chapter for detail.',
 'calib_adaptive_lens_intro_multiples_only': 'Upswitch Adaptive selected the market approach for this profile: a transaction-calibrated EBITDA multiple is the primary lens. DCF does not contribute to this valuation; the headline runs entirely on calibrated market multiples. See the adaptive chapter for the method eligibility assessment.',
 'calib_adaptive_lens_badge': 'Upswitch adaptive market approach',
 'calib_adaptive_lens_badge_multiples_only': 'Upswitch Adaptive · Market Approach',
 'calib_multiples_intro': 'Each step from market multiple to final enterprise value — full '
                          'transparency.',
 'calib_multiple_applied': 'Applied multiple',
 'calib_multiple_range': 'Range',
 'calib_methodology_label': 'Methodology',
 'calib_sde_market_median': 'SDE Market Median',
 'calib_dcf_calculated_value': 'Calculated Value',
 'calib_market_median': 'Initial multiple',
 'calib_dcf_market_validation': 'Market Validation',
 'calib_risk_discounts': 'Risk Discounts',
 'calib_dcf_final_value': 'Final Value',
 'calib_applied': 'Applied',
 'calib_asset_basis_label': 'Valuation basis',
 'calib_asset_basis_value': 'Book value / NAV',
 'calib_asset_adjustments_label': 'Balance-sheet adjustments',
 'calib_asset_adjustments_value': 'NAV check',
 'calib_asset_final_label': 'Equity (substance, after net debt)',
 'calib_yield_basis_label': 'Valuation basis',
 'calib_yield_basis_value': 'Net rent / cap rate',
 'calib_yield_adjustments_label': 'Validation',
 'calib_yield_adjustments_value': 'NAV floor',
 'calib_yield_final_label': 'Yield/NAV value',
 'calib_sde_badge': 'SDE Multiples',
 'calib_dcf_badge': 'DCF Analysis',
 'calib_hybrid_badge': 'Hybrid Valuation',
 'calib_asset_badge': 'NAV / balance-sheet substance',
 'calib_yield_badge': 'Real-estate yield',
 'calib_full_calculation': 'Full Calculation',
 'calib_sde_bottom_text': 'SDE (weighted)',
 'calib_dcf_bottom_text': 'NPV of projected cash flows over',
 'calib_multiples_bottom_text': 'Selected valuation basis',
 'calib_ref_market_band': 'The benchmark provenance identifies the reference observations and '
                          'their percentile band. Company adjustments and synthesis determine '
                          'the reported model band; transaction-price accuracy and coverage are unverified.',
 'calib_ref_market_band_reference_only': 'The reference multiple and range are reflected in the '
                                         'calibration; a detailed peer set or sector table was not '
                                         'separately provided in this dossier.',
 'calib_ref_size_discount': 'Discount for size and limited formal processes.',
 'calib_ref_size_discount_skipped': 'Size discount is not stacked separately: the '
                                    'SME/private-transaction multiple already embeds size risk; '
                                    'only remaining company-specific risks are shown separately.',
 'calib_ref_illiquidity': 'Illiquidity discount in accordance with standard private company '
                          'practice (restricted stock studies).',
 'calib_dcf_sensitivity_title': 'DCF Sensitivity Analysis',
 'calib_dcf_wacc_label': 'WACC',
 'calib_dcf_terminal_growth': 'Terminal growth',
 'calib_dcf_exit_multiple': 'Exit multiple',
 'calib_dcf_projection_years': 'Projection years',
 'calib_dcf_terminal_methodology_label': 'Terminal value method',
 'calib_dcf_terminal_method_gordon': 'Gordon Growth',
 'calib_dcf_terminal_method_exit_multiple': 'Exit multiple',
 'calib_dcf_sensitivity_note_gordon': 'Sensitivity shown as WACC versus terminal growth.',
 'calib_dcf_sensitivity_note_exit_multiple': 'Sensitivity shown as WACC versus exit multiple.',
 'calib_dcf_terminal_value_note_gordon': 'Terminal value',
 'calib_dcf_terminal_value_note_exit_multiple': 'Terminal value via exit multiple',
 'calib_dcf_wacc_buildup_label': 'WACC buildup',
 'calib_dcf_mid_year_label': 'Mid-year discounting',
 'calib_dcf_mid_year_note': 'Cash flows are discounted at year 0.5 / 1.5 / 2.5 instead of the end '
                            'of each year.',
 'calib_dcf_year_end_note': 'Cash flows are discounted at year-end (1, 2, 3 …) per the selected '
                            'convention.',
 'calib_dcf_academic_coe_label': 'Cost of equity (CAPM)',
 'calib_dcf_terminal_split_label': 'DCF value split',
 'calib_dcf_explicit_period_label': 'Explicit period',
 'calib_dcf_terminal_period_label': 'Terminal value',
 'dcf_page_title': 'DCF Analysis (Discounted Cash Flow)',
 'dcf_page_subtitle': 'Income approach: free cash flows to the firm (FCFF) are projected over the '
                      'explicit forecast period and discounted to present value at WACC, together '
                      'with a terminal value. The buildup for each component is shown below.',
 'dcf_projection_table_title': 'Free Cash Flow Projection',
 'dcf_wacc_buildup_title': 'WACC Buildup',
 'dcf_wacc_buildup_fallback_title': 'WACC entered manually',
 'dcf_wacc_buildup_fallback_body': 'No CAPM buildup is available because the WACC was entered '
                                   'directly. For a reviewable buildup, supply the risk-free rate, '
                                   'β, equity risk premium and cost of debt in the WACC panel. A '
                                   'documented buildup strengthens defensibility and peer '
                                   'comparison.',
 'dcf_wacc_buildup_fallback_applied_label': 'Applied WACC',
 'dcf_wacc_buildup_override_note': 'Applied WACC reflects advisor or sector-median input; the CAPM '
                                   'buildup below is shown as supporting evidence and a '
                                   'cross-check when it differs.',
 'dcf_wacc_capm_buildup_label': 'CAPM buildup',
 'dcf_wacc_applied_in_wacc_label': 'Applied in WACC',
 'dcf_wacc_rounded_label': 'rounded',
 'dcf_row_revenue': 'Revenue',
 'dcf_row_growth': 'Growth',
 'dcf_row_ebitda': 'EBITDA',
 'dcf_row_ebitda_margin': 'EBITDA margin',
 'dcf_row_ebit': 'EBIT',
 'dcf_row_taxes': 'Taxes',
 'dcf_row_nopat': 'NOPAT',
 'dcf_row_da_addback': 'D&A (add back)',
 'dcf_row_capex': 'CapEx',
 'dcf_row_nwc': 'ΔNWC',
 'dcf_row_fcff': 'FCFF',
 'dcf_row_discount_factor': 'Discount factor',
 'dcf_row_pv_fcff': 'PV(FCFF)',
 'dcf_terminal_value_header': 'Terminal Value',
 'dcf_ev_summary_header': 'Enterprise Value (DCF)',
 'dcf_pv_explicit_label': 'PV explicit period',
 'dcf_pv_terminal_label': 'PV terminal value',
 'dcf_enterprise_value_label': 'Enterprise Value',
 'dcf_sensitivity_matrix_title': 'Sensitivity Matrix (WACC × Terminal Growth)',
 'dcf_assumptions_note': 'Sources — Revenue and EBITDA: management input aligned with available '
                         'normalised history. CapEx, D&A, and ΔNWC: accounting-import data when '
                         'available, sector benchmarks otherwise. WACC: applied advisor/sector '
                         'input where present, with CAPM buildup as support/cross-check (Damodaran '
                         '2026 EU SMB cohort, risk-free rate from 10-year sovereign). Terminal '
                         'value: Gordon Growth unless stated; perpetual growth capped below '
                         'long-run nominal GDP. Discounting: mid-year by default, year-end when '
                         'noted.',
 'dcf_wacc_formula_label': 'WACC formula',
 'dcf_cost_of_equity_label': 'Cost of equity',
 'dcf_cost_of_debt_label': 'Cost of debt',
 'dcf_equity_weight_label': 'Equity weight',
 'dcf_debt_weight_label': 'Debt weight',
 'dcf_tax_rate_label': 'Tax rate',
 'dcf_risk_free_rate_label': 'Risk-free rate',
 'dcf_beta_label': 'Beta',
 'dcf_erp_label': 'Equity Risk Premium',
 'dcf_size_premium_label': 'Size premium',
 'dcf_csr_label': 'Company-specific risk',
 'calib_multiple_waterfall_title': 'Multiple Waterfall',
 'calib_multiple_waterfall_intro': 'How the benchmark multiple is calibrated step by step into the '
                                   'applied multiple.',
 'calib_value_waterfall_title': 'Value Waterfall',
 'calib_value_waterfall_intro': 'From normalized performance to enterprise and equity value. Cash, '
                                'interest-bearing debt, working capital and other balance-sheet '
                                'adjustments are applied only when balance inputs are available. '
                                'Missing cash and debt remain unverified.',
 'calib_value_waterfall_intro_ev_focus': 'From enterprise value to final equity value. Cash, '
                                         'interest-bearing debt, working capital and other '
                                         'balance-sheet adjustments are applied only when balance '
                                         'inputs are available. Missing cash and debt remain '
                                         'unverified.',
 'calib_value_waterfall_intro_balance_provided': 'From enterprise value to final equity value. '
                                                 'Cash, interest-bearing debt, working capital and '
                                                 'other balance-sheet adjustments are reconciled '
                                                 'to the provided balance-sheet inputs.'}
