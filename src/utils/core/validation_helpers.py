"""
Validation Helper Functions

Bank-grade validation utilities for input sanitization, type validation, and business logic validation.
All functions are defensive and handle edge cases.

Author: Upswitch Engineering Team
Date: January 2025
Status: Production Ready
"""

import re
from collections.abc import Mapping
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.exceptions import DataValidationError
from src.utils.valuation_logger import ValuationLogger

from .numeric_helpers import ensure_float, validate_numeric

logger = ValuationLogger(__name__)


def validate_input(
    value: Any,
    expected_type: type,
    allow_none: bool = False,
    min_value: Optional[Union[float, int]] = None,
    max_value: Optional[Union[float, int]] = None,
) -> tuple[bool, Optional[str]]:
    """
    Validate input value against expected type and constraints.

    Args:
        value: Value to validate
        expected_type: Expected type (int, float, str, Decimal, etc.)
        allow_none: Whether to allow None values (default: False)
        min_value: Minimum allowed value (for numeric types)
        max_value: Maximum allowed value (for numeric types)

    Returns:
        Tuple of (is_valid, error_message)

    Examples:
        >>> validate_input(10, int)
        (True, None)
        >>> validate_input(None, int, allow_none=True)
        (True, None)
        >>> validate_input(10, int, min_value=0, max_value=100)
        (True, None)
    """
    # Check for None
    if value is None:
        if allow_none:
            return (True, None)
        return (False, "Value cannot be None")

    # Check type
    if not isinstance(value, expected_type):
        return (False, f"Expected {expected_type.__name__}, got {type(value).__name__}")

    # Check numeric constraints
    if expected_type in (int, float, Decimal) and (min_value is not None or max_value is not None):
        try:
            float_val = ensure_float(value)
            if float_val is None:
                return (False, "Value is not a valid number")

            if min_value is not None and float_val < min_value:
                return (False, f"Value {float_val} is below minimum {min_value}")

            if max_value is not None and float_val > max_value:
                return (False, f"Value {float_val} is above maximum {max_value}")
        except DataValidationError as e:
            return (False, f"Validation error: {str(e)}")

    return (True, None)


def sanitize_input(value: Any, input_type: str = "string", max_length: Optional[int] = None) -> Any:
    """
    Sanitize input value based on type.

    Args:
        value: Value to sanitize
        input_type: Type of input ("string", "email", "phone", "url", "numeric")
        max_length: Maximum length for string inputs (optional)

    Returns:
        Sanitized value

    Examples:
        >>> sanitize_input("  Hello World  ", "string")
        "Hello World"
        >>> sanitize_input("test@example.com", "email")
        "test@example.com"
        >>> sanitize_input("+32 123 456 789", "phone")
        "+32123456789"
    """
    if value is None:
        return None

    if input_type == "string":
        if not isinstance(value, str):
            value = str(value)
        # Remove leading/trailing whitespace
        sanitized = value.strip()
        # Truncate if max_length specified
        if max_length is not None and len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        return sanitized

    elif input_type == "email":
        if not isinstance(value, str):
            value = str(value)
        # Lowercase and trim
        sanitized = value.strip().lower()
        # Basic email validation
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, sanitized):
            logger.warning(
                f"sanitize_input: Invalid email format: {value}",
                extra={"value": value, "sanitized": sanitized},
            )
        return sanitized

    elif input_type == "phone":
        if not isinstance(value, str):
            value = str(value)
        # Remove all non-digit characters except +
        sanitized = re.sub(r"[^\d+]", "", value)
        return sanitized

    elif input_type == "url":
        if not isinstance(value, str):
            value = str(value)
        # Lowercase and trim
        sanitized = value.strip().lower()
        return sanitized

    elif input_type == "numeric":
        return ensure_float(value)

    return value


def _business_logic_result(
    *,
    is_valid: bool = True,
    warnings: Optional[List[str]] = None,
    suggestions: Optional[List[str]] = None,
) -> Dict[str, object]:
    return {
        "is_valid": is_valid,
        "warnings": warnings or [],
        "suggestions": suggestions or [],
    }


def _validate_revenue_business_logic(
    value: object, context: Mapping[str, object]
) -> Dict[str, object]:
    del context
    revenue = ensure_float(value)
    warnings = []
    is_valid = True

    if revenue is None:
        is_valid = False
        warnings.append("Revenue must be a valid number")
    elif revenue < 0:
        is_valid = False
        warnings.append("Revenue cannot be negative")
    elif revenue == 0:
        warnings.append("Revenue is zero - valuation may be unreliable")

    return _business_logic_result(is_valid=is_valid, warnings=warnings)


def _validate_ebitda_business_logic(
    value: object, context: Mapping[str, object]
) -> Dict[str, object]:
    ebitda = ensure_float(value)
    warnings = []
    is_valid = True

    if ebitda is None:
        is_valid = False
        warnings.append("EBITDA must be a valid number")
    elif ebitda < 0:
        warnings.append("Negative EBITDA - company is loss-making")

    revenue = context.get("revenue")
    if revenue and revenue > 0:
        ebitda_margin = ensure_float(ebitda) / ensure_float(revenue) * 100 if ebitda else None
        if ebitda_margin is not None:
            if ebitda_margin < 0:
                warnings.append("Negative EBITDA margin")
            elif ebitda_margin < 3:
                warnings.append("EBITDA margin <3% - may be unreliable for valuation")

    return _business_logic_result(is_valid=is_valid, warnings=warnings)


def _validate_employee_count_business_logic(
    value: object, context: Mapping[str, object]
) -> Dict[str, object]:
    del context
    employees = ensure_float(value)
    warnings = []
    is_valid = True

    if employees is None:
        is_valid = False
        warnings.append("Employee count must be a valid number")
    elif employees < 0:
        is_valid = False
        warnings.append("Employee count cannot be negative")
    elif employees == 0:
        warnings.append("Zero employees - may be a sole trader")

    return _business_logic_result(is_valid=is_valid, warnings=warnings)


def _validate_founded_year_business_logic(
    value: object, context: Mapping[str, object]
) -> Dict[str, object]:
    year = ensure_float(value)
    warnings = []
    is_valid = True

    if year is None:
        is_valid = False
        warnings.append("Founded year must be a valid number")
    else:
        current_year = context.get("current_year", 2025)
        if year < 1800 or year > current_year:
            warnings.append(f"Founded year {year} seems unusual")
        elif current_year - year < 1:
            warnings.append("Company is less than 1 year old")

    return _business_logic_result(is_valid=is_valid, warnings=warnings)


_BUSINESS_LOGIC_VALIDATORS = {
    "revenue": _validate_revenue_business_logic,
    "ebitda": _validate_ebitda_business_logic,
    "employee_count": _validate_employee_count_business_logic,
    "founded_year": _validate_founded_year_business_logic,
}


def validate_business_logic(
    field: str, value: Any, context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Validate business logic for specific fields.

    Args:
        field: Field name being validated
        value: Value to validate
        context: Additional context for validation (optional)

    Returns:
        Dict with 'is_valid', 'warnings', 'suggestions' keys

    Examples:
        >>> validate_business_logic("revenue", 1000000)
        {'is_valid': True, 'warnings': [], 'suggestions': []}
        >>> validate_business_logic("revenue", -1000)
        {'is_valid': False, 'warnings': ['Revenue cannot be negative'], 'suggestions': []}
    """
    context = context or {}
    validator = _BUSINESS_LOGIC_VALIDATORS.get(field)
    if validator is None:
        return _business_logic_result()

    return validator(value, context)
