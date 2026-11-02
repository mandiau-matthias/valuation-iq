"""
Step 0: Data Quality Assessment

This step evaluates the quality and completeness of input data to determine:
1. Whether DCF methodology is viable
2. Overall data quality score (0-100) across 5 dimensions (completeness, validity, consistency, accuracy, timeliness)
3. Which calculation paths should be taken
4. Actionable recommendations to improve data quality

Enhanced with comprehensive validation following McKinsey/Bain 5-dimension framework.
"""

import time
import traceback
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.api.routes.valuation.triage.business_type_triage import BusinessTypeTriageEngine
from src.api.routes.valuation.triage.step_registry import register_step
from src.domain.data_quality_assessor import DataQualityAssessor
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

from src.api.routes.valuation.steps.base_step import (
    CalculationStep,
    StepInput,
    StepOutput,
    StepStatus,
)
from src.api.routes.valuation.steps.step_0_modules.executors.dcf_eligibility_determiner import (
    DCFEligibilityDeterminer,
)
from src.api.routes.valuation.steps.step_0_modules.executors.quality_assessment_executor import (
    QualityAssessmentExecutor,
)
from src.api.routes.valuation.steps.step_0_modules.executors.subcalculation_executor import (
    Step0SubcalculationExecutor,
)

# Import refactored modules
from src.api.routes.valuation.steps.step_0_modules.handlers.entry_point_handler import (
    EntryPointHandler,
)
from src.api.routes.valuation.steps.step_0_modules.handlers.fallback_handler import (
    FallbackHandler,
)
from src.api.routes.valuation.steps.step_0_modules.handlers.result_builder import (
    ResultBuilder,
)
from src.api.routes.valuation.steps.step_0_modules.utils.quality_level_mapper import (
    QualityLevelMapper,
)
from src.api.routes.valuation.steps.step_0_modules.utils.score_breakdown_generator import (
    ScoreBreakdownGenerator,
)
from src.api.routes.valuation.steps.step_0_modules.validators.result_validator import (
    ResultValidator,
)
from src.api.routes.valuation.steps.step_0_modules.subcalculators.subcalculation_registry import (
    Step0SubcalculationRegistry,
)

logger = get_logger(__name__)


