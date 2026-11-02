"""BET-293 — consolidation report context (cover sub-line + section flags).

Turns a ``consolidate_holdings`` result into the report-surface context: the
cover sub-line ("Geconsolideerd · 12 entiteiten · pro rata · intercompany
geëlimineerd") and the flags the Jinja templates branch on. Pure — mirrors
``attestation_context`` — so it unit-tests without the engine, and it satisfies
the BET-293 acceptance "report cover updates with consolidation sub-line".

Localised NL / EN / FR (FR pairs with the BET-291 French report output).
"""

from __future__ import annotations

from collections.abc import Mapping

_LABELS: dict[str, dict[str, str]] = {
    "nl": {
        "consolidated": "Geconsolideerd",
        "entities": "entiteiten",
        "pro_rata": "pro rata",
        "full": "volledige consolidatie",
        "intercompany": "intercompany geëlimineerd",
        "standalone": "Dit rapport waardeert één vennootschap. De groep kon nog niet worden gewaardeerd omdat vennootschapsrapporten of beslissingen van de adviseur ontbreken.",
    },
    "en": {
        "consolidated": "Consolidated",
        "entities": "entities",
        "pro_rata": "pro-rata",
        "full": "full consolidation",
        "intercompany": "intercompany eliminated",
        "standalone": "This report values one company. The group could not yet be valued because company reports or adviser decisions are incomplete.",
    },
    "fr": {
        "consolidated": "Consolidé",
        "entities": "entités",
        "pro_rata": "au prorata",
        "full": "consolidation intégrale",
        "intercompany": "flux intra-groupe éliminés",
        "standalone": "Ce rapport valorise une seule société. Le groupe n’a pas encore pu être valorisé car des rapports de sociétés ou des décisions du conseiller manquent.",
    },
}


def _label_locale(locale: object) -> str:
    raw = str(locale or "").strip().lower()
    if raw.startswith("fr"):
        return "fr"
    if raw.startswith("en"):
        return "en"
    return "nl"


def build_consolidation_report_context(
    consolidation: Mapping[str, object],
    *,
    locale: str = "nl",
) -> dict[str, object]:
    """Build the cover/section context from a ``consolidate_holdings`` result.

    Returns ``show_consolidation: False`` (and a null sub-line) for a standalone
    entity — no subsidiaries — so templates render nothing extra. Otherwise the
    sub-line names the entity count (parent + subsidiaries), the consolidation
    mode, and whether intercompany flows were eliminated.
    """
    c = consolidation if isinstance(consolidation, Mapping) else {}
    raw_count = c.get("subsidiary_count")
    subsidiary_count = raw_count if isinstance(raw_count, int) and raw_count > 0 else 0

    sotp = c.get("sotp")
    holding_sotp = dict(sotp) if isinstance(sotp, Mapping) else None
    has_holding_sotp = bool(holding_sotp and holding_sotp.get("available") is True)

    if subsidiary_count == 0:
        fallback = c.get("fallback_disclosure")
        fallback = dict(fallback) if isinstance(fallback, Mapping) else None
        show_fallback = bool(
            fallback and fallback.get("message_key") == "group_valuation_inputs_incomplete"
        )
        return {
            "show_consolidation": False,
            "cover_sub_line": None,
            "entity_count": 0,
            "subsidiary_count": 0,
            "mode": None,
            "intercompany_eliminated": False,
            "holdings_consolidation": dict(c) if c else None,
            "holding_sotp": holding_sotp,
            "has_holding_sotp_page": False,
            "is_holding_sotp_report": False,
            "show_holdings_fallback": show_fallback,
            "holdings_fallback_message": (
                _LABELS[_label_locale(locale)]["standalone"] if show_fallback else None
            ),
            "holdings_fallback_advisor_reason": (
                (fallback or {}).get("advisor_reason_code") if show_fallback else None
            ),
        }

    mode = "full" if str(c.get("mode")).strip().lower() == "full" else "pro_rata"
    intercompany_eliminated = bool(c.get("eliminations"))
    entity_count = subsidiary_count + 1  # parent + subsidiaries

    labels = _LABELS[_label_locale(locale)]
    parts = [
        labels["consolidated"],
        f"{entity_count} {labels['entities']}",
        labels[mode],
    ]
    if intercompany_eliminated:
        parts.append(labels["intercompany"])

    return {
        "show_consolidation": True,
        "cover_sub_line": " · ".join(parts),
        "entity_count": entity_count,
        "subsidiary_count": subsidiary_count,
        "mode": mode,
        "intercompany_eliminated": intercompany_eliminated,
        # The true-SOTP schedule is already part of the immutable ValuationRun
        # response snapshot. Surface that exact object to both report trees;
        # templates must never reconstruct entity values or bridge arithmetic.
        "holdings_consolidation": dict(c),
        "holding_sotp": holding_sotp,
        "has_holding_sotp_page": has_holding_sotp,
        "is_holding_sotp_report": has_holding_sotp,
        "show_holdings_fallback": False,
        "holdings_fallback_message": None,
        "holdings_fallback_advisor_reason": None,
    }
