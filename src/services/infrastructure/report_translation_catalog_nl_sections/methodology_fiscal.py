"""Dutch method, ledger, and fiscal/synthesis copy."""

from __future__ import annotations


def build_dutch_methodology_fiscal_translations() -> dict[str, object]:
    return {
        # DCF Valuation Page
        "dcf_page_title": "DCF-analyse (Discounted Cash Flow)",
        "dcf_page_subtitle": (
            "Inkomsten-benadering: vrije kasstromen voor de onderneming (FCFF) "
            "worden geprojecteerd over de expliciete periode en samen met een "
            "terminale waarde teruggebracht naar contante waarde tegen WACC. "
            "De opbouw van iedere component vindt u hieronder."
        ),
        "dcf_projection_table_title": "Vrije Kasstroomprojectie",
        "dcf_wacc_buildup_title": "WACC-opbouw",
        "dcf_wacc_buildup_fallback_title": "WACC handmatig ingegeven",
        "dcf_wacc_buildup_fallback_body": (
            "Er is geen CAPM-opbouw beschikbaar omdat de WACC rechtstreeks is ingevoerd. "
            "Voer voor een toetsbare opbouw de risicovrije rente, β, equity risk premium "
            "en kosten van vreemd vermogen in via het WACC-paneel. Een onderbouwde "
            "opbouw versterkt de defensibility en peer-vergelijking."
        ),
        "dcf_wacc_buildup_fallback_applied_label": "Toegepaste WACC",
        "dcf_wacc_buildup_override_note": (
            "De toegepaste WACC volgt adviseur- of sector-mediaaninvoer; de CAPM-opbouw "
            "hieronder dient als onderbouwing en kruistoets wanneer die afwijkt."
        ),
        "dcf_wacc_capm_buildup_label": "CAPM-opbouw",
        "dcf_wacc_applied_in_wacc_label": "Toegepast in WACC",
        "dcf_wacc_rounded_label": "afgerond",
        "dcf_row_revenue": "Omzet",
        "dcf_row_growth": "Groei",
        "dcf_row_ebitda": "EBITDA",
        "dcf_row_ebitda_margin": "EBITDA-marge",
        "dcf_row_ebit": "EBIT",
        "dcf_row_taxes": "Belastingen",
        "dcf_row_nopat": "NOPAT",
        "dcf_row_da_addback": "Afschrijvingen (terugtel)",
        "dcf_row_capex": "CapEx",
        "dcf_row_nwc": "ΔNWC",
        "dcf_row_fcff": "FCFF",
        "dcf_row_discount_factor": "Discontofactor",
        "dcf_row_pv_fcff": "CW(FCFF)",
        "dcf_terminal_value_header": "Terminale waarde",
        "dcf_ev_summary_header": "Ondernemingswaarde (DCF)",
        "dcf_pv_explicit_label": "CW expliciete periode",
        "dcf_pv_terminal_label": "CW terminale waarde",
        "dcf_enterprise_value_label": "Ondernemingswaarde",
        "dcf_sensitivity_matrix_title": "Gevoeligheidsmatrix (WACC × Terminale groei)",
        "dcf_assumptions_note": (
            "Bronnen — Omzet en EBITDA: management-input afgestemd op beschikbare "
            "genormaliseerde historie. CapEx, afschrijvingen en ΔNWC: boekhoudimport "
            "waar beschikbaar, anders sectorbenchmarks. WACC: toegepaste adviseurs-/sectorinvoer "
            "waar aanwezig, met CAPM-opbouw als onderbouwing/kruistoets (Damodaran 2026 EU SMB-cohort, "
            "risicovrije rente OLO 10y). Terminale waarde: Gordon Growth tenzij anders "
            "vermeld; eeuwigdurende groei begrensd onder langetermijn nominale GDP. "
            "Discontomethodiek: middenjaar standaard, jaareinde bij vermelding."
        ),
        "dcf_wacc_formula_label": "WACC-formule",
        "dcf_cost_of_equity_label": "Kosten eigen vermogen",
        "dcf_cost_of_debt_label": "Kosten vreemd vermogen",
        "dcf_equity_weight_label": "Eigen vermogen gewicht",
        "dcf_debt_weight_label": "Vreemd vermogen gewicht",
        "dcf_tax_rate_label": "Belastingtarief",
        "dcf_risk_free_rate_label": "Risicovrije rente",
        "dcf_beta_label": "Bèta",
        "dcf_erp_label": "Aandelenrisicopremie",
        "dcf_size_premium_label": "Omvangspremie",
        "dcf_csr_label": "Bedrijfsspecifiek risico",
        "calib_multiple_waterfall_title": "Multiple-kalibratie",
        "calib_multiple_waterfall_intro": "Hoe de benchmark-multiple stap voor stap wordt gekalibreerd naar de toegepaste multiple.",
        "calib_value_waterfall_title": "Waarde-opbouw",
        "calib_value_waterfall_intro": "Van genormaliseerde prestatie naar ondernemingswaarde en finale aandelenwaarde. Kas, rentedragende schuld, werkkapitaal en overige balanscorrecties worden alleen toegepast wanneer balansinputs beschikbaar zijn. Ontbrekende kasmiddelen en schuld blijven ongeverifieerd.",
        "calib_value_waterfall_intro_ev_focus": "Van ondernemingswaarde naar finale aandelenwaarde. Kas, rentedragende schuld, werkkapitaal en overige balanscorrecties worden alleen toegepast wanneer balansinputs beschikbaar zijn. Ontbrekende kasmiddelen en schuld blijven ongeverifieerd.",
        "calib_value_waterfall_intro_balance_provided": "Van ondernemingswaarde naar finale aandelenwaarde. Kas, rentedragende schuld, werkkapitaal en overige balanscorrecties zijn aangesloten op de aangeleverde balansinputs.",
        "saas_appendix_title": "SaaS-analyse",
        "saas_appendix_intro": "Dit onderdeel toont het ARR-anker en de belangrijkste SaaS-kwaliteitsindicatoren die de waarderingsmultiple ondersteunen.",
        "saas_appendix_metrics_title": "SaaS-kernmetrics",
        "saas_appendix_adjustments_title": "ARR-multiple aanpassingen",
        "saas_appendix_no_adjustments": "Geen afzonderlijke ARR-multiple aanpassingen beschikbaar voor deze waardering.",
        "saas_appendix_factor_label": "Factor",
        "saas_appendix_impact_label": "Impact",
        "saas_appendix_note_label": "Toelichting",
        "saas_appendix_arr_growth_label": "ARR-groei (jaarlijks %)",
        "saas_appendix_gross_margin_label": "Brutomarge (%)",
        "saas_appendix_customer_concentration_label": "Klantconcentratie (%)",
        "saas_appendix_cac_payback_label": "CAC payback (mnd)",
        "saas_appendix_customer_churn_label": "Klantchurn (%)",
        "saas_appendix_nrr_expansion_spread_label": "Netto-expansiespread",
        "saas_appendix_arr_label": "ARR",
        "saas_appendix_ltv_cac_label": "LTV / CAC",
        "saas_appendix_magic_number_label": "Magic Number",
        "saas_quality_score_label": "SaaS-kwaliteitsscore",
        "saas_quality_score_caption": (
            "Samengestelde score van Rule of 40, NRR, LTV/CAC, "
            "bruto omzet-churn en brutomarge — elk gewogen 20%."
        ),
        "saas_appendix_ebitda_crosscheck_label": "EBITDA-kruistoets",
        "saas_quality_strong": "Sterk",
        "saas_quality_healthy": "Gezond",
        "saas_quality_developing": "In ontwikkeling",
        "saas_quality_at_risk": "Risico",
        "saas_waterfall_title": "Opbouw EV/ARR-multiple",
        "saas_waterfall_base": "Basismultiple",
        "saas_waterfall_final": "Eindmultiple",
        "saas_waterfall_benchmark_note": "Publieke SaaS-benchmark (VS)",
        "saas_waterfall_clamp_note": "Begrensd op [2,5×, 12,0×]",
        "saas_arr_bridge_title": "ARR-basis",
        "saas_arr_bridge_source": "Bron",
        "saas_expansion_revenue_label": "Expansieomzet (%)",
        # SaaS cap-table & dilution page
        "saas_cap_table_title": "Cap-tabel & verwatering",
        "saas_cap_table_simulator_heading": "Cap-table-simulator",
        "saas_cap_table_headline_sentence": (
            "Bij een ronde van <strong>{investment}</strong> tegen een pre-money "
            "(equity) van <strong>{pre_money}</strong> verwater je "
            "<strong>{dilution_pct}</strong> van je aandelen."
        ),
        "saas_cap_table_pre_money_label": "Pre-money (equity, na schuldenbrug)",
        "saas_cap_table_round_label": "+ Op te halen ronde",
        "saas_cap_table_post_money_label": "= Post-money waardering",
        "saas_cap_table_investor_dilution_label": "Verwatering nieuwe investeerder",
        "saas_cap_table_safe_dilution_label": "Verwatering door SAFE-conversie",
        "saas_cap_table_option_pool_label": "Optiepool",
        "saas_cap_table_founder_dilution_label": "Totale verwatering oprichters",
        "saas_cap_table_safe_overview_heading": "SAFE-overzicht",
        "saas_cap_table_safe_principal_label": "Openstaande SAFE-principal (totaal)",
        "saas_cap_table_safe_drag_label": "SAFE-conversiedrag op post-money",
        "saas_cap_table_safe_assumption_note": (
            "Conversie-aanname: SAFEs converteren bij de volgende prijsronde tegen de "
            "meest gunstige clausule (cap of discount)."
        ),
        "saas_cap_table_unavailable_note": (
            "Cap-tabel niet beschikbaar — vul een op te halen ronde en (optioneel) je "
            "kapitaalgeschiedenis in om dit overzicht te genereren."
        ),
        # Adjusted NAV (Gecorrigeerde NAV) dedicated page
        "nav_page_title": "Gecorrigeerde Netto Actiefwaarde (NAV)",
        "nav_page_subtitle": "Waardering op basis van de actuele intrinsieke waarde van activa en passiva, na herwaardering van vaste activa, aftrek van belastinglatenties en off-balance correcties.",
        "nav_page_badge": "Asset-anker",
        "nav_methodology_intro": (
            "De Gecorrigeerde NAV vertrekt van het boekhoudkundig eigen vermogen en herwaardeert "
            "individuele activa naar marktwaarde (m.n. terreinen, gebouwen en deelnemingen). "
            "Aftrek van latente belastingen op meerwaarden en eventuele off-balance verplichtingen "
            "geeft de intrinsieke aandelenwaarde — de relevante referentie voor holdings, "
            "vastgoedvennootschappen en activazware ondernemingen waar de going-concern multiples "
            "geen recht doen aan de onderliggende substantiewaarde."
        ),
        "nav_intrinsic_summary_header": "Intrinsieke aandelenwaarde — samenvatting",
        "nav_intrinsic_book_equity_label": "Boekhoudkundig eigen vermogen",
        "nav_intrinsic_revaluation_uplift_label": "Herwaarderingseffect (netto correcties − latenties)",
        "nav_intrinsic_value_label": "Intrinsieke waarde (Gecorrigeerde NAV)",
        "nav_intrinsic_uplift_pct_label": "Herwaardering t.o.v. boekwaarde",
        "nav_intrinsic_ownership_label": "Eigendomspercentage",
        "nav_assumptions_note": (
            "Bron: jaarrekening (codes 22x terreinen & gebouwen, 23-26x materieel, 28x financiële vaste activa, "
            "168 uitgestelde belastingen, 15x kapitaalsubsidies). Herwaarderingen op vastgoed worden bij voorkeur "
            "gestaafd met een externe schatting; bij gebrek hieraan past het model een sector-/regio-specifieke "
            "correctie toe en markeert de regel voor review in de calibratieledger."
        ),
        "nav_label_real_estate": "Vastgoed (herwaardering)",
        "nav_label_hidden_reserves": "Stille reserves",
        "nav_label_inventory": "Voorraad (correctie)",
        "nav_label_receivables": "Vorderingen (correctie)",
        "nav_label_goodwill_writeoff": "Goodwill afschrijving",
        "nav_label_other_revaluations": "Overige herwaarderingen",
        "nav_label_real_estate_appraisal": "Vastgoed (taxatieswap)",
        "nav_label_equipment_revaluation": "Materieel (economische levensduur)",
        "nav_label_off_balance": "Off-balance verplichtingen",
        "nav_net_liability_summary_header": "Netto verplichting — samenvatting",
        "nav_net_liability_callout": (
            "De gecorrigeerde NAV is negatief: na herwaardering en latenties overtreffen de "
            "verplichtingen de activa. Deze positie is een ondergrens-signaal voor koper-onderhandeling "
            "en wettelijke melding (Art. 633 W.Venn. — alarmbelprocedure)."
        ),
        # Audit-trail (round-4)
        "nav_audit_trail_title": "Audit trail — herwaardering & latenties",
        "nav_audit_trail_subtitle": (
            "Verdedigbaar dossier voor de koper: herwaardering per actief, latente belasting per "
            "actiefklasse en de toepasselijke vennootschapsbelasting (Art. 215 WIB 92)."
        ),
        "nav_audit_trail_re_card_title": "Vastgoed — boek → taxatie",
        "nav_audit_trail_re_book": "Boekwaarde",
        "nav_audit_trail_re_appraisal": "Taxatiewaarde",
        "nav_audit_trail_re_meerwaarde": "Meerwaarde",
        "nav_audit_trail_eq_card_title": "Materieel — economische levensduur",
        "nav_audit_trail_eq_subtitle_user": "Gebruiker-aangeleverde economische boekwaarde.",
        "nav_audit_trail_eq_subtitle_straight_line": "Lineaire economische afschrijving",
        "nav_audit_trail_eq_age_label": "leeftijd",
        "nav_audit_trail_eq_life_label": "levensduur",
        "nav_audit_trail_eq_original_cost": "Aanschaffingswaarde",
        "nav_audit_trail_eq_tax_book": "Fiscale boekwaarde",
        "nav_audit_trail_eq_economic_book": "Economische boekwaarde",
        "nav_audit_trail_eq_meerwaarde": "Meerwaarde",
        "nav_audit_trail_dtb_title": "Latente belasting per actiefklasse",
        "nav_audit_trail_dtb_asset_class": "Actiefklasse",
        "nav_audit_trail_dtb_meerwaarde": "Meerwaarde",
        "nav_audit_trail_dtb_rate": "Tarief",
        "nav_audit_trail_dtb_deferred_tax": "Latente belasting",
        "nav_audit_trail_dtb_source": "Bron",
        "nav_audit_trail_dtb_total": "Totaal latente belastingen",
        "nav_audit_trail_dtb_effective_label": "effectief",
        "nav_audit_trail_sme_title": "KMO-tarief (Art. 215 WIB 92)",
        "nav_audit_trail_sme_eligible": "KMO",
        "nav_audit_trail_sme_standard": "standaard",
        "nav_rate_source_user_override": "Gebruiker-override",
        "nav_rate_source_global_user_rate": "Globaal gebruikerstarief",
        "nav_rate_source_engine_default_per_asset": "Standaard per actiefklasse",
        "nav_rate_source_engine_default_global": "Resolutie van vennootschapsbelasting",
        "nav_asset_class_real_estate": "Onroerend goed (vastgoed)",
        "nav_asset_class_inventory": "Voorraad",
        "nav_asset_class_receivables": "Vorderingen",
        "nav_asset_class_hidden_reserves": "Stille reserves",
        "nav_asset_class_other_revaluations": "Overige herwaarderingen",
        # Deal-structure (Aandelen vs. Handelsfonds)
        "nav_deal_structure_title": "Deal-structuur — Aandelen vs. Handelsfonds",
        "nav_deal_structure_subtitle": (
            "Vergelijking van een aandelen- vs. asset-deal, inclusief tax shield op "
            "goodwillafschrijving (Art. 61 WIB 92) en meerwaardebelasting voor de privé-aandeelhouder "
            "(Art. 90 WIB 92; tarief en toepassingsvoorwaarden te bevestigen met fiscaal adviseur)."
        ),
        "nav_deal_headline_price": "Headline-prijs",
        "nav_deal_seller_tax": "Belasting verkoper",
        "nav_deal_seller_net_proceeds": "Netto-opbrengst verkoper",
        "nav_deal_buyer_tax_shield": "Tax shield koper (NPV)",
        "nav_deal_buyer_net_cost": "Netto kost koper",
        "nav_deal_indifference_premium": "Indifferentie-premie",
        "nav_deal_indifference_caption": (
            "Bedrag waarmee de asset-prijs hoger moet liggen dan de aandelen-prijs voor de koper "
            "om indifferent te zijn (gegeven de tax shield)."
        ),
        # EBITDA-Multiple dedicated page
        "ebitda_multiple_methodology_intro": (
            "De EV/EBITDA-multiple wordt verankerd op een peer-set van vergelijkbare Belgische SME-transacties "
            "(sector, omzet-band, regio). Het basisscenario wordt vervolgens gekalibreerd voor onderneming-specifieke "
            "risico's (key-person, klant-concentratie, schaal, liquiditeit) — elke stap is traceerbaar in de "
            "calibratie-ledger hieronder."
        ),
        "ebitda_multiple_assumptions_note": (
            "Bron multiple: peer-set van vergelijkbare Belgische SME-transacties (sector, omzet-band, regio); "
            "jaarlijkse refresh. Gekalibreerde stappen volgen de Damodaran-structuur (size discount, "
            "control / liquidity premia). EBITDA wordt genormaliseerd via het bridge — eigenaar-vergoeding, "
            "niet-recurrente posten en eenmalige meerwaarden worden expliciet gerapporteerd in de "
            "EBITDA-normalisatiepagina."
        ),
        "ebitda_multiple_cross_check_title": "Impliciete kruiscontroles",
        "ebitda_multiple_cross_check_intro": (
            "De toegepaste EV/EBITDA-multiple impliceert ook andere multiples. "
            "Kruiscontroles helpen het cijfer in absolute economie te plaatsen."
        ),
        "ebitda_multiple_implied_ev_sales_label": "Impliciete EV/Omzet",
        "ebitda_multiple_implied_pe_label": "Impliciete koers/winst (na belasting)",
        "ebitda_multiple_dloc_dlom_title": "Controlebasis & verhandelbaarheidsdisclaimer",
        "ebitda_multiple_dloc_dlom_body": (
            "Gerapporteerd op een 100% control, marketable basis. Minderheidskorting (DLOC) "
            "en illiquiditeitskorting (DLOM) zijn niet toegepast — een formele waardering van "
            "een minderheidsbelang vereist aanvullende analyses. Typische M&A-bandbreedtes ter "
            "referentie: DLOC 10–25%, DLOM 15–35% (Mercer Capital 2017; Pratt &amp; Niculita "
            "2008, Hoofdstuk 13). Onder deze typische haircuts zou een 100%-aandelenwaarde van "
            "€X overgaan in een minderheidsbelang van circa €X × (1 − DLOC) × (1 − DLOM)."
        ),
        "ebitda_multiple_provenance_label": "Peer-set herkomst",
        "ebitda_multiple_provenance_n": "N = {count} transacties",
        "ebitda_multiple_provenance_window": "Vensterbreedte: {months} maanden",
        "ebitda_multiple_provenance_refresh": "Laatste refresh: {date}",
        "comparables_table_title": "Vergelijkbare transacties",
        "comparables_table_subtitle": (
            "De multiples van de M&A-comparables waarop de peer-set is verankerd. "
            "Identificatie geanonimiseerd waar dat door NDA is vereist."
        ),
        "comparables_table_col_name": "Onderneming",
        "comparables_table_col_ev_ebitda": "EV/EBITDA",
        "comparables_table_col_ev_revenue": "EV/Omzet",
        "comparables_table_col_pe": "K/W",
        "comparables_table_empty": "Geen comparables in dit dossier.",
        "driver_tornado_title": "Multiple-impact per stap (€)",
        "driver_tornado_subtitle": (
            "De modelaanpassingen gerangschikt op €-impact ten opzichte van de basis-multiple. "
            "De grootste balken bepalen het meest de uiteindelijke ondernemingswaarde."
        ),
        "driver_tornado_axis_label": "€-impact op EV",
        "driver_tornado_basis_label": "basis",
        "ebitda_multiple_calibration_xref": (
            "De volledige stap-voor-stap calibratie-ledger (P25/P75 → kortingen → toegepaste "
            "multiple) staat op de volgende pagina — Calibratie. Daar staan ook de academische "
            "voetnoten (Damodaran, Pratt) per stap."
        ),
        # SDE dedicated page
        "sde_dedicated_page_title": "SDE-waardering",
        "sde_methodology_intro": (
            "SDE (Seller's Discretionary Earnings) is de standaardlens voor eigenaar-geleide ondernemingen waarin "
            "de eigenaar voltijds meedraait. We vertrekken van het meest betrouwbare anker — Nettowinst (volledige "
            "reconciliatie) of Genormaliseerde EBITDA (wanneer intresten / belastingen / afschrijvingen reeds "
            "verwerkt zijn) — en tellen de eigenaar-vergoeding op. De resulterende SDE wordt vermenigvuldigd met "
            "een kopersvergelijkbare multiple uit een gekalibreerde transactiebasis (BizBuySell / EBA voor BE / EU). "
            "Dit is de meest gebruikte lens voor MKB-overdrachten onder €1M."
        ),
        "sde_business_size_label": "Groottecategorie & kopersvergelijkbare band",
        "sde_business_size_intro": (
            "De P25–P75 band is gefit op vergelijkbare transacties binnen dezelfde groottecategorie. "
            "Verder van het mediaan = grotere onzekerheid op de toepasbare multiple."
        ),
        "sde_assumptions_note": (
            "Bron multiple: kopersvergelijkbare transactiedatabank (BizBuySell US, EBA voor BE/EU), gegroepeerd per "
            "omzet-band en sector. Eigenaar-vergoeding wordt genormaliseerd op marktconforme manager-loon. "
            "SDE wordt gerapporteerd voor één voltijds werkende eigenaar; bij meerdere actieve eigenaars hoort "
            "de tweede en volgende als personeelskost geherklasseerd te worden vóór de bridge."
        ),
        "sde_summary_title": "SDE × multiple — samenvatting",
        "sde_summary_row_sde": "SDE (Seller's Discretionary Earnings / discretionaire verkoperswinst)",
        "sde_summary_row_multiple": "SDE-multiple",
        "sde_enterprise_value_label": "Ondernemingswaarde (SDE)",
        "sde_p25_p75_band_label": "Kopersvergelijkbare bandbreedte (P25–P75)",
        "sde_size_band_label": "Grootte-categorie",
        "sde_buyer_pool_label": "kopersgroep",
        "method_label_adjusted_nav": "Gecorrigeerde NAV",
        "method_label_ebitda_multiple": "EV/EBITDA",
        "method_label_sde": "SDE",
        "method_label_revenue_multiple": "EV/Omzet",
        "method_label_dcf": "DCF",
        # SDE bridge ladder
        "sde_bridge_title": "Brug — Gerapporteerde winst → SDE",
        "sde_bridge_net_income": "Nettowinst (boekjaar)",
        "sde_bridge_interest": "Intresten op schulden",
        "sde_bridge_taxes": "Belastingen op het resultaat",
        "sde_bridge_depreciation": "Afschrijvingen & waardeverminderingen",
        "sde_bridge_owner_comp": "Eigenaar-vergoeding (genormaliseerd)",
        "sde_bridge_other": "Overige niet-recurrente posten",
        "sde_bridge_total": "SDE (Seller's Discretionary Earnings / discretionaire verkoperswinst)",
        "sde_bridge_footnote": (
            "SDE wordt gerapporteerd voor één voltijds werkende eigenaar; bij meerdere actieve eigenaars hoort "
            "de tweede en volgende geherklasseerd te worden als personeelskost (manuele aanpassing)."
        ),
        "sde_see_normalization_link": "Zie de EBITDA-normalisatiepagina ↗",
        # Revenue-Multiple dedicated page
        "revenue_multiple_methodology_intro": (
            "De EV/Omzet-multiple is de juiste lens wanneer EBITDA niet representatief is voor het verdienmodel: "
            "hooggroei pre-profit, negatieve-EBITDA-herstel, asset-light operators, of vroege seizoens-/projectfases. "
            "Het basisscenario wordt gefit op een peer-set van vergelijkbare omzet-bands en groei-profielen; "
            "sterke groei rechtvaardigt een hogere multiple, lage groei drukt de band naar beneden "
            "(PEG-correctie hieronder)."
        ),
        "revenue_multiple_summary_title": "EV / Sales — samenvatting",
        "revenue_multiple_operating_revenue_label": "Bedrijfsopbrengsten (operating revenue)",
        "revenue_multiple_revenue_label": "Omzet",
        "revenue_multiple_multiple_label": "EV/Omzet-multiple",
        "revenue_multiple_range_label": "Bandbreedte",
        "revenue_multiple_metric_label": "Omzet",
        "revenue_multiple_axis_label": "EV/Omzet",
        "revenue_multiple_growth_band_label": "Groei-gecorrigeerde band (PEG-stijl)",
        "revenue_multiple_growth_band_intro": (
            "Impliciete PEG = toegepaste EV/Omzet-multiple ÷ omzet-CAGR over 3 jaar. Richtlijn: <0,5 = laag "
            "geprijsd, 0,5–1,5 = evenwichtig, >1,5 = uitgerekt."
        ),
        "revenue_multiple_growth_cagr_label": "Omzet-CAGR over 3 jaar",
        "revenue_multiple_implied_peg_label": "Impliciete PEG",
        "revenue_multiple_growth_band_stretched": "Multiple uitgerekt t.o.v. groei — overweeg DCF cross-check.",
        "revenue_multiple_assumptions_note": (
            "De omzetmethode gebruikt de resultaatdefinitie en prijsbepalende invoer uit de opgeslagen berekening. "
            "Marktbewijs wordt, indien beschikbaar, afzonderlijk met bron en datum vermeld. "
            "Ontbrekend bewijs onderbouwt geen verzameling vergelijkbare transacties. "
            "Dit methoderesultaat draagt alleen bij aan de conclusie indien toegelaten in de opgeslagen synthese."
        ),
        # Generic multiple sensitivity matrix
        "multiple_sensitivity_matrix_title": "Gevoeligheidsanalyse",
        "multiple_sensitivity_caption": (
            "Ondernemingswaarde (€) bij variatie van de basis-metriek (rijen) en de toegepaste multiple (kolommen). "
            "Het gemarkeerde middelpunt is het basisscenario."
        ),
        # Calibration per-method navigator
        "calib_per_method_nav_label": "Per-methode dossiers in dit rapport",
        "calib_per_method_nav_caption": "hieronder de geconsolideerde calibratie-ledger.",
        "calib_waterfall_xref_label": "Multiple-buildup",
        "calib_waterfall_xref_caption": "zie het toegewijde dossier hierboven voor de per-methode-opbouw van de multiple en alle calibratiestappen.",
        "exec_nav_bridge_xref_label": "Gecorrigeerde NAV",
        "exec_nav_bridge_xref_caption": "zie het toegewijde NAV-dossier verderop in dit rapport voor de volledige boekwaarde-naar-intrinsieke-waarde brug, latenties en off-balance correcties.",
        # Fallback Messages
        "adj_no_adjustments": "Geen aanpassingen ingevoerd in deze normalisatiebrug.",
        "exec_no_benchmarks": "Sector benchmarks niet beschikbaar voor dit bedrijfstype.",
        "exec_reference_without_benchmark_table": "Gedetailleerde benchmarkonderbouwing is niet als aparte sectortabel meegeleverd; de gebruikte referentiemultiple is verwerkt in de multiple-kalibratie hierboven.",
        "ebitda_single_year_note": "Waardering gebaseerd op enkeljarige EBITDA. Meerjarige data verhoogt de betrouwbaarheid.",
        "ebitda_no_multi_year": "Onvoldoende historische data voor meerjarige analyse.",
        "warning_zero_ebitda": "Genormaliseerde EBITDA is nul of negatief. Waardering vereist handmatige beoordeling door een adviseur.",
        "warning_missing_revenue": "Omzet niet beschikbaar. Sommige marktbenchmarks kunnen niet worden toegepast.",
        # Calibration Ledger Component
        "ledger_step_column": "Stap",
        "ledger_multiple_column": "Multiple",
        "ledger_impact_column": "Impact",
        "ledger_ev_column": "EV",
        "ledger_ref_column": "Ref",
        "ledger_market_consensus": "Markt Consensus (P50 Mediaan)",
        "ledger_market_consensus_desc": "Baseline uit vergelijkbare transacties",
        "ledger_key_person_risk": "Sleutelpersoon Risico",
        "ledger_micro_sme_discount": "Micro-KMO Korting",
        "ledger_tier_label": "Niveau",
        "ledger_dlom": "Illiquiditeitskorting (DLOM)",
        "ledger_dlom_desc": "Privé-ondernemingen verkopen trager",
        "ledger_conclusion": "Conclusie",
        "ledger_enterprise_value": "Ondernemingswaarde (EV)",
        "ledger_multiple_label": "Multiple",
        "ledger_ev_short": "EV",
        # Panel MAJOR (D1/D2): the substance/property value is NOT an enterprise
        # value — relabel the calibration-box + waterfall start node so an
        # asset/yield dossier never prints a bare "EV" on a NAV/income figure.
        "ledger_substance_short": "Substantiewaarde (bruto / NAV)",
        "ledger_property_value_short": "Vastgoed-marktwaarde (inkomen)",
        "ledger_net_cash_short": "Netto kas",
        "ledger_net_debt_short": "Netto schuld",
        "ledger_equity_short": "Eigen vermogen",
        "ledger_equity_adjusted_parenthetical": "Gecorrigeerde NAV",
        "ledger_value_label": "Waarde",
        "ledger_no_steps": "Volledige kalibratiestappen niet beschikbaar — raadpleeg uw adviseur voor een gedetailleerde multiple-afleiding.",
        "ledger_risk_low": "gediversifieerd klantenbestand, gedelegeerde operaties",
        "ledger_risk_medium": "enige eigenaarafhankelijkheid, gedeeltelijke delegatie",
        "ledger_risk_high": "eigenaar-centrisch, belangrijke relaties in gevaar",
        "ledger_risk_label_low": "LAAG",
        "ledger_risk_label_medium": "GEMIDDELD",
        "ledger_risk_label_high": "HOOG",
        "ledger_tier_micro": "Micro-KMO",
        "ledger_tier_small": "Klein",
        "ledger_tier_medium": "Middelgroot",
        "ledger_dw_base_multiple_step3": "Basismultiple (stap 3)",
        "ledger_dw_initial_multiple_desc_ebitda": (
            "Initiële EV/EBITDA-multiple uit sectorbenchmarks en vergelijkbare transacties."
        ),
        "ledger_dw_initial_multiple_desc_revenue": (
            "Initiële EV/omzet-multiple uit sectorbenchmarks en vergelijkbare transacties."
        ),
        "ledger_dw_initial_multiple_desc_sde": (
            "Initiële SDE-multiple uit sectorbenchmarks en vergelijkbare transacties."
        ),
        "ledger_dw_size_discount": "Omvangskorting",
        "ledger_dw_liquidity_discount": "Illiquiditeitskorting",
        "ledger_dw_revenue_trend": "Omzetrendement",
        "ledger_dw_revenue_trend_desc": (
            "Correctie gekoppeld aan de omzetontwikkeling tussen boekjaren."
        ),
        "ledger_dw_revenue_trend_adjust_template": (
            "Omzetrendementscorrectie: {pct}% toegepast op de multiple."
        ),
        "ledger_dw_size_discount_segment_template": "Omvangskorting — segment {tier}{suffix}.",
        "ledger_dw_size_discount_halved_suffix_template": (
            " (gehalveerd met {reduction}% — eigenaarsconcentratie vangt al een deel "
            "van het omvangrisico op)"
        ),
        "ledger_dw_liquidity_discount_private_desc": (
            "Illiquiditeitskorting (DLOM) voor niet-beursgenoteerde ondernemingen, "
            "in lijn met restricted-stock studies."
        ),
        "ledger_dw_owner_concentration": "Eigenaarsconcentratie",
        "ledger_dw_owner_concentration_note": (
            "Correctie voor eigenaarsconcentratie en sleutelpersoonrisico — "
            "zie het eigenaarprofiel voor detail."
        ),
        "ledger_dw_size_discount_note_zero": (
            "Geen bijkomende omvangskorting in deze stap (gedeeltelijk verwerkt in de KMO-kalibratie)."
        ),
        "ledger_dw_liquidity_discount_note_zero": (
            "Geen bijkomende illiquiditeitskorting in deze stap (gedeeltelijk verwerkt in eerdere stappen)."
        ),
        "adaptive_ev_band_card_title": "Ondernemingswaarde (EV) — puntschatting",
        "adaptive_ev_band_card_subtitle": (
            "De middelste rij is de belangrijkste puntschatting. Zonder materiële nettoschuldcorrectie komt dit "
            "in dit dossier typisch overeen met de waarde voor aandeelhouders."
        ),
        # Fiscal Reference Page
        "fiscal_title": "Fiscale Referentiewaarde",
        "fiscal_subtitle": "Werknota Belgische meerwaardebelasting",
        "fiscal_scope_disclaimer": "Informatieve rekenreferentie voor Belgische fiscale contexten; geen fiscaal, juridisch of boekhoudkundig advies en geen vervanging van een onafhankelijk waarderingsverslag.",
        "fiscal_calc_title": "Berekening forfaitaire waarde",
        "fiscal_normalized_ebitda_label": "Gebruikte EBITDA",
        "fiscal_forfaitaire_multiple_label": "Forfaitaire multiple",
        "fiscal_ebitda_component_label": "EBITDA-component ({n}× EBITDA)",
        "fiscal_book_equity_label": "Eigen vermogen (boekhoudkundig)",
        "fiscal_not_provided": "Niet opgegeven",
        "fiscal_reference_value_label": "Forfaitaire waarde",
        "fiscal_excl_equity": "(excl. eigen vermogen)",
        "fiscal_ma_market_value": "M&A Marktwaarde",
        "fiscal_indicative_share_value": "Indicatieve aandelenwaarde",
        "fiscal_reference_value_short": "Fiscale Referentiewaarde",
        "fiscal_equity_plus_multiple": "Eigen Vermogen + {n}× EBITDA",
        "fiscal_legal_basis_title": "Fiscaal referentiekader",
        "fiscal_legal_intro": "Voor de historische waarde op 31/12/2025 voorziet de Belgische wet deze routes:",
        "fiscal_legal_item_1": "Eigen vermogen + 4 × EBITDA van het laatst afgesloten boekjaar (wettelijke forfaitaire formule)",
        "fiscal_legal_item_2": "Waarde volgens een bestaande waarderingsformule in een geldend contract of aandeelhoudersovereenkomst",
        "fiscal_legal_item_3": "Waarde gebaseerd op een objectieve markttransactie met onafhankelijke derden in 2025",
        "fiscal_legal_item_4": "Waarde in een verslag dat uiterlijk 31/12/2027 is opgesteld door een gecertificeerd accountant of bedrijfsrevisor die niet de gebruikelijke adviseur van de vennootschap is",
        "fiscal_legal_paragraph": "Bij interne meerwaarden (overdracht aan een vennootschap waarin de overdrager of naaste familieleden controle uitoefenen) kan een afzonderlijk tarief van 33% gelden. Controleer de toepassingsvoorwaarden, inclusief eventuele anti-misbruikregels rond financiering en EBITDA-limieten, met een fiscaal adviseur.",
        "fiscal_legal_footer": "Dit is een rekennota, geen juridische of fiscale conclusie. De formule gebruikt de statutaire EBITDA van het laatste boekjaar dat voor 1 januari 2026 is afgesloten. Het is geen marktwaardering. Laat de definitieve fiscale behandeling bevestigen door een bevoegde professional.",
        "fiscal_warning_equity_missing": "Het eigen vermogen (boekhoudkundig) is niet opgegeven in deze berekening. De volledige forfaitaire waarde volgens de wettelijke formule is: Eigen Vermogen + 4 × EBITDA. Raadpleeg uw adviseur of de jaarrekening voor het boekhoudkundig eigen vermogen.",
        "fiscal_warning_equity_negative": "Het boekhoudkundig eigen vermogen is negatief ({amount}). Het resultaat is lager dan het EBITDA-component alleen. Vraag een bevoegde professional of de formule geschikt is voor dit bedrijf.",
        "fiscal_warning_prefix": "Let op:",
        "fiscal_peildatum_label": "Peildatum",
        "fiscal_ebitda_source_label_caption": "EBITDA-bron",
        "fiscal_reported_ebitda_label": "Statutaire EBITDA (laatst afgesloten boekjaar)",
        "fiscal_ebitda_used_label": "Toegepaste EBITDA (laatst afgesloten boekjaar)",
        "fiscal_statutory_ebitda_caution_title": "Controlepunt EBITDA-basis",
        "fiscal_statutory_ebitda_caution_body": "Gebruik hier de statutaire/fiscale EBITDA uit het laatst afgesloten boekjaar. Als dit cijfer uit genormaliseerde of manuele input komt, moet het met de jaarrekening worden afgestemd voordat de fiscale referentiewaarde wordt gedeeld.",
        "fiscal_reported_ebitda_compare_label": "Statutaire EBITDA (jaarrekening)",
        "fiscal_ebitda_basis_advisor_chip_statutair": "Statutaire EBITDA-basis",
        "fiscal_ebitda_basis_advisor_chip_genormaliseerd": "Toegepaste EBITDA-basis — afstemmen met jaarrekening",
        "fiscal_reference_value_incomplete_label": "Forfaitaire waarde (onvolledig)",
        "fiscal_value_incomplete_token": "Niet bepaalbaar",
        "fiscal_value_incomplete_caption": "EBITDA-component (excl. eigen vermogen)",
        "fiscal_value_incomplete_help": "Vul het boekhoudkundig eigen vermogen aan om de volledige forfaitaire waarde te bepalen. Tot dan toont dit rapport enkel het EBITDA-component, niet de wettelijke referentiewaarde.",
        "fiscal_ebitda_component_only_label": "{amount} (4× EBITDA)",
        "fiscal_internal_transfer_title": "Interne overdracht gemarkeerd —",
        "fiscal_internal_transfer_body": "bij overdracht aan een vennootschap waarin de overdrager of naaste familieleden controle uitoefenen kan een tarief van 33% gelden. De totale schuldenlast van de verwervende vennootschap mag niet hoger zijn dan 4× EBITDA van de werkmaatschappij (anti-misbruikregel). Laat dit door een fiscaal adviseur valideren.",
        "fiscal_holding_role_warning": "Dit bedrijf is een holding. De formule gebruikt de eigen jaarrekening van de holding en kan de waarde van onderliggende bedrijven missen. Vervang dit niet door de EBITDA van de groep of werkmaatschappij. Vraag een bevoegde professional of een onafhankelijke waardering beter past.",
        "fiscal_carve_out_title": "Vastgoed carve-out toegepast.",
        "fiscal_carve_out_body": "De getoonde EBITDA en boekhoudkundig eigen vermogen zijn aangepast voor uitgesloten vastgoed (boekwaarde van het pand uit eigen vermogen, fictieve markthuur uit EBITDA). De forfaitaire waarde reflecteert deze carve-out.",
        "fiscal_anchors_acknowledged_text": "De beschikbare wettelijke methodes zijn beoordeeld.",
        "fiscal_anchors_unacknowledged_text": "Controleer of een geldige transactie in 2025, contractuele formule of professioneel verslag van toepassing is voordat je deze waarde gebruikt.",
        "synthesis_title": "Synthese van de Waardering",
        "synthesis_intro": "Onderstaande tabel toont de vastgelegde modelweging van meerdere waarderingsmethodes tot één gewogen waarde.",
        "synthesis_col_method": "Methode",
        "synthesis_col_value": "Berekende Waarde",
        "synthesis_col_weight": "Gewicht",
        "synthesis_col_contribution": "Gewogen Bijdrage",
        "synthesis_total": "Gewogen Waarde",
        "synthesis_formula_label": "Formule",
        "synthesis_justification_label": "Motivering van de modelweging",
        "synthesis_benchmark_label": "Upswitch-benchmark",
        "synthesis_benchmark_label_weighted": "Modelreconciliatie",
        "synthesis_benchmark_note": "De Upswitch-marktbenadering is een onafhankelijke referentie die niet wordt beïnvloed door de adviseurweging. Beide worden bewaard voor marktintegriteit.",
        "synthesis_benchmark_note_weighted": "Deze modelreferentie weerspiegelt de reconciliatie voor de geselecteerde methodemix. Wanneer adviseurgewichten als rekenbasis zijn aanvaard, kan deze gelijk zijn aan de adviseurssynthese.",
        "disc_academic_review_title": "Academische kruiscontrole — beoordelen vóór externe verspreiding",
        "synthesis_subtitle": "Gewogen gemiddelde op basis van geselecteerde waarderingsmethodes",
        "synthesis_info_banner": "De adviseur heeft meerdere waarderingsmethodes geselecteerd en een eigen weging toegepast. Het resultaat is een gewogen gemiddelde dat het professionele oordeel van de adviseur weerspiegelt.",
        "synthesis_section_composition": "Samenstelling",
        "synthesis_table_footer_total": "Totaal",
        "synthesis_adaptive_label": "Upswitch Adaptive",
        "synthesis_engine_reference_label": "Modelreferentie",
        "synthesis_accountant_blend_label": "Gewogen modeluitkomst — ondernemingswaarde (EV)",
        "synthesis_disclaimer_title": "Opmerking",
        "synthesis_disclaimer_body": "De gewogen synthese weerspiegelt het professionele oordeel van de adviseur en kan afwijken van het Upswitch Adaptive-resultaat. De individuele methodewaarden zijn indicatief en afhankelijk van de beschikbare invoergegevens.",
        "synthesis_disclaimer_body_weighted": "De gewogen synthese weerspiegelt het professionele oordeel van de adviseur. De modelreferentie wordt apart bewaard wanneer beschikbaar; individuele methodewaarden zijn indicatief en afhankelijk van de beschikbare invoergegevens.",
        "synthesis_apv_value_basis": "APV-brug",
        "synthesis_apv_bridge_label": "CW belastingschild schulden",
        "synthesis_apv_bridge_note": "DCF omvat de afzonderlijk verdisconteerde APV-belastingschilden uit de klanttemplate.",
        "synthesis_apv_bridge_generic_note": "DCF omvat afzonderlijk verdisconteerde APV-belastingschilden uit expliciete invoer.",
        "synthesis_net_engine_value_basis": "Netto modelwaarde",
        "synthesis_net_engine_note": "Deze bijdrage gebruikt de gekalibreerde nettomultiplewaarde na standaard risico- en illiquiditeitscorrecties.",
        "dcf_sensitivity_matrix_caption_exit_multiple": "Ondernemingswaarde, compact weergegeven, bij variaties in WACC en exit-multiple.",
        "report_multiple_suffix_ev_revenue": "EV/Omzet",
        "report_benchmark_median_ev_revenue": "Marktmediaan (EV/Omzet)",
    }
