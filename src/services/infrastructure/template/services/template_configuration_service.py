"""
Template Configuration Service

BANK-GRADE: Single Responsibility - Configure Jinja2 template environment

RESPONSIBILITY:
- Set up Jinja2 environment
- Register custom filters
- Resolve templates directory
- Validate template files exist
- Configure template caching

DOES NOT:
- Render templates (delegated to TemplateRenderingService)
- Transform data (delegated to TemplateDataTransformer)
- Generate PDFs (delegated to PDFGenerationCoordinator)
- Track versions (delegated to TemplateVersionService)

SRP Compliance: This service has ONE reason to change - template environment configuration
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

from src.utils.logging import get_logger

try:
    from jinja2 import Environment, FileSystemLoader, StrictUndefined, pass_context
    from markupsafe import Markup

    JINJA_AVAILABLE = True
except ImportError:
    JINJA_AVAILABLE = False
    Environment = None
    FileSystemLoader = None
    StrictUndefined = None
    Markup = str

    def pass_context(fn):  # type: ignore[no-redef]
        return fn


logger = get_logger(__name__)


class TemplateConfigurationService:
    """
    BANK-GRADE SRP-COMPLIANT: Configures Jinja2 template environment.

    SINGLE RESPONSIBILITY: Template environment setup

    This service focuses solely on setting up the template system:
    - Finding templates directory
    - Creating Jinja2 environment
    - Registering custom filters
    - Configuring caching

    Design Pattern: Service Pattern
    - Separates configuration from usage
    - Enables testing configuration independently
    - Allows swapping template engines easily
    """

    def __init__(
        self,
        templates_dir: Optional[str] = None,
        enable_caching: bool = True,
        cache_size: int = 50,
    ):
        """
        Initialize template configuration service.

        SRP: Focused on configuration only

        Args:
            templates_dir: Optional templates directory path
            enable_caching: Enable template caching for performance
            cache_size: Maximum number of templates to cache
        """
        self.logger = logger
        self.enable_caching = enable_caching
        self.cache_size = cache_size

        # Resolve templates directory
        self.templates_dir = self._resolve_templates_directory(templates_dir)

        # Create Jinja2 environment if available
        self.env = self._create_environment() if JINJA_AVAILABLE else None

        self.logger.debug(
            "✅ [TEMPLATE-CONFIG] TemplateConfigurationService initialized (SRP-compliant)",
            extra={
                "templates_dir": str(self.templates_dir),
                "jinja_available": JINJA_AVAILABLE,
                "caching_enabled": enable_caching,
            },
        )

    def _resolve_templates_directory(self, templates_dir: Optional[str]) -> Path:
        """
        Resolve templates directory with intelligent fallback logic.

        SRP: Only directory resolution, no environment setup

        Args:
            templates_dir: Optional templates directory path

        Returns:
            Resolved Path to templates directory
        """
        if templates_dir:
            path = Path(templates_dir)
            if self._validate_templates_directory(path):
                self.logger.info(f"✅ Using provided templates directory: {path}")
                return path
            else:
                self.logger.warning(
                    f"⚠️ Provided templates directory invalid: {path}, trying fallbacks"
                )

        # Default path: src/templates
        # Path(__file__) = .../src/services/infrastructure/template/services/template_configuration_service.py
        # Go up five levels to reach src/, then append templates/.
        default_path = Path(__file__).parent.parent.parent.parent.parent / "templates"

        if self._validate_templates_directory(default_path):
            self.logger.debug(f"✅ Using default templates directory: {default_path}")
            return default_path

        # Fallback paths for different environments
        fallback_paths = [
            Path("/app/src/templates"),  # Container path
            Path("/app/templates"),  # Alternative container path
            Path.cwd() / "src" / "templates",  # From project root
            Path.cwd() / "templates",  # Templates at root
        ]

        # Add environment variable path if set
        if os.getenv("TEMPLATES_DIR"):
            fallback_paths.insert(0, Path(os.getenv("TEMPLATES_DIR")))

        for fallback_path in fallback_paths:
            if self._validate_templates_directory(fallback_path):
                self.logger.info(
                    f"✅ Using fallback templates directory: {fallback_path}"
                )
                return fallback_path

        # Last resort: create directory
        self.logger.warning(
            f"⚠️ No valid templates directory found, creating: {default_path}"
        )
        default_path.mkdir(parents=True, exist_ok=True)
        return default_path

    def _validate_templates_directory(self, path: Path) -> bool:
        """
        Validate that templates directory exists and contains required files.

        SRP: Only validation, no setup

        Args:
            path: Path to validate

        Returns:
            True if directory is valid
        """
        if not path.exists() or not path.is_dir():
            return False

        launch_ready_templates = [
            path / "main_report" / "master_report.html",
            path / "main_report_pdf" / "master_report.html",
        ]
        return all(
            template.exists() and template.is_file()
            for template in launch_ready_templates
        )

    def _create_environment(self) -> Optional[Environment]:
        """
        Create and configure Jinja2 environment.

        SRP: Only environment creation

        Returns:
            Configured Jinja2 Environment or None if Jinja2 unavailable
        """
        if not JINJA_AVAILABLE:
            self.logger.warning("⚠️ Jinja2 not available, cannot create environment")
            return None

        try:
            use_strict = os.environ.get("REPORT_STRICT_TEMPLATES", "").strip() == "1"
            undefined_kwargs: Dict[str, object] = {}
            if use_strict and StrictUndefined is not None:
                undefined_kwargs["undefined"] = StrictUndefined

            env_kwargs = {
                "loader": FileSystemLoader(str(self.templates_dir)),
                "cache_size": self.cache_size if self.enable_caching else 0,
                "auto_reload": False,  # Performance: disable auto-reload in production
            }
            env = Environment(
                **env_kwargs,
                autoescape=True,  # Security: prevent XSS
                **undefined_kwargs,
            )
            if use_strict:
                self.logger.info(
                    "Jinja2 StrictUndefined enabled via REPORT_STRICT_TEMPLATES=1"
                )

            self.logger.debug(
                "✅ [TEMPLATE-CONFIG] Jinja2 environment created",
                extra={
                    "autoescape": True,
                    "cache_size": self.cache_size if self.enable_caching else 0,
                },
            )

            return env

        except Exception as e:
            self.logger.error(
                f"❌ [TEMPLATE-CONFIG] Failed to create Jinja2 environment: {e}",
                exc_info=True,
            )
            return None

    def register_filters(self, formatter: Any) -> None:
        """
        Register custom Jinja2 filters.

        SRP: Only filter registration

        Args:
            formatter: TemplateFormatter instance with filter methods
        """
        if not self.env:
            self.logger.warning("⚠️ Cannot register filters - no Jinja2 environment")
            return

        filters = self._register_locale_filters(formatter)
        decimal_functions = self._register_decimal_functions(formatter)
        self._register_reference_filter()
        self._register_domain_template_globals()
        self._register_pdf_font_globals()

        self.logger.info(
            f"✅ [TEMPLATE-CONFIG] Registered {len(filters)} custom filters and {len(decimal_functions)} Decimal functions",
            extra={
                "filters": list(filters.keys()),
                "decimal_functions": list(decimal_functions.keys()),
            },
        )

    @staticmethod
    def _ctx_locale(ctx) -> str:
        # Locale lives at the top level of the render context. Some direct
        # template tests use only startup_report, so keep the fallback chain.
        return (
            ctx.get("locale")
            or (
                (ctx.get("startup_report") or {}).get("locale")
                if isinstance(ctx.get("startup_report"), dict)
                else None
            )
            or "en"
        )

    def _register_locale_filters(self, formatter) -> Dict[str, object]:
        @pass_context
        def _format_currency(ctx, value, currency="EUR"):
            return formatter.format_currency(
                value, currency=currency, locale=self._ctx_locale(ctx)
            )

        @pass_context
        def _format_currency_compact(ctx, value, currency="EUR"):
            return formatter.format_currency_compact(
                value, currency=currency, locale=self._ctx_locale(ctx)
            )

        @pass_context
        def _format_eur_amount(ctx, value):
            return formatter.format_eur_amount(value, locale=self._ctx_locale(ctx))

        @pass_context
        def _format_eur_or_dash(ctx, value):
            if value is None or value == "":
                return "—"
            try:
                if float(value) == 0.0:
                    return "—"
            except (TypeError, ValueError):
                pass
            return formatter.format_eur_amount(value, locale=self._ctx_locale(ctx))

        @pass_context
        def _format_percentage(ctx, value):
            return formatter.format_percentage(value, locale=self._ctx_locale(ctx))

        @pass_context
        def _format_factor_pct(ctx, value, decimals=1):
            if value is None or value == "":
                return "—"
            try:
                pct_value = float(value) * 100
            except (TypeError, ValueError):
                return "—"
            try:
                decimals_int = int(decimals)
            except (TypeError, ValueError):
                decimals_int = 1
            decimals_int = max(0, min(decimals_int, 4))
            body = f"{pct_value:.{decimals_int}f}"
            if self._ctx_locale(ctx) == "nl":
                body = body.replace(".", ",")
            return f"{body}%"

        @pass_context
        def _safe_round(ctx, value, decimals=2):
            return formatter.safe_round(
                value, decimals=decimals, locale=self._ctx_locale(ctx)
            )

        @pass_context
        def _safe_round_or_dash(ctx, value, decimals=2):
            return formatter.safe_round_or_dash(
                value, decimals=decimals, locale=self._ctx_locale(ctx)
            )

        filters = {
            "format_currency": _format_currency,
            "format_currency_compact": _format_currency_compact,
            "format_eur_amount": _format_eur_amount,
            "format_eur_or_dash": _format_eur_or_dash,
            "format_percentage": _format_percentage,
            "format_factor_pct": _format_factor_pct,
            "format_date": formatter.format_date,
            "safe_round": _safe_round,
            "safe_round_or_dash": _safe_round_or_dash,
            "nl2br": formatter.nl2br,
            "css_string": self._css_string,
        }
        for filter_name, filter_func in filters.items():
            self.env.filters[filter_name] = filter_func
        return filters

    @staticmethod
    def _css_string(value: object) -> object:
        """Escape one value for a double-quoted CSS string in a style element."""

        escaped = (
            str(value or "")
            .replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\r", "\\d ")
            .replace("\n", "\\a ")
            .replace("<", "\\3c ")
            .replace(">", "\\3e ")
            .replace("&", "\\26 ")
        )
        return Markup(escaped)

    def _register_reference_filter(self) -> None:
        from src.services.defensibility.reference_formatter import (
            format_valuation_reference as _format_ref_helper,
        )

        def _format_ref(value, valuation_date=None):
            return _format_ref_helper(value, valuation_date) or value

        self.env.filters["format_ref"] = _format_ref

    def _register_decimal_functions(self, formatter) -> Dict[str, object]:
        decimal_functions = {
            "decimal_divide": formatter.decimal_divide,
            "decimal_multiply": formatter.decimal_multiply,
            "decimal_add": formatter.decimal_add,
            "decimal_subtract": formatter.decimal_subtract,
            "to_decimal": formatter.to_decimal,
            "safe_decimal_divide": formatter.safe_decimal_divide,
            "safe_decimal_multiply": formatter.safe_decimal_multiply,
            "safe_decimal_add": formatter.safe_decimal_add,
            "safe_decimal_subtract": formatter.safe_decimal_subtract,
        }

        for func_name, func in decimal_functions.items():
            self.env.globals[func_name] = func
            self.env.filters[func_name] = func
        self.env.globals["hasattr"] = hasattr
        return decimal_functions

    def _register_domain_template_globals(self) -> None:
        try:
            from src.domain.owner_profiling_bands import op_band_color

            self.env.globals["op_band_color"] = op_band_color
        except ImportError:
            pass

        try:
            from src.domain.startup_valuation.defensibility_traffic import (
                defensibility_traffic_bg,
                defensibility_traffic_fg,
                defensibility_traffic_pdf_bg,
                defensibility_traffic_pdf_fg,
            )

            self.env.globals["defensibility_traffic_bg"] = defensibility_traffic_bg
            self.env.globals["defensibility_traffic_fg"] = defensibility_traffic_fg
            self.env.globals["defensibility_traffic_pdf_bg"] = (
                defensibility_traffic_pdf_bg
            )
            self.env.globals["defensibility_traffic_pdf_fg"] = (
                defensibility_traffic_pdf_fg
            )
        except ImportError:
            pass

    def _register_pdf_font_globals(self) -> None:
        try:
            from markupsafe import Markup

            from src.services.infrastructure.pdf.font_css import get_pdf_font_face_css

            self.env.globals["pdf_font_face_css"] = Markup(get_pdf_font_face_css())
        except Exception:  # pragma: no cover - never block env init on fonts
            self.env.globals["pdf_font_face_css"] = ""

    def get_environment(self) -> Optional[Environment]:
        """
        Get configured Jinja2 environment.

        Returns:
            Jinja2 Environment or None if unavailable
        """
        return self.env

    def is_available(self) -> bool:
        """
        Check if template system is available.

        Returns:
            True if Jinja2 is available and environment created
        """
        return JINJA_AVAILABLE and self.env is not None

    def get_templates_directory(self) -> Path:
        """
        Get resolved templates directory path.

        Returns:
            Path to templates directory
        """
        return self.templates_dir

    def validate_required_templates(self) -> Dict[str, bool]:
        """
        Validate that all required templates exist.

        Returns:
            Dictionary mapping template paths to existence status
        """
        required_templates = [
            "accountant_view/master_report.html",
            "accountant_view/executive_summary.html",
            "accountant_view/financial_analysis.html",
            "accountant_view/valuation_methodologies.html",
            "accountant_view/valuation_conclusion.html",
            "main_report/master_report.html",
            "main_report_pdf/master_report.html",
        ]

        validation_results = {}
        for template_path in required_templates:
            full_path = self.templates_dir / template_path
            exists = full_path.exists() and full_path.is_file()
            validation_results[template_path] = exists

            if not exists:
                self.logger.warning(
                    f"⚠️ [TEMPLATE-CONFIG] Required template missing: {template_path}"
                )

        return validation_results
