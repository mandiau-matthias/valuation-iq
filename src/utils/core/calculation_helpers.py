from src.utils.exceptions import CalculationError, ValuationRangeError

"""
Calculation Helper Functions

Bank-grade calculation utilities for percentiles, ranges, and statistical operations.
All functions handle edge cases and provide consistent results.

Author: Upswitch Engineering Team
Date: January 2025
Status: Production Ready
"""

from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.valuation_logger import ValuationLogger

from .numeric_helpers import ensure_float

logger = ValuationLogger(__name__)

# Optional numpy import for advanced percentile calculation
try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    logger.debug("NumPy not available - using nearest-rank method for percentiles")


def calculate_percentile(
    values: List[Decimal], percentile: int, method: str = "nearest-rank"
) -> Optional[Decimal]:
    """
    Calculate a specific percentile from a list of values.

    Uses the nearest-rank method (standard in finance) or numpy interpolation.

    Args:
        values: List of numeric values (will be sorted if not already)
        percentile: Percentile to calculate (0-100, e.g., 25 for P25)
        method: Calculation method - "nearest-rank" (default) or "numpy"

    Returns:
        Percentile value or None if insufficient data

    Examples:
        >>> calculate_percentile([1, 2, 3, 4, 5], 25)
        2.0
        >>> calculate_percentile([1, 2, 3, 4, 5], 50)
        3.0
        >>> calculate_percentile([1, 2, 3, 4, 5], 75)
        4.0
    """
    if not values or len(values) == 0:
        return None

    # Filter out None values and convert to float
    valid_values = []
    for v in values:
        float_val = ensure_float(v)
        if float_val is not None:
            valid_values.append(float_val)

    if len(valid_values) == 0:
        return None

    # Use numpy for more accurate percentile calculation
    if method == "numpy" and NUMPY_AVAILABLE and len(valid_values) >= 1:
        try:
            result = np.percentile(valid_values, percentile)
            return to_decimal(result)
        except CalculationError as e:
            logger.warning(
                f"calculate_percentile: NumPy calculation failed, using nearest-rank: {e}",
                extra={"percentile": percentile, "error": str(e)},
            )
            # Fall through to nearest-rank method

    # Nearest-rank method (standard in finance)
    sorted_values = sorted(valid_values)
    n = len(sorted_values)

    # Calculate position (nearest-rank method)
    # Use Decimal arithmetic for bank-grade precision
    percentile_decimal = to_decimal(percentile)
    position = (percentile_decimal / Decimal("100")) * Decimal(str(n))

    # Handle edge cases
    if position <= 0:
        return sorted_values[0]
    if position >= n:
        return sorted_values[-1]

    # Get value at position (use integer index)
    index = int(position)

    # If position is exact integer, return that value
    if position == index:
        return sorted_values[index]

    # Otherwise interpolate between index and index+1
    # (For nearest-rank, return value at index)
    return sorted_values[index]


def calculate_percentiles(
    values: List[Decimal], percentiles: List[int] = [25, 50, 75], method: str = "nearest-rank"
) -> Dict[int, Optional[Decimal]]:
    """
    Calculate multiple percentiles from a list of values.

    Args:
        values: List of numeric values
        percentiles: List of percentiles to calculate (default: [25, 50, 75])
        method: Calculation method - "nearest-rank" (default) or "numpy"

    Returns:
        Dict mapping percentile number to value (e.g., {25: 2.0, 50: 3.0, 75: 4.0})

    Examples:
        >>> calculate_percentiles([1, 2, 3, 4, 5])
        {25: 2.0, 50: 3.0, 75: 4.0}
    """
    if not values or len(values) < 3:
        # Need at least 3 values for meaningful percentiles
        return {p: None for p in percentiles}

    result = {}
    for percentile in percentiles:
        result[percentile] = calculate_percentile(values, percentile, method)

    return result


