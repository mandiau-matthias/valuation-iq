"""SaaS appendix, cap-table, and adjusted-NAV copy."""

from __future__ import annotations

SAAS_AND_NAV_TRANSLATIONS: dict[str, object] = {'saas_appendix_title': 'SaaS Analysis',
 'saas_appendix_intro': 'This section shows the ARR anchor and the core SaaS quality indicators '
                        'supporting the valuation multiple.',
 'saas_appendix_metrics_title': 'SaaS core metrics',
 'saas_appendix_adjustments_title': 'ARR multiple adjustments',
 'saas_appendix_no_adjustments': 'No standalone ARR-multiple adjustments were available for this '
                                 'valuation.',
 'saas_appendix_factor_label': 'Factor',
 'saas_appendix_impact_label': 'Impact',
 'saas_appendix_note_label': 'Note',
 'saas_appendix_arr_growth_label': 'ARR growth (annual %)',
 'saas_appendix_gross_margin_label': 'Gross margin (%)',
 'saas_appendix_customer_concentration_label': 'Customer concentration (%)',
 'saas_appendix_cac_payback_label': 'CAC payback (mo.)',
 'saas_appendix_customer_churn_label': 'Customer churn (%)',
 'saas_appendix_nrr_expansion_spread_label': 'Net expansion spread',
 'saas_appendix_arr_label': 'ARR',
 'saas_appendix_ltv_cac_label': 'LTV / CAC',
 'saas_appendix_magic_number_label': 'Magic Number',
 'saas_quality_score_label': 'SaaS Quality Score',
 'saas_quality_score_caption': 'Composite of Rule of 40, NRR, LTV/CAC, gross revenue churn and '
                               'gross margin — each weighted 20%.',
 'saas_appendix_ebitda_crosscheck_label': 'EBITDA cross-check',
 'saas_quality_strong': 'Strong',
 'saas_quality_healthy': 'Healthy',
 'saas_quality_developing': 'Developing',
 'saas_quality_at_risk': 'At Risk',
 'saas_waterfall_title': 'EV/ARR multiple build-up',
 'saas_waterfall_base': 'Base multiple',
 'saas_waterfall_final': 'Final multiple',
 'saas_waterfall_benchmark_note': 'US public SaaS benchmark',
 'saas_waterfall_clamp_note': 'Clamped to [2.5×, 12.0×]',
 'saas_arr_bridge_title': 'ARR basis',
 'saas_arr_bridge_source': 'Source',
 'saas_expansion_revenue_label': 'Expansion revenue (%)',
 'saas_cap_table_title': 'Cap table & dilution',
 'saas_cap_table_simulator_heading': 'Cap-table simulator',
 'saas_cap_table_headline_sentence': 'Raising <strong>{investment}</strong> at a pre-money '
                                     '(equity) of <strong>{pre_money}</strong> dilutes the '
                                     'founders by <strong>{dilution_pct}</strong>.',
 'saas_cap_table_pre_money_label': 'Pre-money (equity, after debt bridge)',
 'saas_cap_table_round_label': '+ Round being raised',
 'saas_cap_table_post_money_label': '= Post-money valuation',
 'saas_cap_table_investor_dilution_label': 'New-investor stake',
 'saas_cap_table_safe_dilution_label': 'Dilution from SAFE conversion',
 'saas_cap_table_option_pool_label': 'Option pool',
 'saas_cap_table_founder_dilution_label': 'Total founder dilution',
 'saas_cap_table_safe_overview_heading': 'SAFE overview',
 'saas_cap_table_safe_principal_label': 'Outstanding SAFE principal (total)',
 'saas_cap_table_safe_drag_label': 'SAFE conversion drag on post-money',
 'saas_cap_table_safe_assumption_note': 'Conversion assumption: SAFEs convert at the next priced '
                                        'round under the most favourable clause (cap or discount).',
 'saas_cap_table_unavailable_note': 'Cap table unavailable — enter a round being raised and '
                                    '(optionally) your capital history to generate this overview.',
 'nav_page_title': 'Adjusted Net Asset Value (NAV)',
 'nav_page_subtitle': 'Valuation anchored on the current intrinsic value of assets and '
                      'liabilities, after revaluation of fixed assets, deduction of deferred-tax '
                      'latencies and off-balance corrections.',
 'nav_page_badge': 'Asset anchor',
 'nav_methodology_intro': 'Adjusted NAV starts from book equity and revalues individual assets to '
                          'market (typically land, buildings and participations). Latent tax on '
                          'revaluation gains and off-balance liabilities are deducted to land at '
                          'intrinsic equity value — the most defensible reference for holdings, '
                          'real-estate vehicles and asset-heavy businesses where going-concern '
                          'multiples understate underlying substance.',
 'nav_intrinsic_summary_header': 'Intrinsic equity value — summary',
 'nav_intrinsic_book_equity_label': 'Book equity',
 'nav_intrinsic_revaluation_uplift_label': 'Revaluation effect (net corrections − latencies)',
 'nav_intrinsic_value_label': 'Intrinsic value (Adjusted NAV)',
 'nav_intrinsic_uplift_pct_label': 'Revaluation vs. book value',
 'nav_intrinsic_ownership_label': 'Ownership percentage',
 'nav_assumptions_note': 'Source: statutory accounts (PCMN 22x land & buildings, 23-26x machinery '
                         '& equipment, 28x financial fixed assets, 168 deferred tax liabilities, '
                         '15x capital subsidies). Real-estate revaluations should ideally be '
                         'supported by a third-party appraisal; absent one, the model applies a '
                         'sector/region-calibrated adjustment and marks the entry for review in '
                         'the calibration ledger.',
 'nav_label_real_estate': 'Real estate (revaluation)',
 'nav_label_hidden_reserves': 'Hidden reserves',
 'nav_label_inventory': 'Inventory (correction)',
 'nav_label_receivables': 'Receivables (correction)',
 'nav_label_goodwill_writeoff': 'Goodwill write-off',
 'nav_label_other_revaluations': 'Other revaluations',
 'nav_label_real_estate_appraisal': 'Real estate (appraisal swap)',
 'nav_label_equipment_revaluation': 'Equipment (economic lifespan)',
 'nav_label_off_balance': 'Off-balance obligations',
 'nav_net_liability_summary_header': 'Net liability position — summary',
 'nav_net_liability_callout': 'Adjusted NAV is negative: after revaluation and tax latencies, '
                              'liabilities exceed assets. This is a floor-value signal for '
                              'buy-side negotiation and a statutory trigger in BE (Art. 633 '
                              'W.Venn. — alarm-bell procedure).'}
