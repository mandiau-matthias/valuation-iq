"""Dutch cover, summary, financial, calibration, component, and NAV copy."""

from __future__ import annotations


def build_dutch_core_financial_translations() -> dict[str, object]:
    return {
        # Cover Page
        "cover_estimate_label": "Bedrijfsschatting",
        "cover_estimate_label_seller": "Uw bedrijfsschatting",
        "cover_ev_label": "Indicatieve Ondernemingswaarde (EV)",
        "cover_equity_label": "Indicatief Eigen Vermogen",
        "cover_equity_note": "Eigen vermogen na verrekening van rentedragende schuld en overtollige kaspositie — wat de verkoper indicatief netto ontvangt.",
        "equity_adjusted_label": "Gecorrigeerde NAV (Intrinsieke Waarde)",
        "equity_adjusted_note": "Eigen Vermogen gecorrigeerd voor netto kas/schuld en belastinglatenties.",
        "cover_ebitda_label": "Genormaliseerde EBITDA (gewogen)",
        "cover_sde_label": "Duurzame SDE (gewogen)",
        "cover_multiple_label": "Toegepaste multiple",
        "cover_adaptive_blend_label": "Adaptieve blend",
        "cover_wacc_label": "WACC",
        "cover_date_label": "Datum",
        "cover_confidential": "Vertrouwelijk",
        "cover_founded": "Opgericht",
        "cover_year_suffix": "jaar",
        "cover_years_suffix": "jaar",
        "cover_ev_note_dcf": "Indicatieve ondernemingswaarde via DCF-analyse, op kas- en schuldvrije basis",
        "cover_ev_note_hybrid": "Indicatieve ondernemingswaarde via gewogen EBITDA Multiples + DCF, op kas- en schuldvrije basis",
        "cover_ev_note_adaptive": (
            "Indicatieve ondernemingswaarde via Upswitch adaptieve marktbenadering, "
            "op kas- en schuldvrije basis"
        ),
        "cover_ev_note_adaptive_multiples_only": (
            "Indicatieve ondernemingswaarde via Upswitch Adaptive · marktbenadering, "
            "op kas- en schuldvrije basis"
        ),
        "cover_ev_note_default": "Indicatieve ondernemingswaarde bij kas- en schuldvrije veronderstelling. Netto-opbrengst hangt af van schuld, kas en werkkapitaal op transactiedatum.",
        "cover_statutory_currency_label": "Wettelijke valuta",
        "cover_statutory_currency_note": "waardering uitgedrukt in EUR",
        "cover_owner_profiling_summary": (
            "Eigenaarsprofiel — overdraagbaarheid {tri}/100 · {risk_level} · "
            "multiple-impact {adj_pct}% t.o.v. benchmark"
        ),
        # Executive Summary
        "exec_summary_title": "Samenvatting",
        "exec_indicative_label": "Indicatief",
        "high_severity_callout_title": "Aandachtspunten waardering",
        "high_severity_callout_lead_singular": (
            "Deze waardering bevat 1 signaal met hoge ernst. "
            "Verifieer de onderliggende data voordat het rapport wordt gedeeld."
        ),
        "high_severity_callout_lead_plural": (
            "Deze waardering bevat {count} signalen met hoge ernst. "
            "Verifieer de onderliggende data voordat het rapport wordt gedeeld."
        ),
        "nwc_disclosure_surplus": (
            "Werkkapitaalcorrectie: +{amount} surplus boven de genormaliseerde band "
            "({actual_pct}% vs. doel {target_pct}%) — komt ten goede aan de verkoper bij overdracht."
        ),
        "nwc_disclosure_deficit": (
            "Werkkapitaalcorrectie: −{amount} tekort onder de genormaliseerde band "
            "({actual_pct}% vs. doel {target_pct}%) — wordt typisch verrekend met de aandelenwaarde bij overdracht."
        ),
        "nwc_disclosure_neutral": (
            "Werkkapitaal valt binnen de genormaliseerde band ({actual_pct}% vs. doel {target_pct}%); geen aanpassing toegepast."
        ),
        "nwc_disclosure_unavailable": (
            "Geen balansdata verstrekt — werkkapitaal niet beoordeeld. Transactiestructuur beïnvloedt finale opbrengst."
        ),
        "warning_thin_comparables_proxy_message": (
            "Sectormultiple is afgeleid van een dunne of proxy-sector dataset. "
            "De kop-multiple is op zichzelf statistisch niet robuust."
        ),
        "warning_thin_comparables_proxy_recommendation": (
            "Bevestig dat het bedrijfstype-id overeenkomt met het werkelijke operationele "
            "model en — als de onderneming in een andere sector actief is dan de proxy — "
            "overrule de multiple handmatig of vraag een diepere benchmarks-pull aan."
        ),
        "warning_owner_concentration_skip_message": (
            "Eigenaar-concentratiecorrectie overgeslagen — aantal eigenaren of werknemers "
            "ontbreekt. Voor eigenaar-geleide KMO's is dit een materieel hiaat."
        ),
        "warning_owner_concentration_skip_recommendation": (
            "Vul number_of_owners en number_of_employees aan op het verzoek (of in business_context) "
            "en herbereken; pas anders de korting handmatig toe vóór levering."
        ),
        "warning_ebitda_divergence_message": (
            "EBITDA-veld en genormaliseerde EBITDA in de metadata zijn niet consistent — "
            "de rapportbrug en de rekenmotor kunnen verschillende cijfers tonen."
        ),
        "warning_ebitda_divergence_recommendation": (
            "Corrigeer de request-builder zodat de na-aanpassingswaarde in zowel "
            "current_year_data.ebitda als ebitda_normalization_metadata.normalized_ebitda staat."
        ),
        "warning_method_substitution_message": (
            "De gevraagde waarderingsmethode kon niet worden uitgevoerd; "
            "het rapport gebruikt een vervangende methode (zie methodologie-blok)."
        ),
        "warning_method_substitution_recommendation": (
            "Vul de ontbrekende inputs aan voor de oorspronkelijke methode "
            "(typisch balansdata voor NAV) en herbereken, of bevestig expliciet de vervangende methode."
        ),
        "warning_net_debt_unavailable_message": (
            "Geen balansdata beschikbaar — netto schuld is niet onafhankelijk berekend. "
            "De EV→Equity brug gebruikt een proxy en is niet auditbestendig."
        ),
        "warning_net_debt_unavailable_recommendation": (
            "Voeg totale schuld en kasposities toe (of importeer de jaarrekening) "
            "voordat het rapport extern wordt gedeeld."
        ),
        "warning_owner_comp_estimated_message": (
            "Eigenaarssalaris is niet opgegeven en automatisch geschat. "
            "Voor eigenaar-geleide ondernemingen is dit doorgaans de #1 normalisatiepost."
        ),
        "warning_owner_comp_estimated_recommendation": (
            "Vul het werkelijk uitgekeerde eigenaarssalaris in (of de marktconforme vervangingskost) "
            "zodat de genormaliseerde EBITDA verdedigbaar is."
        ),
        "warning_ebitda_benchmark_deviation_message": (
            "EBITDA-marge wijkt materieel af van de sectormediaan. "
            "Dit kan duiden op normalisatie-ruimte of een fundamenteel marge-verschil."
        ),
        "warning_ebitda_benchmark_deviation_recommendation": (
            "Documenteer de oorzaak van de afwijking (eigenaarssalaris, eenmalige posten, "
            "structureel verschil) of voeg een normalisatiepost toe."
        ),
        "warning_book_equity_unavailable_message": (
            "Boekhoudkundig eigen vermogen niet opgegeven — fiscale referentiewaarde is incompleet. "
            "Het EBITDA-deel wordt apart getoond; de totaalformule kan niet sluitend worden ingevuld."
        ),
        "warning_book_equity_unavailable_recommendation": (
            "Voeg total_equity (of total_assets en total_debt) uit de laatste jaarrekening toe "
            "zodat de wettelijke formule volledig kan worden weergegeven."
        ),
        "exec_confidence_score": "Betrouwbaarheidsscore",
        "exec_comparable_transactions": "vergelijkbare transacties",
        "exec_ev_label": "Indicatieve waarde",
        "exec_range_label": "Bandbreedte",
        "exec_normalized_label": "Genormaliseerd",
        "exec_revenue_label": "Omzet",
        "exec_employee_singular": "medewerker",
        "exec_employee_plural": "medewerkers",
        "exec_industry_comparison": "Sectorvergelijking",
        "exec_median_multiple": "Mediaan multiple",
        "exec_single_reference": "Enkele referentie",
        "exec_sample_label": "Steekproef",
        "exec_transactions": "transacties",
        # VAL-2026-35A4: NL needs a singular form when benchmark_sample_size == 1.
        "exec_transactions_singular": "transactie",
        "exec_limited_data": "beperkte dataset",
        "exec_insufficient_data_warning": "Beperkt aantal referenties — indicatieve marktbenadering",
        "exec_benchmark_source_note": "Referentiesector (niet dezelfde bron als waarderingsbasis)",
        "exec_benchmark_applied_vs_reference": "De toegepaste multiple (na kalibratie en risicocorrecties) wijkt af van de referentie-mediaan; dit is een transactie-specifieke schatting, geen algemene premie of korting op de markt.",
        "exec_thin_benchmark_seller_escalation": "Versterk de onderbouwing met extra boekjaren en sectortransacties vóór een transactie — uw adviseur kan het dossier verder aanscherpen.",
        "exec_thin_benchmark_advisor_escalation": "Versterk het cliëntdossier met extra boekjaren en sectortransacties vóór marketing of due diligence.",
        "adaptive_intro_multiples_only_seller": "Deze waardering gebruikt gekalibreerde marktmultiples. DCF draagt niet bij aan deze schatting. Op deze pagina ziet u <em>hoe</em> uw indicatieve waarde is opgebouwd.",
        "adaptive_intro_hybrid_seller": "Upswitch Adaptive combineert marktmultiples met een discounted-cashflowzicht wanneer uw bedrijfsprofiel dat rechtvaardigt. Op deze pagina ziet u <em>hoe</em> uw indicatieve waarde is opgebouwd.",
        "adaptive_intro_multiples_only_advisor": "Deze waardering gebruikt gekalibreerde marktmultiples. DCF draagt niet bij; de redenen staan in de beoordeling van de methodegeschiktheid. Gebruik deze pagina om aan uw cliënt uit te leggen <em>hoe</em> de hoofdrange is opgebouwd.",
        "adaptive_intro_hybrid_advisor": "Upswitch Adaptive combineert marktgebaseerde multiples met een discounted-cashflowzicht wanneer het bedrijfsprofiel dit rechtvaardigt. Gebruik deze pagina om aan uw cliënt uit te leggen <em>hoe</em> de hoofdrange is opgebouwd in een M&amp;A-context.",
        "adaptive_footnote_multiples_only_seller": "<strong>Uw schatting.</strong> Deze waardering gebruikt marktmultiples; DCF draagt niet bij. De bandbreedte weerspiegelt de gevoeligheid voor EBITDA en de multiple.",
        "adaptive_footnote_hybrid_seller": "<strong>Uw schatting.</strong> Deze aanpak combineert marktankers met prognoses waar dat zinvol is. Detail per methode staat elders in dit rapport.",
        "adaptive_footnote_multiples_only_advisor": "<strong>Voor uw cliëntendossier.</strong> Deze waardering gebruikt gekalibreerde marktmultiples; DCF draagt niet bij. De hoofdrange weerspiegelt multiples-gevoeligheid. De redenen staan in de beoordeling van de methodegeschiktheid.",
        "adaptive_footnote_hybrid_advisor": "<strong>Voor uw cliëntendossier.</strong> Deze aanpak past bij situaties waarin prognoses waardevol zijn maar multiples een marktanker blijven. De gecombineerde resultaten en uitgangspunten staan elders in dit rapport.",
        "seller_limited_scope_title": "Volgende stappen om uw waardering te versterken",
        "seller_limited_scope_intro": "Deze schatting biedt een bruikbare indicatieve basis. Voor een transactie of due diligence raden we de volgende stappen aan:",
        "seller_limited_scope_li_year": "Voeg een tweede boekjaar toe (bijv. 2024) voor trend en betrouwbaarheid.",
        "seller_limited_scope_li_balance": "Koppel uw boekhouding (Yuki, Exact, …) of vul een balans in voor nettoschuld en werkkapitaal.",
        "seller_limited_scope_li_advisor": "Deel het rapport met uw adviseur voor normalisatie en sectorvergelijking.",
        "advisor_limited_scope_title": "Volgende stappen om het cliëntdossier te versterken",
        "advisor_limited_scope_intro": "Deze schatting biedt een bruikbare indicatieve basis voor het cliëntdossier. Voor een transactie of due diligence raden we de volgende stappen aan:",
        "advisor_limited_scope_li_year": "Voeg een tweede boekjaar toe voor de cliënt (bijv. 2024) voor trend en betrouwbaarheid.",
        "advisor_limited_scope_li_balance": "Koppel de boekhouding van de cliënt (Yuki, Exact, …) of vul een balans in voor nettoschuld en werkkapitaal.",
        "advisor_limited_scope_li_client": "Deel het rapport met uw cliënt en stem normalisaties af vóór gesprekken met kopers.",
        "seller_margin_diligence_note": "Uw EBITDA-marge ({reported_pct}%) ligt onder het sectorgemiddelde (~{typical_pct}%). Kopers kunnen dit interpreteren als druk op de multiple of als behoefte aan normalisatie — bespreek dit met uw adviseur.",
        "advisor_margin_diligence_note": "Gerapporteerde EBITDA-marge ({reported_pct}%) ligt onder het sectorgemiddelde (~{typical_pct}%). Signaleer normalisatie en koperverhaal in het cliëntdossier.",
        "seller_multiple_bridge_title": "Van sectorreferentie naar toegepaste multiple",
        "seller_multiple_bridge_reference": "Sectorreferentie (DB-mediaan)",
        "seller_multiple_bridge_base": "Gekalibreerde contractbasis (omvang/marge)",
        "seller_multiple_bridge_applied": "Toegepast op uw EBITDA",
        "advisor_multiple_bridge_title": "Van sectorreferentie naar toegepaste multiple (cliëntdossier)",
        "advisor_multiple_bridge_reference": "Sectorreferentie (DB-mediaan)",
        "advisor_multiple_bridge_base": "Gekalibreerde contractbasis (omvang/marge)",
        "advisor_multiple_bridge_applied": "Toegepast op EBITDA van de cliënt",
        "advisor_controls_audit_title": "Audit trail adviseurinstellingen",
        "advisor_controls_multiple_calibration_title": "Multiple-calibratie",
        "advisor_controls_sector_average_label": "Sectorgemiddelde",
        "advisor_controls_risk_quality_premium_label": "risico-/kwaliteitspremie",
        "advisor_controls_calibrated_label": "gekalibreerd",
        "advisor_controls_effective_override_title": "Finale effectieve multiple override",
        "advisor_controls_model_effective_multiple_label": "model effectief",
        "advisor_controls_advisor_effective_multiple_label": "adviseur effectief",
        "advisor_controls_delta_multiple_label": "delta",
        "advisor_controls_note_label": "Toelichting",
        "advisor_controls_historical_ebitda_weighting_title": "Historische jaarweging",
        "advisor_controls_weighted_ebitda_label": "gewogen EBITDA",
        "advisor_controls_real_estate_treatment_title": "Vastgoedbehandeling",
        "advisor_controls_real_estate_included_label": "Vastgoed inbegrepen in de transactie",
        "advisor_controls_real_estate_carve_out_label": "Vastgoed carve-out buiten de transactie",
        "advisor_controls_market_value_label": "marktwaarde",
        "advisor_controls_book_value_label": "boekwaarde",
        "advisor_controls_surplus_value_label": "meerwaarde",
        "advisor_controls_market_rent_label": "markthuur",
        "seller_advisor_cta_title": "Deel met uw adviseur",
        "seller_advisor_cta_lead": "Uw accountant of M&A-adviseur kan normalisaties, sectorbenchmarks en transactiestructuur verfijnen — en dit dossier gebruiken in een echte verkoopvoorbereiding.",
        "seller_advisor_cta_button": "Deel met uw adviseur",
        "exec_methodology_hybrid": "hybride marktbenadering (EV/EBITDA-multiple + DCF)",
        "exec_methodology_dcf": "inkomstenbenadering (Discounted Cash Flow)",
        "exec_methodology_sde": "marktbenadering met SDE-multiples",
        "exec_methodology_multiples": "marktbenadering met geselecteerde marktmultiple",
        "exec_methodology_asset": "substantie-waardering (NAV)",
        "exec_methodology_yield": "vastgoed yield-benadering (huur ÷ cap-rate)",
        "exec_methodology_badge_hybrid": "EBITDA Multiples + DCF",
        "exec_methodology_badge_dcf": "DCF Analyse",
        "exec_methodology_badge_sde": "SDE-multiples",
        "exec_methodology_badge_multiples": "Marktmultiples",
        "exec_methodology_badge_asset": "Substantie-waardering (NAV)",
        "exec_methodology_badge_yield": "Vastgoed yield",
        "exec_methodology_badge_adaptive": "Upswitch adaptieve marktbenadering",
        "exec_methodology_adaptive": "Upswitch adaptieve marktbenadering",
        "exec_methodology_badge_adaptive_multiples_only": "Upswitch Adaptive · Marktbenadering",
        "exec_methodology_adaptive_multiples_only": "Upswitch Adaptive · marktbenadering",
        "exec_goal_label": "Doel van de Waardering",
        "exec_description_intro": "Deze bedrijfsschatting geeft de indicatieve ondernemingswaarde van",
        "exec_as_of": "per",
        "exec_description_calculated_via": "berekend via de",
        "exec_npv_calculation": "NPV van",
        "exec_fcf_terminal_value": "jaar FCF + Terminale Waarde",
        "exec_market_median": "Marktmediaan",
        "exec_ev_equity_note_title": "Waardering en netto-opbrengst",
        "exec_ev_equity_note_text": "De bovenstaande waarde betreft de ondernemingswaarde (EV). De geschatte aandeelhouderswaarde volgt uit: Ondernemingswaarde (EV) - Netto Schuld = Eigen Vermogen. De netto-opbrengst voor de verkoper hangt af van uitstaande schulden, overtollig kasgeld en werkkapitaalcorrecties op de transactiedatum.",
        "exec_ev_equity_line2": "Netto-opbrengst hangt af van: schuld, cash, en werkkapitaalcorrecties bij overdracht.",
        "exec_ev_equity_with_balance": "Balansdata vastgelegd in het dossier — de netto-schuldbrug is op de vastgelegde balansposities berekend. Werkkapitaal en netto-schuld worden bij een transactie behandeld volgens het overeengekomen prijsmechanisme, bijvoorbeeld completion accounts of een locked-box.",
        "exec_ev_equity_no_balance": "Geen balansdata verstrekt — werkkapitaal niet beoordeeld. Transactiestructuur beïnvloedt finale opbrengst.",
        "exec_sde_note": "Opmerking: Voor eigenaar-geleide micro-ondernemingen kunnen kopers ook SDE-multiples hanteren, gebaseerd op discretionaire eigenaarswinst. Dit rapport gebruikt EBITDA-gebaseerde ondernemingswaarde conform gangbare M&A-praktijk.",
        "exec_sde_cross_check_title": "SDE-cross-check (eigenaar-geleide micro-onderneming)",
        "exec_sde_cross_check_intro": (
            "Voor dit profiel hanteren kopers vaak ook een SDE-multiple "
            "(Seller's Discretionary Earnings). Onderstaand de indicatieve "
            "SDE-waardering naast de EBITDA-hoofdwaardering — als "
            "convergentiecheck, niet als vervangende methode."
        ),
        "exec_sde_cross_check_sde_label": "SDE",
        "exec_sde_cross_check_multiple_label": "SDE-multiple",
        "exec_sde_cross_check_ev_label": "Indicatieve EV op SDE-basis",
        "exec_sde_cross_check_footnote": (
            "SDE = EBITDA + marktconforme eigenaarsvergoeding. Multiple "
            "uit interne benchmarkset voor micro-SME's; vraag een "
            "M&A-adviseur om bevestiging vóór externe distributie."
        ),
        "exec_implied_ebitda_multiple": "Impliciete EBITDA-multiple",
        "exec_pre_blend_label": "Kruiscontrole vóór synthese",
        "exec_blended_headline_note": "waarde na SDE-/synthesebijstelling",
        "exec_ev_bridge_title": "EV-naar-Eigen Vermogen Brug",
        "exec_ev_bridge_ev_label": "Ondernemingswaarde (EV)",
        "exec_ev_bridge_net_debt_label": "Netto Schuld",
        "exec_ev_bridge_net_cash_label": "Netto Kaspositie",
        "exec_ev_bridge_equity_label": "Eigen Vermogen (Equity)",
        "exec_ev_bridge_nwc_label": "Werkkapitaal correctie",
        "exec_ev_bridge_residual_label": "Reconciliatieverschil",
        "exec_nav_bridge_title": "Brug naar Gecorrigeerde NAV (Intrinsieke Waarde)",
        "exec_nav_bridge_book_equity": "Boekhoudkundig Eigen Vermogen",
        "exec_nav_bridge_gross_corrections": "Totaal correcties (bruto)",
        "exec_nav_bridge_tax_latency": "Belastinglatenties op meerwaarden",
        "exec_nav_bridge_off_balance": "Niet-balansgerelateerde verplichtingen",
        "exec_nav_bridge_corrected_nav": "Gecorrigeerde NAV (Intrinsieke Waarde)",
        "exec_asking_price_label": "Voorgestelde Vraagprijs",
        "exec_asking_price_note": "Strategische buffer voor onderhandeling",
        "market_provenance_source_managed_dataset": "Upswitch economische dataset",
        "exec_narrative_basis": "Op basis van de genormaliseerde winstcapaciteit en marktconforme waarderingsmultiples komt de indicatieve ondernemingswaarde uit op",
        "exec_narrative_basis_dcf": "Op basis van de contante waarde van geprojecteerde vrije kasstromen (DCF) komt de indicatieve ondernemingswaarde uit op",
        "exec_narrative_basis_hybrid": "Op basis van de gewogen synthese van marktbenadering en DCF komt de indicatieve ondernemingswaarde uit op",
        "exec_narrative_basis_asset": "Op basis van de balanssubstantie, de NAV-benadering en relevante balanscorrecties komt de indicatieve waarde uit op",
        "exec_narrative_basis_yield": "Op basis van de duurzame netto huuropbrengst, een marktconforme cap-rate en de NAV-vloer komt de indicatieve waarde uit op",
        "exec_narrative_ev_note": "Deze waarde betreft de ondernemingswaarde (Enterprise Value) op kas- en schuldvrije basis, vóór eventuele aanpassingen voor nettoschuld, werkkapitaal of transactiestructuur.",
        "exec_official_registry_head": "Controle officiële bron (NBB)",
        "exec_official_filing_year_label": "Boekjaar",
        "exec_official_source_staatsblad": "Bron: Staatsbladmonitor",
        "exec_dd_accountant_vs_official_title": "Adviseursinvoer t.o.v. officiële cijfers",
        "exec_dd_col_accountant": "Adviseursinvoer",
        "exec_official_dd_line_item": "Post",
        "exec_official_dd_col_official": "Officieel",
        "exec_official_dd_delta_pct": "Δ %",
        "exec_official_variance_title": "Verschilanalyse",
        "exec_official_explanation_required": "Toelichting vereist",
        "exec_official_variance_hard_note": "Grote afwijking t.o.v. officiële filing (harde drempel).",
        "exec_official_trust_match_verified": (
            "De door de adviseur ingevoerde cijfers zijn afgetoetst aan de officiële NBB-jaarrekening "
            "(bron: Staatsbladmonitor)."
        ),
        "exec_official_total_assets_label": "Totale activa",
        "exec_official_equity_label": "Eigen vermogen",
        "exec_saas_anchor_label": "SaaS-anker",
        "exec_saas_quality_title": "SaaS-kwaliteitssignalen",
        "exec_saas_nrr_label": "NRR",
        "exec_saas_rule_of_40_label": "Rule of 40",
        "exec_saas_churn_label": "Bruto churn",
        "exec_saas_arr_growth_label": "ARR-groei (jaarlijks)",
        # EBITDA Normalization
        "ebitda_sde_title": "SDE Berekening",
        "ebitda_normalization_title": "EBITDA Normalisatie",
        "ebitda_sde_description": "SDE vertegenwoordigt de discretionaire eigenaarswinst: de totale financiële voordelen voor een actieve eigenaar.",
        "ebitda_sde_formula": "SDE = EBITDA + Eigenaarssalaris + Eigenaarsgerelateerde voordelen. Dit is de standaardmaatstaf voor micro-ondernemingen.",
        "ebitda_sde_vs_ebitda": "SDE vs EBITDA",
        "ebitda_sde_multiples_note": "SDE is typisch 20-40% hoger dan EBITDA vanwege eigenaarssalaris-toevoegingen. SDE-multiples zijn daarom lager (1.5-3×) dan EBITDA-multiples (3-5×) voor dezelfde waarde.",
        "ebitda_dcf_description": "De DCF-analyse vereist genormaliseerde kasstromen als basis voor projecties.",
        "ebitda_dcf_projections_note": "Onderstaande normalisaties zorgen ervoor dat historische data een betrouwbare basis vormt voor toekomstprojecties.",
        "ebitda_normalization_description": "Normalisatie past de gerapporteerde EBITDA aan om de duurzame winstcapaciteit te weerspiegelen, door eigenaarsspecifieke, eenmalige en niet-operationele posten te verwijderen conform standaard M&A-praktijk.",
        "ebitda_adjustments_disclaimer": "Aanpassingen zijn gebaseerd op door de gebruiker verstrekte categorisatie en kunnen door een adviseur worden herzien.",
        "ebitda_ai_disclaimer_title": "Te bevestigen normalisatievoorstellen.",
        "ebitda_ai_disclaimer_body": "Onderstaande normalisaties zijn patroongebaseerde voorstellen op basis van de grootboekdata. Bevestig elke aanpassing met bewijsstukken en adviseursoordeel vóór fiscale, juridische of M&A-verdediging. Dit is geen formeel boekhoudkundig advies.",
        "ebitda_no_adjustments_note": "Geen normalisatievoorstellen geregistreerd in deze run; de gerapporteerde EBITDA is ongewijzigd overgenomen in de brug.",
        "ebitda_normalization_candidates_note": "{count} normalisatiekandidaat/-kandidaten ({amount} voorgesteld) gedetecteerd uit de grootboekdata, maar nog niet toegepast — adviseursbeoordeling vereist. De gerapporteerde EBITDA is ongewijzigd als waarderingsbasis gebruikt.",
        "ebitda_owner_led_pending_title": "Eigenaar-geleide onderneming — normalisatie nog niet bevestigd.",
        "ebitda_owner_led_pending_body": (
            "Bij een eigenaar-geleide onderneming zal een ervaren koper doorgaans "
            "onderbouwing vragen voor marktconforme eigenaarsvergoeding en voor "
            "eenmalige of privé-uitgaven. De jaarcijfers die voor de waardering "
            "zijn gebruikt, bevatten geen normalisatieaanpassingen. "
            "Laat deze posten bevestigen vóór externe distributie."
        ),
        "ebitda_owner_led_pending_body_prior_year_norms": (
            "Bij een eigenaar-geleide onderneming zal een ervaren koper doorgaans "
            "onderbouwing vragen voor marktconforme eigenaarsvergoeding en voor "
            "eenmalige of privé-uitgaven. Voor het basisjaar zijn nog geen "
            "aanpassingen ingevoerd, maar de gewogen waarderingsbasis bevat wél "
            "normalisaties uit eerdere jaren (zie het meerjarig overzicht). Laat "
            "zowel de eigenaarsvergoeding als deze normalisaties bevestigen vóór "
            "externe distributie."
        ),
        "ebitda_reported_label": "Gerapporteerde EBITDA",
        "ebitda_owner_adjustments": "Eigenaarscorrecties",
        "ebitda_total_adjustments": "Totale Aanpassingen",
        "ebitda_sde_year_label": "SDE",
        "ebitda_normalized_year_label": "Genormaliseerd",
        "ebitda_adjustments_overview": "Aanpassingsoverzicht",
        "ebitda_source_legend": "Bronverklaring",
        "ebitda_source_yuki": "Yuki",
        "ebitda_source_exact": "Exact",
        "ebitda_source_suggestion": "Suggestie Upswitch",
        "ebitda_source_metadata": "Geautomatiseerde extractie",
        "ebitda_source_manual": "Manueel",
        "ebitda_source_yuki_desc": (
            "Automatisch geïmporteerd uit de live Yuki-grootboekkoppeling — boekjaarcijfers."
        ),
        "ebitda_source_exact_desc": (
            "Automatisch geïmporteerd uit de live Exact-grootboekkoppeling — boekjaarcijfers."
        ),
        "ebitda_source_suggestion_desc": (
            "Patroongebaseerde post (eigenaarsvergoeding, eenmalig, niet-recurrent). Te bevestigen door de adviseur."
        ),
        "ebitda_source_metadata_desc": (
            "Afkomstig uit de geautomatiseerde BE-PCMN-grootboekextractie — kandidaten in afwachting van adviseursbeoordeling."
        ),
        "ebitda_source_manual_desc": (
            "Door de adviseur ingevoerd of aangepast — bewijs en motivering in de notitie."
        ),
        "ebitda_multi_year_title": "Meerjarig Overzicht — Basis voor Waardering",
        "ebitda_sustainable_description": "De genormaliseerde EBITDA",
        "ebitda_valuation_basis": "is berekend als gewogen gemiddelde van {count} boekjaren. Dit is de basis voor de waarderingsberekening (EV = Genormaliseerde EBITDA × Multiple).",
        "ebitda_valuation_basis_asset": "is berekend als gewogen gemiddelde van {count} boekjaren. Voor deze substantie-waardering dient EBITDA als operationele sanity check; de primaire waarderingsbasis blijft de balans/NAV.",
        "ebitda_valuation_basis_yield": "is berekend als gewogen gemiddelde van {count} boekjaren. Voor deze vastgoedwaardering dient EBITDA als operationele sanity check; de primaire waarderingsbasis is netto huur gedeeld door cap-rate, met NAV-vloer.",
        "ebitda_valuation_basis_dcf": "is berekend als gewogen gemiddelde van {count} boekjaren en dient als referentie; de FCFF-projecties in de DCF-analyse vertrekken van de waarderingsbasis vermeld in deze tabel.",
        "ebitda_year_column": "Jaar",
        "filing_year_col_base": "Basis",
        "filing_year_col_base_minus": "Basis − {n}",
        "ebitda_reported_column": "Gerapporteerd",
        "ebitda_normalized_column": "Genormaliseerd",
        "ebitda_weight_column": "Weging",
        "ebitda_weighted_column": "Gewogen",
        "ebitda_status_column": "Status",
        "ebitda_margin_suffix": "marge",
        "ebitda_approved": "Goedgekeurd",
        "ebitda_calculated_total": "Berekend totaal",
        "ebitda_rounded_for_valuation": "Afgerond voor waardering",
        "ebitda_weighted_average_note": "Gewogen gemiddelde = Σ (Genormaliseerde EBITDA × Weging).",
        "ebitda_advisor_weighting_audit_note": "De adviseursweging is gedocumenteerd in de audit trail voor adviseurinstellingen.",
        "ebitda_standard_average_note": "Standaardgemiddelde: elk opgenomen jaar weegt even zwaar.",
        "ebitda_recent_years_note": "Gewichten volgens opgeslagen jaarweging: het meest recente jaar weegt het zwaarst. Dezelfde jaarweging geldt voor de omzet.",
        "ebitda_amounts_rounded_note": "Bedragen afgerond op €K tenzij anders vermeld.",
        "ebitda_adjustments_suffix": "aanp.",
        "ebitda_weighting_basis_note": "Waardering gebruikt gewogen EBITDA van {amount} (meerjarige weging, opgeslagen jaarweging). Dit is geen aanvullende normalisatie ten opzichte van het laatste boekjaar.",
        "ebitda_weighting_basis_note_prior_year_norms": (
            "Waardering gebruikt gewogen EBITDA van {amount} (meerjarige weging, "
            "opgeslagen jaarweging). Deze basis omvat normalisaties uit eerdere "
            "jaren; dit is geen aanvullende normalisatie bovenop het laatste "
            "boekjaar."
        ),
        "ebitda_real_estate_carve_out_note": "Vastgoed is uitgesloten uit de transactie: boekwaarde {book_value}. Jaarlijkse fictieve huur van {market_rent} is verwerkt in de EBITDA-basis.",
        # Disclaimers
        "disc_custom_disclaimer_title": "Voorbehouden en formulecontroles bij dit dossier",
        "disc_title": "Belangrijke Opmerkingen",
        "disc_primary_title": "Indicatieve Schatting — Geen Financieel Advies",
        "disc_primary_text": "Dit document biedt een indicatieve waardeschatting uitsluitend ter informatie. Het vormt geen financieel, juridisch of fiscaal advies, geen fairness opinion, en geen wettelijke waardering volgens Belgisch vennootschapsrecht (WVV). Win onafhankelijk professioneel advies in voordat u investerings- of transactiebeslissingen neemt.",
        "disc_custom_disclaimer_matches_primary_body": "De vastgelegde dossierspecifieke tekst komt overeen met de standaarddisclaimer van dit rapport. Er is geen afwijkende aanvullende tekst toegevoegd.",
        "disc_regulatory_title": "Regelgevende Status",
        "disc_regulatory_text": "Dit rapport is softwarematig gegenereerde, indicatieve informatie. Het is geen wettelijke waardering of verslag voor een specifieke toepassing onder het WVV, geen fairness opinion, audit of beleggingsadvies, en geen gereglementeerde beleggingsdienst.",
        "disc_data_dependency_title": "Data-afhankelijkheid",
        "disc_data_dependency_text": "De analyse is gebaseerd op verstrekte informatie zonder onafhankelijke audit. De klant en degene die de brondata aanlevert, blijven verantwoordelijk voor de juistheid en volledigheid van die data.",
        "disc_third_party_title": "Derden Beperking",
        "disc_third_party_text": "Opgesteld uitsluitend voor {company_name}. Derden mogen niet op dit rapport vertrouwen zonder voorafgaande schriftelijke toestemming van Upswitch en, waar van toepassing, de opsteller.",
        "disc_validity_title": "Referentieperiode",
        "disc_validity_text": "Bij ongewijzigde feiten bedoeld als referentie gedurende",
        "disc_validity_days": "maximaal 90 dagen vanaf",
        "disc_validity_until_label": "Herzien uiterlijk op",
        "disc_legal_summary_title": "Juridische Samenvatting",
        "disc_legal_item_1": "Alleen indicatieve schatting — geen financieel advies of wettelijke waardering",
        "disc_legal_item_2": "Gebaseerd op verstrekte data — niet onafhankelijk geaudit",
        "disc_legal_item_3": "Alleen voor genoemde ontvanger — vertrouwen door derden vereist toestemming",
        "disc_legal_footer": "Volledige voorwaarden op upswitch.app/terms-and-conditions • Belgisch recht van toepassing",
        "disc_methodology_title": "Methodologie",
        "disc_methodology_default": "Marktbenadering met EV/EBITDA-multiples, conform gangbare waarderingspraktijk. Alternatieve methodes (DCF, asset-based) kunnen andere resultaten opleveren.",
        "disc_methodology_asset_default": "Substantiewaardering op basis van boekhoudkundig eigen vermogen, documenteerbare balanscorrecties en latente belastingimpact. Operationele metrics worden uitsluitend als sanity check gebruikt.",
        "disc_methodology_yield_default": "Vastgoed-yield waardering op basis van duurzame netto huur, marktconforme cap-rate en NAV-vloer. Operationele EBITDA-multiples zijn geen primaire waarderingsdriver.",
        "disc_benchmarks_label": "Referentiepunten",
        "disc_benchmarks_default": "Europese KMO-transactiedata",
        "disc_revenue_band": "omzetband",
        "disc_sector_label": "Referentiesector",
        "disc_technical_standards": "Rapportstructuur geïnspireerd op IVS; geen volledige IVS- of USPAP-opdracht tenzij afzonderlijk overeengekomen.",
        "disc_quality_notes_title": "Datakwaliteit Opmerkingen",
        "disc_quality_more_label": "+ %d meer — zie Studio Co-pilot voor de volledige lijst",
        "disc_prepared_by": "Opgesteld door",
        "disc_ref_label": "Ref",
        "disc_references_title": "Bronnen & Referenties",
        "disc_references_intro": "De waarderingsmethodologie in dit rapport is gebaseerd op de volgende academische bronnen en vakstandaarden:",
        "disc_references_asset_intro": "De asset-gedreven methodologie in dit rapport steunt op algemeen aanvaarde waarderingsliteratuur en vakstandaarden voor balanssubstantie, NAV en income-capitalisation.",
        "disc_biblio_damodaran": "Damodaran, A. (2012). <em>Investment Valuation</em>. 3e dr. Wiley.",
        "disc_biblio_koller": (
            "Koller, T., Goedhart, M. &amp; Wessels, D. (2020). "
            "<em>Valuation: Measuring and Managing the Value of Companies</em>. 7e dr. McKinsey &amp; Company / Wiley."
        ),
        "disc_biblio_pratt": "Pratt, S. P. &amp; Niculita, A. V. (2008). <em>Valuing a Business: The Analysis and Appraisal of Closely Held Companies</em>. 5e dr. McGraw-Hill.",
        "disc_biblio_hitchner": "Hitchner, J. (2017). <em>Financial Valuation</em>. 4e dr. Wiley.",
        "disc_biblio_trugman": "Trugman, G. (2017). <em>Understanding Business Valuation</em>. 5e dr. AICPA.",
        "disc_biblio_pepperdine": "Pepperdine Private Capital Markets Report (2024).",
        "disc_biblio_vfb": "VFB Belgium – Private Company Valuation Data (2024).",
        "disc_biblio_ibba": "IBBA Market Pulse Survey (2024).",
        "disc_biblio_ivs": "International Valuation Standards (IVS), editie 2024 (effectief 31 januari 2025), IVSC — methodologische referentie, geen conformiteitsclaim.",
        "disc_biblio_vlerick": "Vlerick Business School – Belgian SME Benchmark Data.",
        "disc_biblio_mercer": (
            "Mercer Capital (2017) — <em>Discount for Lack of Marketability &amp; "
            "Discount for Lack of Control</em>: typische M&A-haircuts (DLOC 10–25%, "
            "DLOM 15–35%)."
        ),
        "disc_biblio_marktlink": (
            "Marktlink + Vlerick (2024) — Belgisch SME-multiples-handboek; peer-set "
            "kalibratie voor de EV/EBITDA-multiple per sector × omzet-band × regio."
        ),
        "disc_biblio_asset_nav": (
            "NAV / adjusted net asset value — balanssubstantie, reële-waarde-correcties "
            "en latente belastingimpact als onderbouwde asset approach."
        ),
        "disc_biblio_yield_income": (
            "Inkomenskapitalisatiebenadering — duurzame netto huuropbrengst, kapitalisatievoet "
            "en NAV-vloer als vastgoed-gedreven waarderingskader."
        ),
        "disc_biblio_startup_intro": (
            "Startup-traject (pre-revenue) — toegepast wanneer de actieve methode "
            "<em>startup_valuation</em> is. De methodologie steunt op de volgende "
            "venture- en pre-seed-specifieke bronnen:"
        ),
        "disc_biblio_berkus": (
            "Berkus, D. (1996, herzien 2016/2024). <em>The Berkus Method — "
            "Valuing the Early Stage Investment</em>."
        ),
        "disc_biblio_payne": (
            "Payne, B. (2024). <em>Scorecard Valuation Methodology</em>. "
            "Angel Capital Association."
        ),
        "disc_biblio_sahlman": (
            "Sahlman, W. A. (1989, herzien). <em>The Venture Capital Method</em>. "
            "Harvard Business School Note 9-288-006."
        ),
        "disc_biblio_strebulaev": (
            "Strebulaev, I. (2024). <em>The Venture Mindset</em>. " "Stanford GSB / Portfolio."
        ),
        "disc_biblio_atomico": (
            "Atomico (2024). <em>State of European Tech 2024</em> — Benelux pre-seed dataset."
        ),
        "disc_biblio_dealroom": (
            "Dealroom (2024). <em>Benelux Venture Capital Report 2024</em> — "
            "rondegrootte- en valuation-distributies."
        ),
        "disc_biblio_insead_lbs": (
            "INSEAD (2023) &amp; London Business School (2024). "
            "<em>Founder–Market Fit and Pedigree Premia in European Pre-Seed</em>."
        ),
        "disc_biblio_index_p9": (
            "Index Ventures, Point Nine, Seedcamp (2025). "
            "<em>SaaS Forward Multiple Method — Practitioner Guide</em>."
        ),
        "disc_preparer_override_title": "Aanpassing multiple (voorbereider)",
        "disc_preparer_override_template": (
            "Er werd een EV/EBITDA-baseline van {baseline}× gehanteerd, afgeleid van het opgeloste Upswitch Index-benchmarkcontract. "
            "De voorbereider paste een {adjustment_label} van {delta_abs}× toe ({applied}× toegepast). "
            "Rechtvaardiging: {reason}."
        ),
        "preparer_adjustment_premium": "premie",
        "preparer_adjustment_discount": "korting",
        "preparer_reason_strategic_buyer_premium": "premie strategische koper",
        "preparer_reason_exceptional_management_premium": "premie uitzonderlijk management",
        "preparer_reason_key_person_discount": "korting sleutelpersoon / afhankelijkheid",
        "preparer_reason_real_estate_included": "onroerend goed inbegrepen",
        "preparer_reason_customer_concentration": "klantenconcentratie",
        "preparer_reason_distressed_sale": "gedwongen of moeilijke verkoop",
        "preparer_reason_recurring_revenue_premium": "premie terugkerende omzet",
        "preparer_reason_other": "overige (zie werkpapieren)",
        # Attestation (Enterprise / accountant-branded reports only).
        "attestation_title": "Verklaring & ondertekening",
        "attestation_intro": (
            "Ondergetekende verklaart de inputgegevens, methodekeuze, rekenkundige "
            "aansluiting en beperkingen van dit rapport te hebben beoordeeld. De "
            "getoonde berekeningen zijn, voor zover de aangeleverde brondata volledig "
            "en juist zijn, reproduceerbaar op basis van de beschikbare brondata. De "
            "waardering is opgesteld op basis van algemeen aanvaarde waarderingsmethoden "
            "en het professionele oordeel van de ondergetekende bij de toepassing van "
            "sectorspecifieke multiples, normalisatiecorrecties en synthesegewichten."
        ),
        "attestation_intro_asset": (
            "Ondergetekende verklaart de inputgegevens, methodekeuze, rekenkundige "
            "aansluiting en beperkingen van dit rapport te hebben beoordeeld. De "
            "getoonde berekeningen zijn, voor zover de aangeleverde brondata volledig "
            "en juist zijn, reproduceerbaar op basis van de beschikbare brondata. De "
            "waardering is opgesteld op basis van algemeen aanvaarde waarderingsmethoden "
            "en het professionele oordeel van de ondergetekende voor balanssubstantie, "
            "documenteerbare NAV-correcties en latente belastingimpact."
        ),
        "attestation_intro_yield": (
            "Ondergetekende verklaart de inputgegevens, methodekeuze, rekenkundige "
            "aansluiting en beperkingen van dit rapport te hebben beoordeeld. De "
            "getoonde berekeningen zijn, voor zover de aangeleverde brondata volledig "
            "en juist zijn, reproduceerbaar op basis van de beschikbare brondata. De "
            "waardering is opgesteld op basis van algemeen aanvaarde waarderingsmethoden "
            "en het professionele oordeel van de ondergetekende voor duurzame netto huur, "
            "cap-rate, NAV-vloer en balanscorrecties."
        ),
        "attestation_caveat": (
            "Deze ondertekening bevestigt de uitgevoerde beoordeling; zij ontslaat "
            "partijen niet van hun eigen due diligence-verplichtingen en houdt geen "
            "garantie in op de uiteindelijke transactieprijs."
        ),
        "attestation_preparer_role": "Voor de opsteller",
        "attestation_client_role": "Voor de opdrachtgever",
        "attestation_signature_label": "Naam & handtekening",
        "attestation_date_label": "Datum",
        # SOTP-trigger warning (Executive Summary callout)
        "sotp_trigger_title": "Groepsstructuur: Sum-of-the-Parts-waardering vereist",
        "sotp_trigger_text": (
            "Deze entiteit maakt deel uit van een groepsstructuur (operationele "
            "holding of vastgoedvennootschap). De stand-alone waardering hiernaast "
            "is een nuttige diagnostiek, maar de transactie-grade waarde van de "
            "groep vereist een Sum-of-the-Parts (SOTP): elke deelneming en "
            "vastgoedentiteit afzonderlijk gewaardeerd, met eigendomspercentages, "
            "minderheidsbelangen en intercompany-eliminaties. Waar de stand-alone "
            "equity laag of negatief uitkomt, weerspiegelt dat doorgaans schulden "
            "die gefinancierd zijn tegen activa buiten deze entiteit — niet een "
            "lage onderliggende waarde."
        ),
        # Components - Footer
        "footer_indicative_estimate": "Indicatieve schatting",
        "footer_confidential": "Vertrouwelijk",
        "footer_page": "Pagina",
        "footer_of": "van",
        # Components - Header
        "header_confidential": "Vertrouwelijk",
        "header_powered_by": "Aangedreven door Upswitch",
        # Components - Sensitivity Table
        "sensitivity_title": "Gevoeligheidsanalyse",
        "sensitivity_description": "Ondernemingswaarde bij verschillende EBITDA- en multiple-scenario's (€ duizenden)",
        "sensitivity_ebitda_multiple_header": "EBITDA ↓ / multiple →",
        "sensitivity_low": "Laag",
        "sensitivity_base": "Basis",
        "sensitivity_high": "Hoog",
        "sensitivity_range": "Bandbreedte",
        "sensitivity_illustrative_note": (
            "(±20% illustratieve band — modelmatige multiple-bandbreedte niet beschikbaar voor dit rapport.)"
        ),
        "sensitivity_corner_label": "Scenario-uitersten (laag × laag → hoog × hoog)",
        # Components - Adjustments Table
        "adj_description": "Omschrijving",
        "adj_source": "Bron",
        "adj_category": "Categorie",
        "adj_status": "Status",
        "adj_amount": "Bedrag (€)",
        "adj_result": "Resultaat",
        "adj_base": "Basis",
        "adj_owner": "Eigenaar",
        "adj_non_recurring": "Eenmalig",
        "adj_personal": "Persoonlijk",
        "adj_related_party": "Verbonden partij",
        "adj_depreciation": "Afschrijving",
        "adj_tax": "Fiscaal",
        "adj_discretionary": "Discretionair",
        "adj_accounting": "Boekhoudkundig",
        "adj_real_estate": "Vastgoed",
        "adj_other": "Overig",
        "adj_approved": "Goedgekeurd",
        "adj_pending": "In behandeling",
        "adj_rejected": "Afgewezen",
        "adj_manual": "Manueel",
        # Components - Waterfall Chart
        "waterfall_title": "EBITDA Normalisatiebrug",
        "waterfall_reported": "Gerapporteerd",
        "waterfall_normalized": "Genormaliseerd",
        "waterfall_adjustment": "Aanpassing",
        "waterfall_no_data": "EBITDA normalisatiegrafiek niet beschikbaar — onvoldoende data",
        # Miscellaneous
        "adj_by": "door",
        # Tax Latencies
        "tax_latency_title": "Belastinglatenties",
        "tax_latency_description": "Latente belastingvorderingen en -verplichtingen die de vermogenspositie beïnvloeden. Deze correcties bepalen de Gecorrigeerde NAV (Intrinsieke Waarde).",
        "tax_latency_type": "Type",
        "tax_latency_desc_column": "Omschrijving",
        "tax_latency_temp_diff": "Tijdelijk verschil (€)",
        "tax_latency_rate": "Tarief",
        "tax_latency_amount": "Bedrag (€)",
        "tax_latency_active": "Actief",
        "tax_latency_passive": "Passief",
        "tax_latency_net_impact": "Netto impact op vermogenswaarde",
        "tax_latency_account_code": "Grootboek",
        "tax_latency_equity_bridge_qualifier": " (netto)",
        # Calibration Page
        "calib_title": "Waarderingskalibratie",
        "calib_sde_intro": "Voor eigenaar-geleide micro-ondernemingen passen we SDE-multiples (Seller's Discretionary Earnings / discretionaire verkoperswinst) toe. SDE omvat de EBITDA plus eigenaarssalaris en voordelen, en weerspiegelt zo de werkelijke verdiencapaciteit van een eigenaar-operator.",
        "calib_dcf_intro": "De DCF-analyse (Discounted Cash Flow) waardeert het bedrijf op basis van de contante waarde van toekomstige kasstromen. Deze methode is geschikt wanneer gedetailleerde financiële prognoses beschikbaar zijn.",
        "calib_hybrid_intro": "Een hybride benadering combineert marktmultiples en DCF als afzonderlijke waarderingsmethodes. De eindwaarde is de ingestelde gewogen synthese van beide componenten.",
        "calib_asset_intro": "Deze waardering vertrekt vanuit de balanssubstantie. Boekhoudkundig eigen vermogen, documenteerbare balanscorrecties en latente belastingimpact bepalen de gecorrigeerde NAV (substantiewaarde); EBITDA wordt enkel als operationele cross-check getoond.",
        "calib_yield_intro": "Deze waardering vertrekt vanuit het vastgoedrendement. De duurzame netto huur wordt gekapitaliseerd via een marktconforme cap-rate en getoetst aan een NAV-vloer; EBITDA-multiples zijn hier geen primaire waarderingsdriver.",
        "calib_adaptive_lens_intro": (
            "Bij de Upswitch adaptieve marktbenadering is een transactie-gekalibreerde EBITDA-multiple "
            "de primaire lens. Een verkorte DCF-crosscheck ondersteunt de bandbreedte intern; "
            "detail staat in het adaptieve hoofdstuk."
        ),
        "calib_adaptive_lens_intro_multiples_only": "Upswitch Adaptive heeft voor dit profiel de marktbenadering gekozen: een transactie-gekalibreerde EBITDA-multiple is de primaire lens. DCF draagt niet bij aan deze waardering; de hoofdwaardering werkt volledig met gekalibreerde marktmultiples. De beoordeling van de methodegeschiktheid staat in het adaptieve hoofdstuk.",
        "calib_adaptive_lens_badge": "Upswitch adaptieve marktbenadering",
        "calib_adaptive_lens_badge_multiples_only": "Upswitch Adaptive · Marktbenadering",
        "calib_multiples_intro": "Elke stap van marktmultiple naar finale ondernemingswaarde — volledige transparantie.",
        "calib_multiple_applied": "Toegepaste multiple",
        "calib_multiple_range": "Bandbreedte",
        "calib_methodology_label": "Methodologie",
        "calib_sde_market_median": "SDE Markt Mediaan",
        "calib_dcf_calculated_value": "Berekende Waarde",
        "calib_market_median": "Vertrekpunt multiple",
        "calib_dcf_market_validation": "Marktvalidatie",
        "calib_risk_discounts": "Risicokortingen",
        "calib_dcf_final_value": "Finale Waarde",
        "calib_applied": "Toegepast",
        "calib_asset_basis_label": "Waarderingsbasis",
        "calib_asset_basis_value": "Boekwaarde / NAV",
        "calib_asset_adjustments_label": "Balanscorrecties",
        "calib_asset_adjustments_value": "NAV-toets",
        "calib_asset_final_label": "Eigen vermogen (substantie, na nettoschuld)",
        "calib_yield_basis_label": "Waarderingsbasis",
        "calib_yield_basis_value": "Netto huur / cap-rate",
        "calib_yield_adjustments_label": "Validatie",
        "calib_yield_adjustments_value": "NAV-vloer",
        "calib_yield_final_label": "Yield/NAV-waarde",
        "calib_sde_badge": "SDE-multiples",
        "calib_dcf_badge": "DCF Analyse",
        "calib_hybrid_badge": "Hybride Waardering",
        "calib_asset_badge": "NAV / balanssubstantie",
        "calib_yield_badge": "Vastgoed yield",
        "calib_full_calculation": "Volledige Berekening",
        "calib_sde_bottom_text": "SDE (gewogen)",
        "calib_dcf_bottom_text": "NPV van geprojecteerde kasstromen over",
        "calib_multiples_bottom_text": "Geselecteerde waarderingsbasis",
        "calib_ref_market_band": "De benchmarkonderbouwing vermeldt de referentiewaarnemingen en hun percentielband. Bedrijfscorrecties en synthese bepalen de gerapporteerde modelbandbreedte; transactieprijsnauwkeurigheid en dekking zijn niet geverifieerd.",
        "calib_ref_market_band_reference_only": "Referentiemultiple en bandbreedte zijn verwerkt in de kalibratie; gedetailleerde peer-set of sectortabel is niet apart meegeleverd in dit dossier.",
        "calib_ref_size_discount": "Korting voor omvang en beperkte formele processen.",
        "calib_ref_size_discount_skipped": "Omvangskorting niet apart gestapeld: de SME/private-transactie-multiple verwerkt omvangsrisico al; alleen resterende bedrijfsspecifieke risico's zijn apart getoond.",
        "calib_ref_illiquidity": "Illiquiditeitskorting conform gangbare praktijk voor niet-beursgenoteerde ondernemingen (restricted-stock studies).",
        "calib_dcf_sensitivity_title": "DCF Gevoeligheidsanalyse",
        "calib_dcf_wacc_label": "WACC",
        "calib_dcf_terminal_growth": "Terminale groei",
        "calib_dcf_exit_multiple": "Exit-multiple",
        "calib_dcf_projection_years": "Projectiejaren",
        "calib_dcf_terminal_methodology_label": "Terminale methode",
        "calib_dcf_terminal_method_gordon": "Gordon Growth",
        "calib_dcf_terminal_method_exit_multiple": "Exit-multiple",
        "calib_dcf_sensitivity_note_gordon": "Gevoeligheid getoond als WACC versus terminale groei.",
        "calib_dcf_sensitivity_note_exit_multiple": "Gevoeligheid getoond als WACC versus exit-multiple.",
        "calib_dcf_terminal_value_note_gordon": "Terminale waarde",
        "calib_dcf_terminal_value_note_exit_multiple": "Terminale waarde via exit-multiple",
        "calib_dcf_wacc_buildup_label": "WACC-opbouw",
        "calib_dcf_mid_year_label": "Mid-year verdiscontering",
        "calib_dcf_mid_year_note": "Kasstromen worden verdisconteerd op 0,5 / 1,5 / 2,5 jaar in plaats van op jaareinde.",
        "calib_dcf_year_end_note": "Kasstromen worden verdisconteerd op jaareinde (1, 2, 3 …) per de gekozen conventie.",
        "calib_dcf_academic_coe_label": "Kosten eigen vermogen (CAPM)",
        "calib_dcf_terminal_split_label": "DCF-waardesplit",
        "calib_dcf_explicit_period_label": "Expliciete periode",
        "calib_dcf_terminal_period_label": "Terminale waarde",
    }
