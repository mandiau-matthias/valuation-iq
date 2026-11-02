"""
PDF Generation Strategy

BANK-GRADE: Rocket-grade PDF generation with independent failure isolation,
circuit breaker protection, retry mechanisms, and comprehensive observability.

RESPONSIBILITIES:
- Generate Accountant View PDF reports from HTML content
- Handle PDF conversion with WeasyPrint
- Provide fallback PDF generation when primary fails
- Track metrics and health status
"""

import asyncio
import re
import threading
from datetime import datetime
from html import escape
from typing import Any, Dict, Mapping, Optional

from src.services.infrastructure.report_generation.circuit_breaker import CircuitState
from src.services.infrastructure.report_generation.config import ReportGenerationConfig
from src.services.infrastructure.report_generation.metrics_collector import MetricsCollector
from src.services.infrastructure.report_generation.strategies.base_report_strategy import (
    BaseReportStrategy,
)

# PDF Enhancement Services
try:
    from src.services.infrastructure.pdf import (
        FontManager,
        PDFEnhancer,
        PDFPermissions,
        PDFSecurityService,
        PDFValidator,
    )
    from src.services.infrastructure.pdf.pdfa_postprocessor import (
        normalize_pdfa_image_interpolation,
    )

    PDF_ENHANCEMENT_AVAILABLE = True
except ImportError:
    PDF_ENHANCEMENT_AVAILABLE = False
    FontManager = None
    PDFEnhancer = None
    PDFSecurityService = None
    PDFPermissions = None
    PDFValidator = None
    normalize_pdfa_image_interpolation = None

# Configure env before first weasyprint import (suppresses fontTools/WeasyPrint warnings)
import src.services.infrastructure.weasyprint_env  # noqa: F401

# Check WeasyPrint availability (OSError = missing system libs e.g. cairo, pango)
try:
    from weasyprint import HTML as WeasyPrintHTML
    from weasyprint import URLFetcher
    from weasyprint.text.fonts import FontConfiguration

    WEASYPRINT_AVAILABLE = True
    WEASYPRINT_IMPORT_ERROR = None
except (ImportError, OSError) as e:
    WEASYPRINT_AVAILABLE = False
    WEASYPRINT_IMPORT_ERROR = e
    WeasyPrintHTML = None
    URLFetcher = None
    FontConfiguration = None


_RECURSION_LIMIT_LOCK = threading.Lock()


def _build_archival_url_fetcher() -> object:
    """Return a fail-closed fetcher for immutable, network-isolated renders."""

    if URLFetcher is None:
        raise RuntimeError("WeasyPrint URL fetcher is unavailable")

    from urllib.parse import urlsplit

    class LocalArchivalURLFetcher(URLFetcher):
        def fetch(self, url: str, headers: object = None) -> object:
            scheme = urlsplit(url).scheme.lower()
            if scheme not in {"data", "file"}:
                raise ValueError(
                    f"Archival PDF rendering prohibits the {scheme or 'relative'} URL scheme"
                )
            return super().fetch(url, headers=headers)

    return LocalArchivalURLFetcher(
        timeout=10,
        allow_redirects=False,
        fail_on_errors=True,
    )


def _inject_archival_html_metadata(
    html_content: str, template_data: Optional[Mapping[str, object]]
) -> str:
    """Bind native WeasyPrint XMP dates to the immutable run timestamp.

    WeasyPrint maps ``dcterms.created`` and ``dcterms.modified`` HTML metadata
    into the PDF/A XMP packet. Supplying the sealed timestamp before rendering
    avoids a second metadata-authoring pass and preserves deterministic bytes.
    """

    timestamp = str((template_data or {}).get("artifact_timestamp") or "").strip()
    if not timestamp:
        raise ValueError("Archival PDF rendering requires artifact_timestamp")
    head_close = re.search(r"</head\s*>", html_content, flags=re.IGNORECASE)
    if head_close is None:
        raise ValueError("Archival PDF HTML requires a closing </head> element")
    escaped_timestamp = escape(timestamp, quote=True)
    metadata = (
        f'<meta name="dcterms.created" content="{escaped_timestamp}">'
        f'<meta name="dcterms.modified" content="{escaped_timestamp}">'
    )
    return html_content[: head_close.start()] + metadata + html_content[head_close.start() :]


