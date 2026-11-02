"""
Summary Generation Coordinator

Handles summary text generation logic.
Extracted from summary_generator.py to improve modularity.

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive summary generation
- Detailed logging
"""

from typing import Any, Dict

from src.api.schemas import ValuationRequest
from src.utils.core import format_currency
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SummaryGenerationCoordinator:
    """
    Coordinates summary text generation logic.
    
    Responsibilities:
    - Generate valuation summary text
    - Format currency values
    - Add profitability context
    """
    
    def __init__(self, logger_instance=None):
        """
        Initialize summary generation coordinator.
        
        Args:
            logger_instance: Logger instance (optional)
        """
        self.logger = logger_instance or logger
    
    def generate_summary(self, request: ValuationRequest, results: Dict[str, Any]) -> str:
        """
        Generate valuation summary.

        Args:
            request: Valuation request
            results: Valuation results

        Returns:
            Summary text
        """
        try:
            self.logger.debug(
                "📝 Generating valuation summary", extra={"company": request.company_name}
            )

            equity_value = results.get("equity_value_mid", results.get("equity_value", 0))
            methodology = results.get("methodology", "DCF")

            # Use unified utility with smart formatting (M/K suffixes)
            formatted_value = format_currency(
                equity_value, currency="EUR", use_smart_formatting=True
            )

            summary = (
                f"Based on the {methodology} methodology, {request.company_name} "
                f"has an estimated equity value of {formatted_value}. "
            )

            # Add profitability context
            if request.current_year_data.ebitda and request.current_year_data.revenue:
                margin = request.current_year_data.ebitda / request.current_year_data.revenue
                if margin > 0.2:
                    summary += "The company demonstrates strong profitability margins. "
                elif margin > 0:
                    summary += "The company shows moderate profitability. "
                else:
                    summary += "The company is currently operating at a loss. "

            self.logger.debug(
                "✅ Summary generated", extra={"length": len(summary), "methodology": methodology}
            )

            return summary

        except Exception as e:
            self.logger.error(
                f"❌ Summary generation failed: {e}",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            return f"Valuation analysis for {request.company_name}"

