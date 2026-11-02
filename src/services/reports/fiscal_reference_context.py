"""Fiscal-reference context preparation for report builders."""

from collections.abc import Callable
from decimal import Decimal
from typing import Optional, cast

from src.services.reports.fiscal_method_selection import user_selected_fiscal_4x
from src.services.reports.fiscal_year_data import latest_closed_fiscal_year_data
from src.services.reports.report_metadata_access import get_metadata_bool, get_request_metadata

LatestClosedFiscalYearResolver = Callable[[object | None], object]
CountryCodeResolver = Callable[[object | None], str]

FISCAL_INPUT_METADATA_KEY_MAP = {
    "acquisition_cost": "fiscal_acquisition_cost",
    "anchor_2_value": "fiscal_anchor_2_value",
    "anchor_3_value": "fiscal_anchor_3_value",
    "anchor_4_value": "fiscal_anchor_4_value",
}

HOLDING_NACE_PREFIXES = {"6420", "6430", "7010"}


def country_code_from_request(request: object | None) -> str:
    """Resolve the report country code from a valuation request."""
    country_code = (getattr(request, "country_code", None) or "BE") if request else "BE"
    return str(country_code).strip().upper() or "BE"


def should_show_fiscal_reference(request: object | None) -> bool:
    """Return True when metadata or selected method requests the fiscal annex."""
    return bool(get_metadata_bool(request, "show_fiscal_reference", False)) or bool(
        user_selected_fiscal_4x(request)
    )


def prepare_fiscal_reference_metadata(request: object | None) -> dict[str, object]:
    """Return metadata enriched with fiscal-annex values derived from request fields."""
    metadata = dict(get_request_metadata(request) or {})
    if request is None:
        return metadata

    _add_real_estate_carve_out_metadata(metadata, request)
    _add_fiscal_input_metadata(metadata, request)
    if "fiscal_company_role" not in metadata:
        role = _fiscal_company_role_from_request(request)
        if role is not None:
            metadata["fiscal_company_role"] = role
    return metadata


def _add_real_estate_carve_out_metadata(
    metadata: dict[str, object],
    request: object,
) -> None:
    if not bool(getattr(request, "exclude_real_estate", False) or False):
        return

    metadata.setdefault("real_estate_carve_out_applied", True)
    metadata.setdefault(
        "real_estate_book_value",
        getattr(request, "real_estate_book_value", None),
    )
    metadata.setdefault(
        "real_estate_market_rent",
        getattr(request, "estimated_market_rent", None),
    )


def _add_fiscal_input_metadata(metadata: dict[str, object], request: object) -> None:
    fiscal_inputs = getattr(request, "fiscal_inputs", None)
    if not isinstance(fiscal_inputs, dict):
        return

    for source_key, metadata_key in FISCAL_INPUT_METADATA_KEY_MAP.items():
        if source_key in fiscal_inputs and fiscal_inputs[source_key] is not None:
            metadata[metadata_key] = fiscal_inputs[source_key]


def _fiscal_company_role_from_request(request: object) -> str | None:
    nace_prefix = _nace_prefix_from_request(request)
    if not nace_prefix:
        return None
    return "holding" if nace_prefix in HOLDING_NACE_PREFIXES else "werkmaatschappij"


def _nace_prefix_from_request(request: object) -> str:
    nace_raw = str(getattr(request, "nace_code", "") or "") or str(
        getattr(request, "activity_code", "") or ""
    )
    return nace_raw.replace(".", "").replace(" ", "")[:4] if nace_raw else ""


def build_fiscal_reference_report_context(
    *,
    request: object | None,
    fiscal_ebitda: Decimal,
    fiscal_reported_ebitda: Optional[Decimal] = None,
    latest_closed_fiscal_year_resolver: LatestClosedFiscalYearResolver = latest_closed_fiscal_year_data,
    country_code_resolver: CountryCodeResolver = country_code_from_request,
) -> dict[str, object]:
    """Build the fiscal-reference template context through the canonical section builder."""
    from src.services.infrastructure.report_sections.fiscal_section import (
        build_fiscal_reference_context,
    )

    prepared_metadata = prepare_fiscal_reference_metadata(request)
    if fiscal_reported_ebitda is not None:
        prepared_metadata.setdefault("fiscal_ebitda_source", "annual_accounts")

    return cast(
        dict[str, object],
        build_fiscal_reference_context(
            show_fiscal_reference=should_show_fiscal_reference(request),
            country_code=country_code_resolver(request),
            fiscal_ebitda=fiscal_ebitda,
            closed_fiscal_year_data=latest_closed_fiscal_year_resolver(request),
            metadata=prepared_metadata,
            fiscal_reported_ebitda=fiscal_reported_ebitda,
        ),
    )
