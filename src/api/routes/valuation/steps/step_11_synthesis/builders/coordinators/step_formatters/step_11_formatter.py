"""
Step 11 Formatter

Formats Step 11 (Final Valuation) descriptions.
"""

from decimal import Decimal

from src.errors import ValidationError

from .base_formatter import BaseStepFormatter
from ..types import StepOutput, PreviousResults
from ..validation import BankGradeValidator
from .....base_step import StepStatus


class Step11Formatter(BaseStepFormatter):
    """Formatter for Step 11 descriptions."""
    
    def format(self, template: str, result: StepOutput, previous_results: PreviousResults) -> str:
        """Format Step 11 description."""
        # Get final values from Step 10
        step10 = previous_results.get(10)
        if not step10 or step10.status != StepStatus.COMPLETED:
            return template
        
        # Extract valuation range
        low_raw = step10.result.get("valuation_low", 0)
        high_raw = step10.result.get("valuation_high", 0)
        
        low = self.ensure_decimal(low_raw, "valuation_low", Decimal("0.0"))
        high = self.ensure_decimal(high_raw, "valuation_high", Decimal("0.0"))
        
        # Validate range ordering
        try:
            mid_raw = step10.result.get("valuation_mid", 0)
            mid = self.ensure_decimal(mid_raw, "valuation_mid", Decimal("0.0"))
            BankGradeValidator.validate_range(low, mid, high, "valuation")
        except ValidationError as e:
            self.logger.warning(
                f"⚠️ Step 10 range validation warning: {e}",
                extra={"step_number": 10},
            )
        
        description = template.replace("{low}", f"{low/Decimal('1000.0'):.0f}")
        description = description.replace("{high}", f"{high/Decimal('1000.0'):.0f}")
        
        return description

