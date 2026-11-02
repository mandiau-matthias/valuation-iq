"""
Percentile Calculator for Step 2 Benchmarking

This module provides reusable percentile calculation functions for benchmark analysis.
Calculates percentiles (P10/P25/P50/P75/P90) from data arrays with outlier handling.

Author: Upswitch Engineering Team
Date: January 2025
Status: Production Ready
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.valuation_logger import ValuationLogger

logger = ValuationLogger(__name__)


def calculate_percentile(values: List[Decimal], percentile: int) -> Optional[Decimal]:
    """
    Calculate a specific percentile from a list of values.

    Uses the nearest-rank method (standard in finance):
    - P25: Value at position n * Decimal('0.25')
    - P50: Value at position n * Decimal('0.50') (median)
    - P75: Value at position n * Decimal('0.75')

    Args:
        values: List of numeric values (must be sorted)
        percentile: Percentile to calculate (0-100, e.g., 25 for P25)

    Returns:
        Percentile value or None if insufficient data

    Examples:
        >>> calculate_percentile([1, 2, 3, 4, 5], 25)
        Decimal('2.0')

        >>> calculate_percentile([1, 2, 3, 4, 5], 50)
        Decimal('3.0')

        >>> calculate_percentile([1, 2, 3, 4, 5], 75)
        Decimal('4.0')
    """
    if not values or len(values) == 0:
        return None

    # Sort values if not already sorted
    sorted_values = sorted(values)
    n = len(sorted_values)

    # Calculate position (nearest-rank method, 1-based)
    position = (percentile / Decimal("100.0")) * n

    # Handle edge cases
    if position <= 0:
        return sorted_values[0]
    if position >= n:
        return sorted_values[-1]

    # Convert 1-based position to 0-based index
    index = int(position)

    if position == index:
        return sorted_values[index - 1]

    return sorted_values[index]


def calculate_percentiles(
    values: List[Decimal], percentiles: List[int] = [25, 50, 75]
) -> Dict[int, Optional[Decimal]]:
    """
    Calculate multiple percentiles from a list of values.

    Args:
        values: List of numeric values
        percentiles: List of percentiles to calculate (default: [25, 50, 75])

    Returns:
        Dict mapping percentile number to value (e.g., {25: Decimal('2.0'), 50: Decimal('3.0'), 75: 4.0})

    Examples:
        >>> calculate_percentiles([1, 2, 3, 4, 5])
        {25: Decimal('2.0'), 50: Decimal('3.0'), 75: 4.0}
    """
    if not values or len(values) < 3:
        # Need at least 3 values for meaningful percentiles
        return {p: None for p in percentiles}

    result = {}
    for percentile in percentiles:
        result[percentile] = calculate_percentile(values, percentile)

    return result


def calculate_p25_p50_p75(values: List[Decimal]) -> Dict[str, Optional[Decimal]]:
    """
    Calculate P25, P50 (median), and P75 percentiles from a list of values.

    Convenience function for the most common percentiles used in valuation.

    Args:
        values: List of numeric values

    Returns:
        Dict with keys 'p25', 'p50', 'p75' and their values

    Examples:
        >>> calculate_p25_p50_p75([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        {'p25': Decimal('3.0'), 'p50': Decimal('5.0'), 'p75': 8.0}
    """
    percentiles = calculate_percentiles(values, [25, 50, 75])

    return {"p25": percentiles.get(25), "p50": percentiles.get(50), "p75": percentiles.get(75)}


def filter_outliers(values: List[Decimal], method: str = "iqr") -> List[Decimal]:
    """
    Filter outliers from a list of values using IQR (Interquartile Range) method.

    Outliers are values that fall outside:
    - Lower bound: Q1 - Decimal('1.5') * IQR
    - Upper bound: Q3 + Decimal('1.5') * IQR

    Where:
    - Q1 = P25
    - Q3 = P75
    - IQR = Q3 - Q1

    Args:
        values: List of numeric values
        method: Outlier detection method ('iqr' is only supported method)

    Returns:
        Filtered list with outliers removed

    Examples:
        >>> filter_outliers([1, 2, 3, 4, 5, 100])
        [1, 2, 3, 4, 5]
    """
    if not values or len(values) < 4:
        # Need at least 4 values for IQR calculation
        return values

    if method != "iqr":
        logger.warning(f"Unknown outlier method: {method}, using IQR")

    # Calculate quartiles
    p25 = calculate_percentile(values, 25)
    p75 = calculate_percentile(values, 75)

    if p25 is None or p75 is None:
        return values

    # Calculate IQR
    iqr = p75 - p25

    # Calculate bounds
    lower_bound = p25 - Decimal("1.5") * iqr
    upper_bound = p75 + Decimal("1.5") * iqr

    # Filter values
    filtered = [v for v in values if lower_bound <= v <= upper_bound]

    outliers_removed = len(values) - len(filtered)
    if outliers_removed > 0:
        logger.info(
            f"Filtered {outliers_removed} outliers using IQR method",
            extra={
                "original_count": len(values),
                "filtered_count": len(filtered),
                "lower_bound": lower_bound,
                "upper_bound": upper_bound,
            },
        )

    return filtered


def validate_percentile_calculation(
    values: List[Decimal], percentile: int, result: Optional[Decimal]
) -> bool:
    """
    Validate that a percentile calculation is reasonable.

    Checks:
    - Result is within min/max bounds of input values
    - Result is not None if sufficient data exists

    Args:
        values: Original input values
        percentile: Percentile that was calculated
        result: Calculated percentile value

    Returns:
        True if validation passes, False otherwise
    """
    if not values:
        return result is None

    if result is None:
        return len(values) < 3  # None is valid if insufficient data

    # Check bounds
    min_value = min(values)
    max_value = max(values)

    if result < min_value or result > max_value:
        logger.warning(
            f"Percentile {percentile} result {result} is outside bounds [{min_value}, {max_value}]",
            extra={
                "percentile": percentile,
                "result": result,
                "min_value": min_value,
                "max_value": max_value,
            },
        )
        return False

    return True
