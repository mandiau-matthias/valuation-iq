"""
Calculators module for Step 2 Benchmarking.

This module contains classes responsible for calculating multiples,
percentiles, and ranges from benchmark data.
"""

from decimal import Decimal

from src.utils.decimal_helpers import from_decimal, to_decimal

from .multiples_calculator import MultiplesCalculator
from .percentile_calculator import (
    calculate_p25_p50_p75,
    calculate_percentile,
    calculate_percentiles,
    filter_outliers,
    validate_percentile_calculation,
)
from .range_calculator import RangeCalculator

__all__ = [
    "calculate_percentile",
    "calculate_percentiles",
    "calculate_p25_p50_p75",
    "filter_outliers",
    "validate_percentile_calculation",
    "MultiplesCalculator",
    "RangeCalculator",
]
