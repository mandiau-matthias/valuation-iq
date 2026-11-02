"""Quality-warning localization policy for report payloads.

The large ``translations`` catalog still owns the actual report copy. This
module owns the warning-code catalogs and mapping logic so warning policy can
be tested and evolved without editing the monolithic translation data file.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from src.services.infrastructure.report_locale import normalize_report_locale

QUALITY_WARNING_TRANSLATIONS: dict[str, tuple[str, str]] = {
    "MISSING_REVENUE": (
        "Omzetgegevens ontbreken of zijn ongeldig",
        "Revenue data is missing or invalid",
    ),
    "MISSING_EBITDA": (
        "EBITDA-gegevens ontbreken",
        "EBITDA data is missing",
    ),
    "INSUFFICIENT_HISTORICAL": (
        "Slechts {count} jaar historische data (3+ aanbevolen voor DCF)",
        "Only {count} year(s) of historical data (3+ recommended for DCF)",
    ),
    "NO_HISTORICAL_DATA": (
        "Geen historische data beschikbaar",
        "No historical data available",
    ),
    "INCOMPLETE_BALANCE_SHEET": (
        "Balansgegevens zijn onvolledig",
        "Balance sheet data is incomplete",
    ),
    "INVALID_REVENUE_RANGE": (
        "Omzet valt buiten het geldige bereik",
        "Revenue is outside valid range",
    ),
    "INVALID_REVENUE_TYPE": (
        "Omzet is geen geldig getal",
        "Revenue is not a valid number",
    ),
    "UNREALISTIC_EBITDA": (
        "EBITDA overschrijdt omzet (wiskundig onmogelijk)",
        "EBITDA exceeds revenue (mathematically impossible)",
    ),
    "EXTREME_MARGIN": (
        "EBITDA-marge van {margin}% is extreem",
        "EBITDA margin of {margin}% is extreme",
    ),
    "MARGIN_OUTSIDE_BENCHMARK": (
        "EBITDA-marge van {margin}% valt buiten het typische sectorbereik ({min}% tot {max}%)",
        "EBITDA margin of {margin}% is outside typical industry range ({min}% to {max}%)",
    ),
    "MARGIN_DEVIATION": (
        "EBITDA-marge van {margin}% wijkt af van sectorgemiddelde ({typical}%)",
        "EBITDA margin of {margin}% deviates from industry average ({typical}%)",
    ),
    "EXTREME_GROWTH_RATE": (
        "Groeipercentage van {growth}% is extreem",
        "Growth rate of {growth}% is extreme",
    ),
    "QUALITY_DEGRADATION": (
        "Datakwaliteit met {degradation} punten gedaald sinds eerste beoordeling",
        "Data quality degraded by {degradation} points since initial assessment",
    ),
    "MULTI_YEAR_DATA_NOT_AVAILABLE": (
        "Meerjarige data niet beschikbaar",
        "Multi-year data not available",
    ),
    "LIMITED_HISTORICAL_DATA": (
        "Minder dan 2 jaar historische data beschikbaar",
        "Less than 2 years of historical data available",
    ),
}


TYPED_WARNING_TO_TRANSLATION_KEYS: dict[str, tuple[str, str]] = {
    "indicative_dcf_forecast": (
        "warning_indicative_dcf_message",
        "warning_indicative_dcf_recommendation",
    ),
    "thin_comparables_proxy": (
        "warning_thin_comparables_proxy_message",
        "warning_thin_comparables_proxy_recommendation",
    ),
    "owner_concentration_skipped_missing_inputs": (
        "warning_owner_concentration_skip_message",
        "warning_owner_concentration_skip_recommendation",
    ),
    "ebitda_divergence": (
        "warning_ebitda_divergence_message",
        "warning_ebitda_divergence_recommendation",
    ),
    "method_substitution": (
        "warning_method_substitution_message",
        "warning_method_substitution_recommendation",
    ),
    "net_debt_unavailable": (
        "warning_net_debt_unavailable_message",
        "warning_net_debt_unavailable_recommendation",
    ),
    "owner_compensation_estimated": (
        "warning_owner_comp_estimated_message",
        "warning_owner_comp_estimated_recommendation",
    ),
    "ebitda_benchmark_deviation": (
        "warning_ebitda_benchmark_deviation_message",
        "warning_ebitda_benchmark_deviation_recommendation",
    ),
    "book_equity_unavailable": (
        "warning_book_equity_unavailable_message",
        "warning_book_equity_unavailable_recommendation",
    ),
    "impossible_margin": (
        "warning_impossible_margin_message",
        "warning_impossible_margin_recommendation",
    ),
}

# Compatibility name for legacy imports from ``translations``.
_TYPED_WARNING_TO_TRANSLATION_KEYS = TYPED_WARNING_TO_TRANSLATION_KEYS

_QUALITY_WARNING_PLACEHOLDERS = (
    "{count}",
    "{margin}",
    "{min}",
    "{max}",
    "{typical}",
    "{growth}",
    "{degradation}",
)
_TEMPLATE_PLACEHOLDER_RE = re.compile(r"\{[a-z_]+\}")
_NUMBER_RE = re.compile(r"-?\d+\.?\d*")
_COUNT_RE = re.compile(r"Only (\d+) years?", re.I)
_PERCENT_RE = re.compile(r"([-\d.]+)%")
_DEGRADATION_RE = re.compile(r"degraded by (\d+)", re.I)


def localize_typed_data_quality_warnings(
    warnings: Sequence[object] | None,
    translations: object,
) -> list[object]:
    """Apply typed warning translation keys with an already-resolved bundle."""

    if not warnings:
        return []
    out: list[object] = []
    for warning in warnings:
        if not isinstance(warning, dict):
            out.append(warning)
            continue
        entry = dict(warning)
        warning_type = entry.get("type")
        attrs = (
            TYPED_WARNING_TO_TRANSLATION_KEYS.get(warning_type)
            if isinstance(warning_type, str)
            else None
        )
        if attrs:
            msg_attr, rec_attr = attrs
            msg = getattr(translations, msg_attr, None)
            rec = getattr(translations, rec_attr, None)
            if msg:
                entry["message"] = msg
            if rec:
                entry["recommendation"] = rec
        out.append(entry)
    return out


def _warning_template_for_message(original: str) -> tuple[str, str] | None:
    original_text = original.strip().lower()
    for catalog_template in QUALITY_WARNING_TRANSLATIONS.values():
        _nl, english_template = catalog_template
        if _english_template_matches(english_template, original_text):
            return catalog_template
    return None


def _english_template_matches(english_template: str, original_text: str) -> bool:
    en_pattern = _TEMPLATE_PLACEHOLDER_RE.sub("", english_template).strip().lower()
    if en_pattern and en_pattern == original_text:
        return True

    if "{" not in english_template:
        return False
    regex = re.escape(english_template)
    regex = re.sub(r"\\\{[a-z_]+\\\}", r".+?", regex)
    regex = regex.replace(r"year\(s\)", r"years?")
    return bool(re.fullmatch(regex, original_text, flags=re.I))


def _warning_template_for(
    *,
    code: str,
    original: str,
) -> tuple[str, str] | None:
    return QUALITY_WARNING_TRANSLATIONS.get(code) or _warning_template_for_message(original)


def _localized_warning_message(
    *,
    template: tuple[str, str],
    locale: str | None,
) -> str:
    msg_nl, msg_en = template
    return msg_nl if normalize_report_locale(locale) == "nl" else msg_en


def _replace_if_present(message: str, placeholder: str, value: str | None) -> str:
    if placeholder in message and value:
        return message.replace(placeholder, value)
    return message


def _interpolate_count(message: str, original: str) -> str:
    match = _COUNT_RE.search(original)
    return message.replace("{count}", match.group(1) if match else "1")


def _interpolate_numeric_warning(message: str, original: str) -> str:
    nums = _NUMBER_RE.findall(original)
    if not nums:
        return message
    message = _replace_if_present(message, "{margin}", nums[0])
    if len(nums) >= 2:
        message = _replace_if_present(message, "{min}", nums[-2])
        message = _replace_if_present(message, "{max}", nums[-1])
    typical = nums[-1] if len(nums) > 1 else nums[0]
    return _replace_if_present(message, "{typical}", typical)


def _interpolate_single_match(
    message: str,
    *,
    placeholder: str,
    pattern: re.Pattern[str],
    original: str,
) -> str:
    match = pattern.search(original)
    return _replace_if_present(message, placeholder, match.group(1) if match else None)


def _interpolate_warning_message(message: str, *, code: str, original: str) -> str:
    if "{count}" in message:
        return _interpolate_count(message, original)
    if any(token in message for token in ("{margin}", "{min}", "{max}", "{typical}")):
        return _interpolate_numeric_warning(message, original)
    if "{growth}" in message:
        return _interpolate_single_match(
            message,
            placeholder="{growth}",
            pattern=_PERCENT_RE,
            original=original,
        )
    if "{degradation}" in message:
        return _interpolate_single_match(
            message,
            placeholder="{degradation}",
            pattern=_DEGRADATION_RE,
            original=original,
        )
    return message


def _replace_unresolved_placeholders(message: str) -> str:
    for placeholder in _QUALITY_WARNING_PLACEHOLDERS:
        message = message.replace(placeholder, "—")
    return message


def translate_quality_warning(
    warning: Mapping[str, object],
    locale: str | None = "nl",
) -> dict[str, object]:
    """Translate a quality warning message based on its code."""

    code = str(warning.get("code", ""))
    original = str(warning.get("message", str(warning)))
    template = _warning_template_for(code=code, original=original)
    if not template:
        return {**dict(warning), "message": original}

    msg = _localized_warning_message(template=template, locale=locale)
    try:
        msg = _interpolate_warning_message(msg, code=code, original=original)
    except Exception:
        pass

    return {**dict(warning), "message": _replace_unresolved_placeholders(msg)}
