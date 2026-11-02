"""HTML report orchestration service."""

import asyncio
from threading import Lock
from typing import TYPE_CHECKING, Callable, Dict, Optional

if TYPE_CHECKING:
    from src.api.schemas import ValuationResponse, ValuationRequest

from src.services.infrastructure.exceptions import (
    DataTransformationError,
    ReportGenerationError,
    TemplateRenderingError,
)
from src.services.infrastructure.html_report_pagination import apply_css_pagination_policy
from src.services.infrastructure.html_report_safety_net import build_html_service_safety_net_reports
from src.services.infrastructure.html_report_service_boundary import (
    extract_report_context,
    log_report_entry,
    template_service_available,
    validate_report_inputs,
)
from src.services.infrastructure.html_report_service_contracts import (
    HTMLReportConfig,
    ReportServiceLogger,
    TemplateData,
)
from src.services.infrastructure.html_report_service_runtime import (
    build_html_report_service_runtime,
)
from src.services.infrastructure.html_report_template_rendering import render_template_with_timeout
from src.services.infrastructure.html_report_validation import validate_html_content
from src.services.infrastructure.html_report_visualizations import (
    add_visualizations_to_template_data,
)
from src.services.infrastructure.main_report_data_aggregator import get_main_report_aggregator
from src.services.infrastructure.report_data_transformer import transform_for_info_tab
from src.services.infrastructure.report_generation.dual_report_renderer import (
    generate_dual_report_variants,
)
from src.services.infrastructure.report_generation.report_variant_renderer import (
    render_main_report_html,
    render_main_report_pdf_html,
    render_simplified_report_html,
)
from src.services.infrastructure.template_service import (
    JINJA_AVAILABLE,
    TemplateService,
    get_template_service,
)
from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


