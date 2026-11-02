"""
Step 6 Formatter

Formats Step 6 (Liquidity Discount) descriptions.
"""

from decimal import Decimal

from src.utils.decimal_helpers import to_decimal

from .base_formatter import BaseStepFormatter
from ..types import StepOutput, PreviousResults
from .....base_step import StepStatus


class Step6Formatter(BaseStepFormatter):
    """Formatter for Step 6 descriptions."""
    
    def format(self, template: str, result: StepOutput, previous_results: PreviousResults) -> str:
        """Format Step 6 description."""
        if result.status != StepStatus.COMPLETED:
            return template
        
        discount_raw = None
        for key in ("total_discount_percentage", "liquidity_discount_percentage"):
            if key in result.result and result.result[key] is not None:
                discount_raw = result.result[key]
                break
        if discount_raw is None:
            discount_raw = result.metadata.get("total_discount_applied", 0)
            if isinstance(discount_raw, str):
                try:
                    discount_raw = to_decimal(discount_raw.replace("%", "")) / Decimal("100.0")
                except (ValueError, AttributeError):
                    discount_raw = 0
        
        discount = self.ensure_decimal(discount_raw, "liquidity_discount", Decimal("0.0"))
        
        if discount:
            discount_pct = abs(discount * Decimal("100.0"))
            return template.replace("{adjustment}", f"{discount_pct:.1f}")
        else:
            return "Liquidity Discount: Not applied"
