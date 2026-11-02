from src.utils.exceptions import ExternalServiceError

"""
Template Formatter Module

RESPONSIBILITIES:
- Format values for template rendering (currency, percentage, dates, rounding)
- Provide null-safe formatting functions

REFACTORING NOTE:
Extracted from template_service.py to improve maintainability and reduce file size.
"""

from datetime import datetime, date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from src.utils.decimal_helpers import to_decimal, from_decimal, bank_round

# Import HTML escaping for explicit XSS protection (defense in depth)
try:
    from markupsafe import escape
except ImportError:
    # Fallback if markupsafe not available (shouldn't happen with Jinja2)
    def escape(s):
        return (
            str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;")
        )


def _normalize_locale(locale: object) -> str:
    """Coerce any locale-ish input to "nl", "en", or "fr". Defaults to
    "en" so a missing locale never silently switches the formatter to NL
    conventions on an EN report.

    BET-291: "fr" adds French number conventions to the formatter without
    touching the strict report ``Locale`` type or the copy catalog — so FR
    figures render correctly even before the FR copy translation lands."""
    if not locale:
        return "en"
    raw = str(locale).strip().lower()
    if raw.startswith("nl"):
        return "nl"
    if raw.startswith("fr"):
        return "fr"
    return "en"


def _apply_locale_separators(formatted: str, locale: str) -> str:
    """Convert a Python ``f"{x:,.2f}"`` (en_US: ``1,234.56``) string to
    the requested locale's separators.

    - NL: ``.`` thousands, ``,`` decimal — the inverse of EN (``1.234,56``).
    - FR: non-breaking-space thousands, ``,`` decimal (``1 234,56``),
      the standard French/SI convention. The NBSP keeps the grouped number
      from wrapping across a PDF line break. (Belgian-FR thousands separator
      — space vs period — is flagged for native-accountant review per BET-291.)
    - EN (and any other locale): unchanged.

    Two-step swap via a ``\\x00`` placeholder so the second substitution
    doesn't re-flip the first."""
    norm = _normalize_locale(locale)
    if norm == "nl":
        return formatted.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    if norm == "fr":
        return formatted.replace(",", "\x00").replace(".", ",").replace("\x00", " ")
    return formatted


_LOCALIZED_MONTHS: dict[str, tuple[str, ...]] = {
    "nl": (
        "januari",
        "februari",
        "maart",
        "april",
        "mei",
        "juni",
        "juli",
        "augustus",
        "september",
        "oktober",
        "november",
        "december",
    ),
    "fr": (
        "janvier",
        "février",
        "mars",
        "avril",
        "mai",
        "juin",
        "juillet",
        "août",
        "septembre",
        "octobre",
        "novembre",
        "décembre",
    ),
}


