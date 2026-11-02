"""
Step Result Validation Coordinator

Handles result validation logic, especially for Step 2.
Extracted from step_executor.py to improve modularity.

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive validation
- Recovery logic for Step 2
"""

from collections.abc import Mapping

from src.api.routes.valuation.steps.base_step import CalculationStep, StepOutput
from src.utils.valuation_logger import ValuationLogger

from .step2_result_validation import validate_step_2_result

logger = ValuationLogger(__name__)


class StepResultValidationCoordinator:
    """
    Coordinates step result validation logic.

    Responsibilities:
    - Validate Step 2 results (special handling)
    - Validate other step results
    - Recovery logic for Step 2
    """

    def __init__(self, logger_instance):
        """
        Initialize step result validation coordinator.

        Args:
            logger_instance: Logger instance
        """
        self.logger = logger_instance

    def validate_step_result(
        self,
        step: CalculationStep,
        output: StepOutput,
        context: Mapping[str, object],
    ) -> StepOutput:
        """
        Validate step result, with special handling for Step 2.

        Args:
            step: The step that was executed
            output: The step output to validate
            context: Execution context

        Returns:
            Validated StepOutput (may be modified if recovery occurred)
        """
        # Special validation for Step 2
        if step.step_number == 2:
            return self._validate_step2_result(output, context)

        # For other steps, validate result is not empty
        if (
            hasattr(output, "status")
            and output.status.value == "completed"
            and hasattr(output, "result")
            and isinstance(output.result, dict)
        ):
            if len(output.result) == 0:
                self.logger.warning(
                    f"⚠️ Step {step.step_number} result is empty",
                    extra={
                        "step_number": step.step_number,
                        "step_name": step.step_name,
                        "correlation_id": context.get("correlation_id"),
                    },
                )

        return output

    def _validate_step2_result(
        self, output: StepOutput, context: Mapping[str, object]
    ) -> StepOutput:
        """
        Validate Step 2 result with recovery logic.

        Args:
            output: Step 2 output to validate
            context: Execution context

        Returns:
            Validated StepOutput (may be modified if recovery occurred)
        """
        return validate_step_2_result(self.logger, output, context)
