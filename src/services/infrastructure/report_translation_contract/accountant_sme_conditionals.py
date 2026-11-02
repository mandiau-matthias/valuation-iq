"""SME rationale, business-type analysis, conditionals, and warning contract fields."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReportTranslationAccountantSmeConditionalFields:
    # ACCOUNTANT VIEW PHASE 2: SME EXPERT RATIONALE COMPONENT
    # =========================================================================
    accountant_sme_title: str = "KMO-Expertanalyse: Bedrijfstype & Bedrijfskenmerken"
    accountant_sme_business_type_classification: str = "Bedrijfstype Classificatie"
    accountant_sme_business_type_label: str = "Bedrijfstype"
    accountant_sme_business_type_id_label: str = "Bedrijfstype ID"
    accountant_sme_industry_label: str = "Sector"
    accountant_sme_insight_classification: str = (
        "KMO-Expertinzicht — Bedrijfstypeclassificatie van wereldklasse:"
    )
    accountant_sme_insight_with_type: str = (
        "Bedrijfstype <strong>{type}</strong> is één van <strong>188 onderscheiden "
        "bedrijfstypes</strong> in onze uitgebreide database. Deze classificatie maakt "
        "<strong>KMO-waardering van wereldklasse</strong> mogelijk die veel verder gaat dan "
        "generieke sectorgemiddelden."
    )
    accountant_sme_insight_no_type: str = (
        "Deze waardering gebruikt <strong>bedrijfstype-specifieke logica</strong> uit onze "
        "database van <strong>188 onderscheiden bedrijfstypes</strong>. Dit maakt KMO-waardering "
        "van wereldklasse mogelijk."
    )
    accountant_sme_how_label: str = "Hoe Bedrijfstype de Waardering Beïnvloedt:"
    accountant_sme_multiple_selection: str = "Multiple-Selectie:"
    accountant_sme_multiple_db_default: str = (
        "Bedrijfstypespecifieke KMO-multiples uit regionale marktdata (VFB Belgium 2024, Vlerick 2023)"
    )
    accountant_sme_multiple_other_default: str = (
        "Bedrijfstypespecifieke EBITDA-multiples worden geselecteerd uit regionale KMO-marktbronnen"
    )
    accountant_sme_multiple_suffix: str = (
        "in plaats van generieke sectordatabases. Hierdoor weerspiegelen de multiples het unieke risicoprofiel van dit bedrijfstype."
    )
    accountant_sme_owner_dep_label: str = "Correcties Eigenaarsafhankelijkheid:"
    accountant_sme_owner_dep_body: str = (
        "Elk bedrijfstype heeft specifieke kenmerken van eigenaarsafhankelijkheid die direct "
        "invloed hebben op correcties voor eigenaarsconcentratie. Bedrijfstypes met hoge "
        "eigenaarsafhankelijkheid (bijv. consultancy, professionele dienstverlening) ontvangen "
        "hogere kortingen dan schaalbare bedrijfstypes (bijv. SaaS, e-commerce)."
    )
    accountant_sme_margin_label: str = "Marge-Gebaseerde Correcties:"
    accountant_sme_margin_body: str = (
        "Bedrijfstype-specifieke typische EBITDA-marges fungeren als benchmarks. Als de werkelijke "
        "marges aanzienlijk afwijken van bedrijfstype-specifieke benchmarks, worden "
        "marge-correcties toegepast om operationeel risico te weerspiegelen."
    )
    accountant_sme_methodology_sel_label: str = "Methodologie-Selectie:"
    accountant_sme_methodology_sel_body: str = (
        "Bedrijfstype-specifieke methodologievoorkeuren begeleiden of DCF of multiples "
        "geschikter is. Bedrijfstypes met hoge eigenaarsafhankelijkheid of beperkte vooruitzichten "
        "geven de voorkeur aan multiples boven DCF."
    )
    accountant_sme_academic_basis: str = "Academische Basis:"
    accountant_sme_academic_body: str = (
        "Trugman (2017), Coulon (2021) en VFB Belgium (2024) documenteren dat KMO-waarderingen "
        "bedrijfstypespecifieke correcties vereisen, en geen generieke sectormultiples. Onze "
        "database van 188 bedrijfstypes maakt <strong>KMO-waardering van wereldklasse</strong> "
        "mogelijk en weerspiegelt de unieke kenmerken van elk bedrijfstype, in lijn met de "
        "precisie van International Valuation Standards (IVS 2017) en academische "
        "KMO-waarderingspraktijken."
    )
    accountant_sme_growth_stage_title: str = "Analyse Groeifase"
    accountant_sme_growth_stage_label: str = "Groeifase Onderneming"
    accountant_sme_risk_adj_label: str = "Risicocorrectie"
    accountant_sme_startup_adj: str = "-5% tot -10% multiple-reductie"
    accountant_sme_stable_stage: str = "Stabiele Fase"
    accountant_sme_stable_no_adj: str = "Geen correctie groeifase"
    accountant_sme_mature_stage: str = "Volwassen Fase"
    accountant_sme_mature_lower_risk: str = "Lager risicoprofiel"
    accountant_sme_insight_label: str = "KMO-Expertinzicht:"
    accountant_sme_startup_body: str = (
        "<strong>Startupfase ({stage})</strong>: Ondernemingen jonger dan 3 jaar of met hoge "
        "omzetvolatiliteit (>50%) staan voor verhoogd risico. Volgens academisch onderzoek "
        "(Trugman 2017, Coulon 2021) vereisen startup-KMO's een multiple-reductie van -5% tot "
        "-10% om rekening te houden met: (1) Onbewezen bedrijfsmodel, (2) Beperkte "
        "operationele historiek, (3) Hoger faalrisico, (4) Koperscepsis. De exacte correctie "
        "(-5% tot -10%) schaalt met de leeftijd van de onderneming: nieuwere ondernemingen "
        "ontvangen hogere kortingen."
    )
    accountant_sme_growth_body: str = (
        "<strong>Groeifase ({stage})</strong>: Ondernemingen 3-10 jaar oud met stabiele "
        "omzetgroeipatronen. Deze fase wijst op een bewezen bedrijfsmodel en operationele "
        "stabiliteit. Geen correctie groeifase wordt toegepast, aangezien de onderneming "
        "levensvatbaarheid en marktacceptatie heeft aangetoond."
    )
    accountant_sme_mature_body: str = (
        "<strong>Volwassen Fase ({stage})</strong>: Ondernemingen ouder dan 10 jaar met "
        "gevestigde activiteiten. Volwassen KMO's hebben lagere risicoprofielen dankzij een bewezen "
        "staat van dienst, stabiele activiteiten en marktpositie. Er wordt geen korting voor de "
        "groeifase toegepast, wat de lagere risicopremie weerspiegelt die kopers vereisen."
    )
    accountant_sme_owner_dep_title: str = "Analyse Eigenaarsafhankelijkheid"
    accountant_sme_owner_dep_impact_label: str = "Impact Eigenaarsafhankelijkheid"
    accountant_sme_high_risk: str = "Hoog Risico"
    accountant_sme_medium_risk: str = "Gemiddeld Risico"
    accountant_sme_low_risk: str = "Laag Risico"
    accountant_sme_high_dep_caption: str = (
        "Aanzienlijke afhankelijkheid van sleutelpersoon - bedrijfswaarde sterk gebonden aan eigenaar"
    )
    accountant_sme_med_dep_caption: str = (
        "Gemiddelde afhankelijkheid van sleutelpersoon - enige operationele onafhankelijkheid"
    )
    accountant_sme_low_dep_caption: str = (
        "Lage afhankelijkheid van sleutelpersoon - sterke operationele onafhankelijkheid"
    )
    accountant_sme_owner_dep_intro: str = "Impact eigenaarsafhankelijkheid van"
    accountant_sme_owner_dep_intro_suffix: str = (
        "is afgeleid uit bedrijfstypekenmerken in onze database."
    )
    accountant_sme_owner_dep_high: str = (
        "<strong>Hoge eigenaarsafhankelijkheid (≥70%)</strong> wijst erop dat de onderneming "
        "sterk afhankelijk is van de persoonlijke relaties, expertise of aanwezigheid van de "
        "eigenaar. Dit creëert significant overdraagbaarheidsrisico, aangezien kopers de "
        "waardebijdrage van de eigenaar niet eenvoudig kunnen vervangen. Volgens Astrachan & "
        "Jaskiewicz (2008) en Hitchner (2017) resulteert hoge eigenaarsafhankelijkheid doorgaans "
        "in waarderingskortingen van 15-25% voor KMO's."
    )
    accountant_sme_owner_dep_medium: str = (
        "<strong>Gemiddelde eigenaarsafhankelijkheid (40-70%)</strong> wijst op gematigde "
        "afhankelijkheid van de eigenaar, met enige operationele systemen en managementdiepte op "
        "hun plaats. Dit creëert gematigd overdraagbaarheidsrisico. Volgens academisch onderzoek "
        "resulteert gemiddelde eigenaarsafhankelijkheid doorgaans in waarderingskortingen van "
        "7-15%."
    )
    accountant_sme_owner_dep_low: str = (
        "<strong>Lage eigenaarsafhankelijkheid (<40%)</strong> wijst op sterke operationele "
        "onafhankelijkheid met gevestigde systemen, managementdiepte en institutionele kennis. "
        "Dit creëert minimaal overdraagbaarheidsrisico. Volgens academisch onderzoek resulteert "
        "lage eigenaarsafhankelijkheid doorgaans in waarderingskortingen van 0-7%."
    )
    accountant_sme_owner_dep_footer: str = (
        "Deze bedrijfstype-specifieke impact van eigenaarsafhankelijkheid beïnvloedt direct de correctie eigenaarsconcentratie in Stap 4."
    )
    accountant_sme_adj_breakdown_title: str = "KMO-Specifieke Toegepaste Correcties"
    accountant_sme_adj_breakdown_intro: str = (
        "Deze correcties zijn <strong>KMO-specifiek</strong> en verschillen van de "
        "waarderingslogica voor grote ondernemingen. Elke correctie is gebaseerd op academisch "
        "onderzoek (Trugman 2017, Coulon 2021, VFB Belgium 2024, Vlerick 2023) en weerspiegelt het "
        "unieke risicoprofiel van KMO's. De correcties houden rekening met:"
    )
    accountant_sme_adj_size: str = (
        "<strong>Omvanggerelateerd risico</strong>: KMO's staan voor hogere operationele kwetsbaarheid dan grote ondernemingen,"
    )
    accountant_sme_adj_type: str = (
        "<strong>Bedrijfstypekenmerken</strong>: Eigenaarsafhankelijkheid, typische marges en schaalbaarheid variëren per bedrijfstype,"
    )
    accountant_sme_adj_growth: str = (
        "<strong>Groeifase</strong>: Startup-ondernemingen staan voor hoger risico dan volwassen ondernemingen,"
    )
    accountant_sme_adj_market: str = (
        "<strong>Marktspecifieke factoren</strong>: Belgische KMO-marktmultiples verschillen van generieke databases."
    )
    accountant_sme_adj_academic: str = (
        "<strong>Academische Basis:</strong> Koller, Goedhart & Wessels (2020) en Trugman (2017) "
        "documenteren dat KMO-waarderingen systematische correcties vereisen om overwaardering uit "
        "multiples van databases voor grote ondernemingen te voorkomen."
    )

    # =========================================================================
    # ACCOUNTANT VIEW PHASE 2: BUSINESS TYPE ANALYSIS COMPONENT
    # =========================================================================
    accountant_bta_strategic_profile: str = "Strategisch Waarderingsprofiel"
    accountant_bta_methodology_fit: str = "Marktmultiples Verkozen"
    accountant_bta_methodology_alignment: str = "Methodologie-Afstemming"
    accountant_bta_multiples_fit: str = "Multiples-Geschiktheid"
    accountant_bta_high_volume_caption: str = (
        "Groot volume aan transactiedata beschikbaar voor {type}. Marktvergelijkingen leveren sterker bewijs dan theoretische kasstromen."
    )
    accountant_bta_key_person_risk: str = "Sleutelpersoonrisico"
    accountant_bta_impact_label: str = "Impact"
    accountant_bta_critical_risk: str = (
        "Kritieke risicofactor. Waarde sterk gebonden aan eigenaarsrelaties. Significante korting gerechtvaardigd."
    )
    accountant_bta_moderate_risk: str = (
        "Gematigde risicofactor. Overgangsplan vereist om waarde te behouden."
    )
    accountant_bta_low_risk_caption: str = (
        "Lage risicofactor. Activiteiten duurzaam zonder huidige eigenaar."
    )
    accountant_bta_standard_risk: str = (
        "Standaard risicofactor. Specifieke impactdata niet beschikbaar voor dit bedrijfstype."
    )
    accountant_bta_sector_margin: str = "Sectormarge"
    accountant_bta_target_label: str = "Doel"
    accountant_bta_benchmark_caption: str = (
        "Benchmark mediaan EBITDA-marge voor {type}. Afwijkingen triggeren specifieke risicocorrecties in het model."
    )
    accountant_bta_academic_basis_label: str = "Academische Basis"
    accountant_bta_academic_basis_ref: str = (
        "Ref: Trugman (2017), Coulon (2021) • KMO-Waarderingsstandaarden"
    )

    # =========================================================================
    # ACCOUNTANT VIEW PHASE 2: CONDITIONALS
    # =========================================================================
    accountant_cond_data_not_available_title: str = "Data niet beschikbaar"
    accountant_cond_data_not_available_default: str = (
        "De gevraagde data is niet beschikbaar voor deze onderneming. Dit kan komen door onvoldoende historische informatie of beperkingen bij dataverzameling."
    )
    accountant_cond_limited_data_title: str = "Waarschuwing: beperkte data"
    accountant_cond_limited_data_default: str = (
        "Deze analyse is gebaseerd op beperkte historische data. Resultaten dienen met voorzichtigheid te worden geïnterpreteerd."
    )
    accountant_cond_limited_data_impact: str = "Impact op Waardering:"
    accountant_cond_neg_revenue_title: str = "Waarderingsbenadering: Omzetmultiples"
    accountant_cond_neg_revenue_body: str = (
        "De onderneming opereert momenteel met negatieve EBITDA-marges terwijl er wordt geïnvesteerd in groei. Omzetmultiples zijn meer geschikt dan EBITDA-multiples voor ondernemingen in groei-/investeringsfasen. Deze aanpak is consistent met waardering van snelgroeiende ondernemingen (Damodaran, 2017)."
    )
    accountant_cond_neg_high_risk_title: str = "Hoog Risico Waarderingsscenario"
    accountant_cond_neg_high_risk_body: str = (
        "Significante operationele verliezen vereisen substantiële risicocorrecties. Het waarderingsbereik wordt verbreed tot ±40% om onzekerheid te weerspiegelen. Aannames over pad naar winstgevendheid zijn cruciaal voor waarderingsbetrouwbaarheid."
    )
    accountant_cond_neg_not_determinable_title: str = "Beperkte Toepasbaarheid Waardering"
    accountant_cond_neg_not_determinable_body: str = (
        "Aanhoudende verliezen en dalende omzet duiden op continuïteitsonzekerheid. Traditionele waarderingsmethoden veronderstellen winstgevende activiteiten. Vermogensgebaseerde of liquidatiewaarde kan meer geschikt zijn (FASB ASC 205-40). Gebruikers dienen turnaround-analyse te overwegen en specialisten te raadplegen."
    )
    accountant_cond_class_subject_to: str = (
        "Dit rapport is onderhevig aan significante beperkingen vanwege:"
    )
    accountant_cond_class_caution: str = (
        "Gebruikers dienen voorzichtigheid te betrachten en professionele adviseurs te raadplegen alvorens op deze conclusies te vertrouwen."
    )
    accountant_cond_class_special_purpose: str = (
        "Deze waardering is uitsluitend voor speciale doeleinden en is mogelijk niet geschikt voor transactieprijsstelling of financiële verslaglegging."
    )

    # ─────────────────────────────────────────────────────────────────────
    # Yuki-audit follow-up (May 2026): defensibility chips + corrected
    # asking-price strapline. Localised in dutch() / english() below; the
    # field defaults here are NL-leaning (the primary product locale).
    # ─────────────────────────────────────────────────────────────────────
    # Asking-price note variants for the executive-summary hero card.
    # ``_below_basis`` fires when the recommended asking price sits AT or BELOW
    # the central headline value — "Strategische buffer voor onderhandeling"
    # is wrong in that case (a buffer goes ABOVE the value, not below). The
    # ``_suppressed`` variant covers the asking_price_gate.py path where the
    # recommendation collapses to the equity midpoint for limited-scope or
    # methodology-unsupported reports.
    exec_asking_price_note_below_basis: str = "Markt-anker — geen onderhandelingsbuffer"
    exec_asking_price_note_suppressed: str = (
        "Beperkte scope — geen onderhandelingsbuffer toegevoegd"
    )
    # Data-coverage chip on Page 1. The previous "Hoog / Medium / Indicatief"
    # badge was easy to misread as overall confidence; this label binds it
    # explicitly to data inputs (revenue, EBITDA, normalisaties, comparables).
    exec_data_coverage_chip_label: str = "Datadekking"
    exec_engine_confidence_chip_label: str = "Modelvertrouwen"
    # EBITDA volatility chip on Page 1 + cover. Fires when the normalised
    # EBITDA spread (max/min ratio) exceeds 3× across the displayed multi-year
    # window — unless reported EBITDA shows smooth monotonic growth with stable
    # margins. The McKinsey weighting hides spread in a single multiple, but a
    # buyer-side reviewer will rebuild it within the hour. A second variant
    # (``_loss_year``) covers the sign-change case where at least one year
    # has normalised EBITDA ≤ 0 (loss → profit is material volatility a
    # single multiple cannot represent).
    exec_volatility_chip_label: str = "Volatiele EBITDA"
    exec_volatility_chip_note_template: str = (
        "Genormaliseerde EBITDA varieert {min} ({min_year}) – {max} ({max_year}) "
        "over de weergegeven jaren."
    )
    exec_volatility_chip_note_loss_year_template: str = (
        "Eén of meer jaren tonen een verlies-EBITDA ({min} in {min_year} → "
        "{max} in {max_year}); een enkele multiple representeert dit niet."
    )
    exec_volatility_chip_note_normalization_template: str = (
        "Piek/dal op gerapporteerde EBITDA; {max_year} bevat materiële normalisatie."
    )
    # Sensitivity table provenance — names both ranges so the reader does not
    # assume the sensitivity corners ARE the engine confidence interval.
    sensitivity_provenance_note_template: str = (
        "De scenario-tabel toont uiterste combinaties rond de toegepaste multiple "
        "(niet de DB-sectorpercentielen). "
        "Hoofdwaarderingsbandbreedte: {engine_low} — {engine_high}."
    )
    # Cover chip surfacing the count of high-severity engine warnings that
    # would otherwise be routed only to the EngineCoPilot rail. Renders only
    # when count >= 1.
    cover_warning_count_chip_singular: str = "{count} signaal voor review"
    cover_warning_count_chip_plural: str = "{count} signalen voor review"
    # ``impossible_margin`` typed warning — emitted by the business-logic
    # validator when any year (current or historical) has normalized EBITDA
    # margin ≥ 100% of revenue. The catalog wires the localized copy through
    # ``localize_data_quality_warnings``; the engine emits an English-leaning
    # message via build_impossible_margin_warning() which the localizer then
    # swaps for these strings at response-build time.
    warning_impossible_margin_message: str = (
        "Een of meer jaren tonen een genormaliseerde EBITDA-marge ≥ 100%; "
        "dit is wiskundig onmogelijk voor een operationele entiteit."
    )
    warning_impossible_margin_recommendation: str = (
        "Controleer de EBITDA-mapping voor het betreffende jaar. Typische "
        "oorzaken: te agressieve normalisatie, niet-omzetinkomsten (huur, "
        "intercompany) of een operationele entiteit met vastgoed binnen "
        "dezelfde NV — overweeg een Vastgoed carve-out."
    )

    warning_indicative_dcf_message: str = (
        "Indicatieve DCF op basis van aangeleverde of gemodelleerde kasstroomaannames. "
        "De bedrijfsprognose is niet aan bronbewijs getoetst."
    )
    warning_indicative_dcf_recommendation: str = (
        "Controleer kasstromen, belastingen, herinvesteringen en terminale aannames "
        "aan de hand van bedrijfsdocumentatie voordat u op deze raming vertrouwt."
    )
