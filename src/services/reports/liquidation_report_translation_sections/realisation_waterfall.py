"""Realisation schedule, waterfall, tax, wind-down, PV, and sensitivity copy."""

from __future__ import annotations

from typing import Dict


def build_realisation_waterfall_translations() -> Dict[str, Dict[str, str]]:
    """Return realisation schedule, waterfall, tax, wind-down, pv, and sensitivity copy."""
    return {
        # ---------------------------------------------------------------
        # Phase 1 — Section 3: Statement of Net Realisable Value
        # ---------------------------------------------------------------
        "schedule_section_title": {
            "nl": "Realisatieschema (12 activacategorieën)",
            "en": "Realisation Schedule (12 asset classes)",
        },
        "schedule_section_subtitle": {
            "nl": "EY/KPMG/Deloitte werkpapier-format — boek → FMV → realisatie",
            "en": "EY/KPMG/Deloitte working-paper format — book → FMV → realisation",
        },
        "schedule_col_class": {
            "nl": "Activacategorie",
            "en": "Asset class",
        },
        "schedule_col_book": {
            "nl": "Boekwaarde",
            "en": "Book value",
        },
        "schedule_col_adjusted": {
            "nl": "Aangepaste FMV",
            "en": "Adjusted FMV",
        },
        "schedule_col_orderly": {
            "nl": "Geordende realisatie",
            "en": "Orderly realisation",
        },
        "schedule_col_forced": {
            "nl": "Gedwongen realisatie",
            "en": "Forced realisation",
        },
        "schedule_col_orderly_factor": {
            "nl": "Factor (G)",
            "en": "Factor (O)",
        },
        "schedule_col_forced_factor": {
            "nl": "Factor (G)",
            "en": "Factor (F)",
        },
        "schedule_col_orderly_month": {
            "nl": "Maand (G)",
            "en": "Month (O)",
        },
        "schedule_total_label": {
            "nl": "Totaal",
            "en": "Total",
        },
        "schedule_unallocated_label": {
            "nl": "Niet-toegewezen residuele activa",
            "en": "Unallocated residual assets",
        },
        "schedule_unallocated_warning": {
            "nl": (
                "Het verschil tussen de balanstotaal en de gedecomponeerde "
                "activacategorieën wordt apart getoond. Override per categorie "
                "in het Venus-formulier om dit verder te verfijnen."
            ),
            "en": (
                "The gap between balance-sheet total and decomposed asset lines "
                "is shown separately. Override per class in the Venus form to "
                "refine further."
            ),
        },
        "schedule_class_cash": {"nl": "Liquide middelen", "en": "Cash"},
        "schedule_class_trade_receivables": {
            "nl": "Handelsvorderingen",
            "en": "Trade receivables",
        },
        "schedule_class_other_receivables": {
            "nl": "Overige vorderingen",
            "en": "Other receivables",
        },
        "schedule_class_inventory_finished": {
            "nl": "Voorraad — afgewerkt",
            "en": "Inventory — finished",
        },
        "schedule_class_inventory_wip": {
            "nl": "Voorraad — onderhanden werk",
            "en": "Inventory — work in progress",
        },
        "schedule_class_inventory_raw": {
            "nl": "Voorraad — grondstoffen",
            "en": "Inventory — raw materials",
        },
        "schedule_class_land": {"nl": "Terreinen", "en": "Land"},
        "schedule_class_buildings": {"nl": "Gebouwen", "en": "Buildings"},
        "schedule_class_machinery_equipment": {
            "nl": "Machines & uitrusting",
            "en": "Machinery & equipment",
        },
        "schedule_class_vehicles": {"nl": "Voertuigen", "en": "Vehicles"},
        "schedule_class_it_equipment": {
            "nl": "IT-uitrusting",
            "en": "IT equipment",
        },
        "schedule_class_intangibles": {
            "nl": "Immateriële activa",
            "en": "Intangibles",
        },
        "schedule_class_investments": {
            "nl": "Financiële vaste activa",
            "en": "Financial assets",
        },
        "schedule_class_other_tangible": {
            "nl": "Overige materiële activa",
            "en": "Other tangible assets",
        },
        # ---------------------------------------------------------------
        # Phase 2 — Section 5: Insolvency Priority Cascade (BE/NL)
        # ---------------------------------------------------------------
        "cascade_section_title": {
            "nl": "Schuldeisersrangorde (insolventie-cascade)",
            "en": "Creditor priority cascade (insolvency waterfall)",
        },
        "cascade_section_subtitle_be": {
            "nl": "Boek XX WER — wettelijke verdeling bij faillissement",
            "en": "Boek XX WER — statutory distribution in bankruptcy (Belgium)",
        },
        "cascade_section_subtitle_nl": {
            "nl": "Faillissementswet — wettelijke verdeling bij faillissement",
            "en": "Faillissementswet — statutory distribution in bankruptcy (Netherlands)",
        },
        "cascade_col_tier": {"nl": "Rang", "en": "Tier"},
        "cascade_col_anchor": {"nl": "Wettelijke basis", "en": "Statutory anchor"},
        "cascade_col_claim": {"nl": "Aangemelde vordering", "en": "Claim"},
        "cascade_col_recovery": {"nl": "Uitgekeerd", "en": "Recovered"},
        "cascade_col_recovery_rate": {"nl": "Dekking %", "en": "Recovery %"},
        "cascade_col_shortfall": {"nl": "Tekort", "en": "Shortfall"},
        "cascade_total_label": {"nl": "Totaal", "en": "Total"},
        "cascade_equity_to_shareholders": {
            "nl": "Restwaarde voor aandeelhouders (vóór belastingen)",
            "en": "Equity to shareholders (pre-tax)",
        },
        "cascade_estimated_buckets_warning": {
            "nl": (
                "Schuldverdeling per tranche is geschat op basis van "
                "jurisdictie-defaults (Graydon/KPMG cohort-statistiek). "
                "Voor een EY-grade rapport: lever expliciete tranches aan "
                "via de Venus-input."
            ),
            "en": (
                "Per-tier liability buckets are estimated from "
                "jurisdiction defaults (Graydon/KPMG cohort statistics). "
                "For an EY-grade report, supply explicit buckets via the "
                "Venus input."
            ),
        },
        # ---------------------------------------------------------------
        # Phase 2 — Section 6: Tax Leakage Bridge
        # ---------------------------------------------------------------
        "tax_section_title": {
            "nl": "Fiscale lekkage — bruto naar netto",
            "en": "Tax leakage bridge — gross to net",
        },
        "tax_section_subtitle_be": {
            "nl": "BE — scenario op basis van adviseursgegevens",
            "en": "BE — advisor-input tax scenario",
        },
        "tax_section_subtitle_nl": {
            "nl": "NL — progressieve box 2 + aanvullende vennootschapsbelasting",
            "en": "NL — progressive box 2 + incremental corporate tax",
        },
        "liquidation_scope_note": {
            "nl": "Ondernemingswaarde en voorwaardelijke netto-uitkeringen aan de eigenaar zijn afzonderlijke ramingen. Zonder volledige, gedateerde adviseursgegevens wordt de belasting niet berekend. Biedingsranges zijn niet onderbouwd zolang waarderingsgrondslagen en koperspremies niet zijn gereconcilieerd. Recuperatieaannames en gevoeligheidskwantielen vereisen onafhankelijke validatie; het zijn geen gekalibreerde voorspellingsintervallen.",
            "en": "Company equity and conditional after-tax owner proceeds are separate estimates. Tax is not assessed without complete dated advisor inputs. Buyer bid ranges are withheld because value bases and preset premiums have not been substantiated. Recovery assumptions and sensitivity quantiles require independent validation; they are not calibrated prediction intervals.",
        },
        "tax_not_assessed": {
            "nl": "Niet berekend: geen volledige, gedateerde fiscale onderbouwing voor deze situatie. De ondernemingswaarde is geen netto-uitkering aan de aandeelhouder.",
            "en": "Not assessed: complete dated tax inputs for this ownership situation are unavailable. Company value is not an after-tax shareholder payout.",
        },
        "tax_scope_note": {
            "nl": "Scenario voor één binnenlandse particuliere aandeelhouder met 100% eigendom. Geen bevestiging van fiscale vrijstellingen. Bedragen volgen de vermelde adviseursgegevens; belastingkredieten en verliesverrekening zijn niet gemodelleerd.",
            "en": "Scenario for one domestic individual owning 100%. Tax exemptions are not independently certified. Amounts use the referenced advisor inputs; tax credits and loss offsets are not modeled.",
        },
        "tax_calculation_note": {
            "nl": "De aanvullende vennootschapsbelasting is na belastingbedragen die al in de schuldeiserscascade zijn opgenomen. Meerwaarden en uitgestelde belastingen worden niet opnieuw belast. Gewone belaste reserves zijn niet vrijgesteld. Een ongedekte belastingverplichting vereist een herziening van de schuldeisersverdeling.",
            "en": "Incremental corporate cash tax excludes tax amounts already paid through the creditor cascade. Gains and deferred-tax balances are not charged again. Ordinary taxed reserves are not exempt. An unfunded tax liability requires reassessment of creditor distributions.",
        },
        "tax_sources_label": {"nl": "Fiscale bronnen", "en": "Tax policy sources"},
        "tax_basis_label_be": {"nl": "Fiscaal gestort kapitaal", "en": "Fiscal paid-up capital"},
        "tax_basis_label_nl": {"nl": "Verkrijgingsprijs aandelen", "en": "Share acquisition basis"},
        "tax_exempt_label": {
            "nl": "Expliciete vrijgestelde liquidatiereserve",
            "en": "Explicit exempt liquidation reserve",
        },
        "tax_other_income_label": {
            "nl": "Overig box-2-inkomen in hetzelfde jaar",
            "en": "Other box-2 income in the same year",
        },
        "tax_year_label": {"nl": "Belastingjaar", "en": "Tax year"},
        "tax_evidence_label": {"nl": "Fiscale onderbouwing", "en": "Tax evidence reference"},
        "tax_unfunded_label": {
            "nl": "Ongedekte vennootschapsbelasting",
            "en": "Unfunded corporate tax",
        },
        "tax_line_label_corporate_cash_tax": {
            "nl": "Aanvullende vennootschapsbelasting (na schuldeiserscascade)",
            "en": "Incremental corporate cash tax (after creditor cascade)",
        },
        "tax_col_label": {"nl": "Component", "en": "Component"},
        "tax_col_anchor": {"nl": "Wettelijke basis", "en": "Statutory anchor"},
        "tax_col_gross": {"nl": "Grondslag", "en": "Tax base"},
        "tax_col_rate": {"nl": "Tarief", "en": "Rate"},
        "tax_col_amount": {"nl": "Belasting", "en": "Tax"},
        "tax_total_label": {"nl": "Totale lekkage", "en": "Total leakage"},
        "tax_net_to_shareholders": {
            "nl": "Netto naar aandeelhouders",
            "en": "Net to shareholders",
        },
        "tax_gross_distribution": {
            "nl": "Bruto uitkering",
            "en": "Gross distribution",
        },
        # Per-line tax-leakage labels — keyed by `TaxLeakageLine.code`.
        # The engine emits Dutch labels as the fallback (so existing
        # engine-level unit tests stay green and direct dict consumers get
        # a useful label without resolving the locale); the report context
        # overlays the localized label on the way to the template.
        "tax_line_label_be_liquidation_bonus": {
            "nl": "Liquidatiebonus (30%)",
            "en": "Liquidation bonus (30%)",
        },
        "tax_line_label_be_capital_gains": {
            "nl": "Meerwaarde-belasting (historische aanname)",
            "en": "Capital-gains tax (historical assumption)",
        },
        "tax_line_label_nl_box2": {
            "nl": "Box 2 (progressief)",
            "en": "Box 2 (progressive)",
        },
        "tax_line_label_nl_vpb_gains": {
            "nl": "Vpb meerwaarde (25,8%)",
            "en": "Vpb capital gains (25.8%)",
        },
        "tax_line_label_dtl_reversal": {
            "nl": "Reversal uitgestelde belastingen (DTL)",
            "en": "Deferred tax liabilities reversal",
        },
        # ---------------------------------------------------------------
        # Phase 2 — Section 7: Wind-down Cost Build-up
        # ---------------------------------------------------------------
        "wind_down_section_title": {
            "nl": "Afbouwkosten — bottom-up opbouw",
            "en": "Wind-down costs — bottom-up build-up",
        },
        "wind_down_section_subtitle": {
            "nl": "EY/KPMG werkpapierformat — runway, ontslag, fees",
            "en": "EY/KPMG working-paper format — runway, severance, fees",
        },
        "wind_down_col_component": {"nl": "Component", "en": "Component"},
        "wind_down_col_anchor": {"nl": "Bron", "en": "Source"},
        "wind_down_col_amount": {"nl": "Bedrag", "en": "Amount"},
        "wind_down_total_label": {"nl": "Totaal afbouwkosten", "en": "Total wind-down cost"},
        "wind_down_runway_label": {"nl": "Runway", "en": "Runway"},
        "wind_down_headcount_label": {"nl": "VTE", "en": "Headcount"},
        "wind_down_months": {"nl": "maanden", "en": "months"},
        # Per-line wind-down label templates — keyed by
        # `WindDownLine.component`.  Use Python ``str.format()`` placeholders
        # so the engine-emitted ``label_params`` dict interpolates the
        # numeric values (runway_months / headcount / months / pct).  Engine
        # retains a Dutch fallback label so legacy / direct-dict consumers
        # still render without the locale-resolution step.
        "wind_down_line_label_payroll_runway": {
            "nl": "Payroll {runway_months} maanden ({headcount} VTE)",
            "en": "Payroll {runway_months} months ({headcount} FTE)",
        },
        "wind_down_line_label_lease_and_utilities": {
            "nl": "Huur + nutsvoorzieningen ({months} maanden)",
            "en": "Rent + utilities ({months} months)",
        },
        "wind_down_line_label_severance": {
            "nl": "Ontslagvergoeding ({months:.1f} mnd × {headcount} VTE)",
            "en": "Severance ({months:.1f} mo × {headcount} FTE)",
        },
        "wind_down_line_label_professional_fees": {
            "nl": "Curator/legal/audit fees ({pct:.1f}%)",
            "en": "Trustee / legal / audit fees ({pct:.1f}%)",
        },
        "wind_down_line_label_retention_bonuses": {
            "nl": "Retentiebonussen kernpersoneel",
            "en": "Key-staff retention bonuses",
        },
        "wind_down_line_label_other_one_offs": {
            "nl": "Overige eenmalige kosten ({pct:.1f}%)",
            "en": "Other one-off costs ({pct:.1f}%)",
        },
        # ---------------------------------------------------------------
        # Phase 3 — Section 8: PV-Discounted Disposal Schedule
        # ---------------------------------------------------------------
        "pv_section_title": {
            "nl": "Tijdgewogen realisatie — PV-discount",
            "en": "Time-weighted realisation — PV discount",
        },
        "pv_section_subtitle": {
            "nl": "Damodaran (2012) Hfdst. 23 — distress WACC over disposal-tijdlijn",
            "en": "Damodaran (2012) Ch. 23 — distress WACC over disposal timeline",
        },
        "pv_col_class": {"nl": "Activacategorie", "en": "Asset class"},
        "pv_col_nominal": {"nl": "Nominaal", "en": "Nominal"},
        "pv_col_month": {"nl": "Maand", "en": "Month"},
        "pv_col_factor": {"nl": "PV factor", "en": "PV factor"},
        "pv_col_pv": {"nl": "Contante waarde", "en": "Present value"},
        "pv_col_haircut": {"nl": "Tijdkorting", "en": "Time discount"},
        "pv_total_label": {"nl": "Totaal PV", "en": "Total PV"},
        "pv_wacc_label": {"nl": "Distress WACC (jaarlijks)", "en": "Distress WACC (annual)"},
        # ---------------------------------------------------------------
        # Phase 3 — Section 9: Sensitivity Analysis (Tornado + P10/P50/P90)
        # ---------------------------------------------------------------
        "sensitivity_section_title": {
            "nl": "Gevoeligheidsanalyse — Tornado + P10/P50/P90",
            "en": "Sensitivity analysis — Tornado + P10/P50/P90",
        },
        "sensitivity_section_subtitle": {
            "nl": "McKinsey 2020 Hfdst. 35 + Iman & Conover (1982) Latin-hypercube",
            "en": "McKinsey 2020 Ch. 35 + Iman & Conover (1982) Latin-hypercube",
        },
        "sensitivity_central": {"nl": "Centrale waarde", "en": "Central value"},
        "sensitivity_p10": {"nl": "P10 (bear case)", "en": "P10 (bear case)"},
        "sensitivity_p50": {"nl": "P50 (mediaan)", "en": "P50 (median)"},
        "sensitivity_p90": {"nl": "P90 (bull case)", "en": "P90 (bull case)"},
        "sensitivity_tornado_title": {
            "nl": "Tornado-impact per driver",
            "en": "Tornado impact per driver",
        },
        "sensitivity_col_driver": {"nl": "Driver", "en": "Driver"},
        # Per-driver labels — replace engine-internal keys
        # ("asset_recovery_scalar" etc.) with human-readable copy per
        # locale. Maps onto the four drivers `_run_sensitivity` registers
        # in scenarios.py. New driver names need a new key here AND a
        # bilingual entry in the translation dict.
        "sensitivity_driver_asset_recovery_scalar": {
            "nl": "Activarecuperatie (× factor)",
            "en": "Asset recovery (× factor)",
        },
        "sensitivity_driver_liability_scalar": {
            "nl": "Passiva (× factor)",
            "en": "Liabilities (× factor)",
        },
        "sensitivity_driver_wind_down_scalar": {
            "nl": "Afbouwkost (× factor)",
            "en": "Wind-down cost (× factor)",
        },
        "sensitivity_driver_tax_scalar": {
            "nl": "Belastinglekkage (× factor)",
            "en": "Tax leakage (× factor)",
        },
        "sensitivity_col_impact_low": {"nl": "Impact bij lage waarde", "en": "Impact at low"},
        "sensitivity_col_impact_high": {"nl": "Impact bij hoge waarde", "en": "Impact at high"},
        "sensitivity_col_range": {"nl": "Bereik", "en": "Range"},
        "sensitivity_sample_count": {"nl": "Aantal samples", "en": "Sample count"},
        # ---------------------------------------------------------------
        # Phase 3 — Section 9b: Premise Reconciliation
        # ---------------------------------------------------------------
        "reconciliation_section_title": {
            "nl": "Premissereconciliatie — LV vs Adj-NAV vs DCF",
            "en": "Premise reconciliation — LV vs Adj-NAV vs DCF",
        },
        "reconciliation_section_subtitle": {
            "nl": "Vergelijking van equitywaarden — beoordeling vereist",
            "en": "Equity comparison — review required",
        },
        "reconciliation_lv": {
            "nl": "Liquidatiewaarde vóór aandeelhoudersbelasting",
            "en": "Liquidation equity before shareholder tax",
        },
        "reconciliation_nav": {"nl": "Adjusted NAV", "en": "Adjusted NAV"},
        "reconciliation_dcf": {"nl": "DCF waarde", "en": "DCF value"},
        "reconciliation_multiples": {"nl": "Multiples waarde", "en": "Multiples value"},
        "reconciliation_defensible_yes": {
            "nl": "Going-concern verdedigbaar",
            "en": "Going-concern defensible",
        },
        "reconciliation_defensible_no": {
            "nl": "Going-concern niet langer verdedigbaar",
            "en": "Going-concern no longer defensible",
        },
        "reconciliation_recommendation_label": {
            "nl": "Aanbevolen primaire lens",
            "en": "Recommended primary lens",
        },
        "reconciliation_recommendation_going_concern_dcf": {
            "nl": "Going-concern (DCF/multiples)",
            "en": "Going-concern (DCF/multiples)",
        },
        "reconciliation_recommendation_going_concern_nav": {
            "nl": "Going-concern (Adjusted NAV)",
            "en": "Going-concern (Adjusted NAV)",
        },
        "reconciliation_recommendation_liquidation": {
            "nl": "Liquidatie",
            "en": "Liquidation",
        },
        "reconciliation_recommendation_indeterminate": {
            "nl": "Onbepaald — onvoldoende data",
            "en": "Indeterminate — insufficient data",
        },
        "reconciliation_requires_review": {
            "nl": "Continuïteit niet beoordeeld",
            "en": "Going-concern viability not assessed",
        },
        "reconciliation_scope": {
            "nl": "De vergelijking veronderstelt equitywaarden voor hetzelfde belang, dezelfde datum en munt. Aangeleverde vergelijkingswaarden en de vergelijkingsmarge van het model vereisen beoordeling; deze rangschikking bepaalt geen continuïteit, juridische insolventie of transactieprijs.",
            "en": "The comparison assumes equity values for the same interest, date and currency. Supplied comparisons and the model's ranking margin require review; this ranking does not establish viability, legal insolvency or a transaction price.",
        },
    }
