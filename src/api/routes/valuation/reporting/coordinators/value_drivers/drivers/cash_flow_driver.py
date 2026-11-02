"""
Cash Flow Driver Extractor

Extracts cash flow-related value drivers.
"""

from collections.abc import Mapping
from decimal import Decimal
from typing import List

from .decimal_coercion import as_decimal


class CashFlowDriverExtractor:
    """Extracts cash flow value drivers."""

    MILLION_THRESHOLD = 1_000_000
    THOUSAND_THRESHOLD = 1_000

    @staticmethod
    def extract(financial_metrics: Mapping[str, object]) -> List[str]:
        """
        Extract cash flow drivers (e.g., positive FCF).

        Args:
            financial_metrics: Financial metrics dictionary

        Returns:
            List of cash flow driver descriptions
        """
        drivers: List[str] = []

        fcf_raw = financial_metrics.get("free_cash_flow")
        if fcf_raw is None:
            fcf_raw = financial_metrics.get("fcf")
        fcf = as_decimal(fcf_raw)
        if fcf is None or fcf <= 0:
            return drivers

        if fcf >= Decimal(str(CashFlowDriverExtractor.MILLION_THRESHOLD)):
            drivers.append(
                f"Positive free cash flow generation (€{fcf/CashFlowDriverExtractor.MILLION_THRESHOLD:.1f}M annually)"
            )
        else:
            drivers.append(
                f"Positive free cash flow generation (€{fcf/CashFlowDriverExtractor.THOUSAND_THRESHOLD:.0f}K annually)"
            )

        return drivers
