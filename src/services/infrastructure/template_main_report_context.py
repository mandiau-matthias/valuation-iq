"""Shared context preparation for main-report template rendering."""

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Dict

from src.services.infrastructure.report_config import get_report_config
from src.services.reports.indicative_report_presentation import prepare_indicative_presentation
from src.services.infrastructure.translations import get_translations, normalize_report_locale


def prepare_main_report_context(
    context: Dict[str, Any],
    locale: str,
    *,
    convert_dates: Callable[[Any], Any],
    force_reference_format: bool,
) -> Dict[str, Any]:
    """Return an isolated render context with template defaults injected."""
    prepared = dict(context)
    prepared = convert_dates(prepared)

    prepared["generation_timestamp"] = datetime.now(timezone.utc).isoformat()

    config = get_report_config()
    prepared["config"] = config.to_dict()

    normalized_locale = normalize_report_locale(locale)
    country_code = str(prepared.get("country_code") or "").strip().upper()
    prepared["country_code"] = country_code
    prepared["t"] = get_translations(normalized_locale, country_code=country_code)
    prepared["locale"] = normalized_locale
    # Cached aggregation labels may have been produced in a different locale.
    # Translate recognized qualitative bands, preserving the underlying scores.
    quality_bands = {
        "hoog": "high", "high": "high", "élevé": "high",
        "gemiddeld": "medium", "medium": "medium", "moyen": "medium",
        "laag": "low", "low": "low", "faible": "low",
    }
    for key in ("quality_level", "data_quality_level"):
        band = quality_bands.get(str(prepared.get(key) or "").strip().lower())
        if band:
            prepared[key] = getattr(prepared["t"], f"data_quality_band_{band}")

    if force_reference_format or not prepared.get("report_id_display"):
        try:
            from src.services.defensibility.reference_formatter import format_valuation_reference

            candidate = prepared.get("report_id_display") or prepared.get("report_id")
            display_ref = format_valuation_reference(
                candidate,
                prepared.get("valuation_date"),
            )
            if display_ref:
                prepared["report_id_display"] = display_ref
        except Exception:
            pass

    return prepare_indicative_presentation(prepared, locale=normalized_locale)
