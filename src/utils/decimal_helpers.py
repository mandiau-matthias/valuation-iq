"""
Decimal Helpers for Financial Calculations

Bank-grade precision for all money calculations using Python's Decimal type.
Implements ROUND_HALF_EVEN (banker's rounding) for consistent, unbiased rounding.

CRITICAL: All financial calculations MUST use Decimal, never float.
This ensures:
- No rounding errors
- Deterministic results
- Bank-grade precision
- Consistent across all calculation steps
"""

import math
from decimal import ROUND_HALF_EVEN, Context, Decimal, InvalidOperation, getcontext
from typing import Any, Optional, Union

from src.utils.valuation_band_helpers import (
    BAND_MEANINGFUL_HALF_SPREAD_THRESHOLD,
    EV_BAND_SOURCE_ENGINE_EQUITY,
    EV_BAND_SOURCE_PIPELINE,
    band_is_meaningful,
    pin_band_monotone,
    reconcile_asking_price_after_phantom_bridge,
    select_ev_band,
)


# Lazy import to avoid circular dependency
def _get_logger():
    """Lazy import of logger to avoid circular dependency."""
    from src.utils.logging import get_logger

    return get_logger(__name__)


logger = _get_logger()

# Configure Decimal context for financial calculations
# Precision: 28 decimal places (sufficient for EUR calculations)
# Rounding: ROUND_HALF_EVEN (banker's rounding - unbiased)
FINANCIAL_CONTEXT = Context(
    prec=28, rounding=ROUND_HALF_EVEN, Emin=-999999, Emax=999999, capitals=1, clamp=0
)

# Set as default context
getcontext().prec = 28
getcontext().rounding = ROUND_HALF_EVEN

# Type alias for money
Money = Decimal


def to_decimal(value: Union[str, int, float, Decimal, None]) -> Decimal:
    """
    Convert any numeric type to Decimal safely.

    Args:
        value: Value to convert (str, int, float, Decimal, or None)

    Returns:
        Decimal value

    Raises:
        ValueError: If value cannot be converted to Decimal or contains NaN/Infinity
    """
    if value is None:
        raise ValueError("Cannot convert None to Decimal")

    if isinstance(value, Decimal):
        # Decimal doesn't support NaN/Infinity, but check for invalid operations
        if value.is_nan() or value.is_infinite():
            raise ValueError(f"Cannot convert invalid Decimal (NaN/Infinity) to Decimal: {value}")
        return value

    if isinstance(value, str):
        # Remove currency symbols and whitespace
        cleaned = value.strip().replace("\u20ac", "").replace("$", "").replace(",", "").strip()
        if not cleaned:
            raise ValueError(f"Cannot convert empty string to Decimal: {value}")
        try:
            decimal_value = Decimal(cleaned)
            if decimal_value.is_nan() or decimal_value.is_infinite():
                raise ValueError(f"String converts to invalid Decimal (NaN/Infinity): {value}")
            return decimal_value
        except (InvalidOperation, ValueError) as e:
            raise ValueError(f"Cannot convert string to Decimal: {value}") from e

    if isinstance(value, (int, float)):
        # CRITICAL: Check for NaN/Infinity before conversion
        if isinstance(value, float):
            if math.isnan(value):
                raise ValueError(f"Cannot convert NaN to Decimal: {value}")
            if math.isinf(value):
                raise ValueError(f"Cannot convert Infinity to Decimal: {value}")
            # Use string conversion to preserve precision
            try:
                decimal_value = Decimal(str(value))
                if decimal_value.is_nan() or decimal_value.is_infinite():
                    raise ValueError(f"Float converts to invalid Decimal (NaN/Infinity): {value}")
                return decimal_value
            except (InvalidOperation, ValueError) as e:
                raise ValueError(f"Cannot convert float to Decimal: {value}") from e
        # int values are always valid
        return Decimal(value)

    raise ValueError(f"Cannot convert {type(value).__name__} to Decimal: {value}")


