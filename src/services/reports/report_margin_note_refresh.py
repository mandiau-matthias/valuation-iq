"""Refresh derived margin prose from saved financial evidence during report recovery."""

from __future__ import annotations

from collections.abc import Mapping
from types import SimpleNamespace

from src.services.infrastructure.translations import get_translations
from src.services.reports.report_audience_context import _margin_deviation_note


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def refresh_report_margin_notes(
    context: dict[str, object], valuation_data: Mapping[str, object], *, locale: str
) -> None:
    """Replace cached prose only; never modify saved financial values or valuation outputs."""
    details = _mapping(valuation_data.get("details"))
    current = next(
        (
            row
            for source in (valuation_data, details, context)
            if (row := _mapping(source.get("current_year_data")))
        ),
        {},
    )
    metadata = _mapping(current.get("ebitda_normalization_metadata"))
    reported = current.get("reported_ebitda")
    if reported is None:
        reported = metadata.get("reported_ebitda")
    # A normalized value alone cannot substantiate a reported-margin claim.
    has_normalization_evidence = (
        current.get("ebitda_normalized")
        or current.get("normalized_ebitda") is not None
        or bool(metadata)
    )
    if reported is None and not has_normalization_evidence:
        reported = current.get("ebitda")
    typical = next(
        (
            value
            for source in (valuation_data, details, context)
            if (value := _mapping(source.get("industry_benchmarks")).get("typical_ebitda_margin"))
            is not None
        ),
        context.get("benchmark_ebitda_margin"),
    )
    request = SimpleNamespace(
        current_year_data=SimpleNamespace(
            revenue=current.get("revenue"), reported_ebitda=reported, ebitda=reported
        ),
        industry_benchmarks={"typical_ebitda_margin": typical},
    )
    translations = get_translations(locale)
    for audience in ("advisor", "seller"):
        context[f"{audience}_margin_diligence_note"] = _margin_deviation_note(
            request, translations, audience=audience
        )
