"""
Report Rendering Coordinator

Handles HTML report rendering logic.
Extracted from template_service.py to improve modularity.

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive rendering logic
- Detailed logging
"""

import time
from pathlib import Path
from typing import Any, Dict, Optional

from src.services.infrastructure.exceptions import TemplateRenderingError
from src.utils.logging import get_logger

from .report_rendering_support import (
    MASTER_TEMPLATE_PATH,
    add_generation_timestamp,
    attach_academic_references,
    is_missing_template_error,
    log_cover_page_status,
    log_include_status,
    log_performance_thresholds,
    log_required_field_status,
    log_section_status,
    missing_required_includes,
    optimize_for_streaming,
    performance_metrics,
    prepare_accountant_template_context,
    require_jinja_available,
    require_master_template,
    safe_company_name,
    template_environment_unavailable,
    validate_rendered_html,
)

logger = get_logger(__name__)

try:
    from jinja2 import Environment, TemplateNotFound, TemplateSyntaxError, UndefinedError

    JINJA_AVAILABLE = True
except ImportError:
    JINJA_AVAILABLE = False
    Environment = None
    TemplateNotFound = Exception
    TemplateSyntaxError = Exception
    UndefinedError = Exception


class ReportRenderingCoordinator:
    """
    Coordinates HTML report rendering logic.

    Responsibilities:
    - Render Accountant View reports
    - Render Info Tab reports
    - Handle template loading and rendering
    - Optimize HTML for streaming
    """

    def __init__(
        self,
        templates_dir: Path,
        env: Optional[Environment],
        generate_fallback_html_func,
        logger_instance=None,
    ):
        """
        Initialize report rendering coordinator.

        Args:
            templates_dir: Templates directory path
            env: Jinja2 environment instance
            generate_fallback_html_func: Function to generate fallback HTML
            logger_instance: Logger instance (optional)
        """
        self.logger = logger_instance or logger
        self.templates_dir = templates_dir
        self.env = env
        self.generate_fallback_html = generate_fallback_html_func

    def render_accountant_view_report(self, valuation_data: Dict[str, Any]) -> str:
        """
        Render Accountant View report HTML from templates.

        Args:
            valuation_data: Transformed valuation data dictionary

        Returns:
            Rendered HTML string with all sections

        Raises:
            TemplateRenderingError: If rendering fails
        """
        start_time = time.time()
        self.logger.info(
            "🔄 STARTING ACCOUNTANT VIEW REPORT GENERATION",
            extra={
                "company_name": safe_company_name(valuation_data),
                "templates_dir": (
                    str(self.templates_dir) if hasattr(self, "templates_dir") else "N/A"
                ),
            },
        )

        require_jinja_available(self.logger, JINJA_AVAILABLE)

        try:
            log_required_field_status(self.logger, valuation_data)
            attach_academic_references(self.logger, valuation_data)
            add_generation_timestamp(valuation_data)

            self.logger.info(
                "Step 2: Rendering master template",
                extra={
                    "template": "master_report.html",
                    "company_name": safe_company_name(valuation_data),
                },
            )

            require_master_template(self.templates_dir)
            missing_includes = missing_required_includes(self.templates_dir)
            log_include_status(
                self.logger,
                valuation_data=valuation_data,
                templates_dir=self.templates_dir,
                missing_includes=missing_includes,
            )
            if missing_includes:
                raise FileNotFoundError(
                    f"Required template includes not found: {missing_includes}. "
                    f"Templates directory: {self.templates_dir}"
                )

            # Render master template (includes all sections via {% include %})
            self.logger.info(f"Rendering master template: {MASTER_TEMPLATE_PATH}")

            # Check if env is None (fallback mode)
            if not self.env:
                self.logger.warning("Template environment is None - generating fallback HTML")
                return self.generate_fallback_html(valuation_data)

            # Inject translations and locale so accountant_view templates can use {{ t. }}.
            # Locale falls back to 'nl' (default audience) when caller did not set it,
            # mirroring the convention in render_main_report.
            valuation_data = prepare_accountant_template_context(valuation_data)

            try:
                master_template = self.env.get_template(MASTER_TEMPLATE_PATH)
                html = master_template.render(**valuation_data)
                log_cover_page_status(self.logger, html=html, valuation_data=valuation_data)
                log_section_status(self.logger, html=html, valuation_data=valuation_data)
            except TemplateNotFound as template_error:
                # Template file not found
                self.logger.error(
                    f"❌ Template not found: {template_error}",
                    extra={
                        "company_name": valuation_data.get("company_name", "N/A"),
                        "template_path": MASTER_TEMPLATE_PATH,
                        "templates_dir": str(self.templates_dir),
                        "error": str(template_error),
                    },
                    exc_info=True,
                )
                return self.generate_fallback_html(valuation_data)
            except (TemplateSyntaxError, UndefinedError) as template_error:
                # Template syntax or variable error
                self.logger.error(
                    f"❌ Template rendering error: {template_error}",
                    extra={
                        "company_name": valuation_data.get("company_name", "N/A"),
                        "template_path": MASTER_TEMPLATE_PATH,
                        "error_type": type(template_error).__name__,
                        "error": str(template_error),
                        "error_line": getattr(template_error, "lineno", None),
                        "error_message": getattr(template_error, "message", None),
                    },
                    exc_info=True,
                )
                # Re-raise template errors - they indicate code issues that need fixing
                raise TemplateRenderingError(
                    f"Template rendering failed: {template_error}",
                    company_name=valuation_data.get("company_name", "N/A"),
                ) from template_error
            except (FileNotFoundError, Exception) as template_error:
                # If template loading fails, generate fallback HTML
                error_msg = str(template_error)
                if is_missing_template_error(template_error):
                    self.logger.warning(
                        f"Template not found - generating fallback HTML: {error_msg}",
                        extra={
                            "company_name": valuation_data.get("company_name", "N/A"),
                            "template_path": MASTER_TEMPLATE_PATH,
                            "error": error_msg,
                        },
                    )
                    return self.generate_fallback_html(valuation_data)
                # Log unexpected errors with full context
                self.logger.error(
                    f"❌ Unexpected template rendering error: {template_error}",
                    extra={
                        "company_name": valuation_data.get("company_name", "N/A"),
                        "template_path": MASTER_TEMPLATE_PATH,
                        "error_type": type(template_error).__name__,
                        "error": error_msg,
                    },
                    exc_info=True,
                )
                # Re-raise if it's a different error
                raise

            html = validate_rendered_html(
                html,
                template_path=MASTER_TEMPLATE_PATH,
                templates_dir=self.templates_dir,
                logger=self.logger,
            )
            self.logger.info(f"  ✓ Master template rendered: {len(html):,} chars")

            html = optimize_for_streaming(self.logger, html)
            generation_duration = time.time() - start_time

            # BANK-GRADE: Performance metrics
            metrics = performance_metrics(generation_duration=generation_duration, html=html)

            # Performance thresholds (CTO-level monitoring)
            log_performance_thresholds(
                self.logger,
                generation_duration=generation_duration,
                valuation_data=valuation_data,
                metrics=metrics,
            )

            self.logger.info(
                "✅ REPORT GENERATION COMPLETE",
                extra={
                    "template": "master_report.html",
                    "sections_included": 10,
                    "company_name": safe_company_name(valuation_data),
                    **metrics,
                },
            )

            return html

        except (ValueError, TypeError, KeyError, AttributeError) as e:
            error_type = type(e).__name__
            error_msg = str(e)

            # If env is None or AttributeError related to env, generate fallback HTML
            if template_environment_unavailable(self.env, e):
                self.logger.warning(
                    "Template environment unavailable - generating fallback HTML",
                    extra={
                        "error_type": error_type,
                        "error_message": error_msg,
                        "company_name": valuation_data.get("company_name", "N/A"),
                    },
                )
                return self.generate_fallback_html(valuation_data)

            self.logger.error(
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
                company_name=(
                    valuation_data.get("company_name") if isinstance(valuation_data, dict) else None
                ),
                correlation_id=(
                    valuation_data.get("correlation_id")
                    if isinstance(valuation_data, dict)
                    else None
                ),
            ) from e
