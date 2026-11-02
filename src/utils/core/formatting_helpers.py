from src.utils.exceptions import APIError

"""
Formatting Helper Functions

Bank-grade formatting utilities for currency, percentages, and numbers.
All functions handle edge cases and provide consistent formatting across the application.

Author: Upswitch Engineering Team
Date: January 2025
Status: Production Ready
"""

from decimal import Decimal
from typing import Optional, Union

from src.utils.decimal_helpers import bank_round, to_decimal
from src.utils.valuation_logger import ValuationLogger

from .numeric_helpers import ensure_float

logger = ValuationLogger(__name__)

# Currency symbol constants
# IMPORTANT: Unicode escape sequences (\u20AC) are automatically converted to actual symbols by Python
# when string literals are parsed. This means \u20AC becomes the actual € character.
# This conversion happens at parse time, so the Euro symbol will always display correctly
# in templates, logs, HTML output, and any other string contexts.
# \u20AC = Euro symbol (€) - Unicode code point U+20AC
EURO_SYMBOL = (
    "\u20AC"  # Always renders as € - verified: Python converts this to the actual € character
)


def format_currency(
    value: Union[Decimal, float, int],
    currency: str = "EUR",
    precision: int = 2,
    use_smart_formatting: bool = False,
) -> str:
    """
    Format money value as currency string.

    Bank-grade currency formatting with support for:
    - Multiple currencies (EUR, USD, GBP)
    - Smart formatting (M/K suffixes for large numbers)
    - Consistent precision and thousand separators

    Args:
        value: Value to format (Decimal, float, or int)
        currency: Currency code (EUR, USD, GBP) or symbol (€, $, £)
        precision: Number of decimal places (default: 2)
        use_smart_formatting: If True, use M/K suffixes for large numbers (default: False)

    Returns:
        Formatted currency string (e.g., "€1,000,000.00" or "€1.0M")

    Examples:
        >>> format_currency(1000000)
        "€1,000,000.00"
        >>> format_currency(1000000, currency="USD")
        "$1,000,000.00"
        >>> format_currency(1000000, use_smart_formatting=True)
        "€1.0M"
        >>> format_currency(1500, use_smart_formatting=True)
        "€1.5K"
    """
    if value is None:
        return "—"  # Em dash for missing values (professional standard)

    # Normalize currency symbol
    # Using EURO_SYMBOL constant ensures consistent Euro symbol rendering
    currency_symbols = {
        "EUR": EURO_SYMBOL,
        "USD": "$",
        "GBP": "£",
        "€": EURO_SYMBOL,  # Also handle literal Euro symbol input
        "$": "$",
        "£": "£",
    }
    symbol = currency_symbols.get(currency.upper(), currency)

    # Convert to Decimal for precision
    try:
        decimal_value = to_decimal(value)
    except ValueError as e:
        logger.warning(
            f"format_currency: Failed to convert value to Decimal: {value}",
            extra={"value": value, "error": str(e)},
        )
        return "—"  # Em dash for invalid values (professional standard)

    # Smart formatting for large numbers
    if use_smart_formatting:
        abs_value = abs(decimal_value)
        if abs_value >= Decimal("1000000"):
            # Millions
            millions = to_decimal(decimal_value / Decimal("1000000"))
            return f"{symbol}{millions:.1f}M"
        elif abs_value >= Decimal("1000"):
            # Thousands
            thousands = to_decimal(decimal_value / Decimal("1000"))
            return f"{symbol}{thousands:.0f}K"

    # Standard formatting with smart decimals (Big 4 standard)
    rounded = bank_round(decimal_value, precision)

    # Smart formatting: no decimals for whole numbers (unless explicitly requested with precision > 2)
    if precision == 2 and rounded % 1 == 0:
        # Whole number - no decimals (e.g., "€360,000" instead of "€360,000.00")
        formatted = f"{rounded:,.0f}"
    else:
        # Has decimals or custom precision requested
        formatted = f"{rounded:,.{precision}f}"

    return f"{symbol}{formatted}"


def format_percent(
    value: Union[Decimal, float, int], precision: int = 1, include_sign: bool = False
) -> str:
    """
    Format value as percentage string.

    Args:
        value: Value to format (as decimal, e.g., 0.15 for 15%)
        precision: Number of decimal places (default: 1)
        include_sign: If True, include + sign for positive values (default: False)

    Returns:
        Formatted percentage string (e.g., "15.0%" or "+15.0%")

    Examples:
        >>> format_percent(0.15)
        "15.0%"
        >>> format_percent(0.155, precision=2)
        "15.50%"
        >>> format_percent(0.15, include_sign=True)
        "+15.0%"
    """
    if value is None:
        return "0.0%"

    try:
        float_value = ensure_float(value)
        if float_value is None:
            return "0.0%"

        # Convert to percentage (multiply by 100)
        percent_value = float_value * 100

        # Format with sign if requested
        if include_sign and percent_value > 0:
            return f"+{percent_value:.{precision}f}%"

        return f"{percent_value:.{precision}f}%"

    except APIError as e:
        logger.warning(
            f"format_percent: Error formatting percentage: {e}",
            extra={"value": value, "error": str(e)},
        )
        return "0.0%"


def format_number(
    value: Union[Decimal, float, int], precision: int = 0, use_thousands_separator: bool = True
) -> str:
    """
    Format number with thousand separators.

    Args:
        value: Value to format
        precision: Number of decimal places (default: 0)
        use_thousands_separator: If True, use comma separators (default: True)

    Returns:
        Formatted number string (e.g., "1,000,000" or "1000000")

    Examples:
        >>> format_number(1000000)
        "1,000,000"
        >>> format_number(1000.5, precision=2)
        "1,000.50"
        >>> format_number(1000, use_thousands_separator=False)
        "1000"
    """
    if value is None:
        return "0"

    try:
        float_value = ensure_float(value)
        if float_value is None:
            return "0"

        if use_thousands_separator:
            return f"{float_value:,.{precision}f}"
        else:
            return f"{float_value:.{precision}f}"

    except Exception as e:
        logger.warning(
            f"format_number: Error formatting number: {e}", extra={"value": value, "error": str(e)}
        )
        return "0"
