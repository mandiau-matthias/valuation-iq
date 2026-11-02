"""
Step Journey Validator

Validates final step journey integrity.
"""

from typing import List, Dict, Any

from src.utils.logging import get_logger

logger = get_logger(__name__)


class StepJourneyValidator:
    """Validates step journey integrity."""

    EXPECTED_STEP_COUNT = 12
    EXPECTED_STEP_NUMBERS = list(range(12))

    @staticmethod
    def validate(calculation_steps: List[Dict[str, Any]]) -> None:
        """
        Validate step journey integrity.

        Args:
            calculation_steps: List of step dictionaries

        Raises:
            ValueError: If step count or sequence is invalid
        """
        StepJourneyValidator._validate_step_count(calculation_steps)
        StepJourneyValidator._validate_step_sequence(calculation_steps)

    @staticmethod
    def _validate_step_count(calculation_steps: List[Dict[str, Any]]) -> None:
        """Validate we have exactly 12 steps."""
        if len(calculation_steps) != StepJourneyValidator.EXPECTED_STEP_COUNT:
            logger.error(
                f"CRITICAL: Expected {StepJourneyValidator.EXPECTED_STEP_COUNT} steps, "
                f"got {len(calculation_steps)}",
                extra={
                    'expected_steps': StepJourneyValidator.EXPECTED_STEP_COUNT,
                    'actual_steps': len(calculation_steps),
                    'step_numbers': [s.get('step_number') for s in calculation_steps]
                }
            )
            raise ValueError(
                f"Expected {StepJourneyValidator.EXPECTED_STEP_COUNT} calculation steps, "
                f"got {len(calculation_steps)}"
            )

    @staticmethod
    def _validate_step_sequence(calculation_steps: List[Dict[str, Any]]) -> None:
        """Validate step numbers are sequential (0-11)."""
        step_numbers = [s.get('step_number') for s in calculation_steps]
        if step_numbers != StepJourneyValidator.EXPECTED_STEP_NUMBERS:
            logger.error(
                "CRITICAL: Step numbers are not sequential",
                extra={
                    'expected_steps': StepJourneyValidator.EXPECTED_STEP_NUMBERS,
                    'actual_steps': step_numbers,
                    'missing_steps': (
                        set(StepJourneyValidator.EXPECTED_STEP_NUMBERS) - set(step_numbers)
                    ),
                    'extra_steps': set(step_numbers) - set(StepJourneyValidator.EXPECTED_STEP_NUMBERS)
                }
            )
            raise ValueError(
                f"Step numbers must be sequential 0-11, got: {step_numbers}"
            )

