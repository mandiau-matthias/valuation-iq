
from src.errors.error_types import ValidationError

"""
Quality Assessor Module

Assesses overall quality rating of valuation based on multiple factors.

RESPONSIBILITIES:
- Determine valuation quality rating
- Assess data quality impact
- Evaluate methodology appropriateness
- Generate quality scores

REFACTORING NOTE:
Extracted from valuation_orchestrator.py to isolate quality assessment logic.
"""

from decimal import Decimal
from typing import Any, Dict

from src.api.schemas import ValuationRequest
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

from ..valuation_types import ValuationQuality

logger = get_logger(__name__)


class QualityAssessor:
    """
    Assesses valuation quality rating

    Features:
    - Data quality assessment
    - Methodology evaluation
    - Confidence integration
    - Quality rating determination
    """

    def __init__(self):
        """Initialize quality assessor"""
        self.logger = logger
        self.logger.debug("✅ QualityAssessor initialized")

    async def determine_quality_rating(
        self,
        request: ValuationRequest,
        valuation_results: Dict[str, Any],
        confidence_score: Decimal,
    ) -> ValuationQuality:
        """
        Determine overall quality rating

        Args:
            request: Valuation request
            valuation_results: Calculation results
            confidence_score: Confidence score

        Returns:
            ValuationQuality enum
        """
        try:
            # DEBUG: lifecycle breadcrumb; the final "Quality rating: X" line
            # below is the canonical INFO summary for this assessment.
            self.logger.debug(
                "⭐ Determining quality rating",
                extra={"company": request.company_name, "confidence_score": confidence_score},
            )

            # Factor 1: Confidence score (40% weight) - convert to Decimal if needed
            confidence_factor = Decimal(str(confidence_score)) if not isinstance(confidence_score, Decimal) else confidence_score

            # Factor 2: Data completeness (30% weight)
            completeness_factor = await self._assess_completeness(request)

            # Factor 3: Methodology appropriateness (20% weight)
            methodology_token = getattr(request, "methodology", None) or "DCF"
            methodology_factor = await self._assess_methodology(methodology_token)

            # Factor 4: Financial health (10% weight)
            health_factor = await self._assess_health(request)

            # Calculate weighted quality score
            quality_score = (
                confidence_factor * Decimal("0.4")
                + completeness_factor * Decimal("0.3")
                + methodology_factor * Decimal("0.2")
                + health_factor * Decimal("0.1")
            )

            # DEBUG: per-factor diagnostic; final "Quality rating" carries the summary.
            self.logger.debug(
                "📊 Quality factors",
                extra={
                    "confidence_factor": confidence_factor,
                    "completeness_factor": completeness_factor,
                    "methodology_factor": methodology_factor,
                    "health_factor": health_factor,
                    "quality_score": quality_score,
                },
            )

            # Map to quality rating
            if quality_score >= 0.8:
                rating = ValuationQuality.HIGH
            elif quality_score >= 0.6:
                rating = ValuationQuality.MEDIUM
            else:
                rating = ValuationQuality.LOW

            self.logger.info(
                f"✅ Quality rating: {rating.value}",
                extra={"quality_score": quality_score, "rating": rating.value},
            )

            return rating

        except Exception as e:
            self.logger.error(
                f"❌ Quality rating determination failed: {e}",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            return ValuationQuality.MEDIUM

    async def _assess_completeness(self, request: ValuationRequest) -> Decimal:
        """Assess data completeness factor"""
        try:
            fields = ["revenue", "ebitda", "total_assets", "total_debt"]
            present = sum(1 for f in fields if getattr(request.current_year_data, f, None) is not None)
            score = Decimal(str(present / len(fields)))

            self.logger.debug(
                f"📋 Completeness: {float(score)*100:.0f}%",
                extra={"present": present, "total": len(fields)},
            )

            return score
        except (ValueError, TypeError, AttributeError, KeyError, ZeroDivisionError):
            return Decimal("0.5")

    async def _assess_methodology(self, methodology: str) -> Decimal:
        """Assess methodology appropriateness"""
        try:
            methodology_scores = {
                "dcf": Decimal("0.9"),
                "hybrid": Decimal("0.95"),
                "multiples": Decimal("0.8"),
                "market": Decimal("0.75"),
                "income": Decimal("0.8"),
                "asset_based": Decimal("0.7"),
                "asset-based": Decimal("0.7"),
                "cost": Decimal("0.7"),
            }
            score = methodology_scores.get(str(methodology).lower(), Decimal("0.7"))

            self.logger.debug(
                f"🎯 Methodology score: {score}", extra={"methodology": methodology, "score": score}
            )

            return score
        except (ValueError, TypeError, AttributeError, KeyError):
            return Decimal("0.7")

    async def _assess_health(self, request: ValuationRequest) -> Decimal:
        """Assess financial health factor"""
        try:
            revenue = request.current_year_data.revenue or 0
            ebitda = request.current_year_data.ebitda or 0

            if revenue == 0:
                return Decimal("0.3")

            margin = Decimal(str(ebitda / revenue))
            score = Decimal("0.5") + min(margin * Decimal("2"), Decimal("0.5"))

            self.logger.debug(
                f"💪 Health score: {score}", extra={"margin": f"{margin*100:.1f}%", "score": score}
            )

            return score
        except (ValueError, TypeError, AttributeError, ZeroDivisionError):
            return Decimal("0.5")
