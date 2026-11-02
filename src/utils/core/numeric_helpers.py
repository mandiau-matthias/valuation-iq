"""
Numeric Helper Functions

Bank-grade numeric utilities for type conversion, safe division, and validation.
All functions are defensive and handle edge cases (None, NaN, Infinity, zero division).

Author: Upswitch Engineering Team
Date: January 2025
Status: Production Ready
"""

import math
from decimal import Decimal
from typing import Any, Optional, Union

from src.utils.decimal_helpers import safe_money_divide, to_decimal
from src.utils.valuation_logger import ValuationLogger

logger = ValuationLogger(__name__)


def ensure_float(value: Any) -> Optional[Decimal]:
    """
    Convert value to float, handling None and Decimal types.

    Bank-grade conversion that handles:
    - None → None
    - Decimal → float
    - int → float
    - float → to_decimal(validated)
    - str → to_decimal(if numeric)
    - NaN/Infinity → None (defensive)

    Args:
        value: Value to convert (can be None, float, int, Decimal, str)

    Returns: Decimal value or None if conversion fails or value is invalid

    Examples:
        >>> ensure_float(10)
        10.0
        >>> ensure_float(Decimal('10.5'))
        10.5
        >>> ensure_float(None)
        None
        >>> ensure_float('invalid')
        None
    """
    if value is None:
        return None

    # Handle Decimal type
    if isinstance(value, Decimal):
        try:
            result = to_decimal(value)
            if result.is_nan() or result.is_infinite():
                logger.warning(
                    f"ensure_float: Decimal converts to invalid to_decimal(NaN/Infinity): {value}",
                    extra={"value": str(value), "result": result},
                )
                return None
            return result
        except (ValueError, TypeError, OverflowError) as e:
            logger.warning(
                f"ensure_float: Failed to convert Decimal to float: {value}",
                extra={"value": str(value), "error": str(e)},
            )
            return None

    # Handle numeric types
    if isinstance(value, (int, float)):
        # Validate float is not NaN/Infinity
        if isinstance(value, float):
            if math.isnan(value):
                logger.warning("ensure_float: Input is NaN", extra={"value": value})
                return None
            if math.isinf(value):
                logger.warning("ensure_float: Input is Infinity", extra={"value": value})
                return None
        return to_decimal(value)

    # Handle string
    if isinstance(value, str):
        try:
            # Remove currency symbols and whitespace
            cleaned = value.strip().replace("\u20AC", "").replace("$", "").replace(",", "").strip()
            if not cleaned:
                return None
            result = to_decimal(cleaned)
            if isinstance(result, Decimal) and (result.is_nan() or result.is_infinite()):
                logger.warning(
                    f"ensure_float: String converts to invalid to_decimal(NaN/Infinity): {value}",
                    extra={"value": value, "result": result},
                )
                return None
            return result
        except (ValueError, TypeError) as e:
            logger.debug(
                f"ensure_float: Failed to convert string to float: {value}",
                extra={"value": value, "error": str(e)},
            )
            return None

    # Unknown type
    logger.debug(
        f"ensure_float: Cannot convert type {type(value).__name__} to float",
        extra={"value": value, "type": type(value).__name__},
    )
    return None


def _is_invalid_float(value: object) -> bool:
    return isinstance(value, float) and (math.isnan(value) or math.isinf(value))


def _log_invalid_operand(
    operand_name: str,
    *,
    numerator: object,
    denominator: object,
    default: Optional[Decimal],
) -> None:
    operand_value = numerator if operand_name == "numerator" else denominator
    logger.warning(
        f"safe_divide: Invalid {operand_name} (NaN/Infinity): {operand_value}",
        extra={"numerator": numerator, "denominator": denominator, "default": default},
    )


def _has_invalid_float_operand(
    numerator: object,
    denominator: object,
    default: Optional[Decimal],
) -> bool:
    if _is_invalid_float(numerator):
        _log_invalid_operand(
            "numerator",
            numerator=numerator,
            denominator=denominator,
            default=default,
        )
        return True
    if _is_invalid_float(denominator):
        _log_invalid_operand(
            "denominator",
            numerator=numerator,
            denominator=denominator,
            default=default,
        )
        return True
    return False


def _is_zero_denominator(
    numerator: object,
    denominator: object,
    default: Optional[Decimal],
) -> bool:
    if denominator != 0:
        return False
    logger.warning(
        "safe_divide: Division by zero",
        extra={"numerator": numerator, "denominator": denominator, "default": default},
    )
    return True


def _decimal_division_result(numerator: Decimal, denominator: Decimal) -> Optional[Decimal]:
    result_decimal = safe_money_divide(numerator, denominator, Decimal("0"))
    return ensure_float(result_decimal)


def _coerced_division_result(
    numerator: object,
    denominator: object,
) -> Optional[Decimal]:
    num_float = ensure_float(numerator)
    den_float = ensure_float(denominator)

    if num_float is None or den_float is None:
        return None
    if den_float == 0:
        return None
    return num_float / den_float


