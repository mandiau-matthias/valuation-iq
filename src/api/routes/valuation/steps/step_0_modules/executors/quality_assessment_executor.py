"""
Quality Assessment Executor for Step 0 Data Quality

Executes quality assessment and handles timeout protection.
"""

import time
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from src.domain.data_quality_assessor import DataQualityAssessor
from src.utils.logging import get_logger

logger = get_logger(__name__)


class QualityAssessmentExecutor:
    """Executes quality assessment with timeout protection."""

    def __init__(self, quality_assessor: DataQualityAssessor):
        """
        Initialize the quality assessment executor.

        Args:
            quality_assessor: The data quality assessor instance
        """
        self.quality_assessor = quality_assessor

    def execute_assessment(
        self, request, step_number: int = 0
    ) -> Tuple[Dict[str, Any], Optional[Decimal], bool]:
        """
        Execute quality assessment with timeout protection.

        Args:
            request: The valuation request object
            step_number: The step number (default: 0)

        Returns:
            Tuple of (quality_assessment, duration, timeout_occurred):
            - quality_assessment: The quality assessment dictionary
            - duration: Duration in seconds, or None if failed
            - timeout_occurred: Whether a timeout occurred
        """
        logger.info(
            "📊 Executing 5-dimension data quality assessment",
            extra={
                "step_number": step_number,
                "dimensions": ["completeness", "validity", "consistency", "accuracy", "timeliness"],
                "assessor_class": self.quality_assessor.__class__.__name__,
                "company_name": getattr(request, "company_name", "N/A"),
            },
        )

        assess_quality_start_time = time.time()
        quality_assessment = None
        assess_quality_duration = None
        timeout_occurred = False

        # Wrap assess_quality call in try/except with timeout protection
        try:
            try:
                quality_assessment = self.quality_assessor.assess_quality(request)
                assess_quality_duration = time.time() - assess_quality_start_time

                # Check if it took too long
                if assess_quality_duration > 5.0:
                    timeout_occurred = True
                    logger.warning(
                        "⚠️ Step 0 assess_quality() took longer than 5 seconds, using result but logging warning",
                        extra={
                            "step_number": step_number,
                            "duration_seconds": round(assess_quality_duration, 3),
                            "threshold_seconds": Decimal("5.0"),
                        },
                    )
            except Exception as assess_error:
                assess_quality_duration = time.time() - assess_quality_start_time
                raise

            # DEBUG: dup of "Data quality assessment complete" emitted by
            # the assessor itself (one extra trailing 'd').
            logger.debug(
                "✅ Data quality assessment completed",
                extra={
                    "step_number": step_number,
                    "assess_quality_duration_seconds": (
                        round(assess_quality_duration, 3) if assess_quality_duration else None
                    ),
                    "timeout_occurred": timeout_occurred,
                    "has_quality_score": (
                        "quality_score" in quality_assessment
                        if isinstance(quality_assessment, dict)
                        else False
                    ),
                    "has_dimension_scores": (
                        "dimension_scores" in quality_assessment
                        if isinstance(quality_assessment, dict)
                        else False
                    ),
                    "has_warnings": (
                        "warnings" in quality_assessment
                        if isinstance(quality_assessment, dict)
                        else False
                    ),
                    "has_recommendations": (
                        "recommendations" in quality_assessment
                        if isinstance(quality_assessment, dict)
                        else False
                    ),
                },
            )

        except Exception as e:
            assess_quality_duration = time.time() - assess_quality_start_time
            logger.error(
                "❌ CRITICAL: Step 0 assess_quality() failed, using fallback assessment",
                extra={
                    "step_number": step_number,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "assessor_class": self.quality_assessor.__class__.__name__,
                    "company_name": getattr(request, "company_name", "N/A"),
                    "business_type_id": getattr(request, "business_type_id", "N/A"),
                    "assess_quality_duration_seconds": round(assess_quality_duration, 3),
                },
                exc_info=True,
            )
            # Return fallback assessment with default quality score
            quality_assessment = {
                "quality_score": 50,  # Default score - allows execution to continue
                "dimension_scores": {
                    "completeness": 10,
                    "validity": 10,
                    "consistency": 10,
                    "accuracy": 10,
                    "timeliness": 10,
                },
                "warnings": [
                    {
                        "severity": "critical",
                        "message": f"Quality assessment failed: {str(e)}",
                        "category": "system_error",
                    }
                ],
                "recommendations": ["Review data quality assessment system"],
            }

        return quality_assessment, assess_quality_duration, timeout_occurred
