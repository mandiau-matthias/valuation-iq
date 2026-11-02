"""
Step 5 Formatter

Formats Step 5 (Size Discount) descriptions.
"""

from decimal import Decimal

from .base_formatter import BaseStepFormatter
from ..types import StepOutput, PreviousResults
from .....base_step import StepStatus


class Step5Formatter(BaseStepFormatter):
    """Formatter for Step 5 descriptions."""
    
    def format(self, template: str, result: StepOutput, previous_results: PreviousResults) -> str:
        """Format Step 5 description."""
        if result.status != StepStatus.COMPLETED:
            return template
        
        discount_raw = None
        for key in ("size_discount_percentage", "size_discount"):
            if key in result.result and result.result[key] is not None:
                discount_raw = result.result[key]
                break
        if discount_raw is None:
            discount_raw = result.metadata.get("final_discount", 0)
        
        discount = self.ensure_decimal(discount_raw, "size_discount", Decimal("0.0"))
        
        if discount:
            discount_pct = abs(discount * Decimal("100.0"))
            return template.replace("{adjustment}", f"{discount_pct:.1f}")
        else:
            return "Size Discount: Not applied"
