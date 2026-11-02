"""
DCF Section Builder.

Extracts DCF-specific valuation data from a response and returns the template
context fragment for the DCF page of the report.
"""

from decimal import Decimal
from typing import Optional, Protocol, cast

from src.api.schemas.stateless_api import MethodResult
from src.services.infrastructure.report_sections.dcf_context_assembly import assemble_dcf_context
from src.services.infrastructure.report_sections.dcf_context_support import JsonMap, attr
from src.services.infrastructure.report_sections.dcf_context_support import (
    detect_flat_projections as _detect_flat_projections,
)
from src.services.infrastructure.report_sections.dcf_readiness import (
    DcfReadinessContext,
    build_dcf_readiness_context,
    parse_optional_decimal,
)
from src.services.infrastructure.report_sections.dcf_reconciliation import reconcile_dcf_display
from src.services.infrastructure.translations import (
    ReportTranslations,
    get_translations,
    normalize_report_locale,
)


class DcfResponseShape(Protocol):
    dcf_valuation: object


def build_dcf_context(
    response: object,
    locale: str = "nl",
    t: Optional[ReportTranslations] = None,
    country_code: str = "BE",
) -> JsonMap:
    """Build template context for the DCF page.

    Returns ``{"has_dcf": False}`` when DCF data is absent so callers can
    skip the DCF page entirely.
    """
    if not hasattr(response, "dcf_valuation") or not response.dcf_valuation:
        return {"has_dcf": False}

    translations = t or get_translations(
        normalize_report_locale(locale),
        country_code=str(country_code or "BE").strip().upper() or "BE",
    )
    dcf = cast(DcfResponseShape, response).dcf_valuation
    readiness = build_dcf_readiness_context(
        attr(dcf, "historical_fcf_readiness", None),
        translations,
    )
    dcf_equity_decimal = parse_optional_decimal(attr(dcf, "equity_value", 0))
    dcf_wacc_decimal = parse_optional_decimal(attr(dcf, "wacc", None))
    display = reconcile_dcf_display(
        response=response,
        dcf=dcf,
        dcf_wacc_decimal=dcf_wacc_decimal,
    )

    return assemble_dcf_context(
        dcf=dcf,
        dcf_method=_dcf_method(
            readiness=readiness,
            dcf_equity_decimal=dcf_equity_decimal,
            dcf_wacc_decimal=dcf_wacc_decimal,
        ),
        display=display,
        readiness=readiness,
        audit_trail=attr(dcf, "dcf_audit_trail", None),
        projection_detail=attr(dcf, "fcf_projection_detail", None),
    )


def _dcf_method(
    *,
    readiness: DcfReadinessContext,
    dcf_equity_decimal: Decimal | None,
    dcf_wacc_decimal: Decimal | None,
) -> MethodResult:
    confidence_by_readiness = {
        "imported_ready": "high",
        "explicit_fcff_forecast": "high",
        "partial": "medium",
        "manual_fallback": "low",
    }
    return MethodResult(
        method_key="dcf",
        label="Discounted Cash Flow (DCF)",
        value=dcf_equity_decimal,
        wacc=dcf_wacc_decimal,
        available=True,
        confidence=confidence_by_readiness.get(str(readiness.status or "")),
    )