class HTMLReportService:
    """Generate HTML and PDF-ready report variants from valuation responses."""

    def __init__(
        self,
        template_service: Optional[TemplateService] = None,
        logger_instance: Optional[ReportServiceLogger] = None,
        enable_smart_pagination: bool = False,  # Changed to False - CSS handles pagination
    ) -> None:
        """Initialize the report service with injectable runtime dependencies."""
        runtime = build_html_report_service_runtime(
            template_service=template_service,
            logger_instance=logger_instance,
            jinja_available=JINJA_AVAILABLE,
            template_service_factory=get_template_service,
        )
        self.logger = runtime.logger
        self.enable_smart_pagination = runtime.enable_smart_pagination
        self.shared_transformer = runtime.shared_transformer
        self.chart_service = runtime.chart_service
        self.metrics_collector = runtime.metrics_collector
        self.parallel_orchestrator = runtime.parallel_orchestrator
        self.pagination_service = runtime.pagination_service
        self.accountant_view_strategy = runtime.accountant_view_strategy
        self.info_tab_strategy = runtime.info_tab_strategy
        self.pdf_strategy = runtime.pdf_strategy
        self.template_service = runtime.template_service
        self.health_checker = runtime.health_checker
        self.runtime_support = runtime.runtime_support

    async def _transform_data(
        self,
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol,
        context: Dict[str, Optional[str]],
        report_type: str,
        transform_func: Callable[
            [ValuationResponseProtocol, ValuationRequestProtocol], TemplateData
        ],
        timeout: float = HTMLReportConfig.TRANSFORMATION_TIMEOUT_SECONDS,
    ) -> TemplateData:
        """Transform valuation data for template consumption with timeout protection."""
        self.logger.info(
            f"🔍 [HTML-SERVICE] Transforming valuation response for {report_type}",
            extra={
                "company": context["company_name"],
                "correlation_id": context["correlation_id"],
                "report_type": report_type,
                "timeout_seconds": timeout,
            },
        )

        try:
            template_data = await asyncio.wait_for(
                asyncio.to_thread(transform_func, response, request), timeout=timeout
            )

            # BANK-GRADE: Generate optional visualizations if data allows
            if self.chart_service:
                try:
                    # Generate visualizations in a separate thread to avoid blocking
                    # Note: We catch exceptions here so chart failure doesn't break report generation
                    await self._add_visualizations(template_data, report_type)
                except Exception as viz_error:
                    self.logger.warning(
                        f"⚠️ [HTML-SERVICE] Visualization generation failed for {report_type} - proceeding without charts",
                        extra={"error": str(viz_error), "report_type": report_type},
                    )

            self.logger.info(
                f"🔍 [HTML-SERVICE] Data transformation completed for {report_type}",
                extra={
                    "company": context["company_name"],
                    "correlation_id": context["correlation_id"],
                    "report_type": report_type,
                    "template_data_type": type(template_data).__name__ if template_data else "None",
                    "template_data_keys": (
                        list(template_data.keys())
                        if isinstance(template_data, dict)
                        else "not_a_dict"
                    ),
                    "template_data_size": (
                        len(template_data) if isinstance(template_data, dict) else 0
                    ),
                },
            )
            return template_data

        except asyncio.TimeoutError:
            self.logger.error(
                f"❌ [HTML-SERVICE] Data transformation timed out for {report_type}",
                extra={
                    "company": context["company_name"],
                    "correlation_id": context["correlation_id"],
                    "report_type": report_type,
                    "timeout_seconds": timeout,
                    "error_category": "timeout_error",
                },
                exc_info=True,
            )
            raise DataTransformationError(
                f"Data transformation timed out after {timeout} seconds for {report_type}",
                company_name=context["company_name"],
                correlation_id=context["correlation_id"],
            )
        except Exception as transform_error:
            self.logger.error(
                f"❌ [HTML-SERVICE] Data transformation failed for {report_type}",
                extra={
                    "company": context["company_name"],
                    "correlation_id": context["correlation_id"],
                    "report_type": report_type,
                    "error_type": type(transform_error).__name__,
                    "error_message": str(transform_error),
                    "error_category": "data_transformation_error",
                },
                exc_info=True,
            )
            raise DataTransformationError(
                f"Data transformation failed for {report_type}: {str(transform_error)}",
                company_name=context["company_name"],
                correlation_id=context["correlation_id"],
            ) from transform_error

    async def _add_visualizations(self, template_data: TemplateData, report_type: str) -> None:
        """Add optional visualizations to template data."""
        await add_visualizations_to_template_data(
            template_data=template_data,
            chart_service=self.chart_service,
        )

    async def _render_template(
        self,
        template_data: TemplateData,
        context: Dict[str, Optional[str]],
        report_type: str,
        render_method: str,
        timeout: float = HTMLReportConfig.RENDERING_TIMEOUT_SECONDS,
    ) -> str:
        """Render a named template method with timeout and typed errors."""
        return await render_template_with_timeout(
            template_service=self.template_service,
            logger=self.logger,
            template_data=template_data,
            context=context,
            report_type=report_type,
            render_method=render_method,
            timeout=timeout,
        )

    def _validate_html_content(
        self,
        html_content: Optional[str],
        context: Dict[str, Optional[str]],
        report_type: str,
        min_length: int = HTMLReportConfig.MIN_HTML_CONTENT_LENGTH,
    ) -> bool:
        """Validate rendered HTML before returning it to callers."""
        return validate_html_content(
            html_content=html_content,
            context=context,
            report_type=report_type,
            min_length=min_length,
            logger=self.logger,
        )

    async def _apply_smart_pagination(
        self, html_content: str, context: Dict[str, Optional[str]], report_type: str
    ) -> str:
        """Apply the configured pagination policy to rendered HTML."""
        return await apply_css_pagination_policy(
            html_content=html_content,
            context=context,
            report_type=report_type,
            enable_smart_pagination=self.enable_smart_pagination,
            pagination_service=self.pagination_service,
            logger=self.logger,
        )

    async def generate_accountant_view_html(
        self, response: ValuationResponseProtocol, request: ValuationRequestProtocol
    ) -> Optional[str]:
        """Generate the accountant-view HTML report."""
        report_type = "Accountant View"
        locale = getattr(request, "locale", None) or "nl"

        validate_report_inputs(response, request, report_type)
        context = extract_report_context(response, request)
        log_report_entry(
            self.logger,
            method_name="generate_accountant_view_html",
            context=context,
            report_type=report_type,
            template_service=self.template_service,
        )

        if not template_service_available(
            self.logger,
            context=context,
            report_type=report_type,
            template_service=self.template_service,
            jinja_available=JINJA_AVAILABLE,
        ):
            return None

        template_service = self.template_service
        assert template_service is not None
        return await render_main_report_html(
            response=response,
            request=request,
            template_service=template_service,
            logger=self.logger,
            context=context,
            report_type=report_type,
            locale=locale,
            rendering_timeout_seconds=HTMLReportConfig.RENDERING_TIMEOUT_SECONDS,
            min_html_content_length=HTMLReportConfig.MIN_HTML_CONTENT_LENGTH,
        )

    async def generate_info_tab_html(
        self, response: ValuationResponseProtocol, request: ValuationRequestProtocol
    ) -> Optional[str]:
        """Generate standalone Info Tab HTML for backward-compatible callers."""
        report_type = "Info Tab"
        validate_report_inputs(response, request, report_type)
        context = extract_report_context(response, request)
        log_report_entry(
            self.logger,
            method_name="generate_info_tab_html",
            context=context,
            report_type=report_type,
            template_service=self.template_service,
        )

        if not template_service_available(
            self.logger,
            context=context,
            report_type=report_type,
            template_service=self.template_service,
            jinja_available=JINJA_AVAILABLE,
        ):
            return None

        try:
            template_data = await self._transform_data(
                response=response,
                request=request,
                context=context,
                report_type=report_type,
                transform_func=transform_for_info_tab,
            )

            html_content = await self._render_template(
                template_data=template_data,
                context=context,
                report_type=report_type,
                render_method="render_info_tab_report",
            )

            html_content = await self._apply_smart_pagination(html_content, context, report_type)

            if self._validate_html_content(html_content, context, report_type):
                return html_content
            return None

        except (TemplateRenderingError, DataTransformationError) as e:
            self.logger.error(
                f"❌ [HTML-SERVICE] {report_type} HTML generation failed",
                extra={
                    "company": context["company_name"],
                    "correlation_id": context["correlation_id"],
                    "report_type": report_type,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            return None
        except Exception as e:
            self.logger.error(
                f"❌ [HTML-SERVICE] Unexpected error during {report_type} HTML generation",
                extra={
                    "company": context["company_name"],
                    "correlation_id": context["correlation_id"],
                    "report_type": report_type,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            return None

    async def generate_simplified_report_html(
        self, response: ValuationResponseProtocol, request: ValuationRequestProtocol
    ) -> Optional[str]:
        """Generate the simplified report HTML variant."""
        report_type = "Simplified Report"

        # BANK-GRADE: Validate inputs at boundary
        validate_report_inputs(response, request, report_type)
        context = extract_report_context(response, request)
        log_report_entry(
            self.logger,
            method_name="generate_simplified_report_html",
            context=context,
            report_type=report_type,
            template_service=self.template_service,
        )

        # BANK-GRADE: Check template service availability
        if not template_service_available(
            self.logger,
            context=context,
            report_type=report_type,
            template_service=self.template_service,
            jinja_available=JINJA_AVAILABLE,
        ):
            return None

        template_service = self.template_service
        assert template_service is not None
        return await render_simplified_report_html(
            response=response,
            request=request,
            template_service=template_service,
            logger=self.logger,
            context=context,
            report_type=report_type,
            rendering_timeout_seconds=HTMLReportConfig.RENDERING_TIMEOUT_SECONDS,
            min_html_content_length=HTMLReportConfig.MIN_HTML_CONTENT_LENGTH,
        )

    async def generate_main_report_html(
        self,
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol,
        locale: str = "nl",
    ) -> Optional[str]:
        """Generate the canonical main report HTML."""
        report_type = "Main Report"

        # BANK-GRADE: Validate inputs at boundary
        validate_report_inputs(response, request, report_type)
        context = extract_report_context(response, request)
        log_report_entry(
            self.logger,
            method_name="generate_main_report_html",
            context=context,
            report_type=report_type,
            template_service=self.template_service,
        )

        # BANK-GRADE: Check template service availability
        if not template_service_available(
            self.logger,
            context=context,
            report_type=report_type,
            template_service=self.template_service,
            jinja_available=JINJA_AVAILABLE,
        ):
            return None

        template_service = self.template_service
        assert template_service is not None
        return await render_main_report_html(
            response=response,
            request=request,
            template_service=template_service,
            logger=self.logger,
            context=context,
            report_type=report_type,
            locale=locale,
            rendering_timeout_seconds=HTMLReportConfig.RENDERING_TIMEOUT_SECONDS,
            min_html_content_length=HTMLReportConfig.MIN_HTML_CONTENT_LENGTH,
        )

    async def generate_html_report(
        self,
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol,
        use_main_report: bool = True,
        locale: str = "nl",
    ) -> Optional[str]:
        """Generate the canonical HTML report entry point."""
        company = getattr(response, "company_name", "unknown") if response else "unknown"

        self.logger.info(
            f"🚀 [HTML-SERVICE] generate_html_report() - generating {'Main Report' if use_main_report else 'Accountant View'}",
            extra={
                "company": company,
                "has_template_service": self.template_service is not None,
                "use_main_report": use_main_report,
            },
        )

        validate_report_inputs(response, request, "HTML Report")
        context = extract_report_context(response, request)
        log_report_entry(
            self.logger,
            method_name="generate_html_report",
            context=context,
            report_type="HTML Report",
            template_service=self.template_service,
        )

        if not self.template_service:
            raise ReportGenerationError(
                "Template service not available — cannot generate any report",
                company_name=context.get("company_name"),
            )

        if use_main_report:
            html_report = await self.generate_main_report_html(response, request, locale=locale)

            if not html_report:
                raise ReportGenerationError(
                    f"Main report generation returned empty result for {context.get('company_name', 'unknown')}. "
                    "No fallback to legacy views — the main report template must succeed."
                )

            self.logger.info(
                "✅ [HTML-SERVICE] Main Report generated successfully",
                extra={
                    "company": context["company_name"],
                    "html_length": len(html_report),
                },
            )
            return html_report

        self.logger.warning(
            "Legacy accountant view requested; using canonical main report instead",
            extra={"company": context["company_name"], "locale": locale},
        )
        return await self.generate_main_report_html(response, request, locale=locale)

    async def generate_main_report_pdf_html(
        self,
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol,
        locale: str = "nl",
    ) -> Optional[str]:
        """Generate PDF-optimized HTML from the main-report templates."""
        report_type = "Main Report PDF"

        validate_report_inputs(response, request, report_type)
        context = extract_report_context(response, request)

        if not template_service_available(
            self.logger,
            context=context,
            report_type=report_type,
            template_service=self.template_service,
            jinja_available=JINJA_AVAILABLE,
        ):
            raise ReportGenerationError(
                f"{report_type}: template service not available",
                company_name=context.get("company_name"),
                correlation_id=context.get("correlation_id"),
            )

        template_service = self.template_service
        assert template_service is not None
        return await render_main_report_pdf_html(
            response=response,
            request=request,
            template_service=template_service,
            logger=self.logger,
            context=context,
            report_type=report_type,
            locale=locale,
            rendering_timeout_seconds=HTMLReportConfig.RENDERING_TIMEOUT_SECONDS,
            min_html_content_length=HTMLReportConfig.MIN_HTML_CONTENT_LENGTH,
        )

    async def generate_both_reports(
        self,
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol,
        locale: str = "nl",
    ) -> TemplateData:
        """
        Generate screen and PDF HTML variants.

        Robustness contract: always returns non-empty ``html_report`` and
        ``pdf_html_report``. Template-service failures degrade through the
        safety-net renderer and mark ``report_context.safety_net`` for QA.
        """
        report_type = "generate_both_reports"
        context = extract_report_context(response, request)

        if not template_service_available(
            self.logger,
            context=context,
            report_type=report_type,
            template_service=self.template_service,
            jinja_available=JINJA_AVAILABLE,
        ):
            self.logger.warning(
                "🛟 [HTML-SAFETY-NET] Template service unavailable — returning safety-net report",
                extra={**context, "reason": "template_service_unavailable"},
            )
            return build_html_service_safety_net_reports(
                response,
                request,
                locale=locale,
                reason="template_service_unavailable",
                context=context,
            )

        template_service = self.template_service
        assert template_service is not None

        return await generate_dual_report_variants(
            response=response,
            request=request,
            aggregator=get_main_report_aggregator(),
            template_service=template_service,
            logger=self.logger,
            context=context,
            locale=locale,
            rendering_timeout_seconds=HTMLReportConfig.RENDERING_TIMEOUT_SECONDS,
            screen_min_length=HTMLReportConfig.MIN_HTML_CONTENT_LENGTH,
        )

    def get_metrics(self) -> dict[str, object]:
        """Get report generation metrics."""
        return self.runtime_support.get_metrics()

    def export_metrics_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        return self.runtime_support.export_metrics_prometheus()

    def get_health_status(self) -> dict[str, object]:
        """Get health check status."""
        return self.runtime_support.get_health_status()

    def check_health(self) -> dict[str, object]:
        """Perform health checks on all components."""
        return self.runtime_support.check_health()

    async def generate_accountant_view_pdf(
        self,
        html_content: str,
        template_data: Optional[TemplateData] = None,
        correlation_id: Optional[str] = None,
    ) -> Optional[bytes]:
        """Generate Accountant View PDF bytes from HTML content."""
        return await self.runtime_support.generate_accountant_view_pdf(
            html_content=html_content,
            template_data=template_data,
            correlation_id=correlation_id,
        )


_html_report_service_instance: Optional[HTMLReportService] = None
_html_report_service_lock = Lock()


def get_html_report_service() -> HTMLReportService:
    """
    Return the process-wide HTML report service.

    Runtime routes generate reports and PDFs frequently; constructing the full
    service stack per request reloads templates, resets metrics, and creates
    noisy startup-style logs. This singleton keeps the stack warm while tests
    can still instantiate HTMLReportService directly with injected fakes.
    """
    global _html_report_service_instance
    if _html_report_service_instance is None:
        with _html_report_service_lock:
            if _html_report_service_instance is None:
                template_service = get_template_service() if JINJA_AVAILABLE else None
                _html_report_service_instance = HTMLReportService(template_service=template_service)
    return _html_report_service_instance
