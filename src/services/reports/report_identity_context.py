"""Identity extraction helpers for main report aggregation.

These functions keep schema-compatibility probing out of
``MainReportDataAggregator`` so the aggregator can stay focused on composing
the final report context.
"""

from typing import Optional, Protocol, cast

from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)
from src.utils.registry_identity_context import resolve_business_type_id, resolve_registry_identity

ValuationRequest = ValuationRequestProtocol
ValuationResponse = ValuationResponseProtocol


class SupportsGet(Protocol):
    def get(self, key: str, default: object = None) -> object | None: ...


def get_report_business_type_id(
    response: ValuationResponse,
    request: Optional[ValuationRequest],
) -> Optional[str]:
    """Extract business type id from request or response."""
    if request:
        request_business_type_id = resolve_business_type_id(
            business_context=getattr(request, "business_context", None),
            business_type_id=getattr(request, "business_type_id", None),
        )
        if request_business_type_id:
            return str(request_business_type_id)

        request_business_type = getattr(request, "business_type", None)
        if request_business_type:
            return str(request_business_type)

    detailed_results = _mapping_or_none(getattr(response, "detailed_results", None))
    if detailed_results:
        business_type_id = detailed_results.get("business_type_id") or detailed_results.get(
            "business_type"
        )
        if business_type_id:
            return str(business_type_id)

    return None


def get_report_nace_code(
    response: ValuationResponse,
    request: Optional[ValuationRequest],
) -> Optional[str]:
    """Extract NACE code from request or response."""
    if request:
        request_nace_code = getattr(request, "nace_code", None)
        if request_nace_code:
            return str(request_nace_code)

        request_activity_code = getattr(request, "activity_code", None)
        if request_activity_code:
            return str(request_activity_code)

    detailed_results = _mapping_or_none(getattr(response, "detailed_results", None))
    if detailed_results:
        nace_code = (
            detailed_results.get("nace_code")
            or detailed_results.get("activity_code")
            or detailed_results.get("primary_activity_code")
        )
        if nace_code:
            return str(nace_code)

    return None


def get_report_registration_number(
    response: ValuationResponse,
    request: Optional[ValuationRequest],
) -> Optional[str]:
    """Extract company registration number from request or response."""
    if request:
        resolved_identity = resolve_registry_identity(
            country_code=getattr(request, "country_code", None),
            business_context=getattr(request, "business_context", None),
            registration_number=getattr(request, "registration_number", None),
            kbo_number=getattr(request, "kbo_number", None),
            kvk_number=getattr(request, "kvk_number", None),
        )
        for field in ("registration_number", "kbo_number", "kvk_number"):
            value = resolved_identity.get(field)
            if value:
                return str(value)

        company_id = getattr(request, "company_id", None)
        if company_id:
            return str(company_id)

        for field in ("registration_number", "kbo_number", "kvk_number"):
            value = getattr(request, field, None)
            if value:
                return str(value)

    detailed_results = _mapping_or_none(getattr(response, "detailed_results", None))
    if detailed_results:
        registration_number = (
            detailed_results.get("registration_number")
            or detailed_results.get("kbo_number")
            or detailed_results.get("kvk_number")
            or detailed_results.get("company_id")
            or detailed_results.get("enterprise_number")
        )
        if registration_number:
            return str(registration_number)

    return None


def _mapping_or_none(value: object) -> SupportsGet | None:
    if value is not None and hasattr(value, "get") and callable(value.get):
        return cast(SupportsGet, value)
    return None
