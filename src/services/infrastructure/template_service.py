"""
Template Service for PDF Report Generation
Adapted from Ilara Artemis template engine

Generates professional valuation reports with:
- Executive summary
- Financial analysis
- Market insights
- Valuation calculations
- Risk assessment

Uses Jinja2 templates + WeasyPrint for PDF generation
"""

from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Literal, Optional

try:
    from jinja2 import TemplateError, TemplateNotFound, TemplateSyntaxError, UndefinedError

    JINJA_AVAILABLE = True
except ImportError:
    JINJA_AVAILABLE = False
    TemplateError = Exception
    UndefinedError = Exception
    TemplateSyntaxError = Exception
    TemplateNotFound = Exception


from src.services.infrastructure.exceptions import TemplateRenderingError
from src.services.infrastructure.pdf_generator import PDFGenerator
from src.services.infrastructure.template.coordinators import (
    DataValidationCoordinator,
    PDFGenerationCoordinator,
    ReportRenderingCoordinator,
    TemplateInitializationCoordinator,
)

# Import specialized services for SRP compliance
from src.services.infrastructure.template.services import (
    TemplateConfigurationService,
    TemplateDataTransformer,
    TemplateRenderingService,
    TemplateVersionService,
)
from src.services.infrastructure.template_fallback_html import generate_fallback_html
from src.services.infrastructure.template_formatter import TemplateFormatter
from src.services.infrastructure.template_main_report_context import prepare_main_report_context
from src.utils.logging import get_logger

logger = get_logger(__name__)


