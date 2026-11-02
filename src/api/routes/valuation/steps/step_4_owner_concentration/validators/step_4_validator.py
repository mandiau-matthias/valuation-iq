"""
Step 4 Validator

Validates data for owner concentration calculations.
"""

from typing import Optional, Tuple

from src.utils.logging import get_logger
from src.utils.sole_trader_detector import SoleTraderDetector

from ...step_utilities import extract_owner_employee_counts
from src.utils.core.data_extraction_helpers import extract_owner_employee_counts_from_request

logger = get_logger(__name__)


class Step4Validator:
    """Validates data for Step 4."""

    def validate_step3_data(self, step3: Optional[dict]) -> Tuple[bool, Optional[str]]:
        """
        Validate Step 3 data is available.

        Args:
            step3: Step 3 result dictionary

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not step3:
            return False, "Step 3 (Base EV) results not available"
        return True, None

    def extract_and_validate_owner_employee_data(
        self, request: any, is_sole_trader: bool
    ) -> Tuple[Optional[int], Optional[int], Optional[str]]:
        """
        Extract and validate owner/employee data.

        Args:
            request: The valuation request
            is_sole_trader: Whether this is a sole trader

        Returns:
            Tuple of (num_owners, num_employees, error_message)
        """
        if is_sole_trader:
            # Sole traders: 1 owner, 0-1 employees
            num_owners = 1
            # Use unified utility to extract employee count
            _, num_employees = extract_owner_employee_counts_from_request(request)
            num_employees = num_employees or 0
            logger.debug(
                "✅ Sole trader detected: Auto-setting owner/employee values",
                extra={"num_owners": num_owners, "num_employees": num_employees},
            )
            return num_owners, num_employees, None
        else:
            # Use shared utility (which delegates to unified utilities)
            num_owners, num_employees = extract_owner_employee_counts(request)
            if num_owners is None or num_employees is None:
                return None, None, "Owner/employee data not available"
            return num_owners, num_employees, None

    def validate_owner_employee_types(
        self, num_owners: any, num_employees: any
    ) -> Tuple[Optional[int], Optional[int], Optional[str]]:
        """
        Validate and convert owner/employee counts to integers.

        Args:
            num_owners: Owner count (may be any type)
            num_employees: Employee count (may be any type)

        Returns:
            Tuple of (validated_num_owners, validated_num_employees, error_message)
        """
        try:
            if num_owners is not None:
                num_owners = int(num_owners) if not isinstance(num_owners, int) else num_owners
            if num_employees is not None:
                num_employees = (
                    int(num_employees) if not isinstance(num_employees, int) else num_employees
                )
            return num_owners, num_employees, None
        except (ValueError, TypeError) as type_error:
            logger.error(
                "❌ Invalid type for owner/employee counts",
                extra={
                    "num_owners": num_owners,
                    "num_employees": num_employees,
                    "error": str(type_error),
                },
            )
            return None, None, f"Invalid type for owner/employee counts: {type_error}"

    def validate_owner_employee_non_negative(
        self, num_owners: Optional[int], num_employees: Optional[int]
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate owner/employee counts are non-negative.

        Args:
            num_owners: Owner count
            num_employees: Employee count

        Returns:
            Tuple of (is_valid, error_message)
        """
        if num_owners is not None and num_employees is not None:
            if num_owners < 0 or num_employees < 0:
                logger.warning(
                    "⚠️ Invalid owner/employee counts (negative values)",
                    extra={"num_owners": num_owners, "num_employees": num_employees},
                )
                return False, "Invalid owner/employee data (negative values)"
        return True, None