class PDFGenerationStrategy(BaseReportStrategy):
    """
    Strategy for generating PDF reports from HTML content.

    BANK-GRADE FEATURES:
    - Independent failure isolation (doesn't affect HTML generation)
    - Circuit breaker protection
    - Retry with exponential backoff
    - Timeout management
    - Graceful degradation with fallback PDF
    - Comprehensive metrics and observability
    """

    def __init__(
        self,
        logger_instance=None,
        metrics_collector: Optional[MetricsCollector] = None,
    ):
        """
        Initialize PDF generation strategy.

        Args:
            logger_instance: Logger instance (optional)
            metrics_collector: Metrics collector instance (optional)
        """
        super().__init__(
            logger_instance=logger_instance,
            metrics_collector=metrics_collector,
        )
        self.report_type = "pdf"
        self.weasyprint_available = WEASYPRINT_AVAILABLE
        self.pdf_enhancement_available = PDF_ENHANCEMENT_AVAILABLE

        if not self.weasyprint_available:
            err_msg = str(WEASYPRINT_IMPORT_ERROR) if WEASYPRINT_IMPORT_ERROR else "unknown"
            self.logger.warning(
                "⚠️ [PDF-STRATEGY] WeasyPrint not available - PDF generation will fail",
                extra={
                    "weasyprint_available": False,
                    "import_error": err_msg,
                    "error_type": (
                        type(WEASYPRINT_IMPORT_ERROR).__name__ if WEASYPRINT_IMPORT_ERROR else None
                    ),
                },
            )

        # Initialize PDF enhancement services
        if self.pdf_enhancement_available:
            try:
                self.font_manager = FontManager()
                self.pdf_enhancer = PDFEnhancer()  # Will auto-detect ICC profile
                self.pdf_security = PDFSecurityService()
                self.pdf_validator = PDFValidator()
                self.logger.debug("✅ [PDF-STRATEGY] PDF enhancement services initialized")
            except Exception as e:
                self.logger.warning(
                    f"⚠️ [PDF-STRATEGY] PDF enhancement initialization failed: {e}",
                    extra={"error": str(e)},
                )
                self.pdf_enhancement_available = False
        else:
            self.logger.warning("⚠️ [PDF-STRATEGY] PDF enhancement not available - basic PDF only")

    def get_report_type(self) -> str:
        """Return report type name."""
        return "PDF"

    def get_timeout_seconds(self) -> float:
        """Return timeout for PDF generation."""
        return ReportGenerationConfig.PDF_CONVERSION_TIMEOUT_SECONDS

    def get_min_content_length(self) -> int:
        """Return minimum content length (not applicable for PDF)."""
        return ReportGenerationConfig.MIN_PDF_SIZE_BYTES

    async def generate(
        self,
        html_content: str,
        template_data: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ) -> Optional[bytes]:
        """
        Generate PDF from HTML content.

        BANK-GRADE: Full error handling, circuit breaker, retry, timeout.

        Args:
            html_content: HTML content to convert to PDF
            template_data: Optional template data for metadata
            correlation_id: Optional correlation ID for tracing

        Returns:
            PDF bytes, or None if generation fails
        """
        if not self.weasyprint_available:
            self.logger.error(
                "❌ [PDF-STRATEGY] WeasyPrint not available",
                extra={
                    "correlation_id": correlation_id,
                    "weasyprint_available": False,
                },
            )
            return None

        if not html_content or len(html_content) < 100:
            self.logger.error(
                "❌ [PDF-STRATEGY] Invalid HTML content",
                extra={
                    "correlation_id": correlation_id,
                    "html_length": len(html_content) if html_content else 0,
                    "minimum_required": 100,
                },
            )
            return None

        loop = asyncio.get_running_loop()
        start_time = loop.time()

        try:
            # BANK-GRADE: Check circuit breaker before attempting generation
            if self.circuit_breaker.get_state() == CircuitState.OPEN:
                self.logger.warning(
                    "⚠️ [PDF-STRATEGY] Circuit breaker is OPEN - skipping PDF generation",
                    extra={
                        "correlation_id": correlation_id,
                        "circuit_state": "OPEN",
                    },
                )
                self.metrics_collector.record_circuit_breaker_open(self.report_type)
                return None

            # BANK-GRADE: Retry wrapper with exponential backoff
            async def _generate_with_retry():
                return await self._convert_html_to_pdf(
                    html_content,
                    template_data,
                    correlation_id,
                )

            pdf_bytes = await self.retry_handler.retry_async(
                _generate_with_retry,
                context={"operation_name": "pdf_generation", "correlation_id": correlation_id},
            )

            if pdf_bytes:
                duration = loop.time() - start_time
                self.metrics_collector.record_success(
                    self.report_type,
                    duration,
                )
                self.circuit_breaker._record_success()

                self.logger.info(
                    "✅ [PDF-STRATEGY] PDF generated successfully",
                    extra={
                        "correlation_id": correlation_id,
                        "pdf_size_bytes": len(pdf_bytes),
                        "pdf_size_kb": round(len(pdf_bytes) / 1024, 2),
                        "duration_seconds": round(duration, 3),
                    },
                )
                return pdf_bytes
            else:
                duration = loop.time() - start_time
                self.metrics_collector.record_failure(
                    self.report_type,
                    "pdf_generation_failed",
                    duration,
                )
                self.circuit_breaker._record_failure()
                return None

        except Exception as e:
            duration = loop.time() - start_time
            self.metrics_collector.record_failure(
                self.report_type,
                type(e).__name__,
                duration,
            )
            self.circuit_breaker._record_failure()

            self.logger.error(
                "❌ [PDF-STRATEGY] PDF generation failed",
                extra={
                    "correlation_id": correlation_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "duration_seconds": round(duration, 3),
                },
                exc_info=True,
            )
            return None

    async def _convert_html_to_pdf(
        self,
        html_content: str,
        template_data: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ) -> Optional[bytes]:
        """
        Convert HTML content to PDF using WeasyPrint.

        BANK-GRADE: Timeout protection, error handling.

        Args:
            html_content: HTML content to convert
            template_data: Optional template data for metadata
            correlation_id: Optional correlation ID

        Returns:
            PDF bytes, or None if conversion fails
        """
        try:
            # BANK-GRADE: Timeout protection for PDF conversion
            pdf_bytes = await asyncio.wait_for(
                self._weasyprint_convert(html_content, template_data),
                timeout=ReportGenerationConfig.PDF_CONVERSION_TIMEOUT_SECONDS,
            )

            if not pdf_bytes or len(pdf_bytes) == 0:
                self.logger.error(
                    "❌ [PDF-STRATEGY] PDF conversion returned empty bytes",
                    extra={"correlation_id": correlation_id},
                )
                return None

            # BANK-GRADE: Validate PDF size (should be reasonable)
            if len(pdf_bytes) < ReportGenerationConfig.MIN_PDF_SIZE_BYTES:
                self.logger.warning(
                    "⚠️ [PDF-STRATEGY] PDF size suspiciously small",
                    extra={
                        "correlation_id": correlation_id,
                        "pdf_size_bytes": len(pdf_bytes),
                        "minimum_expected": ReportGenerationConfig.MIN_PDF_SIZE_BYTES,
                    },
                )

            return pdf_bytes

        except asyncio.TimeoutError:
            self.logger.error(
                "❌ [PDF-STRATEGY] PDF conversion timed out",
                extra={
                    "correlation_id": correlation_id,
                    "timeout_seconds": ReportGenerationConfig.PDF_CONVERSION_TIMEOUT_SECONDS,
                },
            )
            raise
        except RecursionError as e:
            self.logger.error(
                "❌ [PDF-STRATEGY] WeasyPrint recursion limit - HTML/CSS too complex",
                extra={
                    "correlation_id": correlation_id,
                    "error": str(e),
                },
                exc_info=True,
            )
            return None  # Graceful fallback: valuation completes without PDF
        except Exception as e:
            self.logger.error(
                "❌ [PDF-STRATEGY] PDF conversion failed",
                extra={
                    "correlation_id": correlation_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def _weasyprint_convert(
        self,
        html_content: str,
        template_data: Optional[Dict[str, Any]] = None,
    ) -> bytes:
        """
        Convert HTML to PDF using WeasyPrint with bank-grade enhancements.

        Applies professional PDF features:
        - PDF/A-3 archival compliance
        - Unrestricted copy, print and accessibility permissions
        - Enhanced metadata and bookmarks
        - Accessibility tags
        - Validation checks

        Args:
            html_content: HTML content
            template_data: Optional template data for metadata

        Returns:
            Enhanced PDF bytes
        """
        loop = asyncio.get_running_loop()

        def _convert():
            """Synchronous PDF conversion with enhancement pipeline."""
            try:
                # Step 1: Generate raw PDF with WeasyPrint
                import sys

                base_url = template_data.get("base_url") if template_data else None
                font_config = FontConfiguration() if FontConfiguration is not None else None
                with _RECURSION_LIMIT_LOCK:
                    old_limit = sys.getrecursionlimit()
                    sys.setrecursionlimit(max(old_limit, 5000))
                    try:
                        archival_pdfa = bool((template_data or {}).get("archival_pdfa"))
                        url_fetcher = (
                            _build_archival_url_fetcher()
                            if archival_pdfa
                            else URLFetcher(timeout=10, fail_on_errors=False)
                        )
                        render_html = (
                            _inject_archival_html_metadata(html_content, template_data)
                            if archival_pdfa
                            else html_content
                        )
                        pdf_doc = WeasyPrintHTML(
                            string=render_html,
                            base_url=base_url,
                            url_fetcher=url_fetcher,
                        )
                        artifact_identifier = str(
                            (template_data or {}).get("artifact_identifier") or ""
                        ).strip()
                        raw_pdf_bytes = pdf_doc.write_pdf(
                            font_config=font_config,
                            # FontTools' subset compiler carries volatile font
                            # table state even when glyphs render identically.
                            # Archival runs embed the deterministic bundled font
                            # binaries in full and pin the PDF identifier to the
                            # sealed run hash.
                            full_fonts=archival_pdfa,
                            pdf_identifier=(
                                artifact_identifier.encode("ascii")
                                if archival_pdfa and artifact_identifier
                                else None
                            ),
                            # Native WeasyPrint conformance is the archival
                            # authority. The old pikepdf enhancer stamped a
                            # PDF/A-3 claim after rendering and could mutate an
                            # otherwise deterministic artifact.
                            pdf_variant="pdf/a-2b" if archival_pdfa else None,
                            pdf_tags=archival_pdfa,
                            # Presentational hints are intentionally disabled.
                            # Besides keeping sealed rendering deterministic,
                            # this is the mandatory containment for the
                            # WeasyPrint 68 advisory recorded in the owned risk
                            # acceptance under docs/security/.
                            presentational_hints=False,
                            srgb=archival_pdfa,
                        )
                    finally:
                        sys.setrecursionlimit(old_limit)

                self.logger.debug(
                    "✅ [PDF-STRATEGY] Raw PDF generated", extra={"size_bytes": len(raw_pdf_bytes)}
                )

                # WeasyPrint emits the native PDF/A structure. It can still set
                # `/Interpolate true` on raster images, which ISO 19005-2
                # forbids. Apply only that deterministic object-level repair;
                # independent veraPDF validation remains the publication gate.
                archival_pdfa = bool((template_data or {}).get("archival_pdfa"))
                if archival_pdfa:
                    if not self.pdf_enhancement_available:
                        raise RuntimeError("PDF/A validation dependencies are unavailable")
                    raw_pdf_bytes, repaired_images = normalize_pdfa_image_interpolation(
                        raw_pdf_bytes
                    )
                    if repaired_images:
                        self.logger.debug(
                            "✅ [PDF-STRATEGY] Disabled forbidden PDF/A image interpolation",
                            extra={"image_count": repaired_images},
                        )
                    validation = self.pdf_validator.validate_pdf(raw_pdf_bytes)
                    if not validation.is_valid_pdfa:
                        raise RuntimeError(
                            "Canonical archival PDF failed the PDF/A-2b validation gate: "
                            + "; ".join(validation.errors)
                        )
                    return raw_pdf_bytes

                # If enhancement not available, return raw PDF
                if not self.pdf_enhancement_available:
                    return raw_pdf_bytes

                # Enhancement pipeline: metadata, bookmarks, encryption, validation.
                # Failures propagate so PDF generation fails with clear errors (no silent fallback).
                # Step 2: Build metadata
                metadata = self._build_metadata(template_data)
                # The HTML document is the render authority for language.  The
                # generic strategy can be invoked without a full template
                # context, so reading its declared ``lang`` avoids shipping a
                # Dutch/French report with English accessibility metadata.
                declared_language = re.search(
                    r"<html\b[^>]*\blang=[\"']([^\"']+)[\"']",
                    html_content,
                    flags=re.IGNORECASE,
                )
                if declared_language:
                    language = declared_language.group(1).strip().lower()
                    metadata["language"] = (
                        "nl-BE"
                        if language.startswith("nl")
                        else "fr-BE" if language.startswith("fr") else "en-US"
                    )

                # Step 3: Extract TOC structure for bookmarks
                toc_structure = self._extract_toc_structure(html_content)

                # Step 4: Enhance PDF (metadata, color profile, bookmarks)
                enhanced_pdf = self.pdf_enhancer.enhance_pdf(
                    raw_pdf_bytes=raw_pdf_bytes,
                    metadata=metadata,
                    toc_structure=toc_structure,
                )

                self.logger.debug(
                    "✅ [PDF-STRATEGY] PDF enhanced with metadata and bookmarks",
                    extra={
                        "bookmark_count": len(toc_structure) if toc_structure else 0,
                    },
                )

                # Ordinary reports must support copying, printing and accessibility without
                # an undisclosed owner password. Access is enforced at the download endpoint.
                # Archival artifacts keep their existing conformance validation gate.
                archival_pdfa = bool((template_data or {}).get("archival_pdfa"))
                secured_pdf = enhanced_pdf

                # Step 6: Validate PDF quality
                validation = self.pdf_validator.validate_pdf(secured_pdf)

                if not validation.is_valid_pdfa:
                    self.logger.warning(
                        "⚠️ [PDF-STRATEGY] PDF/A validation warnings",
                        extra={
                            "errors": validation.errors,
                            "warnings": validation.warnings,
                        },
                    )
                    if archival_pdfa:
                        raise RuntimeError(
                            "Canonical archival PDF failed the PDF/A validation gate"
                        )
                else:
                    self.logger.debug("✅ [PDF-STRATEGY] PDF/A-3 compliant")

                if validation.is_valid_pdfua:
                    self.logger.debug("✅ [PDF-STRATEGY] PDF/UA accessible")

                return secured_pdf

            except Exception as e:
                self.logger.error(
                    "❌ [PDF-STRATEGY] PDF conversion or enhancement error",
                    extra={
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    },
                    exc_info=True,
                )
                raise

        # Run in executor to avoid blocking event loop
        return await loop.run_in_executor(None, _convert)

    def _build_metadata(self, template_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Build enhanced metadata for PDF.

        Args:
            template_data: Template data with company info

        Returns:
            Metadata dictionary
        """
        metadata = {
            "author": "Upswitch Valuation Services",
            "subject": "SME Business Valuation Report",
            "keywords": "valuation, business, SME, financial analysis",
            "description": "Professional business valuation report with comprehensive financial analysis",
            "language": "en-US",
        }

        if template_data:
            company_name = template_data.get("company_name", "Unknown Company")
            valuation_date = template_data.get("valuation_date", datetime.now().date())
            company_id = template_data.get("company_id", "")

            metadata["title"] = f"Business Valuation Report - {company_name}"
            metadata["valuation_date"] = (
                valuation_date.strftime("%Y-%m-%d")
                if hasattr(valuation_date, "strftime")
                else str(valuation_date)
            )
            metadata["company_id"] = company_id
            metadata["artifact_timestamp"] = template_data.get("artifact_timestamp")
            locale = str(template_data.get("locale") or "en").lower()
            metadata["language"] = (
                "nl-BE"
                if locale.startswith("nl")
                else "fr-BE" if locale.startswith("fr") else "en-US"
            )
        else:
            metadata["title"] = "Business Valuation Report"
            metadata["valuation_date"] = datetime.now().strftime("%Y-%m-%d")
            metadata["company_id"] = ""

        return metadata

    def _extract_toc_structure(self, html_content: str) -> Optional[list]:
        """
        Extract table of contents structure from HTML for bookmarks.

        Args:
            html_content: HTML content with section headers

        Returns:
            List of TOC items with title, page (estimated), level
        """
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html_content, "html.parser")
            toc_structure = []

            # Find all headers with IDs (section markers)
            headers = soup.find_all(["h1", "h2", "h3"], id=True)

            for idx, header in enumerate(headers):
                # Determine level from tag
                level = int(header.name[1])  # h1 -> 1, h2 -> 2, etc.

                # Get title text
                title = header.get_text(strip=True)

                # Estimate page number (rough heuristic)
                # In reality, WeasyPrint doesn't expose page numbers before rendering
                # For now, use sequential page numbers
                page = idx + 2  # Start from page 2 (after cover)

                toc_structure.append(
                    {
                        "title": title,
                        "page": page,
                        "level": level,
                    }
                )

            return toc_structure if toc_structure else None

        except Exception as e:
            self.logger.warning(f"⚠️ [PDF-STRATEGY] Could not extract TOC structure: {e}")
            return None

    def generate_fallback_pdf(
        self,
        error_message: str,
        template_data: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ) -> Optional[bytes]:
        """
        DEPRECATED — Intentionally disabled.

        Previously generated a fallback PDF containing an error message.
        This caused a critical bug: the error PDF was indistinguishable from a
        real report (returned with 200 OK), bypassed Titan's validation
        (content is zlib-compressed), got cached, and was served to users as
        their valuation report.

        Callers should propagate the error via an HTTP error response instead
        of masquerading it as a valid PDF.
        """
        self.logger.error(
            "❌ [PDF-STRATEGY] generate_fallback_pdf called — this method is "
            "disabled. Raising instead of producing an error PDF.",
            extra={
                "correlation_id": correlation_id,
                "error_message": error_message,
            },
        )
        raise RuntimeError(
            f"PDF generation failed: {error_message} " f"(correlation_id={correlation_id})"
        )
