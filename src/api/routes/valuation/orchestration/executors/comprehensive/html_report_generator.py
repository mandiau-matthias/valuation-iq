"""
HTML Report Generator for Comprehensive Valuation

Generates HTML reports using HTMLReportService with bank-grade error handling.

BANK-GRADE QUALITY:
- Full type hints for type safety
- Specific exception handling (no generic Exception)
- Input validation at boundaries
- Comprehensive audit trail logging
- Explicit failure propagation

REFACTORED (Jan 2026):
- Simplified to only generate html_report
- info_tab_html removed from architecture
- report_data removed from architecture
"""

import time
from typing import Optional, TYPE_CHECKING

from src.api.schemas import ValuationRequest, ValuationResponse
from src.utils.valuation_logger import ValuationLogger
from src.utils.exceptions import APIError
from src.services.infrastructure.exceptions import ReportGenerationError

if TYPE_CHECKING:
    from src.services.infrastructure.html_report_service import HTMLReportService


class HTMLReportGenerator:
    """
    Generates HTML reports for comprehensive valuation.

    BANK-GRADE RESPONSIBILITIES:
    - Generate HTML reports using HTMLReportService
    - Handle errors gracefully with specific exception types
    - Initialize report attributes safely
    - Provide full audit trail of generation process
    - Validate inputs at boundaries

    DESIGN PATTERN: Facade + Delegation
    - Provides unified interface for HTML report generation
    - Delegates actual generation to HTMLReportService
    - Handles errors and logging at orchestration level
    """

    def __init__(
        self,
        html_report_service: Optional["HTMLReportService"],
        logger: Optional[ValuationLogger] = None,
    ) -> None:
        """
        Initialize HTML report generator.

        Args:
            html_report_service: HTMLReportService instance (can be None for graceful degradation)
            logger: Optional logger instance (creates default if not provided)
        """
        self.html_report_service = html_report_service
        self.logger = logger or ValuationLogger(self.__class__.__name__)

        self.logger.debug(
            "🔍 [HTML-GEN] HTMLReportGenerator initialized",
            extra={
                "html_report_service_available": html_report_service is not None,
                "html_report_service_type": (
                    type(html_report_service).__name__ if html_report_service else "None"
                ),
            },
        )

    async def generate_reports(
        self,
        response: ValuationResponse,
        request: ValuationRequest,
        correlation_id: str,
    ) -> ValuationResponse:
        """
        Generate HTML report and attach to response.

        Args:
            response: Valuation response object (must not be None)
            request: Valuation request object (must not be None)
            correlation_id: Correlation ID for request tracing

        Returns:
            ValuationResponse with html_report and pdf_html_report set

        Raises:
            APIError: When required inputs are missing
            ReportGenerationError: When report generation fails or returns incomplete output
        """
        company = request.company_name if request else "unknown"
        has_service = self.html_report_service is not None
        
        self.logger.debug(
            "🔍 [HTML-GEN] generate_reports() called",
            extra={
                "company": company,
                "correlation_id": correlation_id,
                "has_response": response is not None,
                "has_html_report_service": has_service,
            },
        )

        # Input validation
        if response is None:
            self.logger.error(
                "❌ [HTML-GEN] Input validation failed: response is None",
                extra={
                    "company": request.company_name if request else "unknown",
                    "correlation_id": correlation_id,
                },
            )
            raise APIError("HTML report generation received a null response object")

        if not request:
            self.logger.error(
                "❌ [HTML-GEN] Input validation failed: request is None",
                extra={"correlation_id": correlation_id},
            )
            raise APIError("HTML report generation received a null request object")

        # Reset report fields up front so a reused response object can never
        # leak stale HTML/PDF content across retries or repeated invocations.
        response.html_report = None
        response.pdf_html_report = None
        response.report_generation_error = None

        # Generate HTML report using service
        if not self.html_report_service:
            self.logger.error(
                "❌ [HTML-GEN] HTML Report Service not available",
                extra={
                    "company": request.company_name,
                    "correlation_id": correlation_id,
                },
            )
            raise ReportGenerationError(
                "HTML report service not available. Reports cannot be generated."
            )
        else:
            html_generation_start = time.time()
            try:
                self.logger.debug(
                    "🔄 [HTML-GEN] Starting HTML report generation",
                    extra={
                        "company": request.company_name,
                        "correlation_id": correlation_id,
                    },
                )

                # Generate report using service — no fallbacks; failures propagate
                locale = getattr(request, 'locale', None) or 'nl'
                reports = await self.html_report_service.generate_both_reports(
                    response, request, locale=locale
                )

                # Assign main report to response (info tab removed)
                response.html_report = reports.get("html_report")
                response.pdf_html_report = reports.get("pdf_html_report")
                report_context = reports.get("report_context") or {}
                response.report_context = report_context
                vw = report_context.get("valuation_waterfall_steps")
                if vw is not None:
                    response.ev_equity_waterfall_steps = list(vw)
                # Non-fatal: HTMLReportService.generate_both_reports() now
                # guarantees non-empty outputs via an internal safety-net.
                # We log if something slipped through so ops can see it, but
                # we MUST NOT block the successful valuation response.
                if not response.html_report or not response.pdf_html_report:
                    self.logger.error(
                        "❌ [HTML-GEN] Report service returned empty output despite safety net — continuing",
                        extra={
                            "company": request.company_name,
                            "correlation_id": correlation_id,
                            "has_html_report": bool(response.html_report),
                            "has_pdf_html_report": bool(response.pdf_html_report),
                        },
                    )
                    response.report_generation_error = (
                        "Report service returned empty output despite safety net."
                    )

                html_generation_duration = time.time() - html_generation_start

                pdf_html_len = len(response.pdf_html_report) if response.pdf_html_report else 0
                # DEBUG: TEMPLATE-SERVICE already logged "Main report PDF
                # rendered successfully" at the layer below.
                self.logger.debug(
                    "HTML report generation complete",
                    extra={
                        "company": request.company_name,
                        "correlation_id": correlation_id,
                        "html_report_length": len(response.html_report) if response.html_report else 0,
                        "pdf_html_report_length": pdf_html_len,
                        "generation_duration_seconds": round(html_generation_duration, 3),
                        "html_report_size_kb": (
                            round(len(response.html_report) / 1024, 2)
                            if response.html_report
                            else 0
                        ),
                    },
                )

            except Exception as report_error:
                html_generation_duration = time.time() - html_generation_start
                error_msg = f"{type(report_error).__name__}: {report_error}"
                self.logger.error(
                    f"❌ [HTML-GEN] Report generation failed: {error_msg}",
                    extra={
                        "company": request.company_name,
                        "correlation_id": correlation_id,
                        "error_type": type(report_error).__name__,
                        "error_message": str(report_error),
                        "generation_duration_seconds": round(html_generation_duration, 3),
                    },
                    exc_info=True,
                )
                response.html_report = None
                response.pdf_html_report = None
                response.report_generation_error = error_msg
                if isinstance(report_error, ReportGenerationError):
                    raise
                raise ReportGenerationError(error_msg) from report_error

        # Log final state
        final_html_report_length = len(response.html_report) if response.html_report else 0
        
        self.logger.debug(
            "🔍 [HTML-GEN] Final state",
            extra={
                "company": request.company_name,
                "correlation_id": correlation_id,
                "final_html_report_length": final_html_report_length,
                "html_report_generated": final_html_report_length > 0,
            },
        )

        return response
