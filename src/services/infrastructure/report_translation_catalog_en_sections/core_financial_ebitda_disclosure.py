"""EBITDA, disclaimer, attestation, and SOTP-trigger copy."""

from __future__ import annotations

EBITDA_AND_DISCLOSURE_TRANSLATIONS: dict[str, object] = {'ebitda_sde_title': 'SDE Calculation',
 'ebitda_normalization_title': 'EBITDA Normalization',
 'ebitda_sde_description': "SDE (Seller's Discretionary Earnings) represents the total financial "
                           'benefits to an owner-operator.',
 'ebitda_sde_formula': 'SDE = EBITDA + Owner Salary + Owner-related benefits. This is the standard '
                       'metric for micro-enterprises.',
 'ebitda_sde_vs_ebitda': 'SDE vs EBITDA',
 'ebitda_sde_multiples_note': 'SDE is typically 20-40% higher than EBITDA due to owner salary '
                              'add-backs. SDE multiples are therefore lower (1.5-3×) than EBITDA '
                              'multiples (3-5×) for the same value.',
 'ebitda_dcf_description': 'DCF analysis requires normalized cash flows as the basis for '
                           'projections.',
 'ebitda_dcf_projections_note': 'The normalizations below ensure that historical data forms a '
                                'reliable basis for future projections.',
 'ebitda_normalization_description': 'Normalization adjusts reported EBITDA to reflect sustainable '
                                     'earning capacity by removing owner-specific, one-time and '
                                     'non-operating items in accordance with standard M&A '
                                     'practice.',
 'ebitda_adjustments_disclaimer': 'Adjustments are based on user-provided categorization and may '
                                  'be reviewed by an advisor.',
 'ebitda_ai_disclaimer_title': 'Normalization proposals requiring review.',
 'ebitda_ai_disclaimer_body': 'The normalisations below are pattern-based proposals derived from '
                              'ledger data. Confirm each adjustment with evidence and advisor '
                              'judgement before tax, legal or M&A reliance. This is not a formal '
                              'accounting opinion.',
 'ebitda_no_adjustments_note': 'No normalization suggestions were recorded in this run; reported '
                               'EBITDA is carried unchanged in the bridge.',
 'ebitda_normalization_candidates_note': '{count} normalization candidate(s) ({amount} proposed) '
                                         'were detected from the ledger data but not yet applied — '
                                         'advisor review required. Reported EBITDA is used '
                                         "unchanged as the valuation basis; see 'Normalisation & "
                                         "risk-discount audit trail' for the per-item evidence.",
 'ebitda_owner_led_pending_title': 'Owner-led business — normalisation not yet confirmed.',
 'ebitda_owner_led_pending_body': 'An experienced buyer will normally request support for '
                                  'market-rate owner compensation and any one-time or personal '
                                  'expenses. No adjustments have been entered yet; reported EBITDA '
                                  'is therefore used as the valuation basis without normalisation. '
                                  'Confirm these items before external distribution.',
 'ebitda_owner_led_pending_body_prior_year_norms': 'An experienced buyer will normally request '
                                                   'support for market-rate owner compensation and '
                                                   'any one-time or personal expenses. No '
                                                   'adjustments have been entered for the base '
                                                   'year, but the weighted valuation basis does '
                                                   'include normalisations from earlier years (see '
                                                   'the multi-year overview). Have both the owner '
                                                   'compensation and those normalisations '
                                                   'confirmed before external distribution.',
 'ebitda_reported_label': 'Reported EBITDA',
 'ebitda_owner_adjustments': 'Owner Adjustments',
 'ebitda_total_adjustments': 'Total Adjustments',
 'ebitda_sde_year_label': 'SDE',
 'ebitda_normalized_year_label': 'Normalized',
 'ebitda_adjustments_overview': 'Adjustments Overview',
 'ebitda_source_legend': 'Source Legend',
 'ebitda_source_yuki': 'Yuki',
 'ebitda_source_exact': 'Exact',
 'ebitda_source_suggestion': 'Upswitch Suggestion',
 'ebitda_source_metadata': 'Automated extraction',
 'ebitda_source_manual': 'Manual',
 'ebitda_source_yuki_desc': 'Auto-imported from the live Yuki ledger integration — fiscal-year '
                            'figures.',
 'ebitda_source_exact_desc': 'Auto-imported from the live Exact ledger integration — fiscal-year '
                             'figures.',
 'ebitda_source_suggestion_desc': 'Pattern-based entry (owner compensation, one-off, '
                                  'non-recurring). To be confirmed by the advisor.',
 'ebitda_source_metadata_desc': 'From the automated BE-PCMN general-ledger extraction — candidates '
                                'pending advisor review.',
 'ebitda_source_manual_desc': 'Entered or amended by the advisor — evidence and rationale in the '
                              'note.',
 'ebitda_multi_year_title': 'Multi-Year Overview — Valuation Basis',
 'ebitda_sustainable_description': 'Normalized EBITDA',
 'ebitda_valuation_basis': 'is calculated as a weighted average of {count} fiscal years. This is '
                           'the basis for the valuation calculation (EV = Normalized EBITDA × '
                           'Multiple).',
 'ebitda_valuation_basis_asset': 'is calculated as a weighted average of {count} fiscal years. For '
                                 'this asset-based valuation, EBITDA is shown as an operating '
                                 'sanity check; the primary valuation basis remains balance-sheet '
                                 'NAV.',
 'ebitda_valuation_basis_yield': 'is calculated as a weighted average of {count} fiscal years. For '
                                 'this real-estate valuation, EBITDA is shown as an operating '
                                 'sanity check; the primary valuation basis is net rent divided by '
                                 'cap rate, with a NAV floor.',
 'ebitda_valuation_basis_dcf': 'is calculated as a weighted average of {count} fiscal years. This '
                               'forms the basis for the FCFF projections in the DCF analysis.',
 'ebitda_year_column': 'Year',
 'filing_year_col_base': 'Base',
 'filing_year_col_base_minus': 'Base − {n}',
 'ebitda_reported_column': 'Reported',
 'ebitda_normalized_column': 'Normalized',
 'ebitda_weight_column': 'Weight',
 'ebitda_weighted_column': 'Weighted',
 'ebitda_status_column': 'Status',
 'ebitda_margin_suffix': 'margin',
 'ebitda_approved': 'Approved',
 'ebitda_calculated_total': 'Calculated total',
 'ebitda_rounded_for_valuation': 'Rounded for valuation',
 'ebitda_weighted_average_note': 'Weighted average = Σ (Normalized EBITDA × Weight).',
 'ebitda_advisor_weighting_audit_note': 'Advisor-selected weights are documented in the advisor '
                                        'override audit trail.',
 'ebitda_standard_average_note': 'Standard average: each included year carries an equal weight.',
 'ebitda_recent_years_note': 'Weights follow the saved year-weighting policy: the most recent year weighs '
                             'heaviest. The same year weighting is applied to revenue.',
 'ebitda_amounts_rounded_note': 'Amounts rounded to €K unless otherwise stated.',
 'ebitda_adjustments_suffix': 'adj.',
 'ebitda_weighting_basis_note': 'The valuation uses weighted EBITDA of {amount} (multi-year '
                                'saved year weights). This is not an additional normalization '
                                'adjustment relative to the latest fiscal year.',
 'ebitda_weighting_basis_note_prior_year_norms': 'The valuation uses weighted EBITDA of {amount} '
                                                 '(multi-year saved year weights). This basis '
                                                 'includes normalisations from earlier years; it '
                                                 'is not an additional adjustment on top of the '
                                                 'latest fiscal year.',
 'ebitda_real_estate_carve_out_note': 'Real estate is excluded from the transaction: book value '
                                      '{book_value}. Annual estimated market rent of {market_rent} '
                                      'is reflected in the EBITDA basis.',
 'disc_custom_disclaimer_title': 'Reservations and formula controls for this dossier',
 'disc_title': 'Important Notes',
 'disc_primary_title': 'Indicative Estimate — Not Financial Advice',
 'disc_primary_text': 'This document provides an indicative valuation estimate for informational '
                      'purposes only. It does not constitute financial, legal or tax advice, a '
                      'fairness opinion, or a statutory valuation under Belgian company law (WVV). '
                      'Seek independent professional advice before making investment or '
                      'transaction decisions.',
 'disc_custom_disclaimer_matches_primary_body': 'The dossier-specific text recorded for this '
                                                'report matches the standard disclaimer. No '
                                                'additional diverging text has been added.',
 'disc_regulatory_title': 'Regulatory Status',
 'disc_regulatory_text': 'Upswitch is not a licensed investment firm or auditor. This estimate '
                         'does not meet statutory requirements under Belgian WVV or FSMA '
                         'regulations.',
 'disc_data_dependency_title': 'Data Dependency',
 'disc_data_dependency_text': 'The analysis is based on provided information without independent '
                              'audit. The customer and the party supplying the source data remain '
                              'responsible for its accuracy and completeness.',
 'disc_third_party_title': 'Third Party Limitation',
 'disc_third_party_text': 'Prepared exclusively for {company_name}. Third parties may not rely on '
                          'this report without prior written consent from Upswitch and, where '
                          'applicable, the preparer.',
 'disc_validity_title': 'Reference Period',
 'disc_validity_text': 'Assuming facts remain unchanged, intended as a reference for',
 'disc_validity_days': 'up to 90 days from',
 'disc_validity_until_label': 'Review no later than',
 'disc_legal_summary_title': 'Legal Summary',
 'disc_legal_item_1': 'Indicative estimate only — not financial advice or statutory valuation',
 'disc_legal_item_2': 'Based on provided data — not independently audited',
 'disc_legal_item_3': 'For named recipient only — third party reliance requires consent',
 'disc_legal_footer': 'Full terms at upswitch.app/terms-and-conditions • Belgian law applies',
 'disc_methodology_title': 'Methodology',
 'disc_methodology_default': 'Market approach with EV/EBITDA multiples, in accordance with '
                             'standard valuation practice. Alternative methods (DCF, asset-based) '
                             'may yield different results.',
 'disc_methodology_asset_default': 'Asset-based valuation using book equity, documented '
                                   'balance-sheet adjustments and deferred tax effects. Operating '
                                   'metrics are used only as a reasonableness cross-check.',
 'disc_methodology_yield_default': 'Real-estate yield valuation using sustainable net rent, a '
                                   'market-conform cap rate and a NAV floor. Operating EBITDA '
                                   'multiples are not the primary valuation driver.',
 'disc_benchmarks_label': 'Benchmarks',
 'disc_benchmarks_default': 'European SME transaction data',
 'disc_revenue_band': 'revenue band',
 'disc_sector_label': 'Reference sector',
 'disc_technical_standards': 'Report structure inspired by IVS; not a full IVS or USPAP engagement '
                             'unless separately agreed.',
 'disc_quality_notes_title': 'Data Quality Notes',
 'disc_quality_more_label': '+ %d more — see Studio Co-pilot for full list',
 'disc_prepared_by': 'Prepared by',
 'disc_ref_label': 'Ref',
 'disc_references_title': 'Sources & References',
 'disc_references_intro': 'The valuation methodology in this report is based on the following '
                          'academic sources and professional standards:',
 'disc_references_asset_intro': 'The asset-led methodology in this report is grounded in accepted '
                                'valuation literature and professional standards for balance-sheet '
                                'substance, NAV and income capitalisation.',
 'disc_biblio_damodaran': 'Damodaran, A. (2012). <em>Investment Valuation</em>. 3rd ed. Wiley.',
 'disc_biblio_koller': 'Koller, T., Goedhart, M. &amp; Wessels, D. (2020). <em>Valuation: '
                       'Measuring and Managing the Value of Companies</em>. 7th ed. McKinsey &amp; '
                       'Company / Wiley.',
 'disc_biblio_pratt': 'Pratt, S. P. &amp; Niculita, A. V. (2008). <em>Valuing a Business: The '
                      'Analysis and Appraisal of Closely Held Companies</em>. 5th ed. '
                      'McGraw-Hill.',
 'disc_biblio_hitchner': 'Hitchner, J. (2017). <em>Financial Valuation</em>. 4th ed. Wiley.',
 'disc_biblio_trugman': 'Trugman, G. (2017). <em>Understanding Business Valuation</em>. 5th ed. '
                        'AICPA.',
 'disc_biblio_pepperdine': 'Pepperdine Private Capital Markets Report (2024).',
 'disc_biblio_vfb': 'VFB Belgium – Private Company Valuation Data (2024).',
 'disc_biblio_ibba': 'IBBA Market Pulse Survey (2024).',
 'disc_biblio_ivs': 'International Valuation Standards (IVS) 2022, IVSC.',
 'disc_biblio_vlerick': 'Vlerick Business School – Belgian SME Benchmark Data.',
 'disc_biblio_mercer': 'Mercer Capital (2017) — <em>Discount for Lack of Marketability &amp; '
                       'Discount for Lack of Control</em>: typical M&A haircut bands (DLOC 10–25%, '
                       'DLOM 15–35%).',
 'disc_biblio_marktlink': 'Marktlink + Vlerick (2024) — Belgian SME multiples handbook; peer-set '
                          'calibration for the EV/EBITDA multiple by sector × revenue band × '
                          'region.',
 'disc_biblio_asset_nav': 'NAV / adjusted net asset value — balance-sheet substance, fair-value '
                          'adjustments and deferred tax effects as a documented asset approach.',
 'disc_biblio_yield_income': 'Income-capitalisation approach — sustainable net rent, cap rate and '
                             'NAV floor as the real-estate-led valuation framework.',
 'disc_biblio_startup_intro': 'Startup track (pre-revenue) — applied when the active method is '
                              '<em>startup_valuation</em>. The methodology is grounded in the '
                              'following venture- and pre-seed-specific sources:',
 'disc_biblio_berkus': 'Berkus, D. (1996, revised 2016/2024). <em>The Berkus Method — Valuing the '
                       'Early Stage Investment</em>.',
 'disc_biblio_payne': 'Payne, B. (2024). <em>Scorecard Valuation Methodology</em>. Angel Capital '
                      'Association.',
 'disc_biblio_sahlman': 'Sahlman, W. A. (1989, revised). <em>The Venture Capital Method</em>. '
                        'Harvard Business School Note 9-288-006.',
 'disc_biblio_strebulaev': 'Strebulaev, I. (2024). <em>The Venture Mindset</em>. Stanford GSB / '
                           'Portfolio.',
 'disc_biblio_atomico': 'Atomico (2024). <em>State of European Tech 2024</em> — Benelux pre-seed '
                        'dataset.',
 'disc_biblio_dealroom': 'Dealroom (2024). <em>Benelux Venture Capital Report 2024</em> — round '
                         'size and valuation distributions.',
 'disc_biblio_insead_lbs': 'INSEAD (2023) &amp; London Business School (2024). <em>Founder–Market '
                           'Fit and Pedigree Premia in European Pre-Seed</em>.',
 'disc_biblio_index_p9': 'Index Ventures, Point Nine, Seedcamp (2025). <em>SaaS Forward Multiple '
                         'Method — Practitioner Guide</em>.',
 'disc_preparer_override_title': 'Preparer multiple adjustment',
 'disc_preparer_override_template': 'A baseline EV/EBITDA multiple of {baseline}× was used from '
                                    'the resolved benchmark contract. The preparer applied a '
                                    '{adjustment_label} of {delta_abs}× (applied multiple '
                                    '{applied}×). Justification: {reason}.',
 'preparer_adjustment_premium': 'premium',
 'preparer_adjustment_discount': 'discount',
 'preparer_reason_strategic_buyer_premium': 'strategic buyer premium',
 'preparer_reason_exceptional_management_premium': 'exceptional management premium',
 'preparer_reason_key_person_discount': 'key person / dependency discount',
 'preparer_reason_real_estate_included': 'real estate included',
 'preparer_reason_customer_concentration': 'customer concentration',
 'preparer_reason_distressed_sale': 'distressed or forced sale',
 'preparer_reason_recurring_revenue_premium': 'recurring revenue premium',
 'preparer_reason_other': 'other (see workpapers)',
 'attestation_title': 'Attestation & signature',
 'attestation_intro': 'The undersigned confirms having reviewed the input data, method selection, '
                      'arithmetic reconciliation and limitations of this report. The calculations '
                      'shown are reproducible from the available source data to the extent that '
                      'the submitted source data is complete and accurate. The valuation has been '
                      'prepared using generally accepted valuation methods and the professional '
                      'judgement of the undersigned regarding sector-specific multiples, '
                      'normalisation adjustments and synthesis weights.',
 'attestation_intro_asset': 'The undersigned confirms having reviewed the input data, method '
                            'selection, arithmetic reconciliation and limitations of this report. '
                            'The calculations shown are reproducible from the available source '
                            'data to the extent that the submitted source data is complete and '
                            'accurate. The valuation has been prepared using generally accepted '
                            'valuation methods and the professional judgement of the undersigned '
                            'regarding balance-sheet substance, documented NAV adjustments and '
                            'deferred tax effects.',
 'attestation_intro_yield': 'The undersigned confirms having reviewed the input data, method '
                            'selection, arithmetic reconciliation and limitations of this report. '
                            'The calculations shown are reproducible from the available source '
                            'data to the extent that the submitted source data is complete and '
                            'accurate. The valuation has been prepared using generally accepted '
                            'valuation methods and the professional judgement of the undersigned '
                            'regarding sustainable net rent, cap rate, NAV floor and balance-sheet '
                            'adjustments.',
 'attestation_caveat': 'This signature confirms the review performed; it does not release the '
                       'parties from their own due diligence obligations and does not guarantee '
                       'the eventual transaction price.',
 'attestation_preparer_role': 'On behalf of the preparer',
 'attestation_client_role': 'On behalf of the client',
 'attestation_signature_label': 'Name & signature',
 'attestation_date_label': 'Date',
 'sotp_trigger_title': 'Group structure: Sum-of-the-Parts valuation required',
 'sotp_trigger_text': 'This entity is part of a group structure (operating holding or real-estate '
                      'company). The stand-alone valuation alongside is a useful diagnostic, but '
                      'the transaction-grade value of the group requires a Sum-of-the-Parts '
                      '(SOTP): each participation and real-estate entity valued separately, with '
                      'ownership percentages, minority interests and intercompany eliminations. '
                      'Where stand-alone equity comes out low or negative, that typically reflects '
                      'debt funded against assets held outside this entity — not a low underlying '
                      'value.'}
