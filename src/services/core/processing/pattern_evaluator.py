from src.utils.exceptions import DataValidationError

"""
Pattern Evaluator

This module handles pattern evaluation, significance testing,
and confidence scoring for MCP pattern analysis.
"""

import asyncio
from typing import Dict, Any, List, Optional, Tuple, Union
from decimal import Decimal
import numpy as np
from datetime import datetime, timedelta
from src.utils.logging import get_logger
from src.utils.decimal_helpers import to_decimal, from_decimal
from .pattern_types import (
    ValuationData, PatternInsight, InsightType, ConfidenceLevel,
    PatternType, MarketTrend, IndustryAnalysis, RiskAssessment,
    Opportunity, StrategicRecommendation, MCPInsight,
    PATTERN_THRESHOLDS
)

logger = get_logger(__name__)


class PatternEvaluator:
    """
    Pattern evaluation service for MCP analysis

    Handles:
    - Pattern significance evaluation
    - Confidence scoring
    - Statistical validation
    - Pattern ranking and prioritization
    """

    def __init__(self):
        """Initialize the pattern evaluator"""
        self.logger = logger
        self.evaluation_cache = {}

        self.logger.info("PatternEvaluator initialized")

    async def evaluate_pattern_significance(
        self,
        pattern: PatternInsight,
        valuations: List[ValuationData]
    ) -> Decimal:
        """
        Evaluate the significance of a pattern

        Args:
            pattern: Pattern insight to evaluate
            valuations: Valuation data for context

        Returns:
            Significance score (0.0 to 1.0)
        """
        try:
            self.logger.debug("Evaluating pattern significance",
                            pattern_id=pattern.insight_id,
                            pattern_type=pattern.pattern_type.value)

            significance_score_decimal = Decimal('0.0')

            # Base significance from pattern type
            type_significance_decimal = self._get_pattern_type_significance(pattern.pattern_type)
            significance_score_decimal += type_significance_decimal * Decimal('0.3')

            # Data coverage significance
            coverage_significance_decimal = self._calculate_data_coverage_significance(
                pattern, valuations
            )
            significance_score_decimal += coverage_significance_decimal * Decimal('0.3')

            # Temporal significance
            temporal_significance_decimal = self._calculate_temporal_significance(pattern)
            significance_score_decimal += temporal_significance_decimal * Decimal('0.2')

            # Statistical significance
            statistical_significance_decimal = await self._calculate_statistical_significance(
                pattern, valuations
            )
            significance_score_decimal += statistical_significance_decimal * Decimal('0.2')

            # Ensure score is between 0 and 1
            significance_score_decimal = max(Decimal('0.0'), min(Decimal('1.0'), significance_score_decimal))

            self.logger.debug("Pattern significance evaluated",
                            pattern_id=pattern.insight_id,
                            significance_score=from_decimal(significance_score_decimal))

            return significance_score_decimal

        except Exception as e:
            self.logger.error(f"Pattern significance evaluation failed: {e}")
            return Decimal('0.0')

    async def evaluate_pattern_confidence(
        self,
        pattern: PatternInsight,
        valuations: List[ValuationData]
    ) -> ConfidenceLevel:
        """
        Evaluate the confidence level of a pattern

        Args:
            pattern: Pattern insight to evaluate
            valuations: Valuation data for context

        Returns:
            Confidence level
        """
        try:
            self.logger.debug("Evaluating pattern confidence",
                            pattern_id=pattern.insight_id)

            confidence_score_decimal = Decimal('0.0')

            # Data quality confidence
            data_quality_decimal = self._assess_data_quality(valuations)
            confidence_score_decimal += data_quality_decimal * Decimal('0.3')

            # Pattern consistency confidence
            consistency_decimal = await self._assess_pattern_consistency(pattern, valuations)
            confidence_score_decimal += consistency_decimal * Decimal('0.3')

            # Statistical confidence
            statistical_confidence_decimal = await self._calculate_statistical_confidence(
                pattern, valuations
            )
            confidence_score_decimal += statistical_confidence_decimal * Decimal('0.2')

            # Cross-validation confidence
            cross_validation_decimal = await self._perform_cross_validation(pattern, valuations)
            confidence_score_decimal += cross_validation_decimal * Decimal('0.2')

            # Determine confidence level
            if confidence_score_decimal >= Decimal('0.8'):
                confidence_level = ConfidenceLevel.VERY_HIGH
            elif confidence_score_decimal >= Decimal('0.6'):
                confidence_level = ConfidenceLevel.HIGH
            elif confidence_score_decimal >= Decimal('0.4'):
                confidence_level = ConfidenceLevel.MEDIUM
            else:
                confidence_level = ConfidenceLevel.LOW

            self.logger.debug("Pattern confidence evaluated",
                            pattern_id=pattern.insight_id,
                            confidence_level=confidence_level.value)

            return confidence_level

        except Exception as e:
            self.logger.error(f"Pattern confidence evaluation failed: {e}")
            return ConfidenceLevel.LOW

    async def rank_patterns_by_importance(
        self,
        patterns: List[PatternInsight],
        valuations: List[ValuationData]
    ) -> List[Tuple[PatternInsight, float]]:
        """
        Rank patterns by importance score

        Args:
            patterns: List of patterns to rank
            valuations: Valuation data for context

        Returns:
            List of (pattern, importance_score) tuples sorted by importance
        """
        try:
            self.logger.info("Ranking patterns by importance",
                           patterns_count=len(patterns))

            ranked_patterns = []

            for pattern in patterns:
                # Calculate importance score
                importance_score = await self._calculate_pattern_importance(
                    pattern, valuations
                )

                ranked_patterns.append((pattern, importance_score))

            # Sort by importance score (descending)
            ranked_patterns.sort(key=lambda x: x[1], reverse=True)

            self.logger.info("Pattern ranking completed",
                           top_pattern=ranked_patterns[0][0].insight_id if ranked_patterns else None,
                           top_score=ranked_patterns[0][1] if ranked_patterns else 0.0)

            return ranked_patterns

        except DataValidationError as e:
            self.logger.error(f"Pattern ranking failed: {e}")
            return []

    async def validate_pattern_quality(
        self,
        pattern: PatternInsight,
        valuations: List[ValuationData]
    ) -> Dict[str, Any]:
        """
        Validate the quality of a pattern

        Args:
            pattern: Pattern to validate
            valuations: Valuation data for context

        Returns:
            Quality validation results
        """
        try:
            self.logger.debug("Validating pattern quality",
                            pattern_id=pattern.insight_id)

            validation_results = {
                "is_valid": True,
                "quality_score": 0.0,
                "issues": [],
                "recommendations": []
            }

            # Check data sufficiency
            if len(pattern.affected_companies) < 3:
                validation_results["issues"].append("Insufficient data points")
                validation_results["is_valid"] = False

            # Check temporal validity
            if pattern.timeframe[1] - pattern.timeframe[0] < timedelta(days=30):
                validation_results["issues"].append("Insufficient temporal coverage")
                validation_results["recommendations"].append("Extend analysis timeframe")

            # Check statistical validity
            if pattern.significance_score < PATTERN_THRESHOLDS["significance_level"]:
                validation_results["issues"].append("Low statistical significance")
                validation_results["recommendations"].append("Increase sample size or refine analysis")

            # Check confidence validity
            if pattern.confidence == ConfidenceLevel.LOW:
                validation_results["issues"].append("Low confidence level")
                validation_results["recommendations"].append("Improve data quality or analysis method")

            # Calculate overall quality score
            quality_score = 1.0
            quality_score -= len(validation_results["issues"]) * 0.2
            quality_score = max(0.0, quality_score)
            validation_results["quality_score"] = quality_score

            self.logger.debug("Pattern quality validation completed",
                            pattern_id=pattern.insight_id,
                            is_valid=validation_results["is_valid"],
                            quality_score=quality_score)

            return validation_results

        except DataValidationError as e:
            self.logger.error(f"Pattern quality validation failed: {e}")
            return {
                "is_valid": False,
                "quality_score": 0.0,
                "issues": [f"Validation error: {e}"],
                "recommendations": ["Fix validation errors"]
            }

    async def generate_pattern_insights(
        self,
        patterns: List[PatternInsight],
        valuations: List[ValuationData]
    ) -> List[MCPInsight]:
        """
        Generate MCP insights from patterns

        Args:
            patterns: List of patterns to convert
            valuations: Valuation data for context

        Returns:
            List of MCP insights
        """
        try:
            self.logger.info("Generating MCP insights from patterns",
                           patterns_count=len(patterns))

            insights = []

            for pattern in patterns:
                # Convert pattern to MCP insight
                mcp_insight = await self._convert_pattern_to_mcp_insight(pattern, valuations)
                insights.append(mcp_insight)

            self.logger.info("MCP insights generation completed",
                           insights_generated=len(insights))

            return insights

        except Exception as e:
            self.logger.error(f"MCP insights generation failed: {e}")
            return []

    def _get_pattern_type_significance(self, pattern_type: PatternType) -> Decimal:
        """Get base significance score for pattern type"""
        significance_map = {
            PatternType.TREND: Decimal('0.8'),
            PatternType.SEASONAL: Decimal('0.6'),
            PatternType.CYCLICAL: Decimal('0.7'),
            PatternType.ANOMALY: Decimal('0.9'),
            PatternType.CORRELATION: Decimal('0.7'),
            PatternType.CLUSTER: Decimal('0.6'),
            PatternType.OUTLIER: Decimal('0.8')
        }
        return significance_map.get(pattern_type, Decimal('0.5'))

    def _calculate_data_coverage_significance(
        self,
        pattern: PatternInsight,
        valuations: List[ValuationData]
    ) -> Decimal:
        """Calculate significance based on data coverage"""
        if not valuations:
            return Decimal('0.0')

        affected_count_decimal = Decimal(str(len(pattern.affected_companies)))
        total_count_decimal = Decimal(str(len(valuations)))
        if total_count_decimal > Decimal('0'):
            coverage_ratio_decimal = affected_count_decimal / total_count_decimal
            return min(Decimal('1.0'), coverage_ratio_decimal * Decimal('2'))  # Scale up to emphasize coverage
        return Decimal('0.0')

    def _calculate_temporal_significance(self, pattern: PatternInsight) -> Decimal:
        """Calculate significance based on temporal coverage"""
        timeframe_duration = pattern.timeframe[1] - pattern.timeframe[0]

        # Longer timeframes are more significant
        if timeframe_duration > timedelta(days=365):
            return Decimal('1.0')
        elif timeframe_duration > timedelta(days=180):
            return Decimal('0.8')
        elif timeframe_duration > timedelta(days=90):
            return Decimal('0.6')
        else:
            return Decimal('0.4')

    async def _calculate_statistical_significance(
        self,
        pattern: PatternInsight,
        valuations: List[ValuationData]
    ) -> Decimal:
        """Calculate statistical significance of pattern"""
        # Simplified statistical significance calculation
        # In a real implementation, this would use proper statistical tests

        significance_score_decimal = to_decimal(pattern.significance_score)
        threshold_decimal = to_decimal(PATTERN_THRESHOLDS["significance_level"])

        if significance_score_decimal >= threshold_decimal:
            return Decimal('1.0')
        else:
            if threshold_decimal > Decimal('0'):
                return significance_score_decimal / threshold_decimal
            return Decimal('0.0')

    def _assess_data_quality(self, valuations: List[ValuationData]) -> Decimal:
        """Assess data quality for confidence calculation"""
        if not valuations:
            return Decimal('0.0')

        # Check for missing or invalid data
        valid_valuations = 0
        for valuation in valuations:
            if (valuation.revenue > 0 and 
                valuation.ebitda is not None and 
                valuation.equity_value > 0):
                valid_valuations += 1

        valid_count_decimal = Decimal(str(valid_valuations))
        total_count_decimal = Decimal(str(len(valuations)))
        if total_count_decimal > Decimal('0'):
            return valid_count_decimal / total_count_decimal
        return Decimal('0.0')

    async def _assess_pattern_consistency(
        self,
        pattern: PatternInsight,
        valuations: List[ValuationData]
    ) -> Decimal:
        """Assess consistency of pattern across data"""
        # Simplified consistency assessment
        # In a real implementation, this would analyze pattern consistency

        if len(pattern.affected_companies) < 3:
            return Decimal('0.3')
        elif len(pattern.affected_companies) < 10:
            return Decimal('0.6')
        else:
            return Decimal('0.9')

    async def _calculate_statistical_confidence(
        self,
        pattern: PatternInsight,
        valuations: List[ValuationData]
    ) -> Decimal:
        """Calculate statistical confidence of pattern"""
        # Simplified statistical confidence calculation
        # In a real implementation, this would use proper statistical methods

        base_confidence_decimal = to_decimal(pattern.significance_score)

        # Adjust based on sample size
        sample_size_decimal = Decimal(str(len(pattern.affected_companies)))
        sample_size_factor_decimal = min(Decimal('1.0'), sample_size_decimal / Decimal('20'))

        return base_confidence_decimal * sample_size_factor_decimal

    async def _perform_cross_validation(
        self,
        pattern: PatternInsight,
        valuations: List[ValuationData]
    ) -> Decimal:
        """Perform cross-validation for pattern confidence"""
        # Simplified cross-validation
        # In a real implementation, this would use proper cross-validation techniques

        if len(pattern.affected_companies) < 5:
            return Decimal('0.3')
        elif len(pattern.affected_companies) < 15:
            return Decimal('0.6')
        else:
            return Decimal('0.8')

    async def _calculate_pattern_importance(
        self,
        pattern: PatternInsight,
        valuations: List[ValuationData]
    ) -> Decimal:
        """Calculate importance score for pattern"""
        importance_score_decimal = Decimal('0.0')

        # Significance weight
        significance_score_decimal = to_decimal(pattern.significance_score)
        importance_score_decimal += significance_score_decimal * Decimal('0.4')

        # Confidence weight
        confidence_weights = {
            ConfidenceLevel.VERY_HIGH: Decimal('1.0'),
            ConfidenceLevel.HIGH: Decimal('0.8'),
            ConfidenceLevel.MEDIUM: Decimal('0.6'),
            ConfidenceLevel.LOW: Decimal('0.4')
        }
        confidence_weight_decimal = confidence_weights.get(pattern.confidence, Decimal('0.5'))
        importance_score_decimal += confidence_weight_decimal * Decimal('0.3')

        # Impact weight (based on affected companies)
        affected_count_decimal = Decimal(str(len(pattern.affected_companies)))
        impact_weight_decimal = min(Decimal('1.0'), affected_count_decimal / Decimal('50'))
        importance_score_decimal += impact_weight_decimal * Decimal('0.3')

        return min(Decimal('1.0'), importance_score_decimal)

    async def _convert_pattern_to_mcp_insight(
        self,
        pattern: PatternInsight,
        valuations: List[ValuationData]
    ) -> MCPInsight:
        """Convert pattern to MCP insight format"""
        return MCPInsight(
            insight_id=f"mcp_{pattern.insight_id}",
            insight_type=pattern.insight_type,
            title=f"{pattern.pattern_type.value.title()} Pattern Detected",
            description=pattern.description,
            confidence=pattern.confidence,
            data_sources=["valuation_data", "pattern_analysis"],
            analysis_method="statistical_pattern_detection",
            key_findings=[
                f"Pattern type: {pattern.pattern_type.value}",
                f"Affected companies: {len(pattern.affected_companies)}",
                f"Significance: {pattern.significance_score:.2f}"
            ],
            implications=[
                f"This pattern affects {len(pattern.affected_companies)} companies",
                f"Pattern confidence: {pattern.confidence.value}"
            ],
            recommendations=pattern.recommendations,
            metadata=pattern.metadata
        )
