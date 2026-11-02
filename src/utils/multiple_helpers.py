"""
Multiple Discount Helpers

Utility functions for applying discounts to valuation multiples and
recalculating Enterprise Value from adjusted multiples.

This module supports the "Multiple-First Discounting" feature where all
adjustments are applied to the multiple itself before recalculating EV.
"""

from decimal import Decimal
from typing import Tuple

from src.utils.decimal_helpers import bank_round, from_decimal, to_decimal


def apply_discount_to_multiple(
    current_multiple: Decimal, discount_percentage: Decimal  # e.g., -20.0 for 20% discount
) -> Tuple[Decimal, Decimal]:
    """
    Apply discount to a valuation multiple.

    Calculates the adjusted multiple after applying a discount percentage.
    Returns both the original and adjusted multiples for transparency.

    Args:
        current_multiple: Current multiple value (e.g., Decimal('10.0') for 10x)
        discount_percentage: Discount as percentage (e.g., -20.0 for 20% discount,
                           +10.0 for 10% premium)

    Returns:
        Tuple of (multiple_before, multiple_after)

    Formula:
        multiple_after = multiple_before × (1 + discount_percentage/100)

    Examples:
        >>> apply_discount_to_multiple(Decimal('10.0'), -20.0)
        (Decimal('10.0'), Decimal('8.0'))

        >>> apply_discount_to_multiple(Decimal('8.0'), -10.0)
        (Decimal('8.0'), Decimal('7.2'))

        >>> apply_discount_to_multiple(Decimal('5.0'), +15.0)  # Premium
        (Decimal('5.0'), Decimal('5.75'))

    Note:
        - Negative percentages apply discounts (reduce multiple)
        - Positive percentages apply premiums (increase multiple)
        - Uses Decimal arithmetic for bank-grade precision
    """
    multiple_before = current_multiple

    # Convert percentage to adjustment factor
    # e.g., -20% → 0.80, +15% → 1.15
    adjustment_factor = Decimal("1") + (Decimal(str(discount_percentage)) / Decimal("100"))

    # Apply adjustment to multiple
    multiple_after = multiple_before * adjustment_factor

    # Apply banker's rounding for consistency
    multiple_after = bank_round(multiple_after, 2)  # Round to 2 decimal places for multiples

    return (multiple_before, multiple_after)


def calculate_ev_from_multiple(metric_value: Decimal, multiple: Decimal) -> Decimal:
    """
    Calculate Enterprise Value from metric and multiple.

    Args:
        metric_value: EBITDA or Revenue value (Decimal)
        multiple: Valuation multiple (Decimal, e.g., 10.0 for 10x)

    Returns:
        Enterprise Value (Decimal)

    Formula:
        EV = Metric × Multiple

    Examples:
        >>> calculate_ev_from_multiple(Decimal('1000000'), Decimal('10.0'))
        Decimal('10000000')

        >>> calculate_ev_from_multiple(Decimal('500000'), Decimal('6.48'))
        Decimal('3240000')

    Note:
        Uses Decimal arithmetic for bank-grade precision
    """
    ev = metric_value * multiple

    # Apply banker's rounding for final EV
    ev = bank_round(ev, 0)  # Round to whole currency units

    return ev


def apply_discount_cascade(
    initial_multiple: Decimal, discount_percentages: list[float]
) -> Tuple[Decimal, list[Decimal]]:
    """
    Apply a cascade of discounts to a multiple.

    Useful for testing or batch calculations where multiple discounts
    are applied sequentially.

    Args:
        initial_multiple: Starting multiple
        discount_percentages: List of discount percentages to apply in order

    Returns:
        Tuple of (final_multiple, list_of_intermediate_multiples)

    Example:
        >>> apply_discount_cascade(Decimal('10.0'), [-20.0, -10.0, -10.0])
        (Decimal('6.48'), [Decimal('10.0'), Decimal('8.0'), Decimal('7.2'), Decimal('6.48')])
    """
    current_multiple = initial_multiple
    multiples = [current_multiple]

    for discount_pct in discount_percentages:
        _, current_multiple = apply_discount_to_multiple(current_multiple, discount_pct)
        multiples.append(current_multiple)

    return (current_multiple, multiples)


def calculate_effective_multiple_from_ev(ev_value: Decimal, metric_value: Decimal) -> Decimal:
    """
    Calculate the effective multiple given an EV and metric.

    Useful for reverse-engineering or validation.

    Args:
        ev_value: Enterprise Value (Decimal)
        metric_value: EBITDA or Revenue value (Decimal)

    Returns:
        Effective multiple (Decimal)

    Formula:
        Multiple = EV / Metric

    Example:
        >>> calculate_effective_multiple_from_ev(Decimal('8000000'), Decimal('1000000'))
        Decimal('8.0')

    Raises:
        ValueError: If metric_value is zero
    """
    if metric_value == Decimal("0"):
        raise ValueError("Cannot calculate multiple: metric_value is zero")

    effective_multiple = ev_value / metric_value

    # Round to 2 decimal places for multiples
    effective_multiple = bank_round(effective_multiple, 2)

    return effective_multiple


def validate_multiple_cascade(
    initial_multiple: Decimal,
    final_ev: Decimal,
    metric_value: Decimal,
    expected_final_multiple: Decimal,
    tolerance: Decimal = Decimal("0.01"),  # Bank-grade: Decimal default
) -> Tuple[bool, str]:
    """
    Validate that a multiple discount cascade is consistent.

    Checks that: final_ev = metric_value × expected_final_multiple

    Args:
        initial_multiple: Starting multiple
        final_ev: Final Enterprise Value after all discounts
        metric_value: EBITDA or Revenue value
        expected_final_multiple: Expected final multiple after all discounts
        tolerance: Acceptable tolerance for validation (default 1%)

    Returns:
        Tuple of (is_valid, message)

    Example:
        >>> validate_multiple_cascade(10.0, 6480000, 1000000, 6.48)
        (True, "Multiple cascade is consistent")
    """
    # Calculate effective multiple from final EV
    effective_multiple = final_ev / metric_value if metric_value > 0 else 0

    # Check if within tolerance
    difference_pct = (
        abs((effective_multiple - expected_final_multiple) / expected_final_multiple * 100)
        if expected_final_multiple > 0
        else 0
    )

    if difference_pct <= tolerance:
        return (True, "Multiple cascade is consistent")
    else:
        return (
            False,
            f"Multiple cascade inconsistent: expected {expected_final_multiple:.2f}x, "
            f"calculated {effective_multiple:.2f}x (difference: {difference_pct:.2f}%)",
        )