def calculate_p25_p50_p75(
    values: List[Decimal],
) -> Tuple[Optional[Decimal], Optional[Decimal], Optional[Decimal]]:
    """
    Calculate P25, P50 (median), and P75 percentiles from a list of values.

    Convenience function that returns a tuple for easy unpacking.

    Args:
        values: List of numeric values

    Returns:
        Tuple of (p25, p50, p75) percentiles

    Examples:
        >>> calculate_p25_p50_p75([1, 2, 3, 4, 5])
        (2.0, 3.0, 4.0)
    """
    percentiles = calculate_percentiles(values, [25, 50, 75])
    return (percentiles.get(25), percentiles.get(50), percentiles.get(75))


def calculate_range(
    values: List[Decimal], include_outliers: bool = False
) -> Dict[str, Optional[Decimal]]:
    """
    Calculate statistical range (min, max, mean, median) from a list of values.

    Args:
        values: List of numeric values
        include_outliers: If False, filter outliers using IQR method (default: False)

    Returns:
        Dict with 'min', 'max', 'mean', 'median' keys

    Examples:
        >>> calculate_range([1, 2, 3, 4, 5])
        {'min': 1.0, 'max': 5.0, 'mean': 3.0, 'median': 3.0}
    """
    if not values or len(values) == 0:
        return {"min": None, "max": None, "mean": None, "median": None}

    # Filter out None values and convert to float
    valid_values = []
    for v in values:
        float_val = ensure_float(v)
        if float_val is not None:
            valid_values.append(float_val)

    if len(valid_values) == 0:
        return {"min": None, "max": None, "mean": None, "median": None}

    # Filter outliers if requested
    if not include_outliers and len(valid_values) >= 4:
        try:
            p25, p50, p75 = calculate_p25_p50_p75(valid_values)
            if p25 is not None and p75 is not None:
                # Use Decimal arithmetic for IQR calculation
                p25_decimal = to_decimal(p25)
                p75_decimal = to_decimal(p75)
                iqr = p75_decimal - p25_decimal
                lower_bound = p25_decimal - Decimal("1.5") * iqr
                upper_bound = p75_decimal + Decimal("1.5") * iqr
                valid_values = [
                    v
                    for v in valid_values
                    if to_decimal(v) >= lower_bound and to_decimal(v) <= upper_bound
                ]
        except ValuationRangeError as e:
            logger.debug(f"calculate_range: Outlier filtering failed: {e}", extra={"error": str(e)})

    if len(valid_values) == 0:
        return {"min": None, "max": None, "mean": None, "median": None}

    sorted_values = sorted(valid_values)

    return {
        "min": sorted_values[0],
        "max": sorted_values[-1],
        "mean": sum(valid_values) / len(valid_values),
        "median": calculate_percentile(valid_values, 50),
    }


def filter_outliers(values: List[Decimal], method: str = "iqr") -> List[Decimal]:
    """
    Filter outliers from a list of values using IQR method.

    Args:
        values: List of numeric values
        method: Filtering method - "iqr" (default) uses interquartile range

    Returns:
        Filtered list of values with outliers removed

    Examples:
        >>> filter_outliers([1, 2, 3, 4, 5, 100])
        [1, 2, 3, 4, 5]
    """
    if not values or len(values) < 4:
        return values

    # Filter out None values
    valid_values = []
    for v in values:
        float_val = ensure_float(v)
        if float_val is not None:
            valid_values.append(float_val)

    if len(valid_values) < 4:
        return valid_values

    # IQR method
    if method == "iqr":
        try:
            p25, p50, p75 = calculate_p25_p50_p75(valid_values)
            if p25 is not None and p75 is not None:
                iqr = p75 - p25
                lower_bound = p25 - Decimal("1.5") * iqr
                upper_bound = p75 + Decimal("1.5") * iqr
                return [v for v in valid_values if lower_bound <= v <= upper_bound]
        except Exception as e:
            logger.warning(f"filter_outliers: IQR filtering failed: {e}", extra={"error": str(e)})

    return valid_values
