"""
Data Extraction Helper Functions

Unified utilities for extracting financial data from various sources:
- ValuationRequest objects (for calculation steps)
- collected_data dictionaries (for progressive valuation)
- ValuationResponse objects (for transformers)

This module consolidates extraction logic to eliminate duplication and improve maintainability.

Author: Upswitch Engineering Team
Date: January 2025
Status: Production Ready
"""

from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from src.api.schemas import ValuationRequest
from src.utils.decimal_helpers import to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


# ==================== Enum/String Extraction Utilities ====================


def extract_enum_value(value: Any) -> Optional[str]:
    """
    Safely extract string value from enum or string.

    Handles both enum objects (with .value attribute) and plain strings.
    This utility eliminates the need for repetitive isinstance/hasattr checks.

    Args:
        value: Enum object or string value

    Returns:
        String value if available, None otherwise

    Examples:
        >>> extract_enum_value(BusinessCategory.TECHNOLOGY)
        'technology'
        >>> extract_enum_value('technology')
        'technology'
        >>> extract_enum_value(None)
        None
    """
    if value is None:
        return None

    if isinstance(value, str):
        return value

    if hasattr(value, "value"):
        return str(value.value)

    return str(value) if value else None


# ==================== ValuationRequest Extraction ====================


def extract_revenue_from_request(request: ValuationRequest) -> Optional[Decimal]:
    """
    Safely extract revenue from ValuationRequest.

    Args:
        request: Valuation request

    Returns:
        Revenue as Decimal, or None if not available
    """
    if not hasattr(request, "current_year_data") or request.current_year_data is None:
        return None

    revenue = getattr(request.current_year_data, "revenue", None)
    if revenue is None:
        return None

    try:
        return to_decimal(revenue) if not isinstance(revenue, Decimal) else revenue
    except (ValueError, TypeError):
        return None


def extract_ebitda_from_request(request: ValuationRequest) -> Optional[Decimal]:
    """
    Safely extract EBITDA from ValuationRequest.

    Args:
        request: Valuation request

    Returns:
        EBITDA as Decimal, or None if not available
    """
    if not hasattr(request, "current_year_data") or request.current_year_data is None:
        return None

    ebitda = getattr(request.current_year_data, "ebitda", None)
    if ebitda is None:
        return None

    try:
        return to_decimal(ebitda) if not isinstance(ebitda, Decimal) else ebitda
    except (ValueError, TypeError):
        return None


def extract_owner_employee_counts_from_request(
    request: ValuationRequest,
) -> Tuple[Optional[int], Optional[int]]:
    """
    Safely extract owner and employee counts from ValuationRequest.

    Checks multiple possible locations:
    1. Direct attributes on request
    2. Within business_context
    3. Within current_year_data

    Args:
        request: Valuation request

    Returns:
        Tuple of (num_owners, num_employees), either may be None
    """
    # Try direct attributes
    num_owners = getattr(request, "number_of_owners", None)
    num_employees = getattr(request, "number_of_employees", None)

    # Try business_context
    if num_owners is None and hasattr(request, "business_context") and request.business_context:
        num_owners = getattr(request.business_context, "number_of_owners", None)

    if num_employees is None and hasattr(request, "business_context") and request.business_context:
        num_employees = getattr(request.business_context, "number_of_employees", None)

    # Try current_year_data
    if num_owners is None and hasattr(request, "current_year_data") and request.current_year_data:
        num_owners = getattr(request.current_year_data, "number_of_owners", None)

    if (
        num_employees is None
        and hasattr(request, "current_year_data")
        and request.current_year_data
    ):
        num_employees = getattr(request.current_year_data, "number_of_employees", None)

    return num_owners, num_employees


# ==================== Collected Data Dictionary Extraction ====================


def extract_revenue_from_collected_data(
    collected_data: Dict[str, Any], default: Decimal = Decimal("0.0")
) -> Tuple[Decimal, bool]:
    """
    Safely extract revenue from collected_data dictionary.

    Args:
        collected_data: Dictionary containing collected data
        default: Default value to return if extraction fails

    Returns:
        Tuple of (revenue_decimal, has_revenue) where has_revenue indicates if valid revenue was found
    """
    revenue_decimal = default
    has_revenue = False

    try:
        revenue_raw = collected_data.get("revenue")
        if revenue_raw is not None and revenue_raw != "":
            revenue_decimal = to_decimal(revenue_raw)
            has_revenue = revenue_decimal > Decimal("0")
    except (ValueError, TypeError) as e:
        logger.warning(
            f"[DATA_EXTRACTION] Could not parse revenue: {revenue_raw}",
            extra={"error": str(e), "revenue_raw": revenue_raw},
        )
        revenue_decimal = default
        has_revenue = False

    return revenue_decimal, has_revenue


def extract_ebitda_from_collected_data(
    collected_data: Dict[str, Any], default: Decimal = Decimal("0.0")
) -> Tuple[Decimal, bool]:
    """
    Safely extract EBITDA from collected_data dictionary.

    Args:
        collected_data: Dictionary containing collected data
        default: Default value to return if extraction fails

    Returns:
        Tuple of (ebitda_decimal, has_ebitda) where has_ebitda indicates if valid EBITDA was found
    """
    ebitda_decimal = default
    has_ebitda = False

    try:
        ebitda_raw = collected_data.get("ebitda")
        if ebitda_raw is not None and ebitda_raw != "":
            ebitda_decimal = to_decimal(ebitda_raw)
            has_ebitda = ebitda_decimal > Decimal("0")
    except (ValueError, TypeError) as e:
        logger.warning(
            f"[DATA_EXTRACTION] Could not parse EBITDA: {ebitda_raw}",
            extra={"error": str(e), "ebitda_raw": ebitda_raw},
        )
        ebitda_decimal = default
        has_ebitda = False

    return ebitda_decimal, has_ebitda


