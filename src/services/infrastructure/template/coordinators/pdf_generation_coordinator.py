"""
PDF Generation Coordinator.

Owns the Accountant View PDF workflow so TemplateService can stay a facade:
- dependency availability checks
- HTML rendering validation
- WeasyPrint document creation
- PDF metadata, performance metrics, and optional file persistence
"""

import time
from datetime import date, datetime
from functools import lru_cache
from importlib import import_module
from typing import Callable, Optional

from src.services.infrastructure.exceptions import TemplateRenderingError
from src.utils.logging import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def _get_weasyprint_html():
    import_module("src.services.infrastructure.weasyprint_env")
    try:
        from weasyprint import HTML

        return HTML, None
    except (ImportError, OSError) as exc:
        return None, exc


class PDFGenerationCoordinator:
    """Coordinates Accountant View PDF generation."""

    PERFORMANCE_TARGET_SECONDS = 3.0
    PERFORMANCE_TARGET_MB = 5.0

    def __init__(
        self,
        pdf_generator,
        render_accountant_view_func,
        logger_instance=None,
        jinja_available_provider: Optional[Callable[[], bool]] = None,
    ):
        self.logger = logger_instance or logger
        self.pdf_generator = pdf_generator
        self.render_accountant_view = render_accountant_view_func
        self.jinja_available_provider = jinja_available_provider or (lambda: True)

    def generate_accountant_view_pdf(
        self, valuation_data: dict[str, object], output_path: Optional[str] = None
    ) -> bytes:
        """
        Generate Accountant View PDF report from valuation data.

        Keeps the historical TemplateService error contract intact:
        ImportError/ValueError/TypeError are logged and re-raised, while
        TemplateRenderingError carries domain context for template/PDF failures.
        """
        company_name = valuation_data.get("company_name", "Unknown Company")

        try:
            self._ensure_runtime_available(company_name)
            pdf_start_time = time.time()

            html_content = self._render_html(valuation_data, company_name)
            html_length = len(html_content)
            report_id = valuation_data.get("report_id", "N/A")

            self.logger.info(
                "🔍 [PDF-GEN-TEMPLATE] Step 2: Preparing PDF metadata",
                extra={"company": company_name},
            )
            date_str = self._format_metadata_date(
                valuation_data.get("valuation_date", datetime.now().date())
            )

            self.logger.info(
                "🔍 [PDF-GEN-TEMPLATE] Step 3: Converting HTML to PDF using WeasyPrint",
                extra={
                    "company": company_name,
                    "html_length": html_length,
                    "report_id": report_id,
                },
            )
            pdf_doc = self._create_pdf_document(html_content, company_name, html_length)
            pdf_bytes = self._write_pdf_bytes(pdf_doc, company_name, html_length)

            if not pdf_bytes or len(pdf_bytes) == 0:
                error_msg = "PDF generation returned empty bytes"
                self.logger.error(
                    f"❌ [PDF-GEN-TEMPLATE] {error_msg}",
                    extra={"company": company_name},
                )
                raise ValueError(error_msg)

            pdf_generation_duration = time.time() - pdf_start_time
            self._log_pdf_metrics(company_name, pdf_bytes, pdf_generation_duration)
            self._save_pdf_if_requested(output_path, pdf_bytes, company_name)

            self.logger.info(
                "✅ [PDF-GEN-TEMPLATE] Accountant View PDF generated successfully",
                extra={
                    "company": company_name,
                    "pdf_size_bytes": len(pdf_bytes),
                    "html_length": html_length,
                    "valuation_date": date_str,
                },
            )
            return pdf_bytes

        except (ImportError, ValueError, TypeError) as e:
            self.logger.error(
                f"❌ [PDF-GEN-TEMPLATE] Error generating Accountant View PDF: {e}",
                extra={
                    "company": company_name,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise
        except TemplateRenderingError:
            raise

    def _ensure_runtime_available(self, company_name: object) -> None:
        if not self.pdf_generator.is_available():
            error_msg = "WeasyPrint not installed - PDF generation unavailable"
            self.logger.error(
                f"❌ [PDF-GEN-TEMPLATE] {error_msg}",
                extra={"company": company_name},
            )
            raise ImportError(
                "WeasyPrint required for PDF generation. Install with: pip install weasyprint"
            )

        if not self.jinja_available_provider():
            error_msg = "Jinja2 not installed - HTML rendering unavailable"
            self.logger.error(
                f"❌ [PDF-GEN-TEMPLATE] {error_msg}",
                extra={"company": company_name},
            )
            raise ImportError(
                "Jinja2 required for PDF generation. Install with: pip install jinja2"
            )

    def _render_html(self, valuation_data: dict[str, object], company_name: object) -> str:
        self.logger.info(
            "🔍 [PDF-GEN-TEMPLATE] Step 1: Rendering HTML from template",
            extra={"company": company_name},
        )
        html_content = self.render_accountant_view(valuation_data)

        if not html_content:
            error_msg = "HTML rendering returned empty content"
            self.logger.error(
                f"❌ [PDF-GEN-TEMPLATE] {error_msg}",
                extra={"company": company_name},
            )
            raise ValueError(error_msg)

        if not isinstance(html_content, str):
            error_msg = f"HTML rendering returned wrong type: {type(html_content).__name__}"
            self.logger.error(
                f"❌ [PDF-GEN-TEMPLATE] {error_msg}",
                extra={
                    "company": company_name,
                    "html_content_type": type(html_content).__name__,
                },
            )
            raise TypeError(error_msg)

        html_length = len(html_content)
        self.logger.info(
            "✅ [PDF-GEN-TEMPLATE] Step 1 completed: HTML rendered successfully",
            extra={
                "company": company_name,
                "html_length": html_length,
                "html_preview": html_content[:200] if html_length > 0 else None,
            },
        )
        return html_content

    @staticmethod
    def _format_metadata_date(valuation_date: object) -> str:
        if isinstance(valuation_date, datetime):
            return valuation_date.strftime("%Y-%m-%d")
        if isinstance(valuation_date, date):
            return valuation_date.strftime("%Y-%m-%d")
        return str(valuation_date)

    def _create_pdf_document(self, html_content: str, company_name: object, html_length: int):
        HTML, import_error = _get_weasyprint_html()
        if HTML is None:
            raise ImportError(
                "WeasyPrint required for PDF generation. "
                f"Import failed: {import_error}. Install with: pip install weasyprint"
            )

        try:
            pdf_doc = HTML(string=html_content)
            self.logger.info(
                "✅ [PDF-GEN-TEMPLATE] Step 3a: HTML document parsed successfully",
                extra={"company": company_name},
            )
            return pdf_doc
        except (ValueError, TypeError, AttributeError) as html_parse_error:
            self.logger.error(
                "❌ [PDF-GEN-TEMPLATE] Step 3a failed: HTML parsing error",
                extra={
                    "company": company_name,
                    "error_type": type(html_parse_error).__name__,
                    "error_message": str(html_parse_error),
                    "html_length": html_length,
                },
                exc_info=True,
            )
            raise TemplateRenderingError(
                f"Failed to parse HTML for PDF generation: {str(html_parse_error)}",
                company_name=company_name,
            ) from html_parse_error
        except TemplateRenderingError as html_parse_error:
            self.logger.error(
                "❌ [PDF-GEN-TEMPLATE] Step 3a failed: Unexpected HTML parsing error",
                extra={
                    "company": company_name,
                    "error_type": type(html_parse_error).__name__,
                    "error_message": str(html_parse_error),
                    "html_length": html_length,
                },
                exc_info=True,
            )
            raise TemplateRenderingError(
                f"Unexpected error parsing HTML for PDF: {str(html_parse_error)}",
                company_name=company_name,
            ) from html_parse_error

    def _write_pdf_bytes(self, pdf_doc, company_name: object, html_length: int) -> bytes:
        try:
            pdf_bytes = pdf_doc.write_pdf(metadata=self._build_pdf_metadata(company_name))
            self.logger.info(
                "✅ [PDF-GEN-TEMPLATE] Step 3b: PDF generation successful",
                extra={
                    "company": company_name,
                    "pdf_size_bytes": len(pdf_bytes) if pdf_bytes else 0,
                },
            )
            return pdf_bytes
        except (ValueError, IOError, OSError) as pdf_write_error:
            self.logger.error(
                "❌ [PDF-GEN-TEMPLATE] Step 3b failed: PDF write error",
                extra={
                    "company": company_name,
                    "error_type": type(pdf_write_error).__name__,
                    "error_message": str(pdf_write_error),
                    "html_length": html_length,
                },
                exc_info=True,
            )
            raise TemplateRenderingError(
                f"Failed to generate PDF from HTML: {str(pdf_write_error)}",
                company_name=company_name,
            ) from pdf_write_error
        except TemplateRenderingError as pdf_write_error:
            self.logger.error(
                "❌ [PDF-GEN-TEMPLATE] Step 3b failed: Unexpected PDF write error",
                extra={
                    "company": company_name,
                    "error_type": type(pdf_write_error).__name__,
                    "error_message": str(pdf_write_error),
                    "html_length": html_length,
                },
                exc_info=True,
            )
            raise TemplateRenderingError(
                f"Unexpected error generating PDF: {str(pdf_write_error)}",
                company_name=company_name,
            ) from pdf_write_error

    @staticmethod
    def _build_pdf_metadata(company_name: object) -> dict[str, str]:
        return {
            "title": f"Business Valuation Report - {company_name}",
            "author": "Upswitch Valuation Engine",
            "subject": "Business Valuation Report",
            "keywords": "business valuation, SME valuation, company valuation, financial analysis",
            "creator": "Upswitch Valuation Engine",
            "producer": "WeasyPrint",
        }

    def _log_pdf_metrics(
        self, company_name: object, pdf_bytes: bytes, pdf_generation_duration: float
    ) -> None:
        pdf_size_bytes = len(pdf_bytes)
        pdf_size_mb = pdf_size_bytes / (1024 * 1024)

        self.logger.info(
            "✅ [PDF-GEN-TEMPLATE] PDF generation performance metrics",
            extra={
                "company": company_name,
                "pdf_generation_time_seconds": round(pdf_generation_duration, 3),
                "pdf_size_bytes": pdf_size_bytes,
                "pdf_size_mb": round(pdf_size_mb, 2),
                "performance_target_met": (
                    pdf_generation_duration < self.PERFORMANCE_TARGET_SECONDS
                    and pdf_size_mb < self.PERFORMANCE_TARGET_MB
                ),
            },
        )

        if pdf_generation_duration >= self.PERFORMANCE_TARGET_SECONDS:
            self.logger.warning(
                "⚠️ [PDF-GEN-TEMPLATE] PDF generation time "
                f"({pdf_generation_duration:.2f}s) exceeds target (<3s)",
                extra={
                    "company": company_name,
                    "generation_time_seconds": round(pdf_generation_duration, 3),
                    "target_seconds": self.PERFORMANCE_TARGET_SECONDS,
                },
            )
        if pdf_size_mb >= self.PERFORMANCE_TARGET_MB:
            self.logger.warning(
                "⚠️ [PDF-GEN-TEMPLATE] PDF file size "
                f"({pdf_size_mb:.2f}MB) exceeds target (<5MB)",
                extra={
                    "company": company_name,
                    "pdf_size_mb": round(pdf_size_mb, 2),
                    "target_mb": self.PERFORMANCE_TARGET_MB,
                },
            )

    def _save_pdf_if_requested(
        self, output_path: Optional[str], pdf_bytes: bytes, company_name: object
    ) -> None:
        if not output_path:
            return

        try:
            with open(output_path, "wb") as f:
                f.write(pdf_bytes)
            self.logger.info(
                f"✅ [PDF-GEN-TEMPLATE] PDF saved to: {output_path}",
                extra={"company": company_name, "output_path": output_path},
            )
        except (IOError, OSError, PermissionError) as save_error:
            self.logger.warning(
                f"⚠️ [PDF-GEN-TEMPLATE] Failed to save PDF to file: {save_error}",
                extra={"company": company_name, "output_path": output_path},
            )
        except TemplateRenderingError as save_error:
            self.logger.warning(
                f"⚠️ [PDF-GEN-TEMPLATE] Unexpected error saving PDF to file: {save_error}",
                extra={"company": company_name, "output_path": output_path},
            )
