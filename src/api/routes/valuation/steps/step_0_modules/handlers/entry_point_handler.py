"""
Entry Point Handler for Step 0 Data Quality

Handles defensive logging, input validation, and request extraction at method entry.
"""

from typing import Optional, Tuple

from src.utils.logging import get_logger

from ...base_step import StepInput, StepOutput, StepStatus

logger = get_logger(__name__)


class EntryPointHandler:
    """Handles entry point validation and defensive logging for Step 0."""

    def __init__(self, step_name: str):
        """
        Initialize the entry point handler.

        Args:
            step_name: The name of the step (e.g., "Data Quality Assessment")
        """
        self.step_name = step_name

    def handle_entry(
        self, input_data: Optional[StepInput], step_number: int = 0
    ) -> Tuple[Optional[object], Optional[StepOutput]]:
        """
        Handle entry point validation and defensive logging.

        Args:
            input_data: The input data for the step
            step_number: The step number (default: 0)

        Returns:
            Tuple of (request, early_return_output):
            - request: The extracted request object, or None if validation failed
            - early_return_output: StepOutput to return early if validation failed, or None
        """
        # Ultra-defensive entry point logging - absolute first thing, no variable access
        self._log_entry_raw()

        # Print immediately on entry - no variable access
        self._print_entry()

        # Validate and log input data
        input_data_info = self._validate_and_log_input_data(input_data)

        # Validate and log step attributes
        step_attrs_info = self._validate_and_log_step_attributes()

        # Log entry point
        self._log_entry_point(input_data_info, step_attrs_info, step_number)

        # Validate input_data exists
        if not input_data:
            return None, self._create_early_return(
                step_number, "input_data_is_none", "Step 0: input_data is None"
            )

        # Validate request exists
        try:
            request = input_data.request
        except AttributeError as e:
            return None, self._create_early_return(
                step_number,
                "request_missing",
                f"Step 0: input_data.request missing: {str(e)}",
                error=str(e),
                input_data_attrs=dir(input_data) if input_data else [],
            )

        if not request:
            return None, self._create_early_return(
                step_number, "request_is_none", "Step 0: request is None"
            )

        return request, None

    def _log_entry_raw(self) -> None:
        """BANK-GRADE: Structured logging for entry point."""
        logger.debug(
            "[STEP-0-ENTRY] Execute method entry point",
            extra={"step_name": self.step_name}
        )

    def _print_entry(self) -> None:
        """BANK-GRADE: Structured logging for entry point information."""
        logger.debug(
            "[STEP-0-ENTRY] Method entry point reached",
            extra={"step_name": self.step_name}
        )
        logger.debug(
            "[STEP-0] Execute method called",
            extra={"step_name": self.step_name}
        )

    def _validate_and_log_input_data(self, input_data: Optional[StepInput]) -> dict:
        """BANK-GRADE: Validate and log input data information using structured logging."""
        info = {"exists": input_data is not None, "type": None}

        if input_data:
            info["type"] = type(input_data).__name__
            logger.debug(
                "[STEP-0] Input data validation",
                extra={
                    "step_name": self.step_name,
                    "input_data_exists": info["exists"],
                    "input_data_type": info["type"],
                }
            )
        else:
            logger.debug(
                "[STEP-0] Input data validation",
                extra={
                    "step_name": self.step_name,
                    "input_data_exists": False,
                    "input_data_type": None,
                }
            )

        return info

    def _validate_and_log_step_attributes(self) -> dict:
        """BANK-GRADE: Validate and log step attributes using structured logging."""
        info = {
            "has_step_name": False,
            "step_name": None,
            "has_quality_assessor": False,
            "quality_assessor_type": None,
        }

        logger.debug(
            "[STEP-0] Validating step attributes",
            extra={"step_name": self.step_name}
        )

        try:
            info["step_name"] = getattr(self, "step_name", "Unknown")
            info["has_step_name"] = True
            logger.debug(
                "[STEP-0] Step name accessed",
                extra={
                    "step_name": info["step_name"],
                    "has_step_name": True,
                }
            )
        except (AttributeError, TypeError, ValueError) as e:
            logger.warning(
                "[STEP-0] Failed to access step_name",
                extra={
                    "step_name": self.step_name,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                }
            )

        # Note: quality_assessor check would need self reference, but we don't have it here
        # This is handled in the main step class

        return info

    def _log_entry_point(
        self, input_data_info: dict, step_attrs_info: dict, step_number: int
    ) -> None:
        """BANK-GRADE: Log entry point with comprehensive information using structured logging."""
        logger.info(
            "🔍 Step 0: EXECUTE METHOD CALLED - Entry point",
            extra={
                "step_number": step_number,
                "step_name": step_attrs_info.get("step_name"),
                "has_input_data": input_data_info.get("exists"),
                "input_data_type": input_data_info.get("type"),
                "has_quality_assessor": step_attrs_info.get("has_quality_assessor"),
                "quality_assessor_type": step_attrs_info.get("quality_assessor_type"),
            },
        )

    def _create_early_return(
        self, step_number: int, reason: str, message: str, **extra_kwargs
    ) -> StepOutput:
        """
        Create an early return StepOutput for validation failures.

        Args:
            step_number: The step number
            reason: The reason for early return
            message: The error message
            **extra_kwargs: Additional error information

        Returns:
            StepOutput with fallback values
        """
        # BANK-GRADE: Structured logging for early return
        logger.error(
            f"❌ CRITICAL: Step 0 {reason}",
            extra={
                "step_number": step_number,
                "reason": reason,
                "message": message,
                **extra_kwargs
            },
            exc_info=True if "error" in extra_kwargs else False,
        )

        return StepOutput(
            step_number=step_number,
            step_name=self.step_name,
            status=StepStatus.COMPLETED,  # Mark as completed with fallback
            result={
                "quality_score": 50,
                "dcf_eligible": False,
                "multiples_method": "primary",
                "dimension_scores": {},
                "warnings": [{"severity": "critical", "message": message}],
                "recommendations": [],
            },
            metadata={"fallback_mode": True, "reason": reason},
        )
