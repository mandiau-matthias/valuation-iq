"""
Step 2.5 Result Builder

Builds StepOutput for EBITDA normalization results.
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from src.utils.decimal_helpers import from_decimal
from src.utils.logging import get_logger

from ...base_step import StepOutput, StepStatus

logger = get_logger(__name__)


class Step25ResultBuilder:
    """Builds result output for Step 2.5."""
    
    def __init__(self, step_name: str):
        """Initialize builder with step name."""
        self.step_name = step_name
    
    def build_success_output(
        self,
        quality_result: Dict[str, Any],
        execution_time_ms: Decimal,
        correlation_id: Optional[str] = None,
        transparency_metadata: Optional[Dict[str, Any]] = None
    ) -> StepOutput:
        """
        Build successful quality calibration output (MULTIPLE-FIRST).
        
        Args:
            quality_result: Result from quality calculator
            execution_time_ms: Execution time in milliseconds
            correlation_id: Correlation ID for tracking
            transparency_metadata: Optional metadata about EBITDA source for transparency
            
        Returns:
            StepOutput with quality multiple adjustment data
        """
        # Extract key values
        quality_multiple_adjustment = quality_result["quality_multiple_adjustment"]
        quality_analysis = quality_result["quality_analysis"]
        
        # Extract base_multiple from quality_result if available
        base_multiple = quality_result.get("base_multiple", 0)
        calibrated_multiple = from_decimal(base_multiple) + quality_multiple_adjustment if base_multiple else quality_multiple_adjustment
        
        result_dict = {
            # MULTIPLE-FIRST: Core output is adjustment to multiple, NOT normalized EBITDA
            "quality_multiple_adjustment": quality_multiple_adjustment,
            
            # EBITDA BRIDGE: Transparency data for waterfall bridge
            "reported_ebitda": quality_result.get("reported_ebitda"),
            "normalized_ebitda": quality_result.get("normalized_ebitda"),
            "ebitda_adjustments": quality_result.get("ebitda_adjustments", []),

            # POST-DEAL LENS: actual + market-rate metadata, used by
            # `orchestration/builders/post_deal_swap.py` to compute the
            # Post-Deal equity value emitted on the response.
            "owner_compensation_metadata": quality_result.get(
                "owner_compensation_metadata"
            ),
            
            # CRITICAL TRANSPARENCY: Add current year EBITDA for audit trail
            "current_year_ebitda": transparency_metadata.get("current_year_ebitda") if transparency_metadata else None,
            "using_weighted_ebitda": transparency_metadata.get("using_weighted_from_step1") if transparency_metadata else False,
            "ebitda_source_explanation": transparency_metadata.get("ebitda_source_explanation") if transparency_metadata else None,
            
            # PHASE 3: Multiple tracking for waterfall display
            "multiple_before": from_decimal(base_multiple) if base_multiple else None,
            "multiple_adjustment": quality_multiple_adjustment,
            "multiple_after": calibrated_multiple,
            "adjustment_percentage": (quality_multiple_adjustment / from_decimal(base_multiple) * 100) if base_multiple and base_multiple > 0 else 0,
            
            # Quality analysis summary
            "quality_analysis": quality_analysis,
            "earnings_quality_score": quality_analysis["earnings_quality_score"],
            
            # Quality factors details
            "quality_factors": quality_result["quality_factors"],
            "num_quality_factors": len(quality_result["quality_factors"]),
            
            # Margin analysis (for reference/display only)
            "margin_analysis": quality_result["margin_analysis"],
            
            # ACADEMIC SOURCES: SME-specific research backing quality calibration
            "academic_sources": quality_result.get("academic_sources", []),
            "methodology_foundation": quality_result.get("methodology_foundation", {}),
            
            # Metadata
            "year": quality_result["year"],
            "confidence_score": quality_result["confidence_score"],
            "rationale": quality_result["rationale"],
            
            # Quality flags
            "quality_of_earnings_flag": quality_result["margin_analysis"]["quality_of_earnings_flag"],
            "volatility_level": quality_result["margin_analysis"]["volatility_level"],
            
            # Correlation tracking
            "correlation_id": correlation_id,
        }
        
        metadata = {
            "execution_time_ms": from_decimal(execution_time_ms),
            "quality_factors_detected": len(quality_result["quality_factors"]),
            "quality_confidence": quality_result["confidence_score"],
            "methodology": "Multiple-first approach (Big 4 standard)",
        }
        
        # DEBUG: dup of "[STEP-2.5-SUMMARY] Multiple Calibration Complete".
        logger.debug(
            "✅ Step 2.5 quality calibration result built successfully (MULTIPLE-FIRST)",
            extra={
                "quality_multiple_adjustment": quality_multiple_adjustment,
                "earnings_quality_score": quality_analysis["earnings_quality_score"],
                "num_quality_factors": len(quality_result["quality_factors"]),
                "volatility_level": quality_result["margin_analysis"]["volatility_level"],
                "methodology": "No double-counting - adjustments to multiple only"
            }
        )
        
        return StepOutput(
            step_number=2,
            step_name=self.step_name,
            status=StepStatus.COMPLETED,
            result=result_dict,
            metadata=metadata
        )
