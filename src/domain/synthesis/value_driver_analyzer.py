"""
Value Driver Analyzer Module

RESPONSIBILITIES:
- Identify key factors driving business value
- Analyze profitability, growth, financial health

REFACTORING NOTE:
Extracted from synthesizer.py to improve maintainability and reduce file size.
"""

from typing import Any, List, Optional

import numpy as np

from src.domain.models import DCFResult, FinancialMetrics
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ValueDriverAnalyzer:
    """
    Analyzes and identifies value drivers for a business
    """

    def __init__(self):
        """Initialize value driver analyzer"""
        self.logger = logger

    def identify_value_drivers(
        self,
        financial_metrics: FinancialMetrics,
        dcf_result: Optional[DCFResult],
        financial_data: Any,  # FinancialData type
    ) -> List[str]:
        """
        Identify key factors driving business value.

        Args:
            financial_metrics: Financial metrics
            dcf_result: Optional DCF result
            financial_data: Financial data object

        Returns:
            List of value driver descriptions
        """
        drivers = []

        # Strong profitability
        if financial_metrics.ebitda_margin > 0.20:
            drivers.append(
                f"Strong profitability with {financial_metrics.ebitda_margin:.1%} EBITDA margin"
            )

        # Revenue growth
        if financial_metrics.revenue_growth > 0.20:
            drivers.append(f"Robust revenue growth of {financial_metrics.revenue_growth:.1%} YoY")

        # Recurring revenue
        if financial_data.recurring_revenue_percentage > 0.60:
            drivers.append(
                f"High revenue predictability ({financial_data.recurring_revenue_percentage:.0%} recurring)"
            )

        # Financial health - quantitative
        if financial_metrics.financial_health_score >= 75:
            drivers.append(
                f"Excellent financial health and low bankruptcy risk (score: {financial_metrics.financial_health_score:.0f}/100)"
            )

        # Operating leverage - quantitative
        if financial_metrics.debt_to_equity and financial_metrics.debt_to_equity < 1.0:
            drivers.append(
                f"Conservative capital structure with manageable debt levels (debt-to-equity: {financial_metrics.debt_to_equity:.2f})"
            )

        # Strong cash generation
        if dcf_result and dcf_result.fcf_projections:
            avg_fcf = np.mean(dcf_result.fcf_projections[:3])  # First 3 years
            if avg_fcf > 0:
                drivers.append(f"Positive free cash flow generation (\u20AC{avg_fcf:,.0f} annually)")

        # Market position (if available in industry benchmarks) - quantitative
        if financial_data.latest_revenue > 10_000_000:
            drivers.append(
                f"Established market presence with significant scale (\u20AC{financial_data.latest_revenue:,.0f} revenue)"
            )

        return drivers[:5]  # Return top 5 drivers