@register_step
class Step0DataQuality(CalculationStep):
    """
    Data Quality Assessment Step (REFACTORED)

    Evaluates data completeness and determines methodology eligibility based on:
    - Data completeness (revenue, EBITDA, balance sheet, historical data)
    - Company size (revenue threshold for DCF)
    - Historical data availability (3+ years required for DCF)

    McKinsey Methodology:
    - Data quality score < 60% → Multiples only
    - Historical data < 3 years → Multiples only
    - Revenue < €5M AND data quality < 70% → Multiples only
    - Otherwise → Hybrid (DCF primary, Multiples cross-check)

    REFACTORING SUMMARY:
    - Original: 1,571 lines monolithic class
    - Refactored: ~200 lines coordinator + 9 specialized modules
    - Benefits: Better maintainability, testability, separation of concerns
    """

    @property
    def step_number(self) -> int:
        return 0

    @property
    def step_name(self) -> str:
        return "Data Quality Assessment"

    def __init__(self):
        self.business_type_triage = BusinessTypeTriageEngine()
        self.quality_assessor = DataQualityAssessor()

        # Initialize refactored modules
        self.entry_point_handler = EntryPointHandler(self.step_name)
        self.fallback_handler = FallbackHandler(self.step_name)
        self.quality_assessment_executor = QualityAssessmentExecutor(self.quality_assessor)
        self.subcalculation_executor = Step0SubcalculationExecutor(
            Step0SubcalculationRegistry()
        )
        self.result_validator = ResultValidator()
        self.dcf_eligibility_determiner = DCFEligibilityDeterminer(self.business_type_triage)
        self.score_breakdown_generator = ScoreBreakdownGenerator()
        self.quality_level_mapper = QualityLevelMapper()
        self.result_builder = ResultBuilder(self.step_name)

    @property
    def dependencies(self) -> List[int]:
        return []  # No dependencies, this is the first step

    def should_execute(self, input_data: StepInput) -> bool:
        return True  # Always assess data quality

    async def execute(self, input_data: StepInput) -> StepOutput:
        """
        Assess data quality and determine methodology eligibility.

        Uses comprehensive 5-dimension assessment:
        1. Completeness: Required fields, historical data
        2. Validity: Data types, ranges, formats
        3. Consistency: Cross-field relationships, temporal trends
        4. Accuracy: Reasonableness vs benchmarks, outliers
        5. Timeliness: Data freshness, recency

        Returns:
            StepOutput with quality_score, dcf_eligible, multiples_method, warnings, recommendations
        """
        step_start_time = time.time()

        # CRITICAL: Wrap entire method body in try/except to catch ALL exceptions
        try:
            # Handle entry point validation
            request, early_return = self.entry_point_handler.handle_entry(input_data, step_number=0)
            if early_return:
                return early_return

            sub_calculations = self.subcalculation_executor.execute(request, step_number=0)

            # Execute quality assessment
            quality_assessment, assess_quality_duration, timeout_occurred = (
                self.quality_assessment_executor.execute_assessment(request, step_number=0)
            )

            # Validate quality assessment structure
            quality_assessment = self.result_validator.validate_quality_assessment(
                quality_assessment, step_number=0
            )

            # Extract and validate quality score
            quality_score = self.result_validator.validate_quality_score(
                quality_assessment.get("quality_score", 0), step_number=0
            )

            # Extract and validate dimension scores
            dimension_scores = self.result_validator.validate_dimension_scores(
                quality_assessment.get("dimension_scores", {}), step_number=0
            )

            # Extract and validate warnings
            warnings = self.result_validator.validate_warnings(
                quality_assessment.get("warnings", []), step_number=0
            )

            # Extract and validate recommendations
            recommendations = self.result_validator.validate_recommendations(
                quality_assessment.get("recommendations", []), step_number=0
            )

            # DEBUG: per-dimension breakdown; Step 0 EXECUTION COMPLETE
            # carries the headline quality_score.
            logger.debug(
                "📊 Data quality dimension scores calculated",
                extra={
                    "step_number": 0,
                    "overall_quality_score": quality_score,
                    "completeness_score": dimension_scores.get("completeness", 0),
                    "validity_score": dimension_scores.get("validity", 0),
                    "consistency_score": dimension_scores.get("consistency", 0),
                    "accuracy_score": dimension_scores.get("accuracy", 0),
                    "timeliness_score": dimension_scores.get("timeliness", 0),
                    "dimension_scores": dimension_scores,
                    "all_dimensions_present": all(
                        dim in dimension_scores for dim in ResultValidator.REQUIRED_DIMENSIONS
                    ),
                },
            )

            # Determine DCF eligibility
            logger.debug(
                "🔍 Evaluating DCF eligibility using McKinsey criteria",
                extra={
                    "step_number": 0,
                    "quality_score": quality_score,
                    "criteria": [
                        "Data quality score >= 60%",
                        "Revenue >= threshold (business-type aware)",
                        "Historical data >= 2 years (3 preferred)",
                        "Not a sole trader",
                    ],
                },
            )

            dcf_eligible, dcf_exclusion_reason = self.dcf_eligibility_determiner.is_dcf_eligible(
                request,
                quality_score,
                step_number=0,
                user_selected_method=getattr(request, "selected_method", None),
                sub_calculations=sub_calculations,
            )

            # Determine multiples method role
            multiples_method = "primary" if not dcf_eligible else "cross_check"

            # Count warnings by severity
            critical_warnings = [w for w in warnings if w.get("severity") == "critical"]
            high_warnings = [w for w in warnings if w.get("severity") == "high"]
            medium_warnings = [w for w in warnings if w.get("severity") == "medium"]

            # DEBUG: methodology decision is logged by the methodology
            # determiner with full context; this is a per-step echo.
            logger.debug(
                "✅ Methodology decision determined",
                extra={
                    "step_number": 0,
                    "dcf_eligible": dcf_eligible,
                    "multiples_method": multiples_method,
                    "methodology": "Hybrid (DCF + Multiples)" if dcf_eligible else "Multiples Only",
                    "decision_factors": {
                        "quality_score": quality_score,
                        "quality_threshold_met": quality_score >= 60,
                        "revenue": (
                            getattr(request.current_year_data, "revenue", 0)
                            if hasattr(request, "current_year_data") and request.current_year_data
                            else 0
                        ),
                        "historical_years": (
                            len(getattr(request, "historical_years_data", []))
                            if getattr(request, "historical_years_data", None)
                            else 0
                        ),
                    },
                },
            )

            # Comprehensive summary logging for auditability — DEBUG since the
            # canonical "EXECUTION COMPLETE" exit log below already carries the
            # same outputs. This block stays for offline replay of full inputs.
            logger.debug(
                "📊 Step 0: Data Quality Assessment - Calculation Complete",
                extra={
                    "step_number": 0,
                    "step_name": "Data Quality Assessment",
                    "status": "COMPLETED",
                    "inputs": {
                        "has_current_year_data": hasattr(request, "current_year_data")
                        and request.current_year_data is not None,
                        "historical_years_count": (
                            len(getattr(request, "historical_years_data", []))
                            if getattr(request, "historical_years_data", None)
                            else 0
                        ),
                        "has_balance_sheet": (
                            bool(
                                getattr(request.current_year_data, "total_debt", None) is not None
                                and getattr(request.current_year_data, "cash", None) is not None
                            )
                            if hasattr(request, "current_year_data") and request.current_year_data
                            else False
                        ),
                    },
                    "calculation": {
                        "methodology": "5-dimension framework (McKinsey/Bain)",
                        "dimensions": [
                            "completeness",
                            "validity",
                            "consistency",
                            "accuracy",
                            "timeliness",
                        ],
                        "quality_score": quality_score,
                        "dimension_scores": dimension_scores,
                        "dcf_eligible": dcf_eligible,
                    },
                    "outputs": {
                        "quality_score": quality_score,
                        "quality_level": self.quality_level_mapper.get_quality_level(quality_score),
                        "dcf_eligible": dcf_eligible,
                        "multiples_method": multiples_method,
                        "methodology_recommendation": (
                            "DCF + Multiples" if dcf_eligible else "Multiples Only"
                        ),
                    },
                    "metadata": {
                        "warnings_count": len(warnings),
                        "critical_warnings": len(critical_warnings),
                        "high_warnings": len(high_warnings),
                        "recommendations_count": len(recommendations),
                        "assessment_method": "5-dimension framework (McKinsey/Bain)",
                        "academic_reference": "McKinsey Valuation (2015), PwC Data Quality Standards",
                    },
                },
            )

            # DEBUG: duplicate of the "EXECUTION COMPLETE" exit log below.
            logger.debug(
                f"📊 Data quality assessment complete",
                extra={
                    "step_number": 0,
                    "quality_score": quality_score,
                    "quality_level": self.quality_level_mapper.get_quality_level(quality_score),
                    "dimension_scores": dimension_scores,
                    "dcf_eligible": dcf_eligible,
                    "multiples_method": multiples_method,
                    "warnings_count": len(warnings),
                    "critical_warnings": len(critical_warnings),
                    "high_warnings": len(high_warnings),
                    "medium_warnings": len(medium_warnings),
                    "recommendations_count": len(recommendations),
                    "warnings_summary": {
                        "total": len(warnings),
                        "critical": len(critical_warnings),
                        "high": len(high_warnings),
                        "medium": len(medium_warnings),
                    },
                },
            )

            # Get quality level
            quality_level = self.quality_level_mapper.get_quality_level(int(quality_score))

            # Get score breakdown
            score_breakdown = self.score_breakdown_generator.get_score_breakdown(request)

            # Build result dictionary
            result_dict = self.result_builder.build_result_dict(
                quality_score=quality_score,
                dcf_eligible=dcf_eligible,
                dcf_exclusion_reason=dcf_exclusion_reason,
                multiples_method=multiples_method,
                dimension_scores=dimension_scores,
                warnings=warnings,
                recommendations=recommendations,
                score_breakdown=score_breakdown,
                quality_level=quality_level,
                sub_calculations=sub_calculations,
                step_number=0,
            )

            # Validate result dictionary
            result_dict = self.result_validator.validate_result_dict(result_dict, step_number=0)

            # Log final result to track propagation — DEBUG, intermediate
            # bookkeeping that's already covered by the EXECUTION COMPLETE exit.
            logger.debug(
                "✅ Step 0: Data Quality Assessment - Result dict validated and ready",
                extra={
                    "step_number": 0,
                    "quality_score": result_dict["quality_score"],
                    "quality_level": quality_level,
                    "result_dict_keys": list(result_dict.keys()),
                    "result_dict_size": len(result_dict),
                    "has_quality_score": "quality_score" in result_dict
                    and result_dict["quality_score"] is not None,
                    "dcf_eligible": result_dict["dcf_eligible"],
                    "dimension_scores": dimension_scores,
                    "dimension_scores_total": (
                        sum(dimension_scores.values()) if isinstance(dimension_scores, dict) else 0
                    ),
                    "warnings_count": len(warnings),
                    "recommendations_count": len(recommendations),
                },
            )

            # Quality score breakdown is debug-level diagnostic data; the
            # EXECUTION COMPLETE exit log already carries the headline score
            # and dimension breakdown.
            logger.debug(
                "🔍 Step 0: Quality Score Calculation Breakdown",
                extra={
                    "step_number": 0,
                    "quality_score": quality_score,
                    "quality_score_type": type(quality_score).__name__,
                    "dimension_scores": dimension_scores,
                    "completeness": (
                        dimension_scores.get("completeness", 0)
                        if isinstance(dimension_scores, dict)
                        else 0
                    ),
                    "validity": (
                        dimension_scores.get("validity", 0)
                        if isinstance(dimension_scores, dict)
                        else 0
                    ),
                    "consistency": (
                        dimension_scores.get("consistency", 0)
                        if isinstance(dimension_scores, dict)
                        else 0
                    ),
                    "accuracy": (
                        dimension_scores.get("accuracy", 0)
                        if isinstance(dimension_scores, dict)
                        else 0
                    ),
                    "timeliness": (
                        dimension_scores.get("timeliness", 0)
                        if isinstance(dimension_scores, dict)
                        else 0
                    ),
                    "total_dimension_scores": (
                        sum(dimension_scores.values()) if isinstance(dimension_scores, dict) else 0
                    ),
                    "warnings_count": len(warnings),
                    "recommendations_count": len(recommendations),
                    "has_revenue": hasattr(request, "current_year_data")
                    and request.current_year_data
                    and getattr(request.current_year_data, "revenue", None) is not None,
                    "has_ebitda": hasattr(request, "current_year_data")
                    and request.current_year_data
                    and getattr(request.current_year_data, "ebitda", None) is not None,
                    "historical_years_count": (
                        len(getattr(request, "historical_years_data", []))
                        if getattr(request, "historical_years_data", None)
                        else 0
                    ),
                },
            )

            logger.debug("[STEP-0-RETURN] Returning successful result with COMPLETED status")

            # Calculate total execution time
            step_total_duration = time.time() - step_start_time

            # Build StepOutput
            output = self.result_builder.build_step_output(
                result_dict=result_dict,
                dcf_eligible=dcf_eligible,
                warnings=warnings,
                quality_level=quality_level,
                dcf_exclusion_reason=dcf_exclusion_reason,
                step_total_duration=step_total_duration,
                assess_quality_duration=assess_quality_duration,
                sub_calculations=sub_calculations,
                step_number=0,
            )

            # Log exit with summary and timing
            logger.info(
                "✅ Step 0: Data Quality Assessment - EXECUTION COMPLETE",
                extra={
                    "step_number": 0,
                    "step_name": self.step_name,
                    "status": "COMPLETED",
                    "total_duration_seconds": round(step_total_duration, 3),
                    "assess_quality_duration_seconds": (
                        round(assess_quality_duration, 3) if assess_quality_duration else None
                    ),
                    "quality_score": int(quality_score),
                    "quality_level": quality_level,
                    "dcf_eligible": dcf_eligible,
                    "dcf_exclusion_reason": dcf_exclusion_reason,
                    "multiples_method": multiples_method,
                    "dimension_scores": dimension_scores,
                    "warnings_count": len(warnings),
                    "recommendations_count": len(recommendations),
                    "company_name": getattr(request, "company_name", "N/A"),
                },
            )

            # Alert if Step 0 takes too long
            if step_total_duration > 5.0:
                logger.warning(
                    "⚠️ Step 0 total execution took longer than 5 seconds",
                    extra={
                        "step_number": 0,
                        "total_duration_seconds": round(step_total_duration, 3),
                        "threshold_seconds": Decimal("5.0"),
                    },
                )

            logger.debug(f"[STEP-0-RETURN] Returning output with status: {output.status.value}")
            return output

        except AttributeError as e:
            # CRITICAL FIX: Catch AttributeError specifically
            logger.error(
                "❌ CRITICAL: Step 0 AttributeError, returning fallback StepOutput",
                extra={
                    "step_number": 0,
                    "step_name": self.step_name,
                    "error_type": "AttributeError",
                    "error_message": str(e),
                    "error_attr": str(e).split("'")[1] if "'" in str(e) else None,
                    "company_name": (
                        getattr(request, "company_name", "N/A") if "request" in locals() else "N/A"
                    ),
                    "business_type_id": (
                        getattr(request, "business_type_id", "N/A")
                        if "request" in locals()
                        else "N/A"
                    ),
                },
                exc_info=True,
            )
            return self.fallback_handler.create_fallback_step_output(
                str(e), "AttributeError", step_number=0
            )

        except KeyError as e:
            # CRITICAL FIX: Catch KeyError specifically
            logger.error(
                "❌ CRITICAL: Step 0 KeyError, returning fallback StepOutput",
                extra={
                    "step_number": 0,
                    "step_name": self.step_name,
                    "error_type": "KeyError",
                    "error_message": str(e),
                    "missing_key": (
                        str(e).strip("'\"")
                        if str(e).startswith("'") or str(e).startswith('"')
                        else str(e)
                    ),
                    "company_name": (
                        getattr(request, "company_name", "N/A") if "request" in locals() else "N/A"
                    ),
                },
                exc_info=True,
            )
            return self.fallback_handler.create_fallback_step_output(
                str(e), "KeyError", step_number=0
            )

        except TypeError as e:
            # CRITICAL FIX: Catch TypeError specifically
            logger.error(
                "❌ CRITICAL: Step 0 TypeError, returning fallback StepOutput",
                extra={
                    "step_number": 0,
                    "step_name": self.step_name,
                    "error_type": "TypeError",
                    "error_message": str(e),
                    "company_name": (
                        getattr(request, "company_name", "N/A") if "request" in locals() else "N/A"
                    ),
                },
                exc_info=True,
            )
            return self.fallback_handler.create_fallback_step_output(
                str(e), "TypeError", step_number=0
            )

        except Exception as e:
            logger.error(
                "❌ CRITICAL: Step 0 execution failed with unexpected exception, returning fallback StepOutput",
                extra={
                    "step_number": 0,
                    "step_name": self.step_name,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "company_name": (
                        getattr(request, "company_name", "N/A") if "request" in locals() else "N/A"
                    ),
                    "business_type_id": (
                        getattr(request, "business_type_id", "N/A")
                        if "request" in locals()
                        else "N/A"
                    ),
                },
                exc_info=True,
            )
            return self.fallback_handler.create_fallback_step_output(
                str(e), type(e).__name__, step_number=0
            )
