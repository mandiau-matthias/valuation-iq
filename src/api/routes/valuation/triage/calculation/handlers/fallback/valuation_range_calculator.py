"""
Valuation Range Calculator

Calculates valuation range from equity value or revenue/EBITDA.
"""

from decimal import Decimal
from typing import Any, Optional, Tuple

from src.api.schemas import ValuationRequest
from src.utils.decimal_helpers import to_decimal
from src.utils.valuation_logger import ValuationLogger


class ValuationRangeCalculator:
    """Calculates valuation range with multiple fallback strategies."""
    
    def __init__(self, logger: ValuationLogger):
        self.logger = logger
    
    def calculate_from_equity(
        self, equity_value: Decimal, spread_pct: Decimal
    ) -> Tuple[Decimal, Decimal, Decimal]:
        """
        Calculate valuation range from equity value.
        
        Args:
            equity_value: Equity value
            spread_pct: Spread percentage
            
        Returns:
            Tuple of (valuation_low, valuation_mid, valuation_high)
        """
        valuation_mid = equity_value
        valuation_low = valuation_mid * (Decimal("1") - spread_pct)
        valuation_high = valuation_mid * (Decimal("1") + spread_pct)
        return valuation_low, valuation_mid, valuation_high
    
    def calculate_from_revenue_ebitda(
        self, request: ValuationRequest, spread_pct: Decimal
    ) -> Tuple[Decimal, Decimal, Decimal, int]:
        """
        Calculate valuation range from revenue/EBITDA with fallbacks.
        
        Args:
            request: Valuation request
            spread_pct: Spread percentage
            
        Returns:
            Tuple of (valuation_low, valuation_mid, valuation_high, confidence_score)
        """
        revenue = self._get_revenue(request)
        ebitda = self._get_ebitda(request)
        
        if revenue and revenue > 0:
            valuation_mid = to_decimal(revenue) * Decimal("0.5")
            valuation_low = valuation_mid * (Decimal("1") - spread_pct)
            valuation_high = valuation_mid * (Decimal("1") + spread_pct)
            confidence_score = 30  # At least 30% confidence
            self.logger.info(
                "✅ Step 11 fallback: Using revenue-based estimate",
                extra={"revenue": revenue, "valuation_mid": valuation_mid},
            )
        elif ebitda and ebitda > 0:
            valuation_mid = to_decimal(ebitda) * Decimal("3.0")
            valuation_low = valuation_mid * (Decimal("1") - spread_pct)
            valuation_high = valuation_mid * (Decimal("1") + spread_pct)
            confidence_score = 30  # At least 30% confidence
            self.logger.info(
                "✅ Step 11 fallback: Using EBITDA-based estimate",
                extra={"ebitda": ebitda, "valuation_mid": valuation_mid},
            )
        else:
            # Absolute minimum fallback
            valuation_mid = Decimal("10000.0")
            valuation_low = valuation_mid * Decimal("0.8")
            valuation_high = valuation_mid * Decimal("1.2")
            confidence_score = 0  # No confidence with no data
            self.logger.warning(
                "⚠️ Step 11 fallback: Using absolute minimum (€10K) - no revenue/EBITDA data available",
            )
        
        return valuation_low, valuation_mid, valuation_high, confidence_score
    
    def calculate_emergency_minimum(
        self, request: ValuationRequest
    ) -> Tuple[Decimal, Decimal, Decimal]:
        """
        Calculate emergency minimum valuation range (last resort).
        
        Args:
            request: Valuation request
            
        Returns:
            Tuple of (valuation_low, valuation_mid, valuation_high)
        """
        revenue = self._get_revenue(request)
        ebitda = self._get_ebitda(request)
        
        if revenue and revenue > 0:
            valuation_mid = to_decimal(revenue) * Decimal("0.5")
        elif ebitda and ebitda > 0:
            valuation_mid = to_decimal(ebitda) * Decimal("3.0")
        else:
            valuation_mid = Decimal("10000.0")  # €10K minimum
        
        valuation_low = valuation_mid * Decimal("0.8")
        valuation_high = valuation_mid * Decimal("1.2")
        
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

