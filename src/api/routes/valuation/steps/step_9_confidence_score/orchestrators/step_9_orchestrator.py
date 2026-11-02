"""
Step 9 Orchestrator

Orchestrates the main execution flow for Step 9 Confidence Score calculation.
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from src.domain.data_quality_assessor import DataQualityAssessor
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

from ...base_step import StepOutput, StepStatus
from ..builders.step_9_result_builder import Step9ResultBuilder
from ..calculators.step_9_factor_calculator import Step9FactorCalculator
from ..calculators.step_9_score_calculator import Step9ScoreCalculator
from ..handlers.step_9_error_handler import Step9ErrorHandler

logger = get_logger(__name__)


class Step9Orchestrator:
    """Orchestrates the main execution flow for Step 9."""

    def __init__(self, step_name: str):
        """
        Initialize the orchestrator.

        Args:
            step_name: Step name for StepOutput
        """
        self.step_name = step_name
        self.error_handler = Step9ErrorHandler(step_name)
        self.factor_calculator = Step9FactorCalculator()
        self.score_calculator = Step9ScoreCalculator()
        self.result_builder = Step9ResultBuilder(step_name)
        self.quality_assessor = DataQualityAssessor()

    async def orchestrate_execution(
        self,
        request: any,
        step0: Dict[str, Any],
        step1: Dict[str, Any],
        step2: Optional[Dict[str, Any]],
        equity_step: any,
        previous_results: Dict[int, Any],
    ) -> StepOutput:
        """
        Orchestrate the main execution flow.

        Args:
            request: Valuation request
            step0: Step 0 result dictionary
            step1: Step 1 result dictionary
            step2: Step 2 result dictionary (optional)
            equity_step: Equity step result (Step 7 or 8)
            previous_results: Dictionary of all previous step results

        Returns:
            StepOutput with calculation results
        """
        # Fetch Step 2.5 (Multiple Calibration) for Quality of Earnings analysis
        step2_5 = previous_results.get(2.5)
        if step2_5 and hasattr(step2_5, 'result'):
            step2_5_result = step2_5.result
            logger.debug(
                "✅ Step 2.5 Multiple Calibration data available for QoE analysis",
                extra={
                    "step_number": 9,
                    "qoe_flag": step2_5_result.get("quality_of_earnings_flag", False),
                    "margin_volatility": step2_5_result.get("margin_analysis", {}).get("volatility_level"),
                }
            )
        else:
            step2_5_result = None
            logger.debug(
                "ℹ️ Step 2.5 not available - QoE penalties will not be applied",
                extra={"step_number": 9}
            )
        
        # If Step 2 not available, log warning but continue
        if not step2:
            logger.warning(
                "⚠️  Step 2 results not available, using defaults for methodology agreement and industry benchmarks",
                extra={
                    "step_number": 9,
                    "impact": "Methodology agreement and industry benchmarks will use default values",
                },
            )

        logger.debug(
            "🧮 Calculating 8-factor confidence score",
            extra={
                "step_number": 9,
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

        # Calculate 8 factors
        equity_result = equity_step.result if equity_step else {}
        scores = self.factor_calculator.calculate_all_factors(
            request, step0, step1, step2 or {}, equity_result
        )

        logger.debug(
            "✅ 8-factor scores calculated",
            extra={
                "step_number": 9,
                "factor_scores": scores,
                "min_score": min(scores.values()) if scores else 0,
                "max_score": max(scores.values()) if scores else 0,
                "avg_score": sum(scores.values()) / len(scores) if scores else 0,
            },
        )

        # Quality checkpoint: Validate quality hasn't degraded
        logger.debug("🔍 Validating data quality checkpoint", extra={"step_number": 9})

        quality_checkpoint = self._validate_quality_checkpoint(request, previous_results)

        if quality_checkpoint and quality_checkpoint.get("status") == "degraded":
            logger.warning(
                "⚠️  Data quality degraded at Step 9 checkpoint",
                extra={
                    "step_number": 9,
                    "baseline_score": quality_checkpoint.get("baseline_score"),
                    "current_score": quality_checkpoint.get("current_score"),
                    "degradation": quality_checkpoint.get("degradation"),
                },
            )

        # Calculate overall score with adjustments (including QoE penalties from Step 2.5)
        logger.debug(
            "🧮 Calculating overall confidence score (weighted average)",
            extra={"step_number": 9, "weights": self.score_calculator.WEIGHTS},
        )

        weighted_contributions = self.score_calculator.calculate_weighted_contributions(scores)
        overall_score, size_adjustments = self.score_calculator.calculate_overall_score(
            scores, step2, step2_5_result
        )
        confidence_level = self.score_calculator.determine_confidence_level(overall_score)

        # Get quality warnings from Step 0
        quality_warnings = step0.get("warnings", [])
        dimension_scores = step0.get("dimension_scores", {})

        # Log comprehensive confidence score breakdown
        logger.info(
            f"✅ Step 9: Confidence Score Analysis Complete - {overall_score}% ({confidence_level})",
            extra={
                "step_number": 9,
                "step_name": "Confidence Score Analysis",
                "overall_score": overall_score,
                "confidence_level": confidence_level,
                "confidence_breakdown": {
                    "factor_scores": scores,
                    "weights": self.score_calculator.WEIGHTS,
                    "weighted_contributions": weighted_contributions,
                    "calculation": f"Overall = Σ(Factor × Weight) = {overall_score:.2f}%",
                },
                "data_quality": {
                    "quality_score": step0.get("quality_score", 0),
                    "dimension_scores": dimension_scores,
                    "warnings_count": len(quality_warnings),
                    "critical_warnings": len(
                        [w for w in quality_warnings if w.get("severity") == "critical"]
                    ),
                    "high_warnings": len(
                        [w for w in quality_warnings if w.get("severity") == "high"]
                    ),
                },
                "quality_checkpoint": quality_checkpoint,
                "methodology": "Big 4 8-factor model",
                "academic_sources": ["Damodaran (2012)", "PwC Valuation Standards"],
            },
        )

        # Build result and metadata
        result_dict = self.result_builder.build_result_dict(overall_score, confidence_level, scores)

        metadata_dict = self.result_builder.build_metadata_dict(
            step0, quality_checkpoint, size_adjustments, weighted_contributions
        )

        # DEBUG: dup of "Step 9: Confidence Score Analysis Complete - X% (LEVEL)" above.
        logger.debug(
            "📊 Step 9: Confidence Score Analysis - Calculation Complete",
            extra={
                "step_number": 9,
                "step_name": "Confidence Score Analysis",
                "status": "COMPLETED",
                "inputs": {
                    "has_step0": bool(step0),
                    "has_step1": bool(step1),
                    "has_step2": bool(step2),
                    "has_equity_step": bool(equity_step),
                },
                "calculation": {
                    "methodology": "Big 4 8-factor model",
                    "formula": "Overall = Σ(Factor × Weight)",
                    "factor_scores": scores,
                    "weights": self.score_calculator.WEIGHTS,
                    "weighted_contributions": weighted_contributions,
                },
                "outputs": {
                    "overall_confidence_score": overall_score,
                    "confidence_level": confidence_level,
                },
                "metadata": {
                    "data_quality_score": step0.get("quality_score", 0),
                    "warnings_count": len(quality_warnings),
                    "critical_warnings": len(
                        [w for w in quality_warnings if w.get("severity") == "critical"]
                    ),
                    "academic_reference": "Damodaran (2012), PwC Valuation Standards",
                },
            },
        )

        return StepOutput(
            step_number=9,
            step_name=self.step_name,
            status=StepStatus.COMPLETED,
            result=result_dict,
            metadata=metadata_dict,
        )

    def _validate_quality_checkpoint(
        self, request: any, previous_results: Dict[int, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Validate data quality hasn't degraded since Step 0.

        Args:
            request: Valuation request
            previous_results: Dictionary of all previous step results

        Returns:
            Dict with quality_checkpoint results or None if Step 0 not available
        """
        # Get Step 0 baseline
        step0_result = previous_results.get(0)
        if not step0_result or step0_result.status != StepStatus.COMPLETED:
            return None

        baseline_score = step0_result.result.get("quality_score")
        if baseline_score is None:
            return None

        # Re-assess quality at checkpoint
        checkpoint_assessment = self.quality_assessor.assess_quality(
            request, baseline_score=baseline_score
        )

        current_score = checkpoint_assessment["quality_score"]
        degradation = checkpoint_assessment.get("degradation", 0)

        # Log if significant degradation detected
        if degradation and degradation > 5:
            logger.warning(
                f"⚠️ Data quality degraded by {degradation} points at Step 9 checkpoint",
                extra={
                    "baseline_score": baseline_score,
                    "current_score": current_score,
                    "degradation": degradation,
                },
            )

        return {
            "baseline_score": baseline_score,
            "current_score": current_score,
            "degradation": degradation,
            "status": "degraded" if degradation and degradation > 5 else "stable",
            "warnings_count": len(checkpoint_assessment.get("warnings", [])),
        }
