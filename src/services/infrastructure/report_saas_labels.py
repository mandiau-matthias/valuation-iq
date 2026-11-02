"""Localized display labels for SaaS ARR-multiple adjustment breakdowns."""

from __future__ import annotations

from collections.abc import Mapping

from src.services.infrastructure.report_locale import normalize_report_locale

_SAAS_BREAKDOWN_NOTES_EN: dict[str, str] = {
    "saas_regional": (
        "Private Benelux / EU SaaS SMEs trade below US public cloud benchmark levels."
    ),
    "saas_nrr_120": "NRR above 120% unlocks premium ARR multiples.",
    "saas_nrr_110": "NRR above 110% supports a premium multiple.",
    "saas_nrr_100": "NRR at or above 100% shows healthy retention.",
    "saas_nrr_90": "NRR below 90% pressures the valuation multiple.",
    "saas_churn_15": "High revenue churn is a strong multiple drag.",
    "saas_churn_10": "Revenue churn above 10% reduces multiple confidence.",
    "saas_churn_5": "Revenue churn between 5–10% is moderate for SME SaaS.",
    "saas_ro40_60": "Rule of 40 above 60 is elite for SME SaaS.",
    "saas_ro40_40": "Rule of 40 at or above 40 supports a premium multiple.",
    "saas_ro40_20": "Rule of 40 below 20 signals weaker SaaS efficiency.",
    "saas_ag_50": "ARR growth above 50% warrants the strongest premium.",
    "saas_ag_30": "ARR growth above 30% supports a premium.",
    "saas_ag_10_30": "ARR growth between 10–30% shows steady momentum.",
    "saas_ag_10": "Low ARR growth narrows the valuation range.",
    "saas_cc_70": "Heavy customer concentration increases retention risk.",
    "saas_cc_50": "Top-customer concentration above 50% reduces quality.",
    "saas_cc_30": "Customer concentration between 30–50% is a moderate risk signal.",
    "saas_gm_80": "Gross margin above 80% supports SaaS quality.",
    "saas_gm_60": "Gross margin below 60% weakens SaaS quality.",
    "saas_exp_20": "Expansion revenue above 20% improves compounding quality.",
    "saas_exp_10": "Expansion revenue between 10–20% shows healthy upsell motion.",
    "saas_exp_low": "Expansion revenue below 5% signals limited upsell capability.",
}

_SAAS_BREAKDOWN_NOTES_NL: dict[str, str] = {
    "saas_regional": (
        "Private Benelux- en EU-SaaS-KMO's noteren doorgaans onder Amerikaanse "
        "beursbenchmarks voor cloud."
    ),
    "saas_nrr_120": "NRR boven 120% rechtvaardigt een premie op de ARR-multiple.",
    "saas_nrr_110": "NRR boven 110% ondersteunt een hogere multiple.",
    "saas_nrr_100": "NRR van minstens 100% toont gezonde retentie.",
    "saas_nrr_90": "NRR onder 90% drukt de waarderingsmultiple.",
    "saas_churn_15": "Hoge omzet-churn is een sterke rem op de multiple.",
    "saas_churn_10": "Omzet-churn boven 10% vermindert het vertrouwen in de multiple.",
    "saas_churn_5": "Omzet-churn tussen 5–10% is matig voor KMO-SaaS.",
    "saas_ro40_60": "Rule of 40 boven 60 is uitzonderlijk sterk voor KMO-SaaS.",
    "saas_ro40_40": "Rule of 40 van minstens 40 ondersteunt een premie op de multiple.",
    "saas_ro40_20": "Rule of 40 onder 20 wijst op lagere SaaS-efficiëntie.",
    "saas_ag_50": "ARR-groei boven 50% rechtvaardigt de sterkste premie.",
    "saas_ag_30": "ARR-groei boven 30% ondersteunt een premie.",
    "saas_ag_10_30": "ARR-groei tussen 10–30% toont stabiel momentum.",
    "saas_ag_10": "Lage ARR-groei vernauwt het waardebereik.",
    "saas_cc_70": "Sterke klantconcentratie verhoogt retentierisico.",
    "saas_cc_50": "Topklantconcentratie boven 50% vermindert kwaliteit.",
    "saas_cc_30": "Klantconcentratie tussen 30–50% is een matig risicosignaal.",
    "saas_gm_80": "Brutomarge boven 80% ondersteunt SaaS-kwaliteit.",
    "saas_gm_60": "Brutomarge onder 60% verzwakt SaaS-kwaliteit.",
    "saas_exp_20": "Expansie-omzet boven 20% verbetert de samengestelde groei.",
    "saas_exp_10": "Expansie-omzet tussen 10–20% toont gezonde upsell-beweging.",
    "saas_exp_low": "Expansie-omzet onder 5% wijst op beperkte upsell-capaciteit.",
}

