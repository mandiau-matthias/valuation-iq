"""
Growth Driver Extractor

Extracts growth-related value drivers.
"""

from collections.abc import Mapping
from decimal import Decimal
from typing import List

from .decimal_coercion import as_decimal


class GrowthDriverExtractor:
    """Extracts growth value drivers."""

    @staticmethod
    def extract(financial_metrics: Mapping[str, object]) -> List[str]:
        """
        Extract growth drivers (e.g., revenue growth >20%).

        Args:
            financial_metrics: Financial metrics dictionary

        Returns:
            List of growth driver descriptions
        """
        drivers: List[str] = []

        revenue_growth = financial_metrics.get("revenue_growth")
        if revenue_growth is None:
            revenue_growth = financial_metrics.get("revenue_cagr_3y")
        growth_value = as_decimal(revenue_growth)
        if growth_value is None:
            return drivers

        is_percentage = abs(growth_value) > Decimal("1.0")
        threshold_decimal = Decimal("0.20")
        threshold_percentage = Decimal("20.0")

        if (is_percentage and growth_value > threshold_percentage) or (
            not is_percentage and growth_value > threshold_decimal
        ):
            if is_percentage:
                drivers.append(f"Robust revenue growth of {growth_value:.1f}% YoY")
            else:
                drivers.append(f"Robust revenue growth of {growth_value:.1%} YoY")

        return drivers
