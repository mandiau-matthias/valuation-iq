"""Localized labels and static metadata for transaction-readiness reporting."""

from __future__ import annotations

LabelTuple = tuple[str, ...]


BUYER_PACKAGE_ARTIFACT_OWNER_BY_TYPE = {
    "valuation_main_report": "valuationiq",
    "valuation_pdf": "valuationiq",
    "im_cim": "valuationiq",
    "dd_checklist": "advisor",
    "buyer_faq": "advisor",
    "ebitda_bridge": "valuationiq",
    "wc_tax": "valuationiq",
    "data_room_manifest": "advisor",
    "price_recommendation": "valuationiq",
    "legal_readiness": "lawyer",
}

BUYER_PACKAGE_ARTIFACT_ACCESS_GATE_BY_TYPE = {
    "valuation_main_report": "internal",
    "valuation_pdf": "internal",
    "im_cim": "after_nda",
    "dd_checklist": "after_nda",
    "buyer_faq": "after_nda",
    "ebitda_bridge": "after_nda",
    "wc_tax": "after_nda",
    "data_room_manifest": "after_nda",
    "price_recommendation": "internal",
    "legal_readiness": "lawyer_only",
}

STATUS_LABELS: dict[str, LabelTuple] = {
    "ready": ("Vrijgaveklaar", "Ready", "Prêt à diffuser"),
    "blocked": ("Controle vereist", "Review required", "Contrôle requis"),
    "needs_review": ("Review vereist", "Needs review", "Revue nécessaire"),
    "missing": ("Ontbreekt", "Missing", "Manquant"),
    "present": ("Aanwezig", "Present", "Présent"),
    "review": ("Te reviewen", "Review", "À revoir"),
    "lawyer_review_required": (
        "Juridische beoordeling vereist",
        "Legal review required",
        "Revue juridique requise",
    ),
    "nda_required": ("NDA vereist", "NDA required", "NDA requis"),
    "teaser_ready": ("Teaserklaar", "Teaser ready", "Teaser prêt"),
}

SEVERITY_LABELS: dict[str, LabelTuple] = {
    "critical": ("Kritiek", "Critical", "Critique"),
    "high": ("Hoog", "High", "Élevé"),
    "medium": ("Middel", "Medium", "Moyen"),
    "low": ("Laag", "Low", "Faible"),
}

PRICE_MECHANISM_LABELS: dict[str, LabelTuple] = {
    "completion_accounts": (
        "Completion accounts",
        "Completion accounts",
        "Comptes de clôture",
    ),
    "locked_box_not_recommended_until_balance_sheet_verified": (
        "Locked-box niet aanbevolen zonder gevalideerde balans",
        "Locked box not recommended until balance sheet verified",
        "Locked-box déconseillé sans bilan validé",
    ),
}

SPA_AREA_LABELS: dict[str, LabelTuple] = {
    "price_mechanics": ("Prijsmechaniek", "Price mechanics", "Mécanique de prix"),
    "disclosure_schedule": (
        "Disclosurebijlage",
        "Disclosure schedule",
        "Annexe de divulgation",
    ),
    "management_continuity": (
        "Managementcontinuïteit",
        "Management continuity",
        "Continuité de la direction",
    ),
    "risk_allocation": ("Risicoverdeling", "Risk allocation", "Répartition des risques"),
}

SPA_INSTRUMENT_LABELS: dict[str, LabelTuple] = {
    "completion_accounts_or_locked_box_with_leakage_covenant": (
        "Completion accounts of locked-box met leakage-clausule",
        "Completion accounts or locked box with leakage covenant",
        "Comptes de clôture ou locked-box avec clause de leakage",
    ),
    "completion_accounts_required": (
        "Completion accounts vereist",
        "Completion accounts required",
        "Comptes de clôture requis",
    ),
    "seller_disclosure_and_document_completion": (
        "Verkopersdisclosure en documentaanvulling",
        "Seller disclosure and document completion",
        "Divulgation du vendeur et complétion documentaire",
    ),
    "owner_transition_covenant_or_earn_out": (
        "Eigenaars-overdrachtsbeding of earn-out",
        "Owner transition covenant or earn-out",
        "Clause de transition du dirigeant ou earn-out",
    ),
    "specific_indemnity_or_restructuring_condition": (
        "Specifieke vrijwaring of herstructureringsvoorwaarde",
        "Specific indemnity or restructuring condition",
        "Indemnité spécifique ou condition de restructuration",
    ),
}

BUYER_PACKAGE_ARTIFACT_LABELS: dict[str, LabelTuple] = {
    "valuation_main_report": (
        "Waarderingsrapport",
        "Valuation report",
        "Rapport de valorisation",
    ),
    "valuation_pdf": ("PDF-export", "PDF export", "Export PDF"),
    "im_cim": ("IM/CIM", "IM/CIM", "IM/CIM"),
    "dd_checklist": (
        "Due diligence-checklist",
        "Due diligence checklist",
        "Check-list de due diligence",
    ),
    "buyer_faq": ("Kopers-Q&A", "Buyer Q&A", "Q&R acquéreur"),
    "ebitda_bridge": ("EBITDA-brug", "EBITDA bridge", "Pont d'EBITDA"),
    "wc_tax": (
        "Werkkapitaal- en fiscaal pakket",
        "Working-capital and tax pack",
        "Dossier fonds de roulement et fiscalité",
    ),
    "data_room_manifest": (
        "Data-room manifest",
        "Data room manifest",
        "Manifeste de data room",
    ),
    "price_recommendation": (
        "Prijsadvies",
        "Price recommendation",
        "Recommandation de prix",
    ),
    "legal_readiness": (
        "Juridische gereedheidsoverdracht",
        "Legal-readiness handoff",
        "Transfert de préparation juridique",
    ),
}


def text(locale: str, nl: str, en: str, fr: str | None = None) -> str:
    loc = str(locale).lower()
    if loc.startswith("fr"):
        # Fall back to English, never Dutch, for FR strings not yet provided.
        return fr if fr is not None else en
    return en if loc.startswith("en") else nl


def tuple_text(locale: str, labels: LabelTuple) -> str:
    """Resolve a (nl, en[, fr]) label tuple for the report locale."""
    nl = labels[0]
    en = labels[1] if len(labels) > 1 else labels[0]
    fr = labels[2] if len(labels) > 2 else None
    return text(locale, nl, en, fr)


def fallback_label(value: object) -> str:
    return str(value or "").replace("_", " ").strip().title()


def _catalog_label(catalog: dict[str, LabelTuple], value: object, locale: str) -> str:
    key = str(value or "").strip().lower()
    labels = catalog.get(key)
    if labels is None:
        return fallback_label(value)
    return tuple_text(locale, labels)


def status_label(status: object, locale: str) -> str:
    return _catalog_label(STATUS_LABELS, status, locale)


def severity_label(severity: object, locale: str) -> str:
    return _catalog_label(SEVERITY_LABELS, severity, locale)


def price_mechanism_label(mechanism: object, locale: str) -> str:
    return _catalog_label(PRICE_MECHANISM_LABELS, mechanism, locale)


def spa_area_label(area: object, locale: str) -> str:
    return _catalog_label(SPA_AREA_LABELS, area, locale)


def spa_instrument_label(instrument: object, locale: str) -> str:
    return _catalog_label(SPA_INSTRUMENT_LABELS, instrument, locale)


def buyer_package_artifact_label(artifact_type: str, locale: str) -> str:
    labels = BUYER_PACKAGE_ARTIFACT_LABELS.get(artifact_type)
    if labels is None:
        return artifact_type.replace("_", " ").title()
    return tuple_text(locale, labels)
