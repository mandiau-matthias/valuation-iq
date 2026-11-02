"""
Standardized Error Logging Utilities

This module provides standardized error logging with comprehensive context
for debugging and troubleshooting production issues.

Author: Upswitch Engineering Team
Date: November 2025
Status: Production Ready
"""

import sys
import traceback
from datetime import datetime
from typing import Any, Dict, Optional


def get_standardized_error_context(
    error: Exception,
    step_number: Optional[int] = None,
    step_name: Optional[str] = None,
    input_data: Optional[Dict[str, Any]] = None,
    step_state: Optional[Dict[str, Any]] = None,
    additional_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generate standardized error context for logging.

    Args:
        error: The exception that occurred
        step_number: Step number if applicable
        step_name: Step name if applicable
        input_data: Snapshot of input data (sanitized, no PII)
        step_state: Current state of step execution
        additional_context: Any additional context

    Returns:
        Dictionary with comprehensive error context
    """
    context = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "error_type": type(error).__name__,
        "error_message": str(error),
        "stack_trace": traceback.format_exc(),
        "error_module": error.__class__.__module__ if hasattr(error, "__class__") else None,
    }

    if step_number is not None:
        context["step_number"] = step_number

    if step_name:
        context["step_name"] = step_name

    if input_data:
        # Sanitize input data to remove PII
        context["input_data"] = sanitize_data_for_logging(input_data)

    if step_state:
        context["step_state"] = step_state

    if additional_context:
        context.update(additional_context)

    return context


def sanitize_data_for_logging(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove or mask PII from data before logging.

    Args:
        data: Data dictionary to sanitize

    Returns:
        Sanitized data dictionary
    """
    if not isinstance(data, dict):
        return {}

    sanitized = {}
    pii_fields = {
        "company_name",
        "email",
        "phone",
        "address",
        "city",
        "contact_name",
        "owner_name",
        "business_description",
    }

    for key, value in data.items():
        if key.lower() in pii_fields:
            # Mask PII fields
            sanitized[key] = f"<{key.upper()}_REDACTED>"
        elif isinstance(value, dict):
            # Recursively sanitize nested dicts
            sanitized[key] = sanitize_data_for_logging(value)
        elif isinstance(value, (int, float, bool)):
            # Numbers and booleans are safe
            sanitized[key] = value
        elif isinstance(value, str) and len(value) < 100:
            # Short strings are probably safe
            sanitized[key] = value
        else:
            # For safety, truncate or mask
            sanitized[key] = f"<{type(value).__name__}>"

    return sanitized


def format_error_for_user(error: Exception, include_details: bool = False) -> Dict[str, Any]:
    """
    Format error for user-facing error messages.

    Args:
        error: The exception that occurred
        include_details: Whether to include technical details

    Returns:
        User-friendly error dictionary
    """
    error_response = {
        "error": "An error occurred during valuation calculation",
        "error_type": type(error).__name__,
        "message": str(error),
    }

    if include_details:
        error_response["details"] = {
            "module": error.__class__.__module__ if hasattr(error, "__class__") else None,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    return error_response


# ==================== EXPORT ====================

__all__ = ["get_standardized_error_context", "sanitize_data_for_logging", "format_error_for_user"]