def from_decimal(value: Decimal, precision: int = 2) -> Decimal:
    """
    Round Decimal value with banker's rounding.

    NOTE: For JSON serialization, use decimal_to_float() instead.

    Args:
        value: Decimal value
        precision: Number of decimal places (default: 2 for currency)

    Returns:
        Decimal value rounded to specified precision
    """
    if not isinstance(value, Decimal):
        raise ValueError(f"Expected Decimal, got {type(value).__name__}")

    # Round using banker's rounding
    rounded = value.quantize(Decimal("0.1") ** precision, rounding=ROUND_HALF_EVEN)
    return rounded


def decimal_to_float(value: Decimal, precision: int = 2) -> float:
    """
    Convert Decimal to float for JSON serialization.

    This function is specifically for serializing Decimal values to JSON-safe floats.
    Use this when preparing data for API responses, JSON dumps, or frontend communication.

    Args:
        value: Decimal value
        precision: Number of decimal places (default: 2 for currency)

    Returns:
        float value rounded to specified precision using banker's rounding

    Example:
        >>> decimal_to_float(Decimal('500000.50'), precision=2)
        500000.5
        >>> json.dumps({"value": decimal_to_float(Decimal('1234.567'))})
        '{"value": 1234.57}'
    """
    if not isinstance(value, Decimal):
        raise ValueError(f"Expected Decimal, got {type(value).__name__}")

    # Round using banker's rounding
    rounded = value.quantize(Decimal("0.1") ** precision, rounding=ROUND_HALF_EVEN)
    # Bank-grade: Convert to float for JSON serialization
    return float(rounded)


def safe_decimal(
    value: Union[str, int, float, Decimal, None], default: Decimal = Decimal("0")
) -> Decimal:
    """
    Safely convert to Decimal with default fallback.

    Args:
        value: Value to convert
        default: Default value if conversion fails (default: 0)

    Returns:
        Decimal value or default
    """
    if value is None:
        return default

    try:
        return to_decimal(value)
    except (ValueError, TypeError) as e:
        logger.warning(
            f"Failed to convert {value} to Decimal, using default {default}",
            extra={"value": value, "error": str(e), "default": str(default)},
        )
        return default


def bank_round(value: Decimal, precision: int = 2) -> Decimal:
    """
    Round using banker's rounding (ROUND_HALF_EVEN).

    Banker's rounding is unbiased and preferred for financial calculations:
    - 0.5 rounds to nearest even number
    - Example: 2.5 → 2, 3.5 → 4

    Args:
        value: Decimal value to round
        precision: Number of decimal places (default: 2 for currency)

    Returns:
        Rounded Decimal value
    """
    if not isinstance(value, Decimal):
        value = to_decimal(value)

    quantizer = Decimal("0.1") ** precision
    return value.quantize(quantizer, rounding=ROUND_HALF_EVEN)


def validate_money(
    value: Decimal, min_value: Optional[Decimal] = None, max_value: Optional[Decimal] = None
) -> Decimal:
    """
    Validate money value is within acceptable range.

    Args:
        value: Decimal value to validate
        min_value: Minimum allowed value (optional)
        max_value: Maximum allowed value (optional)

    Returns:
        Validated Decimal value

    Raises:
        ValueError: If value is outside acceptable range
    """
    if not isinstance(value, Decimal):
        value = to_decimal(value)

    if min_value is not None and value < min_value:
        raise ValueError(f"Value {value} is below minimum {min_value}")

    if max_value is not None and value > max_value:
        raise ValueError(f"Value {value} is above maximum {max_value}")

    return value


def money_multiply(
    amount: Union[Decimal, float, int], multiplier: Union[Decimal, float, int]
) -> Decimal:
    """
    Multiply money amount by multiplier with proper rounding.

    Args:
        amount: Money amount
        multiplier: Multiplier (e.g., 1.2 for 20% increase)

    Returns:
        Decimal result
    """
    amount_decimal = to_decimal(amount)
    multiplier_decimal = to_decimal(multiplier)
    return amount_decimal * multiplier_decimal


