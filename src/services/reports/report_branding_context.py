"""Accountant branding and report setting context builders."""

from typing import TypeAlias

from src.services.reports.color_context import build_color_context
from src.services.reports.report_currency_context import resolve_cover_statutory_currency
from src.services.reports.report_metadata_access import (
    get_accountant_logo,
    get_accountant_name,
    get_metadata_bool,
    get_metadata_str,
)

ReportMap: TypeAlias = dict[str, object]


def build_report_branding_context(
    *,
    request: object | None,
    country_code: str,
    preparer_ebitda_override_title: str | None,
    preparer_ebitda_override_footnote: str | None,
) -> ReportMap:
    """Build accountant branding, cover settings, and report disclaimers."""
    primary_color = get_metadata_str(request, "primary_color")
    return {
        "accountant_firm_name": get_accountant_name(request),
        "accountant_logo_url": get_accountant_logo(request),
        "accountant_email": get_metadata_str(request, "accountant_email"),
        "accountant_phone": get_metadata_str(request, "accountant_phone"),
        "show_cover_price": get_metadata_bool(request, "show_cover_price", True),
        "cover_statutory_currency": resolve_cover_statutory_currency(country_code),
        "valuation_goal": get_metadata_str(request, "valuation_goal"),
        "custom_disclaimer": get_metadata_str(request, "custom_disclaimer"),
        "preparer_ebitda_override_title": preparer_ebitda_override_title,
        "preparer_ebitda_override_footnote": preparer_ebitda_override_footnote,
        "primary_color": primary_color,
        **build_color_context(primary_color),
    }
