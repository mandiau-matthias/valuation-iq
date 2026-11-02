"""
Equity Value Extractor

Extracts equity value from Step 8, Step 7, or Step 6 EV (as fallback).
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from src.api.routes.valuation.steps.base_step import StepOutput, StepStatus
from src.utils.decimal_helpers import to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class EquityValueExtractor:
    """Extracts equity value from step results."""
    
    @staticmethod
    def extract(previous_results: Dict[int, StepOutput]) -> Optional[Decimal]:
        """
        Extract equity value with priority: Step 8 > Step 7 > Step 6 EV (fallback).
        
        Args:
            previous_results: Results from previous steps
            
        Returns:
            Equity value or None if not found
        """
        step8_output = previous_results.get(8)
        step7_output = previous_results.get(7)
        step6_output = previous_results.get(6)
        
        # Try Step 8 first (ownership-adjusted)
        if step8_output and step8_output.status == StepStatus.COMPLETED:
            equity_value = step8_output.result.get("ownership_adjusted_equity_mid")
            if equity_value:
                return to_decimal(equity_value)
        
        # Fallback to Step 7
        if step7_output and step7_output.status == StepStatus.COMPLETED:
            equity_value = step7_output.result.get("equity_value_mid")
            if equity_value:
                return to_decimal(equity_value)
        
        # CRITICAL FIX: Use Step 6 EV values when Step 7 fails
        if step6_output and step6_output.status == StepStatus.COMPLETED:
            ev_mid = step6_output.result.get("enterprise_value_mid")
            if ev_mid:
                logger.info(
                    "ℹ️ Using Step 6 EV as equity approximation (Step 7 unavailable)",
                    extra={
                        "step6_ev_mid": ev_mid,
                        "step7_status": step7_output.status.value if step7_output else "not_found",
                    },
                )
                return to_decimal(ev_mid)
        
        return None

