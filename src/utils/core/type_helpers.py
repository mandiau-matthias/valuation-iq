"""
Type Helper Functions

Bank-grade type conversion and normalization utilities.
All functions handle edge cases and provide consistent type handling.

Author: Upswitch Engineering Team
Date: January 2025
Status: Production Ready
"""

from decimal import Decimal
from typing import Any, Optional, Union

from src.utils.decimal_helpers import safe_decimal, to_decimal
from src.utils.valuation_logger import ValuationLogger

from .numeric_helpers import ensure_float

logger = ValuationLogger(__name__)


def ensure_type(value: Any, target_type: type, default: Optional[Any] = None) -> Optional[Any]:
    """
    Convert value to target type with fallback to default.

    Args:
        value: Value to convert
        target_type: Target type (int, float, Decimal, str, bool)
        default: Default value if conversion fails (optional)

    Returns:
        Converted value or default

    Examples:
        >>> ensure_type("10", int)
        10
        >>> ensure_type("invalid", int, default=0)
        0
        >>> ensure_type(10.5, int)
        10
    """
    if value is None:
        return default

    # Already correct type
    if isinstance(value, target_type):
        return value

    try:
        if target_type == int:
            float_val = ensure_float(value)
            return int(float_val) if float_val is not None else default

        elif target_type == float:
            return ensure_float(value) or default

        elif target_type == Decimal:
            return safe_decimal(value, Decimal("0") if default is None else default)

        elif target_type == str:
            return str(value)

        elif target_type == bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)
            if isinstance(value, str):
                return value.lower() in ("true", "1", "yes", "on")
            return default

        else:
            # Try direct conversion
            return target_type(value)

    except (ValueError, TypeError, OverflowError) as e:
        logger.debug(
            f"ensure_type: Failed to convert {type(value).__name__} to {target_type.__name__}: {e}",
            extra={"value": value, "target_type": target_type.__name__, "error": str(e)},
        )
        return default


def convert_type(value: Any, from_type: type, to_type: type) -> Optional[Any]:
    """
    Convert value from one type to another.

    Args:
        value: Value to convert
        from_type: Expected source type
        to_type: Target type

    Returns:
        Converted value or None if conversion fails

    Examples:
        >>> convert_type(10, int, float)
        10.0
        >>> convert_type("10", str, int)
        10
    """
    if not isinstance(value, from_type):
        logger.warning(
            f"convert_type: Value is not of expected type {from_type.__name__}",
            extra={"value": value, "from_type": from_type.__name__, "to_type": to_type.__name__},
        )
        return None

    return ensure_type(value, to_type)


def normalize_type(value: Any, preferred_type: type = float) -> Optional[Any]:
    """
    Normalize value to preferred numeric type.

    Converts various numeric types (int, float, Decimal, str) to preferred type.

    Args:
        value: Value to normalize
        preferred_type: Preferred type (int, float, or Decimal) - default: Decimal

    Returns:
        Normalized value or None if conversion fails

    Examples:
        >>> normalize_type(Decimal('10.5'), float)
        10.5
        >>> normalize_type("10", int)
        10
    """
    if value is None:
        return None

    if preferred_type == float:
        return ensure_float(value)

    elif preferred_type == int:
        float_val = ensure_float(value)
        return int(float_val) if float_val is not None else None

    elif preferred_type == Decimal:
        return safe_decimal(value, Decimal("0"))

    return ensure_type(value, preferred_type)
