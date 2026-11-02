"""
Asking Price Calculation Coordinator

Handles asking price calculation logic.
Extracted from synthesizer.py to improve modularity.

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive price calculation
- Detailed logging
"""

from decimal import Decimal
from typing import Optional, Tuple

from src.config.valuation_constants import get_asking_price_markup
from src.utils.decimal_helpers import bank_round, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class AskingPriceCalculationCoordinator:
    """
    Coordinates asking price calculation logic.
    
    Responsibilities:
    - Calculate recommended asking price
    - Apply confidence-based markup
    - Round to clean presentation values
    """
    
    def __init__(self):
        """Initialize asking price calculation coordinator."""
        self.logger = logger
    
    def calculate_asking_price(
        self, 
        equity_value_mid: Decimal, 
        confidence_score: int,
        ebitda: Optional[Decimal] = None,
        net_debt: Optional[Decimal] = None,
        current_multiple: Optional[Decimal] = None
    ) -> Tuple[Decimal, Decimal]:
        """
        Calculate recommended asking price and strategic asking multiple.
        
        Typically 10-20% above valuation to allow for negotiation.
        Higher confidence = higher markup is justified.
        
        Applying the markup to the MULTIPLE instead of the final value 
        ensures negotiation space is built into the yield expectations.
        
        Args:
            equity_value_mid: Mid-point equity value
            confidence_score: Overall confidence score (0-100)
            ebitda: Company EBITDA (optional, for multiple calculation)
            net_debt: Company Net Debt (optional, for multiple calculation)
            current_multiple: Current adjusted multiple (optional)
            
        Returns:
            Tuple of (Recommended asking price, Strategic asking multiple)
        """
        equity_value_mid_decimal = to_decimal(equity_value_mid)
        ebitda_decimal = to_decimal(ebitda) if ebitda is not None else None
        net_debt_decimal = to_decimal(net_debt) if net_debt is not None else Decimal("0")
        
        if confidence_score >= 75:
            confidence_level = "high"
        elif confidence_score >= 50:
            confidence_level = "medium"
        else:
            confidence_level = "low"
        markup_factor = get_asking_price_markup(confidence_level)
        
        # Logic: Apply premium to the multiple
        # 1. Get current effective multiple if not provided
        if current_multiple is None and ebitda_decimal and ebitda_decimal > 0:
            enterprise_value = equity_value_mid_decimal + net_debt_decimal
            current_multiple = enterprise_value / ebitda_decimal
        
        if current_multiple is not None:
            # Apply premium to multiple
            asking_multiple = current_multiple * markup_factor
            
            # Calculate asking price from new multiple: EV = EBITDA * Asking Multiple
            # Asking Equity Price = EV - Net Debt
            if ebitda_decimal:
                asking_ev = ebitda_decimal * asking_multiple
                asking_price = asking_ev - net_debt_decimal
            else:
                # Fallback if no EBITDA
                asking_price = equity_value_mid_decimal * markup_factor
                asking_multiple = Decimal("0")
        else:
            # Fallback to value markup
            asking_price = equity_value_mid_decimal * markup_factor
            asking_multiple = Decimal("0")
        
        # Round to nearest 10,000 for cleaner presentation
        asking_price_rounded = bank_round(asking_price / Decimal("10000"), 0) * Decimal("10000")
        
        return asking_price_rounded, bank_round(asking_multiple, 2)

