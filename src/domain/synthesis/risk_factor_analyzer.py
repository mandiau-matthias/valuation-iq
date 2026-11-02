"""
Risk Factor Analyzer Module

RESPONSIBILITIES:
- Identify key risk factors affecting valuation
- Analyze methodology divergence, profitability, leverage, liquidity

REFACTORING NOTE:
Extracted from synthesizer.py to improve maintainability and reduce file size.
"""

from typing import Any, List, Optional

from src.domain.models import DCFResult, FinancialMetrics, MultiplesResult
from src.utils.logging import get_logger

logger = get_logger(__name__)


class RiskFactorAnalyzer:
    """
    Analyzes and identifies risk factors for a business valuation
    """

    def __init__(self):
        """Initialize risk factor analyzer"""
        self.logger = logger

    def identify_risk_factors(
        self,
        financial_metrics: FinancialMetrics,
        dcf_result: Optional[DCFResult],
        multiples_result: Optional[MultiplesResult],
        financial_data: Any,  # FinancialData type
    ) -> List[str]:
        """
        Identify key risk factors.

        Args:
            financial_metrics: Financial metrics
            dcf_result: Optional DCF result
            multiples_result: Optional Multiples result
            financial_data: Financial data object

        Returns:
            List of risk factor descriptions
        """
        risks = []

        # Methodology divergence (Big 4 best practice: flag disagreement as risk, not range expansion)
        if dcf_result and multiples_result:
            dcf_value = dcf_result.equity_value
            multiples_value = getattr(multiples_result, "adjusted_equity_value", None)
            if multiples_value is not None:
                max_val = max(dcf_value, multiples_value)
                variance = abs(dcf_value - multiples_value) / max_val if max_val > 0 else 0.0

                if variance > 0.30:  # >30% divergence
                    risks.append(
                        f"Methodology divergence: DCF (\u20AC{dcf_value:,.0f}) vs Multiples (\u20AC{multiples_value:,.0f}) "
                        f"indicates valuation uncertainty due to limited comparables or unique business characteristics"
                    )
            else:
                logger.warning(
                    "multiples_result.adjusted_equity_value missing, skipping variance calculation"
                )

        # Profitability concerns - quantitative
        if financial_metrics.ebitda_margin < 0.05:
            risks.append(
                f"Low profitability margins limit valuation multiples (EBITDA margin: {financial_metrics.ebitda_margin:.1%})"
            )
        
        # Unrealistic high margins - quantitative (flags unrealistic inputs)
        # Note: 40% exactly is borderline - flag it as potentially unrealistic
        if financial_metrics.ebitda_margin > 0.40:  # >40% is unrealistic for most industries
            risks.append(
                f"Unrealistic EBITDA margin ({financial_metrics.ebitda_margin:.1%}) suggests data quality issues or exceptional circumstances. "
                f"Typical margins range from 5-30% depending on industry."
            )

        # Negative growth
        if financial_metrics.revenue_growth < 0:
            risks.append(f"Declining revenue ({financial_metrics.revenue_growth:.1%} YoY)")

        # High leverage - quantitative
        if financial_metrics.debt_to_equity and financial_metrics.debt_to_equity > 2.0:
            risks.append(
                f"High leverage increases financial risk (debt-to-equity: {financial_metrics.debt_to_equity:.2f})"
            )

        # Liquidity concerns - quantitative
        if financial_metrics.current_ratio and financial_metrics.current_ratio < 1.0:
            risks.append(
                f"Current ratio below 1.0 ({financial_metrics.current_ratio:.2f}) indicates potential liquidity issues"
            )

        # Limited operating history - quantitative
        if financial_data.operating_history_years < 3:
            risks.append(
                f"Limited operating history ({financial_data.operating_history_years} years) increases valuation uncertainty"
            )

        # Size risk - quantitative
        if financial_data.latest_revenue < 1_000_000:
            risks.append(
                f"Small company size (\u20AC{financial_data.latest_revenue:,.0f} revenue) results in higher risk and lower multiples"
            )

        # Customer concentration (if data available - placeholder)
        # This would require additional data in FinancialData model

        return risks[:5]  # Return top 5 risks