def _is_invalid_division_result(result: object) -> bool:
    if isinstance(result, Decimal):
        return result.is_nan() or result.is_infinite()
    if isinstance(result, float):
        return math.isnan(result) or math.isinf(result)
    return False


def _log_invalid_division_result(
    result: object,
    *,
    numerator: object,
    denominator: object,
    default: Optional[Decimal],
) -> None:
    logger.warning(
        f"safe_divide: Invalid result (NaN/Infinity): {result}",
        extra={
            "numerator": numerator,
            "denominator": denominator,
            "result": result,
            "default": default,
        },
    )


def safe_divide(
    numerator: Union[float, int, Decimal, None],
    denominator: Union[float, int, Decimal, None],
    default: Optional[Decimal] = None,
) -> Optional[Decimal]:
    """
    Safely divide two numbers, handling zero denominator and invalid inputs.

    Bank-grade division that handles:
    - Division by zero → returns default
    - None inputs → returns default
    - NaN/Infinity inputs → returns default
    - Invalid result (NaN/Infinity) → returns default

    Args:
        numerator: Numerator value
        denominator: Denominator value
        default: Value to return if division fails (default: None)

    Returns:
        Division result or default value

    Examples:
        >>> safe_divide(10, 2)
        5.0
        >>> safe_divide(10, 0)
        None
        >>> safe_divide(10, 0, default=0.0)
        0.0
        >>> safe_divide(None, 2)
        None
    """
    if numerator is None or denominator is None:
        return default

    if _has_invalid_float_operand(numerator, denominator, default):
        return default

    if _is_zero_denominator(numerator, denominator, default):
        return default

    try:
        if isinstance(numerator, Decimal) and isinstance(denominator, Decimal):
            return _decimal_division_result(numerator, denominator)

        result = _coerced_division_result(numerator, denominator)
        if result is None:
            return default

        if _is_invalid_division_result(result):
            _log_invalid_division_result(
                result,
                numerator=numerator,
                denominator=denominator,
                default=default,
            )
            return default
        return result

    except (TypeError, ValueError, ZeroDivisionError) as e:
        logger.warning(
            f"safe_divide: Error during division: {e}",
            extra={
                "numerator": numerator,
                "denominator": denominator,
                "error": str(e),
                "default": default,
            },
        )
        return default


def validate_numeric(
    value: Union[Decimal, Decimal, int, None],
    min_value: Optional[Union[Decimal, Decimal, int]] = None,
    max_value: Optional[Union[Decimal, Decimal, int]] = None,
    allow_none: bool = False,
) -> Optional[Decimal]:
    """
    Validate numeric value for NaN/Infinity and range, returning float.

    This is a float-focused version of validate_numeric_value from decimal_helpers.
    For Decimal validation, use decimal_helpers.validate_numeric_value directly.

    Args:
        value: Value to validate
        min_value: Minimum allowed value (optional)
        max_value: Maximum allowed value (optional)
        allow_none: Whether to allow None values (default: False)

    Returns:
        Validated float value or None if allow_none=True and value is None

    Raises:
        ValueError: If value is None (and allow_none=False), NaN, Infinity, or outside range

    Examples:
        >>> validate_numeric(10.5, min_value=0, max_value=100)
        10.5
        >>> validate_numeric(None, allow_none=True)
        None
        >>> validate_numeric(to_decimal('nan'))
        ValueError: Value is NaN
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

    # Convert to float
    float_value = ensure_float(value)
    if float_value is None:
        raise ValueError(f"Cannot validate value: {value}")

    # Check range
    if min_value is not None:
        min_float = ensure_float(min_value)
        if min_float is not None and float_value < min_float:
            raise ValueError(f"Value {float_value} is below minimum {min_float}")

    if max_value is not None:
        max_float = ensure_float(max_value)
        if max_float is not None and float_value > max_float:
            raise ValueError(f"Value {float_value} is above maximum {max_float}")

    return float_value


def round_value(value: Union[float, Decimal, int], precision: int = 2) -> Decimal:
    """
    Round value to specified precision using banker's rounding.

    Args:
        value: Value to round
        precision: Number of decimal places (default: 2)

    Returns:
        Rounded float value

    Examples:
        >>> round_value(10.555, 2)
        10.56
        >>> round_value(10.545, 2)
        10.54  # Banker's rounding
    """
    if value is None:
        raise ValueError("Cannot round None value")

    # Convert to Decimal for banker's rounding
    try:
        from src.utils.decimal_helpers import bank_round

        if isinstance(value, Decimal):
            rounded_decimal = bank_round(value, precision)
        else:
            decimal_value = to_decimal(value)
            rounded_decimal = bank_round(decimal_value, precision)
        return ensure_float(rounded_decimal) or 0.0
    except Exception as e:
        logger.warning(
            f"round_value: Error during rounding: {e}",
            extra={"value": value, "precision": precision, "error": str(e)},
        )
        # Fallback to standard rounding
        return round(to_decimal(value), precision)
