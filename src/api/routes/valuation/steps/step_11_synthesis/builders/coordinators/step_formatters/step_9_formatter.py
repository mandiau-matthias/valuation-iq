"""
Step 9 Formatter

Formats Step 9 (Confidence Score) descriptions.
"""

from decimal import Decimal

from .base_formatter import BaseStepFormatter
from ..types import StepOutput, PreviousResults
from .....base_step import StepStatus


class Step9Formatter(BaseStepFormatter):
    """Formatter for Step 9 descriptions."""
    
    def format(self, template: str, result: StepOutput, previous_results: PreviousResults) -> str:
        """Format Step 9 description."""
        if result.status != StepStatus.COMPLETED:
            return template
        
        confidence_score_raw = result.result.get("overall_confidence_score", 66)
        confidence_score = self.ensure_decimal(confidence_score_raw, "overall_confidence_score", Decimal("66.0"))
        
        return template.replace("{confidence_score}", f"{confidence_score:.0f}")

