"""
Step 2 Validator

Validates data quality and step results.
"""

from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from src.domain.data_quality_assessor import DataQualityAssessor
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.valuation_logger import ValuationLogger

from ...base_step import StepStatus


class Step2Validator:
    """Validates data quality and step results."""

    def __init__(self, logger: ValuationLogger):
        """
        Initialize the validator.

        Args:
            logger: Logger instance
        """
        self.logger = logger

    def validate_step_0_data(
        self, step0_output: Any, previous_results: Dict[int, Any]
    ) -> Tuple[Optional[Dict[str, Any]], bool]:
        """
        Validate Step 0 data and handle failures gracefully.

        Args:
            step0_output: Step 0 output object
            previous_results: Dictionary of previous step results

        Returns:
            Tuple of (step0_result_dict, step_0_failed):
            - step0_result_dict: Step 0 result dictionary or fallback
            - step_0_failed: Whether Step 0 failed
        """
        step_0_failed = False
        step0_result = None

        # Check if Step 0 exists in previous_results
        if 0 in previous_results:
            step_0_output = previous_results[0]
            if hasattr(step_0_output, "status") and step_0_output.status == StepStatus.FAILED:
                step_0_failed = True
                self.logger.warning(
                    "⚠️ Step 2: Step 0 failed, using fallback quality score",
                    extra={
                        "step_number": 2,
                        "step_0_status": step_0_output.status.value,
                        "step_0_error": getattr(step_0_output, "error", None),
                        "fallback_quality_score": 50,
                        "note": "Step 2 will continue with fallback quality assumptions",
                    },
                )
                # Create fallback Step 0 result
                step0_result = {
                    "quality_score": 50,  # Default fallback score
                    "dcf_eligible": False,
                    "multiples_method": "primary",
                    "dimension_scores": {},
                    "warnings": [
                        {
                            "severity": "high",
                            "message": "Step 0 failed, using fallback quality score",
                        }
                    ],
                    "recommendations": [],
                }
            elif hasattr(step_0_output, "result"):
                step0_result = (
                    step_0_output.result if isinstance(step_0_output.result, dict) else None
                )

        # If Step 0 exists but result is empty - use fallback
        if not step0_result:
            step0_result = {
                "quality_score": 50,
                "dcf_eligible": False,
                "multiples_method": "primary",
                "dimension_scores": {},
                "warnings": [],
                "recommendations": [],
            }

        return step0_result, step_0_failed

    def validate_step_1_data(
        self, step1_result: Optional[Dict[str, Any]], request: Any
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Validate Step 1 data.

        Args:
            step1_result: Step 1 result dictionary
            request: The valuation request

        Returns:
            Tuple of (is_valid, validated_result):
            - is_valid: Whether Step 1 data is valid
            - validated_result: Validated result or None if invalid
        """
        if not step1_result:
            return False, None

        # Check if revenue is present and positive
        revenue = step1_result.get("revenue")
        if not revenue or revenue <= 0:
            return False, None

        return True, step1_result

    def validate_quality_checkpoint(
        self, request: Any, previous_results: Dict[int, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Validate data quality hasn't degraded since Step 0.

        This is a checkpoint to ensure data quality remains consistent
        throughout the valuation flow, especially at key decision points.

        Args:
            request: The valuation request
            previous_results: Dictionary of previous step results

        Returns:
            Dict with quality_checkpoint results or None if Step 0 not available
        """
        # Get Step 0 baseline
        step0_result = previous_results.get(0)
        if not step0_result or step0_result.status != StepStatus.COMPLETED:
            return None

        baseline_score = step0_result.result.get("quality_score")
        if baseline_score is None:
            return None

        # Re-assess quality at checkpoint
        quality_assessor = DataQualityAssessor()
        checkpoint_assessment = quality_assessor.assess_quality(
            request, baseline_score=baseline_score
        )

        current_score = checkpoint_assessment["quality_score"]
        degradation = checkpoint_assessment.get("degradation", 0)

        # Log if significant degradation detected
        if degradation and degradation > 5:
            self.logger.warning(
                f"⚠️ Data quality degraded by {degradation} points at Step 2 checkpoint",
                extra={
                    "baseline_score": baseline_score,
                    "current_score": current_score,
                    "degradation": degradation,
                },
            )

        return {
            "baseline_score": baseline_score,
            "current_score": current_score,
            "degradation": degradation,
            "status": "degraded" if degradation and degradation > 5 else "stable",
            "warnings_count": len(checkpoint_assessment.get("warnings", [])),
        }
