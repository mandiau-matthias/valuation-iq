"""
Template Initializer

Initializes Jinja2 environment and template directory setup.
"""

from typing import Optional
from pathlib import Path
import os
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal

try:
    from jinja2 import Environment, FileSystemLoader, pass_context
    JINJA_AVAILABLE = True
except ImportError:
    JINJA_AVAILABLE = False
    def pass_context(fn):  # type: ignore[no-redef]
        return fn

from src.utils.logging import get_logger
from src.services.infrastructure.template_formatter import TemplateFormatter

logger = get_logger(__name__)


class TemplateInitializer:
    """
    Initializes template environment and directory setup.
    """
    
    @staticmethod
    def find_templates_directory(templates_dir: Optional[str] = None) -> Path:
        """
        Find templates directory using fallback paths.
        
        Args:
            templates_dir: Optional explicit templates directory path
            
        Returns:
            Path to templates directory
        """
        if templates_dir:
            return Path(templates_dir)
        
        # Default to src/templates
        default_path = Path(__file__).parent.parent.parent.parent.parent / "templates"
        
        # If default path doesn't exist, try fallback paths
        if not default_path.exists():
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
                accountant_view_dir = fallback_path / "accountant_view"
                if accountant_view_dir.exists() and accountant_view_dir.is_dir():
                    logger.info(f"✅ Found templates directory via fallback: {fallback_path}")
                    return fallback_path
        
        return default_path
    
    @staticmethod
    def create_environment(templates_dir: Path, formatter: TemplateFormatter) -> Optional[Environment]:
        """
        Create Jinja2 environment with custom filters.
        
        Args:
            templates_dir: Path to templates directory
            formatter: TemplateFormatter instance for custom filters
            
        Returns:
            Jinja2 Environment instance, or None if Jinja2 not available
        """
        if not JINJA_AVAILABLE:
            logger.warning("⚠️ Jinja2 not installed - template service in fallback mode")
            return None
        
        env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=True
        )
        
        # Add custom filters with locale-awareness via Jinja context.
        # Mirrors the wiring in template_service.py — see the docstring
        # there for the rationale. ``ctx['locale']`` is set by
        # render_main_report / render_main_report_pdf at the start of
        # every render; the wrappers below pull it per call so NL
        # reports get NL number conventions and EN reports get EN.
        def _ctx_locale(ctx):
            return ctx.get('locale') or (
                (ctx.get('startup_report') or {}).get('locale') if isinstance(ctx.get('startup_report'), dict) else None
            ) or 'en'

        @pass_context
        def _format_currency(ctx, value, currency='EUR'):
            return formatter.format_currency(value, currency=currency, locale=_ctx_locale(ctx))

        @pass_context
        def _format_currency_compact(ctx, value, currency='EUR'):
            return formatter.format_currency_compact(value, currency=currency, locale=_ctx_locale(ctx))

        @pass_context
        def _format_eur_amount(ctx, value):
            return formatter.format_eur_amount(value, locale=_ctx_locale(ctx))

        @pass_context
        def _format_eur_or_dash(ctx, value):
            # Render missing-data as an em-dash rather than collapsing
            # to "€0" — important for downside-scenario reports where
            # a missing input is meaningfully different from a true zero
            # (e.g. an un-decomposed asset class vs. an actually-empty
            # asset class).  Used in place of `default(0)|format_eur_amount`
            # on every card-headline + table-cell where a None upstream
            # could leak through. Audit P1 #10.
            if value is None or value == "":
                return "—"
            try:
                # Treat truly-zero as missing-data too: in liquidation
                # reports a €0 line is rarely informative — the asset
                # class is omitted from the schedule when it's actually
                # zero (engine emits the row only for non-zero buckets).
                # When it slips through anyway, the em-dash communicates
                # "not applicable" rather than implying precision.
                if float(value) == 0.0:
                    return "—"
            except (TypeError, ValueError):
                pass
            return formatter.format_eur_amount(value, locale=_ctx_locale(ctx))

        @pass_context
        def _format_percentage(ctx, value):
            return formatter.format_percentage(value, locale=_ctx_locale(ctx))

        @pass_context
        def _format_factor_pct(ctx, value, decimals=1):
            # Render a 0–1 decimal factor as a locale-aware percent at
            # the caller-chosen precision (default 1dp).  Replaces the
            # ad-hoc inline `(x|float * 100)|safe_round(N) %` pattern
            # used across ~30 liquidation template cells so locale
            # separators (NL `12,5%`, EN `12.5%`) stay consistent without
            # forcing every site onto `format_percentage`'s fixed 2dp.
            # Audit P0 #3.  Returns "—" for missing inputs.
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
            # Reuse the formatter's locale-separator helper indirectly
            # via format_percentage's logic — but it pre-multiplies, so
            # we apply NL's `,` swap inline here to keep the path simple.
            if _ctx_locale(ctx) == 'nl':
                body = body.replace('.', ',')
            return f"{body}%"

        @pass_context
        def _safe_round(ctx, value, decimals=2):
            return formatter.safe_round(value, decimals=decimals, locale=_ctx_locale(ctx))

        env.filters['format_currency'] = _format_currency
        env.filters['format_currency_compact'] = _format_currency_compact
        env.filters['format_eur_amount'] = _format_eur_amount
        env.filters['format_eur_or_dash'] = _format_eur_or_dash
        env.filters['format_percentage'] = _format_percentage
        env.filters['format_factor_pct'] = _format_factor_pct
        env.filters['format_date'] = formatter.format_date
        env.filters['safe_round'] = _safe_round
        env.filters['nl2br'] = formatter.nl2br
        
        # BANK-GRADE: Register Decimal arithmetic functions as globals and filters
        # Standard Decimal functions
        decimal_functions = {
            'decimal_divide': formatter.decimal_divide,
            'decimal_multiply': formatter.decimal_multiply,
            'decimal_add': formatter.decimal_add,
            'decimal_subtract': formatter.decimal_subtract,
            'to_decimal': formatter.to_decimal,
            # Safe versions with fallback handling
            'safe_decimal_divide': formatter.safe_decimal_divide,
            'safe_decimal_multiply': formatter.safe_decimal_multiply,
            'safe_decimal_add': formatter.safe_decimal_add,
            'safe_decimal_subtract': formatter.safe_decimal_subtract,
        }
        
        # Register as globals for function-style calls: {{ safe_decimal_divide(a, b, 0) }}
        for func_name, func in decimal_functions.items():
            env.globals[func_name] = func
            # Also register as filters for pipe syntax: {{ a | safe_decimal_divide(b, 0) }}
            env.filters[func_name] = func
        
        # BANK-GRADE: Add Python built-ins that templates may need
        env.globals['hasattr'] = hasattr
        
        logger.info(
            f"✅ Template environment initialized with directory: {templates_dir}",
            extra={'decimal_functions': list(decimal_functions.keys())}
        )
        return env
    
    @staticmethod
    def ensure_templates_directory(templates_dir: Path) -> None:
        """
        Ensure templates directory exists, create default templates if needed.
        
        Args:
            templates_dir: Path to templates directory
        """
        if not templates_dir.exists():
            logger.warning(f"Templates directory not found: {templates_dir}")
            templates_dir.mkdir(parents=True, exist_ok=True)
            TemplateInitializer._create_default_template(templates_dir)
    
    @staticmethod
    def _create_default_template(templates_dir: Path) -> None:
        """Create default valuation report template"""
        default_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Valuation Report - {{ company_name }}</title>
    <style>
        body { font-family: 'Helvetica', 'Arial', sans-serif; line-height: 1.6; color: #333; max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { border-bottom: 3px solid #2563eb; padding-bottom: 20px; margin-bottom: 30px; }
        .header h1 { color: #1e40af; margin: 0; }
        .section { margin-bottom: 40px; page-break-inside: avoid; }
        .section h2 { color: #1e40af; border-bottom: 2px solid #e5e7eb; padding-bottom: 10px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Business Valuation Report</h1>
        <p><strong>Company:</strong> {{ company_name }}</p>
        <p><strong>Report Date:</strong> {{ report_date | format_date }}</p>
    </div>
    <div class="section">
        <h2>Executive Summary</h2>
        <p><strong>Estimated Valuation Range:</strong> {{ valuation_range_min | format_currency }} - {{ valuation_range_max | format_currency }}</p>
    </div>
</body>
</html>"""
        
        template_file = templates_dir / "valuation_report.html"
        with open(template_file, 'w') as f:
            f.write(default_template)
        
        logger.info(f"✅ Created default template: {template_file}")

