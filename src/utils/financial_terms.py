"""
Amsterdam Dictionary — BE vs NL financial terminology (Ticket 4).

Maps Belgian (BE) vs Dutch (NL) administrative/financial terminology
for PDF reports. A Dutch user in the Netherlands should never see
Belgian-specific jargon.
"""

from __future__ import annotations

from src.services.infrastructure.translations import normalize_report_locale

TRIAL_BALANCE_TERM: dict[str, dict[str, str]] = {
    "BE": {"nl": "Proef- en saldibalans", "en": "Trial Balance", "fr": "Balance de vérification"},
    "NL": {"nl": "Kolommenbalans", "en": "Trial Balance", "fr": "Balance de vérification"},
}

MANUAL_INPUT_TERM: dict[str, str] = {
    "nl": "Manuele invoer",
    "en": "Manual input",
    "fr": "Saisie manuelle",
}

# Known accounting software integrations.  The source label should only
# include the provider name when data was actually imported from it.
KNOWN_SOURCES: dict[str, str] = {
    "yuki": "Yuki",
    "exact": "Exact Online",
    "octopus": "Octopus",
    "manual": "",
}


def _trial_balance_lang_key(locale: str | None) -> str:
    """Map BCP-47 tags to TRIAL_BALANCE_TERM keys (nl / en / fr)."""
    raw = str(locale or "").strip().lower()
    if raw.startswith("fr"):
        return "fr"
    if normalize_report_locale(locale) == "en":
        return "en"
    return "nl"


def get_trial_balance_label(
    country_code: str,
    locale: str,
    year: int,
    source: str | None = None,
) -> str:
    """Return locale- and country-aware trial balance source label.

    ``source`` should be the slug of the accounting provider that
    supplied the data (e.g. ``"yuki"``, ``"exact"``).  When *None* or
    ``"manual"``, only the generic trial-balance term is returned
    without a provider prefix.
    """
    cc = str(country_code or "BE").strip().upper() or "BE"
    code = "NL" if cc == "NL" else "BE"
    loc = _trial_balance_lang_key(locale)
    term = TRIAL_BALANCE_TERM.get(code, TRIAL_BALANCE_TERM["BE"]).get(loc, "Proef- en saldibalans")

    provider = KNOWN_SOURCES.get(source or "", "")
    if provider:
        return f"{provider} {term} {year}"
    return f"{term} {year}"


def get_manual_input_label(locale: str, year: int) -> str:
    """Return a localized source label for figures entered directly by a user."""
    loc = _trial_balance_lang_key(locale)
    term = MANUAL_INPUT_TERM.get(loc, MANUAL_INPUT_TERM["nl"])
    return f"{term} {year}"