_SAAS_FACTOR_LABELS_EN: dict[str, str] = {
    "regional_belgian_eu_private_discount": "Regional discount (private SME)",
    "nrr": "Net revenue retention (NRR)",
    "gross_revenue_churn": "Gross revenue churn",
    "rule_of_40": "Rule of 40",
    "arr_growth": "ARR growth",
    "customer_concentration": "Customer concentration",
    "gross_margin": "Gross margin",
    "expansion_revenue": "Expansion revenue",
}

_SAAS_FACTOR_LABELS_NL: dict[str, str] = {
    "regional_belgian_eu_private_discount": "Regionale korting (privé-KMO)",
    "nrr": "Netto-omzetretentie (NRR)",
    "gross_revenue_churn": "Bruto omzet-churn",
    "rule_of_40": "Rule of 40",
    "arr_growth": "ARR-groei",
    "customer_concentration": "Klantconcentratie",
    "gross_margin": "Brutomarge",
    "expansion_revenue": "Expansie-omzet",
}

_SAAS_FALLBACK_ACRONYMS: dict[str, str] = {
    "arr": "ARR",
    "ai": "AI",
    "be": "BE",
    "cac": "CAC",
    "ebit": "EBIT",
    "ebitda": "EBITDA",
    "eu": "EU",
    "fr": "FR",
    "kmo": "KMO",
    "ltv": "LTV",
    "mrr": "MRR",
    "nl": "NL",
    "nrr": "NRR",
    "saas": "SaaS",
    "sme": "SME",
    "us": "US",
    "yoy": "YoY",
}


def _smart_title_factor(slug: str) -> str:
    """
    Title-case fallback for engine-emitted factor slugs not present in curated maps.

    Preserves common acronyms so a never-before-seen factor still reads correctly.
    """
    parts = [p for p in slug.split("_") if p]
    if not parts:
        return ""
    rendered = [
        (
            _SAAS_FALLBACK_ACRONYMS[p.lower()]
            if p.lower() in _SAAS_FALLBACK_ACRONYMS
            else p.capitalize()
        )
        for p in parts
    ]
    return " ".join(rendered)


def localize_saas_adjustment_breakdown(
    rows: list[object] | None,
    locale: str,
) -> list[dict[str, object]]:
    """
    Add ``factor_display`` and ``note_display`` to each SaaS ARR-multiple adjustment row.
    """
    if not rows:
        return []
    loc_en = normalize_report_locale(locale) == "en"
    notes = _SAAS_BREAKDOWN_NOTES_EN if loc_en else _SAAS_BREAKDOWN_NOTES_NL
    factors = _SAAS_FACTOR_LABELS_EN if loc_en else _SAAS_FACTOR_LABELS_NL
    out: list[dict[str, object]] = []
    for r in rows:
        if not isinstance(r, Mapping):
            continue
        factor = str(r.get("factor") or "")
        ik = r.get("i18n_key")
        raw_note = str(r.get("note") or "")
        factor_display = (
            factors.get(factor)
            or (factors.get(str(ik)) if isinstance(ik, str) else None)
            or (_smart_title_factor(factor) if factor else "")
        )
        if isinstance(ik, str) and ik in notes:
            note_display = notes[ik]
        else:
            note_display = raw_note
        out.append({**dict(r), "factor_display": factor_display, "note_display": note_display})
    return out
