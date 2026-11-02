"""
Step Placeholder Creator

Creates placeholder steps for missing data.
"""

from typing import Dict, Any

# Import from __init__ using relative import to avoid circular dependency
from .utils import ensure_step_outputs_defaults
from src.utils.logging import get_logger

logger = get_logger(__name__)


class StepPlaceholderCreator:
    """Creates placeholder steps for missing data."""

    @staticmethod
    def create_placeholder(step_number: int) -> Dict[str, Any]:
        """
        Create placeholder step with not_executed status.

        Args:
            step_number: Step number (0-11)

        Returns:
            Dictionary containing placeholder step data
        """
        # Ensure outputs has all required fields with defaults
        placeholder_outputs = ensure_step_outputs_defaults({})

        placeholder = {
            'step_number': step_number,
            'step_name': f'Step {step_number}',  # Template expects this field
            'calculation_name': f'Step {step_number}',
            'formula': '',
            'formula_explanation': None,
            'inputs': {},
            'output': 0,
            'outputs': placeholder_outputs,
            'explanation': f'Step {step_number} data not available from triage system',
            'rationale': f'Step {step_number} was not executed',  # Template expects this field
            'metadata': {},
            'status': 'not_executed',
            'skip_reason': None,
            'academic_source_ids': [],
            'academic_sources': [],
        }

        logger.debug(
            f"Step {step_number} not found in transparency data, created placeholder",
            extra={'step_number': step_number, 'status': 'not_executed'}
        )

        return placeholder

