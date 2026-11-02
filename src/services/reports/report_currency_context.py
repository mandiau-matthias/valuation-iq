"""Currency helpers for report cover-page context."""

from __future__ import annotations


def resolve_cover_statutory_currency(country_code: str | None) -> str:
    """Return the statutory currency for the cover-page disclosure."""
    if not country_code or not isinstance(country_code, str):
        return "EUR"
    code = country_code.strip().upper()
    if code == "UK":
        code = "GB"

    try:
        from src.services.country_data_service import get_country_data_service

        live = get_country_data_service().get_currency_code(code)
        if live:
            return live
    except Exception:
        pass

    try:
        from src.config.countries import currency_for_country

        return currency_for_country(code) or "EUR"
    except Exception:
        return "EUR"
