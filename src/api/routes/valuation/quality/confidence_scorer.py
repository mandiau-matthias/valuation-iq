"""
Confidence Scorer Module

Calculates confidence scores for valuations based on data quality and methodology.

RESPONSIBILITIES:
- Calculate comprehensive confidence scores (8 factors)
- Assess data completeness impact on confidence
- Map confidence scores to levels (low/medium/high)
- Track confidence factors and adjustments with full transparency

REFACTORING NOTE:
Extracted from valuation_orchestrator.py to isolate confidence scoring logic.

TRANSPARENCY ENHANCEMENT:
Now tracks all 8 confidence factors individually with detailed explanations.
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from src.api.schemas import ValuationRequest
from src.api.routes.valuation.quality.coordinators import (
    ComprehensiveAssessmentCoordinator,
    FactorCalculationCoordinator,
)
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ConfidenceScorer:
    """
    Calculates confidence scores for valuations with 8-factor breakdown

    Features:
    - 8-factor confidence assessment
    - Data completeness assessment
    - Methodology-based confidence
    - Risk factor integration
    - Confidence level mapping
    - Full transparency tracking
    """

    def __init__(self, transparency_collector: Optional[Any] = None):
        """
        Initialize confidence scorer

        Args:
            transparency_collector: Optional transparency collector for tracking
        """
        self.logger = logger
        self.transparency_collector = transparency_collector
        
        # Initialize coordinators
        self.factor_calculation_coordinator = FactorCalculationCoordinator(
            transparency_collector, self.logger
        )
        self.comprehensive_assessment_coordinator = ComprehensiveAssessmentCoordinator(self.logger)
        
        self.logger.debug("✅ ConfidenceScorer initialized with transparency tracking")

    async def calculate_comprehensive_score(
        self, request: ValuationRequest, valuation_results: Dict[str, Any]
    ) -> Decimal:
        """
        Calculate comprehensive confidence score

        Args:
            request: Valuation request
            valuation_results: Valuation calculation results

        Returns:
            Confidence score (Decimal('0.0') to Decimal('1.0'))
        """
        try:
            self.logger.info(
                "🎯 Calculating comprehensive confidence score",
                extra={
                    "company": request.company_name,
                    "methodology": valuation_results.get("methodology", "unknown"),
                },
            )

            # Base confidence by methodology
            methodology = valuation_results.get("methodology", "DCF")
            base_confidence = {
                "DCF": Decimal("0.8"),
                "Multiples": Decimal("0.75"),
                "Asset-Based": Decimal("0.6"),
                "Market": Decimal("0.7"),
                "Income": Decimal("0.75"),
                "Cost": Decimal("0.65"),
                "Hybrid": Decimal("0.85"),
            }.get(methodology, Decimal("0.7"))

            self.logger.info(
                f"📊 Base confidence: {base_confidence}",
                extra={"methodology": methodology, "base_confidence": base_confidence},
            )

            # Data completeness factor (delegated to ComprehensiveAssessmentCoordinator)
            completeness_score = await self.comprehensive_assessment_coordinator.assess_data_completeness(request)
            self.logger.info(
                f"📋 Data completeness: {completeness_score}",
                extra={"completeness_score": completeness_score},
            )

            # Financial health factor (delegated to ComprehensiveAssessmentCoordinator)
            health_score = await self.comprehensive_assessment_coordinator.assess_financial_health(request)
            self.logger.info(
                f"💪 Financial health: {health_score}", extra={"health_score": health_score}
            )

            # Market data quality factor (delegated to ComprehensiveAssessmentCoordinator)
            market_quality = await self.comprehensive_assessment_coordinator.assess_market_data_quality(request)
            self.logger.info(
                f"📈 Market data quality: {market_quality}",
                extra={"market_quality": market_quality},
            )

            # Calculate weighted confidence
            confidence_score = (
                base_confidence * Decimal("0.4")
                + completeness_score * Decimal("0.3")
                + health_score * Decimal("0.2")
                + market_quality * Decimal("0.1")
            )

            # Clamp to valid range
            confidence_score = min(Decimal("1.0"), max(Decimal("0.0"), confidence_score))

            self.logger.info(
                "✅ Comprehensive confidence score calculated",
                extra={
                    "base_confidence": base_confidence,
                    "completeness_score": completeness_score,
                    "health_score": health_score,
                    "market_quality": market_quality,
                    "final_confidence": confidence_score,
                    "percentage": f"{confidence_score*100:.0f}%",
                },
            )

            return confidence_score

        except Exception as e:
            self.logger.error(
                f"❌ Confidence score calculation failed: {e}",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            return Decimal("0.7")

    async def calculate_8_factor_confidence(
        self, request: ValuationRequest, valuation_results: Dict[str, Any]
    ) -> Dict[str, int]:
        """
        Calculate detailed 8-factor confidence breakdown with transparency tracking.

        Delegates to FactorCalculationCoordinator.

        The 8 factors are:
        1. Data Quality (0-100)
        2. Historical Data (0-100)
        3. Methodology Agreement (0-100)
        4. Industry Benchmarks (0-100)
        5. Company Profile (0-100)
        6. Market Conditions (0-100)
        7. Geographic Data (0-100)
        8. Business Model Clarity (0-100)

        Args:
            request: Valuation request
            valuation_results: Valuation calculation results

        Returns:
            Dict with all 8 factor scores and overall score
        """
        return await self.factor_calculation_coordinator.calculate_8_factor_confidence(
            request, valuation_results
        )

    def map_score_to_level(self, confidence_score: Decimal) -> str:
        """
        Map confidence score to level

        Args:
            confidence_score: Confidence score (Decimal('0.0') to Decimal('1.0'))

        Returns:
            Confidence level string ('low', 'medium', 'high')
        """
        try:
            # DEBUG: lifecycle breadcrumb; the level itself is in the
            # final-summary log emitted by the comprehensive orchestrator
            # ("🎯 Confidence: X% (from Step 9 eight-factor model)").
            self.logger.debug(
                "🎯 Mapping confidence score to level", extra={"confidence_score": confidence_score}
            )

            if confidence_score >= 0.8:
                level = "high"
            elif confidence_score >= 0.6:
                level = "medium"
            else:
                level = "low"

            self.logger.debug(
                f"✅ Confidence level: {level}",
                extra={"confidence_score": confidence_score, "level": level},
            )

            return level

        except Exception as e:
            self.logger.error(
                f"❌ Confidence level mapping failed: {e}",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            return "medium"
