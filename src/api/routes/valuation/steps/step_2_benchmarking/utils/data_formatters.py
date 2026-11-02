"""
Data formatting utilities for Step 2 Benchmarking.

This module contains functions for formatting multiple values,
percentiles, and ranges for display and logging.
"""

from decimal import Decimal
from typing import Optional


def format_multiple_value(value: Optional[Decimal], precision: int = 2) -> Optional[str]:
    """
    Format a multiple value for display.

    Args:
        value: Multiple value to format
        precision: Number of decimal places

    Returns:
        Formatted string or None
    """
    if value is None:
        return None
    return f"{value:.{precision}f}x"


def format_percentile_value(
    value: Optional[Decimal], percentile: int, precision: int = 2
) -> Optional[str]:
    """
    Format a percentile value for display.

    Args:
        value: Percentile value to format
        percentile: Percentile number (e.g., 25, 50, 75)
        precision: Number of decimal places

    Returns:
        Formatted string or None
    """
    if value is None:
        return None
    return f"P{percentile}: {value:.{precision}f}x"


def format_range_value(
    low: Optional[Decimal], mid: Optional[Decimal], high: Optional[Decimal], precision: int = 2
) -> Optional[str]:
    """
    Format a range value for display.

    Args:
        low: Low value
        mid: Mid value
        high: High value
        precision: Number of decimal places

    Returns:
        Formatted string or None
    """
    if low is None or mid is None or high is None:
        return None
    return f"{low:.{precision}f}x - {mid:.{precision}f}x - {high:.{precision}f}x"
