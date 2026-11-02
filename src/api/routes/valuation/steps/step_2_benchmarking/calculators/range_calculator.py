"""
Range Calculator for Step 2 Benchmarking

This module wraps the existing ValuationRangeCalculator to provide range calculations
for Step 2 benchmarking. Reuses existing domain calculator to avoid duplication.

Author: Upswitch Engineering Team
Date: January 2025
Status: Production Ready
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from src.domain.range_calculator import ValuationRangeCalculator
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.exceptions import ValidationError
from src.utils.valuation_logger import ValuationLogger

logger = ValuationLogger(__name__)


class RangeCalculator:
    """
    Wrapper for ValuationRangeCalculator to provide range calculations for Step 2.

    Reuses existing ValuationRangeCalculator.calculate_multiples_dispersion_range()
    instead of duplicating range calculation logic.

    Dependencies:
    - ValuationRangeCalculator from src.domain.range_calculator
    """

    def __init__(self):
        """Initialize RangeCalculator wrapper."""
        self.range_calculator = ValuationRangeCalculator()
        self.logger = logger

    def calculate_multiples_dispersion_range(
        self,
        ebitda: Decimal,
        revenue: Decimal,
        p25_ebitda_multiple: Optional[Decimal],
        p50_ebitda_multiple: Optional[Decimal],
        p75_ebitda_multiple: Optional[Decimal],
        revenue_multiple_p25: Optional[Decimal],
        revenue_multiple_p50: Optional[Decimal],
        revenue_multiple_p75: Optional[Decimal],
        total_adjustment_factor: Decimal,
        net_debt: Decimal = Decimal("0.0"),
        cash: Decimal = Decimal("0.0"),
        primary_method: str = "ebitda_multiple",
    ) -> Dict[str, Decimal]:
        """
        Calculate range using multiple dispersion (P25/P50/P75).

        Delegates to ValuationRangeCalculator.calculate_multiples_dispersion_range()
        to reuse existing, tested range calculation logic.

        Formula:
            Low = P25 Multiple × Financial Metric × Adjustment Factor - Net Debt
            Mid = P50 Multiple × Financial Metric × Adjustment Factor - Net Debt
            High = P75 Multiple × Financial Metric × Adjustment Factor - Net Debt

        Args:
            ebitda: EBITDA value
            revenue: Revenue value
            p25_ebitda_multiple: 25th percentile EBITDA multiple
            p50_ebitda_multiple: 50th percentile (median) EBITDA multiple
            p75_ebitda_multiple: 75th percentile EBITDA multiple
            revenue_multiple_p25: 25th percentile revenue multiple
            revenue_multiple_p50: 50th percentile (median) revenue multiple
            revenue_multiple_p75: 75th percentile revenue multiple
            total_adjustment_factor: Combined adjustment factor
            net_debt: Net debt (total_debt - cash)
            cash: Cash balance
            primary_method: "ebitda_multiple" or "revenue_multiple"

        Returns:
            Dict with equity_value_low, equity_value_mid, equity_value_high, and range_methodology

        Examples:
            >>> calculator = RangeCalculator()
            >>> range_result = calculator.calculate_multiples_dispersion_range(
            ...     ebitda=100000,
            ...     revenue=1000000,
            ...     p25_ebitda_multiple=Decimal('8.0'),
            ...     p50_ebitda_multiple=Decimal('10.0'),
            ...     p75_ebitda_multiple=Decimal('12.0'),
            ...     revenue_multiple_p25=Decimal('0.8'),
            ...     revenue_multiple_p50=Decimal('1.0'),
            ...     revenue_multiple_p75=Decimal('1.2'),
            ...     total_adjustment_factor=Decimal('1.0'),
            ...     primary_method="ebitda_multiple"
            ... )
            >>> print(f"Mid value: €{range_result['equity_value_mid']:,.0f}")
        """
        try:
            # Delegate to existing ValuationRangeCalculator
            result = self.range_calculator.calculate_multiples_dispersion_range(
                ebitda=ebitda,
                revenue=revenue,
                p25_ebitda_multiple=p25_ebitda_multiple,
                p50_ebitda_multiple=p50_ebitda_multiple,
                p75_ebitda_multiple=p75_ebitda_multiple,
                revenue_multiple_p25=revenue_multiple_p25,
                revenue_multiple_p50=revenue_multiple_p50,
                revenue_multiple_p75=revenue_multiple_p75,
                total_adjustment_factor=total_adjustment_factor,
                net_debt=net_debt,
                cash=cash,
                primary_method=primary_method,
            )

            self.logger.info(
                "✓ Range calculated using multiples dispersion",
                extra={
                    "primary_method": primary_method,
                    "equity_value_low": result.get("equity_value_low"),
                    "equity_value_mid": result.get("equity_value_mid"),
                    "equity_value_high": result.get("equity_value_high"),
                    "range_methodology": result.get("range_methodology"),
                },
            )

            return result

        except ValidationError:
            raise
        except Exception as e:
            self.logger.error(
                f"Range calculation failed: {e}",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "primary_method": primary_method,
                },
                exc_info=True,
            )
            # Return fallback range
            return {
                "equity_value_low": Decimal("0.0"),
                "equity_value_mid": Decimal("0.0"),
                "equity_value_high": Decimal("0.0"),
                "range_methodology": "fallback",
                "error": str(e),
            }
