"""
Step 9 Result Builder

Builds result dictionaries and metadata for Step 9.
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class Step9ResultBuilder:
    """Builds result dictionaries and metadata for Step 9."""

    def __init__(self, step_name: str):
        """
        Initialize the result builder.

        Args:
            step_name: Step name for StepOutput
        """
        self.step_name = step_name

    def build_result_dict(
        self, overall_score: int, confidence_level: str, scores: Dict[str, int]
    ) -> Dict[str, Any]:
        """
        Build comprehensive result dictionary.

        Args:
            overall_score: Overall confidence score
            confidence_level: Confidence level ('HIGH', 'MEDIUM', 'LOW')
            scores: Dictionary of factor scores

        Returns:
            Result dictionary with both nested and flattened factor scores
        """
        # BANK-GRADE: Include both nested and flattened structures for template compatibility
        result = {
            "output": overall_score,  # CRITICAL: step.output expects this field
            "overall_confidence_score": overall_score,  # Also keep for backward compatibility
            "confidence_level": confidence_level,
            "factor_scores": scores,  # Nested structure for backward compatibility
        }
        
        # Flatten factor scores to top-level for direct template access
        # Templates expect: step.outputs.data_quality, step.outputs.historical_data, etc.
        result.update(scores)
        
        return result

    def build_metadata_dict(
        self,
        step0: Dict[str, Any],
        quality_checkpoint: Optional[Dict[str, Any]],
        size_adjustments: list,
        weighted_contributions: Dict[str, Dict[str, Decimal]],
    ) -> Dict[str, Any]:
        """
        Build metadata dictionary.

        Args:
            step0: Step 0 result dictionary
            quality_checkpoint: Quality checkpoint result (optional)
            size_adjustments: List of size adjustments
            weighted_contributions: Dictionary of weighted contributions

        Returns:
            Metadata dictionary
        """
        quality_warnings = step0.get("warnings", [])
        dimension_scores = step0.get("dimension_scores", {})

        metadata = {
            "methodology": "Big 4 8-factor model",
            "sources": "Damodaran (2012), PwC Valuation Standards",
            "size_adjustments": size_adjustments,
            "data_quality": {
                "score": step0.get("quality_score", 0),
                "dimension_scores": dimension_scores,
                "warnings_count": len(quality_warnings),
                "critical_warnings": len(
                    [w for w in quality_warnings if w.get("severity") == "critical"]
                ),
                "high_warnings": len([w for w in quality_warnings if w.get("severity") == "high"]),
            },
        }

        if quality_checkpoint:
            metadata["quality_checkpoint"] = quality_checkpoint

        return metadata
