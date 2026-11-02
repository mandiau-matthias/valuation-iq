"""Public report reference and validity-window context."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Mapping, Optional

from src.services.defensibility.reference_formatter import format_valuation_reference
from src.services.reports.discussion_phase_signoff import build_discussion_signoff_line
from src.services.reports.report_bridge_helpers import format_date_localized


@dataclass(frozen=True)
class ReportReferenceContext:
    report_id: str
    report_id_display: str
    discussion_signoff_line: Optional[str]
    valuation_date: str
    valuation_expiry_date: str


def build_report_reference_context(
    *,
    response: object,
    request_metadata: Mapping[str, object] | None,
    locale: str,
    report_locale: str,
) -> ReportReferenceContext:
    """Build the canonical public report reference context.

    The aggregator, PDF renderers, and safety-net paths should all inherit
    these values instead of rebuilding their own report-code and validity
    rules. Template-level formatting remains a last-line defensive fallback.
    """
    valuation_date = getattr(response, "valuation_date", None)
    report_id = str(
        getattr(response, "valuation_id", None) or f"VAL-{datetime.now().strftime('%Y%m%d')}"
    )
    report_code = _report_code_from_metadata(request_metadata)
    report_id_display = (
        report_code or format_valuation_reference(report_id, valuation_date) or report_id
    )
    valuation_day = _parse_valuation_date(valuation_date) or datetime.now().date()

    return ReportReferenceContext(
        report_id=report_id,
        report_id_display=report_id_display,
        discussion_signoff_line=build_discussion_signoff_line(request_metadata, report_locale),
        valuation_date=format_date_localized(valuation_date, locale),
        valuation_expiry_date=format_date_localized(
            valuation_day + timedelta(days=90),
            locale,
        ),
    )


def _report_code_from_metadata(metadata: Mapping[str, object] | None) -> Optional[str]:
    if not metadata:
        return None
    report_code = metadata.get("report_code")
    if isinstance(report_code, str) and report_code.strip():
        return report_code.strip()
    return None


def _parse_valuation_date(value: object) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            return None
