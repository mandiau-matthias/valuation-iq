"""Accountant quality, roadmap, strategy, normalization, and growth contract fields."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReportTranslationAccountantQualityStrategyFields:
    # =========================================================================
    # ACCOUNTANT VIEW PHASE 2: ENHANCED NORMALIZATION SCHEDULE
    # =========================================================================
    accountant_norm_section_title: str = "Gedetailleerd Normalisatieschema (ASA BVS-III)"
    accountant_norm_intro: str = (
        "Het volgende schema identificeert en kwantificeert systematisch correcties die nodig zijn "
        "om fiscaal geoptimaliseerde financiële stukken om te zetten in genormaliseerde economische "
        "winsten. Elke categorie vertegenwoordigt een standaard normalisatiegebied conform "
        "<strong>ASA BVS-III Winstkwaliteit</strong> en het kader <strong>Trugman (2017, "
        "Hoofdstuk 8)</strong>."
    )
    accountant_norm_caption: str = "Uitgebreid Normalisatieschema"
    accountant_norm_col_category: str = "Categorie"
    accountant_norm_col_item: str = "Aanpassingspost"
    accountant_norm_col_amount: str = "Bedrag"
    accountant_norm_col_rationale: str = "Onderbouwing / Bron"
    accountant_norm_col_status: str = "Status"
    accountant_norm_section_owner: str = "1. Normalisatie Eigenaarsvergoeding"
    accountant_norm_owner_salary: str = "Eigenaarsalaris Boven/Onder Marktconform"
    accountant_norm_owner_salary_default: str = "Correctie naar marktconform vervangingssalaris"
    accountant_norm_owner_salary_no: str = (
        "Eigenaarsvergoeding op marktniveau (geen correctie nodig)"
    )
    accountant_norm_status_applied: str = "Toegepast"
    accountant_norm_status_na: str = "N.v.t."
    accountant_norm_section_discretionary: str = "2. Discretionaire & Persoonlijke Uitgaven"
    accountant_norm_personal_auto: str = "Persoonlijke Voertuigkosten"
    accountant_norm_personal_auto_caption: str = (
        "Geen persoonlijke voertuigkosten geïdentificeerd in operationele kosten"
    )
    accountant_norm_personal_travel: str = "Persoonlijke Reizen & Entertainment"
    accountant_norm_personal_travel_caption: str = "Geen discretionaire reiskosten geïdentificeerd"
    accountant_norm_family_comp: str = "Vergoeding Familieleden (Niet-Operationeel)"
    accountant_norm_family_comp_caption: str = (
        "Geen niet-operationele familievergoedingen geïdentificeerd"
    )
    accountant_norm_personal_insurance: str = "Persoonlijke Verzekering & Voordelen"
    accountant_norm_personal_insurance_caption: str = (
        "Geen persoonlijke verzekeringskosten geïdentificeerd"
    )
    accountant_norm_section_nonrecurring: str = "3. Eenmalige Posten"
    accountant_norm_litigation: str = "Geschilbeslechtingen / Juridische Kosten"
    accountant_norm_litigation_caption: str = "Geen eenmalige juridische kosten geïdentificeerd"
    accountant_norm_restructuring: str = "Herstructurerings- / Reorganisatiekosten"
    accountant_norm_restructuring_caption: str = "Geen herstructureringskosten geïdentificeerd"
    accountant_norm_asset_sale: str = "Winsten / Verliezen op Activaverkoop"
    accountant_norm_asset_sale_caption: str = "Geen activaverkopen in periode"
    accountant_norm_covid: str = "COVID-19 / Pandemiesteun"
    accountant_norm_covid_caption: str = "Geen overheidssubsidies geïdentificeerd"
    accountant_norm_section_other: str = "4. Overige Normalisatieposten"
    accountant_norm_related_party: str = "Verbonden Partij Transacties (Boven/Onder Markt)"
    accountant_norm_related_party_caption: str = (
        "Geen verbonden partij transacties tegen niet-marktconforme voorwaarden"
    )
    accountant_norm_excess_rent: str = "Overmatige Huur / Onder-Markt Huur"
    accountant_norm_excess_rent_caption: str = "Huurkosten op marktniveau"
    accountant_norm_professional_fees: str = "Professionele Honoraria (Eenmalige Advies)"
    accountant_norm_professional_fees_caption: str = (
        "Geen eenmalige adviseringshonoraria geïdentificeerd"
    )
    accountant_norm_total_label: str = "Totaal Normalisatiecorrecties"
    accountant_norm_adjustments_applied: str = "Correcties toegepast"
    accountant_norm_no_material: str = "Geen materiële correcties vereist"
    accountant_norm_status_reviewed: str = "Beoordeeld"
    accountant_norm_status_standard: str = "Standaard"
    accountant_norm_normalized_label: str = "Genormaliseerde EBITDA"
    accountant_norm_sustainable_earning: str = "Duurzame Winstgevendheid"
    accountant_norm_valuation_basis: str = "Waarderingsbasis"
    accountant_norm_data_limit_title: str = "Mededeling over de databeperking"
    accountant_norm_data_limit_body: str = (
        "<strong>Beperkte Zichtbaarheid:</strong> Dit normalisatieschema is opgesteld met "
        "{availability} financiële datazichtbaarheid. Een uitgebreide ASA BVS-III "
        "Winstkwaliteitsanalyse vereist toegang tot:"
    )
    accountant_norm_data_limit_default_avail: str = "beperkte"
    accountant_norm_data_limit_item1: str = (
        "Gedetailleerde grootboekuitsplitsing per kostencategorie"
    )
    accountant_norm_data_limit_item2: str = (
        "Documentatie eigenaarsvergoeding (arbeidscontracten, voordeelgegevens)"
    )
    accountant_norm_data_limit_item3: str = (
        "Meerjarige historische financiële stukken (3-5 jaar aanbevolen)"
    )
    accountant_norm_data_limit_item4: str = "Belastingaangiftes voor kruisvalidatie"
    accountant_norm_data_limit_footer: str = (
        "De waardering past <strong>conservatieve kwaliteitscorrecties op de multiple</strong> toe "
        "(Stap 2.5: Kwaliteitskalibratie) om rekening te houden met potentieel niet bekendgemaakte "
        "eigenaarsvoordelen en discretionaire uitgaven."
    )
    accountant_norm_categories_title: str = "ASA BVS-III Normalisatiecategorieën"
    accountant_norm_standard_categories: str = "Standaard Aanpassingscategorieën"
    accountant_norm_cat_owner: str = (
        "<strong>Eigenaarsvergoeding:</strong> Aanpassen naar marktconform vervangingstarief"
    )
    accountant_norm_cat_personal: str = (
        "<strong>Persoonlijke Uitgaven:</strong> Voertuigen, reizen, entertainment"
    )
    accountant_norm_cat_family: str = (
        "<strong>Familieleden:</strong> Boven-marktconforme familievergoeding"
    )
    accountant_norm_cat_nonrecurring: str = (
        "<strong>Eenmalige Posten:</strong> Eenmalige winsten/verliezen"
    )
    accountant_norm_cat_related: str = (
        "<strong>Verbonden Partij Transacties:</strong> Niet-marktconforme prijzen"
    )
    accountant_norm_academic_foundation: str = "Academische Basis"
    accountant_norm_acad_trugman: str = (
        "<strong>Trugman (2017):</strong> Hoofdstuk 8 - Normalisatiekader"
    )
    accountant_norm_acad_hitchner: str = (
        "<strong>Hitchner (2017):</strong> Hoofdstuk 11 - Winstkwaliteit"
    )
    accountant_norm_acad_pratt: str = (
        "<strong>Pratt & Niculita (2008):</strong> Hoofdstuk 14 - KMO-Correcties"
    )
    accountant_norm_acad_asa: str = "<strong>ASA BVS-III:</strong> Standaarden Winstkwaliteit"
    accountant_norm_acad_aicpa: str = (
        "<strong>AICPA BVS-VII:</strong> Vereisten Uitgebreide Waardering"
    )
    accountant_norm_enhanced_disclosure_title: str = "Vereiste Uitgebreide Bekendmaking"
    accountant_norm_enhanced_disclosure_body: str = (
        "<strong>Fiduciaire Standaard:</strong> Voor waarderingen die fairness opinions, geschillen "
        "of regelgevingsdocumenten ondersteunen, vereist ASA BVS-III een volledig "
        "normalisatieschema met gedetailleerde documentatie van elke aanpassingscategorie. Dit "
        "uitgebreide schema vertegenwoordigt het minimumkader; werkelijke implementatie vereist "
        "toegang tot gedetailleerde financiële stukken en managementinterviews om elke categorie "
        "te kwantificeren."
    )

    # =========================================================================
    # ACCOUNTANT VIEW PHASE 2: BUSINESS VITALITY DASHBOARD
    # =========================================================================
    accountant_vitality_section_title: str = (
        "Sectie 4.1 — Bedrijfsvitaliteit & Financiële Gezondheid"
    )
    accountant_vitality_intro: str = (
        "Deze sectie evalueert de operationele veerkracht van de Onderneming via systematische "
        "analyse van liquiditeits-, solvabiliteits- en efficiëntiemetrieken. Ons "
        "beoordelingskader past <strong>Primitief 4: Gedeelde Realiteit</strong>-normen toe om "
        "structurele gezondheidsindicatoren te kwantificeren die institutionele beleggers "
        "prioriteren bij beoordeling van KMO-overnamedoelen."
    )
    accountant_vitality_market_context: str = (
        "<strong>Marktcontext:</strong> Empirisch onderzoek toont aan dat institutionele kopers "
        "waarderingsmultiples systematisch aanpassen op basis van vitaliteitsbeoordelingen. "
        "Ondernemingen met sterke vitaliteitsscores (75%+) commanderen doorgaans "
        "waarderingspremies van 15-25%, terwijl zwakke vitaliteitsmetrieken multiple-kortingen van "
        "0,3x-0,5x triggeren door verhoogd waargenomen transactierisico."
    )
    accountant_vitality_liquidity_title: str = "Beoordeling van liquiditeit en solvabiliteit"
    accountant_vitality_liquidity_intro: str = (
        "Operationele veerkracht is een functie van liquiditeit, solvabiliteit en efficiëntie. Dit "
        "dashboard biedt een beoordeling op hoog niveau van de structurele gezondheid van de "
        "Onderneming vergeleken met sectorbenchmarks, en identificeert potentiële "
        "kwetsbaarheden die de ondernemingswaarde kunnen beïnvloeden."
    )
    accountant_vitality_caption: str = "Beoordeling van vitaliteitsindicatoren"
    accountant_vitality_col_indicator: str = "Gezondheidsindicator"
    accountant_vitality_col_value: str = "Waarde"
    accountant_vitality_col_assessment: str = "Beoordeling"
    accountant_vitality_col_impact: str = "Waarderingsimpact"
    accountant_vitality_score_summary_title: str = "Samenvatting Vitaliteitsscore"
    accountant_vitality_score_label: str = "Bedrijfsvitaliteitsscore"
    accountant_vitality_excellent: str = (
        "<strong>Uitstekende Vitaliteit:</strong> Sterke liquiditeits- en solvabiliteitspositie ondersteunt premium waarderingsmultiples"
    )
    accountant_vitality_moderate: str = (
        "<strong>Gematigde Vitaliteit:</strong> Acceptabele structurele gezondheid met ruimte voor operationele verbeteringen"
    )
    accountant_vitality_weak: str = (
        "<strong>Zwakke Vitaliteit:</strong> Significante structurele kwetsbaarheden kunnen waarderingskortingen triggeren"
    )
    accountant_vitality_unavailable_title: str = "Vitaliteitsindicatoren niet beschikbaar"
    accountant_vitality_unavailable_body: str = (
        "Financiële gezondheidsdata is niet beschikbaar voor vitaliteitsbeoordeling. Dit vormt een materiële beperking voor uitgebreide risicobeoordeling."
    )
    accountant_vitality_growth_title: str = "Analyse Groeitraject"
    accountant_vitality_growth_intro: str = (
        "Duurzame groeipatronen zijn kritieke indicatoren van bedrijfsvitaliteit. Deze analyse "
        "evalueert historische groeitrends en hun implicaties voor de voorspelbaarheid van "
        "toekomstige prestaties."
    )
    accountant_vitality_primitive_title: str = "Primitief 4: Kader Gedeelde Realiteit"
    accountant_vitality_primitive_body: str = (
        "<strong>IVS 105:</strong> Waardering moet alle factoren in overweging nemen die "
        "marktdeelnemers redelijkerwijs zouden overwegen. Bedrijfsvitaliteitsmetrieken bieden de "
        "empirische basis voor het beoordelen van ondernemingsrisico en het bepalen van passende "
        "waarderingscorrecties."
    )

    # =========================================================================
    # ACCOUNTANT VIEW PHASE 2: DATA QUALITY COMPLIANCE
    # =========================================================================
    accountant_dq_section_title: str = (
        "Sectie 4.2 — Datakwaliteit & Conformiteit Professionele Standaarden"
    )
    accountant_dq_intro: str = (
        "Beoordeling van datakwaliteit vormt de basis van waarderingsgeloofwaardigheid door "
        "systematische evaluatie van de integriteit, volledigheid en betrouwbaarheid van "
        "financiële informatie. Deze sectie past <strong>ASA BVS-III</strong>-normen toe om "
        "vertrouwensniveaus van data en hun impact op waarderingszekerheid te kwantificeren."
    )
    accountant_dq_pro_standard: str = (
        "<strong>Professionele Standaard:</strong> USPAP vereist dat waarderingsprofessionals "
        "datakwaliteit beoordelen en vertrouwensniveaus dienovereenkomstig aanpassen. Data van "
        "lage kwaliteit triggert waarderingskortingen van 0,2x-0,4x om verhoogde onzekerheid en "
        "due diligence-risico te weerspiegelen."
    )
    accountant_dq_assessment_title: str = "Beoordeling van de datakwaliteit"
    accountant_dq_assessment_intro: str = (
        "De betrouwbaarheid van deze waardering is verankerd in de integriteit van de "
        "onderliggende financiële data. We beoordelen de documentatiekwaliteit om te waarborgen dat "
        "het 'Economische Waarheid'-Primitief behouden blijft en kwantificeren het "
        "vertrouwensniveau voor institutionele stakeholders."
    )
    accountant_dq_overall_label: str = "Algemene Datakwaliteit"
    accountant_dq_overall_caption: str = "Integriteit van inputs en documentatie"
    accountant_dq_confidence_label: str = "Vertrouwensscore"
    accountant_dq_confidence_caption: str = "Verdedigbaarheidsbeoordeling voor waarderingsconclusie"
    accountant_dq_dimensions_title: str = "Kwaliteitsdimensies"
    accountant_dq_dim_completeness: str = "Documentatiedekking en databeschikbaarheid"
    accountant_dq_dim_accuracy: str = "Numerieke precisie en berekeningsverificatie"
    accountant_dq_dim_consistency: str = "Interne coherentie en kruisvalidatie"
    accountant_dq_dim_timeliness: str = "Actualiteit van financiële informatie"
    accountant_dq_dim_default: str = "Dimensie kwaliteitsbeoordeling"
    accountant_dq_warnings_title: str = "Waarschuwingen Datakwaliteit"
    accountant_dq_recommendation_label: str = "Aanbeveling:"
    accountant_dq_unavailable_title: str = "Beoordeling van datakwaliteit niet beschikbaar"
    accountant_dq_unavailable_body: str = (
        "Gedetailleerde datakwaliteitsmetrieken zijn niet beschikbaar voor deze waardering. Dit vormt een materiële beperking die het vertrouwen in de waarderingsconclusie beïnvloedt."
    )
    accountant_dq_guardrail_title: str = "Academische Vangrail"
    accountant_dq_guardrail_body: str = (
        "<strong>Hitchner (2017):</strong> Financiële analyse moet voorafgaan aan waardering om "
        "vervormingen te identificeren en de duurzaamheid van de winstgevingsbasis te waarborgen. "
        "Deze beoordeling voldoet aan de kwantitatieve analysevereisten van <strong>ASA BVS-III</strong> "
        "en <strong>USPAP</strong>-normen voor evaluatie van datakwaliteit."
    )

    # =========================================================================
    # ACCOUNTANT VIEW PHASE 2: STRATEGIC ROADMAP
    # =========================================================================
    accountant_roadmap_section_title: str = "Sectie 5 — Waarderingsconclusie & Marktcontext"
    accountant_roadmap_intro: str = (
        "Deze sectie presenteert het hoogtepunt van de waarderingsanalyse, en integreert "
        "marktbenchmarks van transacties met de uiteindelijke conclusie over de "
        "ondernemingswaarde. Conform <strong>USPAP Standaard 10</strong> en <strong>IVS 105 "
        "(Waarderingsbenaderingen en Methoden)</strong> bieden wij vergelijkende marktmultiples "
        "naast het gesynthetiseerde waarderingsbereik om geïnformeerde strategische "
        "besluitvorming mogelijk te maken."
    )
    accountant_roadmap_consistency: str = (
        "<strong>Methodologische Consistentie:</strong> Transactiemultiples zijn gekalibreerd "
        "tegen vergelijkbare verkoopdata van soortgelijke ondernemingen, systematisch aangepast "
        "voor verschillen in omvang, groeitrajecten en risicoprofielen. De uiteindelijke "
        "waarderingsconclusie verwerkt alle methodologische correcties met behoud van "
        "mathematische verzoening en professionele verdedigbaarheid."
    )
    accountant_roadmap_benchmarks_title: str = "Marktbenchmarks Transacties"
    accountant_roadmap_industry_multiples: str = "Sectorspecifieke Transactiemultiples"
    accountant_roadmap_ev_ebitda_label: str = "EV/EBITDA-multiple"
    accountant_roadmap_median_label: str = "Mediaan"
    accountant_roadmap_multiple_range: str = "Bandbreedte multiple"
    accountant_roadmap_p25_p75: str = "P25-P75"
    accountant_roadmap_typical_margin: str = "Typische EBITDA-Marge"
    accountant_roadmap_industry_label: str = "Sector"
    accountant_roadmap_synthesized_label: str = (
        "Gesynthetiseerde Intrinsieke Waarde (Eigen Vermogen)"
    )
    accountant_roadmap_valuation_range_label: str = "Waarderingsbereik"
    accountant_roadmap_to_label: str = "tot"
    accountant_roadmap_listing_price_label: str = "Voorgestelde Vraagprijs"
    accountant_roadmap_premium_suffix: str = "Premie"
    accountant_roadmap_premium_caption: str = (
        "Strategische premie toegepast op multiple; biedt onderhandelingsbuffer."
    )
    accountant_roadmap_not_available: str = "Niet beschikbaar"

    # =========================================================================
    # ACCOUNTANT VIEW PHASE 2: STRATEGIC ASSESSMENT
    # =========================================================================
    accountant_strategic_section_title: str = (
        "Sectie 1.1 — Strategische Beoordeling & Waardeoptimalisatie"
    )
    accountant_strategic_intro: str = (
        "Deze sectie biedt een systematische beoordeling van de strategische positionering van de "
        "Onderneming en identificeert kansen voor waardeoptimalisatie. Onze analyse put uit "
        "empirisch waarderingsonderzoek en vergelijkbare transactiedata om zowel huidige "
        "waardedrijvers als uitvoerbare verbeteringen die de ondernemingswaarde verhogen, te "
        "kwantificeren."
    )
    accountant_strategic_methodology: str = (
        "<strong>Methodologische Basis:</strong> Deze beoordeling voldoet aan USPAP Standaard 9 "
        "en IVS 105, en verwerkt marktafgeleide correcties uit analyse van vergelijkbare "
        "transacties. Alle waardedrijvers en risicofactoren zijn berekend uit feitelijke "
        "financiële data, ondersteund door academisch onderzoek (Damodaran 2012, Koller 2020, "
        "Trugman 2017)."
    )
    accountant_strategic_drivers_title: str = "Primaire Waardedrijvers"
    accountant_strategic_drivers_intro: str = (
        "De volgende factoren ondersteunen momenteel de waardering van de Onderneming en "
        "vertegenwoordigen duurzame concurrentievoordelen."
    )
    accountant_strategic_risks_title: str = "Kritieke Risico-Overwegingen"
    accountant_strategic_risks_intro: str = (
        "Deze factoren beperken momenteel de waarderingsmultiples en vertegenwoordigen gebieden "
        "die managementaandacht vereisen om de volledige ondernemingswaarde te ontsluiten."
    )

    # =========================================================================
    # ACCOUNTANT VIEW PHASE 2: USER NORMALIZATION
    # =========================================================================
    accountant_un_section_title: str = (
        "Sectie 2 — Economische Realiteit (Gebruikersgedefinieerde EBITDA-Normalisatie)"
    )
    accountant_un_methodology_note: str = (
        "<strong>Methodologische Opmerking:</strong> De volgende EBITDA-normalisatiecorrecties "
        "zijn uitgevoerd door de gebruiker om duurzame winstgevendheid te reconstrueren. Deze "
        "correcties weerspiegelen gebruikersspecifieke kennis van de bedrijfsactiviteiten en "
        "financiële structuur, en vervangen geautomatiseerde normalisatieberekeningen."
    )
    accountant_un_year_normalization: str = "Normalisatie"
    accountant_un_bridge_caption: str = "EBITDA-Normalisatiebrug"
    accountant_un_col_item: str = "Post"
    accountant_un_col_amount: str = "Bedrag (€)"
    accountant_un_col_rationale: str = "Onderbouwing"
    accountant_un_reported_ebitda: str = "Gerapporteerde EBITDA"
    accountant_un_as_shown: str = "Zoals weergegeven in financiële stukken"
    accountant_un_custom_label: str = "AANGEPAST"
    accountant_un_total_adjustments: str = "Totaal Correcties"
    accountant_un_of_reported: str = "% van gerapporteerd"
    accountant_un_normalized: str = "Genormaliseerde EBITDA"
    accountant_un_true_performance: str = "Werkelijke operationele prestaties"
    accountant_un_performed_label: str = "Normalisatie uitgevoerd:"
    accountant_un_confidence_label: str = "Vertrouwensniveau:"
    accountant_un_version_label: str = "Waarderingsversie:"
    accountant_un_disclosure_title: str = "Bekendmaking Gebruikersnormalisatie"
    accountant_un_disclosure_body: str = (
        "Deze gebruikersgedefinieerde correcties vervangen de geautomatiseerde "
        "normalisatieberekeningen die anders zouden worden uitgevoerd in Stap 2.5 "
        "(Kwaliteitskalibratie). De waardering is berekend met de bovenstaande genormaliseerde "
        "EBITDA-waarden. Alle correcties zijn gedocumenteerd met onderbouwing en zijn opgenomen in "
        "het volledige audittraject. Deze normalisatiemethodologie volgt gangbare professionele "
        "praktijk voor EBITDA-reconstructie in KMO-waarderingen."
    )

    # =========================================================================
    # ACCOUNTANT VIEW PHASE 2: GROWTH METRICS
    # =========================================================================
    accountant_growth_title: str = "Analyse Groeimetrieken"
    accountant_growth_cagr3y: str = "3-Jaar CAGR"
    accountant_growth_cagr_caption: str = "Samengestelde jaarlijkse groei."
    accountant_growth_yoy: str = "Jaar-op-Jaar Omzetgroei"
    accountant_growth_yoy_caption: str = "Recentste boekjaar."
    accountant_growth_historical_title: str = "Historische Groeitrends"
    accountant_growth_col_year: str = "Jaar"
    accountant_growth_col_revenue: str = "Omzet"
    accountant_growth_col_growth: str = "Groei"
    accountant_growth_trajectory_positive: str = (
        "<strong>Groeitraject:</strong> Positieve CAGR duidt op consistente groei over de analyseperiode en dient als belangrijke waardedrijver voor de waardering."
    )
    accountant_growth_trajectory_negative: str = (
        "<strong>Groeitraject:</strong> Negatieve CAGR duidt op afnemende omzettrends, wat de waarderingsmultiples en aannames over toekomstige groei kan beïnvloeden."
    )
    accountant_growth_trajectory_flat: str = (
        "<strong>Groeitraject:</strong> Stabiel omzetprofiel met vlakke groei over de analyseperiode."
    )
    accountant_growth_insufficient: str = (
        "<strong>Onvoldoende Data:</strong> Niet in staat groeimetrieken te berekenen. Minimaal 2 jaar historische financiële data is vereist."
    )

    # =========================================================================