def extract_growth_rate_from_collected_data(
    collected_data: Dict[str, Any], default: Decimal = Decimal("0.0")
) -> Decimal:
    """
    Safely extract growth rate from collected_data dictionary.

    Args:
        collected_data: Dictionary containing collected data
        default: Default value to return if extraction fails

    Returns:
        Growth rate as Decimal
    """
    try:
        growth_rate_raw = collected_data.get("growth_rate", 0)
        if growth_rate_raw is not None and growth_rate_raw != "":
            return to_decimal(growth_rate_raw)
    except (ValueError, TypeError) as e:
        logger.warning(
            f"[DATA_EXTRACTION] Could not parse growth_rate: {growth_rate_raw}",
            extra={"error": str(e), "growth_rate_raw": growth_rate_raw},
        )

    return default


def extract_employees_from_collected_data(collected_data: Dict[str, Any], default: int = 5) -> int:
    """
    Safely extract employee count from collected_data dictionary.

    Args:
        collected_data: Dictionary containing collected data
        default: Default value to return if extraction fails

    Returns:
        Employee count as int
    """
    try:
        employees_raw = collected_data.get("employees")
        if employees_raw is not None and employees_raw != "":
            employees_int = (
                int(employees_raw) if not isinstance(employees_raw, int) else employees_raw
            )
            return max(0, employees_int)  # Ensure non-negative
    except (ValueError, TypeError) as e:
        logger.warning(
            f"[DATA_EXTRACTION] Could not parse employees: {employees_raw}",
            extra={"error": str(e), "employees_raw": employees_raw},
        )

    return default


def extract_owner_count_from_collected_data(
    collected_data: Dict[str, Any], default: Optional[int] = None
) -> Optional[int]:
    """
    Safely extract owner count from collected_data dictionary.

    Args:
        collected_data: Dictionary containing collected data
        default: Default value to return if extraction fails

    Returns:
        Owner count as int, or None if not available
    """
    try:
        owners_raw = collected_data.get("number_of_owners") or collected_data.get("owners")
        if owners_raw is not None and owners_raw != "":
            return int(owners_raw) if not isinstance(owners_raw, int) else owners_raw
    except (ValueError, TypeError) as e:
        logger.warning(
            f"[DATA_EXTRACTION] Could not parse owners: {owners_raw}",
            extra={"error": str(e), "owners_raw": owners_raw},
        )

    return default


# ==================== Step Output Extraction Utilities ====================


def extract_step_result(step_output: Any) -> Optional[Dict[str, Any]]:
    """
    Extract result dictionary from step output.

    WHAT: Handles both StepOutput objects and dictionaries
    WHY: Step results may be stored as objects or serialized dictionaries (eliminates duplication)
    HOW: Checks for .result attribute or treats as dict directly
    WHEN: Called when extracting data from step results for template rendering or data transformation

    Academic Reference: None (infrastructure utility)
    Business Rule: Step results must be extracted consistently across all transformers

    Args:
        step_output: StepOutput object or dictionary

    Returns:
        Result dictionary or None if not found

    Examples:
        >>> from src.api.routes.valuation.steps.base_step import StepOutput, StepStatus
        >>> step = StepOutput(step_number=2, step_name="Test", status=StepStatus.COMPLETED, result={"value": 100})
        >>> extract_step_result(step)
        {'value': 100}
        >>> extract_step_result({"result": {"value": 100}})
        {'value': 100}
        >>> extract_step_result({"value": 100})
        {'value': 100}
        >>> extract_step_result(None)
        None
    """
    if step_output is None:
        return None

    # Handle StepOutput object
    if hasattr(step_output, "result"):
        if isinstance(step_output.result, dict):
            return step_output.result

    # Handle dictionary directly
    if isinstance(step_output, dict):
        # If it's already a result dict (has result-like keys), return it
        # Check for common result keys to identify result dictionaries
        result_keys = [
            "component_scores",
            "confidence_score",
            "result",
            "multiple_after_mid",
            "multiple_before_mid",
            "ev_ebitda_multiple",
            "ev_revenue_multiple",
            "enterprise_value_mid",
            "equity_value_mid",
        ]
        has_result_keys = any(key in step_output for key in result_keys)

        if has_result_keys:
            # If it has a 'result' key, return that
            if "result" in step_output and isinstance(step_output["result"], dict):
                return step_output["result"]
            # Otherwise, treat the dict itself as the result
            return step_output

    return None


# ==================== Export ====================

__all__ = [
    # ValuationRequest extraction
    "extract_revenue_from_request",
    "extract_ebitda_from_request",
    "extract_owner_employee_counts_from_request",
    # Collected data dictionary extraction
    "extract_revenue_from_collected_data",
    "extract_ebitda_from_collected_data",
    "extract_growth_rate_from_collected_data",
    "extract_employees_from_collected_data",
    "extract_owner_count_from_collected_data",
    # Enum/string extraction utilities
    "extract_enum_value",
    # Step output extraction utilities
    "extract_step_result",
]
