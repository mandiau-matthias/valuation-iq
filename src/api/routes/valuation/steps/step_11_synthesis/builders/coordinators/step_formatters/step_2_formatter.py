"""
Step 2 Formatter

Formats Step 2 (Industry Benchmarking) descriptions.
"""

from .base_formatter import BaseStepFormatter
from ..types import StepOutput, PreviousResults
from .....base_step import StepStatus


class Step2Formatter(BaseStepFormatter):
    """Formatter for Step 2 descriptions."""
    
    def format(self, template: str, result: StepOutput, previous_results: PreviousResults) -> str:
        """Format Step 2 description."""
        if result.status != StepStatus.COMPLETED:
            return template
        
        primary_method = result.result.get("primary_method", "Revenue")
        return template.replace("{primary_method}", primary_method)

