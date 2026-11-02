"""
Shared Utilities for Calculation Steps

This module contains common utility functions used across multiple calculation steps
to reduce code duplication and improve maintainability.

Author: Upswitch Engineering Team
Date: November 2025
Status: Production Ready
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.api.schemas import ValuationRequest
from src.utils.core.data_extraction_helpers import (
    extract_ebitda_from_request,
    extract_owner_employee_counts_from_request,
    extract_revenue_from_request,
)
from src.utils.decimal_helpers import to_decimal
from src.utils.logging import get_logger
from src.utils.registry_identity_context import resolve_business_type_id

logger = get_logger(__name__)


# ==================== DATA EXTRACTION UTILITIES ====================
# NOTE: These functions are maintained for backward compatibility.
# New code should use src.utils.core.data_extraction_helpers directly.


def extract_revenue(request: ValuationRequest) -> Optional[Decimal]:
    """
    Safely extract revenue from request.

    Delegates to extract_revenue_from_request for consistency.

    Args:
        request: Valuation request

    Returns:
        Revenue as Decimal, or None if not available
    """
    return extract_revenue_from_request(request)


def extract_ebitda(request: ValuationRequest) -> Optional[Decimal]:
    """
    Safely extract EBITDA from request.

    Delegates to extract_ebitda_from_request for consistency.

    Args:
        request: Valuation request

    Returns:
        EBITDA as Decimal, or None if not available
    """
    return extract_ebitda_from_request(request)


def extract_owner_employee_counts(request: ValuationRequest) -> tuple[Optional[int], Optional[int]]:
    """
    Safely extract owner and employee counts from request.

    Delegates to extract_owner_employee_counts_from_request for consistency.

    Args:
        request: Valuation request

    Returns:
        Tuple of (num_owners, num_employees), either may be None
    """
    return extract_owner_employee_counts_from_request(request)


def extract_business_type_id(request: ValuationRequest) -> Optional[str]:
    """
    Safely extract business_type_id from request.

    Args:
        request: Valuation request

    Returns:
        Business type ID, or None if not available
    """
    return resolve_business_type_id(
        business_context=getattr(request, "business_context", None),
        business_type_id=getattr(request, "business_type_id", None),
    )


# ==================== VALIDATION UTILITIES ====================


def validate_decimal_range(
    value: Decimal,
    min_value: Optional[Decimal] = None,
    max_value: Optional[Decimal] = None,
    field_name: str = "value",
) -> tuple[bool, Optional[str]]:
    """
    Validate that a Decimal value is within specified range.

    Args:
        value: Value to validate
        min_value: Minimum allowed value (inclusive)
        max_value: Maximum allowed value (inclusive)
        field_name: Name of field for error message

    Returns:
        Tuple of (is_valid, error_message)
    """
    if min_value is not None and value < min_value:
        return False, f"{field_name} must be >= {min_value}, got {value}"

    if max_value is not None and value > max_value:
        return False, f"{field_name} must be <= {max_value}, got {value}"

    return True, None


def validate_percentage(
    percentage: Decimal, field_name: str = "percentage"
) -> tuple[bool, Optional[str]]:
    """
    Validate that a value represents a valid percentage (-Decimal('1.0') to Decimal('1.0') for discounts/premiums).

    Args:
        percentage: Percentage value to validate
        field_name: Name of field for error message

    Returns:
        Tuple of (is_valid, error_message)
    """
    if percentage < Decimal("-1.0") or percentage > Decimal("1.0"):
        return False, f"{field_name} must be between -100% and +100%, got {percentage * 100}%"

    return True, None


# ==================== LOGGING UTILITIES ====================


def log_step_start(step_number: int, step_name: str, request: ValuationRequest):
    """
    Standardized logging for step start.

    Args:
        step_number: Step number
        step_name: Step name
        request: Valuation request
    """
    logger.info(
        f"🚀 Step {step_number} ({step_name}) - Starting",
        extra={
            "step_number": step_number,
            "step_name": step_name,
            "company_name": getattr(request, "company_name", "Unknown"),
            "business_type_id": extract_business_type_id(request),
        },
    )


def log_step_complete(
    step_number: int, step_name: str, key_results: Optional[Dict[str, Any]] = None
):
    """
    Standardized logging for step completion.

    Args:
        step_number: Step number
        step_name: Step name
        key_results: Dictionary of key results to log
    """
    extra = {"step_number": step_number, "step_name": step_name}

    if key_results:
        extra.update(key_results)

    logger.info(f"✅ Step {step_number} ({step_name}) - Completed", extra=extra)


def log_step_skipped(step_number: int, step_name: str, reason: str):
    """
    Standardized logging for step skip.

    Args:
        step_number: Step number
        step_name: Step name
        reason: Reason for skipping
    """
    logger.info(
        f"⏭️ Step {step_number} ({step_name}) - Skipped: {reason}",
        extra={"step_number": step_number, "step_name": step_name, "skip_reason": reason},
    )


def log_step_error(
    step_number: int, step_name: str, error: Exception, context: Optional[Dict[str, Any]] = None
):
    """
    Standardized logging for step errors.

    Args:
        step_number: Step number
        step_name: Step name
        error: Exception that occurred
        context: Additional context for debugging
    """
    extra = {
        "step_number": step_number,
        "step_name": step_name,
        "error_type": type(error).__name__,
        "error_message": str(error),
    }

    if context:
        extra.update(context)

    logger.error(
        f"❌ Step {step_number} ({step_name}) - Error: {str(error)}", extra=extra, exc_info=True
    )


# ==================== RESULT FORMATTING UTILITIES ====================


def format_discount_result(
    discount: Decimal,
    discount_name: str,
    tier: Optional[str] = None,
    rationale: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Format discount result in standardized format for transparency reporting.

    Args:
        discount: Discount value (negative for discount, positive for premium)
        discount_name: Name of the discount
        tier: Optional tier classification
        rationale: Optional rationale explanation

    Returns:
        Formatted discount dictionary
    """
    result = {
        "discount_percentage": to_decimal(discount),
        "discount_name": discount_name,
        "discount_display": f"{discount * 100:.1f}%",
    }

    if tier:
        result["tier"] = tier

    if rationale:
        result["rationale"] = rationale

    return result


def format_valuation_result(
    valuation_low: Decimal,
    valuation_mid: Decimal,
    valuation_high: Decimal,
    methodology: str = "Unknown",
) -> Dict[str, Any]:
    """
    Format valuation result in standardized format.

    Args:
        valuation_low: Low estimate
        valuation_mid: Mid-point estimate
        valuation_high: High estimate
        methodology: Valuation methodology used

    Returns:
        Formatted valuation dictionary
    """
    return {
        "valuation_low": to_decimal(valuation_low),
        "valuation_mid": to_decimal(valuation_mid),
        "valuation_high": to_decimal(valuation_high),
        "methodology": methodology,
        "range_spread_pct": (
            to_decimal((valuation_high - valuation_low) / valuation_mid * 100)
            if valuation_mid > 0
            else 0
        ),
    }


# ==================== EXPORT ====================

__all__ = [
    # Data Extraction
    "extract_revenue",
    "extract_ebitda",
    "extract_owner_employee_counts",
    "extract_business_type_id",
    # Validation
    "validate_decimal_range",
    "validate_percentage",
    # Logging
    "log_step_start",
    "log_step_complete",
    "log_step_skipped",
    "log_step_error",
    # Result Formatting
    "format_discount_result",
    "format_valuation_result",
]
