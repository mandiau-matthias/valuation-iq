"""
Step Description Formatting Coordinator

Orchestrates step description formatting with actual values from step results.
"""

from src.errors import ValidationError
from src.utils.logging import get_logger
from .types import PreviousResults, StepOutput
from .validation import BankGradeValidator
from .step_formatters import (
    Step2Formatter,
    Step4Formatter,
    Step5Formatter,
    Step6Formatter,
    Step8Formatter,
    Step9Formatter,
    Step10Formatter,
    Step11Formatter,
)

logger = get_logger(__name__)


class StepDescriptionFormattingCoordinator:
    """
    Coordinates step description formatting with actual values.
    
    Uses Strategy pattern with individual formatters for each step to reduce complexity.
    """
    
    def __init__(self) -> None:
        self.logger = logger
        # Initialize formatters using Strategy pattern
        self.formatters = {
            2: Step2Formatter(),
            4: Step4Formatter(),
            5: Step5Formatter(),
            6: Step6Formatter(),
            8: Step8Formatter(),
            9: Step9Formatter(),
            10: Step10Formatter(),
            11: Step11Formatter(),
        }
    
    def format_step_description(
        self, template: str, step_num: int, result: StepOutput, previous_results: PreviousResults
    ) -> str:
        """
        Format step description with actual values.
        
        BANK-GRADE: Includes input validation and Decimal type safety.
        
        Args:
            template: Description template with placeholders
            step_num: Step number
            result: Step result
            previous_results: All previous step results
            
        Returns:
            Formatted description string
            
        Raises:
            ValidationError: If inputs are invalid
        """
        # Bank-grade input validation
        if not isinstance(template, str):
            raise ValidationError(f"template must be str, got {type(template).__name__}")
        
        if not isinstance(step_num, int):
            raise ValidationError(f"step_num must be int, got {type(step_num).__name__}")
        
        try:
            BankGradeValidator.validate_step_result(result, step_num)
        except ValidationError as e:
            self.logger.warning(
                f"⚠️ Step {step_num} result validation warning: {e}",
                extra={"step_number": step_num},
            )
        
        # Use formatter if available, otherwise return template as-is
        formatter = self.formatters.get(step_num)
        if formatter:
            return formatter.format(template, result, previous_results)
        
        # Steps without formatters return template unchanged
        return template

