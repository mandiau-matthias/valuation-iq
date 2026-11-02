"""
Summary Generation Coordinator

Handles summary and methodology notes generation logic.
Extracted from synthesizer.py to improve modularity.

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive summary generation
- Detailed logging
"""

from decimal import Decimal
from typing import Optional

from src.domain.models import DCFResult, FinancialData, IndustryBenchmarks, MarketContext, MultiplesResult
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SummaryGenerationCoordinator:
    """
    Coordinates summary and methodology notes generation logic.
    
    Responsibilities:
    - Generate valuation summary
    - Generate methodology notes
    - Format human-readable text
    """
    
    def __init__(
        self,
        financial_data: FinancialData,
        market_context: MarketContext,
        industry_benchmarks: IndustryBenchmarks,
    ):
        """
        Initialize summary generation coordinator.
        
        Args:
            financial_data: Company financial data
            market_context: Market and economic context
            industry_benchmarks: Industry benchmarks
        """
        self.logger = logger
        self.financial_data = financial_data
        self.market_context = market_context
        self.industry_benchmarks = industry_benchmarks
    
    def generate_valuation_summary(
        self,
        equity_value_low: Decimal,
        equity_value_mid: Decimal,
        equity_value_high: Decimal,
        dcf_result: Optional[DCFResult],
        multiples_result: Optional[MultiplesResult],
    ) -> str:
        """
        Generate human-readable valuation summary.
        
        Args:
            equity_value_low: Low equity value
            equity_value_mid: Mid equity value
            equity_value_high: High equity value
            dcf_result: DCF calculation results
            multiples_result: Multiples calculation results
            
        Returns:
            Human-readable valuation summary string
        """
        summary_parts = []
        
        equity_mid_decimal = to_decimal(equity_value_mid)
        equity_low_decimal = to_decimal(equity_value_low)
        equity_high_decimal = to_decimal(equity_value_high)
        
        summary_parts.append(
            f"Based on a comprehensive analysis using multiple valuation methodologies, "
            f"the estimated equity value for {self.financial_data.company_name} is "
            f"\u20AC{from_decimal(equity_mid_decimal, precision=0):,.0f}, with a valuation range of "
            f"\u20AC{from_decimal(equity_low_decimal, precision=0):,.0f} to \u20AC{from_decimal(equity_high_decimal, precision=0):,.0f}."
        )
        
        if dcf_result and multiples_result:
            multiples_value = getattr(multiples_result, "adjusted_equity_value", None)
            if multiples_value is not None:
                summary_parts.append(
                    f"\n\nThe DCF methodology yielded an equity value of \u20AC{dcf_result.equity_value:,.0f}, "
                    f"while market multiples analysis indicated \u20AC{multiples_value:,.0f}."
                )
            else:
                self.logger.warning(
                    "multiples_result.adjusted_equity_value missing, skipping from summary"
                )
        
        # Add context about company performance
        ebitda_margin = (
            self.financial_data.current_year.ebitda / self.financial_data.current_year.revenue
        )
        summary_parts.append(
            f"\n\nThe company generates \u20AC{self.financial_data.latest_revenue:,.0f} in annual revenue "
            f"with an EBITDA margin of {ebitda_margin:.1%}."
        )
        
        return "".join(summary_parts)
    
    def generate_methodology_notes(
        self,
        dcf_result: Optional[DCFResult],
        multiples_result: Optional[MultiplesResult],
        dcf_weight: Decimal,
        multiples_weight: Decimal,
    ) -> str:
        """
        Generate notes on methodology and assumptions.
        
        Args:
            dcf_result: DCF calculation results
            multiples_result: Multiples calculation results
            dcf_weight: Weight for DCF methodology
            multiples_weight: Weight for multiples methodology
            
        Returns:
            Methodology notes string
        """
        notes = []
        
        notes.append("**Valuation Methodologies:**\n")
        
        dcf_weight_decimal = to_decimal(dcf_weight)
        multiples_weight_decimal = to_decimal(multiples_weight)
        
        if dcf_result:
            notes.append(
                f"- **DCF Analysis ({from_decimal(dcf_weight_decimal * Decimal('100'), precision=0):.0f}% weight)**: "
                f"10-year cash flow projection with WACC of {dcf_result.wacc:.2%} "
                f"and terminal growth rate of {dcf_result.terminal_growth_rate:.2%}. "
                f"Confidence: {(dcf_result.confidence.value.upper() if hasattr(dcf_result.confidence, 'value') else str(dcf_result.confidence).upper())}"
            )
        
        if multiples_result:
            comparables_count = getattr(multiples_result, "comparables_count", 0)
            ebitda_multiple = getattr(multiples_result, "ebitda_multiple", None)
            revenue_multiple = getattr(multiples_result, "revenue_multiple", None)
            confidence = getattr(multiples_result, "confidence", None)
            
            if (
                ebitda_multiple is not None
                and revenue_multiple is not None
                and confidence is not None
            ):
                notes.append(
                    f"\n- **Market Multiples ({from_decimal(multiples_weight_decimal * Decimal('100'), precision=0):.0f}% weight)**: "
                    f"Based on {comparables_count} comparable companies "
                    f"or industry benchmarks. Applied EV/EBITDA of {ebitda_multiple:.1f}x "
                    f"and EV/Revenue of {revenue_multiple:.1f}x. "
                    f"Confidence: {(confidence.value.upper() if hasattr(confidence, 'value') else str(confidence).upper())}"
                )
            else:
                self.logger.warning("multiples_result missing required attributes for methodology notes")
        
        notes.append(
            "\n\n**Key Assumptions:**\n"
            f"- Risk-free rate: {self.market_context.government_bond_yield:.2%}\n"
            f"- Long-term GDP growth: {self.market_context.long_term_gdp_growth:.2%}\n"
            f"- Industry average tax rate: {self.industry_benchmarks.avg_tax_rate:.1%}"
        )
        
        notes.append(
            "\n\n**Important Notes:**\n"
            "- This valuation is based on historical financial data and forward-looking assumptions.\n"
            "- Actual transaction value may vary based on market conditions, buyer synergies, and negotiation.\n"
            "- This analysis should be used as a starting point for valuation discussions."
        )
        
        return "".join(notes)

