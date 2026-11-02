from src.utils.exceptions import DataValidationError

"""
PDF Generator Module

RESPONSIBILITIES:
- Generate PDF reports from HTML content
- Handle PDF conversion and file operations
- Return base64-encoded PDF bytes for Titan to store in Supabase

ARCHITECTURE:
- ValuationIQ generates PDF bytes using WeasyPrint
- PDF bytes are base64 encoded and included in the API response
- Titan API receives the bytes, decodes, and stores in Supabase Storage
- Titan generates the pdf_url and returns to frontend

REFACTORING NOTE:
Extracted from template_service.py to improve maintainability and reduce file size.
"""

import base64
import json
import sys
import threading
from functools import lru_cache
from importlib import import_module
from typing import Any, Dict, Optional, Tuple

from src.utils.logging import get_logger

_RECURSION_LIMIT_LOCK = threading.Lock()

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def _get_weasyprint_runtime():
    """Import WeasyPrint lazily so non-PDF startup paths stay clean."""
    import_module("src.services.infrastructure.weasyprint_env")
    try:
        from weasyprint import HTML
        from weasyprint.text.fonts import FontConfiguration

        return HTML, FontConfiguration, None
    except (ImportError, OSError) as e:
        return None, None, e


class PDFGenerator:
    """
    Handles PDF generation from HTML content
    """

    def __init__(self):
        """Initialize PDF generator"""
        self.logger = logger

    def generate_pdf(
        self,
        html_content: str,
        output_path: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> bytes:
        """
        Generate PDF report from HTML content

        Args:
            html_content: HTML content to convert to PDF
            output_path: Optional path to save PDF file
            base_url: Optional base URL for resolving relative URLs (images, logos)

        Returns:
            PDF bytes

        Raises:
            ImportError: If WeasyPrint is not installed
            Exception: If PDF generation fails
        """
        HTML, FontConfiguration, import_error = _get_weasyprint_runtime()
        if HTML is None:
            err_msg = str(import_error) if import_error else "unknown"
            self.logger.error(
                "WeasyPrint not installed - PDF generation unavailable",
                extra={"import_error": err_msg},
            )
            raise ImportError(
                f"WeasyPrint required for PDF generation. Import failed: {err_msg}. "
                "Install with: pip install weasyprint and ensure system deps: libcairo2 libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libharfbuzz-subset0"
            )

        try:
            # FontConfiguration enables proper @font-face resolution for PDF
            font_config = FontConfiguration() if FontConfiguration else None
            html_doc = HTML(
                string=html_content,
                base_url=base_url,
            )
            # WeasyPrint's CSS variable resolution can recurse deeply with
            # complex stylesheets. Temporarily raise the limit to avoid
            # RecursionError on valid (but nested) CSS.
            with _RECURSION_LIMIT_LOCK:
                old_limit = sys.getrecursionlimit()
                sys.setrecursionlimit(max(old_limit, 5000))
                try:
                    pdf_bytes = html_doc.write_pdf(font_config=font_config)
                finally:
                    sys.setrecursionlimit(old_limit)

            # Save to file if path provided
            if output_path:
                with open(output_path, "wb") as f:
                    f.write(pdf_bytes)
                self.logger.info(f"✅ PDF saved to: {output_path}")

            self.logger.info("✅ PDF generated successfully")
            return pdf_bytes

        except RecursionError as e:
            self.logger.error(
                "WeasyPrint recursion limit exceeded - HTML/CSS may be too complex",
                extra={"error": str(e)},
                exc_info=True,
            )
            raise  # Re-raise so caller can catch and return graceful fallback
        except DataValidationError as e:
            self.logger.error(f"Error generating PDF: {e}", exc_info=True)
            raise Exception(f"Failed to generate PDF: {e}") from e

    def is_available(self) -> bool:
        """
        Check if PDF generation is available

        Returns:
            True if WeasyPrint is installed, False otherwise
        """
        HTML, _, _ = _get_weasyprint_runtime()
        return HTML is not None

    def generate_pdf_from_html(
        self, html_content: str, valuation_id: str, company_name: str
    ) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Generate PDF from HTML content and return bytes and base64 string.

        Args:
            html_content: HTML content to convert to PDF
            valuation_id: Valuation ID for logging
            company_name: Company name for logging

        Returns:
            Tuple of (pdf_bytes, pdf_base64)
            - pdf_bytes: Raw PDF bytes for direct use
            - pdf_base64: Base64 encoded string for API response
            Returns (None, None) if PDF generation fails

        ARCHITECTURE:
            ValuationIQ generates PDF bytes and base64 encodes them.
            Titan API receives the base64 string, decodes, and stores in Supabase Storage.
            Titan generates the pdf_url and returns to frontend.
        """
        try:
            # Validate HTML content
            if not html_content or len(html_content) < 100:
                self.logger.warning(
                    "HTML content too short for PDF generation",
                    extra={
                        "valuation_id": valuation_id,
                        "company_name": company_name,
                        "html_length": len(html_content) if html_content else 0,
                    },
                )
                return (None, None)

            # Generate PDF bytes using WeasyPrint
            pdf_bytes = self.generate_pdf(html_content)

            # Base64 encode for API response
            pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

            self.logger.info(
                "✅ PDF generated successfully - returning bytes for Titan storage",
                extra={
                    "valuation_id": valuation_id,
                    "company_name": company_name,
                    "pdf_size_bytes": len(pdf_bytes),
                    "pdf_base64_length": len(pdf_base64),
                },
            )

            return (pdf_bytes, pdf_base64)

        except RecursionError as e:
            self.logger.error(
                "PDF generation failed: WeasyPrint recursion limit (HTML/CSS too complex)",
                extra={
                    "valuation_id": valuation_id,
                    "company_name": company_name,
                    "error": str(e),
                },
                exc_info=True,
            )
            return (None, None)
        except Exception as e:
            self.logger.error(
                f"Error generating PDF from HTML: {e}",
                extra={
                    "valuation_id": valuation_id,
                    "company_name": company_name,
                },
                exc_info=True,
            )
            return (None, None)


# Global instance
_pdf_generator: Optional[PDFGenerator] = None


def get_pdf_generator() -> PDFGenerator:
    """Get global PDF generator instance"""
    global _pdf_generator
    if _pdf_generator is None:
        _pdf_generator = PDFGenerator()
    return _pdf_generator
