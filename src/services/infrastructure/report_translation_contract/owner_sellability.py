"""Owner profiling, sellability, and waterfall contract fields."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.services.infrastructure.report_step_names import CALC_STEP_NAMES_NL as _CALC_STEP_NAMES_NL


@dataclass(frozen=True)
class ReportTranslationOwnerSellabilityFields:
    # SELLABILITY-MVP (BET-204) — section in the main report.
    #
    # Caregiver-tone copy per the A0 brand-voice baseline (drafted with
    # Janaina, ex-Unilever brand director). No superlatives ("best",
    # "only", "leading" are forbidden — see banned-words.txt). Every
    # band / confidence / state has a calm, on-the-owner's-side phrasing.
    # ───────────────────────────────────────────────────────────────────
    sellability_section_title: str = "Verkoopbaarheid"
    sellability_section_subtitle: str = (
        "Wat zou uw waarde verhogen — concreet en in € becijferd tegen de "
        "huidige sectormultiples."
    )
    sellability_score_label: str = "Sellability-score"
    sellability_confidence_high: str = "Hoge zekerheid"
    sellability_confidence_med: str = "Middelmatige zekerheid"
    sellability_confidence_low: str = "Lage zekerheid"
    # 4 band labels + caregiver-tone advice. These mirror the Mercury
    # OwnerSummary section copy — drift is caught by the cross-app
    # i18n-parity test on the Mercury side.
    sellability_band_significant_label: str = "Nog veel werk aan de winkel"
    sellability_band_significant_advice: str = (
        "Een koper zou vandaag echte risico's zien. Het goede nieuws: elk "
        "daarvan is haalbaar in een voorbereidingsperiode van 12 tot 18 "
        "maanden."
    )
    sellability_band_foundations_label: str = "Basis is gelegd"
    sellability_band_foundations_advice: str = (
        "Het fundament staat. Een gerichte inspanning op enkele punten zou "
        "dit aanzienlijk verhogen voor een verkoop."
    )
    sellability_band_sale_ready_in_most_label: str = "Grotendeels verkoopklaar"
    sellability_band_sale_ready_in_most_advice: str = (
        "U bent dichtbij. De hefbomen hieronder zijn het verschil tussen het "
        "cijfer van vandaag en wat een doordachte koper zou betalen."
    )
    sellability_band_sale_ready_today_label: str = "Vandaag verkoopklaar"
    sellability_band_sale_ready_today_advice: str = (
        "Uw zaak presenteert zich goed. Bij de juiste timing kunt u nu een " "proces starten."
    )
    # Factor labels — render in the breakdown table + lift cards.
    sellability_factor_owner_dependence: str = "Afhankelijkheid van de eigenaar"
    sellability_factor_customer_concentration: str = "Klantconcentratie"
    sellability_factor_revenue_quality: str = "Kwaliteit van de omzet"
    sellability_factor_financial_cleanliness: str = "Ordelijke boekhouding"
    sellability_factor_growth_trend: str = "Groeitrend"
    sellability_factor_transferability: str = "Overdraagbaarheid"
    # Factor breakdown — per-factor caregiver-tone explanations
    # (one line each, ticket A1 / report integration). These render
    # alongside the bars on Page 1 top.
    sellability_factor_breakdown_heading: str = "Hoe uw zaak scoort"
    sellability_factor_breakdown_subheading: str = (
        "Zes factoren die kopers wegen, in één oogopslag."
    )
    sellability_factor_owner_dependence_explanation: str = (
        "Hoe goed loopt de zaak zonder u — sleutels, klantrelaties en kennis."
    )
    sellability_factor_customer_concentration_explanation: str = (
        "Wat kopers zien als concentratierisico op uw top-3 klanten."
    )
    sellability_factor_revenue_quality_explanation: str = (
        "Hoeveel van uw omzet jaarlijks terugkomt zonder dat u opnieuw moet verkopen."
    )
    sellability_factor_financial_cleanliness_explanation: str = (
        "Of een koper de boeken kan vertrouwen zonder forensisch werk."
    )
    sellability_factor_growth_trend_explanation: str = (
        "Of de zaak vooruitgaat — omzet en marge over de laatste jaren."
    )
    sellability_factor_transferability_explanation: str = (
        "Hoe makkelijk de zaak in andere handen kan overgaan — vergunningen, contracten, processen."
    )
    # Panel headings.
    sellability_top_lifts_heading: str = "Wat zou uw waarde verhogen"
    sellability_top_lifts_subheading: str = (
        "Drie dingen die het cijfer bewegen, in € becijferd tegen de " "huidige sectormultiples."
    )
    sellability_tertiary_lifts_heading: str = "Andere mogelijke hefbomen"
    sellability_tertiary_lifts_subheading: str = (
        "De moeite waard, maar we hebben meer informatie over uw zaak nodig "
        "om deze accuraat in € te kwantificeren."
    )
    # Empty states.
    sellability_skipped_title: str = "Verkoopbaarheidsscore overgeslagen"
    sellability_skipped_body: str = (
        "Vul uw eigenaarsprofiel aan om uw Sellability-score te ontgrendelen. "
        "Zo onderbouwt u de waardering scherper en verklaart u overdraagbaarheid "
        "duidelijker. De score laat zien wat een koper concreet zou willen zien voor de "
        "verkoop, en in € becijferd wat elke verbetering kan opleveren."
    )
    sellability_low_confidence_heading: str = "Vertel ons iets meer over uw zaak"
    sellability_low_confidence_body: str = (
        "Vul uw eigenaarsprofiel aan en voer een volledige waardering uit. "
        "Zo wordt de waardering beter onderbouwd en wordt overdraagbaarheid duidelijker "
        "— zodra we genoeg gegevens hebben om de cijfers te onderbouwen, becijferen we "
        "de hefbomen in € tegen uw sectormultiples."
    )
    sellability_sale_ready_empty_heading: str = "Uw zaak staat er goed voor."
    sellability_sale_ready_empty_body: str = (
        "Op de score is er niets materieels meer te verbeteren. Wanneer u "
        "klaar bent, kunnen we het verkoopproces voorbereiden — dat is werk "
        "van een andere aard, en daar begeleiden we u graag in."
    )
    # Provenance footer.
    sellability_provenance_native: str = "Becijferd tegen de sectormultiples van uw land."
    sellability_provenance_aggregate_clone: str = (
        "Becijferd tegen een nauw verwante sector in uw land."
    )
    sellability_provenance_aggregate: str = (
        "Becijferd tegen een bredere sectorbenchmark — lokale data wordt " "nog verzameld."
    )

    # Section-close footer — caregiver-tone close + invite-accountant CTA.
    # The close line lands at the bottom of the report's sellability
    # section regardless of state; the invite CTA only renders when the
    # request supplies an `invite_accountant_cta_url` in metadata.
    sellability_close_caregiver: str = (
        "Dit is een momentopname. De echte waarde ontstaat in het werk "
        "tussen vandaag en uw uittreding."
    )
    sellability_invite_accountant_heading: str = "Laat uw boekhouder meekijken"
    sellability_invite_accountant_body: str = (
        "Uw boekhouder kent uw zaak en kan deze score samen met u "
        "kalibreren. Eén klik en zij krijgen toegang."
    )
    sellability_invite_accountant_cta: str = "Mijn boekhouder uitnodigen"

    # Post-Deal swap (OWNER-PROFILING-2): SDE-driven before/after equity
    # break-out. Only rendered when the engine emitted a swap with
    # `applied=true`. The section sits below the dependency adjustment
    # because the two are conceptually distinct: the adjustment captures
    # transition risk, the swap captures the buyer's economic reset.
    owner_profiling_post_deal_section_title: str = "Pre-Deal vs. Post-Deal eigen vermogen"
    owner_profiling_post_deal_section_subtitle: str = (
        "Effect van het vervangen van de huidige eigenaarsbeloning door "
        "een marktconforme manager."
    )
    owner_profiling_post_deal_pre_label: str = "Pre-Deal eigen vermogen"
    owner_profiling_post_deal_post_label: str = "Post-Deal eigen vermogen"
    owner_profiling_post_deal_delta_label: str = "Verschil"
    owner_profiling_post_deal_owner_comp_label: str = "Huidige eigenaarsbeloning"
    owner_profiling_post_deal_market_label: str = "Marktloon vervanger"
    owner_profiling_post_deal_multiple_label: str = "Toegepaste multiple"
    owner_profiling_post_deal_estimated_caveat: str = (
        "Eigenaarsbeloning geschat op basis van omzetheuristieken; geef "
        "werkelijke cijfers op voor cijfers met meer vertrouwen."
    )
    owner_profiling_post_deal_not_applicable_title: str = (
        "Na-deal weergave: niet van toepassing op deze methode"
    )
    owner_profiling_post_deal_not_applicable_body: str = (
        "Vermogen-gebaseerde en startup-waarderingen ontlenen hun waarde "
        "niet aan vervangbare bedrijfsresultaten. De Pre-Deal/Na-deal "
        "swap is hier niet zinvol."
    )

    # Transferability v2 — decomposed advisor view (BET-180 follow-up).
    # Sub-factor labels group the 12 raw factors into 5 chunks an M&A
    # advisor recognises immediately. Buyer-archetype labels name the
    # likely buyer the discount is being defended against.
    owner_profiling_transferability_v2_title: str = "Transferability — gedecomponeerd"
    owner_profiling_transferability_v2_subtitle: str = (
        "De 12-factor analyse opgesplitst in 5 zichtbare drijfveren plus "
        "het waarschijnlijke koperprofiel."
    )
    owner_profiling_subfactor_planning_continuity: str = "Planning & continuïteit"
    owner_profiling_subfactor_relationship_transferability: str = "Overdraagbaarheid van relaties"
    owner_profiling_subfactor_operational_independence: str = "Operationele zelfstandigheid"
    owner_profiling_subfactor_knowledge_codification: str = "Kenniscodificatie"
    owner_profiling_subfactor_brand_independence: str = "Merkonafhankelijkheid"
    owner_profiling_buyer_block_title: str = "Waarschijnlijke koper"
    owner_profiling_buyer_archetype_individual_operator: str = "Individuele exploitant"
    owner_profiling_buyer_archetype_search_fund: str = "Search-fund"
    owner_profiling_buyer_archetype_pe_add_on: str = "PE add-on"
    owner_profiling_buyer_archetype_strategic: str = "Strategisch"
    owner_profiling_buyer_archetype_family_office: str = "Family office"
    owner_profiling_buyer_hours_label: str = "Verwachte inzet"
    owner_profiling_buyer_skill_label: str = "Sectorvaardigheidsmatch"
    owner_profiling_cascade_title: str = "Hoe deze correctie tot stand komt"
    owner_profiling_method_incidence_title: str = "Effect per methode"
    owner_profiling_method_incidence_subtitle: str = (
        "Niet elke methode absorbeert de eigenaarafhankelijkheid in " "gelijke mate."
    )
    owner_profiling_method_col_method: str = "Methode"
    owner_profiling_method_col_coefficient: str = "Coëfficiënt"
    owner_profiling_method_col_applied: str = "Toegepast"
    owner_profiling_method_col_rationale: str = "Reden"
    owner_profiling_method_skips_label: str = "n.v.t."
    owner_profiling_blended_label: str = "Mix-effect over methodes"

    # Severity badge labels (Tier 1..4) — render as "Tier 3 / 4 · Severe"
    owner_profiling_severity_minimal: str = "Minimaal"
    owner_profiling_severity_moderate: str = "Beperkt"
    owner_profiling_severity_severe: str = "Ernstig"
    owner_profiling_severity_extreme: str = "Extreem"
    owner_profiling_severity_tier_label: str = "Tier {tier} / 4"

    # Confidence chip labels + headings
    owner_profiling_confidence_label: str = "Vertrouwensniveau"
    owner_profiling_confidence_high: str = "Hoog"
    owner_profiling_confidence_medium: str = "Gemiddeld"
    owner_profiling_confidence_low: str = "Laag"
    owner_profiling_confidence_coverage_template: str = "{coverage}% factordekking"

    # Hero cascade card — the headline narrative panel that sits at the
    # top of the v2 section. The "kicker" is the small uppercase label
    # above the bold story.
    owner_profiling_hero_kicker: str = "Overdraagbaarheidsverhaal"
    owner_profiling_hero_subtitle: str = (
        "Hoe deze waardering rekening houdt met de overstap van de eigenaar "
        "naar een nieuwe koper."
    )

    # Methodology footnote — tells the buyer or accountant where the
    # numbers come from. Layer labels group citations by what part of
    # the model they back.
    owner_profiling_methodology_title: str = "Methodologie & onderbouwing"
    owner_profiling_methodology_subtitle: str = (
        "Elke laag van het model is gedocumenteerd tegen vakliteratuur "
        "en geaccepteerde marktstandaarden."
    )
    owner_profiling_methodology_layer_decomposition: str = "Decompositie van de afhankelijkheid"
    owner_profiling_methodology_layer_buyer_profile: str = "Koperprofiel"
    owner_profiling_methodology_layer_incidence: str = "Per-methode-incidentie"
    owner_profiling_methodology_layer_severity: str = "Ernst & rauwe correctie"
    # Reader-facing note explaining why citation lines stay in their
    # source language (English) even in NL reports. Without this, a
    # Dutch reader could mistake the English citations for a translation
    # defect; the academic literature is published in English and a
    # paraphrased Dutch citation would weaken defensibility.
    owner_profiling_methodology_source_language_note: str = (
        "Citaten staan in de oorspronkelijke publicatietaal "
        "(doorgaans Engels) ter behoud van academische verifieerbaarheid."
    )

    # SME segment block — formal EU 2003/361 label rendered next to the
    # buyer archetype so the report stays defensible to institutional
    # readers (PE / banks) who use the same scheme.
    owner_profiling_sme_segment_label: str = "EU SME-segment"

    # EU SME segment labels per archetype — formal regulatory taxonomy
    # surfaced next to the buyer block.
    owner_profiling_sme_segment_individual_operator: str = (
        "Micro (EU 2003/361: <10 werknemers, ≤€2M omzet)"
    )
    owner_profiling_sme_segment_search_fund: str = (
        "Klein (EU 2003/361: <50 werknemers, ≤€10M omzet)"
    )
    owner_profiling_sme_segment_pe_add_on: str = (
        "Klein / middelgroot (EU 2003/361: <250 werknemers, ≤€50M omzet)"
    )
    owner_profiling_sme_segment_strategic: str = "Lower mid-market (boven het EU SME-plafond)"
    owner_profiling_sme_segment_family_office: str = "Cross-band (segment hangt af van platformfit)"

    # Buyer-archetype rationale templates. Render at aggregator boundary
    # so the report defends the pick in the active locale. `{eur}` is
    # pre-formatted (e.g. "€250.000").
    owner_profiling_buyer_rationale_individual_operator: str = (
        "Bij {eur} mediaan eigen vermogen bestaat de reële koperspool "
        "uit individuele exploitanten die zichzelf een eigenaar-"
        "exploitantenrol kopen (40 uur/week, beperkte sectorvaardigheid)."
    )
    owner_profiling_buyer_rationale_search_fund: str = (
        "Bij {eur} mediaan eigen vermogen bestaat de reële koperspool "
        "uit search-fund-principalen — first-time operators met hoge "
        "inzet maar beperkte sectordiepte (50 uur/week, gemiddelde "
        "vaardigheidsmatch)."
    )
    owner_profiling_buyer_rationale_pe_add_on: str = (
        "Bij {eur} mediaan eigen vermogen is de reële koper een PE "
        "add-on met operationele infrastructuur al aanwezig (30 uur/"
        "week effectief, hoge vaardigheidsmatch via portfolio-playbooks)."
    )
    owner_profiling_buyer_rationale_strategic: str = (
        "Bij {eur} mediaan eigen vermogen is de reële koper een "
        "strategische verwerver die het bedrijf op een bestaand platform "
        "inpast (15 uur/week effectief, zeer hoge vaardigheidsmatch)."
    )
    owner_profiling_buyer_rationale_family_office: str = (
        "Family office-aanname toegepast; verifieer met de adviseur."
    )
    owner_profiling_buyer_rationale_unknown: str = (
        "Dealgrootte onbekend; standaard zoeker-koper aangenomen "
        "(50 uur/week, gemiddelde sectorvaardigheid) per Pepperdine PCMI."
    )

    # Per-method labels (the 9 valuation methods).
    owner_profiling_method_label_ebitda_multiple: str = "EBITDA-multiple"
    owner_profiling_method_label_dcf: str = "DCF"
    owner_profiling_method_label_sde: str = "SDE-multiple"
    owner_profiling_method_label_revenue_multiple: str = "Omzet-multiple"
    owner_profiling_method_label_arr_multiple: str = "ARR-multiple"
    owner_profiling_method_label_adaptive: str = "Adaptief (gewogen)"
    owner_profiling_method_label_adjusted_nav: str = "Gecorrigeerde NAV"
    owner_profiling_method_label_fiscal_4x: str = "Fiscale 4×"
    owner_profiling_method_label_startup: str = "Startup / VC"

    # Per-method rationale strings — short, advisor-readable, NL.
    owner_profiling_method_rationale_ebitda_multiple: str = (
        "Vergelijkbare bedrijven zijn beheerde ondernemingen; volledige "
        "eigenaar-overgangscorrectie van toepassing."
    )
    owner_profiling_method_rationale_dcf: str = (
        "Kasstroomprojecties veronderstellen continuïteit; volledige " "correctie van toepassing."
    )
    owner_profiling_method_rationale_sde: str = (
        "SDE bevat al de eigenaarsbeloning; alleen de residuele "
        "overdraagbaarheidscorrectie op de multiple is van toepassing (~0,7×)."
    )
    owner_profiling_method_rationale_revenue_multiple: str = (
        "Omzet-multiples leunen op klantenbinding; gedeeltelijke " "correctie (~0,6×)."
    )
    owner_profiling_method_rationale_arr_multiple: str = (
        "ARR-multiples verdisconteren al door eigenaar geleide klant"
        "succes; gedeeltelijk (~0,5×)."
    )
    owner_profiling_method_rationale_adaptive: str = (
        "Adaptief mengt meerdere lenzen; vrijwel volledige correctie " "(~0,85×)."
    )
    owner_profiling_method_rationale_adjusted_nav: str = (
        "NAV gaat over met de activa; eigenaarafhankelijkheid niet van " "toepassing."
    )
    owner_profiling_method_rationale_fiscal_4x: str = (
        "Fiscale 4× is een regelgevend plafond; eigenaarafhankelijkheid " "past dit niet aan."
    )
    owner_profiling_method_rationale_startup: str = (
        "Startup-waardering kijkt vooruit naar team / markt; "
        "eigenaarafhankelijkheid wordt elders gevangen."
    )

    # Inline labels referenced by both report and PDF templates.
    owner_profiling_gap_inline_title: str = "Overdraagbaarheidsgap"
    owner_profiling_weakest_pill: str = "↓ zwakste"
    owner_profiling_strongest_pill: str = "↑ sterkste"

    # Hero "applied" pill at the bottom of the cascade card — the eye-
    # locking headline figure rendered in primary colour.
    owner_profiling_hero_applied_label: str = "Toegepast"
    owner_profiling_hero_blended_label: str = "Mix-effect"

    # Localised unit so the buyer block reads "40 uur/week" in NL and
    # "40 hrs/wk" in EN. Don't use the hero applied label or other
    # hard-coded units in templates.
    owner_profiling_hours_per_week_unit: str = "uur/week"

    # Templated `gap_summary` so the inline gap callout reads in NL.
    # Aggregator interpolates {owner_hours, buyer_hours, hours_gap,
    # skill_gap, severity_localised, raw_pct} at the boundary.
    owner_profiling_gap_summary_template: str = (
        "Eigenaar werkt ~{owner_hours} uur/week vs. koperaanname "
        "~{buyer_hours} uur/week (gap: {hours_gap} uur); "
        "vaardigheidsgap {skill_gap}/100. "
        "Ernst: {severity_localised}; ruwe correctie {raw_pct}."
    )

    # Localised cascade templates — keyed by line type so the renderer
    # can interpolate `cascade_data[i].fields` into the active locale.
    # The English originals also exist for fallback / observability.
    # Severity tokens are localised separately via the severity_* keys
    # so the cascade reads naturally ("ernstig" not "severe") in NL.
    owner_profiling_cascade_owner_template: str = (
        "Eigenaarsprofiel: ~{owner_hours} uur/week, zwakste subfactor is "
        "{weakest_label_lower} (score {weakest_score}/100)."
    )
    owner_profiling_cascade_buyer_template: str = (
        "Waarschijnlijke koper ({buyer_archetype}): ~{buyer_hours} uur/week, "
        "sectorvaardigheidsmatch {buyer_skill}/100."
    )
    owner_profiling_cascade_gap_template: str = (
        "Overdraagbaarheidsgap is {severity_localised}: {hours_gap} uur/week + "
        "{skill_gap}/100 vaardigheid. Ruwe modelcorrectie {raw_pct}."
    )
    owner_profiling_cascade_applied_template: str = (
        "Toegepast {headline_pct}, gemixt over geschikte methodes op " "{blended_pct} effectief."
    )

    # Omni-Calc (single pinned method) — methodology_statement override in reports router
    omni_methodology_statement_dcf: str = (
        "De waardering is gebaseerd op een DCF-analyse waarbij de onderneming "
        "wordt gewaardeerd op basis van de contante waarde van toekomstige vrije "
        "kasstromen, inclusief terminale waarde en WACC als disconteringsvoet."
    )
    omni_methodology_statement_adjusted_nav: str = (
        "De waardering is gebaseerd op de gecorrigeerde netto-actiefwaarde, "
        "waarbij aangepaste activa, passiva en latente lasten de primaire "
        "waardedrijvers vormen in plaats van markt-multiples."
    )
    omni_methodology_statement_fiscal_4x: str = (
        "De historische Belgische fiscale referentiewaarde gebruikt het boekhoudkundig "
        "eigen vermogen plus viermaal de EBITDA van het laatste boekjaar dat vóór "
        "1 januari 2026 werd afgesloten. Ze bepaalt een waarde op 31 december 2025 "
        "en is geen waardering voor verkoop, successie of interne overdracht."
    )

    # DCF historical FCF readiness (footnotes)
    dcf_readiness_note_imported_ready: str = (
        "Historische dekking voor de DCF: effectieve CapEx in {capex_years} jaren, "
        "belastinglast in {tax_years} jaren en jaarlijkse ΔNWC in {nwc_years} jaren."
    )
    dcf_readiness_note_partial: str = (
        "De DCF gebruikt geïmporteerde inputs voor CapEx ({capex_years}), belastingen ({tax_years}) "
        "en werkkapitaal ({nwc_years}), maar valt nog deels terug op aannames waar de historie onvolledig is."
    )
    dcf_readiness_note_manual_fallback: str = (
        "De DCF draait hoofdzakelijk op fallback-aannames omdat historische vrije-kasstroomdetail nog beperkt is."
    )
    dcf_readiness_note_explicit_fcff: str = (
        "De DCF gebruikt {forecast_years} expliciet opgegeven en in de verzegelde run "
        "vastgelegde FCFF-prognosejaren. Historische CapEx-, belasting- en "
        "werkkapitaalgegevens worden niet als vervanging in deze kasstromen verwerkt."
    )
    dcf_missing_field_label_capex: str = "CapEx"
    dcf_missing_field_label_tax: str = "belastinglast"
    dcf_missing_field_label_nwc: str = "werkkapitaalbeweging"

    # Trial-balance anomaly — one-line executive summary (when a primary flag exists)
    anomaly_summary_template: str = (
        "Statistische anomalie gedetecteerd in rekening {account} voor {year}{direction_clause}."
    )

    # Waterfall charts — SVG compact labels (multiple + valuation waterfalls)
    wf_compact_database_p50: str = "Database P50"
    wf_compact_market_median: str = "Marktmediaan"
    wf_compact_sme_calib: str = "KMO-kalib."
    wf_compact_key_person: str = "Sleutelpers."
    wf_compact_size: str = "Omvang"
    wf_compact_other_adj: str = "Overig"
    wf_bs_debt: str = "Schuld corr."
    wf_bs_asset: str = "Actief corr."
    wf_bs_provision: str = "Voorz."
    wf_bs_tax: str = "Belasting corr."
    wf_bs_cash: str = "Kas corr."
    wf_bs_working_capital: str = "WC corr."
    wf_bs_other: str = "Balans"

    # EUR valuation waterfall (metric → EV → equity)
    wf_basis_revenue: str = "Omzet"
    wf_basis_sde: str = "Gewogen SDE"
    wf_basis_sde_short: str = "SDE"
    wf_basis_ebitda: str = "Genormaliseerde EBITDA"
    wf_basis_ebitda_short: str = "Norm. EBITDA"
    wf_applied_multiple: str = "Toegepaste multiple"
    wf_applied_multiple_short: str = "Toegepast"
    wf_bridge_multiple_short: str = "Multiple"
    wf_enterprise_value: str = "Ondernemingswaarde"
    wf_excess_cash: str = "Overtollige kas"
    wf_excess_cash_short: str = "Overtol. kas"
    wf_cash_equivalents: str = "Kas & kasequivalenten"
    wf_cash_short: str = "Kas"
    wf_financial_debt: str = "Financiële schuld"
    wf_debt_short: str = "Schuld"
    wf_net_cash: str = "Netto kas"
    wf_net_debt: str = "Netto schuld"
    wf_balance_sheet_fallback: str = "Balanscorrectie"
    wf_equity_value: str = "Aandelenwaarde"
    wf_equity_short: str = "Eigen verm."
    wf_tax_latency_short: str = "Latenties"
    wf_nwc_short: str = "NWC"

    # EBITDA adjustment table (Page 3) — reported vs normalized & metadata-driven rows
    adj_reported_ebitda_year: str = "Gerapporteerde EBITDA ({year})"
    adj_normalized_ebitda_year: str = "Genormaliseerde EBITDA ({year})"
    adj_fallback_label: str = "Aanpassing"
    adj_submitted_metadata: str = "Aangeleverde metadata"
    adj_total_normalization_label: str = "Totale normalisatie-aanpassingen"
    adj_auto_desc_count_template: str = "{count} normalisatie(s) uit aangeleverde metadata"
    adj_auto_desc_aggregate: str = "Normalisatiedelta uit aangeleverde metadata"

    # Pipeline / transparency fallbacks
    report_unknown_stage_label: str = "Onbekend"
    calc_step_names: tuple[str, ...] = field(default_factory=lambda: _CALC_STEP_NAMES_NL)
    calc_step_generic: str = "Stap {n}"

    # Primary methodology display (cover / context — distinct from internal methodology keys)
    val_method_display_hybrid: str = "Hybride (Multiples + DCF)"
    val_method_display_dcf: str = "DCF-analyse"
    val_method_display_multiples_ebitda: str = "Marktmultiples (EV/EBITDA)"
    val_method_display_multiples_revenue: str = "Marktmultiples (EV/Revenue)"
    # Asset-anchored methodologies — for holdings (NAV) and real estate (yield).
    # Surface separately from market-multiples so the cover / synthesis pages
    # don't read "EV/EBITDA" on a balance-sheet-driven valuation.
    val_method_display_asset: str = "Substantie-waardering (NAV)"
    val_method_display_yield: str = "Vastgoed yield (huur ÷ cap-rate)"