def money_add(*amounts: Union[Decimal, float, int]) -> Decimal:
    """
    Add multiple money amounts with proper precision.

    Args:
        *amounts: Money amounts to add

    Returns:
        Decimal sum
    """
    result = Decimal("0")
    for amount in amounts:
        result += to_decimal(amount)
    return result


def money_subtract(
    minuend: Union[Decimal, float, int], subtrahend: Union[Decimal, float, int]
) -> Decimal:
    """
    Subtract money amounts with proper precision.

    Args:
        minuend: Amount to subtract from
        subtrahend: Amount to subtract

    Returns:
        Decimal difference
    """
    return to_decimal(minuend) - to_decimal(subtrahend)


def money_divide(
    numerator: Union[Decimal, float, int], denominator: Union[Decimal, float, int]
) -> Decimal:
    """
    Divide money amounts with proper precision.

    Args:
        numerator: Amount to divide
        denominator: Divisor

    Returns:
        Decimal quotient

    Raises:
        ZeroDivisionError: If denominator is zero
        ValueError: If inputs contain NaN/Infinity
    """
    numerator_decimal = to_decimal(numerator)
    denominator_decimal = to_decimal(denominator)

    if denominator_decimal == 0:
        raise ZeroDivisionError("Cannot divide by zero")

    result = numerator_decimal / denominator_decimal

    # Validate result is not NaN/Infinity
    if result.is_nan() or result.is_infinite():
        raise ValueError(
            f"Division result is invalid (NaN/Infinity): {numerator_decimal} / {denominator_decimal} = {result}"
        )

    return result


def safe_money_divide(
    numerator: Union[Decimal, float, int, None],
    denominator: Union[Decimal, float, int, None],
    default: Decimal = Decimal("0"),
) -> Decimal:
    """
    Safely divide money amounts with fallback to default value.

    Handles:
    - Division by zero → returns default
    - NaN/Infinity inputs → returns default
    - None inputs → returns default
    - Invalid result (NaN/Infinity) → returns default

    Args:
        numerator: Amount to divide
        denominator: Divisor
        default: Default value if division is invalid (default: 0)

    Returns:
        Decimal quotient or default value
    """
    try:
        # Check for None first
        if numerator is None or denominator is None:
            logger.warning(
                f"safe_money_divide: None input detected, using default {default}",
                extra={"numerator": numerator, "denominator": denominator, "default": str(default)},
            )
            return default

        # Check for NaN/Infinity in float inputs
        if isinstance(numerator, float):
            if math.isnan(numerator) or math.isinf(numerator):
                logger.warning(
                    f"safe_money_divide: Invalid numerator ({numerator}), using default {default}",
                    extra={
                        "numerator": numerator,
                        "denominator": denominator,
                        "default": str(default),
                    },
                )
                return default

        if isinstance(denominator, float):
            if math.isnan(denominator) or math.isinf(denominator):
                logger.warning(
                    f"safe_money_divide: Invalid denominator ({denominator}), using default {default}",
                    extra={
                        "numerator": numerator,
                        "denominator": denominator,
                        "default": str(default),
                    },
                )
                return default

        numerator_decimal = to_decimal(numerator)
        denominator_decimal = to_decimal(denominator)

        if denominator_decimal == 0:
            logger.warning(
                f"safe_money_divide: Division by zero, using default {default}",
                extra={
                    "numerator": str(numerator_decimal),
                    "denominator": str(denominator_decimal),
                    "default": str(default),
                },
            )
            return default

        result = numerator_decimal / denominator_decimal

        # Validate result is not NaN/Infinity
        if result.is_nan() or result.is_infinite():
            logger.warning(
                f"safe_money_divide: Invalid result (NaN/Infinity), using default {default}",
                extra={
                    "numerator": str(numerator_decimal),
                    "denominator": str(denominator_decimal),
                    "result": str(result),
                    "default": str(default),
                },
            )
            return default

        return result

    except (ValueError, ZeroDivisionError, TypeError, InvalidOperation) as e:
        logger.warning(
            f"safe_money_divide: Error during division, using default {default}",
            extra={
                "numerator": numerator,
                "denominator": denominator,
                "error": str(e),
                "default": str(default),
            },
        )
        return default


