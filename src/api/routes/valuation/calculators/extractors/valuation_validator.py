"""
Valuation Validator

Validates and fixes invalid valuation values.
"""

from decimal import Decimal
from typing import Dict

from src.utils.valuation_logger import ValuationLogger


class ValuationValidator:
    """Validates and fixes invalid valuation values."""
    
    def __init__(self, logger: ValuationLogger):
        self.logger = logger
    
    def validate_and_fix(
        self,
        valuation_low: Decimal,
        valuation_mid: Decimal,
        valuation_high: Decimal,
        equity_value: Decimal,
        enterprise_value: Decimal,
    ) -> Dict[str, Decimal]:
        """
        Validate all values and apply emergency fallbacks if needed.
        
        Args:
            valuation_low: Low valuation
            valuation_mid: Mid valuation
            valuation_high: High valuation
            equity_value: Equity value
            enterprise_value: Enterprise value
            
        Returns:
            Dictionary with validated values
        """
        # Final validation
        if equity_value <= 0 or enterprise_value <= 0 or valuation_mid <= 0:
            self.logger.error(
                "❌ CRITICAL: Final validation failed - values still invalid after all fallbacks",
                extra={
                    "equity_value": equity_value,
                    "enterprise_value": enterprise_value,
                    "valuation_mid": valuation_mid,
                },
            )
            
            if equity_value <= 0:
                equity_value = Decimal("10000.0")
            if enterprise_value <= 0:
                enterprise_value = Decimal("11000.0")
            if valuation_mid <= 0:
                valuation_mid = Decimal("10000.0")
                valuation_low = valuation_mid * Decimal("0.8")
                valuation_high = valuation_mid * Decimal("1.2")
        
        return {
            "enterprise_value": enterprise_value,
            "equity_value": equity_value,
            "valuation_low": valuation_low,
            "valuation_mid": valuation_mid,
            "valuation_high": valuation_high,
        }

