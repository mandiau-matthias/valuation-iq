"""
Confidence and Quality Calculator for Comprehensive Valuation Orchestrator

Handles confidence score and quality rating calculation.
"""

from decimal import Decimal
from typing import Any, Dict, Tuple

from src.api.schemas import ValuationRequest
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.valuation_logger import ValuationLogger


class ConfidenceQualityCalculator:
    """Calculates confidence scores and quality ratings."""

    def __init__(self, confidence_scorer, quality_assessor, logger: ValuationLogger):
        """
        Initialize the confidence and quality calculator.

        Args:
            confidence_scorer: Confidence scorer instance
            quality_assessor: Quality assessor instance
            logger: Logger instance
        """
        self.confidence_scorer = confidence_scorer
        self.quality_assessor = quality_assessor
        self.logger = logger

    async def calculate_confidence_and_quality(
        self, request: ValuationRequest, detailed_results: Dict[str, Any]
    ) -> Tuple[float, Any, str]:
        """
        Calculate confidence score and quality rating.

        Prefers Step 9's 8-factor confidence model when available, falling back
        to the 4-factor comprehensive scorer otherwise.

        Args:
            request: The valuation request
            detailed_results: The detailed valuation results

        Returns:
            Tuple of (confidence_score, quality_rating, confidence_level):
            - confidence_score: Confidence score (Decimal('0.0')-Decimal('1.0'))
            - quality_rating: Quality rating object
            - confidence_level: Confidence level string
        """
        # Prefer Step 9's rigorous 8-factor model (0-100 scale) when available
        step_9_score = self._extract_step_9_confidence(detailed_results)
        if step_9_score is not None:
            confidence_score = Decimal(str(step_9_score)) / Decimal("100")
            self.logger.info(
                f"🎯 Confidence: {confidence_score*100:.0f}% (from Step 9 eight-factor model)",
            )
        else:
            confidence_score = await self.confidence_scorer.calculate_comprehensive_score(
                request, detailed_results
            )
            self.logger.info(f"🎯 Confidence: {confidence_score*100:.0f}% (from comprehensive scorer fallback)")

        # Determine quality rating (delegated to QualityAssessor)
        quality_rating = await self.quality_assessor.determine_quality_rating(
            request, detailed_results, confidence_score
        )

        # DEBUG: duplicate of "✅ Quality rating: …" already logged by QualityAssessor.
        self.logger.debug(f"⭐ Quality: {quality_rating.value}")

        # Map confidence to level
        confidence_level = self.confidence_scorer.map_score_to_level(confidence_score)

        return confidence_score, quality_rating, confidence_level

    def _extract_step_9_confidence(self, detailed_results: Dict[str, Any]):
        """Extract Step 9's overall_confidence_score from multiples step results."""
        try:
            multiples = detailed_results.get("multiples_valuation", {})
            if not isinstance(multiples, dict):
                return None
            step_results = multiples.get("_step_results", {})
            if not isinstance(step_results, dict):
                return None
            step_9_output = step_results.get(9)
            if step_9_output is None or not hasattr(step_9_output, "result"):
                return None
            result = step_9_output.result
            if not isinstance(result, dict):
                return None
            score = result.get("overall_confidence_score")
            if score is not None and isinstance(score, (int, float, Decimal)):
                return int(score)
            return None
        except Exception:
            return None
