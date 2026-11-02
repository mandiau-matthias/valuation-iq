"""
Methodology Eligibility Decider

Determines DCF eligibility and methodology decision using growth-aware matrix.
Incorporates cofounder feedback: SaaS €1M with 30% growth ≠ Traditional SME €1M.

Key Factors:
- Revenue size (with growth context)
- Data quality and completeness
- Growth rate (NEW - critical for high-growth companies)
- Business model (NEW - SaaS/subscription bonus)
- Recurring revenue ratio (NEW)
- Historical data availability
- EBITDA volatility

Decision Matrix:
- Score < 40: MULTIPLES_ONLY
- Score 40-69: HYBRID_MULTIPLES_PRIMARY (e.g., SaaS €1M @ 30% growth)
- Score ≥ 70: HYBRID_DCF_PRIMARY (e.g., Established €10M+ company)

@author UpSwitch CTO Team
@version 1.0.0
@date November 2025
"""

from decimal import Decimal
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.api.schemas import ValuationRequest

from src.domain.dcf_policy import dcf_history_exclusion_reason, user_explicitly_configured_dcf
from src.domain.interfaces.request_protocol import ValuationRequestProtocol
from src.domain.hybrid_types import (
    DCFSuitabilityScore,
    MethodologyDecision,
    MethodologyEligibilityResult,
)
from src.domain.methodology.dcf_suitability_calculator import DCFSuitabilityCalculator
from src.utils.decimal_helpers import to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class MethodologyEligibilityDecider:
    """
    Determines DCF eligibility and methodology decision.

    Enhanced with growth-aware decision matrix per cofounder feedback:
    - Traditional SME €1M, 5% growth → MULTIPLES_ONLY (score ~35)
    - SaaS €1M, 30% growth → HYBRID_MULTIPLES_PRIMARY (score ~55)
    - Established €10M+ → HYBRID_DCF_PRIMARY (score ~75+)
    """

    def __init__(self, suitability_calculator: Optional[DCFSuitabilityCalculator] = None):
        """
        Initialize methodology eligibility decider.
        
        Args:
            suitability_calculator: Optional DCF suitability calculator (injected for testability)
        """
        self.logger = get_logger(__name__)
        self.suitability_calculator = suitability_calculator or DCFSuitabilityCalculator()

    @staticmethod
    def _user_explicitly_configured_dcf(request: ValuationRequestProtocol) -> bool:
        """Delegate to the single-source-of-truth in ``dcf_policy``."""
        return user_explicitly_configured_dcf(request)

    def decide_methodology(
        self, request: ValuationRequestProtocol, quality_score_from_step0: Optional[int] = None
    ) -> MethodologyEligibilityResult:
        """
        Determine methodology decision with growth-aware scoring.

        Args:
            request: Valuation request with company data
            quality_score_from_step0: Optional quality score (0-100) from Step 0.
                                     If provided, will be used instead of recalculating.

        Returns:
            MethodologyEligibilityResult with decision and scoring breakdown
        """
        # DEBUG: per-decision intro; "Methodology decision complete" below
        # carries the resulting decision + weights.
        self.logger.debug(
            "🎯 Starting methodology eligibility decision",
            extra={
                "company": request.company_name,
                "revenue": request.current_year_data.revenue,
                "business_model": request.business_model,
                "quality_score_from_step0": quality_score_from_step0,
            },
        )

        user_wants_dcf = self._user_explicitly_configured_dcf(request)

        # Calculate DCF suitability score (0-100)
        self.logger.debug(
            "🧮 Calculating DCF suitability score (6 dimensions, 0-100 points)",
            extra={
                "dimensions": [
                    "Revenue Size (0-25)",
                    "Data Quality (0-25)",
                    "Growth Rate (0-20)",
                    "Business Model (0-15)",
                    "Recurring Revenue (0-10)",
                    "Historical Data (0-5)",
                ],
                "total_max": 100,
            },
        )

        suitability_score = self.suitability_calculator.calculate_score(request, quality_score_from_step0)

        self.logger.debug(
            "✅ DCF suitability score calculated",
            extra={
                "total_score": suitability_score.total_score,
                "revenue_size_score": suitability_score.revenue_size_score,
                "data_quality_score": suitability_score.data_quality_score,
                "growth_score": suitability_score.growth_score,
                "business_model_score": suitability_score.business_model_score,
                "recurring_revenue_score": suitability_score.recurring_revenue_score,
                "historical_data_score": suitability_score.historical_data_score,
                "breakdown": suitability_score.breakdown,
                "exclusion_reason": suitability_score.exclusion_reason,
            },
        )

        # Determine decision based on total score
        self.logger.debug(
            "🎯 Determining methodology decision from score",
            extra={
                "total_score": suitability_score.total_score,
                "decision_matrix": {
                    "score < 40": "MULTIPLES_ONLY",
                    "score 40-69": "HYBRID_MULTIPLES_PRIMARY",
                    "score ≥ 70": "HYBRID_DCF_PRIMARY",
                },
            },
        )

        decision = self._score_to_decision(suitability_score.total_score)
        history_exclusion = None if user_wants_dcf else dcf_history_exclusion_reason(request)
        if history_exclusion:
            decision = MethodologyDecision.MULTIPLES_ONLY

        if user_wants_dcf and decision == MethodologyDecision.MULTIPLES_ONLY:
            decision = MethodologyDecision.HYBRID_MULTIPLES_PRIMARY
            self.logger.info(
                "✅ User explicitly configured DCF parameters — "
                "overriding MULTIPLES_ONLY → HYBRID_MULTIPLES_PRIMARY "
                f"(suitability score {suitability_score.total_score} bypassed per user intent)"
            )

        # Generate explanation
        explanation = (f"DCF valuation excluded: {history_exclusion}" if history_exclusion
                       else self._generate_explanation(request, suitability_score, decision))

        # Calculate recommended weights based on decision
        self.logger.debug(
            "⚖️  Calculating recommended weights",
            extra={
                "decision": decision.value,
                "methodology": "Weight calculation based on decision and suitability score",
            },
        )

        dcf_weight, multiples_weight = self._decision_to_weights(decision, suitability_score)

        if user_wants_dcf and dcf_weight < Decimal("0.20"):
            dcf_weight = Decimal("0.20")
            multiples_weight = Decimal("0.80")

        # DEBUG: per-decision summary; the calling step's "📊 Methodology: X"
        # line at the orchestrator level is the canonical INFO.
        self.logger.debug(
            "✅ Methodology decision complete",
            extra={
                "decision": decision.value,
                "total_score": suitability_score.total_score,
                "should_calculate_dcf": decision != MethodologyDecision.MULTIPLES_ONLY,
                "user_dcf_override": user_wants_dcf,
                "recommended_dcf_weight": dcf_weight,
                "recommended_multiples_weight": multiples_weight,
                "recommended_weights": f"DCF: {dcf_weight:.1%}, Multiples: {multiples_weight:.1%}",
                "explanation": explanation,
            },
        )

        return MethodologyEligibilityResult(
            decision=decision,
            suitability_score=suitability_score,
            should_calculate_dcf=(decision != MethodologyDecision.MULTIPLES_ONLY),
            explanation=explanation,
            recommended_dcf_weight=dcf_weight,
            recommended_multiples_weight=multiples_weight,
        )

    # REMOVED: _calculate_dcf_suitability_score() and all scoring methods
    # Logic moved to DCFSuitabilityCalculator for better SRP compliance

    def _score_to_decision(self, score: int) -> MethodologyDecision:
        """
        Convert suitability score to methodology decision.

        Thresholds:
        - < 40: MULTIPLES_ONLY (DCF not suitable)
        - 40-69: HYBRID_MULTIPLES_PRIMARY (Multiples favored, DCF supplementary)
        - ≥ 70: HYBRID_DCF_PRIMARY (DCF favored, Multiples cross-check)
        """
        if score < 40:
            return MethodologyDecision.MULTIPLES_ONLY
        elif score < 70:
            return MethodologyDecision.HYBRID_MULTIPLES_PRIMARY
        else:
            return MethodologyDecision.HYBRID_DCF_PRIMARY

    def _decision_to_weights(
        self, decision: MethodologyDecision, score: DCFSuitabilityScore
    ) -> tuple[Decimal, Decimal]:
        """
        Convert decision to recommended weights.

        Weights based on decision:
        - MULTIPLES_ONLY: 0/100
        - HYBRID_MULTIPLES_PRIMARY: 30/70 (score 40-69)
        - HYBRID_DCF_PRIMARY: 60/40 (score 70+)
        """
        if decision == MethodologyDecision.MULTIPLES_ONLY:
            return (Decimal("0.0"), Decimal("1.0"))
        elif decision == MethodologyDecision.HYBRID_MULTIPLES_PRIMARY:
            # Scale DCF weight from 0.2 to 0.4 based on score (40-69)
            # Score 40 → 20% DCF, Score 69 → 40% DCF
            normalized_score = to_decimal(
                (score.total_score - 40) / 29
            )  # Decimal('0.0') to Decimal('1.0')
            dcf_weight = Decimal("0.20") + (normalized_score * Decimal("0.20"))
            return (dcf_weight, Decimal("1.0") - dcf_weight)
        else:  # HYBRID_DCF_PRIMARY
            # Scale DCF weight from 0.5 to 0.7 based on score (70-100)
            # Score 70 → 50% DCF, Score 100 → 70% DCF
            normalized_score = min(
                to_decimal((score.total_score - 70) / 30), Decimal("1.0")
            )  # 0.0 to 1.0
            dcf_weight = Decimal("0.50") + (normalized_score * Decimal("0.20"))
            return (dcf_weight, Decimal("1.0") - dcf_weight)

    def _generate_explanation(
        self, request: ValuationRequestProtocol, score: DCFSuitabilityScore, decision: MethodologyDecision
    ) -> str:
        """Generate human-readable explanation of the decision."""

        if score.exclusion_reason:
            return f"DCF excluded: {score.exclusion_reason}"

        revenue = request.current_year_data.revenue
        company = request.company_name

        if decision == MethodologyDecision.MULTIPLES_ONLY:
            return (
                f"{company} scored {score.total_score}/100 for DCF suitability. "
                f"Given the revenue size (€{revenue:,.0f}), data quality, and business characteristics, "
                f"market multiples provide a more reliable valuation methodology. "
                f"DCF is not recommended for this valuation."
            )
        elif decision == MethodologyDecision.HYBRID_MULTIPLES_PRIMARY:
            return (
                f"{company} scored {score.total_score}/100 for DCF suitability. "
                f"A hybrid approach is recommended with multiples as the primary methodology. "
                f"DCF will provide supplementary perspective, especially valuable given "
                f"{'high growth trajectory' if score.growth_score >= 15 else 'business characteristics'}. "
                f"This is common for companies in the €1M-€5M range with growth potential."
            )
        else:  # HYBRID_DCF_PRIMARY
            return (
                f"{company} scored {score.total_score}/100 for DCF suitability. "
                f"A hybrid approach is recommended with DCF as the primary methodology. "
                f"The company's size (€{revenue:,.0f}), data quality, and "
                f"{'predictable cash flows' if score.recurring_revenue_score >= 7 else 'business maturity'} "
                f"make DCF highly reliable. Multiples will provide market validation."
            )

    # REMOVED: All explanation methods moved to DCFSuitabilityCalculator