def percentage_to_decimal(percentage: Union[Decimal, float, int]) -> Decimal:
    """
    Convert percentage to decimal (e.g., 20 → 0.20).

    Args:
        percentage: Percentage value (e.g., 20 for 20%)

    Returns:
        Decimal value (e.g., 0.20)
    """
    return to_decimal(percentage) / Decimal("100")


def decimal_to_percentage(decimal: Union[Decimal, float, int]) -> Decimal:
    """
    Convert decimal to percentage (e.g., 0.20 → 20).

    Args:
        decimal: Decimal value (e.g., 0.20)

    Returns:
        Decimal percentage (e.g., 20)
    """
    return to_decimal(decimal) * Decimal("100")


def calculate_decimal_cagr(
    beginning_value: Union[Decimal, float, int],
    ending_value: Union[Decimal, float, int],
    periods: Union[Decimal, float, int],
    *,
    as_percentage: bool = False,
) -> Decimal:
    """
    Calculate CAGR safely when inputs are Decimal-backed financial values.

    Python's ``Decimal`` type does not reliably support fractional exponents in
    all environments, so this helper performs the exponentiation in float space
    after validating inputs, then converts the result back to Decimal.

    Args:
        beginning_value: Starting value (> 0)
        ending_value: Ending value (> 0)
        periods: Number of periods (> 0)
        as_percentage: When True, return percentage points instead of decimal form

    Returns:
        CAGR as Decimal (e.g. 0.10 for 10%, or 10.0 when ``as_percentage=True``)

    Raises:
        ValueError: If inputs are invalid or produce NaN/Infinity
        ZeroDivisionError: If periods is zero
    """
    start = to_decimal(beginning_value)
    end = to_decimal(ending_value)
    period_count = to_decimal(periods)

    if start <= 0:
        raise ValueError(f"Beginning value must be > 0, got {start}")
    if end <= 0:
        raise ValueError(f"Ending value must be > 0, got {end}")
    if period_count <= 0:
        raise ZeroDivisionError("Periods must be > 0")

    ratio = end / start
    cagr_float = float(ratio) ** (1.0 / float(period_count)) - 1.0

    if math.isnan(cagr_float) or math.isinf(cagr_float):
        raise ValueError(
            f"CAGR calculation produced invalid result: start={start}, end={end}, periods={period_count}"
        )

    cagr = to_decimal(cagr_float)
    return cagr * Decimal("100.0") if as_percentage else cagr


def apply_discount(
    base_value: Union[Decimal, float, int], discount_percentage: Union[Decimal, float, int]
) -> Decimal:
    """
    Apply discount percentage to base value.

    Args:
        base_value: Base money amount
        discount_percentage: Discount percentage (e.g., -20 for -20%)

    Returns:
        Decimal result after discount
    """
    base = to_decimal(base_value)
    discount = percentage_to_decimal(discount_percentage)
    return base * (Decimal("1") + discount)


def format_money(value: Decimal, currency: str = "EUR", precision: int = 2) -> str:
    """
    Format money value for display.

    Args:
        value: Decimal value
        currency: Currency symbol (default: EUR)
        precision: Number of decimal places (default: 2)

    Returns:
        Formatted string (e.g., "€1,000,000.00")
    """
    rounded = bank_round(value, precision)
    # Format with thousands separator
    formatted = f"{rounded:,.{precision}f}"
    return f"{currency}{formatted}" if currency else formatted


