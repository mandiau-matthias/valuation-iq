"""
Valuation Fallback Calculator

Calculates fallback valuation values when primary sources are invalid.
"""

from decimal import Decimal
from typing import Optional

from src.api.schemas import ValuationRequest
from src.utils.decimal_helpers import to_decimal
from src.utils.valuation_logger import ValuationLogger


class ValuationFallbackCalculator:
    """Calculates fallback valuation values."""
    
    def __init__(self, logger: ValuationLogger):
        self.logger = logger
    
    def calculate_from_equity(
        self, equity_value: Decimal
    ) -> tuple[Decimal, Decimal, Decimal]:
        """
        Calculate valuation range from equity value.
        
        Args:
            equity_value: Equity value to use as base
            
        Returns:
            Tuple of (valuation_low, valuation_mid, valuation_high)
        """
        valuation_mid = equity_value
        valuation_low = equity_value * Decimal("0.8")
        valuation_high = equity_value * Decimal("1.2")
        return valuation_low, valuation_mid, valuation_high
    
    def calculate_from_revenue_ebitda(
        self, request: ValuationRequest
    ) -> tuple[Decimal, Decimal, Decimal]:
        """
        Calculate valuation range from revenue/EBITDA (last resort).
        
        Args:
            request: Valuation request with financial data
            
        Returns:
            Tuple of (valuation_low, valuation_mid, valuation_high)
        """
        revenue = self._get_revenue(request)
        ebitda = self._get_ebitda(request)
        
        if revenue and revenue > 0:
            valuation_mid = to_decimal(revenue) * Decimal("0.5")
            valuation_low = valuation_mid * Decimal("0.8")
            valuation_high = valuation_mid * Decimal("1.2")
            self.logger.warning(
                "⚠️ Using revenue-based fallback for valuation",
                extra={"valuation_mid": valuation_mid, "revenue": revenue},
            )
        elif ebitda and ebitda > 0:
            valuation_mid = to_decimal(ebitda) * Decimal("3.0")
            valuation_low = valuation_mid * Decimal("0.8")
            valuation_high = valuation_mid * Decimal("1.2")
            self.logger.warning(
                "⚠️ Using EBITDA-based fallback for valuation",
                extra={"valuation_mid": valuation_mid, "ebitda": ebitda},
            )
        else:
            # Absolute minimum fallback
            valuation_mid = Decimal("10000.0")
            valuation_low = valuation_mid * Decimal("0.8")
            valuation_high = valuation_mid * Decimal("1.2")
            self.logger.warning(
                "⚠️ Using absolute minimum fallback (€10K) - no revenue/EBITDA data",
            )
        
        return valuation_low, valuation_mid, valuation_high
    
    def _get_revenue(self, request: ValuationRequest) -> Optional[Decimal]:
        """Extract revenue from request."""
        if hasattr(request, "current_year_data") and request.current_year_data:
            return getattr(request.current_year_data, "revenue", None)
        return None
    
    def _get_ebitda(self, request: ValuationRequest) -> Optional[Decimal]:
        """Extract EBITDA from request."""
        if hasattr(request, "current_year_data") and request.current_year_data:
            return getattr(request.current_year_data, "ebitda", None)
        return None
