"""
Post-Processing Handler for Comprehensive Valuation Orchestrator

BANK-GRADE HANDLER for final processing steps including performance summary,
HTML report generation, and payload reduction.

BANK-GRADE QUALITY:
- Full type hints for type safety
- Comprehensive audit trail logging
- Performance monitoring integration
- Graceful error handling
- Clear separation of concerns

DESIGN PATTERN: Handler Pattern
- Coordinates final processing steps
- Delegates to specialized components
- Provides unified interface for post-processing
"""

import time
from decimal import Decimal
from typing import Any, Dict

from src.api.schemas import ValuationRequest, ValuationResponse
from src.utils.valuation_logger import ValuationLogger

from .html_report_generator import HTMLReportGenerator
from .payload_reducer import PayloadReducer
from .performance_monitor import PerformanceMonitor
from .post_processing_safety_net import apply_safety_net_payload, valuation_data_for_safety_net


class PostProcessingHandler:
    """
    BANK-GRADE HANDLER for post-processing steps after response building.

    RESPONSIBILITIES:
    - Log performance summary for audit trail
    - Generate HTML reports (Main Report + Accountant View)
    - Reduce payload size for API efficiency
    - Provide full audit trail of post-processing

    DESIGN PATTERN: Handler + Dependency Injection
    - Coordinates multiple post-processing steps
    - Uses dependency injection for testability
    - Handles errors gracefully
    - Provides comprehensive logging
    """

    def __init__(
        self,
        performance_monitor: PerformanceMonitor,
        html_report_generator: HTMLReportGenerator,
        payload_reducer: PayloadReducer,
        logger: ValuationLogger,
    ) -> None:
        """
        Initialize the post-processing handler.

        BANK-GRADE INITIALIZATION:
        - Validates all dependencies are provided
        - Logs initialization state for audit trail
        - Ensures all components are ready

        Args:
            performance_monitor: Performance monitor instance (must not be None)
            html_report_generator: HTML report generator instance (can be None for graceful degradation)
            payload_reducer: Payload reducer instance (must not be None)
            logger: Logger instance (must not be None)

        Raises:
            None: Initialization never fails - validates and logs state
        """
        self.performance_monitor = performance_monitor
        self.html_report_generator = html_report_generator
        self.payload_reducer = payload_reducer
        self.logger = logger

    async def finalize_response(
        self,
        response: ValuationResponse,
        request: ValuationRequest,
        valuation_id: str,
        equity_value_mid: Decimal,
        quality_rating_value: str,
        correlation_id: str,
        overall_start_time: Decimal,
        stage_timings: Dict[str, Any],
    ) -> ValuationResponse:
        """
        Finalize the response with performance summary, HTML reports, and payload reduction.

        Args:
            response: The valuation response to finalize
            request: The valuation request
            valuation_id: Valuation ID
            equity_value_mid: Mid equity value
            quality_rating_value: Quality rating value
            correlation_id: Correlation ID for logging
            overall_start_time: Overall start time for performance monitoring
            stage_timings: Dictionary tracking stage timings

        Returns:
            Finalized ValuationResponse
        """
        company = request.company_name if request else "unknown"

        self.logger.debug(
            "finalize_response() entry point",
            extra={
                "correlation_id": correlation_id,
                "company": company,
                "valuation_id": valuation_id,
                "has_response": response is not None,
                "has_request": request is not None,
                "overall_start_time_type": type(overall_start_time).__name__,
                "overall_start_time_value": str(overall_start_time),
                "html_report_generator_is_none": self.html_report_generator is None,
            },
        )

        # Performance monitoring: Final summary
        # CRITICAL: Handle type conversion - overall_start_time might be float or Decimal
        try:
            overall_start_time_float = (
                float(overall_start_time)
                if isinstance(overall_start_time, Decimal)
                else overall_start_time
            )
            overall_duration = time.time() - overall_start_time_float
        except (TypeError, ValueError) as time_error:
            self.logger.error(
                "❌ [POST-PROCESS] CRITICAL: Error calculating overall_duration",
                extra={
                    "correlation_id": correlation_id,
                    "company": request.company_name if request else "unknown",
                    "valuation_id": valuation_id,
                    "error_type": type(time_error).__name__,
                    "error_message": str(time_error),
                    "overall_start_time_type": type(overall_start_time).__name__,
                    "overall_start_time_value": str(overall_start_time),
                },
                exc_info=True,
            )
            # Use a default duration if calculation fails
            overall_duration = 0.0
        stage_timings["total"] = overall_duration

        # Log performance summary using PerformanceMonitor
        self.performance_monitor.log_performance_summary(
            valuation_id=valuation_id,
            equity_value_mid=equity_value_mid,
            quality_rating_value=quality_rating_value,
            correlation_id=correlation_id,
            stage_timings=stage_timings,
            overall_duration=overall_duration,
        )

        # DIAGNOSTIC: Log state before HTML generation
        html_report_before = getattr(response, "html_report", None)
        html_report_length_before = len(html_report_before) if html_report_before else 0

        self.logger.debug(
            "🔍 [POST-PROCESS] State before HTML generation",
            extra={
                "correlation_id": correlation_id,
                "company": request.company_name,
                "valuation_id": valuation_id,
                "html_report_length_before": html_report_length_before,
                "has_html_report_attr": hasattr(response, "html_report"),
                "html_report_generator_available": self.html_report_generator is not None,
            },
        )

        # Generate HTML reports using HTMLReportGenerator.
        # Valuation numbers are already validated at this point — report failures
        # must not discard a successful valuation response.
        safety_net_reason: str | None = None
        if self.html_report_generator is None:
            self.logger.error(
                "❌ [POST-PROCESS] HTMLReportGenerator is None — skipping report generation",
                extra={
                    "correlation_id": correlation_id,
                    "company": request.company_name,
                    "valuation_id": valuation_id,
                },
            )
            response.report_generation_error = (
                "HTML report generator not available. Reports were not generated."
            )
            safety_net_reason = "post_processing_handler.no_html_report_generator"
        else:
            try:
                response = await self.html_report_generator.generate_reports(
                    response=response, request=request, correlation_id=correlation_id
                )
            except Exception as html_gen_error:
                self.logger.error(
                    "❌ [POST-PROCESS] HTML report generation failed — engaging safety-net",
                    extra={
                        "correlation_id": correlation_id,
                        "company": request.company_name,
                        "valuation_id": valuation_id,
                        "error_type": type(html_gen_error).__name__,
                        "error_message": str(html_gen_error),
                    },
                    exc_info=True,
                )
                response.report_generation_error = (
                    f"Report generation failed: {type(html_gen_error).__name__}: {html_gen_error}"
                )
                safety_net_reason = (
                    f"post_processing_handler.html_gen_failure:{type(html_gen_error).__name__}"
                )

        # Final guard: if templated rendering produced empty/short HTML for any
        # reason (silent skip, generator returned None, length under contract),
        # engage the safety-net for observability/PDF internals only. The
        # preview contract is strict: Venus may show a full templated report,
        # or no report. It must never show the safety-net summary card as if it
        # were a real ValuationIQ report.
        current_html = getattr(response, "html_report", None) or ""
        current_pdf_html = getattr(response, "pdf_html_report", None) or ""
        if safety_net_reason is None and (len(current_html) < 100 or len(current_pdf_html) < 500):
            safety_net_reason = (
                "post_processing_handler.empty_after_generation"
                if not current_html
                else "post_processing_handler.short_after_generation"
            )

        if safety_net_reason is not None:
            self._apply_safety_net(
                response=response,
                request=request,
                valuation_id=valuation_id,
                correlation_id=correlation_id,
                reason=safety_net_reason,
            )

        # DIAGNOSTIC: Log state after HTML generation
        html_report_after = getattr(response, "html_report", None)
        html_report_length_after = len(html_report_after) if html_report_after else 0

        self.logger.debug(
            "🔍 [POST-PROCESS] State after HTML generation",
            extra={
                "correlation_id": correlation_id,
                "company": request.company_name,
                "valuation_id": valuation_id,
                "html_report_length_after": html_report_length_after,
                "html_report_generated": html_report_length_after > 0,
                "html_report_changed": html_report_length_after != html_report_length_before,
                "safety_net_reason": safety_net_reason,
            },
        )

        # Reduce payload using PayloadReducer
        response = self.payload_reducer.reduce_payload(
            response=response,
            request_company_name=request.company_name,
            correlation_id=correlation_id,
        )

        return response

    def _apply_safety_net(
        self,
        *,
        response: ValuationResponse,
        request: ValuationRequest,
        valuation_id: str,
        correlation_id: str,
        reason: str,
    ) -> None:
        """Populate safety-net PDF/context data after screen report failure.

        The screen `html_report` is deliberately cleared: Venus may render a
        real templated report or no report, but never the safety-net summary as
        if it were the full ValuationIQ output.

        Wrapped in its own try/except: this helper must NEVER raise. A failure
        here would tank a successful valuation, which is precisely what the
        safety-net exists to prevent.
        """
        try:
            from src.services.infrastructure.safety_net_report import build_safety_net_reports

            locale = getattr(request, "locale", None) or "nl"
            company_name = getattr(request, "company_name", None) or "—"

            safety = build_safety_net_reports(
                valuation_data_for_safety_net(response),
                company_name=company_name,
                locale=locale,
                reason=reason,
                correlation_id=correlation_id,
            )
            apply_safety_net_payload(response, safety)

            self.logger.warning(
                "🛟 [POST-PROCESS] Safety-net report applied",
                extra={
                    "correlation_id": correlation_id,
                    "company": getattr(request, "company_name", None),
                    "valuation_id": valuation_id,
                    "reason": reason,
                    "html_report_length": (
                        len(response.html_report) if response.html_report else 0
                    ),
                    "pdf_html_report_length": (
                        len(response.pdf_html_report) if response.pdf_html_report else 0
                    ),
                },
            )
        except Exception as safety_error:
            # Last-line-of-defense logging only. We deliberately swallow so
            # the calculate flow returns valuation numbers even if the
            # safety-net itself fails (e.g. import error, OOM during string
            # build). The empty html_report will be re-handled by Titan's
            # defensive backfill before persistence.
            self.logger.error(
                "❌ [POST-PROCESS] Safety-net builder itself failed — returning valuation without report HTML",
                extra={
                    "correlation_id": correlation_id,
                    "company": getattr(request, "company_name", None),
                    "valuation_id": valuation_id,
                    "reason": reason,
                    "safety_error_type": type(safety_error).__name__,
                    "safety_error_message": str(safety_error)[:300],
                },
                exc_info=True,
            )
