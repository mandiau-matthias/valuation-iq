"""Flat official-financials fields for main report template contexts."""

from __future__ import annotations

from collections.abc import Mapping

from src.services.reports.official_variance_context import (
    build_official_variance_comparison_rows,
    official_revenue_is_comparable,
    official_trust_match_eligible,
)
from src.utils.decimal_helpers import safe_float

JsonMap = dict[str, object]


def _float_or_none(value: object) -> float | None:
    return safe_float(value) if value is not None else None


def _mapping_or_none(value: object) -> Mapping[str, object] | None:
    return value if isinstance(value, Mapping) else None


def build_main_report_official_financials_flat_context(
    *,
    official_financials: Mapping[str, object],
    user_revenue: object,
    user_reported_ebitda: object,
    translations: object,
) -> JsonMap:
    """Flatten official-filing context into the report template key contract."""
    variance_analysis = _mapping_or_none(official_financials.get("variance_analysis"))
    verification_badge = _mapping_or_none(official_financials.get("verification_badge"))

    return {
        "has_official_financials": official_financials.get("has_official_financials", False),
        "official_source": official_financials.get("source"),
        "official_source_label": official_financials.get("source_label"),
        "official_filing_year": official_financials.get("filing_year"),
        "official_revenue": _float_or_none(official_financials.get("revenue")),
        "official_revenue_source": official_financials.get("revenue_source"),
        "official_revenue_comparable": official_revenue_is_comparable(official_financials),
        "official_ebitda": _float_or_none(official_financials.get("ebitda")),
        "official_total_assets": _float_or_none(official_financials.get("total_assets")),
        "official_equity": _float_or_none(official_financials.get("equity")),
        "official_pdf_url": official_financials.get("pdf_url"),
        "official_source_links": official_financials.get("source_links", []),
        "official_data_health": official_financials.get("data_health"),
        "official_historical_years": official_financials.get("historical_years"),
        "official_valuation_input_years": official_financials.get("valuation_input_years"),
        "official_excluded_valuation_years": official_financials.get("excluded_valuation_years"),
        "official_valuation_input_status": official_financials.get("valuation_input_status"),
        "official_variance_analysis": variance_analysis,
        "official_variance_state": (
            variance_analysis.get("state") if variance_analysis is not None else None
        ),
        "official_requires_explanation": bool(
            variance_analysis.get("explanationRequired") if variance_analysis else False
        ),
        "official_variance_explanation": (
            variance_analysis.get("explanation") if variance_analysis is not None else None
        ),
        "official_verification_badge": verification_badge,
        "official_verification_state": (
            verification_badge.get("state") if verification_badge is not None else None
        ),
        "official_verification_label": (
            verification_badge.get("label") if verification_badge is not None else None
        ),
        "official_variance_comparison_rows": build_official_variance_comparison_rows(
            official_financials,
            _float_or_none(user_revenue),
            _float_or_none(user_reported_ebitda),
            translations,
        ),
        "official_variance_severity": (
            variance_analysis.get("severity") if variance_analysis is not None else None
        ),
        "official_trust_match_eligible": official_trust_match_eligible(official_financials),
    }
