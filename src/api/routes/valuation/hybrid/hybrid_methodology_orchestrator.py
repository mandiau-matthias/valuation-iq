"""
Hybrid Methodology Orchestrator

Main coordinator for hybrid valuation (DCF + Multiples).
Replaces the 1076-line `_execute_hybrid_valuation()` method with clean modular architecture.

Orchestration flow:
1. Decide methodology eligibility (growth-aware)
2. Calculate DCF (if eligible)
3. Calculate Multiples (always)
4. Calculate weights (if hybrid)
5. Aggregate results
6. Calculate confidence and ranges
7. Build final response

@author UpSwitch CTO Team
@version 1.0.0
@date November 2025
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from src.api.routes.valuation.calculators.dcf_calculator import DCFCalculator
from src.api.routes.valuation.calculators.multiples_calculator import MultiplesCalculator
from src.api.routes.valuation.hybrid.hybrid_final_result_builder import (
    build_hybrid_final_result,
    coerce_confidence_score,
)
from src.api.routes.valuation.quality.confidence_scorer import ConfidenceScorer
from src.api.schemas import ValuationRequest
from src.database.business_types_repository import get_business_types_repository
from src.domain.hybrid_weight_calculator import HybridWeightCalculator
from src.domain.methodology_eligibility_decider import MethodologyEligibilityDecider
from src.domain.range_calculator import ValuationRangeCalculator
from src.domain.valuation_aggregator import ValuationAggregator
from src.services.business_intelligence.business_type_multiples_adapter import (
    get_business_type_multiples_adapter,
)
from src.utils.decimal_helpers import to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)

# A floored DCF resolves both EV and equity to a tiny positive sentinel (≈ €1). Any
# genuine going-concern DCF equity is orders of magnitude larger, so values at or below
# this threshold are treated as the sentinel rather than a real valuation.
_DCF_USABILITY_FLOOR = Decimal("1")


def _dcf_result_is_unusable(dcf_result: Dict[str, Any]) -> bool:
    """Return True when a DCF result must be excluded from the hybrid blend.

    A DCF is unusable when it was floored (its raw EV/equity was non-positive) or when
    the returned EV/equity is missing or collapses to the positive sentinel. Blending
    such a value silently corrupts the headline equity and the EV→equity bridge.
    """
    if dcf_result.get("dcf_value_floored"):
        return True
    for key in ("equity_value", "enterprise_value"):
        value = dcf_result.get(key)
        if value is None:
            return True
        try:
            if to_decimal(value) <= _DCF_USABILITY_FLOOR:
                return True
        except (TypeError, ValueError, ArithmeticError):
            return True
    return False


class HybridMethodologyOrchestrator:
    """
    Orchestrates hybrid valuation with modular components.

    This class replaces the monolithic `_execute_hybrid_valuation()` method (1076 lines)
    with a clean, modular architecture. Each step is delegated to a specialized component.

    Key improvements:
    - Growth-aware methodology decision (SaaS €1M ≠ Traditional SME €1M)
    - Priority cascade for weight calculation
    - Clear separation of concerns
    - Testable components
    - Transparent decision-making
    """

    def __init__(
        self,
        *,
        dcf_calculator: Optional[DCFCalculator] = None,
        multiples_calculator: Optional[MultiplesCalculator] = None,
        confidence_scorer: Optional[ConfidenceScorer] = None,
        business_types_repo: Optional[Any] = None,
        multiples_adapter: Optional[Any] = None,
        fmp_adapter: Optional[Any] = None,
    ):
        self.logger = get_logger(__name__)

        # Initialize components
        self.eligibility_decider = MethodologyEligibilityDecider()
        self.weight_calculator = HybridWeightCalculator()
        self.aggregator = ValuationAggregator()
        self.dcf_calculator = dcf_calculator or DCFCalculator()

        if multiples_calculator is not None:
            self.multiples_calculator = multiples_calculator
        else:
            # MultiplesCalculator requires dependencies. Allow tests and the
            # process-wide ValuationOrchestrator to inject warm collaborators so
            # startup does not register the full step pipeline twice.
            business_types_repo = business_types_repo or get_business_types_repository()
            multiples_adapter = multiples_adapter or get_business_type_multiples_adapter()

            # Phase 3: Initialize market data services (optional)
            if fmp_adapter is None:
                try:
                    from src.adapters.fmp_adapter import FMPAdapter

                    fmp_adapter = FMPAdapter()
                except (ImportError, Exception):
                    pass  # FMP adapter optional

            self.multiples_calculator = MultiplesCalculator(
                multiples_adapter=multiples_adapter,
                business_types_repo=business_types_repo,
                fmp_adapter=fmp_adapter,  # Phase 3: Market Data Integration
                cache_service=None,  # Phase 3: Will be initialized lazily if needed
            )

        self.confidence_scorer = confidence_scorer or ConfidenceScorer()
        # ValuationRangeCalculator is a static class, no instantiation needed

        self.logger.debug("✅ HybridMethodologyOrchestrator initialized")

    async def execute_hybrid(
        self, request: ValuationRequest, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute hybrid valuation with modular components.

        This is the main entry point that replaces the 400-line monolithic method
        with clean orchestration of specialized components.

        Args:
            request: Valuation request
            context: Optional context data

        Returns:
            Complete hybrid valuation result
        """
        try:
            self.logger.info(
                "🚀 Starting hybrid valuation orchestration",
                extra={
                    "company": request.company_name,
                    "revenue": request.current_year_data.revenue,
                    "business_model": request.business_model,
                },
            )

            # === STEP 1: Decide Methodology Eligibility ===
            self.logger.info(
                "🎯 Step 1: Deciding methodology eligibility",
                extra={
                    "company": request.company_name,
                    "revenue": request.current_year_data.revenue,
                    "business_model": request.business_model,
                    "note": "Growth-aware decision matrix (SaaS €1M ≠ Traditional SME €1M)",
                },
            )

            eligibility = self.eligibility_decider.decide_methodology(request)

            self.logger.info(
                "✅ Step 1 complete: Methodology decision",
                extra={
                    "decision": eligibility.decision.value,
                    "suitability_score": eligibility.suitability_score.total_score,
                    "should_calculate_dcf": eligibility.should_calculate_dcf,
                    "recommended_dcf_weight": eligibility.recommended_dcf_weight,
                    "recommended_multiples_weight": eligibility.recommended_multiples_weight,
                    "suitability_breakdown": eligibility.suitability_score.breakdown,
                    "explanation": eligibility.explanation,
                },
            )

            # === STEP 2: Calculate DCF (if eligible) ===
            dcf_result = None
            dcf_failure_reason = None
            if eligibility.should_calculate_dcf:
                self.logger.info(
                    "📊 Step 2: Calculating DCF valuation",
                    extra={
                        "methodology": "DCF (Discounted Cash Flow)",
                        "note": "DCF eligible based on methodology decision",
                        "suitability_score": eligibility.suitability_score.total_score,
                    },
                )
                try:
                    dcf_result = await self.dcf_calculator.calculate(request, context)
                    self.logger.info(
                        "✅ Step 2 complete: DCF calculated",
                        extra={
                            "dcf_equity_value": (
                                dcf_result.get("equity_value") if dcf_result else None
                            ),
                            "dcf_enterprise_value": (
                                dcf_result.get("enterprise_value") if dcf_result else None
                            ),
                            "wacc": dcf_result.get("wacc") if dcf_result else None,
                            "terminal_value": (
                                dcf_result.get("terminal_value") if dcf_result else None
                            ),
                        },
                    )
                except Exception as e:
                    error_type = type(e).__name__
                    error_message = str(e)
                    dcf_failure_reason = f"{error_type}: {error_message}"

                    self.logger.error(
                        "❌ DCF calculation failed — graceful degradation to Multiples-only",
                        exc_info=True,
                        extra={
                            "error_type": error_type,
                            "error_message": error_message,
                            "company": request.company_name,
                            "revenue": request.current_year_data.revenue,
                            "graceful_degradation": True,
                        },
                    )
                    dcf_result = None
            else:
                self.logger.info(
                    "⏭️  Step 2 skipped: DCF excluded by methodology decision",
                    extra={
                        "decision": eligibility.decision.value,
                        "suitability_score": eligibility.suitability_score.total_score,
                        "exclusion_reason": (
                            eligibility.suitability_score.exclusion_reason
                            if hasattr(eligibility.suitability_score, "exclusion_reason")
                            else "Methodology decision"
                        ),
                    },
                )

            # A DCF that resolved to a non-positive value is floored to a sentinel (≈ €1)
            # so the standalone DCF page stays renderable. Such a result is NOT a usable
            # valuation: blending it drags equity toward zero and breaks the EV→equity
            # bridge (it manifests as a large bogus "net debt" residual). Degrade
            # gracefully to Multiples-only — the same path used when DCF raises.
            if dcf_result is not None and _dcf_result_is_unusable(dcf_result):
                dcf_failure_reason = (
                    "DCF resolved to a non-positive value (floored); excluded from blend"
                )
                self.logger.warning(
                    "⚠️  DCF produced a non-positive (floored) value — excluding from hybrid blend",
                    extra={
                        "dcf_equity_value": dcf_result.get("equity_value"),
                        "dcf_enterprise_value": dcf_result.get("enterprise_value"),
                        "dcf_value_floored": dcf_result.get("dcf_value_floored"),
                        "company": request.company_name,
                        "fallback": "Multiples-only",
                    },
                )
                dcf_result = None

            # === STEP 3: Calculate Multiples (always) ===
            self.logger.info(
                "📊 Step 3: Calculating Multiples valuation",
                extra={
                    "methodology": "Multiples (Market Comparables)",
                    "note": "Multiples calculation always executed (required for hybrid)",
                    "system": "modular-12-step",
                },
            )

            multiples_result = await self.multiples_calculator.calculate(request, context)

            # Validate Multiples result
            if not multiples_result or not isinstance(multiples_result, dict):
                self.logger.error(
                    "❌ Multiples calculation returned invalid result",
                    extra={
                        "result_type": type(multiples_result).__name__,
                        "result_is_none": multiples_result is None,
                        "validation_failed": "Result must be a dictionary",
                    },
                )
                raise ValueError(
                    "Multiples calculation returned invalid result (None or not a dict)"
                )

            self.logger.info(
                "✅ Step 3 complete: Multiples calculated",
                extra={
                    "multiples_equity_value": multiples_result.get("adjusted_equity_value")
                    or multiples_result.get("equity_value"),
                    "multiples_equity_low": multiples_result.get("equity_value_low"),
                    "multiples_equity_high": multiples_result.get("equity_value_high"),
                    "primary_method": multiples_result.get("primary_method"),
                    "confidence_score": multiples_result.get("confidence_score"),
                    "steps_executed": (
                        multiples_result.get("modular_system", {}).get("total_steps")
                        if isinstance(multiples_result.get("modular_system"), dict)
                        else None
                    ),
                },
            )

            # === STEP 4: Calculate Weights (if hybrid) ===
            self.logger.info(
                "⚖️  Step 4: Calculating methodology weights",
                extra={
                    "methodology_decision": eligibility.decision.value,
                    "note": "Weight calculation uses priority cascade: business_context → database → hardcoded → profitability default",
                },
            )

            weights = await self.weight_calculator.calculate_weights(request, eligibility.decision)

            self.logger.info(
                "✅ Step 4 complete: Weights calculated",
                extra={
                    "dcf_weight": weights.dcf_weight,
                    "multiples_weight": weights.multiples_weight,
                    "source": weights.source,
                    "base_dcf_weight": weights.base_dcf_weight,
                    "base_multiples_weight": weights.base_multiples_weight,
                    "adjustments_applied": weights.adjustments_applied,
                    "rationale": weights.rationale,
                    "weight_sum": weights.dcf_weight + weights.multiples_weight,
                },
            )

            # === STEP 5: Aggregate Results ===
            self.logger.info(
                "🔄 Step 5: Aggregating DCF and Multiples results",
                extra={
                    "has_dcf_result": dcf_result is not None,
                    "has_multiples_result": multiples_result is not None,
                    "dcf_weight": weights.dcf_weight,
                    "multiples_weight": weights.multiples_weight,
                    "methodology_decision": eligibility.decision.value,
                    "formula": "Aggregated = DCF × DCF_Weight + Multiples × Multiples_Weight",
                },
            )

            aggregated = self.aggregator.aggregate_results(
                dcf_result, multiples_result, weights, eligibility.decision
            )

            self.logger.info(
                "✅ Step 5 complete: Results aggregated",
                extra={
                    "equity_value": aggregated.equity_value,
                    "equity_value_low": aggregated.equity_value_low,
                    "equity_value_high": aggregated.equity_value_high,
                    "enterprise_value": aggregated.enterprise_value,
                    "methodology": aggregated.methodology,
                    "warnings_count": len(aggregated.warnings),
                    "calculation_timestamp": aggregated.calculation_timestamp,
                },
            )

            # === STEP 6: Calculate Confidence and Ranges ===
            self.logger.info(
                "📊 Step 6: Calculating confidence score and valuation ranges",
                extra={
                    "aggregated_equity_value": aggregated.equity_value,
                    "methodology": aggregated.methodology,
                    "note": "Confidence score uses 8-factor model, ranges use enhanced spread methodology",
                },
            )

            # Validate aggregated equity value
            if aggregated.equity_value is None or aggregated.equity_value <= 0:
                self.logger.error(
                    "❌ Invalid aggregated equity value",
                    extra={
                        "aggregated_equity_value": aggregated.equity_value,
                        "validation_failed": "Equity value must be positive",
                    },
                )
                raise ValueError(
                    f"Invalid aggregated equity value: {aggregated.equity_value}. "
                    "Cannot calculate confidence and ranges."
                )

            # Build preliminary result for confidence calculation
            preliminary_result = {
                "equity_value": aggregated.equity_value,
                "enterprise_value": aggregated.enterprise_value,
                "methodology": aggregated.methodology,
                "dcf_result": dcf_result,
                "multiples_result": multiples_result,
            }

            # Calculate confidence score with error handling
            self.logger.debug(
                "🧮 Calculating confidence score (8-factor model)",
                extra={
                    "methodology": "Big 4 8-factor model",
                    "factors": [
                        "Data Quality",
                        "Historical Data",
                        "Methodology Agreement",
                        "Industry Benchmarks",
                        "Company Profile",
                        "Market Conditions",
                        "Geographic Data",
                        "Business Model Clarity",
                    ],
                },
            )

            try:
                # calculate_comprehensive_score returns Decimal(0.0 to 1.0)
                confidence_score = await self.confidence_scorer.calculate_comprehensive_score(
                    request, preliminary_result
                )
                confidence_score, confidence_score_valid = self._coerce_confidence_score(
                    confidence_score
                )
                if not confidence_score_valid:
                    self.logger.warning(
                        "⚠️  Invalid confidence score, using default",
                        extra={
                            "invalid_score": confidence_score,
                            "default_score": Decimal("0.66"),
                            "action": "Using default medium confidence",
                        },
                    )
                    confidence_score = Decimal("0.66")
                confidence_data = {"overall_confidence": confidence_score, "factors": {}}

                self.logger.debug(
                    "✅ Confidence score calculated",
                    extra={
                        "confidence_score": confidence_score,
                        "confidence_score_pct": confidence_score * 100,
                    },
                )
            except Exception as e:
                self.logger.warning(
                    "⚠️  Confidence calculation failed, using default",
                    extra={
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "default_score": Decimal("0.66"),
                        "fallback": "Using default medium confidence",
                    },
                )
                confidence_score = Decimal("0.66")
                confidence_data = {"overall_confidence": Decimal("0.66"), "factors": {}}

            # Map confidence score to level with error handling
            self.logger.debug(
                "📊 Mapping confidence score to level",
                extra={
                    "confidence_score": confidence_score,
                    "mapping_tiers": {
                        "HIGH": "≥0.80 (80-100%)",
                        "MEDIUM": "0.60-0.79 (60-79%)",
                        "LOW": "<0.60 (<60%)",
                    },
                },
            )

            try:
                confidence_level = self.confidence_scorer.map_score_to_level(confidence_score)
                self.logger.debug(
                    "✅ Confidence level mapped",
                    extra={
                        "confidence_score": confidence_score,
                        "confidence_level": confidence_level,
                    },
                )
            except Exception as e:
                self.logger.warning(
                    "⚠️  Confidence level mapping failed, using 'medium'",
                    extra={
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "default_level": "medium",
                        "fallback": "Using default medium level",
                    },
                )
                confidence_level = "medium"

            # Calculate ranges using ValuationRangeCalculator (static method) with error handling
            self.logger.debug(
                "📊 Calculating valuation ranges",
                extra={
                    "equity_value": aggregated.equity_value,
                    "confidence_level": confidence_level,
                    "revenue": (
                        request.current_year_data.revenue
                        if request.current_year_data.revenue
                        else None
                    ),
                    "use_enhanced_spread": True,
                    "methodology": "Enhanced confidence spread with business-type, growth, profitability adjustments",
                },
            )

            try:
                range_result = ValuationRangeCalculator.calculate_range(
                    equity_value=aggregated.equity_value,
                    confidence_level=confidence_level,
                    revenue=(
                        request.current_year_data.revenue
                        if request.current_year_data.revenue
                        else None
                    ),
                    use_enhanced_spread=True,
                )
                # Validate range result
                if not isinstance(range_result, dict):
                    raise ValueError("Range calculation returned invalid result (not a dict)")

                self.logger.debug(
                    "✅ Valuation ranges calculated",
                    extra={
                        "equity_value_low": range_result.get("equity_value_low"),
                        "equity_value_mid": range_result.get("equity_value_mid"),
                        "equity_value_high": range_result.get("equity_value_high"),
                        "range_width_pct": (
                            (
                                (
                                    range_result.get("equity_value_high", 0)
                                    - range_result.get("equity_value_low", 0)
                                )
                                / aggregated.equity_value
                                * 100
                            )
                            if aggregated.equity_value > 0
                            else 0
                        ),
                    },
                )
            except Exception as e:
                self.logger.warning(
                    "⚠️  Range calculation failed, using aggregated ranges",
                    extra={
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "fallback": "Using aggregated ranges from Step 5",
                        "aggregated_equity_low": aggregated.equity_value_low,
                        "aggregated_equity_high": aggregated.equity_value_high,
                    },
                )
                range_result = {
                    "equity_value_low": aggregated.equity_value_low,
                    "equity_value_mid": aggregated.equity_value,
                    "equity_value_high": aggregated.equity_value_high,
                    "enterprise_value_low": aggregated.enterprise_value_low,
                    "enterprise_value_mid": aggregated.enterprise_value,
                    "enterprise_value_high": aggregated.enterprise_value_high,
                }

            self.logger.info(
                "✅ Step 6 complete: Confidence and ranges calculated",
                extra={
                    "confidence_score": confidence_score,
                    "confidence_score_pct": confidence_score * 100,
                    "confidence_level": confidence_level,
                    "equity_value_low": range_result.get("equity_value_low"),
                    "equity_value_mid": range_result.get(
                        "equity_value_mid", aggregated.equity_value
                    ),
                    "equity_value_high": range_result.get("equity_value_high"),
                    "range_width_pct": (
                        (
                            (
                                range_result.get("equity_value_high", 0)
                                - range_result.get("equity_value_low", 0)
                            )
                            / aggregated.equity_value
                            * 100
                        )
                        if aggregated.equity_value > 0
                        else 0
                    ),
                },
            )

            # === STEP 7: Build Final Response ===
            self.logger.info(
                "📦 Step 7: Building final response",
                extra={
                    "note": "Assembling final result in legacy API format for backward compatibility",
                    "includes": [
                        "Core valuation values",
                        "Methodology information",
                        "Confidence and quality",
                        "Component results",
                        "Warnings and notes",
                        "Metadata",
                    ],
                },
            )

            final_result = build_hybrid_final_result(
                aggregated=aggregated,
                eligibility=eligibility,
                weights=weights,
                confidence_data=confidence_data,
                range_result=range_result,
                request=request,
                dcf_failure_reason=dcf_failure_reason,
                multiples_result=multiples_result,
                dcf_result=dcf_result,
            )

            self.logger.info(
                "✅🎉 Hybrid valuation orchestration complete",
                extra={
                    "equity_value": final_result.get("equity_value"),
                    "equity_value_low": final_result.get("equity_value_low"),
                    "equity_value_high": final_result.get("equity_value_high"),
                    "methodology": final_result.get("methodology"),
                    "confidence_score": final_result.get("confidence_score"),
                    "confidence_score_pct": (
                        final_result.get("confidence_score") * 100
                        if final_result.get("confidence_score") is not None
                        else None
                    ),
                    "warnings_count": len(aggregated.warnings),
                    "dcf_weight": final_result.get("dcf_weight"),
                    "multiples_weight": final_result.get("multiples_weight"),
                    "total_steps": 7,
                    "calculation_timestamp": final_result.get("calculation_timestamp"),
                },
            )

            return final_result

        except Exception as e:
            self.logger.error(f"❌ Hybrid valuation orchestration failed: {e}", exc_info=True)
            raise

    @staticmethod
    def _coerce_confidence_score(raw_score: Any) -> tuple[Decimal, bool]:
        return coerce_confidence_score(raw_score)
