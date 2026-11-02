"""
Result Builder for Step 0 Data Quality

Builds final result dictionary and StepOutput.
"""

import time
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.utils.logging import get_logger

from ...base_step import StepOutput, StepStatus

logger = get_logger(__name__)


class ResultBuilder:
    """Builds final result dictionary and StepOutput."""

    def __init__(self, step_name: str):
        """
        Initialize the result builder.

        Args:
            step_name: The name of the step (e.g., "Data Quality Assessment")
        """
        self.step_name = step_name

    def build_result(
        self,
        quality_assessment: Dict[str, Any],
        dcf_eligible: bool,
        execution_time_ms: Decimal,
        step_number: int = 0,
    ) -> StepOutput:
        """
        Build a StepOutput from a quality assessment dict.

        Args:
            quality_assessment: The quality assessment dictionary
            dcf_eligible: Whether DCF is eligible
            execution_time_ms: Execution time in milliseconds
            step_number: The step number (default: 0)

        Returns:
            StepOutput object
        """
        result_dict = {
            "quality_score": quality_assessment.get("quality_score", 50),
            "dcf_eligible": dcf_eligible,
            "dimension_scores": quality_assessment.get("dimension_scores", {}),
            "warnings": quality_assessment.get("warnings", []),
            "recommendations": quality_assessment.get("recommendations", []),
        }

        return StepOutput(
            step_number=step_number,
            step_name=self.step_name,
            status=StepStatus.COMPLETED,
            result=result_dict,
            metadata={},
            execution_time_ms=execution_time_ms,
        )

    def build_result_dict(
        self,
        quality_score: int,
        dcf_eligible: bool,
        dcf_exclusion_reason: Optional[str],
        multiples_method: str,
        dimension_scores: Dict[str, int],
        warnings: List[Dict[str, Any]],
        recommendations: List[str],
        score_breakdown: Dict[str, Any],
        quality_level: str,
        sub_calculations: Optional[Dict[str, Any]] = None,
        step_number: int = 0,
    ) -> Dict[str, Any]:
        """
        Build the final result dictionary.

        Args:
            quality_score: The quality score (0-100)
            dcf_eligible: Whether DCF is eligible
            dcf_exclusion_reason: Reason for DCF exclusion if not eligible
            multiples_method: The multiples method ('primary' or 'cross_check')
            dimension_scores: The dimension scores dictionary
            warnings: The warnings list
            recommendations: The recommendations list
            score_breakdown: The score breakdown dictionary
            quality_level: The quality level string
            step_number: The step number (default: 0)

        Returns:
            Result dictionary
        """
        result_dict = {
            "quality_score": int(quality_score),  # Ensure it's an integer
            "dcf_eligible": bool(dcf_eligible),
            "dcf_exclusion_reason": dcf_exclusion_reason,
            "multiples_method": str(multiples_method) if multiples_method else "primary",
            "dimension_scores": dimension_scores if isinstance(dimension_scores, dict) else {},
            "warnings": warnings if isinstance(warnings, list) else [],
            "recommendations": recommendations if isinstance(recommendations, list) else [],
            "score_breakdown": score_breakdown,
            "quality_level": quality_level,
            "sub_calculations": sub_calculations if isinstance(sub_calculations, dict) else {},
        }

        # DEBUG: result_dict shape diagnostic; the EXECUTION COMPLETE exit log
        # in step_0_data_quality already carries the headline.
        logger.debug(
            "📊 Step 0: Result dict structure validated",
            extra={
                "step_number": step_number,
                "result_dict_keys": list(result_dict.keys()),
                "has_quality_score": "quality_score" in result_dict,
                "has_dcf_eligible": "dcf_eligible" in result_dict,
                "has_dcf_exclusion_reason": "dcf_exclusion_reason" in result_dict,
                "has_quality_level": "quality_level" in result_dict,
                "has_dimension_scores": "dimension_scores" in result_dict,
                "dimension_scores_count": len(result_dict.get("dimension_scores", {})),
                "warnings_count": len(result_dict.get("warnings", [])),
                "recommendations_count": len(result_dict.get("recommendations", [])),
            },
        )

        return result_dict

    def build_step_output(
        self,
        result_dict: Dict[str, Any],
        dcf_eligible: bool,
        warnings: List[Dict[str, Any]],
        quality_level: str,
        dcf_exclusion_reason: Optional[str],
        step_total_duration: Decimal,
        assess_quality_duration: Optional[Decimal],
        sub_calculations: Optional[Dict[str, Any]] = None,
        step_number: int = 0,
    ) -> StepOutput:
        """
        Build the final StepOutput.

        Args:
            result_dict: The result dictionary
            dcf_eligible: Whether DCF is eligible
            warnings: The warnings list
            quality_level: The quality level string
            dcf_exclusion_reason: Reason for DCF exclusion if not eligible
            step_total_duration: Total execution duration in seconds
            assess_quality_duration: Quality assessment duration in seconds
            step_number: The step number (default: 0)

        Returns:
            StepOutput object
        """
        # Count warnings by severity
        critical_warnings = [w for w in warnings if w.get("severity") == "critical"]
        high_warnings = [w for w in warnings if w.get("severity") == "high"]
        medium_warnings = [w for w in warnings if w.get("severity") == "medium"]

        output = StepOutput(
            step_number=step_number,
            step_name=self.step_name,
            status=StepStatus.COMPLETED,
            result=result_dict,
            metadata={
                "factors_scored": [
                    "completeness",
                    "validity",
                    "consistency",
                    "accuracy",
                    "timeliness",
                ],
                "methodology_recommendation": (
                    "DCF + Multiples" if dcf_eligible else "Multiples Only"
                ),
                "warnings_summary": {
                    "total": len(warnings),
                    "critical": len(critical_warnings),
                    "high": len(high_warnings),
                    "medium": len(medium_warnings),
                    "low": len(warnings)
                    - len(critical_warnings)
                    - len(high_warnings)
                    - len(medium_warnings),
                },
                "quality_level": quality_level,
                "dcf_exclusion_reason": dcf_exclusion_reason,
                "sub_calculation_keys": sorted(
                    list(sub_calculations.keys()) if isinstance(sub_calculations, dict) else []
                ),
                "execution_duration_seconds": round(step_total_duration, 3),
                "assess_quality_duration_seconds": (
                    round(assess_quality_duration, 3) if assess_quality_duration else None
                ),
            },
        )

        # CRITICAL: Final safety check - ensure status is never FAILED
        if output.status == StepStatus.FAILED:
            logger.error(
                "❌ CRITICAL: Step 0 attempted to return FAILED, converting to COMPLETED with fallback",
                extra={
                    "step_number": step_number,
                    "original_error": getattr(output, "error", None),
                },
            )
            # Convert to COMPLETED with fallback data
            output = StepOutput(
                step_number=step_number,
                step_name=self.step_name,
                status=StepStatus.COMPLETED,  # Force COMPLETED
                result=(
                    output.result
                    if hasattr(output, "result") and output.result
                    else {
                        "quality_score": 50,
                        "dcf_eligible": False,
                        "multiples_method": "primary",
                        "dimension_scores": {},
                        "warnings": [
                            {"severity": "critical", "message": "Step 0 forced to COMPLETED status"}
                        ],
                        "recommendations": [],
                    }
                ),
                metadata={
                    **(output.metadata if hasattr(output, "metadata") else {}),
                    "forced_completed": True,
                },
            )

        return output