class TemplateFormatter:
    """
    Provides formatting utilities for template rendering
    """

    @staticmethod
    def format_currency(value: object, currency: str = "EUR", locale: str = "en") -> str:
        """
        Format value as currency with comprehensive null safety.
        Uses currency symbols (€, $, £) with exact Decimal formatting.
        Smart formatting: no decimals for whole numbers.

        Locale support:
        - ``"en"`` (default): ``€360,000`` / ``€360,555.75`` (comma thousands, period decimal)
        - ``"nl"``: ``€360.000`` / ``€360.555,75`` (period thousands, comma decimal)

        Args:
            value: Value to format
            currency: Currency code (EUR, USD, GBP)
            locale: Render locale (``"en"`` or ``"nl"``)

        Returns:
            Formatted currency string

        Examples:
            format_currency(360000) -> "€360,000"
            format_currency(360000, locale="nl") -> "€360.000"
            format_currency(360555.75, locale="nl") -> "€360.555,75"
            format_currency(None) -> "—"
        """
        if value is None:
            return "—"  # Em dash for missing values (professional standard)

        try:
            # Handle string inputs - strip all common currency symbols
            if isinstance(value, str):
                cleaned = (
                    value.replace(",", "")
                    .replace(currency, "")
                    .replace("€", "")
                    .replace("$", "")
                    .replace("£", "")
                    .replace("EUR", "")
                    .replace("USD", "")
                    .replace("GBP", "")
                    .strip()
                )
                value_decimal = to_decimal(cleaned)
            else:
                value_decimal = to_decimal(value)

            # Display symbols do not imply compliance or measured accuracy.
            symbols = {"EUR": "€", "USD": "$", "GBP": "£"}
            symbol = symbols.get(currency, currency)

            # Smart formatting: no decimals for whole numbers. The sign is
            # rendered ahead of the symbol ("-€23.732,52"): placing it after
            # produced "€-23.732,52", which reads as a corrupt amount rather
            # than a negative one in bridge and movement tables.
            is_negative = value_decimal < 0
            magnitude = -value_decimal if is_negative else value_decimal
            if magnitude % 1 == 0:
                formatted = f"{magnitude:,.0f}"  # e.g., "360,000"
            else:
                formatted = f"{magnitude:,.2f}"  # e.g., "360,555.75"
            sign = "-" if is_negative else ""
            return f"{sign}{symbol}{_apply_locale_separators(formatted, locale)}"

        except (ValueError, TypeError, AttributeError):
            return "—"

    @staticmethod
    def format_eur_amount(value: object, locale: str = "en") -> str:
        """
        Format a EUR amount as digits-only with thousands separators
        and no currency symbol — for i18n strings that already include
        the leading "€" themselves (e.g. "Berkus methode — €{value}").

        Returns "—" on None / invalid so a missing leg never silently
        renders as "0".

        Examples:
            format_eur_amount(4500000) -> "4,500,000"
            format_eur_amount(4500000, locale="nl") -> "4.500.000"
            format_eur_amount(0)       -> "0"
            format_eur_amount(None)    -> "—"
        """
        if value is None:
            return "—"
        try:
            if isinstance(value, str):
                cleaned = value.replace(",", "").replace("€", "").replace("EUR", "").strip()
                value_decimal = to_decimal(cleaned)
            else:
                value_decimal = to_decimal(value)
            value_float = from_decimal(value_decimal)
            if value_decimal % 1 == 0:
                formatted = f"{value_float:,.0f}"
            else:
                formatted = f"{value_float:,.2f}"
            return _apply_locale_separators(formatted, locale)
        except (ValueError, TypeError, AttributeError, InvalidOperation):
            return "—"

    @staticmethod
    def format_currency_compact(value: object, currency: str = "EUR", locale: str = "en") -> str:
        """
        Format value as compact currency (€274K or €1.2M) for hero cards and summaries.
        Matches React template formatCurrency() behavior.

        Args:
            value: Value to format
            currency: Currency code (EUR, USD, GBP)
            locale: Render locale (``"en"`` or ``"nl"``) — affects the
                decimal separator on the compact ``1.2M`` render.

        Returns:
            Formatted compact currency string (e.g., "€274K", "€1.2M",
            or "€1,2M" when locale="nl")

        Examples:
            format_currency_compact(274000) -> "€274K"
            format_currency_compact(1200000) -> "€1.2M"
            format_currency_compact(1200000, locale="nl") -> "€1,2M"
            format_currency_compact(500) -> "€500"
            format_currency_compact(None) -> "—"
        """
        if value is None:
            return "—"  # Em dash for missing values

        try:
            # Handle string inputs - strip currency symbols
            if isinstance(value, str):
                cleaned = (
                    value.replace(",", "")
                    .replace(currency, "")
                    .replace("€", "")
                    .replace("$", "")
                    .replace("£", "")
                    .replace("EUR", "")
                    .replace("USD", "")
                    .replace("GBP", "")
                    .strip()
                )
                value_decimal = to_decimal(cleaned)
            else:
                value_decimal = to_decimal(value)

            # Currency symbols
            symbols = {"EUR": "€", "USD": "$", "GBP": "£"}
            symbol = symbols.get(currency, currency)

            # Compact formatting: M for millions, K for thousands
            abs_value = abs(value_decimal)
            sign = "-" if value_decimal < 0 else ""

            if abs_value >= Decimal("1000000"):
                # Millions: €1.2M (or €1,2M in NL).  Drop trailing
                # ``.0`` for clean values so €1,000,000 renders as
                # ``€1M`` not ``€1.0M`` — cosmetic but reads cleaner
                # in chart labels (audit issue C4).
                # Round HALF-UP to one decimal so the compact render matches the
                # exact downstream figures (e.g. €2.054.128 -> €2,1M, €4.254.619
                # -> €4,3M) instead of truncating (-> €2,0M / €4,2M), which made
                # the cover disagree with the body's own grids (panel blockers).
                compact_value = (abs_value / Decimal("1000000")).quantize(
                    Decimal("0.1"), rounding=ROUND_HALF_UP
                )
                if compact_value == compact_value.to_integral_value():
                    body = f"{int(compact_value)}"
                else:
                    body = _apply_locale_separators(f"{compact_value:.1f}", locale)
                return f"{sign}{symbol}{body}M"
            elif abs_value >= Decimal("1000"):
                # Thousands: €274K — no decimal, locale-neutral
                compact_value = from_decimal(abs_value / Decimal("1000"))
                return f"{sign}{symbol}{compact_value:.0f}K"
            else:
                # Small values: €500 — locale-neutral (no separators below 1K)
                return f"{sign}{symbol}{from_decimal(abs_value):,.0f}"

        except (ValueError, TypeError, AttributeError):
            return "—"

    @staticmethod
    def format_percentage(value: object, locale: str = "en") -> str:
        """
        Format value as percentage with comprehensive null safety.

        Locale support:
        - ``"en"`` (default): ``15.00%``
        - ``"nl"``: ``15,00%``

        Missing-value sentinel is unified to "—" across the formatter
        family (was "N/A" — caused inconsistent renders next to
        ``format_currency`` on the same row).

        Args:
            value: Value to format (0-1 decimal or percentage)
            locale: Render locale (``"en"`` or ``"nl"``)

        Returns:
            Formatted percentage string
        """
        if value is None:
            return "—"
        try:
            # Handle string inputs
            if isinstance(value, str):
                value_decimal = to_decimal(value.replace("%", "").strip())
                # If string had %, treat as already percentage
                if "%" in value:
                    value_float = from_decimal(value_decimal)
                    return f"{_apply_locale_separators(f'{value_float:.2f}', locale)}%"
                # Decimal wire strings retain the same units as their numeric
                # form. JSON reload must not divide a displayed rate by 100.
                value = value_decimal

            # Convert to Decimal for comparison
            value_decimal = to_decimal(value)
            # If value is decimal (0-1), multiply by 100
            if Decimal("-1.0") <= value_decimal <= Decimal("1.0"):
                percentage_decimal = value_decimal * Decimal("100")
                percentage_float = from_decimal(percentage_decimal)
                body = f"{percentage_float:.2f}"
            else:
                # Value is already in percentage form
                value_float = from_decimal(value_decimal)
                body = f"{value_float:.2f}"
            return f"{_apply_locale_separators(body, locale)}%"
        except (ValueError, TypeError, AttributeError):
            return "—"

    @staticmethod
    def safe_round(value: object, decimals: int = 2, locale: str = "en") -> str:
        """
        Round value with comprehensive null safety, handles None, Undefined, and missing values.

        SECURITY NOTE: This filter returns HTML-escaped strings for XSS protection.
        The "safe" in the name refers to "safe from errors" (handles None/Undefined),
        NOT "safe from XSS" (bypasses HTML escaping). All output is explicitly HTML-escaped.

        Locale support:
        - ``"en"`` (default): ``4.5``
        - ``"nl"``: ``4,5``

        Args:
            value: Value to round
            decimals: Number of decimal places (default: 2)
            locale: Render locale (``"en"`` or ``"nl"``)

        Returns:
            HTML-escaped rounded value as string (e.g., "4.5" / "4,5" depending on locale)

        Note: missing values render as ``"0"`` for backwards compatibility
        across the 9 valuation methods (~370 call sites).  When a missing
        value should render as the em-dash sentinel the rest of the
        formatter family uses, prefer :py:meth:`safe_round_or_dash`.
        """
        # Handle None
        if value is None:
            return escape("0")
        try:
            # Check if value is Jinja2 Undefined (Undefined objects don't have __round__ method)
            # This will catch Undefined objects before we try to round them
            if hasattr(value, "__class__") and "Undefined" in str(type(value).__name__):
                return escape("0")
            # Handle string inputs
            if isinstance(value, str):
                value_decimal = to_decimal(value.replace(",", "").strip())
            else:
                value_decimal = to_decimal(value)
            rounded_decimal = bank_round(value_decimal, decimals)
            # Quantize to the REQUESTED precision. from_decimal() defaults to 2 dp, so
            # omitting `decimals` here silently clamps any decimals>2 render to 2 sig.
            # figures — e.g. a 0.95346 discount factor would print "0.95000000" for
            # safe_round(8). Callers asking for >2 dp (DCF/liquidation discount factors,
            # startup multipliers) depend on this.
            rounded_float = from_decimal(rounded_decimal, decimals)
            body = f"{rounded_float:.{decimals}f}"
            return escape(_apply_locale_separators(body, locale))
        except (ValueError, TypeError, AttributeError):
            # AttributeError occurs when trying to round Undefined objects
            return escape("0")

    @staticmethod
    def safe_round_or_dash(value: object, decimals: int = 2, locale: str = "en") -> str:
        """
        Round value with em-dash sentinel for missing data.

        Sibling of :py:meth:`safe_round` that returns the canonical em-dash
        ``"—"`` for None / Undefined / unparseable inputs, matching the
        sentinel :py:meth:`format_currency` / :py:meth:`format_percentage`
        already use.  Use this for fields that genuinely should not render
        as ``0`` when the engine returned no value (e.g. ``vc.target_roi_x``
        when the founder skipped the input — ``0×`` reads as a zero ROI
        target, ``—`` reads as "not set").

        See :py:meth:`safe_round` for the legacy ``"0"`` sentinel kept for
        the ~370 call sites across the 9 valuation methods that depend
        on it.

        Examples:
            safe_round_or_dash(4.567, 1) -> "4.6"
            safe_round_or_dash(None) -> "—"
            safe_round_or_dash(None, 1) -> "—"
        """
        if value is None:
            return escape("—")
        try:
            if hasattr(value, "__class__") and "Undefined" in str(type(value).__name__):
                return escape("—")
            if isinstance(value, str):
                value_decimal = to_decimal(value.replace(",", "").strip())
            else:
                value_decimal = to_decimal(value)
            rounded_decimal = bank_round(value_decimal, decimals)
            # Quantize to the REQUESTED precision. from_decimal() defaults to 2 dp, so
            # omitting `decimals` here silently clamps any decimals>2 render to 2 sig.
            # figures — e.g. a 0.95346 discount factor would print "0.95000000" for
            # safe_round(8). Callers asking for >2 dp (DCF/liquidation discount factors,
            # startup multipliers) depend on this.
            rounded_float = from_decimal(rounded_decimal, decimals)
            body = f"{rounded_float:.{decimals}f}"
            return escape(_apply_locale_separators(body, locale))
        except (ValueError, TypeError, AttributeError):
            return escape("—")

    @staticmethod
    def format_date(value: object, locale: str = "en") -> str:
        """
        Format a datetime as a date string with comprehensive null safety.

        Locale-aware month names (BET-291): EN keeps ``"June 07, 2026"``
        (unchanged); NL/FR render day-first with a localised month —
        ``"7 juni 2026"`` / ``"7 juin 2026"`` — the convention NL- and
        FR-language reports expect.

        Args:
            value: Date/datetime value to format
            locale: Render locale ("en", "nl", or "fr")

        Returns:
            Formatted date string
        """
        if value is None:
            return "N/A"
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value)
            except ValueError:
                return value
        if isinstance(value, (datetime, date)):
            loc = _normalize_locale(locale)
            if loc == "en":
                return value.strftime("%B %d, %Y")
            months = _LOCALIZED_MONTHS[loc]
            return f"{value.day} {months[value.month - 1]} {value.year}"
        try:
            return str(value)
        except (ValueError, TypeError, AttributeError):
            return "N/A"
        except ExternalServiceError:
            # For any other unexpected error, return safe default
            return "N/A"

    @staticmethod
    def decimal_divide(numerator: object, denominator: object) -> Decimal:
        """
        BANK-GRADE: Divide two values using Decimal arithmetic.

        Per BANK_GRADE_EXCELLENCE_FRAMEWORK.md:
        - All financial calculations MUST use Decimal (no floats)
        - Banker's rounding applied consistently
        - Precision maintained through all operations

        Args:
            numerator: Numerator value (converted to Decimal)
            denominator: Denominator value (converted to Decimal)

        Returns:
            Decimal result of division

        Raises:
            ValueError: If denominator is zero or conversion fails
        """
        if numerator is None or denominator is None:
            raise ValueError("Cannot divide None values")

        num_decimal = to_decimal(numerator)
        den_decimal = to_decimal(denominator)

        if den_decimal == Decimal("0"):
            raise ValueError("Division by zero")

        return num_decimal / den_decimal

    @staticmethod
    def decimal_multiply(value1: object, value2: object) -> Decimal:
        """
        BANK-GRADE: Multiply two values using Decimal arithmetic.

        Args:
            value1: First value (converted to Decimal)
            value2: Second value (converted to Decimal)

        Returns:
            Decimal result of multiplication
        """
        if value1 is None or value2 is None:
            raise ValueError("Cannot multiply None values")

        val1_decimal = to_decimal(value1)
        val2_decimal = to_decimal(value2)

        return val1_decimal * val2_decimal

    @staticmethod
    def decimal_add(value1: object, value2: object) -> Decimal:
        """
        BANK-GRADE: Add two values using Decimal arithmetic.

        Args:
            value1: First value (converted to Decimal)
            value2: Second value (converted to Decimal)

        Returns:
            Decimal result of addition
        """
        if value1 is None:
            value1 = Decimal("0")
        if value2 is None:
            value2 = Decimal("0")

        val1_decimal = to_decimal(value1)
        val2_decimal = to_decimal(value2)

        return val1_decimal + val2_decimal

    @staticmethod
    def decimal_subtract(minuend: object, subtrahend: object) -> Decimal:
        """
        BANK-GRADE: Subtract two values using Decimal arithmetic.

        Args:
            minuend: Value to subtract from (converted to Decimal)
            subtrahend: Value to subtract (converted to Decimal)

        Returns:
            Decimal result of subtraction
        """
        if minuend is None:
            minuend = Decimal("0")
        if subtrahend is None:
            subtrahend = Decimal("0")

        minuend_decimal = to_decimal(minuend)
        subtrahend_decimal = to_decimal(subtrahend)

        return minuend_decimal - subtrahend_decimal

    @staticmethod
    def to_decimal(value: object) -> Decimal:
        """
        BANK-GRADE: Convert any value to Decimal for calculations.

        This filter ensures all template calculations use Decimal precision.
        Use this before any arithmetic operations in templates.

        Args:
            value: Value to convert to Decimal

        Returns:
            Decimal value

        Raises:
            ValueError: If conversion fails
        """
        if value is None:
            raise ValueError("Cannot convert None to Decimal")
        return to_decimal(value)

    @staticmethod
    def safe_decimal_divide(
        numerator: object, denominator: object, default: object = None
    ) -> Decimal:
        """
        BANK-GRADE: Safely divide two values using Decimal arithmetic with fallback.

        This is a robust version that handles edge cases gracefully:
        - Division by zero → returns default (or Decimal('0'))
        - None values → returns default (or Decimal('0'))
        - Invalid conversions → returns default (or Decimal('0'))

        Args:
            numerator: Numerator value (converted to Decimal)
            denominator: Denominator value (converted to Decimal)
            default: Default value if division fails (default: Decimal('0'))

        Returns:
            Decimal result of division or default value
        """
        try:
            if numerator is None or denominator is None:
                return to_decimal(default) if default is not None else Decimal("0")

            num_decimal = to_decimal(numerator)
            den_decimal = to_decimal(denominator)

            if den_decimal == Decimal("0"):
                return to_decimal(default) if default is not None else Decimal("0")

            result = num_decimal / den_decimal

            # Validate result is not NaN/Infinity
            if result.is_nan() or result.is_infinite():
                return to_decimal(default) if default is not None else Decimal("0")

            return result
        except (ValueError, TypeError, InvalidOperation):
            return to_decimal(default) if default is not None else Decimal("0")

    @staticmethod
    def safe_decimal_multiply(value1: object, value2: object, default: object = None) -> Decimal:
        """
        BANK-GRADE: Safely multiply two values using Decimal arithmetic with fallback.

        Args:
            value1: First value (converted to Decimal)
            value2: Second value (converted to Decimal)
            default: Default value if multiplication fails (default: Decimal('0'))

        Returns:
            Decimal result of multiplication or default value
        """
        try:
            if value1 is None or value2 is None:
                return to_decimal(default) if default is not None else Decimal("0")

            val1_decimal = to_decimal(value1)
            val2_decimal = to_decimal(value2)

            result = val1_decimal * val2_decimal

            # Validate result is not NaN/Infinity
            if result.is_nan() or result.is_infinite():
                return to_decimal(default) if default is not None else Decimal("0")

            return result
        except (ValueError, TypeError, InvalidOperation):
            return to_decimal(default) if default is not None else Decimal("0")

    @staticmethod
    def safe_decimal_add(value1: object, value2: object, default: object = None) -> Decimal:
        """
        BANK-GRADE: Safely add two values using Decimal arithmetic with fallback.

        Args:
            value1: First value (converted to Decimal, defaults to Decimal('0') if None)
            value2: Second value (converted to Decimal, defaults to Decimal('0') if None)
            default: Default value if addition fails (default: Decimal('0'))

        Returns:
            Decimal result of addition or default value
        """
        try:
            val1_decimal = to_decimal(value1) if value1 is not None else Decimal("0")
            val2_decimal = to_decimal(value2) if value2 is not None else Decimal("0")

            result = val1_decimal + val2_decimal

            # Validate result is not NaN/Infinity
            if result.is_nan() or result.is_infinite():
                return to_decimal(default) if default is not None else Decimal("0")

            return result
        except (ValueError, TypeError, InvalidOperation):
            return to_decimal(default) if default is not None else Decimal("0")

    @staticmethod
    def safe_decimal_subtract(
        minuend: object, subtrahend: object, default: object = None
    ) -> Decimal:
        """
        BANK-GRADE: Safely subtract two values using Decimal arithmetic with fallback.

        Args:
            minuend: Value to subtract from (converted to Decimal, defaults to Decimal('0') if None)
            subtrahend: Value to subtract (converted to Decimal, defaults to Decimal('0') if None)
            default: Default value if subtraction fails (default: Decimal('0'))

        Returns:
            Decimal result of subtraction or default value
        """
        try:
            minuend_decimal = to_decimal(minuend) if minuend is not None else Decimal("0")
            subtrahend_decimal = to_decimal(subtrahend) if subtrahend is not None else Decimal("0")

            result = minuend_decimal - subtrahend_decimal

            # Validate result is not NaN/Infinity
            if result.is_nan() or result.is_infinite():
                return to_decimal(default) if default is not None else Decimal("0")

            return result
        except (ValueError, TypeError, InvalidOperation):
            return to_decimal(default) if default is not None else Decimal("0")

    @staticmethod
    def nl2br(value: object):
        """Convert newlines to HTML <br> tags, with proper HTML escaping.

        Returns Markup so Jinja2 autoescape treats the <br> tags as safe HTML
        while the original text content remains escaped.
        Handles both Unix (\\n) and Windows (\\r\\n) line endings.
        """
        if value is None:
            return ""
        from markupsafe import Markup

        escaped = str(escape(str(value)))
        normalized = escaped.replace("\r\n", "\n").replace("\r", "\n")
        return Markup(normalized.replace("\n", "<br>"))
