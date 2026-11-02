"""
Result Validator for Step 0 Data Quality

Validates quality assessment results and dimension scores.
"""

from decimal import Decimal
from typing import Any, Dict

from src.utils.logging import get_logger

logger = get_logger(__name__)


class ResultValidator:
    """Validates quality assessment results and dimension scores."""

    REQUIRED_DIMENSIONS = ["completeness", "validity", "consistency", "accuracy", "timeliness"]
    REQUIRED_KEYS = ["quality_score", "dimension_scores", "warnings", "recommendations"]
    VALID_SEVERITIES = ["critical", "high", "medium", "low"]

    def validate_quality_assessment(
        self, quality_assessment: Any, step_number: int = 0
    ) -> Dict[str, Any]:
        """
        Validate quality assessment structure and ensure all required keys exist.

        Args:
            quality_assessment: The quality assessment result
            step_number: The step number (default: 0)

        Returns:
            Validated quality assessment dictionary
        """
        # Validate assess_quality() return structure
        if not isinstance(quality_assessment, dict):
            logger.error(
                "❌ CRITICAL: Step 0 assess_quality() returned non-dict, using fallback",
                extra={
                    "step_number": step_number,
                    "return_type": type(quality_assessment).__name__,
                },
            )
            quality_assessment = self._create_fallback_assessment()

        # Ensure all required keys exist
        missing_keys = [key for key in self.REQUIRED_KEYS if key not in quality_assessment]
        if missing_keys:
            logger.error(
                "❌ CRITICAL: Step 0 assess_quality() missing required keys, adding defaults",
                extra={
                    "step_number": step_number,
                    "missing_keys": missing_keys,
                    "existing_keys": list(quality_assessment.keys()),
                },
            )
            for key in missing_keys:
                if key == "quality_score":
                    quality_assessment[key] = 50
                elif key == "dimension_scores":
                    quality_assessment[key] = {
                        "completeness": 10,
                        "validity": 10,
                        "consistency": 10,
                        "accuracy": 10,
                        "timeliness": 10,
                    }
                elif key == "warnings":
                    quality_assessment[key] = []
                elif key == "recommendations":
                    quality_assessment[key] = []

        return quality_assessment

    def validate_quality_score(self, quality_score: Any, step_number: int = 0) -> int:
        """
        Validate and normalize quality score.

        Args:
            quality_score: The quality score value
            step_number: The step number (default: 0)

        Returns:
            Validated quality score as integer (0-100)
        """
        if quality_score is None:
            logger.warning(
                "⚠️ Step 0: quality_score is None from assessor, defaulting to 0",
                extra={"step_number": step_number},
            )
            return 0

        if not isinstance(quality_score, (int, float, Decimal)):
            logger.warning(
                "⚠️ Step 0: quality_score is invalid type, defaulting to 0",
                extra={
                    "step_number": step_number,
                    "quality_score": quality_score,
                    "quality_score_type": type(quality_score).__name__,
                },
            )
            return 0

        score = int(quality_score)
        clamped = max(0, min(100, score))
        if clamped != score:
            logger.warning(
                "⚠️ Step 0: quality_score out of range, clamping to 0-100",
                extra={
                    "step_number": step_number,
                    "original_score": score,
                    "clamped_score": clamped,
                },
            )
        return clamped

    def validate_dimension_scores(
        self, dimension_scores: Any, step_number: int = 0
    ) -> Dict[str, int]:
        """
        Validate and normalize dimension scores.

        Args:
            dimension_scores: The dimension scores dictionary
            step_number: The step number (default: 0)

        Returns:
            Validated dimension scores dictionary
        """
        # Ensure dimension_scores is a dict
        if not isinstance(dimension_scores, dict):
            logger.warning(
                "⚠️ Step 0: dimension_scores is not a dict, defaulting to empty dict",
                extra={
                    "step_number": step_number,
                    "dimension_scores_type": type(dimension_scores).__name__,
                },
            )
            dimension_scores = {}

        # Verify dimension_scores contains all 5 dimensions
        missing_dimensions = [
            dim for dim in self.REQUIRED_DIMENSIONS if dim not in dimension_scores
        ]

        if missing_dimensions:
            logger.warning(
                "⚠️ Step 0: dimension_scores missing required dimensions, adding defaults",
                extra={
                    "step_number": step_number,
                    "missing_dimensions": missing_dimensions,
                    "existing_dimensions": list(dimension_scores.keys()),
                },
            )
            # Add missing dimensions with default scores
            for dim in missing_dimensions:
                dimension_scores[dim] = 10  # Default score per dimension

        # Ensure all dimension values are integers 0-100
        for dim in self.REQUIRED_DIMENSIONS:
            if dim in dimension_scores:
                value = dimension_scores[dim]
                if not isinstance(value, (int, float)) or value < 0 or value > 100:
                    logger.warning(
                        f"⚠️ Step 0: dimension_scores['{dim}'] is invalid, defaulting to 10",
                        extra={
                            "step_number": step_number,
                            "dimension": dim,
                            "value": value,
                            "value_type": type(value).__name__,
                        },
                    )
                    dimension_scores[dim] = 10
                else:
                    # Ensure it's an integer
                    dimension_scores[dim] = int(value)

        return dimension_scores

    def validate_warnings(self, warnings: Any, step_number: int = 0) -> list:
        """
        Validate and normalize warnings list.

        Args:
            warnings: The warnings list
            step_number: The step number (default: 0)

        Returns:
            Validated warnings list
        """
        # Verify warnings format
        if not isinstance(warnings, list):
            logger.warning(
                "⚠️ Step 0: warnings is not a list, converting to list",
                extra={"step_number": step_number, "warnings_type": type(warnings).__name__},
            )
            return []

        # Validate each warning is a dict with required fields
        valid_warnings = []
        for i, warning in enumerate(warnings):
            if not isinstance(warning, dict):
                logger.warning(
                    f"⚠️ Step 0: warning[{i}] is not a dict, skipping",
                    extra={
                        "step_number": step_number,
                        "warning_index": i,
                        "warning_type": type(warning).__name__,
                    },
                )
                continue

            # Ensure required fields exist
            if "severity" not in warning:
                warning["severity"] = "medium"  # Default severity
            if "message" not in warning:
                warning["message"] = "Unknown warning"

            # Validate severity value
            if warning["severity"] not in self.VALID_SEVERITIES:
                logger.warning(
                    f"⚠️ Step 0: warning[{i}] has invalid severity, defaulting to 'medium'",
                    extra={
                        "step_number": step_number,
                        "warning_index": i,
                        "invalid_severity": warning["severity"],
                        "valid_severities": self.VALID_SEVERITIES,
                    },
                )
                warning["severity"] = "medium"

            valid_warnings.append(warning)

        return valid_warnings

    def validate_recommendations(self, recommendations: Any, step_number: int = 0) -> list:
        """
        Validate and normalize recommendations list.

        Args:
            recommendations: The recommendations list
            step_number: The step number (default: 0)

        Returns:
            Validated recommendations list
        """
        # Validate recommendations is a list
        if not isinstance(recommendations, list):
            logger.warning(
                "⚠️ Step 0: recommendations is not a list, converting to list",
                extra={
                    "step_number": step_number,
                    "recommendations_type": type(recommendations).__name__,
                },
            )
            return []

        # Ensure all recommendations are strings. The assessor can emit
        # structured recommendation dictionaries; preserve the useful fields
        # without logging an avoidable warning for the normal path.
        valid_recommendations = []
        for i, rec in enumerate(recommendations):
            if isinstance(rec, str):
                valid_recommendations.append(rec)
                continue

            if isinstance(rec, dict):
                parts = [
                    str(value)
                    for value in (
                        rec.get("action")
                        or rec.get("recommendation")
                        or rec.get("message"),
                        rec.get("reason"),
                        rec.get("impact"),
                    )
                    if value
                ]
                valid_recommendations.append(" - ".join(parts) if parts else str(rec))
                continue

            logger.debug(
                "Step 0 recommendation is not a string, converting",
                extra={
                    "step_number": step_number,
                    "recommendation_index": i,
                    "recommendation_type": type(rec).__name__,
                },
            )
            valid_recommendations.append(str(rec))

        return valid_recommendations

    def validate_result_dict(
        self, result_dict: Dict[str, Any], step_number: int = 0
    ) -> Dict[str, Any]:
        """
        Validate result dictionary has all required fields.

        Args:
            result_dict: The result dictionary
            step_number: The step number (default: 0)

        Returns:
            Validated result dictionary
        """
        # Ensure result_dict is never empty
        if not result_dict or len(result_dict) == 0:
            logger.error(
                "❌ CRITICAL: Step 0 result_dict is empty, using fallback values",
                extra={
                    "step_number": step_number,
                    "result_dict_size": len(result_dict) if result_dict else 0,
                    "result_dict_keys": list(result_dict.keys()) if result_dict else [],
                },
            )
            return self._create_fallback_result_dict()

        # Validate result_dict has all required fields
        required_fields = [
            "quality_score",
            "dcf_eligible",
            "multiples_method",
            "dimension_scores",
            "warnings",
            "recommendations",
        ]
        missing_fields = [field for field in required_fields if field not in result_dict]
        if missing_fields:
            logger.error(
                "❌ CRITICAL: Step 0 result_dict missing required fields, adding fallback values",
                extra={
                    "step_number": step_number,
                    "missing_fields": missing_fields,
                    "existing_fields": list(result_dict.keys()),
                },
            )
            # Add missing fields with fallback values
            if "quality_score" not in result_dict:
                result_dict["quality_score"] = 50
            if "dcf_eligible" not in result_dict:
                result_dict["dcf_eligible"] = False
            if "multiples_method" not in result_dict:
                result_dict["multiples_method"] = "primary"
            if "dimension_scores" not in result_dict:
                result_dict["dimension_scores"] = {}
            if "warnings" not in result_dict:
                result_dict["warnings"] = []
            if "recommendations" not in result_dict:
                result_dict["recommendations"] = []

        return result_dict

    def _create_fallback_assessment(self) -> Dict[str, Any]:
        """Create a fallback quality assessment."""
        return {
            "quality_score": 50,
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
                    "message": "Quality assessment returned invalid format",
                    "category": "system_error",
                }
            ],
            "recommendations": [],
        }

    def _create_fallback_result_dict(self) -> Dict[str, Any]:
        """Create a fallback result dictionary."""
        return {
            "quality_score": 50,
            "dcf_eligible": False,
            "multiples_method": "primary",
            "dimension_scores": {
                "completeness": 10,
                "validity": 10,
                "consistency": 10,
                "accuracy": 10,
                "timeliness": 10,
            },
            "warnings": [{"severity": "critical", "message": "Step 0 result_dict was empty"}],
            "recommendations": [],
            "score_breakdown": {},
        }
