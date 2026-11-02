"""Service-boundary helpers for HTML report generation."""

from collections.abc import Mapping
from typing import Optional, Protocol

from src.services.infrastructure.exceptions import MissingDataError
from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)


class HTMLReportBoundaryLogger(Protocol):
    def info(
        self,
        message: str,
        *args: object,
        extra: Optional[Mapping[str, object]] = ...,
        **kwargs: object,
    ) -> None: ...

    def warning(
        self,
        message: str,
        *args: object,
        extra: Optional[Mapping[str, object]] = ...,
        **kwargs: object,
    ) -> None: ...


def validate_report_inputs(
    response: ValuationResponseProtocol,
    request: ValuationRequestProtocol,
    report_type: str,
) -> None:
    """Validate required report inputs at the public service boundary."""
    if not response:
        raise MissingDataError(
            f"ValuationResponse is required but was None for {report_type}",
            missing_fields=["response"],
            company_name=None,
            correlation_id=None,
        )
    if not request:
        raise MissingDataError(
            f"ValuationRequest is required but was None for {report_type}",
            missing_fields=["request"],
            company_name=None,
            correlation_id=None,
        )
    if not hasattr(response, "company_name") or not response.company_name:
        raise MissingDataError(
            f"ValuationResponse missing required field: company_name for {report_type}",
            missing_fields=["company_name"],
            company_name=None,
            correlation_id=getattr(request, "correlation_id", None),
        )


def extract_report_context(
    response: ValuationResponseProtocol,
    request: ValuationRequestProtocol,
) -> dict[str, Optional[str]]:
    """Extract common company/correlation context for logs and errors."""
    correlation_id = None
    if request:
        correlation_id = getattr(request, "correlation_id", None)

    if not correlation_id:
        try:
            from src.utils.correlation_context import get_correlation_id

            correlation_id = get_correlation_id()
        except (ImportError, AttributeError):
            pass

    if not correlation_id and response:
        correlation_id = getattr(response, "correlation_id", None)

    return {
        "company_name": getattr(response, "company_name", "unknown") if response else "unknown",
        "correlation_id": correlation_id,
    }


def log_report_entry(
    logger: HTMLReportBoundaryLogger,
    *,
    method_name: str,
    context: Mapping[str, Optional[str]],
    report_type: str,
    template_service: object,
) -> None:
    """Emit the standard structured entry log for report generation methods."""
    logger.info(
        f"[HTML-SERVICE] {method_name}() called",
        extra={
            "company": context["company_name"],
            "correlation_id": context["correlation_id"],
            "report_type": report_type,
            "template_service_available": template_service is not None,
            "template_service_type": (
                type(template_service).__name__ if template_service else "None"
            ),
            "response_is_none": False,
            "request_is_none": False,
        },
    )


def template_service_available(
    logger: HTMLReportBoundaryLogger,
    *,
    context: Mapping[str, Optional[str]],
    report_type: str,
    template_service: object,
    jinja_available: bool,
) -> bool:
    """Return whether a template service is available and log degraded paths."""
    if template_service:
        return True

    logger.warning(
        f"[HTML-SERVICE] Template service not available - cannot generate {report_type} HTML",
        extra={
            "company": context["company_name"],
            "correlation_id": context["correlation_id"],
            "report_type": report_type,
            "template_service_is_none": True,
            "jinja_available": jinja_available,
            "early_return_reason": "template_service_is_none",
        },
    )
    return False