class TemplateService:
    """
    Template service for valuation report generation (REFACTORED FOR SRP).

    SINGLE RESPONSIBILITY: Coordinate template operations by delegating to specialized services.

    REFACTORED ARCHITECTURE:
    - TemplateConfigurationService: Jinja2 environment setup
    - TemplateDataTransformer: Data transformation for templates
    - TemplateRenderingService: Template rendering
    - TemplateVersionService: Template version tracking

    This class now acts as a FACADE, maintaining backward compatibility
    while delegating to specialized SRP-compliant services.

    SOLID PRINCIPLES:
    - SRP: Each service has ONE responsibility
    - OCP: Easy to extend with new services
    - DIP: Depend on service abstractions
    """

    def __init__(self, templates_dir: Optional[str] = None):
        self.logger = get_logger(__name__)

        # Initialize specialized services (SRP-compliant)
        self.config_service = TemplateConfigurationService(templates_dir)
        self.data_transformer = TemplateDataTransformer()
        self.rendering_service = TemplateRenderingService()

        # Use the configuration service as the single source of truth for
        # template root resolution so startup cannot split across two directories.
        self.templates_dir = self.config_service.get_templates_directory()
        self.version_service = TemplateVersionService(self.templates_dir)

        # Check if templates directory exists
        if not self.templates_dir.exists():
            self.logger.warning(f"Templates directory not found: {self.templates_dir}")
            self.templates_dir.mkdir(parents=True, exist_ok=True)

        # Initialize formatter and PDF generator
        self.formatter = TemplateFormatter()
        self.pdf_generator = PDFGenerator()

        # Initialize Jinja2 environment from the configuration service so
        # TemplateService stays a facade instead of duplicating renderer setup.
        if JINJA_AVAILABLE:
            self.config_service.register_filters(self.formatter)
            self.env = self.config_service.get_environment()
            self.logger.debug(
                f"✅ Template service initialized with directory: {self.templates_dir}"
            )
        else:
            self.logger.warning("⚠️ Jinja2 not installed - template service in fallback mode")
            self.env = None  # Ensure env exists for fallback path (tests expect hasattr check)

        # Keep SRP rendering service aligned with the active Jinja environment.
        self.rendering_service.env = self.env

        # Cache for validation results
        self._validation_cache = {}

        # Initialize coordinators (after env is set up)
        self.template_init_coordinator = TemplateInitializationCoordinator(
            self.templates_dir, self.env, self.logger
        )
        self.data_validation_coordinator = DataValidationCoordinator(self.logger)

        # Create default templates only when the directory truly has no templates at all.
        if not self.templates_dir.exists() or not list(self.templates_dir.rglob("*.html")):
            self.template_init_coordinator.create_default_templates()

        # Preload common templates
        if JINJA_AVAILABLE:
            self.template_init_coordinator.preload_common_templates()

        # Initialize rendering coordinator (needs fallback HTML function)
        self.report_rendering_coordinator = ReportRenderingCoordinator(
            self.templates_dir, self.env, self._generate_fallback_html, self.logger
        )

        self._pdf_generation_coordinator = PDFGenerationCoordinator(
            self.pdf_generator,
            self.render_accountant_view_report,
            self.logger,
            jinja_available_provider=lambda: JINJA_AVAILABLE,
        )

    @staticmethod
    def _has_launch_ready_templates(path: Path) -> bool:
        """Check whether a template directory supports the launch-critical report path."""
        required_templates = [
            path / "main_report" / "master_report.html",
            path / "main_report_pdf" / "master_report.html",
        ]
        return all(template.exists() and template.is_file() for template in required_templates)

    def render_valuation_report(
        self, valuation_data: Dict[str, Any], template_name: str = "valuation_report.html"
    ) -> str:
        """
        Render valuation report HTML from template

        Args:
            valuation_data: Valuation data dictionary
            template_name: Template filename

        Returns:
            Rendered HTML string
        """
        if not JINJA_AVAILABLE:
            self.logger.error("Jinja2 not installed - cannot render template")
            return self._generate_fallback_html(valuation_data)

        try:
            render_context = self._convert_dates_to_strings(valuation_data)
            template = self.env.get_template(template_name)

            # Render against a local copy so callers can safely reuse the same
            # input dict across retries or concurrent render flows.
            render_context["generation_timestamp"] = datetime.now(timezone.utc).isoformat()

            html = template.render(**render_context)

            self.logger.info(f"✅ Rendered template: {template_name}")
            return html

        except (KeyError, AttributeError, TypeError) as e:
            self.logger.warning(f"Template data error: {e}")
            return self._generate_fallback_html(valuation_data)
        except TemplateRenderingError as e:
            self.logger.error(f"Template rendering failed: {e}", exc_info=True)
            raise TemplateRenderingError(
                f"Failed to render template {template_name}: {e}",
                company_name=valuation_data.get("company_name"),
            ) from e

    def generate_pdf(
        self,
        valuation_data: Dict[str, Any],
        output_path: Optional[str] = None,
        template_name: str = "valuation_report.html",
    ) -> bytes:
        """
        Generate PDF report from valuation data

        Args:
            valuation_data: Valuation data dictionary
            output_path: Optional path to save PDF file
            template_name: Template filename

        Returns:
            PDF bytes
        """
        try:
            # Render HTML
            html_content = self.render_valuation_report(valuation_data, template_name)

            # Generate PDF using PDF generator
            return self.pdf_generator.generate_pdf(html_content, output_path)

        except TemplateRenderingError:
            raise

    def _generate_fallback_html(self, valuation_data: Dict[str, Any]) -> str:
        """Generate fallback HTML when templates unavailable."""
        return generate_fallback_html(valuation_data)

    def _convert_dates_to_strings(self, data: Any) -> Any:
        """
        Recursively convert all date and datetime objects to ISO format strings.

        Delegates to DateConverter module.
        """
        from src.services.infrastructure.template_service_modular.converters import DateConverter

        return DateConverter.convert_dates_to_strings(data)

    def _get_template_version_metadata(self) -> Dict[str, Any]:
        """Get template version metadata for reproducibility."""
        return self.version_service.get_accountant_view_version_metadata()

    def render_accountant_view_report(self, valuation_data: Dict[str, Any]) -> str:
        """
        Render Accountant View report HTML from templates.

        Combines all section templates into a single report.

        BANK-GRADE: Includes template version metadata for reproducibility.

        Args:
            valuation_data: Transformed valuation data dictionary

        Returns:
            Rendered HTML string with all sections
        """
        # CRITICAL: Convert date/datetime objects to strings before any logging or validation
        # This prevents JSON serialization errors in the logger
        valuation_data = self._convert_dates_to_strings(valuation_data)

        # BANK-GRADE: Add template version metadata for reproducibility
        if "template_metadata" not in valuation_data:
            valuation_data["template_metadata"] = self._get_template_version_metadata()

        # Validate input data before rendering using DataValidationCoordinator
        try:
            self.data_validation_coordinator.validate_accountant_view_data(valuation_data)

            # Add academic references to appendices
            from src.services.infrastructure.academic_references import get_references_for_report

            if "appendices" in valuation_data and valuation_data["appendices"] is not None:
                valuation_data["appendices"]["academic_references"] = get_references_for_report()
            elif "appendices" not in valuation_data or valuation_data["appendices"] is None:
                # Initialize appendices as empty dict if None or missing
                valuation_data["appendices"] = {"academic_references": get_references_for_report()}

            # Render report using ReportRenderingCoordinator
            return self.report_rendering_coordinator.render_accountant_view_report(valuation_data)

        except (
            TemplateError,
            UndefinedError,
            TemplateSyntaxError,
            TemplateNotFound,
        ) as jinja_error:
            # BANK-GRADE: Catch Jinja2-specific template errors
            error_type = type(jinja_error).__name__
            error_msg = str(jinja_error)

            logger.error(
                "❌ REPORT GENERATION FAILED - Jinja2 Template Error",
                extra={
                    "error_type": error_type,
                    "error_message": error_msg,
                    "company_name": valuation_data.get("company_name", "N/A"),
                    "templates_directory": (
                        str(self.templates_dir) if hasattr(self, "templates_dir") else "N/A"
                    ),
                    "jinja_available": JINJA_AVAILABLE,
                    "error_category": "jinja2_template_error",
                },
                exc_info=True,
            )
            raise TemplateRenderingError(
                f"HTML report generation failed - Jinja2 {error_type}: {error_msg}",
                company_name=valuation_data.get("company_name"),
            ) from jinja_error
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            error_type = type(e).__name__
            error_msg = str(e)

            # If env is None or AttributeError related to env, generate fallback HTML
            if not self.env or (isinstance(e, AttributeError) and "env" in error_msg.lower()):
                logger.warning(
                    "Template environment unavailable - generating fallback HTML",
                    extra={
                        "error_type": error_type,
                        "error_message": error_msg,
                        "company_name": valuation_data.get("company_name", "N/A"),
                    },
                )
                return self._generate_fallback_html(valuation_data)

            logger.error(
                "❌ REPORT GENERATION FAILED - Data/Type Error",
                extra={
                    "error_type": error_type,
                    "error_message": error_msg,
                    "company_name": valuation_data.get("company_name", "N/A"),
                    "templates_directory": (
                        str(self.templates_dir) if hasattr(self, "templates_dir") else "N/A"
                    ),
                    "jinja_available": JINJA_AVAILABLE,
                },
                exc_info=True,
            )
            raise TemplateRenderingError(
                f"HTML report generation failed: {error_msg}",
                company_name=valuation_data.get("company_name"),
            ) from e

    def render_simplified_report(self, valuation_data: Dict[str, Any]) -> str:
        """
        Render simplified 5-page HTML report from template.

        NEW: This replaces the complex accountant view with a streamlined
        5-page report matching the React template design.

        Pages:
        1. Cover Page - Company, valuation headline
        2. Executive Summary - Key metrics, sensitivity
        3. EBITDA Normalization - Adjustments table
        4. Valuation Calibration - Multiple derivation
        5. Disclaimers - Legal notices

        Args:
            valuation_data: Context dictionary from SimplifiedReportTransformer

        Returns:
            Rendered HTML string
        """
        # DEBUG: render-entry breadcrumb; the success line below carries the result.
        logger.debug(
            "🔍 [TEMPLATE-SERVICE] Rendering simplified report",
            extra={
                "company_name": valuation_data.get("company_name", "N/A"),
                "valuation_id": valuation_data.get("valuation_id", "N/A"),
            },
        )

        # BANK-GRADE: Convert dates to strings
        valuation_data = self._convert_dates_to_strings(valuation_data)

        try:
            # Load and render the simplified report template
            template = self.env.get_template("simplified_report/main_report.html")
            html_content = template.render(**valuation_data)

            # DEBUG: render-success plumbing; the caller's AUDIT line is the canonical exit.
            logger.debug(
                "✅ [TEMPLATE-SERVICE] Simplified report rendered successfully",
                extra={
                    "company_name": valuation_data.get("company_name", "N/A"),
                    "html_length": len(html_content) if html_content else 0,
                },
            )

            return html_content

        except (TemplateError, UndefinedError, TemplateSyntaxError, TemplateNotFound) as e:
            error_msg = str(e)
            logger.error(
                "❌ [TEMPLATE-SERVICE] Simplified report rendering failed - Jinja2 error",
                extra={
                    "company_name": valuation_data.get("company_name", "N/A"),
                    "error_type": type(e).__name__,
                    "error_message": error_msg,
                },
                exc_info=True,
            )
            raise TemplateRenderingError(
                f"Simplified report generation failed: {error_msg}",
                company_name=valuation_data.get("company_name"),
            ) from e
        except Exception as e:
            logger.error(
                "❌ [TEMPLATE-SERVICE] Simplified report rendering failed - unexpected error",
                extra={
                    "company_name": valuation_data.get("company_name", "N/A"),
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise TemplateRenderingError(
                f"Simplified report generation failed: {str(e)}",
                company_name=valuation_data.get("company_name"),
            ) from e

    def render_main_report(self, context: Dict[str, Any], locale: str = "nl") -> str:
        """
        Render the 5-page main report from main_report/ templates.

        BANK-GRADE: This is the primary report generation method that replaces
        the complex accountant view with a simplified, data-driven template
        matching the React design.

        Template Structure:
        - main_report/master_report.html (orchestrator)
        - main_report/pages/cover_page.html (Page 1)
        - main_report/pages/executive_summary.html (Page 2)
        - main_report/pages/ebitda_normalization.html (Page 3)
        - main_report/pages/valuation_calibration.html (Page 4)
        - main_report/pages/disclaimers.html (Page 5)

        Supports all 4 methodologies:
        - EBITDA Multiples (default)
        - SDE (Seller's Discretionary Earnings)
        - DCF Analysis
        - Hybrid (Multiples + DCF)

        Supports localization:
        - 'nl' (Dutch) - default, primary language
        - 'en' (English) - secondary language

        Args:
            context: Complete context dictionary from MainReportDataAggregator
            locale: Language code for translations ('nl' or 'en')

        Returns:
            Rendered HTML string (5 A4 pages)
        """
        company_name = context.get("company_name", "N/A")
        report_id = context.get("report_id", "N/A")

        # DEBUG: render-entry breadcrumb; the "rendered successfully" line
        # below carries the result.
        logger.debug(
            "🔍 [TEMPLATE-SERVICE] Rendering main report (5-page template)",
            extra={
                "company_name": company_name,
                "report_id": report_id,
                "context_keys": list(context.keys()),
            },
        )

        context = prepare_main_report_context(
            context,
            locale,
            convert_dates=self._convert_dates_to_strings,
            force_reference_format=True,
        )

        try:
            # Load and render the main report master template
            template = self.env.get_template("main_report/master_report.html")
            html_content = template.render(**context)

            # BANK-GRADE: Validate output
            if not html_content or len(html_content) < 500:
                logger.warning(
                    "⚠️ [TEMPLATE-SERVICE] Main report rendered but content is suspiciously short",
                    extra={
                        "company_name": company_name,
                        "html_length": len(html_content) if html_content else 0,
                    },
                )

            # DEBUG: render-success plumbing; the caller's AUDIT line is the canonical exit.
            logger.debug(
                "✅ [TEMPLATE-SERVICE] Main report rendered successfully",
                extra={
                    "company_name": company_name,
                    "report_id": report_id,
                    "html_length": len(html_content) if html_content else 0,
                    "has_cover_page": "cover-page" in html_content if html_content else False,
                    "page_count": html_content.count("a4-page") if html_content else 0,
                },
            )

            return html_content

        except TemplateNotFound as e:
            logger.error(
                "❌ [TEMPLATE-SERVICE] Main report template not found",
                extra={
                    "company_name": company_name,
                    "missing_template": str(e),
                    "templates_dir": str(self.templates_dir),
                },
                exc_info=True,
            )
            raise TemplateRenderingError(
                f"Main report template not found: {str(e)}", company_name=company_name
            ) from e
        except (TemplateError, UndefinedError, TemplateSyntaxError) as e:
            error_msg = str(e)
            logger.error(
                (
                    "❌ [TEMPLATE-SERVICE] Main report rendering failed - "
                    f"{type(e).__name__}: {error_msg}"
                ),
                extra={
                    "company_name": company_name,
                    "error_type": type(e).__name__,
                    "error_message": error_msg,
                },
                exc_info=True,
            )
            raise TemplateRenderingError(
                f"Main report generation failed: {error_msg}", company_name=company_name
            ) from e
        except Exception as e:
            logger.error(
                "❌ [TEMPLATE-SERVICE] Main report rendering failed - unexpected error",
                extra={
                    "company_name": company_name,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise TemplateRenderingError(
                f"Main report generation failed: {str(e)}", company_name=company_name
            ) from e

    def render_main_report_pdf(self, context: Dict[str, Any], locale: str = "nl") -> str:
        """
        Render the 5-page main report from main_report_pdf/ templates.

        PDF-OPTIMIZED: WeasyPrint-compatible version using table-based layouts
        and hardcoded colors. Use this for PDF generation; keep main_report/
        for screen display (flex, grid, CSS vars).

        Template Structure:
        - main_report_pdf/master_report.html (orchestrator)
        - main_report_pdf/pages/cover_page.html (Page 1)
        - main_report_pdf/pages/executive_summary.html (Page 2)
        - main_report_pdf/pages/ebitda_normalization.html (Page 3)
        - main_report_pdf/pages/valuation_calibration.html (Page 4)
        - main_report_pdf/pages/disclaimers.html (Page 5)

        Args:
            context: Complete context dictionary from MainReportDataAggregator
            locale: Language code for translations ('nl' or 'en')

        Returns:
            Rendered HTML string (5 A4 pages, WeasyPrint-compatible)
        """
        company_name = context.get("company_name", "N/A")
        report_id = context.get("report_id", "N/A")

        # DEBUG: PDF render-entry breadcrumb.
        logger.debug(
            "🔍 [TEMPLATE-SERVICE] Rendering main report PDF (WeasyPrint-optimized)",
            extra={
                "company_name": company_name,
                "report_id": report_id,
                "context_keys": list(context.keys()),
            },
        )

        context = prepare_main_report_context(
            context,
            locale,
            convert_dates=self._convert_dates_to_strings,
            force_reference_format=False,
        )

        try:
            # Load and render the main_report_pdf master template (WeasyPrint-compatible)
            template = self.env.get_template("main_report_pdf/master_report.html")
            html_content = template.render(**context)

            # BANK-GRADE: Validate output
            if not html_content or len(html_content) < 500:
                logger.warning(
                    "⚠️ [TEMPLATE-SERVICE] Main report PDF rendered but content is suspiciously short",
                    extra={
                        "company_name": company_name,
                        "html_length": len(html_content) if html_content else 0,
                    },
                )

            # DEBUG: PDF render-success plumbing; the caller's AUDIT line is the canonical exit.
            logger.debug(
                "✅ [TEMPLATE-SERVICE] Main report PDF rendered successfully",
                extra={
                    "company_name": company_name,
                    "report_id": report_id,
                    "html_length": len(html_content) if html_content else 0,
                    "has_cover_page": "cover-page" in html_content if html_content else False,
                    "page_count": html_content.count("a4-page") if html_content else 0,
                },
            )

            return html_content

        except TemplateNotFound as e:
            logger.error(
                "❌ [TEMPLATE-SERVICE] Main report PDF template not found",
                extra={
                    "company_name": company_name,
                    "missing_template": str(e),
                    "templates_dir": str(self.templates_dir),
                },
                exc_info=True,
            )
            raise TemplateRenderingError(
                f"Main report PDF template not found: {str(e)}", company_name=company_name
            ) from e
        except (TemplateError, UndefinedError, TemplateSyntaxError) as e:
            error_msg = str(e)
            logger.error(
                (
                    "❌ [TEMPLATE-SERVICE] Main report PDF rendering failed - "
                    f"{type(e).__name__}: {error_msg}"
                ),
                extra={
                    "company_name": company_name,
                    "error_type": type(e).__name__,
                    "error_message": error_msg,
                },
                exc_info=True,
            )
            raise TemplateRenderingError(
                f"Main report PDF generation failed: {error_msg}", company_name=company_name
            ) from e
        except Exception as e:
            logger.error(
                "❌ [TEMPLATE-SERVICE] Main report PDF rendering failed - unexpected error",
                extra={
                    "company_name": company_name,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise TemplateRenderingError(
                f"Main report PDF generation failed: {str(e)}", company_name=company_name
            ) from e

    def render_buyer_ready_package(
        self,
        package: Any,
        variant: Literal["screen", "pdf"] = "screen",
    ) -> str:
        """
        Render the Stage 5 buyer-ready package from its locked Pydantic payload.

        Titan posts a BuyerReadyPackageRender body to the API route; tests may
        call this directly with either the Pydantic object or a dict. The
        renderer does not compute missing fields here: malformed payloads fail
        before Jinja runs.
        """
        if not JINJA_AVAILABLE or self.env is None:
            error_msg = "Jinja2 not installed - buyer-ready package rendering unavailable"
            self.logger.error("[BUYER-READY] %s", error_msg)
            raise ImportError(error_msg)

        from src.domain.buyer_ready_models import BuyerReadyPackageRender

        parsed_package = (
            package
            if isinstance(package, BuyerReadyPackageRender)
            else BuyerReadyPackageRender.model_validate(package)
        )
        template_name = f"buyer_ready_package/{variant}/buyer_ready_package.html"

        try:
            template = self.env.get_template(template_name)
            html_content = template.render(package=parsed_package)
            if not html_content or len(html_content) < 500:
                self.logger.warning(
                    "[BUYER-READY] Rendered package HTML is suspiciously short",
                    extra={
                        "package_id": parsed_package.package_id,
                        "variant": variant,
                        "html_length": len(html_content) if html_content else 0,
                    },
                )
            return html_content
        except TemplateNotFound as e:
            self.logger.error(
                "[BUYER-READY] Template not found",
                extra={
                    "package_id": parsed_package.package_id,
                    "variant": variant,
                    "missing_template": str(e),
                    "templates_dir": str(self.templates_dir),
                },
                exc_info=True,
            )
            raise TemplateRenderingError(
                f"Buyer-ready package template not found: {str(e)}",
                company_name=parsed_package.cover.anonymised_title,
            ) from e
        except (TemplateError, UndefinedError, TemplateSyntaxError) as e:
            self.logger.error(
                "[BUYER-READY] Jinja rendering failed",
                extra={
                    "package_id": parsed_package.package_id,
                    "variant": variant,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise TemplateRenderingError(
                f"Buyer-ready package generation failed: {str(e)}",
                company_name=parsed_package.cover.anonymised_title,
            ) from e

    def generate_accountant_view_pdf(
        self, valuation_data: Dict[str, Any], output_path: Optional[str] = None
    ) -> bytes:
        """
        Generate Accountant View PDF report from valuation data.

        Args:
            valuation_data: Transformed valuation data dictionary
            output_path: Optional path to save PDF file

        Returns:
            PDF bytes
        """
        return self._pdf_generation_coordinator.generate_accountant_view_pdf(
            valuation_data,
            output_path,
        )

    # Custom Jinja2 filters are now provided by TemplateFormatter class


# Singleton instance
_template_service_instance: Optional[TemplateService] = None
_template_service_lock = Lock()
_template_service_templates_dir: Optional[Path] = None
_template_service_requested_templates_dir: Optional[Path] = None


def get_template_service(templates_dir: Optional[str] = None) -> TemplateService:
    """
    Get the singleton template service instance.

    Args:
        templates_dir: Optional templates directory path

    Returns:
        TemplateService instance
    """
    global _template_service_instance
    global _template_service_templates_dir
    global _template_service_requested_templates_dir
    requested_templates_dir = Path(templates_dir).resolve() if templates_dir else None
    with _template_service_lock:
        if _template_service_instance is None:
            _template_service_instance = TemplateService(templates_dir=templates_dir)
            _template_service_templates_dir = _template_service_instance.templates_dir.resolve()
            _template_service_requested_templates_dir = requested_templates_dir
        elif (
            requested_templates_dir
            and requested_templates_dir != _template_service_templates_dir
            and requested_templates_dir != _template_service_requested_templates_dir
        ):
            raise ValueError(
                "TemplateService singleton already initialized with a different templates_dir. "
                f"existing={_template_service_templates_dir}, requested={requested_templates_dir}"
            )
        return _template_service_instance
