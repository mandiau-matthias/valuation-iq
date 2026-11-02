"""Runtime support for HTML report observability and PDF conversion."""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.services.infrastructure.report_generation.health_checker import HealthChecker
from src.services.infrastructure.report_generation.metrics_collector import MetricsCollector
from src.services.infrastructure.report_generation.strategies import PDFGenerationStrategy


class HTMLReportRuntimeSupport:
    """Owns operational helpers that are adjacent to, but not part of, HTML orchestration."""

    def __init__(
        self,
        *,
        logger: Any,
        metrics_collector: MetricsCollector,
        health_checker: HealthChecker,
        pdf_strategy: PDFGenerationStrategy,
    ) -> None:
        self.logger = logger
        self.metrics_collector = metrics_collector
        self.health_checker = health_checker
        self.pdf_strategy = pdf_strategy

    def get_metrics(self) -> Dict[str, Any]:
        """Return report generation metrics."""
        return self.metrics_collector.get_all_metrics()

    def export_metrics_prometheus(self) -> str:
        """Return report generation metrics in Prometheus format."""
        return self.metrics_collector.export_prometheus()

    def get_health_status(self) -> Dict[str, Any]:
        """Return summarized report-generation component health."""
        return self.health_checker.get_health_summary()

    def check_health(self) -> Dict[str, Any]:
        """Run component health checks and return serializable results."""
        return {
            component: result.to_dict()
            for component, result in self.health_checker.check_all().items()
        }

    async def generate_accountant_view_pdf(
        self,
        html_content: str,
        template_data: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ) -> Optional[bytes]:
        """Generate an Accountant View PDF from already-rendered HTML."""
        if not html_content or len(html_content) < 100:
            self.logger.error(
                "❌ [HTML-SERVICE] Invalid HTML content for PDF generation",
                extra={
                    "correlation_id": correlation_id,
                    "html_length": len(html_content) if html_content else 0,
                    "minimum_required": 100,
                },
            )
            return None

        # DEBUG: pdf_strategy logs the canonical PDF gen success at INFO;
        # this "starting" line is an extra plumbing breadcrumb.
        self.logger.debug(
            "🔍 [HTML-SERVICE] Starting PDF generation",
            extra={
                "correlation_id": correlation_id,
                "html_length": len(html_content) if html_content else 0,
                "html_content_is_none": html_content is None,
                "has_template_data": template_data is not None,
            },
        )

        try:
            pdf_bytes = await self.pdf_strategy.generate(
                html_content=html_content,
                template_data=template_data,
                correlation_id=correlation_id,
            )

            if pdf_bytes:
                # DEBUG: this is a layered confirmation — pdf_strategy already
                # logged the canonical "✅ [PDF-STRATEGY] PDF generated
                # successfully" with size at INFO.
                self.logger.debug(
                    "✅ [HTML-SERVICE] PDF generation successful",
                    extra={
                        "correlation_id": correlation_id,
                        "pdf_size_bytes": len(pdf_bytes),
                        "pdf_size_kb": round(len(pdf_bytes) / 1024, 2),
                    },
                )
                return pdf_bytes

            self.logger.warning(
                "⚠️ [HTML-SERVICE] PDF generation returned None",
                extra={"correlation_id": correlation_id},
            )
            return None

        except Exception as exc:
            self.logger.error(
                "❌ [HTML-SERVICE] PDF generation failed",
                extra={
                    "correlation_id": correlation_id,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
                exc_info=True,
            )
            raise
