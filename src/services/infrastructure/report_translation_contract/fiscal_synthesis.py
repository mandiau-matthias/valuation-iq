"""Fiscal, synthesis, calibration, and methodology contract fields."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReportTranslationFiscalSynthesisFields:
    # =========================================================================
    # FALLBACK MESSAGES (~5 strings)
    # =========================================================================

    adj_no_adjustments: str
    exec_no_benchmarks: str
    exec_reference_without_benchmark_table: str
    ebitda_single_year_note: str
    ebitda_no_multi_year: str
    warning_zero_ebitda: str
    warning_missing_revenue: str

    # =========================================================================
    # CALIBRATION LEDGER COMPONENT (~15 strings)
    # =========================================================================

    ledger_step_column: str
    ledger_multiple_column: str
    ledger_impact_column: str
    ledger_ev_column: str
    ledger_ref_column: str
    ledger_market_consensus: str
    ledger_market_consensus_desc: str
    ledger_key_person_risk: str
    ledger_micro_sme_discount: str
    ledger_tier_label: str
    ledger_dlom: str
    ledger_dlom_desc: str
    ledger_conclusion: str
    ledger_enterprise_value: str
    ledger_multiple_label: str
    ledger_ev_short: str  # Compact for conclusion row (A4 fit)
    # Asset/yield relabels for the conclusion row + waterfall start node so a
    # NAV/income figure is never labelled a bare "EV" (panel D1/D2 major).
    ledger_substance_short: str
    ledger_property_value_short: str
    ledger_net_cash_short: str
    ledger_net_debt_short: str
    ledger_equity_short: str
    ledger_equity_adjusted_parenthetical: str  # "Gecorrigeerd Netto Actief" for compact conclusion
    ledger_value_label: str
    ledger_no_steps: str
    ledger_risk_low: str
    ledger_risk_medium: str
    ledger_risk_high: str
    ledger_risk_label_low: str
    ledger_risk_label_medium: str
    ledger_risk_label_high: str
    ledger_tier_micro: str
    ledger_tier_small: str
    ledger_tier_medium: str

    # =========================================================================
    # FISCAL REFERENCE PAGE (~25 strings)
    # =========================================================================

    fiscal_title: str
    fiscal_subtitle: str
    fiscal_scope_disclaimer: str
    fiscal_calc_title: str
    fiscal_normalized_ebitda_label: str
    fiscal_forfaitaire_multiple_label: str
    fiscal_ebitda_component_label: str
    fiscal_book_equity_label: str
    fiscal_not_provided: str
    fiscal_reference_value_label: str
    fiscal_excl_equity: str
    fiscal_ma_market_value: str
    fiscal_indicative_share_value: str
    fiscal_reference_value_short: str
    fiscal_equity_plus_multiple: str
    fiscal_legal_basis_title: str
    fiscal_legal_intro: str
    fiscal_legal_item_1: str
    fiscal_legal_item_2: str
    fiscal_legal_item_3: str
    fiscal_legal_item_4: str
    fiscal_legal_paragraph: str
    fiscal_legal_footer: str
    fiscal_warning_equity_missing: str
    fiscal_warning_equity_negative: str
    fiscal_warning_prefix: str

    # Fiscal reference — defensibility extensions (peildatum, incomplete-state,
    # intern/extern toggle, holding/werkmaatschappij role, carve-out, anchors)
    fiscal_peildatum_label: str
    fiscal_ebitda_source_label_caption: str
    fiscal_reported_ebitda_label: str
    fiscal_ebitda_used_label: str
    fiscal_statutory_ebitda_caution_title: str
    fiscal_statutory_ebitda_caution_body: str
    fiscal_reported_ebitda_compare_label: str
    fiscal_reference_value_incomplete_label: str
    fiscal_value_incomplete_token: str
    fiscal_value_incomplete_caption: str
    fiscal_value_incomplete_help: str
    fiscal_ebitda_component_only_label: str
    fiscal_internal_transfer_title: str
    fiscal_internal_transfer_body: str
    fiscal_holding_role_warning: str
    fiscal_carve_out_title: str
    fiscal_carve_out_body: str
    fiscal_anchors_acknowledged_text: str
    fiscal_anchors_unacknowledged_text: str

    # ---------------------------------------------------------------------
    # Meerwaarde tax method worksheet and tax impact panel.
    # Defaults provided so legacy callers (e.g. tests) still construct.
    # ---------------------------------------------------------------------
    fiscal_anchors_worksheet_title: str = "Manieren om de waarde te onderbouwen"
    fiscal_anchors_worksheet_intro: str = (
        "De formule wordt automatisch berekend. Een professioneel verslag kan "
        "de formule vervangen. Gebruik alleen methodes met bewijs."
    )
    fiscal_anchors_col_anchor: str = "Methode"
    fiscal_anchors_col_basis: str = "Wettelijke basis"
    fiscal_anchors_col_value: str = "Waarde"
    fiscal_anchor_1_name: str = "Wettelijke formule"
    fiscal_anchor_1_basis: str = "Eigen vermogen + 4 × EBITDA (Art. 102, § 4 WIB 92)"
    fiscal_anchor_2_name: str = "Contractuele formule"
    fiscal_anchor_2_basis: str = (
        "Gedocumenteerde formule in een aandeelhoudersovereenkomst per 31/12/2025"
    )
    fiscal_anchor_3_name: str = "Geldige transactie in 2025"
    fiscal_anchor_3_basis: str = "Objectieve transactie met onafhankelijke derden in 2025"
    fiscal_anchor_4_name: str = "Professioneel verslag"
    fiscal_anchor_4_basis: str = (
        "Gecertificeerd accountant of bedrijfsrevisor die niet de gebruikelijke "
        "adviseur is, uiterlijk 31/12/2027"
    )
    fiscal_anchor_not_applicable: str = "n.v.t."
    fiscal_max_anchor_label: str = "Voorgestelde aanschaffingswaarde 31/12/2025"
    fiscal_max_anchor_caption: str = (
        "Hoogste onderbouwde methode na eventuele vervanging door een professioneel verslag"
    )
    fiscal_acquisition_cost_label: str = "Hogere bewezen historische kostprijs"
    fiscal_acquisition_cost_caption: str = (
        "Alleen gebruikt wanneer deze hoger is dan de onderbouwde methodewaarde"
    )
    fiscal_anchor_winner_chip: str = "Hoogste"
    fiscal_tax_impact_title: str = "Indicatieve belastingdruk meerwaardebelasting"
    fiscal_tax_impact_intro: str = (
        "Bij een latere realisatie boven de aanschaffingswaarde {acq} kan de "
        "bruto meerwaarde worden belast aan 10% (gewone aandelen) of 33% "
        "(interne meerwaarde), afhankelijk van de toepassingsvoorwaarden."
    )
    fiscal_tax_impact_rate_standard: str = "10% — gewone aandelen"
    fiscal_tax_impact_rate_internal: str = "33% — interne meerwaarde"
    fiscal_tax_impact_disclaimer: str = (
        "Indicatief. De effectieve heffing hangt af van het toepasselijk regime "
        "(vrijstelling, familiale overdracht, anti-misbruikregels). Raadpleeg "
        "een fiscaal adviseur voor de definitieve berekening."
    )
    fiscal_ebitda_basis_advisor_chip_statutair: str = "Statutaire EBITDA-basis"
    fiscal_ebitda_basis_advisor_chip_genormaliseerd: str = (
        "Toegepaste EBITDA-basis — afstemmen met jaarrekening"
    )
    # ---- Cover-page meerwaarde-tax variant (NL defaults; EN overrides
    # in the english() classmethod) ----
    # Active when `selected_method == 'fiscal_4x'` AND the forfait
    # headline is computable. The hero number switches from M&A
    # enterprise value to the wettelijke referentiewaarde, with the M&A
    # value preserved as a secondary "marktreferentie" chip.
    cover_fiscal_label: str = "Forfaitaire referentiewaarde"
    cover_fiscal_note: str = (
        "Fiscale referentie volgens Art. 102, § 4 WIB 92. Peildatum {date}"
    )
    cover_fiscal_market_chip: str = "M&A marktreferentie"

    # Valuation Synthesis (Waarderingssynthese)
    synthesis_title: str = "Synthese van de Waardering"
    synthesis_intro: str = (
        "Onderstaande tabel toont de vastgelegde modelweging van meerdere waarderingsmethodes tot één gewogen waarde."
    )
    synthesis_col_method: str = "Methode"
    synthesis_col_value: str = "Berekende Waarde"
    synthesis_col_weight: str = "Gewicht"
    synthesis_col_contribution: str = "Gewogen Bijdrage"
    synthesis_total: str = "Gewogen Waarde"
    synthesis_formula_label: str = "Formule"
    synthesis_justification_label: str = "Motivering van de modelweging"
    synthesis_benchmark_label: str = "UpSwitch Benchmark (ongewogen)"
    synthesis_benchmark_label_weighted: str = "Modelreconciliatie"
    synthesis_benchmark_note: str = (
        "De UpSwitch-marktbenadering is een onafhankelijke referentie die niet wordt beïnvloed door de adviseurweging. Beide worden bewaard voor marktintegriteit."
    )
    synthesis_benchmark_note_weighted: str = (
        "Deze modelreferentie weerspiegelt de reconciliatie voor de geselecteerde methodemix. "
        "Wanneer adviseurgewichten als rekenbasis zijn aanvaard, kan deze gelijk zijn aan de adviseurssynthese."
    )
    disc_academic_review_title: str = "Academische kruiscontrole — review vóór externe verspreiding"
    synthesis_subtitle: str = "Gewogen gemiddelde op basis van geselecteerde waarderingsmethodes"
    synthesis_info_banner: str = (
        "De adviseur heeft meerdere waarderingsmethodes geselecteerd en een eigen weging toegepast. "
        "Het resultaat is een gewogen gemiddelde dat het professionele oordeel van de adviseur weerspiegelt."
    )
    synthesis_section_composition: str = "Samenstelling"
    synthesis_table_footer_total: str = "Totaal"
    synthesis_adaptive_label: str = "UpSwitch Adaptive"
    synthesis_engine_reference_label: str = "Modelreferentie"
    synthesis_accountant_blend_label: str = "Gewogen modeluitkomst"
    synthesis_disclaimer_title: str = "Opmerking"
    synthesis_disclaimer_body: str = (
        "De gewogen synthese weerspiegelt het professionele oordeel van de adviseur en kan afwijken van het UpSwitch Adaptive resultaat. De individuele methodewaarden zijn indicatief en afhankelijk van de beschikbare invoergegevens."
    )
    synthesis_disclaimer_body_weighted: str = (
        "De gewogen synthese weerspiegelt het professionele oordeel van de adviseur. "
        "De modelreferentie wordt apart bewaard wanneer beschikbaar; individuele methodewaarden zijn indicatief en afhankelijk van de beschikbare invoergegevens."
    )
    # Weighted synthesis: formula line + method labels (engine defaults are mixed NL/EN)
    synthesis_weight_total_percent: str = "100%"
    synthesis_formula_term_template: str = "({amount} × {pct}%)"
    synthesis_formula_plus: str = " + "
    synthesis_formula_result_template: str = " = {amount}"
    synthesis_method_ebitda_multiple: str = "EBITDA-multiple"
    synthesis_method_dcf: str = "Verdisconteerde kasstromen (DCF)"
    synthesis_method_sde: str = "SDE-multiple"
    synthesis_method_revenue: str = "Omzetmultiple"
    synthesis_method_arr: str = "SaaS-marktaanpak (EV/ARR)"
    synthesis_method_adjusted_nav: str = "Gecorrigeerde NAV (Intrinsieke Waarde)"
    synthesis_method_fiscal_4x: str = "Fiscale referentiewaarde (4× EBITDA)"
    synthesis_method_upswitch_adaptive: str = "UpSwitch Adaptive"
    synthesis_method_upswitch_adaptive_balance_sheet: str = "UpSwitch Adaptive (balans primair)"
    synthesis_apv_value_basis: str = "APV-brug"
    synthesis_apv_bridge_label: str = "CW belastingschild schulden"
    synthesis_apv_bridge_note: str = (
        "DCF omvat de afzonderlijk verdisconteerde APV-belastingschilden uit de klanttemplate."
    )
    synthesis_apv_bridge_generic_note: str = (
        "DCF omvat afzonderlijk verdisconteerde APV-belastingschilden uit expliciete invoer."
    )
    synthesis_net_engine_value_basis: str = "Netto modelwaarde"
    synthesis_net_engine_note: str = (
        "Deze bijdrage gebruikt de gekalibreerde netto multiple-waarde na standaard risico- en "
        "illiquiditeitscorrecties."
    )

    # Manual method override (accountant-selected method vs UpSwitch Adaptive)
    method_override_title: str = "Waardering op basis van handmatige keuze"
    method_override_subtitle_screen: str = (
        "De adviseur heeft handmatig een waarderingsmethode geselecteerd."
    )
    method_override_subtitle_pdf: str = (
        "De adviseur heeft handmatig een waarderingsmethode geselecteerd ter vervanging van het "
        "UpSwitch Adaptive resultaat."
    )
    method_override_info_banner: str = (
        "Dit rapport toont de vastgelegde waarderingsmethode. "
        "De UpSwitch Adaptive waarde wordt ter vergelijking weergegeven."
    )
    method_override_selected_method_heading: str = "Geselecteerde methode"
    method_override_col_method: str = "Methode"
    method_override_col_manual_value: str = "Handmatige waarde"
    method_override_row_adaptive_reference: str = "UpSwitch Adaptive waarde"
    method_override_adaptive_subcaption: str = "Modelgeselecteerde methode"
    method_override_label_manual_choice: str = "Handmatige keuze"
    # M&A defensibility: explicit % delta between manual choice and adaptive
    # reference so reviewers don't have to compute it mentally. Direction-aware.
    method_override_delta_label: str = "Afwijking t.o.v. UpSwitch Adaptive"
    method_override_delta_premium: str = "+{percent}% boven adaptive referentie"
    method_override_delta_discount: str = "−{percent}% onder adaptive referentie"
    method_override_delta_match: str = "binnen 0,5% van de adaptive referentie"
    # Cover page badge — fires when an explicit method override is in effect
    # so the buyer sees the manual selection on the very first page.
    cover_manual_override_badge: str = "Handmatige methode-override"
    method_override_section_rationale: str = "Verantwoording"
    method_override_reason_label: str = "Reden:"
    method_override_note_label: str = "Toelichting:"
    method_override_recorded_on: str = "Vastgelegd op:"
    method_override_disclaimer_screen: str = (
        "De handmatige selectie weerspiegelt het professionele oordeel van de adviseur en kan afwijken "
        "van het UpSwitch Adaptive resultaat."
    )
    method_override_disclaimer_pdf: str = (
        "De handmatige selectie weerspiegelt het professionele oordeel van de adviseur en kan afwijken "
        "van het UpSwitch Adaptive resultaat. Beide waarden zijn berekend op basis van dezelfde "
        "genormaliseerde invoergegevens."
    )
    method_override_reason_fiscal_compliance: str = "Fiscale naleving"
    method_override_reason_asset_heavy_business: str = "Activa-zwaar bedrijf"
    method_override_reason_internal_transfer: str = "Interne overdracht"
    method_override_reason_conservative_anchor: str = "Conservatief anker"
    method_override_reason_client_preference: str = "Voorkeur klant"
    method_override_reason_regulatory_requirement: str = "Regelgevende vereiste"
    method_override_reason_other: str = "Overig"

    # DCF flat projection warning
    dcf_flat_projection_note: str = (
        "De prognoses gebruiken een constant groeipercentage en een constante EBITDA-marge "
        "over de gehele projectieperiode. Bij een rijpend bedrijf is het gebruikelijk dat "
        "de omzetgroei geleidelijk afneemt terwijl de winstmarge verbetert door schaaleffecten."
    )

    # DCF historical FCF footnote (missing field names)
    dcf_historical_fcf_missing_fields_prefix: str = "Ontbreekt nog:"
    dcf_historical_fcf_readiness_heading: str = "Historische FCF-gereedheid"

    # Working capital & market inputs (NWC / DCF provenance panels)
    nwc_normalization_title: str = "Normalisatie werkkapitaal"
    nwc_normalization_explanation_fallback: str = (
        "Historische werkkapitaalratio’s werden vergeleken met de laatste balans om een surplus of tekort "
        "in werkkapitaal te bepalen."
    )
    nwc_label_target_nwc: str = "Doel-NWC"
    nwc_label_actual_nwc: str = "Actueel NWC"
    nwc_label_bridge_impact: str = "Impact op brug"
    nwc_label_years_analyzed: str = "Geanalyseerde jaren"
    market_provenance_title: str = "Herkomst marktdata"
    market_label_risk_free_rate: str = "Risicovrije rente"
    market_label_source: str = "Bron"
    market_label_manual_override: str = "Handmatige aanpassing"
    market_label_applied: str = "Toegepast"
    market_label_equity_risk_premium: str = "Aandelenrisicopremie"
    market_label_erp_source: str = "ERP-bron"
    market_label_gdp_growth: str = "BBP-groei"
    market_label_as_of: str = "Peildatum"

    # Trial-balance anomaly summary
    anomaly_detection_title: str = "Statistische anomaliedetectie"
    anomaly_label_account: str = "Rekening"
    anomaly_label_year: str = "Jaar"
    anomaly_label_z_score: str = "Z-score"
    anomaly_label_confidence: str = "Betrouwbaarheid"
    anomaly_label_suggested_normalization: str = "Voorgestelde normalisatie"
    anomaly_scan_payload_missing: str = (
        "De anomalie-scan was beschikbaar in de waarderingsworkflow, maar de finale rapportpayload bevatte "
        "geen bruikbare anomalievlag."
    )
    # Round-10 audit: human-readable severity tier next to the raw
    # `z_score` so M&A reviewers don't have to remember the thresholds.
    # Tiers (NIST anomaly-detection convention):
    #   |z| ≥ 3 → critical · |z| ≥ 2 → severe · |z| ≥ 1 → moderate
    anomaly_label_severity: str = "Ernst"
    anomaly_severity_critical: str = "Kritiek"
    anomaly_severity_severe: str = "Significant"
    anomaly_severity_moderate: str = "Matig"
    anomaly_severity_low: str = "Laag"

    # DCF sensitivity matrix (caption under title; axis-specific)
    dcf_sensitivity_matrix_caption_terminal: str = (
        "Ondernemingswaarde, compact weergegeven, bij variaties in WACC en terminale groei."
    )
    dcf_sensitivity_matrix_caption_exit_multiple: str = (
        "Ondernemingswaarde, compact weergegeven, bij variaties in WACC en exit multiple."
    )

    # SaaS appendix — unit suffix for net expansion spread (percentage points)
    saas_appendix_spread_points_suffix: str = "ppts"

    # SDE waterfall (micro-SME) — component labels in executive / bridge tables
    sde_component_owner_salary_label: str = "Eigenaarssalaris correctie"
    sde_component_total_label: str = "SDE Totaal"

    # Data quality / executive summary — short labels for the "inputs available" chip list
    data_inputs_normalizations_label: str = "Normalisaties"
    data_inputs_comparable_transactions_label: str = "Vergelijkbare transacties"

    # Data quality / confidence badge (aligned with pipeline HIGH/MEDIUM/LOW/CRITICAL)
    data_quality_band_high: str = "Hoog"
    data_quality_band_medium: str = "Gemiddeld"
    data_quality_band_low: str = "Laag"
    data_quality_band_critical: str = "Kritiek"

    # When no comparables sample — neutral benchmark source line (not a named database)
    report_benchmark_source_neutral: str = "Sectorbenchmarks"
    # Fallback labels when benchmarks are sourced only from request vs response (aggregator internals)
    report_benchmark_source_request_payload: str = "Aanvraagpayload"
    report_benchmark_source_valuation_response: str = "Waarderingsresponse"

    # Trade register (KVK Netherlands / KBO Belgium) — short names + field labels for cover/context
    report_registry_short_kvk: str = "KVK"
    report_registry_short_kbo: str = "KBO"
    report_registration_number_label_kvk: str = "KVK-nummer"
    report_registration_number_label_kbo: str = "KBO-nummer"

    # Internal report context — multiples row (hybrid vs single) and benchmark median labels
    report_company_name_unknown: str = "Onbekend bedrijf"
    report_multiple_label_prefix_hybrid: str = "Multiples-component"
    report_multiple_suffix_ev_revenue: str = "EV/Revenue"
    report_multiple_suffix_ev_ebitda: str = "EV/EBITDA"
    report_benchmark_median_ev_revenue: str = "Marktmediaan (EV/Revenue)"
    report_benchmark_median_ev_ebitda: str = "Marktmediaan (EV/EBITDA)"

    # Auto-generated methodology paragraph (cover / executive narrative)
    methodology_narrative_multiples: str = (
        "De ondernemingswaarde is berekend op basis van de marktbenadering "
        "met behulp van vergelijkbare transactie-multiples ({metric})."
    )
    methodology_narrative_asset: str = (
        "De waardering is substantie-gedreven: het boekhoudkundig eigen vermogen "
        "vormt het vertrekpunt voor de NAV-benadering, met ruimte voor "
        "documenteerbare balanscorrecties en latente belastingimpact."
    )
    methodology_narrative_yield: str = (
        "De waardering is vastgoed-gedreven: de duurzame netto huuropbrengst "
        "wordt gekapitaliseerd via een marktconforme cap-rate, met een "
        "NAV-vloer wanneer de boekwaarde hoger ligt."
    )
    methodology_narrative_dcf_addon: str = (
        "Aanvullend is een DCF-analyse (Discounted Cash Flow) uitgevoerd "
        "om de intrinsieke waarde te valideren."
    )
    methodology_narrative_dcf_weighted: str = (
        "De DCF-analyse (Discounted Cash Flow) is als afzonderlijke gewogen component "
        "opgenomen in de waarderingssynthese."
    )
    methodology_narrative_dcf_primary: str = (
        "De ondernemingswaarde is berekend via de inkomstenbenadering "
        "(Discounted Cash Flow), op basis van de contante waarde van "
        "toekomstige vrije kasstromen."
    )
    methodology_narrative_normalization: str = (
        "De gerapporteerde EBITDA is genormaliseerd voor niet-recurrente "
        "en eigenaarspecifieke kosten om een duurzame winstcapaciteit te bepalen."
    )
    methodology_narrative_owner_dependency: str = (
        "Risicofactoren zoals eigenaarafhankelijkheid zijn gekwantificeerd "
        "en verwerkt in de toegepaste multiple."
    )
    methodology_narrative_fallback: str = (
        "De waardering is gebaseerd op de marktbenadering met {metric}-multiples."
    )

    # OWNER-PROFILING-1 OP-6 — pro-rapport Owner Profiling section.
    # `cap_applied_note` is templated (`{cap_pct}`) so the report displays the
    # MVP floor that was actually applied; never leak `raw_adjustment` without
    # it (SPIKE-1 §5.4 R8). `risk_*` map the engine's discrete risk_level
    # enum to localized chips. `skipped_*` cover the watermark path when the
    # seller bypassed the wizard.
    owner_profiling_section_title: str = "Eigenaarafhankelijkheid"
    owner_profiling_section_subtitle: str = (
        "Kwantitatieve beoordeling van overdraagbaarheid op basis van het " "9-vragen profiel."
    )
    owner_profiling_score_label: str = "Overdraagbaarheidsscore"
    owner_profiling_transferability_label: str = "Overdraagbaarheidsindex"
    owner_profiling_risk_label: str = "Risiconiveau"
    owner_profiling_adjustment_label: str = "Toegepaste waarderingscorrectie"
    owner_profiling_raw_adjustment_label: str = "Pre-cap correctie"
    owner_profiling_cap_applied_note: str = "Cap van {cap_pct}% toegepast"
    owner_profiling_key_risks_title: str = "Belangrijkste overgangsrisico's"
    owner_profiling_recommendations_title: str = "Acties die de overdraagbaarheid verhogen"
    owner_profiling_explanation_title: str = "Beoordelingssamenvatting"
    owner_profiling_disclaimer: str = (
        "Het eigenaarsprofiel is een kwantitatief model van eigenaarafhankelijkheid. "
        "De aanbevelingen zijn illustratief — uitvoeringstiming hangt af van "
        "sector en context."
    )
    owner_profiling_risk_minimal: str = "Minimaal"
    owner_profiling_risk_low: str = "Laag"
    owner_profiling_risk_medium: str = "Gemiddeld"
    owner_profiling_risk_high: str = "Hoog"
    owner_profiling_risk_critical: str = "Kritisch"
    owner_profiling_skipped_title: str = "Eigenaarsprofiel overgeslagen"
    owner_profiling_skipped_body: str = (
        "De 9-vragen vragenlijst is niet ingevuld. De waardering toont de "
        "indicatieve range zonder eigenaarafhankelijkheidscorrectie. Vul de "
        "vragenlijst in om dit cijfer te verfijnen."
    )
    # Advisor-facing CTA on the skipped banner. The Mercury renderer
    # turns `cta_action` into a button that calls the existing
    # remind-owner-to-complete-profile endpoint (Stage-3 BusinessCard).
    # `cta_label` is what the seller / advisor sees; `cta_action` is the
    # canonical action key the renderer wires to its router.
    owner_profiling_skipped_cta_label: str = "Stuur de 9-vragen vragenlijst"
    owner_profiling_skipped_cta_action: str = "send_owner_profiling_invite"
    owner_profiling_skipped_cta_subtext: str = (
        "Dit ontgrendelt de gedrags-eigenaarcorrectie (Damodaran 12-factor) "
        "op de equity-bridge en maakt het rapport audit-bestendig voor "
        "M&A-due-diligence."
    )

    # M&A Owner Risk Ledger — page 4 reconciliation block.
    owner_risk_ledger_title: str = "Eigenaarrisico-reconciliatie"
    owner_risk_ledger_subtitle: str = (
        "Eén auditspoor van álle eigenaargerelateerde kortingen — "
        "structureel (op de multiple) én gedragsmatig (op de equity-brug)."
    )
    owner_risk_ledger_side_multiple: str = "Op de multiple"
    owner_risk_ledger_side_equity: str = "Op de equity-brug"
    owner_risk_ledger_item_label: str = "Post"
    owner_risk_ledger_total_label: str = "Totaal eigenaargerelateerde impact"
    owner_risk_ledger_audit_quality_label: str = "Audit-kwaliteit"
    owner_risk_ledger_audit_defensible: str = "Verdedigbaar (M&A-grade)"
    owner_risk_ledger_audit_heuristic: str = "Alleen heuristisch"
    owner_risk_ledger_heuristic_marker_title: str = "Heuristisch (geen profiel)"
    owner_risk_ledger_profile_marker_title: str = "Afgeleid uit profiel"
    owner_risk_ledger_methodology_title: str = "Methodologie"
    owner_risk_ledger_no_double_count_title: str = "Geen dubbeltelling"
    owner_risk_ledger_basis_label: str = "Basis"
    owner_risk_ledger_unverified_input: str = "Niet-geverifieerde input"

    # ───────────────────────────────────────────────────────────────────
