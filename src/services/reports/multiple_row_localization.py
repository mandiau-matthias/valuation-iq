"""Presentation captions for generated multiple rows; preserve reconciliation labels."""

from src.services.infrastructure.translations import normalize_report_locale

_CAPTIONS = {
    "Reference multiple": ("Referentiemultiple", "Multiple de référence"),
    "Applied multiple": ("Toegepaste multiple", "Multiple appliqué"),
    "Upswitch model multiple": ("Upswitch-modelmultiple", "Multiple du modèle Upswitch"),
    "Advisor-adjusted multiple": (
        "Door adviseur aangepaste multiple",
        "Multiple ajusté par le conseiller",
    ),
    "Effective multiple (after discounts)": (
        "Effectieve multiple (na kortingen)",
        "Multiple effectif (après décotes)",
    ),
}


def localize_multiple_rows(rows: list[object], locale: str) -> list[object]:
    """Translate known generated captions; retain advisor notes and source values."""
    language = normalize_report_locale(locale)
    result = []
    for row in rows:
        if not isinstance(row, dict):
            result.append(row)
            continue
        label = row.get("label")
        translations = _CAPTIONS.get(label) if isinstance(label, str) else None
        display_label = (
            translations[0 if language == "nl" else 1]
            if translations and language in {"nl", "fr"}
            else label
        )
        result.append({**row, "display_label": display_label})
    return result
