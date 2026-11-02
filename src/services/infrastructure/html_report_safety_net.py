"""Safety-net adapter for HTML report generation fallbacks."""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.services.infrastructure.safety_net_report import (
    build_safety_net_reports as build_shared_safety_net_reports,
)
from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)


def build_html_service_safety_net_reports(
    response: ValuationResponseProtocol,
    request: ValuationRequestProtocol,
    *,
    locale: str,
    reason: str,
    context: Dict[str, Optional[str]],
) -> Dict[str, Any]:
    """Build request-shaped safety-net HTML payloads for the HTML report service."""
    valuation_data: Dict[str, Any] = {
        "company_name": getattr(response, "company_name", None)
        or getattr(request, "company_name", None),
        "currency": getattr(response, "currency", None),
        "enterprise_value_low": getattr(response, "enterprise_value_low", None),
        "enterprise_value_mid": (
            getattr(response, "enterprise_value_mid", None)
            if getattr(response, "enterprise_value_mid", None) is not None
            else getattr(response, "enterprise_value", None)
        ),
        "enterprise_value_high": getattr(response, "enterprise_value_high", None),
        "equity_value_low": getattr(response, "equity_value_low", None),
        "equity_value_mid": (
            getattr(response, "equity_value_mid", None)
            if getattr(response, "equity_value_mid", None) is not None
            else getattr(response, "equity_value", None)
        ),
        "equity_value_high": getattr(response, "equity_value_high", None),
        "methodology": getattr(response, "methodology", None),
        "ebitda_multiple": getattr(response, "ebitda_multiple", None),
        "revenue_multiple": getattr(response, "revenue_multiple", None),
        "confidence_score": getattr(response, "confidence_score", None),
    }

    return build_shared_safety_net_reports(
        valuation_data,
        company_name=getattr(response, "company_name", None)
        or getattr(request, "company_name", None),
        locale=locale,
        reason=reason,
        correlation_id=context.get("correlation_id"),
    )
