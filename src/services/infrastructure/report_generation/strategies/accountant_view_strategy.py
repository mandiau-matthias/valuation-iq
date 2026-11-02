"""
Accountant View Report Strategy

Implements report generation strategy for Accountant View HTML reports.
This is the main comprehensive report (20-30 pages) for SME valuations.

BANK-GRADE IMPLEMENTATION:
- Full validation at boundaries
- Comprehensive error handling
- Audit trail logging
- Timeout management
- Circuit breaker protection
"""

import asyncio
import time
from typing import Dict, Optional, Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from src.api.schemas import ValuationResponse, ValuationRequest

from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)
from src.services.infrastructure.exceptions import (
    MissingDataError,
    DataTransformationError,
    TemplateRenderingError,
)
from src.services.infrastructure.report_generation.strategies.base_report_strategy import (
    BaseReportStrategy,
)
from src.services.infrastructure.report_generation.circuit_breaker import (
    CircuitBreakerOpenError,
)
from src.services.infrastructure.report_generation.config import (
    ReportGenerationConfig,
)

if TYPE_CHECKING:
    from src.services.infrastructure.template_service import TemplateService

class AccountantViewStrategy(BaseReportStrategy):
    """
    Strategy for generating Accountant View HTML reports.
    
    BANK-GRADE RESPONSIBILITIES:
    - Validate inputs at boundary
    - Transform valuation response to template data
    - Render Accountant View template
    - Validate generated HTML content
    - Handle errors gracefully with specific exception types
    - Circuit breaker protection for failure isolation
    """
    
    def get_report_type(self) -> str:
        """Return report type name."""
        return "Accountant View"
    
    def get_timeout_seconds(self) -> float:
        """Return timeout for Accountant View generation."""
        return 45.0  # Accountant View is larger, needs more time
    
    def get_min_content_length(self) -> int:
        """Return minimum HTML content length for Accountant View."""
        return ReportGenerationConfig.MIN_HTML_CONTENT_LENGTH
    
    async def generate(
        self,
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol,
        context: Dict[str, Optional[str]],
        template_service: Any,
        transform_func: Callable,
        render_method: str,
    ) -> Optional[str]:
        """
        Generate Accountant View HTML report.
        
        BANK-GRADE EXECUTION:
        - Validates inputs at boundary
        - Uses circuit breaker for failure isolation
        - Transforms data with timeout protection
        - Renders template with timeout protection
        - Validates content quality
        - Handles errors with specific exception types
        
        Args:
            response: ValuationResponse with calculation results
            request: Original ValuationRequest for context
            context: Context dictionary with company_name and correlation_id
            template_service: TemplateService instance for rendering
            transform_func: Function to transform response to template data
            render_method: Name of render method on template_service
            
        Returns:
            HTML string, or None if generation fails
        """
        report_type = self.get_report_type()
        start_time = time.time()
        
        try:
            self.logger.info(
                f"🚀 [REPORT-STRATEGY] {report_type} generation started",
                extra={
                    "company": context.get("company_name", "unknown"),
                    "correlation_id": context.get("correlation_id"),
                    "report_type": report_type,
                    "template_service_available": template_service is not None,
                    "template_service_type": type(template_service).__name__ if template_service else "None",
                    "circuit_state": self.circuit_breaker.get_state().value,
                },
            )
        except Exception as log_err:
            # BANK-GRADE: Use structured logging instead of direct stderr writes
            try:
                self.logger.error(
                    f"❌ [REPORT-STRATEGY] Failed to log {report_type} entry point",
                    extra={
                        "error_type": type(log_err).__name__,
                        "error_message": str(log_err),
                    },
                    exc_info=True,
                )
            except Exception:
                pass  # If logging fails, continue without polluting stderr
        
        # BANK-GRADE: Top-level exception handler for visibility (like InfoTabStrategy)
        try:
            # BANK-GRADE: Validate inputs at boundary
            try:
                self.validate_inputs(response, request, report_type)
            except (MissingDataError, ValueError, TypeError) as validation_error:
                latency = time.time() - start_time
                if self.metrics_collector:
                    self.metrics_collector.record_failure(report_type, "validation_error", latency)
                
                self.logger.error(
                    f"❌ [REPORT-STRATEGY] {report_type} validation failed",
                    extra={
                        "company": getattr(response, "company_name", "unknown") if response else "unknown",
                        "correlation_id": getattr(request, "correlation_id", None) if request else None,
                        "report_type": report_type,
                        "error_type": type(validation_error).__name__,
                        "error_message": str(validation_error),
                        "error_category": "validation_error",
                    },
                    exc_info=True,
                )
                return None
            
            # BANK-GRADE: Check template service availability
            template_service_available = self._check_template_service_available(context, report_type, template_service)
            if not template_service_available:
                latency = time.time() - start_time
                if self.metrics_collector:
                    self.metrics_collector.record_failure(report_type, "template_service_unavailable", latency)
                self.logger.warning(
                    f"⚠️ [REPORT-STRATEGY] {report_type} generation skipped - template service not available",
                    extra={
                        "company": context["company_name"],
                        "correlation_id": context["correlation_id"],
                        "report_type": report_type,
                        "early_return_reason": "template_service_not_available",
                    },
                )
                return None

            result = await self._generate_report(
                response=response,
                request=request,
                context=context,
                template_service=template_service,
                transform_func=transform_func,
                render_method=render_method,
            )

            # BANK-GRADE: Record metrics
            latency = time.time() - start_time

            # BANK-GRADE: If generation failed, log error and return None (no fallback)
            if result is None:
                if self.metrics_collector:
                    self.metrics_collector.record_failure(report_type, "generation_returned_none", latency)

                self.logger.error(
                    f"❌ [REPORT-STRATEGY] {report_type} generation returned None",
                    extra={
                        "company": context["company_name"],
                        "correlation_id": context["correlation_id"],
                        "report_type": report_type,
                        "fallback_disabled": True,
                    },
                )
                return None

            # Record success
            if self.metrics_collector:
                self.metrics_collector.record_success(report_type, latency)

            return result

        except Exception as top_level_error:
            self.logger.error(
                f"❌ [REPORT-STRATEGY] CRITICAL: Top-level exception in {report_type} generate()",
                extra={
                    "company": context.get("company_name", "unknown") if context else "unknown",
                    "correlation_id": context.get("correlation_id") if context else None,
                    "report_type": report_type,
                    "error_type": type(top_level_error).__name__,
                    "error_message": str(top_level_error),
                },
                exc_info=True,
            )
            return None
    
    async def _generate_report(
        self,
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol,
        context: Dict[str, Optional[str]],
        template_service: Any,
        transform_func: Callable,
        render_method: str,
    ) -> Optional[str]:
        """
        Internal method to generate report (called through circuit breaker).
        
        Args:
            response: ValuationResponse with calculation results
            request: Original ValuationRequest for context
            context: Context dictionary with company_name and correlation_id
            template_service: TemplateService instance for rendering
            transform_func: Function to transform response to template data
            render_method: Name of render method on template_service
            
        Returns:
            HTML string, or None if generation fails
        """
        report_type = self.get_report_type()
        
        try:
            # BANK-GRADE: Transform data with timeout
            self.logger.info(
                f"🔍 [REPORT-STRATEGY] Transforming data for {report_type}",
                extra={
                    "company": context["company_name"],
                    "correlation_id": context["correlation_id"],
                    "report_type": report_type,
                    "timeout_seconds": ReportGenerationConfig.TRANSFORMATION_TIMEOUT_SECONDS,
                    "circuit_state": self.circuit_breaker.get_state().value,
                },
            )
            
            template_data = await asyncio.wait_for(
                asyncio.to_thread(transform_func, response, request),
                timeout=ReportGenerationConfig.TRANSFORMATION_TIMEOUT_SECONDS
            )
            
            self.logger.info(
                f"🔍 [REPORT-STRATEGY] Data transformation completed for {report_type}",
                extra={
                    "company": context["company_name"],
                    "correlation_id": context["correlation_id"],
                    "report_type": report_type,
                    "template_data_type": type(template_data).__name__ if template_data else "None",
                    "template_data_keys": list(template_data.keys()) if isinstance(template_data, dict) else "not_a_dict",
                },
            )
            
            # BANK-GRADE: Render template with timeout
            self.logger.info(
                f"🔍 [REPORT-STRATEGY] Rendering template for {report_type}",
                extra={
                    "company": context["company_name"],
                    "correlation_id": context["correlation_id"],
                    "report_type": report_type,
                    "render_method": render_method,
                    "timeout_seconds": ReportGenerationConfig.RENDERING_TIMEOUT_SECONDS,
                },
            )
            
            render_func = getattr(template_service, render_method)
            html_content = await asyncio.wait_for(
                asyncio.to_thread(render_func, template_data),
                timeout=ReportGenerationConfig.RENDERING_TIMEOUT_SECONDS
            )
            
            self.logger.info(
                f"🔍 [REPORT-STRATEGY] Template rendering completed for {report_type}",
                extra={
                    "company": context["company_name"],
                    "correlation_id": context["correlation_id"],
                    "report_type": report_type,
                    "html_content_length": len(html_content) if html_content else 0,
                },
            )
            
            # BANK-GRADE: Validate content
            validation_passed = self._validate_html_content(
                html_content,
                context,
                report_type,
                self.get_min_content_length()
            )
            if validation_passed:
                return html_content
            return None
            
        except asyncio.TimeoutError as timeout_error:
            # BANK-GRADE: Handle timeout errors (will be recorded by circuit breaker)
            error_type = "transformation_timeout" if "transform" in str(timeout_error).lower() else "rendering_timeout"
            self.logger.error(
                f"❌ [REPORT-STRATEGY] {report_type} generation timed out",
                extra={
                    "company": context["company_name"],
                    "correlation_id": context["correlation_id"],
                    "report_type": report_type,
                    "error_type": type(timeout_error).__name__,
                    "error_category": error_type,
                    "timeout_seconds": (
                        ReportGenerationConfig.TRANSFORMATION_TIMEOUT_SECONDS
                        if error_type == "transformation_timeout"
                        else ReportGenerationConfig.RENDERING_TIMEOUT_SECONDS
                    ),
                },
                exc_info=True,
            )
            raise  # Re-raise so circuit breaker can record failure
            
        except (TemplateRenderingError, DataTransformationError) as e:
            # BANK-GRADE: Specific exception handling (will be recorded by circuit breaker)
            self.logger.error(
                f"❌ [REPORT-STRATEGY] {report_type} generation failed",
                extra={
                    "company": context["company_name"],
                    "correlation_id": context["correlation_id"],
                    "report_type": report_type,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "error_category": "template_or_transformation_error",
                },
                exc_info=True,
            )
            raise  # Re-raise so circuit breaker can record failure
            
        except Exception as e:
            # BANK-GRADE: Catch-all for unexpected errors (will be recorded by circuit breaker)
            self.logger.error(
                f"❌ [REPORT-STRATEGY] Unexpected error during {report_type} generation",
                extra={
                    "company": context["company_name"],
                    "correlation_id": context["correlation_id"],
                    "report_type": report_type,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "error_category": "unexpected_error",
                },
                exc_info=True,
            )
            raise  # Re-raise so circuit breaker can record failure
