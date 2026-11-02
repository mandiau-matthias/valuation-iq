"""
Profitability Driver Extractor

Extracts profitability-related value drivers.
"""

from collections.abc import Mapping
from decimal import Decimal
from typing import List

from .decimal_coercion import as_decimal


class ProfitabilityDriverExtractor:
    """Extracts profitability value drivers."""

    @staticmethod
    def extract(financial_metrics: Mapping[str, object]) -> List[str]:
        """
        Extract profitability drivers (e.g., EBITDA margin >20%).

        Args:
            financial_metrics: Financial metrics dictionary

        Returns:
            List of profitability driver descriptions
        """
        drivers: List[str] = []

        ebitda_margin = financial_metrics.get("ebitda_margin")
        margin_value = as_decimal(ebitda_margin)
        if margin_value is None:
            return drivers

        is_percentage = margin_value > Decimal("1.0")
        threshold_decimal = Decimal("0.20")
        threshold_percentage = Decimal("20.0")

        if (is_percentage and margin_value > threshold_percentage) or (
            not is_percentage and margin_value > threshold_decimal
        ):
            if is_percentage:
                drivers.append(f"Strong profitability with {margin_value:.1f}% EBITDA margin")
            else:
                drivers.append(f"Strong profitability with {margin_value:.1%} EBITDA margin")

        return drivers
