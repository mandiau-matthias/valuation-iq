"""Transformer and accountant core contract fields."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReportTranslationTransformerAccountantCoreFields:
    # =========================================================================
    # TRANSFORMER STRINGS — produced by Python data builders (NOT in Jinja).
    # These flow into template_data dicts (e.g. valuation_methodologies.overview.methods[*].name,
    # primary_method_label, methodology_description) and must therefore be localized at the
    # data layer.  Namespace: ``transformer_*`` (display labels) and ``methodology_*`` (longer prose).
    # =========================================================================

    # Display labels for valuation methods (short, used as method.name)
    transformer_method_label_market_multiples: str = "Marktmultiples"
    transformer_method_label_dcf: str = "Verdisconteerde kasstromen (DCF)"
    transformer_method_label_ebitda_multiple: str = "EV/EBITDA-multiple"
    transformer_method_label_revenue_multiple: str = "EV/Omzet-multiple"
    transformer_method_label_asset_based: str = "Gecorrigeerde intrinsieke waarde"
    transformer_method_label_hybrid: str = "Hybride waardering"

    # Methodology one-liner descriptions (used as overview.description / methodology_description)
    transformer_methodology_desc_multiples: str = "Waardering op basis van marktmultiples"
    transformer_methodology_desc_dcf: str = "Waardering op basis van verdisconteerde kasstromen"
    transformer_methodology_desc_hybrid: str = (
        "Hybride waardering met {multiples_pct}% multiples en {dcf_pct}% DCF"
    )
    transformer_methodology_desc_default: str = (
        "Waardering op basis van marktmultiples-methodologie"
    )

    # Primary-method explanation strings (used as primary_method_explanation)
    transformer_primary_ebitda_with_value: str = (
        "EV/EBITDA-multiple geselecteerd op basis van positieve EBITDA van €{value}"
    )
    transformer_primary_ebitda_no_value: str = (
        "EV/EBITDA-multiple geselecteerd op basis van positieve EBITDA"
    )
    transformer_primary_revenue: str = (
        "EV/Omzet-multiple geselecteerd vanwege negatieve of nul-EBITDA"
    )
    transformer_primary_dcf: str = (
        "DCF-methode geselecteerd op basis van beschikbare financiële prognoses"
    )
    transformer_primary_method_default: str = (
        "{method} geselecteerd op basis van beschikbare financiële kengetallen"
    )

    # Notice / explanation builders (executive summary)
    transformer_sme_calibration_notice: str = (
        "KMO-multiple-kalibratie toegepast om te corrigeren voor bedrijfsomvang"
    )
    transformer_range_methodology_dispersion: str = (
        "Waarderingsbandbreedte op basis van P25/P50/P75 percentielen uit vergelijkbare ondernemingen"
    )
    transformer_range_methodology_confidence: str = (
        "Waarderingsbandbreedte op basis van betrouwbaarheidsspread rond het middelpunt "
        "(±{spread}% bandbreedte)"
    )
    transformer_range_methodology_dispersion_short: str = (
        "Waarderingsbandbreedte op basis van vergelijkbare ondernemingen"
    )
    transformer_range_methodology_confidence_short: str = (
        "Waarderingsbandbreedte op basis van betrouwbaarheidsspread"
    )
    transformer_range_methodology_dispersion_note: str = (
        "Bandbreedte weerspiegelt de spreiding van marktvergelijkbare ondernemingen"
    )
    transformer_range_methodology_confidence_note: str = (
        "Bandbreedte weerspiegelt onzekerheid op basis van betrouwbaarheid"
    )
    transformer_range_methodology_percentile_short: str = (
        "Bandbreedte op basis van P25/P50/P75 percentielen uit vergelijkbare ondernemingen"
    )
    transformer_range_methodology_confidence_only: str = (
        "Bandbreedte op basis van betrouwbaarheidsspread"
    )

    # Business overview / financial highlights (executive summary)
    transformer_company_overview_template: str = (
        "{company} is een {industry}-onderneming actief in de {country}-markt."
    )
    transformer_company_overview_industry_default: str = "onderneming"
    transformer_company_overview_country_default: str = "lokale"
    transformer_fin_highlights_range: str = (
        "Waarderingsbandbreedte: €{low} - €{high} (middelpunt: €{mid})"
    )
    transformer_fin_highlights_range_unavailable: str = "Waarderingsbandbreedte: niet beschikbaar"
    transformer_fin_highlights_ebitda_suffix: str = ". EBITDA lopend boekjaar: €{value}"
    transformer_fin_highlights_revenue_suffix: str = ". Omzet lopend boekjaar: €{value}"

    # Waterfall / pipeline step explanation fallback
    transformer_waterfall_step_default: str = "{step_name}-correctie toegepast"
    transformer_comparables_count_note: str = (
        "Analyse op basis van {count} vergelijkbare ondernemingen"
    )

    # Information sources transformer
    transformer_info_source_financial_desc: str = (
        "Financiële gegevens lopend boekjaar voor {company}, inclusief omzet, EBITDA "
        "en andere kerncijfers"
    )
    transformer_info_source_current_year_statements: str = "Jaarrekening lopend boekjaar per {date}"

    # Methodology notes coordinator (longer methodology prose)
    methodology_notes_dcf: str = (
        "De DCF-methodologie projecteert toekomstige kasstromen en disconteert deze naar "
        "contante waarde."
    )
    methodology_notes_multiples: str = (
        "De marktmultiples-methodologie hanteert vergelijkbare ondernemingswaarderingen en "
        "sectorbenchmarks."
    )
    methodology_notes_asset_based: str = (
        "De vermogensgebaseerde methodologie waardeert de onderneming op basis van de "
        "gecorrigeerde intrinsieke waarde (NAV)."
    )
    methodology_notes_market: str = (
        "De marktbenadering gebruikt recente transactiedata en marktvergelijkbare gegevens."
    )
    methodology_notes_income: str = (
        "De inkomstenbenadering kapitaliseert genormaliseerde winst tegen een passend rendement."
    )
    methodology_notes_cost: str = (
        "De kostenbenadering waardeert de onderneming op basis van de kosten om vergelijkbare "
        "operaties opnieuw op te bouwen."
    )
    methodology_notes_hybrid: str = (
        "De hybride methodologie combineert meerdere waarderingsbenaderingen voor een "
        "uitgebreide analyse."
    )
    methodology_notes_default: str = "Professionele waarderingsmethodologie toegepast."

    # Confidence-level labels (fallback generator)
    transformer_confidence_low_industry: str = "Laag (sectorgemiddelden)"
    transformer_confidence_medium_industry: str = "Gemiddeld (sectorgemiddelden)"
    transformer_confidence_medium_high_industry: str = "Gemiddeld-hoog (sectoranalyse)"

    # Aggregator validation / optional warnings (logging + context notes)
    report_validation_missing_recommended: str = "Ontbrekend aanbevolen: {field}"
    report_validation_required_zero: str = (
        "{field} (nulwaarde — pipeline heeft geen resultaat opgeleverd)"
    )
    report_validation_registry_unavailable: str = "{registry}-gegevens niet beschikbaar ({field})"
    report_validation_no_comparables: str = "Geen vergelijkbare transacties gevonden"
    report_validation_no_benchmark: str = "Geen sectorbenchmark-multiples"
    report_validation_no_dcf_provenance: str = (
        "Geen opgeloste marktdata-herkomst voor DCF- of hybride rapport"
    )

    # Calibration discount waterfall (Step 11 fallback + SME injection)
    calib_wf_market_median_db_p50: str = "Markt Mediaan (Database P50)"
    calib_wf_gross_multiple_before_sme: str = "Bruto-multiple uit marktdata vóór KMO-kalibratie"
    calib_wf_sme_calibration: str = "KMO-Kalibratie"
    calib_wf_sme_calibration_desc: str = "Aanpassing voor klein bedrijf (−{pct}% per Koller et al.)"
    calib_wf_market_consensus_p50: str = "Markt Consensus (P50 Mediaan)"
    calib_wf_not_applicable: str = "Niet van toepassing"
    calib_wf_not_applicable_desc: str = "Break-even of nul-omzet"
    calib_wf_assessment_label: str = "Beoordeling"
    calib_wf_size_discount_suffix: str = "Korting"
    calib_wf_size_discount_desc: str = "Beperkte documentatie, executierisico"
    calib_wf_other_adjustment: str = "Overige Aanpassing"
    calib_wf_other_adjustment_desc: str = "Afronding naar toegepaste multiple"

    # Step 11 discount_waterfall → calibration ledger (NL reports; engine emits English)
    ledger_dw_base_multiple_step3: str = "Basismultiple (stap 3)"
    ledger_dw_initial_multiple_desc_ebitda: str = (
        "Initiële EV/EBITDA-multiple uit sectorbenchmarks en vergelijkbare transacties."
    )
    ledger_dw_initial_multiple_desc_revenue: str = (
        "Initiële EV/omzet-multiple uit sectorbenchmarks en vergelijkbare transacties."
    )
    ledger_dw_initial_multiple_desc_sde: str = (
        "Initiële SDE-multiple uit sectorbenchmarks en vergelijkbare transacties."
    )
    ledger_dw_size_discount: str = "Omvangskorting"
    ledger_dw_liquidity_discount: str = "Illiquiditeitskorting"
    ledger_dw_revenue_trend: str = "Omzetrendement"
    ledger_dw_revenue_trend_desc: str = (
        "Correctie gekoppeld aan de omzetontwikkeling tussen boekjaren."
    )
    ledger_dw_revenue_trend_adjust_template: str = (
        "Omzetrendementscorrectie: {pct}% toegepast op de multiple."
    )
    ledger_dw_owner_concentration: str = "Eigenaarsconcentratie"
    ledger_dw_owner_concentration_note: str = (
        "Correctie voor eigenaarsconcentratie en sleutelpersoonrisico — zie het eigenaarprofiel voor detail."
    )
    ledger_dw_size_discount_note_zero: str = (
        "Geen bijkomende omvangskorting in deze stap (gedeeltelijk verwerkt in de KMO-kalibratie)."
    )
    ledger_dw_liquidity_discount_note_zero: str = (
        "Geen bijkomende illiquiditeitskorting in deze stap (gedeeltelijk verwerkt in eerdere stappen)."
    )
    ledger_dw_size_discount_segment_template: str = "Omvangskorting — segment {tier}{suffix}."
    ledger_dw_size_discount_halved_suffix_template: str = (
        " (gehalveerd met {reduction}% — eigenaarsconcentratie vangt al een deel van het omvangrisico op)"
    )
    ledger_dw_liquidity_discount_private_desc: str = (
        "Illiquiditeitskorting (DLOM) voor niet-beursgenoteerde ondernemingen, "
        "in lijn met restricted-stock studies."
    )
    adaptive_ev_band_card_title: str = "Ondernemingswaarde (EV) — puntschatting"
    adaptive_ev_band_card_subtitle: str = (
        "De middelste rij is de belangrijkste puntschatting. Zonder materiële nettoschuldcorrectie komt dit "
        "in dit dossier typisch overeen met de waarde voor aandeelhouders."
    )

    # =========================================================================
    # ACCOUNTANT VIEW (PDF) — full report templates
    # =========================================================================

    # Cover page
    accountant_cover_report_type: str = "Bedrijfswaarderingsrapport"
    accountant_cover_business_default: str = "Strategische Waarderingsbeoordeling"
    accountant_cover_disclaimer_label: str = "Voorbehoud:"
    accountant_cover_disclaimer_text: str = (
        "Dit rapport biedt een indicatieve waardering op basis van de aangeleverde financiële data. "
        "Conform Belgische en Europese standaarden voor financiële verslaggeving dient dit document als "
        "strategisch instrument voor interne beoordeling en vormt het geen wettelijke controle "
        '("controle legal"), formele fairness opinion of bindend financieel advies binnen het kader '
        "van de regelgeving voor erkende auditors, tenzij uitdrukkelijk ondertekend en bekrachtigd door "
        'een erkend bedrijfsrevisor ("reviseur d\'entreprises" / "bedrijfsrevisor") of accountant '
        '("expert-comptable" / "accountant"). De toegepaste waarderingsmethodes volgen de '
        "standaardkaders van IVS en AICPA, maar mogen niet de enige basis vormen voor investerings- of "
        "desinvesteringsbeslissingen. Upswitch Valuation Services aanvaardt geen aansprakelijkheid voor "
        "beslissingen die uitsluitend op dit strategische rapport zijn gebaseerd."
    )
    accountant_cover_strictly_confidential: str = "Strikt Privé & Vertrouwelijk"
    accountant_cover_generated_on: str = "Opgemaakt op"
    accountant_cover_date_pending: str = "Datum nog te bepalen"
    accountant_cover_reference_id: str = "Referentie-ID"

    # Table of contents
    accountant_toc_title: str = "Inhoud"
    accountant_toc_section_1: str = "Samenvatting"
    accountant_toc_section_1_1: str = "1.1: Strategische Beoordeling & Optimalisatie"
    accountant_toc_section_2: str = "Economische Realiteit (Normalisatie)"
    accountant_toc_section_3: str = "Waarderingsketen (Waterval)"
    accountant_toc_section_4: str = "Operationele Veerkracht & Risico"
    accountant_toc_section_4_1: str = "4.1: Bedrijfsvitaliteitsdashboard"
    accountant_toc_section_4_2: str = "4.2: Datakwaliteit & Compliance"
    accountant_toc_section_5: str = "Strategische Waarderoutekaart"
    accountant_toc_section_6: str = "Technische Bijlagen"
    accountant_toc_appendix_a: str = "A: Detail Financiële Prestaties"
    accountant_toc_appendix_b: str = "B: Beschrijving van de Opdracht"
    accountant_toc_appendix_d: str = "D: Methodologiematrix"
    accountant_toc_appendix_f: str = "F: Standaarden & Voorwaarden"
    accountant_toc_appendix_c: str = "Bijlage C: Informatiebronnen & Datatrouwbaarheid"
    accountant_toc_appendix_e: str = "Bijlage E: Algoritmische Verdedigbaarheid"

    # Executive summary
    accountant_section_executive_summary: str = "Sectie 1 — Samenvatting"
    accountant_exec_intro: str = (
        "Upswitch Valuation Services werd ingeschakeld om de <strong>Reële Marktwaarde (FMV)</strong> "
        'van {company_name} ("de Vennootschap") te schatten per {valuation_date}. '
        "Deze waardering biedt een onafhankelijke, objectieve beoordeling van de ondernemingswaarde "
        "ten behoeve van strategische planning en interne besluitvorming."
    )
    accountant_exec_box_title: str = "Samenvatting"
    accountant_exec_business_value_label: str = "Uw Bedrijfswaarde"
    accountant_exec_range_label: str = "Bandbreedte"
    accountant_exec_valuation_basis_label: str = "Waarderingsbasis"
    accountant_exec_basis_explanation: str = (
        "Aangepast voor bedrijfsomvang, marktomstandigheden en bedrijfsspecifieke risico's"
    )
    accountant_exec_plain_language_label: str = "In begrijpelijke taal:"
    accountant_exec_plain_language_text: str = (
        "Op basis van markttransactiedata van vergelijkbare bedrijven en standaard waarderingsmethodes "
        "is {company_name} ongeveer {value} waard. Deze beoordeling volgt professionele standaarden "
        "(USPAP, IVS) en kan worden gebruikt voor strategische planning, verkoopsonderhandelingen of "
        "interne besluitvorming."
    )
    accountant_exec_range_chart_title: str = "Visualisatie van de waarderingsbandbreedte"
    accountant_exec_estimated_fmv_label: str = "Geschatte Reële Marktwaarde"
    accountant_exec_suggested_listing_price_label: str = "Voorgestelde Vraagprijs:"
    accountant_exec_strategic_buffer: str = "Strategische buffer inbegrepen"
    accountant_exec_implied_multiple_label: str = "Impliciete Multiple"
    accountant_exec_fair_market_value_label: str = "Reële Marktwaarde"

    # Financial analysis (Section 4)
    accountant_section_operational_resilience: str = (
        "Sectie 4 — Operationele Veerkracht & Risicobeoordeling"
    )
    accountant_fa_intro: str = (
        "Deze sectie evalueert de structurele gezondheid en het risicoprofiel van de Vennootschap "
        "via een systematische analyse van historische prestaties, financiële stabiliteit en operationele "
        "kerncijfers. Ons beoordelingskader volgt <strong>IVS 105</strong> en <strong>USPAP Standaard 9</strong> "
        "om operationele risico's die de waarderingsmultiples beïnvloeden te kwantificeren, en biedt zo "
        "kopers een verdedigbare beoordeling van duurzame winstcapaciteit en risicofactoren op "
        "ondernemingsniveau."
    )
    accountant_fa_market_context_label: str = "Marktcontext:"
    accountant_fa_market_context_text: str = (
        "Empirisch onderzoek toont aan dat institutionele kopers systematisch multiplekortingen van "
        "0,3× tot 0,7× toepassen op bedrijven met prestatievolatiliteit of zwakke financiële gezondheid. "
        "Deze sectie identificeert specifieke risicofactoren die due-diligence-teams prioriteren bij de "
        "beoordeling van overnamekandidaten."
    )
    accountant_fa_critical_alerts_title: str = "Kritieke Risicowaarschuwingen"
    accountant_fa_historical_performance_title: str = "4.1 Overzicht Historische Prestaties"
    accountant_fa_historical_intro: str = (
        "Een historische prestatieanalyse legt de empirische basis voor de waardering door groeitrends en "
        "winstgevendheidsstabiliteit te kwantificeren. De samengestelde jaarlijkse groeivoet (CAGR) meet de "
        "duurzame expansiesnelheid, terwijl de EBITDA-marge de operationele efficiëntie en prijszettingsmacht "
        "beoordeelt. Deze indicatoren fungeren als leidende parameters voor de voorspelbaarheid van toekomstige "
        "kasstromen en het ondernemingsrisico."
    )
    accountant_fa_valuation_impact_label: str = "Impact op Waardering:"
    accountant_fa_valuation_impact_text: str = (
        "Een consistente CAGR van 15-25% ondersteunt premiummultiples (1,2× basis), terwijl stabiele "
        "EBITDA-marges van 10-15% wijzen op duurzame winstgevendheid. Afwijkingen leiden tot "
        "risicocorrecties conform de <strong>AICPA BVS-VII</strong>-kaders."
    )
    accountant_fa_data_limitation_title: str = "Beperking van de beschikbare data"
    accountant_fa_data_limitation_text: str = (
        "Analyse gebaseerd op {years} jaar historische data. Standaard waarderingspraktijk beveelt "
        "3-5 jaar aan voor trendanalyse."
    )
    accountant_fa_revenue_cagr_label: str = "Omzet CAGR"
    accountant_fa_revenue_cagr_caption: str = "Geannualiseerd groeipercentage."
    accountant_fa_avg_ebitda_margin_label: str = "Gem. EBITDA-marge"
    accountant_fa_avg_ebitda_margin_caption: str = "Operationele efficiëntie."
    accountant_fa_performance_visualization_title: str = "Prestatievisualisatie"

    # Master valuation waterfall (Section 3)
    accountant_section_valuation_waterfall: str = (
        "Sectie 3 — Waarderingswaterval (Multiplekalibratie)"
    )
    accountant_wf_intro: str = (
        "Dit audittraject toont de <strong>Multiple-First Methodologie</strong> die werd gebruikt om de "
        "intrinsieke waarde af te leiden. We kalibreren de marktmultiple sequentieel om bedrijfsspecifieke "
        "risicofactoren (alpha) te verwerken, waardoor een verdedigbare en transparante overgang van "
        "marktbenchmarks naar reële marktwaarde wordt verzekerd."
    )
    accountant_wf_bridge_title: str = "De Mathematische Brug"
    accountant_wf_bridge_text: str = (
        "Conform <strong>IVS 105</strong> en <strong>USPAP Standaard 10</strong> biedt dit schema de "
        "wiskundige afleiding van de waarde. Door de multiple — en niet de EBITDA — aan te passen, isoleren "
        "we risicofactoren zoals het omvangseffect en illiquiditeit als afzonderlijke variabelen."
    )
    accountant_wf_col_component: str = "Component / Stap"
    accountant_wf_col_equity_value: str = "Eigenvermogenswaarde"
    accountant_wf_col_multiple: str = "Multiple"
    accountant_wf_col_ref: str = "Ref"
    accountant_wf_col_methodology: str = "Methodologie"
    accountant_wf_section_normalization_bridge: str = "Normalisatiebrug"
    accountant_wf_reported_earnings: str = "Gerapporteerde Winst (EBITDA)"
    accountant_wf_as_documented: str = "Zoals gedocumenteerd in financiële stukken"
    accountant_wf_normalized_ebitda: str = "Genormaliseerde EBITDA"
    accountant_wf_representative_earnings: str = "Representatieve winst"
    accountant_wf_margin_suffix: str = "Marge"
    accountant_wf_section_calibration: str = "Waarderingskalibratie (Alpha-factoren)"
    accountant_wf_section_structural: str = "Structurele Aanpassingen"
    accountant_wf_step_market_consensus: str = "Marktconsensus (P50 Mediaan)"
    accountant_wf_step_market_consensus_reason: str = (
        "Niet-aangepaste handelsmultiple afgeleid uit transactiedata."
    )
    accountant_wf_step_sme_calibration: str = "KMO-Marktkalibratie"
    accountant_wf_step_sme_calibration_reason: str = (
        "Kalibratie voor risico van kleine ondernemingen en gebrek aan institutionele liquiditeit."
    )
    accountant_wf_step_quality: str = "Kalibratie Winstkwaliteit"
    accountant_wf_step_quality_reason: str = (
        "Multiple aangepast voor winstvolatiliteit en normalisatiekwaliteit."
    )
    accountant_wf_step_owner: str = "Onsystematisch Risico: Sleutelpersoon"
    accountant_wf_step_owner_reason: str = "Aanpassing voor afhankelijkheid van eigenaar-operator."
    accountant_wf_step_revenue_trend: str = "Omzettrendcorrectie"
    accountant_wf_step_revenue_trend_reason: str = (
        "Korting voor dalende omzet met correlatiebewuste kalibratie. Methodologie houdt rekening met "
        "interactie tussen omvang × omzettrend om over-discounting te vermijden (r ≈ 0,40)."
    )
    accountant_wf_step_size: str = "Premie Omvangseffect"
    accountant_wf_step_size_reason: str = (
        "Premie voor risico's verbonden aan kleinere marktkapitalisatie (Fama-French)."
    )
    accountant_wf_step_liquidity: str = "Illiquiditeitskorting (DLOM)"
    accountant_wf_step_liquidity_reason: str = (
        "Aanpassing voor gebrek aan onmiddellijke verhandelbaarheid."
    )
    accountant_wf_conclusion_label: str = "Conclusie"
    accountant_wf_final_synthesized: str = "Finale gesynthetiseerde waarde"
    accountant_wf_impact_label: str = "Impact"
    accountant_wf_risk_discount: str = "Risicokorting"
    accountant_wf_strength_premium: str = "Sterktepremie"
    accountant_wf_earnings_label: str = "Winst"
    accountant_wf_final_multiple_label: str = "Finale Multiple"
    accountant_wf_intrinsic_value_label: str = "Intrinsieke Waarde"
    accountant_wf_source_registry_title: str = "Bronregister & Academische Citaties"
    accountant_wf_footnote_market_consensus_label: str = "Marktconsensus:"
    accountant_wf_footnote_market_consensus_body: str = (
        "VFB Belgium (2024), Vlerick Business School (2023), Trugman (2017) AICPA."
    )
    accountant_wf_footnote_unsystematic_label: str = "Onsystematisch Risico:"
    accountant_wf_footnote_unsystematic_body: str = (
        "Damodaran (2012) Sleutelpersoonrisico, PwC (2024) Waarderingsrichtlijnen."
    )
    accountant_wf_footnote_size_label: str = "Omvangseffect:"
    accountant_wf_footnote_size_body: str = (
        "Ibbotson SBBI (2024), Duff & Phelps (2024), Fama & French (1992). "
        "Geactualiseerd op 2025-12-20 voor verbeterde academische verdedigbaarheid."
    )
    accountant_wf_footnote_illiquidity_label: str = "Illiquiditeit:"
    accountant_wf_footnote_illiquidity_body: str = (
        "Koeplin (2000), Officer (2007) Journal of Financial Economics."
    )
    accountant_wf_footnote_normalization_label: str = "Normalisatie:"
    accountant_wf_footnote_normalization_body: str = (
        "Trugman (2017) p. 287, Pratt & Niculita (2008) Valuing a Business."
    )
    accountant_wf_footnote_revenue_trend_label: str = "Omzettrend (Correlatiebewust):"
    accountant_wf_footnote_revenue_trend_body: str = (
        "Damodaran (2012) aanpassingen voor distressed assets, McKinsey (2015) Hfd. 11 over de impact "
        "van groei/krimp op multiples. Correlatiebewuste kalibratie houdt rekening met de interactie "
        "tussen omvang × omzettrend (r ≈ 0,40) conform de richtlijnen van McKinsey (2015) over "
        "gecorreleerde risicocorrecties. Voorkomt over-discounting wanneer meerdere risicofactoren "
        "tegelijk aanwezig zijn. Verbeterd op 2025-12-20."
    )
    accountant_wf_methodology_note_label: str = "Methodologische opmerking:"
    accountant_wf_methodology_note_body: str = (
        "Dit rapport volgt de Multiple-First-afleiding conform AICPA SSVS Nr. 1 en IVS 105. "
        "Multiples worden sequentieel gekalibreerd om alpha-risicofactoren te isoleren van het "
        "systematisch marktrisico. Verbeterd op 2025-12-20: omzettrendcorrectie toegevoegd en "
        "omvangskorting verhoogd voor verbeterde academische verdedigbaarheid."
    )
    accountant_wf_no_schedule_title: str = "Gedetailleerd schema niet beschikbaar"
    accountant_wf_no_schedule_text: str = (
        "Zorg ervoor dat alle berekeningstappen succesvol werden uitgevoerd."
    )

    # Appendices (Section 6)
    accountant_section_appendices: str = "Sectie 6 — Technische Bijlagen & Onderbouwende Schema's"
    accountant_app_a_title: str = "Bijlage A — Detail Historische Financiële Prestaties"
    accountant_app_a_caption: str = "Detail historische resultatenrekening (€ duizenden)"
    accountant_app_a_metric: str = "Kerncijfer"
    accountant_app_a_revenue: str = "Omzet"
    accountant_app_a_ebitda: str = "EBITDA"
    accountant_app_a_ebitda_margin: str = "EBITDA-marge %"
    accountant_app_a_net_income: str = "Netto-resultaat"
    accountant_app_a_no_data: str = (
        "Gedetailleerde financiële historiek niet aangeleverd voor deze beoordeling."
    )
    accountant_app_b_title: str = "Bijlage B: Beschrijving van de Opdracht"
    accountant_app_b_purpose_label: str = "Doel:"
    accountant_app_b_scope_label: str = "Reikwijdte:"
    accountant_app_b_standard_of_value: str = "Waardestandaard"
    accountant_app_b_premise_of_value: str = "Veronderstelde Premisse"
    accountant_app_b_intended_users_label: str = "Beoogde Gebruikers:"
    accountant_app_d_title: str = "Bijlage D: Methodologiematrix"
    accountant_app_d_col_criteria: str = "Criterium"
    accountant_app_d_col_assessment: str = "Beoordeling"
    accountant_app_d_col_impact: str = "Impact"
    accountant_app_d_cash_flow_visibility: str = "Zichtbaarheid Kasstromen"
    accountant_app_d_cash_flow_assessment: str = "Laag/Matig"
    accountant_app_d_cash_flow_impact: str = "Inkomstenbenadering gewogen op {weight}"
    accountant_app_d_market_comparability: str = "Marktvergelijkbaarheid"
    accountant_app_d_market_assessment: str = "Hoog"
    accountant_app_d_market_impact: str = "Marktbenadering gewogen op {weight}"
    accountant_app_d_synthesis_title: str = "Synthese & Wegingsmotivatie"
    accountant_app_d_synthesis_default: str = (
        "De waarderingssynthese geeft prioriteit aan de Marktbenadering (Multiples) om aansluiting te "
        "verzekeren met de huidige KMO-transactierealiteit en om de speculatieve voorspellingsrisico's "
        "te minimaliseren die inherent zijn aan de Inkomstenbenadering voor bedrijven van deze omvang. "
        "Conform fiduciaire vereisten wordt de Inkomstenbenadering (DCF) gebruikt als secundaire "
        "verificatie of dienovereenkomstig gewogen op basis van de stabiliteit en auditeerbaarheid van "
        "de geprojecteerde kasstromen (Koller et al., 2020; Hitchner, 2017)."
    )
    accountant_app_f_title: str = "Bijlage F: Standaarden & Voorwaarden"
    accountant_app_f_callout: str = (
        "Deze waardering is uitgevoerd conform <strong>AICPA BVS-VII</strong> (Comprehensive Valuations), "
        "<strong>ASA BVS-III</strong> (Quality of Earnings) en <strong>IVS 105/200</strong> "
        "(Waarderingsbenaderingen)."
    )
    accountant_app_f_key_assumptions_title: str = "Kernveronderstellingen"
    accountant_app_f_key_assumption_1: str = (
        "Aangeleverde financiële stukken zijn correct en volledig."
    )
    accountant_app_f_key_assumption_2: str = (
        "Het management is competent en is voornemens de activiteiten voort te zetten."
    )
    accountant_app_f_key_assumption_3: str = (
        "Geen significante niet-bekendgemaakte verplichtingen of geschillen."
    )
    accountant_app_f_limiting_conditions_title: str = "Beperkende Voorwaarden"
    accountant_app_f_limiting_condition_1: str = (
        "Waardering is uitsluitend geldig op de effectieve datum."
    )
    accountant_app_f_limiting_condition_2: str = (
        "Er werd geen onafhankelijke audit uitgevoerd op de financiële data."
    )
    accountant_app_f_limiting_condition_3: str = (
        "Toekomstige gebeurtenissen kunnen de waarde wezenlijk beïnvloeden."
    )
    accountant_app_compliance_title: str = "Professionele Disclaimer & Compliance"
    accountant_app_methodology_title: str = "Datagedreven Waarderingsmethodologie"
    accountant_app_calculation_integrity_label: str = "Integriteit van de Berekening:"
    accountant_app_calculation_integrity_text: str = (
        "Dit waarderingsrapport presenteert berekende waarden die uitsluitend zijn afgeleid uit financiële "
        "data en empirisch gevalideerde marktmultiples. Alle cijfers worden berekend met behulp van "
        "academisch erkende methodologieën:"
    )
    accountant_app_method_uspap: str = "Bedrijfswaardering — Ontwikkeling & Rapportage"
    accountant_app_method_ivs: str = (
        "Waarderingsbenaderingen en -methoden (International Valuation Standards)"
    )
    accountant_app_method_aicpa: str = "Statement on Standards for Valuation Services"
    accountant_app_method_damodaran: str = "Investment Valuation: Tools and Techniques"
    accountant_app_methodology_footer: str = (
        "Waardedrijvers en risicofactoren in dit rapport zijn afgeleid uit een feitelijke analyse van "
        "de financiële data. Strategische aanbevelingen zijn bewust uitgesloten om de nauwkeurigheid te "
        "waarborgen — alle inhoud is datagedreven en niet adviserend van aard."
    )

    # =========================================================================
    # ACCOUNTANT VIEW PHASE 2: EBITDA NORMALIZATION (_ebitda_normalization.html)
    # =========================================================================
    accountant_ebitda_section_title: str = "Sectie 2 — Economische Realiteit (EBITDA-Normalisatie)"
    accountant_ebitda_ivs_badge: str = "IVS 105 Conform"
    accountant_ebitda_intro: str = (
        "Financiële stukken van KMO's zijn vaak gestructureerd voor fiscale optimalisatie in plaats "
        "van een nauwkeurige economische weergave. Deze sectie past de "
        "<strong>EBITDA-Normalisatiebrug</strong> toe om duurzame winstgevendheid te reconstrueren door "
        "systematisch eenmalige posten, eigenaar-specifieke voordelen en fiscaal gemotiveerde "
        "boekhoudbehandelingen die de werkelijke operationele prestaties verhullen, terug te draaien."
    )
    accountant_ebitda_primitive_title: str = "Primitief 1: Kader Economische Realiteit"
    accountant_ebitda_primitive_body: str = (
        "<strong>Methodologische Basis:</strong> We reconstrueren de duurzame winstgevendheid van de "
        "Onderneming door systematische terugdraaiing van discretionaire uitgaven, eenmalige posten en "
        "fiscaal geoptimaliseerde boekhoudbehandelingen. Deze transformatie vestigt de "
        '"genormaliseerde basislijn" voor de waardering, en zorgt ervoor dat alle volgende '
        "risicocorrecties worden toegepast op een verdedigbare, marktrepresentatieve EBITDA-basis "
        "conform de <strong>ASA BVS-III</strong>-normen."
    )
    accountant_ebitda_schedule_title: str = "EBITDA-Normalisatieschema"
    accountant_ebitda_bridge_caption_user: str = (
        "EBITDA-Brug (Gerapporteerd naar Genormaliseerd) — Jaar"
    )
    accountant_ebitda_col_item: str = "Normalisatiepost"
    accountant_ebitda_col_adjustment: str = "Aanpassing"
    accountant_ebitda_col_rationale: str = "Onderbouwing"
    accountant_ebitda_reported_ebitda_year: str = "Gerapporteerde EBITDA"
    accountant_ebitda_baseline_from_records: str = "Basislijn uit financiële stukken"
    accountant_ebitda_user_defined_adjustment: str = "Gebruikersgedefinieerde aanpassing"
    accountant_ebitda_custom_adjustment: str = "Aangepaste aanpassing"
    accountant_ebitda_no_adjustments: str = "Geen aanpassingen toegepast"
    accountant_ebitda_used_as_reported: str = "EBITDA gebruikt zoals gerapporteerd"
    accountant_ebitda_normalized_year: str = "Genormaliseerde EBITDA"
    accountant_ebitda_used_in_valuation: str = "Gebruikt in Waardering"
    accountant_ebitda_transformation_impact: str = "Impact van de transformatie"
    accountant_ebitda_net_adjustment_caption: str = "Netto-aanpassing op gerapporteerde winst."
    accountant_ebitda_adjustment_count: str = "Aantal Aanpassingen"
    accountant_ebitda_categories_adjusted_year: str = "Aangepaste categorieën voor dit jaar."
    accountant_ebitda_years_normalized: str = "Genormaliseerde Jaren"
    accountant_ebitda_total_years_caption: str = "Totaal aantal jaren met EBITDA-aanpassingen."
    accountant_ebitda_documentation_quality: str = "Documentatiekwaliteit"
    accountant_ebitda_quality_enhanced: str = "Verhoogd"
    accountant_ebitda_quality_standard: str = "Standaard"
    accountant_ebitda_includes_custom: str = "Inclusief aangepaste aanpassingen."
    accountant_ebitda_based_on_standard: str = "Gebaseerd op standaardcategorieën."
    accountant_ebitda_weighted_callout_title: str = "Gewogen EBITDA-Methodologie"
    accountant_ebitda_weighted_callout_body: str = (
        "<strong>McKinsey Academische Standaard:</strong> Deze waardering gebruikt "
        "<strong>gewogen gemiddelde EBITDA</strong> uit historische jaren (niet de eenjarige huidige "
        "EBITDA) om winstvolatiliteit te dempen en duurzame winstgevendheid weer te geven. De "
        "EBITDA van het huidige jaar ({year}) van <strong>{current_ebitda}</strong> is gewogen met "
        "historische prestaties conform McKinsey Valuation (2015, Hoofdstuk 7)."
    )
    accountant_ebitda_weighted_rationale_label: str = "Onderbouwing:"
    accountant_ebitda_weighted_default_rationale: str = (
        "Gewogen middeling vermindert de impact van jaar-op-jaar volatiliteit en levert een stabielere "
        "basislijn voor waardering."
    )
    accountant_ebitda_bridge_caption_weighted: str = "EBITDA-Brug (Gewogen naar Genormaliseerd)"
    accountant_ebitda_bridge_caption_reported: str = (
        "EBITDA-Brug (Gerapporteerd naar Genormaliseerd)"
    )
    accountant_ebitda_current_year_ebitda: str = "EBITDA Huidig Jaar"
    accountant_ebitda_single_year_not_used: str = "Eenjarige prestatie (niet gebruikt)"
    accountant_ebitda_weighted_historical: str = "Gewogen Historische EBITDA"
    accountant_ebitda_multi_year_weighted: str = "Meerjarige gewogen gemiddelde basislijn"
    accountant_ebitda_owner_compensation: str = "Eigenaarsvergoeding"
    accountant_ebitda_market_replacement_rate: str = "Tegen marktconforme vervangingstarief"
    accountant_ebitda_discretionary_expenses: str = "Discretionaire Uitgaven"
    accountant_ebitda_no_non_operating: str = "Geen niet-operationele posten geïdentificeerd"
    accountant_ebitda_normalized_label: str = "Genormaliseerde EBITDA"
    accountant_ebitda_representative_earning: str = "Representatieve Winstgevendheid"
    accountant_ebitda_avg_adjustment: str = "Gemiddelde aanpassing over {count} jaren."
    accountant_ebitda_net_adjustment: str = "Netto-aanpassing op gerapporteerde winst."
    accountant_ebitda_bridge_reliability: str = "Betrouwbaarheid Brug"
    accountant_ebitda_quality_high: str = "Hoog"
    accountant_ebitda_based_on_documentation: str = "Gebaseerd op documentatiekwaliteit."
    accountant_ebitda_quality_assessment_title: str = "Beoordeling van de winstkwaliteit"
    accountant_ebitda_quality_assessment_intro: str = (
        "Duurzame waardering vereist stabiele marges. We analyseren historische margevolatiliteit om "
        "de betrouwbaarheid van genormaliseerde winsten als voorspeller van toekomstige prestaties "
        "te beoordelen."
    )
    accountant_ebitda_metric_label: str = "Kerncijfer"
    accountant_ebitda_value_label: str = "Waarde"
    accountant_ebitda_assessment_label: str = "Beoordeling"
    accountant_ebitda_current_margin: str = "Huidige EBITDA-Marge"
    accountant_ebitda_current_margin_caption: str = "Recentste gerapporteerde prestaties"
    accountant_ebitda_historical_mean: str = "Historische Gemiddelde Marge"
    accountant_ebitda_historical_mean_caption: str = "Gemiddelde over beschikbare historiek"
    accountant_ebitda_margin_volatility: str = "Margevolatiliteit (σ)"
    accountant_ebitda_volatility_high: str = "HOGE VOLATILITEIT"
    accountant_ebitda_volatility_moderate: str = "GEMATIGD"
    accountant_ebitda_volatility_low: str = "LAAG / STABIEL"
    accountant_ebitda_sustainability_flag_title: str = "Duurzaamheidsvlag"
    accountant_ebitda_sustainability_flag_body: str = (
        "<strong>Margevolatiliteit gedetecteerd.</strong> De historische variantie suggereert dat "
        "winsten onderhevig kunnen zijn aan eenmalige fluctuaties of gevoeligheid voor externe "
        "marktcycli. Dit risico wordt verwerkt in de multiple-kalibratie."
    )
    accountant_ebitda_compliance_title: str = "Professionele Compliance"
    accountant_ebitda_compliance_asa: str = (
        "<strong>ASA BVS-III:</strong> Beoordeling van winstkwaliteit is vereist voor een waardering op fiduciair niveau."
    )
    accountant_ebitda_compliance_aicpa: str = (
        "<strong>AICPA BVS-VII:</strong> Normalisatieschema vereist voor uitgebreide KMO-rapportage."
    )
    accountant_ebitda_compliance_trugman: str = (
        "<strong>Trugman (2017):</strong> Kader voor add-backs van eigenaarsvoordelen en terugdraaiing fiscale optimalisatie."
    )
    accountant_ebitda_limited_data_badge: str = "Beoordeling met Beperkte Data"
    accountant_ebitda_limited_intro: str = (
        "Financiële stukken van KMO's vereisen vaak normalisatie om duurzame winstgevendheid te "
        "scheiden van eigenaar-specifieke voordelen en eenmalige posten. Een gedetailleerde "
        "normalisatiebrug vereist echter meerjarige financiële data en uitgebreide bekendmaking van "
        "discretionaire uitgaven."
    )
    accountant_ebitda_limited_notice_title: str = "Mededeling over de databeperking"
    accountant_ebitda_limited_notice_body: str = (
        "<strong>Normalisatie-Analyse Niet Uitgevoerd:</strong> Uitgebreide EBITDA-normalisatie "
        "vereist historische financiële stukken (minimum 2-3 jaar) en gedetailleerde "
        "kostencategorisatie. De huidige beoordeling gebruikt rechtstreeks de gerapporteerde "
        "EBITDA-cijfers, onderhevig aan standaard kwaliteitscorrecties in de multiple-kalibratie "
        "(Stap 2.5: Kwaliteitskalibratie)."
    )
    accountant_ebitda_earning_power_framework: str = "Kader voor beoordeling van de winstgevendheid"
    accountant_ebitda_earning_power_body: str = (
        "Bij gebrek aan gedetailleerde normalisatiedata past de waarderingsmethodologie "
        "<strong>conservatieve kwaliteitscorrecties</strong> rechtstreeks toe op de "
        "waarderingsmultiple in plaats van op de EBITDA. Deze Multiple-First-aanpak voorkomt "
        "overschatting van winstgevendheid en behoudt professionele verdedigbaarheid."
    )
    accountant_ebitda_current_year_baseline_caption: str = "Financiële Basislijn Huidig Jaar"
    accountant_ebitda_status_label: str = "Status"
    accountant_ebitda_revenue: str = "Omzet"
    accountant_ebitda_status_reported: str = "Gerapporteerd"
    accountant_ebitda_reported_label: str = "EBITDA (Gerapporteerd)"
    accountant_ebitda_status_used_as_reported: str = "Gebruikt zoals gerapporteerd"
    accountant_ebitda_margin_label: str = "EBITDA-Marge"
    accountant_ebitda_profitability_indicator: str = "Winstgevendheidsindicator"
    accountant_ebitda_alt_methodology_title: str = "Alternatieve Beoordelingsmethodologie"
    accountant_ebitda_alt_methodology_body: str = (
        "<strong>Multiple-First Risicocorrectie:</strong> In plaats van EBITDA-normalisatie uit te "
        "voeren met beperkte zichtbaarheid van data, past deze waardering kwaliteitscorrecties op "
        "winsten rechtstreeks toe op de waarderingsmultiple tijdens Stap 2.5 (Kwaliteitskalibratie). "
        "Deze aanpak volgt AICPA BVS-VII-richtlijnen voor waarderingen met beperkte financiële "
        "bekendmaking."
    )
    accountant_ebitda_quality_adjustments_title: str = "Toegepaste Kwaliteitscorrecties"
    accountant_ebitda_quality_adj_data: str = (
        "<strong>Premie/Korting Datakwaliteit:</strong> Toegepast op de multiple op basis van "
        "betrouwbaarheidsbeoordeling van financiële stukken"
    )
    accountant_ebitda_quality_adj_earnings: str = (
        "<strong>Kalibratie Winstkwaliteit:</strong> Conservatieve correctie voor potentiële "
        "eigenaarsvoordelen en discretionaire uitgaven"
    )
    accountant_ebitda_quality_adj_size: str = (
        "<strong>Risico Kleine Onderneming:</strong> Omvanggerelateerde correcties houden rekening "
        "met beperkte historische data en documentatiediepte"
    )
    accountant_ebitda_valuation_impact_title: str = "Beoordeling Waarderingsimpact"
    accountant_ebitda_quality_approach_label: str = "Aanpak Kwaliteitscorrectie"
    accountant_ebitda_multiple_first: str = "Multiple eerst"
    accountant_ebitda_quality_approach_caption: str = (
        "Risicocorrecties toegepast op waarderingsmultiple"
    )
    accountant_ebitda_methodology_confidence_label: str = "Vertrouwen Methodologie"
    accountant_ebitda_confidence_moderate: str = "Gematigd"
    accountant_ebitda_limited_visibility: str = "Beperkte normalisatiezichtbaarheid"
    accountant_ebitda_pro_standards_title: str = "Conformiteit Professionele Standaarden"
    accountant_ebitda_pro_standards_body: str = (
        "<strong>AICPA BVS-VII:</strong> Wanneer uitgebreide normalisatie niet haalbaar is door "
        "databeperkingen, dienen waarderingsprofessionals conservatieve kwaliteitscorrecties toe te "
        "passen om te voorkomen dat de waardering de winstgevendheid overschat. Deze aanpak "
        "behoudt professionele scepsis en zorgt voor verdedigbaarheid in scenario's met beperkte "
        "informatie."
    )
