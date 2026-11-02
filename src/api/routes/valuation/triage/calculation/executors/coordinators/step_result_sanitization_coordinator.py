"""
Step Result Sanitization Coordinator

Handles result sanitization logic (NaN/Infinity handling).
Extracted from step_executor.py to improve modularity.

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive sanitization
- Detailed logging
"""

from collections.abc import Mapping

from src.api.routes.valuation.steps.base_step import CalculationStep, StepOutput
from src.utils.valuation_logger import ValuationLogger

from .step_result_sanitization import sanitize_step_output

logger = ValuationLogger(__name__)


class StepResultSanitizationCoordinator:
    """
    Coordinates step result sanitization logic.

    Responsibilities:
    - Sanitize results (NaN/Infinity handling)
    - Log sanitization events
    - Preserve original result if sanitization fails
    """

    def __init__(self, logger_instance):
        """
        Initialize step result sanitization coordinator.

        Args:
            logger_instance: Logger instance
        """
        self.logger = logger_instance

    def sanitize_step_result(
        self,
        step: CalculationStep,
        output: StepOutput,
        context: Mapping[str, object],
    ) -> StepOutput:
        """
        Sanitize step result, removing NaN/Infinity values.

        Args:
            step: The step that was executed
            output: The step output to sanitize
            context: Execution context

        Returns:
            Sanitized StepOutput (may be recreated if sanitization modified result)
        """
        return sanitize_step_output(self.logger, step, output, context)
