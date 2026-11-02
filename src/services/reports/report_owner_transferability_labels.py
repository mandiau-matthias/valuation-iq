"""Localization and citation helpers for owner transferability report context."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Optional, TypeAlias

StringMap: TypeAlias = dict[str, str]

# Locale-aware label helpers. The transferability module ships
# English fallbacks; these helpers prefer a `t.<key>` field when one
# is available so the report localises cleanly without forcing every
# locale to ship every label up front.
SUBFACTOR_T_KEYS: StringMap = {
    "planning_continuity": "owner_profiling_subfactor_planning_continuity",
    "relationship_transferability": "owner_profiling_subfactor_relationship_transferability",
    "operational_independence": "owner_profiling_subfactor_operational_independence",
    "knowledge_codification": "owner_profiling_subfactor_knowledge_codification",
    "brand_independence": "owner_profiling_subfactor_brand_independence",
}

BUYER_ARCHETYPE_T_KEYS: StringMap = {
    "individual_operator": "owner_profiling_buyer_archetype_individual_operator",
    "search_fund": "owner_profiling_buyer_archetype_search_fund",
    "pe_add_on": "owner_profiling_buyer_archetype_pe_add_on",
    "strategic": "owner_profiling_buyer_archetype_strategic",
    "family_office": "owner_profiling_buyer_archetype_family_office",
}

SME_SEGMENT_T_KEYS: StringMap = {
    "individual_operator": "owner_profiling_sme_segment_individual_operator",
    "search_fund": "owner_profiling_sme_segment_search_fund",
    "pe_add_on": "owner_profiling_sme_segment_pe_add_on",
    "strategic": "owner_profiling_sme_segment_strategic",
    "family_office": "owner_profiling_sme_segment_family_office",
}

BUYER_RATIONALE_T_KEYS: StringMap = {
    "individual_operator": "owner_profiling_buyer_rationale_individual_operator",
    "search_fund": "owner_profiling_buyer_rationale_search_fund",
    "pe_add_on": "owner_profiling_buyer_rationale_pe_add_on",
    "strategic": "owner_profiling_buyer_rationale_strategic",
    "family_office": "owner_profiling_buyer_rationale_family_office",
}

METHOD_LABEL_T_KEYS: StringMap = {
    "ebitda_multiple": "owner_profiling_method_label_ebitda_multiple",
    "dcf": "owner_profiling_method_label_dcf",
    "sde": "owner_profiling_method_label_sde",
    "revenue_multiple": "owner_profiling_method_label_revenue_multiple",
    "arr_multiple": "owner_profiling_method_label_arr_multiple",
    "adaptive": "owner_profiling_method_label_adaptive",
    "adjusted_nav": "owner_profiling_method_label_adjusted_nav",
    "fiscal_4x": "owner_profiling_method_label_fiscal_4x",
    "startup": "owner_profiling_method_label_startup",
}

METHOD_RATIONALE_T_KEYS: StringMap = {
    "ebitda_multiple": "owner_profiling_method_rationale_ebitda_multiple",
    "dcf": "owner_profiling_method_rationale_dcf",
    "sde": "owner_profiling_method_rationale_sde",
    "revenue_multiple": "owner_profiling_method_rationale_revenue_multiple",
    "arr_multiple": "owner_profiling_method_rationale_arr_multiple",
    "adaptive": "owner_profiling_method_rationale_adaptive",
    "adjusted_nav": "owner_profiling_method_rationale_adjusted_nav",
    "fiscal_4x": "owner_profiling_method_rationale_fiscal_4x",
    "startup": "owner_profiling_method_rationale_startup",
}

# Citation IDs surface in the per-method incidence table as
# superscript footnote markers (i, ii, iii, …) pointing into the
# methodology footnote. Tying coefficients to specific sources is
# what makes the academic backing load-bearing rather than
# decorative.
METHOD_CITATION_IDS: dict[str, list[str]] = {
    "ebitda_multiple": ["damodaran_2012", "pratt_2008"],
    "dcf": ["damodaran_2012"],
    "sde": ["sbvs"],
    "revenue_multiple": ["mercer_2001"],
    "arr_multiple": ["mercer_2001"],
    "adaptive": ["damodaran_2012", "pratt_2008"],
    "adjusted_nav": [],
    "fiscal_4x": [],
    "startup": [],
}

# Stable display IDs for citations so the footnote markers can use
# roman-numeral indices that match the footnote ordering.
CITATION_DISPLAY_INDEX: StringMap = {
    "damodaran_2012": "i",
    "pratt_2008": "ii",
    "pepperdine_pcmi": "iii",
    "eu_2003_361": "iv",
    "sbvs": "v",
    "mercer_2001": "vi",
    "pratt_severity": "vii",
}

# Map citation citation-string → ID so the aggregator can attach
# `id` to each citation row without changing the engine schema.
CITATION_ID_BY_PREFIX: tuple[tuple[str, str], ...] = (
    ("Damodaran, A. (2012)", "damodaran_2012"),
    ("Pratt, S., Reilly, R., Schweihs, R. (2008)", "pratt_2008"),
    ("Pepperdine", "pepperdine_pcmi"),
    ("EU Recommendation 2003/361", "eu_2003_361"),
    ("SBVS", "sbvs"),
    ("Mercer, Z.C. (2001)", "mercer_2001"),
    ("Pratt, Reilly & Schweihs (2008), §28.7", "pratt_severity"),
)

CASCADE_TEMPLATE_KEYS: StringMap = {
    "owner": "owner_profiling_cascade_owner_template",
    "buyer": "owner_profiling_cascade_buyer_template",
    "gap": "owner_profiling_cascade_gap_template",
    "applied": "owner_profiling_cascade_applied_template",
}

SEVERITY_T_KEYS: StringMap = {
    "minimal": "owner_profiling_severity_minimal",
    "moderate": "owner_profiling_severity_moderate",
    "severe": "owner_profiling_severity_severe",
    "extreme": "owner_profiling_severity_extreme",
}


def citation_id_for(citation_text: str) -> Optional[str]:
    for prefix, cid in CITATION_ID_BY_PREFIX:
        if citation_text.startswith(prefix):
            return cid
    return None


def localise_cascade(
    cascade_data: list[object],
    gap: Mapping[str, object],
    t: object,
) -> list[str]:
    """Format cascade lines in the active locale."""
    if not cascade_data:
        return []

    gap_severity = (gap.get("severity") if isinstance(gap, Mapping) else None) or "minimal"
    sev_t_key = SEVERITY_T_KEYS.get(str(gap_severity).lower())
    severity_localised = (getattr(t, sev_t_key, None) if sev_t_key else None) or str(
        gap_severity
    ).capitalize()

    out: list[str] = []
    for line in cascade_data:
        if not isinstance(line, Mapping):
            return []
        key = line.get("key")
        template_attr = CASCADE_TEMPLATE_KEYS.get(str(key))
        if not template_attr:
            return []
        template = getattr(t, template_attr, None)
        if not template:
            return []
        fields = dict(line.get("fields") or {})
        fields["severity_localised"] = severity_localised
        try:
            out.append(template.format(**fields))
        except (KeyError, IndexError, ValueError):
            return []
    return out


def localize_subfactor_label(key: Optional[str], fallback: Optional[str], t: object) -> str:
    if not key:
        return fallback or ""
    attr = SUBFACTOR_T_KEYS.get(key)
    if attr is not None:
        label = getattr(t, attr, None)
        if label:
            return label
    return fallback or key.replace("_", " ").title()


def localize_buyer_archetype(archetype: Optional[str], t: object) -> str:
    if not archetype:
        return ""
    attr = BUYER_ARCHETYPE_T_KEYS.get(archetype)
    if attr is not None:
        label = getattr(t, attr, None)
        if label:
            return label
    return archetype.replace("_", " ").title()


def localize_sme_segment(
    archetype: Optional[str],
    engine_fallback: Optional[str],
    t: object,
) -> str:
    """Localised EU SME segment label per archetype."""
    if not archetype:
        return engine_fallback or ""
    attr = SME_SEGMENT_T_KEYS.get(archetype)
    if attr is not None:
        label = getattr(t, attr, None)
        if label:
            return label
    return engine_fallback or ""


def localize_buyer_rationale(
    archetype: Optional[str],
    equity_eur: Optional[Decimal],
    t: object,
) -> Optional[str]:
    """Locale-aware buyer rationale sentence."""
    if not archetype:
        return None
    attr = BUYER_RATIONALE_T_KEYS.get(archetype)
    if attr is None:
        attr = "owner_profiling_buyer_rationale_unknown"
    template = getattr(t, attr, None)
    if not template:
        return None
    if equity_eur is None:
        eur_display = "—"
    else:
        try:
            eur_display = f"€{int(equity_eur):,}".replace(",", ".")
        except (TypeError, ValueError):
            eur_display = "—"
    try:
        return template.format(eur=eur_display)
    except (KeyError, IndexError, ValueError):
        return None


def infer_equity_from_rationale(rationale: Optional[str]) -> Optional[Decimal]:
    """Lift the EUR figure out of the engine's English rationale."""
    if not rationale:
        return None
    import re

    match = re.search(r"€\s*([\d\.]+)", rationale)
    if not match:
        return None
    try:
        return Decimal(match.group(1).replace(".", ""))
    except (InvalidOperation, ValueError):
        return None


