"""Locale and country helpers for report context builders."""

from __future__ import annotations

from src.services.infrastructure.translations import (
    ReportTranslations,
    get_translations,
    normalize_report_locale,
)


def country_code_from_request(request: object | None) -> str:
    """Return the firm/report country code used for country-specific copy."""

    raw_country = getattr(request, "country_code", None) if request is not None else None
    country_code = str(raw_country or "BE").strip().upper()
    return country_code or "BE"


def translations_or_fallback(
    locale: str,
    request: object | None,
    translations: ReportTranslations | None,
) -> ReportTranslations:
    """Return the provided translations or resolve them from locale + country."""

    if translations is not None:
        return translations
    return get_translations(
        normalize_report_locale(locale),
        country_code=country_code_from_request(request),
    )
