"""
Enterprise Value Calculator

Calculates enterprise value with debt adjustments.
"""

from decimal import Decimal
from typing import Optional

from src.api.schemas import ValuationRequest
from src.utils.valuation_logger import ValuationLogger


class EnterpriseValueCalculator:
    """Calculates enterprise value with debt adjustments."""
    
    def __init__(self, logger: ValuationLogger):
        self.logger = logger
    
    def calculate(
        self,
        valuation_mid: Decimal,
        step_3_value: Decimal,
        request: ValuationRequest,
    ) -> Decimal:
        """
        Calculate enterprise value with fallbacks and debt adjustments.
        
        Args:
            valuation_mid: Mid valuation (for fallback)
            step_3_value: Enterprise value from Step 3
            request: Valuation request with debt data
            
        Returns:
            Enterprise value
        """
        if step_3_value > 0:
            return step_3_value
        
        # Fallback: derive from valuation_mid
        enterprise_value = valuation_mid * Decimal("1.1")
        
        # Use actual debt data if available
        net_debt = self._calculate_net_debt(request)
        if net_debt is not None:
            enterprise_value = valuation_mid + net_debt
            if enterprise_value <= 0:
                enterprise_value = valuation_mid * Decimal("1.1")
        
        self.logger.warning(
            "⚠️ enterprise_value is invalid, deriving from valuation_mid",
            extra={
                "original_enterprise_value": step_3_value,
                "calculated_enterprise_value": enterprise_value,
                "valuation_mid": valuation_mid,
            },
        )
        
        return enterprise_value
    
    def _calculate_net_debt(self, request: ValuationRequest) -> Optional[Decimal]:
        """Calculate net debt from request."""
        if not hasattr(request, "current_year_data") or not request.current_year_data:
            return None
        
        total_debt = getattr(request.current_year_data, "total_debt", None)
        cash = getattr(request.current_year_data, "cash", None)
        
        if total_debt is not None and cash is not None:
            return (total_debt or Decimal("0.0")) - (cash or Decimal("0.0"))
        
        return None
