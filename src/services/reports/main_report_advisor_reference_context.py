"""Advisor override and public-reference context for main report aggregation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping

from src.services.infrastructure.report_confidence import confidence_score_percent
from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)
from src.services.reports.advisor_override_context import (
    build_advisor_multiple_calibration,
    build_advisor_real_estate_treatment,
)
from src.services.reports.multi_year_ebitda_context import (
    build_advisor_historical_ebitda_weighting,
    resolve_historical_ebitda_weighting_mode,
)
from src.services.reports.protocol_adapter import _attr
from src.services.reports.report_benchmark_contracts import as_plain_mapping
from src.services.reports.report_reference_context import (
    ReportReferenceContext,
    build_report_reference_context,
)

JsonMap = dict[str, object]
JsonRows = list[JsonMap]
ValuationRequest = ValuationRequestProtocol
ValuationResponse = ValuationResponseProtocol


@dataclass(frozen=True)
class MainReportAdvisorReferenceContext:
    request_metadata: JsonMap
    advisor_multiple_calibration: JsonMap | None
    raw_weighting_mode: str
    advisor_historical_ebitda_weighting: JsonMap | None
    advisor_real_estate_treatment: JsonMap | None
    report_reference: ReportReferenceContext
    confidence_score_pct: Decimal | None


def build_main_report_advisor_reference_context(
    *,
    response: ValuationResponse,
    request: ValuationRequest | None,
    request_metadata: Mapping[str, object] | None,
    applied_multiple: Decimal,
    multi_year_data: JsonRows,
    step_data: Mapping[str, object],
    locale: str,
    report_locale: str,
) -> MainReportAdvisorReferenceContext:
    """Build advisor-specific overrides plus public report reference values."""
    metadata = dict(request_metadata or {})
    response_multiples_results = as_plain_mapping(_attr(response, "multiples_results", None)) or {}
    effective_multiple_override_audit = as_plain_mapping(
        response_multiples_results.get("effective_multiple_override")
    )

    raw_confidence_score = step_data.get("overall_confidence_score")
    if raw_confidence_score is None:
        raw_confidence_score = _attr(response, "confidence_score", None)

    return MainReportAdvisorReferenceContext(
        request_metadata=metadata,
        advisor_multiple_calibration=build_advisor_multiple_calibration(
            request=request,
            request_metadata=metadata,
            applied_multiple=applied_multiple,
            effective_multiple_override_audit=effective_multiple_override_audit,
        ),
        raw_weighting_mode=resolve_historical_ebitda_weighting_mode(
            request,
            metadata,
        ),
        advisor_historical_ebitda_weighting=build_advisor_historical_ebitda_weighting(
            request=request,
            request_metadata=metadata,
            multi_year_data=multi_year_data,
        ),
        advisor_real_estate_treatment=build_advisor_real_estate_treatment(
            request=request,
            request_metadata=metadata,
        ),
        report_reference=build_report_reference_context(
            response=response,
            request_metadata=metadata,
            locale=locale,
            report_locale=report_locale,
        ),
        confidence_score_pct=confidence_score_percent(raw_confidence_score),
    )
