"""Localized document requirements for sealed method exclusions."""

METHOD_LABELS = {
    "en": {
        "upswitch_adaptive": "Synthesis",
        "ebitda_multiple": "EBITDA multiple",
        "dcf": "DCF",
        "sde_multiple": "SDE multiple",
        "omzet_multiple": "Revenue multiple",
        "arr_multiple": "ARR multiple",
        "adjusted_nav": "Adjusted net assets",
        "real_estate_yield": "Property yield",
        "fiscal_4x": "Fiscal reference",
        "startup_valuation": "Startup valuation",
        "liquidation_analysis": "Liquidation value",
        "holding_sotp": "Holding sum of parts",
    },
    "nl": {
        "upswitch_adaptive": "Synthese",
        "ebitda_multiple": "EBITDA-multiple",
        "dcf": "DCF",
        "sde_multiple": "SDE-multiple",
        "omzet_multiple": "Omzetmultiple",
        "arr_multiple": "ARR-multiple",
        "adjusted_nav": "Gecorrigeerd netto-actief",
        "real_estate_yield": "Vastgoedrendement",
        "fiscal_4x": "Fiscale referentie",
        "startup_valuation": "Startupwaardering",
        "liquidation_analysis": "Liquidatiewaarde",
        "holding_sotp": "Som van holdingonderdelen",
    },
    "fr": {
        "upswitch_adaptive": "Synthèse",
        "ebitda_multiple": "Multiple d’EBITDA",
        "dcf": "DCF",
        "sde_multiple": "Multiple de SDE",
        "omzet_multiple": "Multiple du chiffre d’affaires",
        "arr_multiple": "Multiple d’ARR",
        "adjusted_nav": "Actif net ajusté",
        "real_estate_yield": "Rendement immobilier",
        "fiscal_4x": "Référence fiscale",
        "startup_valuation": "Valorisation de startup",
        "liquidation_analysis": "Valeur de liquidation",
        "holding_sotp": "Somme des parties de la holding",
    },
}

# These are presentation requirements. The original decision and reason stay
# untouched in the sealed contract and remain available to reviewers.
REQUIREMENTS = {
    "en": {
        "disabled": "This method was excluded by the calculation request.",
        "bridge": "A complete source-backed bridge is required before shareholder value can be published. An independently eligible enterprise value may still be available.",
        "dcf": "Provide a verified company-issued forecast or cash-flow schedule with source documents.",
        "sde_multiple": "Provide approved, source-backed owner compensation adjustments and an eligible SDE benchmark.",
        "omzet_multiple": "Provide the benchmark cohort’s revenue definition and matching source financial facts.",
        "arr_multiple": "Provide verified recurring-revenue metrics and an eligible ARR benchmark.",
        "adjusted_nav": "Provide a complete balance sheet and source-backed asset and liability adjustments.",
        "real_estate_yield": "Provide verified property income, lease terms and a source-backed yield benchmark.",
        "fiscal_4x": "Provide the balance sheet and eligibility evidence required by the fiscal reference method.",
        "startup_valuation": "Provide verified funding, ownership and operating evidence required by the startup method.",
        "liquidation_analysis": "Provide a complete asset and liability schedule, realization assumptions and disposal costs.",
        "holding_sotp": "Provide verified subsidiary values, ownership percentages and holding-level balances.",
        "default": "Required source evidence or an independently eligible value basis is incomplete. Review the sealed method decision before pricing.",
    },
    "nl": {
        "disabled": "Deze methode is uitgesloten door de berekeningsaanvraag.",
        "bridge": "Een volledige brononderbouwde brug is vereist vóór publicatie van de aandelenwaarde. Een afzonderlijk toelaatbare ondernemingswaarde kan wel beschikbaar zijn.",
        "dcf": "Bezorg een geverifieerde bedrijfsprognose of kasstroomschema met brondocumenten.",
        "sde_multiple": "Bezorg goedgekeurde, brononderbouwde correcties voor eigenaarsbezoldiging en een toelaatbare SDE-benchmark.",
        "omzet_multiple": "Bezorg de omzetdefinitie van de benchmarkgroep en overeenstemmende financiële brongegevens.",
        "arr_multiple": "Bezorg geverifieerde cijfers voor recurrente omzet en een toelaatbare ARR-benchmark.",
        "adjusted_nav": "Bezorg een volledige balans en brononderbouwde correcties voor activa en verplichtingen.",
        "real_estate_yield": "Bezorg geverifieerde vastgoedinkomsten, huurvoorwaarden en een brononderbouwde rendementsbenchmark.",
        "fiscal_4x": "Bezorg de balans en het vereiste toelatingsbewijs voor de fiscale referentiemethode.",
        "startup_valuation": "Bezorg geverifieerde financierings-, eigendoms- en operationele gegevens voor de startupmethode.",
        "liquidation_analysis": "Bezorg een volledig overzicht van activa en verplichtingen, realisatieaannames en verkoopkosten.",
        "holding_sotp": "Bezorg geverifieerde dochterwaarden, eigendomspercentages en balansgegevens van de holding.",
        "default": "Vereist bronbewijs of een afzonderlijk toelaatbare waarderingsbasis is onvolledig. Controleer de verzegelde methodebeslissing vóór prijsbepaling.",
    },
    "fr": {
        "disabled": "Cette méthode a été exclue par la demande de calcul.",
        "bridge": "Un passage complet et étayé par les sources est requis avant de publier la valeur des capitaux propres. Une valeur d’entreprise admissible indépendamment peut rester disponible.",
        "dcf": "Fournissez des prévisions émises par l’entreprise ou un tableau de flux de trésorerie vérifiés, avec les documents sources.",
        "sde_multiple": "Fournissez les ajustements approuvés et documentés de rémunération du propriétaire ainsi qu’un benchmark de SDE admissible.",
        "omzet_multiple": "Fournissez la définition du chiffre d’affaires du groupe de référence et les données financières sources correspondantes.",
        "arr_multiple": "Fournissez les revenus récurrents vérifiés et un benchmark d’ARR admissible.",
        "adjusted_nav": "Fournissez un bilan complet et des ajustements documentés des actifs et des passifs.",
        "real_estate_yield": "Fournissez les revenus immobiliers vérifiés, les conditions des baux et un benchmark de rendement documenté.",
        "fiscal_4x": "Fournissez le bilan et les preuves d’admissibilité requises par la méthode de référence fiscale.",
        "startup_valuation": "Fournissez les données vérifiées de financement, de propriété et d’exploitation requises pour la méthode de startup.",
        "liquidation_analysis": "Fournissez un inventaire complet des actifs et passifs, les hypothèses de réalisation et les coûts de cession.",
        "holding_sotp": "Fournissez les valeurs vérifiées des filiales, les pourcentages de propriété et le bilan de la holding.",
        "default": "Les preuves sources requises ou une base de valeur admissible indépendamment sont incomplètes. Examinez la décision scellée avant de chiffrer.",
    },
}


def exclusion_requirement(method: str, reason: str, locale: str) -> str:
    copy = REQUIREMENTS.get(locale[:2].lower(), REQUIREMENTS["en"])
    if "disabled by request" in reason.lower():
        return copy["disabled"]
    if reason.startswith("EQUITY_BRIDGE_INCOMPLETE"):
        return copy["bridge"]
    return copy.get(method, copy["default"])
