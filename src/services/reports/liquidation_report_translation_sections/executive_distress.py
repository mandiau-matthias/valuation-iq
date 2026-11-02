"""Executive, premise, and distress copy."""

from __future__ import annotations

from typing import Dict


def build_executive_distress_translations() -> Dict[str, Dict[str, str]]:
    """Return executive, premise, and distress copy."""
    return {
        # Hero / executive summary
        "headline_section_title": {
            "nl": "Liquidatiewaarde",
            "en": "Liquidation analysis",
        },
        "headline_subtitle": {
            "nl": "Geordende afbouw + gedwongen veiling",
            "en": "Orderly wind-down + forced auction",
        },
        "scenario_orderly": {
            "nl": "Geordende liquidatie (6–12 maanden)",
            "en": "Orderly liquidation (6–12 months)",
        },
        "scenario_forced": {
            "nl": "Gedwongen liquidatie (onmiddellijke veiling)",
            "en": "Forced liquidation (immediate auction)",
        },
        "scenario_book": {
            "nl": "Boekwaarde eigen vermogen (referentie)",
            "en": "Book equity (reference)",
        },
        "label_equity_to_owner": {
            "nl": "Verwacht residueel eigen vermogen",
            "en": "Expected residual equity",
        },
        "label_assets_book": {
            "nl": "Totaal activa (boekwaarde)",
            "en": "Total assets (book value)",
        },
        "label_assets_adjusted": {
            "nl": "Totaal activa (na recovery-factor)",
            "en": "Total assets (after recovery factor)",
        },
        "label_liabilities_adjusted": {
            "nl": "Totaal passiva (incl. liquidatiekosten)",
            "en": "Total liabilities (incl. wind-down costs)",
        },
        "label_value_low": {"nl": "Onderkant", "en": "Low"},
        "label_value_high": {"nl": "Bovenkant", "en": "High"},
        # Insolvency chip
        "insolvency_chip_title": {
            "nl": "Insolventie-signaal",
            "en": "Insolvency signal",
        },
        "insolvency_chip_orderly": {
            "nl": (
                "In het geordende scenario zijn de gecorrigeerde activa "
                "kleiner dan de passiva — restwaarde voor de aandeelhouder "
                "is afgerond op nul."
            ),
            "en": (
                "In the orderly scenario adjusted assets are smaller than "
                "liabilities — residual equity is clamped at zero."
            ),
        },
        "insolvency_chip_forced": {
            "nl": (
                "In het gedwongen scenario zijn de gecorrigeerde activa "
                "kleiner dan de passiva — restwaarde voor de aandeelhouder "
                "is afgerond op nul."
            ),
            "en": (
                "In the forced scenario adjusted assets are smaller than "
                "liabilities — residual equity is clamped at zero."
            ),
        },
        # Scope note (legal-grade caveat surfaced verbatim from the engine)
        "scope_note_title": {
            "nl": "Reikwijdte van deze MVP-analyse",
            "en": "Scope of this MVP analysis",
        },
        # Sources line (footer)
        "sources_label": {
            "nl": "Academische bronnen",
            "en": "Academic sources",
        },
        # CTA — bridges to advisor / curator handoff
        "cta_title": {
            "nl": "Heeft u een formele insolventieprocedure nodig?",
            "en": "Need a formal insolvency proceeding?",
        },
        "cta_body": {
            "nl": (
                "Voor faillissementsdossiers en gerechtelijke reorganisaties "
                "heeft u een advocaat-curator nodig die de volledige "
                "schuldeisersrangorde toepast (RSZ/BTW super-prioriteit, "
                "WCO werknemersafvloeiing, fiscus, gewone schuldeisers, "
                "achtergestelde aandeelhoudersleningen). Deze Upswitch-analyse "
                "trekt verplichtingen af tegen boekwaarde — voldoende voor "
                "scenario-analyse en onderhandelingsvloer, maar niet voor een "
                "gerechtelijke procedure."
            ),
            "en": (
                "Formal bankruptcy dossiers and judicial reorganisation "
                "require a court-appointed trustee who applies the full "
                "creditor priority cascade (RSZ/BTW super-priority, "
                "employee severance under WCO, fiscus, unsecured, "
                "subordinated shareholder loans). This Upswitch analysis "
                "subtracts liabilities at book value — sufficient for "
                "scenario analysis and a negotiation floor, but not for a "
                "formal proceeding."
            ),
        },
        # ---------------------------------------------------------------
        # Phase 1 — Section 1: Premise of Value (IVS 104 §60–80)
        # ---------------------------------------------------------------
        "premise_section_title": {
            "nl": "Premisse van de waarde",
            "en": "Premise of Value",
        },
        "premise_section_subtitle": {
            "nl": "Scenariovergelijking — beoordeling vereist",
            "en": "Scenario comparison — review required",
        },
        "premise_primary_label": {
            "nl": "Vergelijkingsscenario",
            "en": "Comparison scenario",
        },
        "premise_secondary_label": {
            "nl": "Secundaire premisse (reconciliatie)",
            "en": "Secondary premise (reconciliation)",
        },
        "premise_value_going_concern": {
            "nl": "Going concern",
            "en": "Going concern",
        },
        "premise_value_orderly_liquidation": {
            "nl": "Geordende liquidatie",
            "en": "Orderly liquidation",
        },
        "premise_value_forced_liquidation": {
            "nl": "Gedwongen liquidatie",
            "en": "Forced liquidation",
        },
        "premise_weights_label": {
            "nl": "Waarschijnlijkheidsgewogen waarde",
            "en": "Probability-weighted value",
        },
        "premise_going_concern_weight": {
            "nl": "Going-concern gewicht",
            "en": "Going-concern weight",
        },
        "premise_liquidation_weight": {
            "nl": "Liquidatie gewicht",
            "en": "Liquidation weight",
        },
        "premise_expected_value_label": {
            "nl": "Verwachte equity (E[V])",
            "en": "Expected equity (E[V])",
        },
        "premise_rationale_label": {
            "nl": "Rationale",
            "en": "Rationale",
        },
        "premise_trigger_distress_score": {
            "nl": "geactiveerd door distress-score (Altman Z'')",
            "en": "triggered by distress score (Altman Z'')",
        },
        "premise_trigger_balance_sheet_insolvent": {
            "nl": "tekort in liquidatiescenario",
            "en": "shortfall in liquidation scenario",
        },
        "premise_trigger_owner_override": {
            "nl": "geactiveerd door uitdrukkelijke override",
            "en": "triggered by explicit override",
        },
        "premise_trigger_default_going_concern": {
            "nl": "standaardvergelijking — score ontbreekt",
            "en": "default comparison — score unavailable",
        },
        # ---------------------------------------------------------------
        # Phase 1 — Section 2: Distress Probability (Altman Z'' 2000)
        # ---------------------------------------------------------------
        "distress_section_title": {
            "nl": "Financiële screening (Altman Z'')",
            "en": "Financial screening (Altman Z'')",
        },
        "distress_section_subtitle": {
            "nl": "Vier-ratio financiële score",
            "en": "Four-ratio financial score",
        },
        "distress_z_label": {
            "nl": "Altman Z''-score",
            "en": "Altman Z'' score",
        },
        "distress_zone_label": {
            "nl": "Zone",
            "en": "Zone",
        },
        "distress_probability_label": {
            "nl": "P(distress)",
            "en": "P(distress)",
        },
        "distress_zone_safe": {
            "nl": "Hoge score (Z'' > 2,60)",
            "en": "High score (Z'' > 2.60)",
        },
        "distress_zone_grey": {
            "nl": "Grijs (1,10 ≤ Z'' ≤ 2,60)",
            "en": "Grey (1.10 ≤ Z'' ≤ 2.60)",
        },
        "distress_zone_distress": {
            "nl": "Distress (Z'' < 1,10)",
            "en": "Distress (Z'' < 1.10)",
        },
        "distress_zone_undetermined": {
            "nl": "Onbepaald (onvoldoende inputs)",
            "en": "Undetermined (insufficient inputs)",
        },
        "distress_ratio_x1": {
            "nl": "X1 — Werkkapitaal / Totaal activa",
            "en": "X1 — Working capital / Total assets",
        },
        "distress_ratio_x2": {
            "nl": "X2 — Reserves / Totaal activa",
            "en": "X2 — Retained earnings / Total assets",
        },
        "distress_ratio_x3": {
            "nl": "X3 — EBIT / Totaal activa",
            "en": "X3 — EBIT / Total assets",
        },
        "distress_ratio_x4": {
            "nl": "X4 — Eigen vermogen / Totaal passiva",
            "en": "X4 — Equity / Total liabilities",
        },
        "distress_formula_label": {
            "nl": "Z'' = 6,56·X1 + 3,26·X2 + 6,72·X3 + 1,05·X4",
            "en": "Z'' = 6.56·X1 + 3.26·X2 + 6.72·X3 + 1.05·X4",
        },
        "distress_unavailable_title": {
            "nl": "Z'' niet berekend",
            "en": "Z'' not computed",
        },
        "premise_weights_unavailable": {
            "nl": "Niet berekend. Een gekalibreerde kans met passende horizon en vergelijkbare equitywaarden ontbreekt. De financiële score levert geen waarderingsgewichten op.",
            "en": "Not assessed. A calibrated probability with a matching horizon and comparable equity values is unavailable. The financial score does not supply valuation weights.",
        },
        "distress_probability_unavailable": {
            "nl": "Niet gekalibreerd",
            "en": "Not calibrated",
        },
        "distress_screen_scope": {
            "nl": "Dit is een financiële screening, geen faillissementskans of oordeel over continuïteit. De voorspellende nauwkeurigheid voor deze kmo-populatie is niet aangetoond. De zone gebruikt de ongeronde score.",
            "en": "This is a financial screen, not a bankruptcy probability or a conclusion on going concern. Predictive accuracy for this SME population is unproven. The zone uses the unrounded score.",
        },
        "distress_missing_scope": {
            "nl": "De score vereist volledige, eindige en onderling consistente balansgegevens en EBIT uit dezelfde periode. Ontbrekende posten worden niet nul. Oudere scores moeten opnieuw worden berekend.",
            "en": "The score requires complete, finite and consistent balance-sheet data and EBIT from the same period. Missing items are not zero. Older scores require recalculation.",
        },
        "premise_review_owner_override": {
            "nl": "Uitdrukkelijke scenarioaanname van eigenaar of adviseur; beoordeling vereist. Deze keuze verandert de geordende liquidatiewaarde in de samenvatting niet.",
            "en": "Explicit owner or advisor scenario assumption; review required. This choice does not change the orderly liquidation headline.",
        },
        "premise_review_balance_sheet_insolvent": {
            "nl": "Een tekort in het liquidatiescenario vereist onderzoek naar financiering, verplichtingen en verkoopvoorwaarden. Het bewijst geen juridische insolventie of gedwongen verkoop.",
            "en": "A liquidation scenario shortfall requires review of funding, obligations and sale conditions. It does not establish legal insolvency or a forced sale.",
        },
        "premise_review_distress_score": {
            "nl": "De financiële score suggereert alleen een vergelijkingsscenario. De waarderingspremisse vereist beoordeling door een adviseur. De samenvatting toont geordende liquidatie.",
            "en": "The financial screen suggests a comparison scenario only. The valuation premise requires advisor review. The headline shows orderly liquidation.",
        },
        "premise_review_default_going_concern": {
            "nl": "Going-concernvergelijking in afwachting van beoordeling; de financiële score ontbreekt. Dit bevestigt geen continuïteit. De samenvatting toont geordende liquidatie.",
            "en": "Going-concern comparison pending review; the financial screen is unavailable. This does not establish viability. The headline shows orderly liquidation.",
        },
    }
