"""
Step 10 Formatter

Formats Step 10 (Range Methodology) descriptions.
"""

from decimal import Decimal

from .base_formatter import BaseStepFormatter
from ..types import StepOutput, PreviousResults
from .....base_step import StepStatus


class Step10Formatter(BaseStepFormatter):
    """Formatter for Step 10 descriptions."""
    
    def format(self, template: str, result: StepOutput, previous_results: PreviousResults) -> str:
        """Format Step 10 description."""
        if result.status != StepStatus.COMPLETED:
            return template
        
        methodology = result.result.get("methodology", "Confidence Spread")
        return template.replace("{methodology}", methodology)

