"""
Step 4 Error Handler

Handles error scenarios and fallback logic for Step 4.
"""

from decimal import Decimal
from typing import Optional

from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

from ...base_step import StepOutput, StepStatus

logger = get_logger(__name__)


class Step4ErrorHandler:
    """Handles error scenarios and fallback logic."""

    def __init__(self, step_name: str):
        """
        Initialize the error handler.

        Args:
            step_name: Step name for StepOutput
        """
        self.step_name = step_name

    def handle_step3_missing(self, available_steps: list) -> StepOutput:
        """
        Handle missing Step 3 results.

        Args:
            available_steps: List of available step numbers

        Returns:
            StepOutput with FAILED status
        """
        logger.error(
            "❌ Step 4 failed: Step 3 results not available",
            extra={"step_number": 4, "available_steps": available_steps, "required_step": 3},
        )
        return StepOutput(
            step_number=4,
            step_name=self.step_name,
            status=StepStatus.FAILED,
            result={},
            error="Step 3 (Base EV) results not available",
        )

    def handle_owner_employee_data_missing(self) -> StepOutput:
        """
        Handle missing owner/employee data.

        For owner-led SMEs the missing-data branch is high-impact: the discount
        framework needs num_owners and num_employees to size the dependency
        risk, and silently skipping leaves the seller with no concentration
        adjustment at all. Surface the skip as a HIGH-severity quality warning
        so the report renderer and confidence scorer can react.

        Returns:
            StepOutput with SKIPPED status and a structured quality warning.
        """
        warning = {
            "type": "owner_concentration_skipped_missing_inputs",
            "severity": "high",
            "step_number": 4,
            "step_name": self.step_name,
            "message": (
                "Owner concentration adjustment was skipped because number_of_owners "
                "and/or number_of_employees were not provided. For owner-led SMEs this "
                "is a material gap — buyers typically apply 5–20% discount for high "
                "owner dependency."
            ),
            "impact": (
                "No owner concentration discount applied. Reported EV may be "
                "overstated for owner-led businesses with thin management depth."
            ),
            "recommendation": (
                "Capture number_of_owners and number_of_employees on the request "
                "(top-level fields, business_context, or current_year_data) and "
                "re-run, or apply the discount manually before delivery."
            ),
        }
        return StepOutput(
            step_number=4,
            step_name=self.step_name,
            status=StepStatus.SKIPPED,
            result={},
            metadata={
                "reason": "Owner/employee data not available",
                "skip_severity": "high",
                "quality_warning": warning,
            },
        )

    def handle_invalid_type(
        self, num_owners: any, num_employees: any, type_error: Exception
    ) -> StepOutput:
        """
        Handle invalid type for owner/employee counts.

        Args:
            num_owners: Owner count (invalid type)
            num_employees: Employee count (invalid type)
            type_error: The type error exception

        Returns:
            StepOutput with FAILED status
        """
        logger.error(
            "❌ Invalid type for owner/employee counts",
            extra={
                "num_owners": num_owners,
                "num_employees": num_employees,
                "num_owners_type": type(num_owners).__name__,
                "num_employees_type": type(num_employees).__name__,
                "error": str(type_error),
            },
        )
        return StepOutput(
            step_number=4,
            step_name=self.step_name,
            status=StepStatus.FAILED,
            result={},
            error=f"Invalid type for owner/employee counts: {type_error}",
            metadata={"reason": "Type conversion failed"},
        )

    def handle_negative_values(self, num_owners: int, num_employees: int) -> StepOutput:
        """
        Handle negative owner/employee values.

        Args:
            num_owners: Owner count (negative)
            num_employees: Employee count (negative)

        Returns:
            StepOutput with SKIPPED status
        """
        logger.warning(
            "⚠️ Invalid owner/employee counts (negative values)",
            extra={"num_owners": num_owners, "num_employees": num_employees},
        )
        return StepOutput(
            step_number=4,
            step_name=self.step_name,
            status=StepStatus.SKIPPED,
            result={},
            metadata={"reason": "Invalid owner/employee data (negative values)"},
        )

    def handle_invalid_multiple_or_metric(
        self, current_multiple_mid: Decimal, metric_value: Decimal
    ) -> StepOutput:
        """
        Handle invalid multiple or metric from Step 3.

        Args:
            current_multiple_mid: Current multiple (mid)
            metric_value: Metric value

        Returns:
            StepOutput with FAILED status
        """
        return StepOutput(
            step_number=4,
            step_name=self.step_name,
            status=StepStatus.FAILED,
            result={},
            error=f"Invalid multiple ({current_multiple_mid}) or metric ({metric_value}) from Step 3",
        )

    def handle_adjuster_error(
        self,
        adjuster_error: Exception,
        normalized_ratio: Decimal,
        business_type_id: any,
        num_owners: int,
        num_employees: int,
    ) -> None:
        """
        Handle error from owner concentration adjuster.

        Args:
            adjuster_error: The exception from adjuster
            normalized_ratio: Normalized ratio
            business_type_id: Business type ID
            num_owners: Number of owners
            num_employees: Number of employees

        Raises:
            The original exception (to be caught by step execution handler)
        """
        import traceback

        error_msg = str(adjuster_error)
        error_type = type(adjuster_error).__name__
        traceback_str = traceback.format_exc()

        # BANK-GRADE: Structured error logging with comprehensive context
        logger.error(
            f"Owner concentration adjuster failed: {adjuster_error}",
            extra={
                "step_number": 4,
                "normalized_ratio": normalized_ratio,
                "business_type_id": business_type_id,
                "num_owners": num_owners,
                "num_employees": num_employees,
                "error_type": error_type,
                "error_message": error_msg,
            },
            exc_info=True,
        )
        raise  # Re-raise to be caught by step execution handler
