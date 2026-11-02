"""
Core Utility Library

Bank-grade utility functions for numeric operations, formatting, calculations, validation, and type handling.
All functions are defensive, handle edge cases, and provide consistent behavior across the application.

This module consolidates duplicate helper functions from across the codebase into a single,
reusable library following bank-grade standards.

Author: Upswitch Engineering Team
Date: January 2025
Status: Production Ready
"""

from decimal import Decimal

from src.utils.decimal_helpers import from_decimal, to_decimal

# Calculation helpers
from .calculation_helpers import (
    calculate_p25_p50_p75,
    calculate_percentile,
    calculate_percentiles,
    calculate_range,
    filter_outliers,
)

# Data extraction helpers
from .data_extraction_helpers import (
    extract_ebitda_from_request,
    extract_owner_employee_counts_from_request,
    extract_revenue_from_request,
    extract_step_result,
)

# Formatting helpers
from .formatting_helpers import EURO_SYMBOL, format_currency, format_number, format_percent

# Numeric helpers
from .numeric_helpers import ensure_float, round_value, safe_divide, validate_numeric

# Type helpers
from .type_helpers import convert_type, ensure_type, normalize_type

# Validation helpers
from .validation_helpers import sanitize_input, validate_business_logic, validate_input

__all__ = [
    # Numeric helpers
    "ensure_float",
    "safe_divide",
    "validate_numeric",
    "round_value",
    # Formatting helpers
    "format_currency",
    "format_percent",
    "format_number",
    "EURO_SYMBOL",
    # Calculation helpers
    "calculate_percentile",
    "calculate_percentiles",
    "calculate_p25_p50_p75",
    "calculate_range",
    "filter_outliers",
    # Validation helpers
    "validate_input",
    "sanitize_input",
    "validate_business_logic",
    # Type helpers
    "ensure_type",
    "convert_type",
    "normalize_type",
    # Data extraction helpers
    "extract_step_result",
    "extract_revenue_from_request",
    "extract_ebitda_from_request",
    "extract_owner_employee_counts_from_request",
]
