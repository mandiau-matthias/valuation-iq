"""
Step 4 Formatter

Formats Step 4 (Owner Concentration) descriptions.
"""

from decimal import Decimal

from .base_formatter import BaseStepFormatter
from ..types import StepOutput, PreviousResults
from .....base_step import StepStatus


class Step4Formatter(BaseStepFormatter):
    """Formatter for Step 4 descriptions."""
    
    def format(self, template: str, result: StepOutput, previous_results: PreviousResults) -> str:
        """Format Step 4 description."""
        if result.status != StepStatus.COMPLETED:
            return template
        
        adjustment_raw = result.result.get("owner_concentration_adjustment", 0)
        adjustment = self.ensure_decimal(adjustment_raw, "owner_concentration_adjustment", Decimal("0.0"))
        
        if adjustment:
            adjustment_pct = abs(adjustment * Decimal("100.0"))
            return template.replace("{adjustment}", f"{adjustment_pct:.1f}")
        else:
            return "Owner Concentration: Not applied (insufficient data or not applicable)"

