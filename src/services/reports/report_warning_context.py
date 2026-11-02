"""Quality-warning context builder for main report aggregation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from src.services.reports.report_quality_warnings import (
    extract_high_severity_warnings,
    extract_method_substitution_disclosure,
    format_high_severity_callout_lead,
    has_integrity_warnings,
    localize_warnings,
    translate_quality_warnings,
)

JsonMap = dict[str, object]


class ReportWarningTranslations(Protocol):
    high_severity_callout_lead_singular: str
    high_severity_callout_lead_plural: str


@dataclass(frozen=True)
class ReportWarningContext:
    high_severity_warnings: list[JsonMap]
    localized_high_severity_warnings: list[JsonMap]
    high_severity_callout_lead: str
    show_integrity_callout: bool
    method_substitution_disclosure: JsonMap | None
    translated_quality_warnings: list[JsonMap]


def build_report_warning_context(
    *,
    response: object | None,
    step_data: Mapping[str, object] | None,
    fiscal_integrity_warnings: Sequence[Mapping[str, object]] | None,
    locale: str,
    translations: ReportWarningTranslations,
) -> ReportWarningContext:
    """Build all report-quality warning fields from one source snapshot."""
    high_severity_warnings = extract_high_severity_warnings(
        response,
        step_data,
        fiscal_integrity_warnings,
    )
    localized_high_severity_warnings = localize_warnings(high_severity_warnings, translations)

    raw_quality_warnings = (step_data or {}).get("quality_warnings", [])
    quality_warnings = raw_quality_warnings if isinstance(raw_quality_warnings, list) else []

    return ReportWarningContext(
        high_severity_warnings=high_severity_warnings,
        localized_high_severity_warnings=localized_high_severity_warnings,
        high_severity_callout_lead=format_high_severity_callout_lead(
            translations,
            high_severity_warnings,
        ),
        show_integrity_callout=has_integrity_warnings(high_severity_warnings),
        method_substitution_disclosure=extract_method_substitution_disclosure(
            response,
            high_severity_warnings,
            locale,
        ),
        translated_quality_warnings=translate_quality_warnings(quality_warnings, locale),
    )