def validate_numeric_value(
    value: Union[Decimal, float, int, None],
    min_value: Optional[Union[Decimal, float, int]] = None,
    max_value: Optional[Union[Decimal, float, int]] = None,
    allow_none: bool = False,
) -> Optional[Decimal]:
    """
    Validate numeric value for NaN/Infinity and range.

    Args:
        value: Value to validate
        min_value: Minimum allowed value (optional)
        max_value: Maximum allowed value (optional)
        allow_none: Whether to allow None values (default: False)

    Returns:
        Validated Decimal value or None if allow_none=True and value is None

    Raises:
        ValueError: If value is None (and allow_none=False), NaN, Infinity, or outside range
    """
    if value is None:
        if allow_none:
            return None
        raise ValueError("Value cannot be None")

    # Check for NaN/Infinity in float inputs
    if isinstance(value, float):
        if math.isnan(value):
            raise ValueError(f"Value is NaN: {value}")
        if math.isinf(value):
            raise ValueError(f"Value is Infinity: {value}")

    try:
        decimal_value = to_decimal(value)
    except ValueError as e:
        raise ValueError(f"Cannot validate value: {value}") from e

    # Check range
    if min_value is not None:
        min_decimal = to_decimal(min_value)
        if decimal_value < min_decimal:
            raise ValueError(f"Value {decimal_value} is below minimum {min_decimal}")

    if max_value is not None:
        max_decimal = to_decimal(max_value)
        if decimal_value > max_decimal:
            raise ValueError(f"Value {decimal_value} is above maximum {max_decimal}")

    return decimal_value


def is_valid_numeric(value: Union[Decimal, float, int, None]) -> bool:
    """
    Check if value is a valid numeric (not None, NaN, or Infinity).

    Args:
        value: Value to check

    Returns:
        True if value is valid numeric, False otherwise
    """
    if value is None:
        return False

    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return False

    try:
        decimal_value = to_decimal(value)
        return not (decimal_value.is_nan() or decimal_value.is_infinite())
    except (ValueError, InvalidOperation):
        return False


# ─────────────────────────────────────────────────────────────────────
# Canonical coercion helpers (single source of truth)
#
# These replace the 11+ duplicated _safe_decimal / to_float / etc.
# scattered across report sections, aggregator, and route files.
# ─────────────────────────────────────────────────────────────────────


def safe_decimal_or_zero(value: Any) -> Decimal:
    """Parse *value* into a finite ``Decimal``; fallback ``Decimal('0')``.

    Use when a numeric value is needed for arithmetic and ``None`` / bad
    input should silently become zero (e.g., EBITDA, equity value, weights
    in report sections).
    """
    if value is None:
        return Decimal("0")
    try:
        if isinstance(value, float) and (
            value != value or value == float("inf") or value == float("-inf")
        ):
            return Decimal("0")
        d = Decimal(str(value)) if not isinstance(value, Decimal) else value
        if d.is_nan() or d.is_infinite():
            return Decimal("0")
        return d
    except (TypeError, ValueError, ArithmeticError):
        return Decimal("0")


def optional_decimal(value: Any) -> Optional[Decimal]:
    """Parse *value* into a finite ``Decimal``, or ``None``.

    Use when the distinction between "no value" (``None``) and "zero" matters
    (e.g., weight detection in the canonical contract, business-type multiples).
    """
    if value is None:
        return None
    try:
        if isinstance(value, float) and (
            value != value or value == float("inf") or value == float("-inf")
        ):
            return None
        d = Decimal(str(value)) if not isinstance(value, Decimal) else value
        if d.is_nan() or d.is_infinite():
            return None
        return d
    except (TypeError, ValueError, ArithmeticError):
        return None


def safe_float(value: Any) -> float:
    """Convert *value* to a finite ``float``; NaN / Inf / None → ``0.0``.

    Use in report context building where template values must be JSON-safe
    floats.
    """
    if value is None:
        return 0.0
    try:
        if isinstance(value, Decimal):
            if value.is_nan() or value.is_infinite():
                return 0.0
            return float(value)
        f = float(value)
        if f != f or f == float("inf") or f == float("-inf"):
            return 0.0
        return f
    except (TypeError, ValueError):
        return 0.0


def float_or_none(value: Any) -> Optional[float]:
    """Convert *value* to a finite ``float``, or ``None``.

    Use when the absence of a value must be preserved (e.g., optional
    SaaS metrics where ``None`` means "not applicable").
    """
    if value is None:
        return None
    try:
        if isinstance(value, Decimal):
            if value.is_nan() or value.is_infinite():
                return None
            return float(value)
        f = float(value)
        if f != f or f == float("inf") or f == float("-inf"):
            return None
        return f
    except (TypeError, ValueError):
        return None
