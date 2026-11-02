"""
Confidence Calculator for Step 11 Synthesis

Handles confidence score extraction and breakdown.
"""

from decimal import Decimal
from typing import Any, Dict

from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

from ...base_step import StepStatus

logger = get_logger(__name__)


class ConfidenceCalculator:
    """
    Calculator for confidence score operations.

    Responsibilities:
    - Extract confidence breakdown from previous steps
    - Aggregate confidence factors
    - Map confidence scores to levels
    """

    def __init__(self):
        """Initialize confidence calculator."""
        pass

    def extract_confidence(self, previous_results: Dict[int, Any]) -> Dict[str, Any]:
        """
        Extract confidence breakdown from previous steps.

        Args:
            previous_results: Results from previous steps

        Returns:
            Confidence breakdown dictionary
        """
        step9 = previous_results.get(9)  # Step 9 is now confidence score (was step 8)
        step0 = previous_results.get(0)  # Step 0 is data quality assessment

        confidence_breakdown = {}

        # Extract from Step 9 (confidence score)
        if step9 and step9.status == StepStatus.COMPLETED:
            factor_scores = step9.result.get("factor_scores", {})
            confidence_breakdown.update(
                {
                    "overall_score": step9.result.get("overall_confidence_score"),
                    "level": step9.result.get("confidence_level"),
                    "factors": factor_scores,
                    # CRITICAL FIX: Also include individual factor scores at top level for easier frontend access
                    "data_quality": factor_scores.get("data_quality", 0),
                    "historical_data": factor_scores.get("historical_data", 0),
                    "methodology_agreement": factor_scores.get("methodology_agreement", 0),
                    "industry_benchmarks": factor_scores.get("industry_benchmarks", 0),
                    "company_profile": factor_scores.get("company_profile", 0),
                    "market_conditions": factor_scores.get("market_conditions", 0),
                    "geographic_data": factor_scores.get("geographic_data", 0),
                    "business_model_clarity": factor_scores.get("business_model_clarity", 0),
                }
            )

        # CRITICAL FIX: Include Step 0 quality_score as data_quality for frontend extraction
        if step0 and step0.status == StepStatus.COMPLETED:
            quality_score = step0.result.get("quality_score", 0)
            dimension_scores = step0.result.get("dimension_scores", {})

            # DEBUG: fires twice per Step 11 because confidence breakdown
            # is built once for the step result and once for the transparency report.
            logger.debug(
                "✅ Step 11: Including Step 0 quality_score in confidence_breakdown",
                extra={
                    "step_number": 11,
                    "quality_score": quality_score,
                    "has_dimension_scores": bool(dimension_scores),
                    "dimension_scores_keys": (
                        list(dimension_scores.keys()) if isinstance(dimension_scores, dict) else []
                    ),
                },
            )

            confidence_breakdown["data_quality"] = quality_score

            # Also include dimension scores if available
            if dimension_scores and isinstance(dimension_scores, dict):
                confidence_breakdown["data_quality_dimensions"] = dimension_scores

        return confidence_breakdown if confidence_breakdown else {}
