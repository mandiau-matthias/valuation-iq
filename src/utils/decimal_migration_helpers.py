"""
Decimal Migration Helpers

Utilities to assist in migrating from float to Decimal for financial calculations.
These helpers provide safe conversion and migration patterns.

Author: Upswitch Engineering Team
Date: November 2025
Status: Migration Support
"""

from decimal import Decimal
from typing import Any, Callable, Optional, Union

from src.utils.decimal_helpers import bank_round, to_decimal
from src.utils.valuation_logger import ValuationLogger

logger = ValuationLogger(__name__)


def migrate_float_literal(value: Union[float, int, str]) -> Decimal:
    """
    Migrate a float literal to Decimal.

    Use this when replacing float literals in calculations.

    Args:
        value: Float or int value to convert

    Returns:
        Decimal value

    Examples:
        # Before:
        result = base_value * 1.2

        # After:
        result = base_value * migrate_float_literal(1.2)
        # Or better:
        result = base_value * Decimal('1.2')
    """
    return to_decimal(value)


def migrate_float_call(func_result: Any) -> Decimal:
    """
    Migrate a to_decimal() call result to Decimal.

    Use this when replacing to_decimal() calls in calculations.

    Args:
        func_result: Result from a function that returns float

    Returns:
        Decimal value

    Examples:
        # Before:
        result = to_decimal(some_value)

        # After:
        result = migrate_float_call(some_value)
        # Or better:
        result = to_decimal(some_value)
    """
    if isinstance(func_result, float):
        return to_decimal(func_result)
    return to_decimal(func_result)


def migrate_arithmetic_operation(
    left: Union[Decimal, float, int],
    right: Union[Decimal, float, int],
    operation: Callable[[Decimal, Decimal], Decimal],
) -> Decimal:
    """
    Migrate a float arithmetic operation to Decimal.

    Use this as a helper when refactoring arithmetic operations.

    Args:
        left: Left operand
        right: Right operand
        operation: Operation function (e.g., lambda a, b: a * b)

    Returns:
        Decimal result

    Examples:
        # Before:
        result = value1 * value2

        # After:
        result = migrate_arithmetic_operation(
            value1, value2,
            lambda a, b: a * b
        )
        # Or better:
        result = to_decimal(value1) * to_decimal(value2)
    """
    left_decimal = to_decimal(left)
    right_decimal = to_decimal(right)
    return operation(left_decimal, right_decimal)


def ensure_decimal_in_calculation(value: Any, context: str = "") -> Decimal:
    """
    Ensure a value is Decimal in a calculation context.

    Use this to wrap values in calculation functions to ensure Decimal usage.

    Args:
        value: Value to ensure is Decimal
        context: Context string for logging (optional)

    Returns:
        Decimal value

    Raises:
        ValueError: If value cannot be converted to Decimal
    """
    if isinstance(value, Decimal):
        return value

    try:
        return to_decimal(value)
    except (ValueError, TypeError) as e:
        logger.error(
            f"ensure_decimal_in_calculation: Failed to convert to Decimal",
            extra={"value": value, "context": context, "error": str(e)},
        )
        raise ValueError(
            f"Cannot convert {value} to Decimal in calculation context: {context}"
        ) from e


def migrate_discount_cascading(
    base_value: Union[Decimal, float, int], *discounts: Union[Decimal, float, int]
) -> Decimal:
    """
    Apply multiple discounts in cascade using Decimal.

    Formula: base_value × (1 + d1) × (1 + d2) × (1 + d3) ...

    Args:
        base_value: Base value to apply discounts to
        *discounts: Discount percentages (as decimals, e.g., -0.20 for -20%)

    Returns:
        Decimal result after all discounts

    Examples:
        # Before (float):
        result = ev * (1 + discount1) * (1 + discount2) * (1 + discount3)

        # After (Decimal):
        result = migrate_discount_cascading(ev, discount1, discount2, discount3)
    """
    result = to_decimal(base_value)

    for discount in discounts:
        discount_decimal = to_decimal(discount)
        result = result * (Decimal("1") + discount_decimal)

    return result


def migrate_percentage_calculation(
    base: Union[Decimal, float, int], percentage: Union[Decimal, float, int]
) -> Decimal:
    """
    Calculate percentage of base value using Decimal.

    Args:
        base: Base value
        percentage: Percentage (e.g., 20 for 20%)

    Returns:
        Decimal result

    Examples:
        # Before:
        result = base * (percentage / 100.0)

        # After:
        result = migrate_percentage_calculation(base, percentage)
    """
    base_decimal = to_decimal(base)
    percentage_decimal = to_decimal(percentage)
    return base_decimal * (percentage_decimal / Decimal("100"))


def migrate_ratio_calculation(
    numerator: Union[Decimal, float, int],
    denominator: Union[Decimal, float, int],
    default: Optional[Decimal] = None,
) -> Optional[Decimal]:
    """
    Calculate ratio using Decimal with safe division.

    Args:
        numerator: Numerator value
        denominator: Denominator value
        default: Default value if division fails (optional)

    Returns:
        Decimal ratio or default value

    Examples:
        # Before:
        ratio = numerator / denominator if denominator != 0 else 0.0

        # After:
        ratio = migrate_ratio_calculation(numerator, denominator, default=Decimal('0'))
    """
    from src.utils.decimal_helpers import safe_money_divide

    if default is None:
        default = Decimal("0")

    return safe_money_divide(numerator, denominator, default)


# Migration checklist helper
MIGRATION_CHECKLIST = {
    "float_literals": 'Replace float literals (e.g., 1.2) with Decimal("1.2")',
    "float_calls": "Replace to_decimal() calls with to_decimal()",
    "float_arithmetic": "Ensure all arithmetic uses Decimal operands",
    "rounding": "Use bank_round() instead of round()",
    "constants": "Use DecimalConstants for all numeric constants",
    "precision": "Ensure consistent decimal places using bank_round()",
    "validation": "Add edge case handling (None, NaN, Infinity)",
    "testing": "Add unit tests for each migrated function",
}


def get_migration_checklist() -> dict:
    """
    Get migration checklist for Decimal migration.

    Returns:
        Dictionary with migration steps and descriptions
    """
    return MIGRATION_CHECKLIST.copy()
