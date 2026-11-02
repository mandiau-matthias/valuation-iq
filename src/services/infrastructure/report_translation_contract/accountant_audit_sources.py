"""Accountant audit-trail and information-source contract fields."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReportTranslationAccountantAuditSourceFields:
    # =========================================================================
    # ACCOUNTANT VIEW PHASE 2: APPENDIX AUDIT TRAIL (_appendix_audit_trail.html)
    # =========================================================================
    accountant_audit_section_title: str = (
        "Bijlage E — Berekeningsmethodologie & Algoritmisch Audittraject"
    )
    accountant_audit_verification_badge: str = "Methodologie-Verificatie"
    accountant_audit_intro: str = (
        "Deze bijlage levert het volledige algoritmische audittraject dat <strong>Primitief 2: "
        "Algoritmische Verdedigbaarheid</strong> demonstreert — een systematische, stapsgewijze "
        "reconstructie van de waarderingsmethodologie. Elke berekeningsstap, aanpassingsfactor en "
        "analytische beslissing is gedocumenteerd om volledige reproduceerbaarheid en conformiteit "
        "met <strong>USPAP Standaard 9 (Ontwikkelingsvereisten)</strong> voor professionele "
        "verdedigbaarheid te waarborgen."
    )
    accountant_audit_documentation_label: str = "Conform professionele documentatiestandaarden:"
    accountant_audit_documentation_body: str = (
        "USPAP Standaard 9 vereist uitgebreide documentatie van het waarderingsproces, inclusief "
        "alle veronderstellingen, databronnen en analytische methodologieën. Dit audittraject maakt "
        "onafhankelijke peer review, verificatie van regelgevingsconformiteit en stakeholderbegrip "
        "van de waarderingsbasis mogelijk en ondersteunt de fiduciaire standaard die vereist is "
        "voor institutionele transacties."
    )
    accountant_audit_table_title: str = "Audittraject Berekeningsmethodologie"
    accountant_audit_table_intro: str = (
        "De volgende tabel documenteert elke stap van het waarderingsproces en levert de "
        "onderbouwing, databronnen en methodologische beslissingen die hebben geleid tot de "
        "uiteindelijke waarderingsconclusie. Deze transparantie zorgt ervoor dat institutionele "
        "stakeholders de analyse onafhankelijk kunnen verifiëren."
    )
    accountant_audit_caption: str = (
        "Audittraject Waarderingsproces — Volledige Methodologische Documentatie"
    )
    accountant_audit_col_step: str = "Stap"
    accountant_audit_col_process: str = "Procescomponent"
    accountant_audit_col_rationale: str = "Methodologische Onderbouwing"
    accountant_audit_col_source: str = "Databron"
    accountant_audit_col_status: str = "Status"
    accountant_audit_step_prefix: str = "Stap"
    accountant_audit_calc_step_default: str = "Berekeningsstap uitgevoerd"
    accountant_audit_reference_label: str = "Referentie:"
    accountant_audit_internal_calc: str = "Interne berekening"
    accountant_audit_step1_name: str = "Beoordeling van de datakwaliteit"
    accountant_audit_step1_rationale: str = (
        "Uitgebreide evaluatie van de integriteit, volledigheid en betrouwbaarheid van financiële "
        "data. Kwaliteitsmetrieken berekend voor vertrouwensscoring en waarderingscorrecties."
    )
    accountant_audit_step1_ref: str = "Referentie: ASA BVS-III, Standaarden Datakwaliteit"
    accountant_audit_step1_source: str = "Financiële stukken & metadata"
    accountant_audit_step2_name: str = "Invoergegevens & Bedrijfsprofiel"
    accountant_audit_step2_rationale: str = (
        "Validatie van bedrijfsprofiel en opname van financiële data. Bedrijfskenmerken, "
        "sectorclassificatie en operationele metrieken vastgesteld voor het waarderingskader."
    )
    accountant_audit_step2_ref: str = "Referentie: IVS 105, Standaarden Bedrijfsbeschrijving"
    accountant_audit_step2_source: str = "Gebruikersinvoer & registerdata"
    accountant_audit_step3_name: str = "Sectorbenchmarking & Multipleselectie"
    accountant_audit_step3_rationale: str = (
        "Marktgebaseerde waarderingsmultiples geselecteerd via sectorbenchmarking. Analyse van "
        "vergelijkbare ondernemingen met correcties voor omvang, groei en risico om basismultiples "
        "vast te stellen."
    )
    accountant_audit_step3_ref: str = "Referentie: VFB Belgium 2024, Trugman (2017)"
    accountant_audit_step3_source: str = "Database bedrijfstypes"
    accountant_audit_step4_name: str = "Berekening Basis Ondernemingswaarde"
    accountant_audit_step4_rationale: str = (
        "Basis ondernemingswaarde berekend met geselecteerde multiples en genormaliseerde EBITDA. "
        "Kwaliteitskalibratie toegepast op de multiple (Stap 2.5). Multiple aangepast van "
        "vergelijkbare basis naar bedrijfsspecifiek gekalibreerde multiple."
    )
    accountant_audit_step4_ref: str = "Referentie: AICPA BVS-VII, Multiple-First Methodologie"
    accountant_audit_step4_source: str = "Berekend uit Stap 2 & genormaliseerde financiële stukken"
    accountant_audit_step5_name: str = "Correctie Eigenaarsconcentratie"
    accountant_audit_step5_rationale: str = (
        "Analyse van de eigenaar-werknemerratio voor de beoordeling van het sleutelpersoonrisico. Een "
        "ratio van 33% wijst op een LAAG sleutelpersoonrisico. Eigenaars vertegenwoordigen &lt;10% "
        "van het personeel, wat wijst op een diepgaande managementlaag en operationele "
        "onafhankelijkheid."
    )
    accountant_audit_step5_ref: str = "Referentie: Damodaran (2012), Kader Sleutelpersoonrisico"
    accountant_audit_step5_source: str = "Werknemersaantal & eigendomsdata"
    accountant_audit_step6_name: str = "Toepassing Omvangskorting"
    accountant_audit_step6_rationale: str = (
        "Bedrijfsomvangcorrectie toegepast op waarderingsmultiple. Omvangspremie/-korting berekend "
        "op basis van omzetschaal ten opzichte van marktvergelijkbare ondernemingen en "
        "liquiditeitsoverwegingen."
    )
    accountant_audit_step6_ref: str = "Referentie: Ibbotson SBBI (2024), Onderzoek Omvangseffect"
    accountant_audit_step6_source: str = "Omzetdata & omvangsbenchmarks"
    accountant_audit_step7_name: str = "Toepassing Liquiditeitskorting"
    accountant_audit_step7_rationale: str = (
        "Illiquiditeitskorting voor private ondernemingen toegepast op waarderingsmultiple. DLOM "
        "berekend op basis van bedrijfsomvang, groeiprofiel en verhandelbaarheidsfactoren."
    )
    accountant_audit_step7_ref: str = "Referentie: Koeplin (2000), Officer (2007), DLOM-Kader"
    accountant_audit_step7_source: str = "Verhandelbaarheids- & omvanganalyse"
    accountant_audit_step8_name: str = "Conversie Ondernemingswaarde naar Eigen Vermogen"
    accountant_audit_step8_rationale: str = (
        "Ondernemingswaarde geconverteerd naar eigenvermogenswaarde via schuldcorrectie (EV - "
        "Netto Schuld). Zorgt ervoor dat de waardering de werkelijke aandeelhouderswaarde "
        "vertegenwoordigt."
    )
    accountant_audit_step8_ref: str = "Referentie: USPAP Standaarden, Kader Eigenvermogenswaarde"
    accountant_audit_step8_source: str = "Balansgegevens"
    accountant_audit_step9_name: str = "Analyse Vertrouwensscore"
    accountant_audit_step9_rationale: str = (
        "Algemene vertrouwensscore voor de waardering berekend op basis van datakwaliteit, "
        "robuustheid van de methodologie en marktvergelijkbaarheid. Bereikmethodologie "
        "dienovereenkomstig bepaald."
    )
    accountant_audit_step9_ref: str = "Referentie: AICPA BVS-VII, Vertrouwensintervallen"
    accountant_audit_step9_source: str = "Kwaliteitsbeoordeling & methodologische analyse"
    accountant_audit_step10_name: str = "Bereikmethodologie & Eindsynthese"
    accountant_audit_step10_rationale: str = (
        "Uiteindelijk waarderingsbereik gesynthetiseerd via methodologie van multiple-dispersie. De "
        "Multiple-First aanpak voorkomt dubbeltelling van risicocorrecties over "
        "waarderingscomponenten heen."
    )
    accountant_audit_step10_ref: str = "Referentie: USPAP Standaarden, Kader Bereikmethodologie"
    accountant_audit_step10_source: str = "Geïntegreerde berekeningsresultaten"
    accountant_audit_steps_label: str = "Stappen 10-11"
    accountant_audit_step_zero: str = "Stap 0"
    accountant_audit_step_one: str = "Stap 1"
    accountant_audit_step_two: str = "Stap 2"
    accountant_audit_step_three: str = "Stap 3"
    accountant_audit_step_four: str = "Stap 4"
    accountant_audit_step_five: str = "Stap 5"
    accountant_audit_step_six: str = "Stap 6"
    accountant_audit_step_seven: str = "Stap 7"
    accountant_audit_step_nine: str = "Stap 9"
    accountant_audit_methodology_summary_title: str = "Verificatie Methodologie-Integriteit"
    accountant_audit_primary_approach_title: str = "Primaire Aanpak"
    accountant_audit_primary_approach_body: str = (
        "<strong>Marktbenadering (Multiples):</strong> Primaire methodologie geselecteerd vanwege "
        "hoge databeschikbaarheid en marktvergelijkbaarheid voor KMO-waardering."
    )
    accountant_audit_dcf_exclusion_title: str = "DCF-Uitsluiting"
    accountant_audit_dcf_exclusion_body: str = (
        "<strong>Omzet onder €1M:</strong> Inkomstenbenadering uitgesloten vanwege het "
        "kleinbedrijfeffect en voorspellingsonzekerheid bij ondernemingen met een omzet onder €1M."
    )
    accountant_audit_risk_adjustments_title: str = "Risicocorrecties"
    accountant_audit_risk_adjustments_body: str = (
        "<strong>Multiple-First Discounting:</strong> Alle risicocorrecties toegepast op de "
        "waarderingsmultiple in plaats van op de winsten, ter voorkoming van dubbeltelling en ter "
        "waarborging van mathematische verdedigbaarheid."
    )
    accountant_audit_primitive_standards_title: str = (
        "Primitief 2: Standaarden Algoritmische Verdedigbaarheid"
    )
    accountant_audit_primitive_standards_body: str = (
        "<strong>USPAP-Conformiteit:</strong> Dit audittraject demonstreert volledige methodologische "
        "transparantie zoals vereist voor professionele waarderingsstandaarden. Elke stap bevat "
        "databronnen, berekeningsonderbouwing en academische referenties om reproduceerbaarheid en "
        "regelgevingsconformiteit te waarborgen."
    )

    # =========================================================================
    # ACCOUNTANT VIEW PHASE 2: APPENDIX INFO SOURCES (_appendix_information_sources.html)
    # =========================================================================
    accountant_sources_section_title: str = (
        "Bijlage C — Informatiebronnen & Beoordeling Datatrouwbaarheid"
    )
    accountant_sources_transparency_badge: str = "Datatransparantie"
    accountant_sources_intro: str = (
        "Deze bijlage levert uitgebreide documentatie van alle databronnen, methodologieën en "
        "betrouwbaarheidsbeoordelingen die in de waarderingsanalyse zijn toegepast. Conform "
        "<strong>USPAP Standaard 9 (Documentatievereisten)</strong> en <strong>IVS 105</strong> "
        "zijn alle informatiebronnen systematisch gedocumenteerd met betrouwbaarheidsbeoordelingen "
        "om methodologische transparantie en professionele verdedigbaarheid te waarborgen."
    )
    accountant_sources_disclosure_label: str = "Professionele bekendmakingsstandaard:"
    accountant_sources_disclosure_body: str = (
        "Betrouwbaarheid van waardering is fundamenteel verankerd in datakwaliteit. Deze bijlage "
        "stelt stakeholders in staat om de robuustheid van de analytische basis onafhankelijk te "
        "beoordelen en vertrouwensniveaus aan te passen op basis van bronbetrouwbaarheid. "
        "Betrouwbaarheidsbeoordelingen volgen <strong>AICPA BVS-VII</strong>-normen voor "
        "beoordeling van data voor KMO-waardering."
    )
    accountant_sources_inventory_title: str = "Inventaris van databronnen"
    accountant_sources_inventory_intro: str = (
        "De volgende tabel inventariseert alle primaire databronnen die in deze waardering zijn "
        "gebruikt, inclusief hun beschrijvingen, toepassingen en beoordeelde "
        "betrouwbaarheidsniveaus. Betrouwbaarheidsbeoordelingen volgen AICPA BVS-VII-normen voor "
        "beoordeling van data voor KMO-waardering."
    )
    accountant_sources_caption: str = "Databronnen & Betrouwbaarheidsbeoordeling"
    accountant_sources_col_category: str = "Broncategorie"
    accountant_sources_col_description: str = "Beschrijving & Toepassing"
    accountant_sources_col_reliability: str = "Betrouwbaarheid"
    accountant_sources_col_impact: str = "Waarderingsimpact"
    accountant_sources_primary_data: str = "Primaire Data"
    accountant_sources_benchmarking_data: str = "Benchmarkingdata"
    accountant_sources_supporting_data: str = "Ondersteunende Data"
    accountant_sources_used_for_financials: str = (
        "Gebruikt voor: Omzet, EBITDA, marge-analyse, normalisatiecorrecties"
    )
    accountant_sources_used_for_multiples: str = (
        "Gebruikt voor: Ondernemingswaarde-multiples, sectorbenchmarking, omvangscorrecties"
    )
    accountant_sources_reliability_high: str = "Hoog"
    accountant_sources_reliability_medium: str = "Gematigd"
    accountant_sources_reliability_low: str = "Laag"
    accountant_sources_impact_high: str = "+10% vertrouwen"
    accountant_sources_impact_baseline: str = "Basislijn"
    accountant_sources_impact_low: str = "-15% vertrouwen"
    accountant_sources_quality_framework_title: str = "Kader Datakwaliteit"
    accountant_sources_reliability_ratings_title: str = "Betrouwbaarheidsbeoordelingen"
    accountant_sources_rating_high: str = (
        "<strong>Hoog:</strong> Geauditeerde financiële stukken, recente transacties"
    )
    accountant_sources_rating_medium: str = (
        "<strong>Gematigd:</strong> Door management opgestelde data, sectorbenchmarks"
    )
    accountant_sources_rating_low: str = (
        "<strong>Laag:</strong> Schattingen, verouderde informatie, beperkte verificatie"
    )
    accountant_sources_confidence_impact_title: str = "Impact op Vertrouwen"
    accountant_sources_confidence_high: str = (
        "<strong>+10%:</strong> Hoge betrouwbaarheid versterkt waarderingsbereik"
    )
    accountant_sources_confidence_baseline: str = (
        "<strong>Basislijn:</strong> Gematigde betrouwbaarheid vertegenwoordigt standaard marktpraktijk"
    )
    accountant_sources_confidence_low: str = (
        "<strong>-15%:</strong> Lage betrouwbaarheid leidt tot bredere waarderingsbereiken"
    )
    accountant_sources_quality_controls_title: str = "Kwaliteitscontroles"
    accountant_sources_qc_cross: str = (
        "<strong>Kruisvalidatie:</strong> Meerdere bronnen vergeleken op consistentie"
    )
    accountant_sources_qc_reasonableness: str = (
        "<strong>Redelijkheidstoetsen:</strong> Data vergeleken met sectornormen"
    )
    accountant_sources_qc_documentation: str = (
        "<strong>Documentatie:</strong> Alle veronderstellingen en beperkingen vermeld"
    )
    accountant_sources_fs_review_title: str = "Beoordeling Financiële Stukken"
    accountant_sources_fs_review_intro: str = (
        "De volgende financiële stukken zijn beoordeeld en gebruikt in de waarderingsanalyse. Alle "
        "data is getoetst op volledigheid, interne consistentie en redelijkheid."
    )
    accountant_sources_fs_reviewed_label: str = "Beoordeelde Stukken"
    accountant_sources_fs_review_date: str = "Beoordelingsdatum:"
    accountant_sources_fs_assessment: str = (
        "Beoordeling: Gematigde Betrouwbaarheid (Door Management Opgesteld)"
    )
    accountant_sources_market_data_title: str = "Marktdatabronnen & Academische Citaties"
    accountant_sources_market_data_intro: str = (
        "Marktmultiples en benchmarkingdata zijn afkomstig uit gezaghebbende academische en "
        "sectorale publicaties. Alle bronnen bevatten publicatiedata en methodologische kaders "
        "voor transparantie."
    )
    accountant_sources_col_source: str = "Bron"
    accountant_sources_col_publication: str = "Publicatie"
    accountant_sources_col_application: str = "Toepassing"
    accountant_sources_uspap_compliance_title: str = "Conformiteit USPAP-Standaarden"
    accountant_sources_uspap_compliance_body: str = (
        "<strong>IVS 105 & USPAP:</strong> Deze bekendmaking zorgt voor volledige transparantie "
        "betreffende databronnen en hun betrouwbaarheid. Gebruikers kunnen de geschiktheid van de "
        "waarderingsconclusie beoordelen op basis van de kwaliteit en aard van de onderliggende "
        "informatie. Alle bronnen zijn actueel per de waarderingsdatum en volgen professionele "
        "waarderingsstandaarden voor datadocumentatie."
    )
    accountant_sources_app_damodaran: str = (
        "Sectormultipleselectie, risicocorrecties, marktbenadering"
    )
    accountant_sources_app_koller: str = "Methodologie ondernemingswaarde, GPCM-kader"
    accountant_sources_app_trugman: str = (
        "SDE-methodologie, KMO-specifieke correcties, normalisatie"
    )
    accountant_sources_app_pratt: str = (
        "Kortingen private ondernemingen, omvangspremies, gebrek aan verhandelbaarheid"
    )
    accountant_sources_app_pepperdine: str = (
        "KMO-omvangskortingen, kalibratie multiples private ondernemingen"
    )
    accountant_sources_app_vfb: str = "Belgische marktmultiples, sectorspecifieke correcties"
    accountant_sources_app_vlerick: str = "Transactie-gebaseerde multiples, KMO-waarderingspatronen"
    accountant_sources_app_aicpa: str = "SDE-standaarden, normalisatie eigenaarsvergoeding"
    accountant_sources_app_ivs: str = "Conformiteit internationale waarderingsstandaarden"
