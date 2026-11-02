"""
Step Output Validator

Validates and fixes step outputs to ensure they are dictionaries.
"""

from typing import List, Dict, Any
from src.utils.logging import get_logger

logger = get_logger(__name__)


class StepOutputValidator:
    """
    Validates and fixes step outputs to ensure they are dictionaries.
    
    Prevents AttributeError when templates access step.outputs.adjustment_percentage.
    """
    
    @staticmethod
    def validate_and_fix_step_outputs(calculation_steps: List[Dict[str, Any]]) -> None:
        """
        Validate and fix all step outputs to ensure they are dictionaries.
        
        Args:
            calculation_steps: List of calculation step dictionaries
        """
        for step in calculation_steps:
            if isinstance(step, dict):
                # Ensure 'outputs' is always a dictionary
                if 'outputs' not in step or not isinstance(step.get('outputs'), dict):
                    step['outputs'] = {}
                # Ensure 'inputs' is always a dictionary
                if 'inputs' not in step or not isinstance(step.get('inputs'), dict):
                    step['inputs'] = {}
                
                # For steps that typically have adjustment_percentage, ensure it exists
                step_number = step.get('step_number')
                outputs = step.get('outputs', {})
                if step_number in [4, 5, 6, 8] and isinstance(outputs, dict):
                    if 'adjustment_percentage' not in outputs:
                        discount_pct = outputs.get('discount_percentage')
                        outputs['adjustment_percentage'] = discount_pct

