"""Localize standard bridge captions without changing saved financial evidence."""

from __future__ import annotations

from collections.abc import Mapping

# Exact generated captions only: advisor-entered explanations remain verbatim.
_CAPTIONS = {
    "Enterprise value": ("Ondernemingswaarde", "Valeur d’entreprise"),
    "Equity value": ("Aandelenwaarde", "Valeur des capitaux propres"),
    "Net cash": ("Nettokaspositie", "Trésorerie nette"),
    "Net debt": ("Nettoschuld", "Dette nette"),
    "Tax latencies": ("Belastinglatenties", "Impôts latents"),
    "Normalised working capital": (
        "Genormaliseerd werkkapitaal",
        "Besoin en fonds de roulement normalisé",
    ),
    "Reconciliation item": ("Aansluitingspost", "Poste de rapprochement"),
    "Balance adjustment": ("Balanscorrectie", "Ajustement du bilan"),
    "Adjustment": ("Correctie", "Ajustement"),
    "NWC normalization and surplus assets not assessed - no balance sheet.": (
        "Normalisatie van werkkapitaal en overtollige activa niet beoordeeld: geen balans beschikbaar.",
        "La normalisation du besoin en fonds de roulement et les actifs excédentaires n’ont pas été évalués : aucun bilan disponible.",
    ),
    "No EV-to-equity adjustment was required by the available balance data.": (
        "De beschikbare balansgegevens vereisten geen correctie van ondernemingswaarde naar aandelenwaarde.",
        "Les données du bilan disponibles ne nécessitaient aucun ajustement entre la valeur d’entreprise et celle des capitaux propres.",
    ),
    "NWC normalization not assessed separately in the supplied balance data.": (
        "De normalisatie van het werkkapitaal is niet afzonderlijk beoordeeld in de aangeleverde balansgegevens.",
        "La normalisation du besoin en fonds de roulement n’a pas été évaluée séparément dans les données du bilan fournies.",
    ),
}


def localize_equity_bridge(bridge: Mapping[str, object], locale: str) -> dict[str, object]:
    """Return a presentation copy; keep amounts, operators and custom text unchanged."""
    language = str(locale or "nl").lower().replace("_", "-").split("-", 1)[0]

    def caption(value: object) -> object:
        if not isinstance(value, str) or language not in {"nl", "fr"}:
            return value
        translated = _CAPTIONS.get(value)
        return translated[0 if language == "nl" else 1] if translated else value

    result = dict(bridge)
    rows = bridge.get("rows")
    if isinstance(rows, list):
        result["rows"] = [
            {**row, "label": caption(row.get("label"))} if isinstance(row, dict) else row
            for row in rows
        ]
    disclosures = bridge.get("disclosures")
    if isinstance(disclosures, list):
        result["disclosures"] = [caption(disclosure) for disclosure in disclosures]
    return result