def localize_gap_summary(gap: Mapping[str, object], t: object) -> Optional[str]:
    """Build the inline gap callout sentence in the active locale."""
    template = getattr(t, "owner_profiling_gap_summary_template", None)
    if not template or not isinstance(gap, Mapping):
        return None
    try:
        return template.format(**_gap_summary_values(gap, t))
    except (KeyError, IndexError, ValueError, TypeError):
        return None


def _gap_summary_values(gap: Mapping[str, object], t: object) -> dict[str, object]:
    return {
        "owner_hours": gap.get("owner_hours_per_week") or 60,
        "buyer_hours": gap.get("buyer_hours_per_week") or 0,
        "hours_gap": gap.get("hours_gap") or 0,
        "skill_gap": int(round(float(gap.get("skill_gap") or 0))),
        "severity_localised": _localized_gap_severity(gap, t),
        "raw_pct": format_pct(gap.get("raw_discount_pct")),
    }


def _localized_gap_severity(gap: Mapping[str, object], t: object) -> str:
    severity = str(gap.get("severity") or "minimal").lower()
    severity_key = SEVERITY_T_KEYS.get(severity)
    localized = getattr(t, severity_key, None) if severity_key else None
    return str(localized or severity.capitalize())


def format_pct(value: object) -> str:
    """`-0.32` → `-32.0%`. Defensive for non-numeric inputs."""
    try:
        return f"{float(Decimal(str(value or 0)) * Decimal('100')):+.1f}%"
    except (InvalidOperation, TypeError, ValueError, ArithmeticError):
        return "0.0%"
