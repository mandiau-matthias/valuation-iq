"""
Step 8 Formatter

Formats Step 8 (Ownership Adjustment) descriptions.
"""

from decimal import Decimal

from .base_formatter import BaseStepFormatter
from ..types import StepOutput, PreviousResults
from .....base_step import StepStatus


class Step8Formatter(BaseStepFormatter):
    """Formatter for Step 8 descriptions."""
    
    def format(self, template: str, result: StepOutput, previous_results: PreviousResults) -> str:
        """Format Step 8 description."""
        if result.status != StepStatus.COMPLETED:
            return template
        
        ownership_pct_raw = result.result.get("ownership_percentage", 100)
        ownership_pct = self.ensure_decimal(ownership_pct_raw, "ownership_percentage", Decimal("100.0"))
        
        adjustment_type = result.result.get("adjustment_type", "none")
        
        adjustment_pct_raw = result.result.get("adjustment_percentage", 0)
        adjustment_pct = self.ensure_decimal(adjustment_pct_raw, "adjustment_percentage", Decimal("0.0"))
        
        description = template.replace("{ownership_pct}", f"{ownership_pct:.2f}")
        description = description.replace("{adjustment_type}", adjustment_type)
        description = description.replace("{adjustment_pct}", f"{abs(adjustment_pct):.1f}")
        
        return description

