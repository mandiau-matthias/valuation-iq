"""Fiscal-reference method-selection helpers for report builders."""

from typing import Optional

from src.domain.valuation_contract import method_key_matches, resolve_effective_method_key
from src.services.reports.report_metadata_access import get_request_metadata


def user_selected_fiscal_4x(request: object | None) -> bool:
    """Return True when a valuation request explicitly selects the fiscal 4x method."""
    if not request:
        return False

    metadata = get_request_metadata(request) or {}
    method_key = resolve_effective_method_key(
        getattr(request, "selected_method", None),
        metadata.get("selected_method"),
        metadata.get("selected_valuation_method"),
        getattr(request, "method_override_selected_method", None),
        metadata.get("method_override_selected_method"),
        getattr(request, "primary_method_key", None),
        metadata.get("primary_method_key"),
    )
    return bool(method_key_matches(method_key, "fiscal_4x"))
