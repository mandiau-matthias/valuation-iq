"""
Step 11 Output Builder

Builds StepOutput for Step 11 fallback results.
"""

from decimal import Decimal
from typing import Any, Dict

from src.api.routes.valuation.steps.base_step import StepOutput, StepStatus
from .spread_calculator import SpreadCalculator


class Step11OutputBuilder:
    """Builds StepOutput for Step 11 fallback."""
    
    @staticmethod
    def build_success(
        valuation_low: Decimal,
        valuation_mid: Decimal,
        valuation_high: Decimal,
        confidence_score: int,
        previous_results: Dict[int, StepOutput],
    ) -> StepOutput:
        """
        Build successful StepOutput.
        
        Args:
            valuation_low: Low valuation
            valuation_mid: Mid valuation
            valuation_high: High valuation
            confidence_score: Confidence score
            previous_results: Previous step results
            
        Returns:
            StepOutput with COMPLETED status
        """
        confidence_level = SpreadCalculator.get_confidence_level(confidence_score)
        equity_source = Step11OutputBuilder._determine_equity_source(previous_results)
        
        return StepOutput(
            step_number=11,
            step_name="Final Valuation Range",
            status=StepStatus.COMPLETED,
            result={
                "valuation_low": valuation_low,
                "valuation_mid": valuation_mid,
                "valuation_high": valuation_high,
                "confidence_score": confidence_score,
                "confidence_level": confidence_level,
                "methodology_statement": "Valuation completed using fallback logic due to processing constraints",
                "fallback_mode": True,
                "error_recovered": True,
            },
            metadata={
                "fallback_used": True,
                "fallback_reason": "Step 11 normal execution unavailable or failed",
                "fallback_methodology": "Confidence-based spread from Step 7/8 equity values",
                "equity_source": equity_source,
            },
            execution_time_ms=Decimal("0.0"),
        )
    
    @staticmethod
    def build_emergency(
        valuation_low: Decimal,
        valuation_mid: Decimal,
        valuation_high: Decimal,
        error: Exception,
    ) -> StepOutput:
        """
        Build emergency StepOutput (last resort).
        
        Args:
            valuation_low: Low valuation
            valuation_mid: Mid valuation
            valuation_high: High valuation
            error: Exception that occurred
            
        Returns:
            StepOutput with COMPLETED status
        """
        return StepOutput(
            step_number=11,
            step_name="Final Valuation Range",
            status=StepStatus.COMPLETED,
            result={
                "valuation_low": valuation_low,
                "valuation_mid": valuation_mid,
                "valuation_high": valuation_high,
                "confidence_score": 0,
                "confidence_level": "LOW",
                "methodology_statement": "Valuation completed using emergency fallback logic - insufficient data",
                "fallback_mode": True,
                "error_recovered": False,
            },
            metadata={
                "fallback_used": True,
                "fallback_failed": True,
                "error": str(error),
                "error_type": type(error).__name__,
            },
            execution_time_ms=Decimal("0.0"),
        )
    
    @staticmethod
    def _determine_equity_source(previous_results: Dict[int, StepOutput]) -> str:
        """Determine equity source from previous results."""
        step8_output = previous_results.get(8)
        step7_output = previous_results.get(7)
        
        if step8_output and step8_output.status == StepStatus.COMPLETED:
            return "Step 8"
        elif step7_output and step7_output.status == StepStatus.COMPLETED:
            return "Step 7"
        else:
            return "none"

