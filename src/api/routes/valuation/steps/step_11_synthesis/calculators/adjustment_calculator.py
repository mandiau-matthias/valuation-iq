"""
Adjustment Calculator for Step 11 Synthesis

Handles asking price calculation and value adjustments.
"""

from decimal import Decimal
from typing import Optional

from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class AdjustmentCalculator:
    """
    Calculator for adjustment operations.

    Responsibilities:
    - Calculate asking price with markup
    - Apply value adjustments
    - Handle rounding for adjustments
    """

    def __init__(self, range_calculator):
        """
        Initialize adjustment calculator.

        Args:
            range_calculator: RangeCalculator instance for rounding
        """
        self.range_calculator = range_calculator

    def calculate_asking_price(
        self, valuation_mid: Decimal, asking_price_markup: Decimal, current_multiple: Optional[Decimal] = None
    ) -> tuple[Optional[Decimal], Optional[Decimal]]:
        """
        Calculate asking price with markup and strategic asking multiple.

        Args:
            valuation_mid: Mid-point valuation
            asking_price_markup: Markup percentage (e.g., Decimal('0.15') for 15%)
            current_multiple: Current adjusted multiple (optional)

        Returns:
            Tuple of (Asking price, Asking multiple) or (None, None) if markup is 0
        """
        if asking_price_markup <= 0:
            return None, None

        markup_factor = 1 + asking_price_markup
        asking_price = self.range_calculator.round_valuation(
            valuation_mid * markup_factor
        )
        
        asking_multiple = None
        if current_multiple:
            asking_multiple = current_multiple * markup_factor

        logger.debug(
            "Calculated asking price",
            extra={
                "valuation_mid": valuation_mid,
                "markup": asking_price_markup,
                "asking_price": asking_price,
                "asking_multiple": asking_multiple,
            },
        )

        return asking_price, asking_multiple
