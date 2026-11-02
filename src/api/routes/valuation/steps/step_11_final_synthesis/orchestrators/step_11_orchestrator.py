"""
Step 11 Orchestrator

Orchestrates the main execution flow for Step 11 Final Synthesis.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from src.domain.valuation_contract import is_sde_method_key, resolve_effective_method_key
from src.errors.error_types import TemplateRenderError
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

from ...base_step import StepInput, StepOutput, StepStatus
from ..builders.step_11_metadata_builder import Step11MetadataBuilder
from ..builders.step_11_result_builder import Step11ResultBuilder
from ..handlers.step_11_error_handler import Step11ErrorHandler
from .step_11_completion_logging import log_completion_summary

logger = get_logger(__name__)


class Step11Orchestrator:
    """Orchestrates the main execution flow for Step 11."""

    def __init__(
        self,
        step_name: str,
        range_calculator: any,
        confidence_calculator: any,
        adjustment_calculator: any,
        validator: any,
        methodology_builder: any,
        transparency_builder: any,
        synthesis_orchestrator: any,
        get_previous_step_result_func: any,
        error_handler: Step11ErrorHandler,
        result_builder: Step11ResultBuilder,
        metadata_builder: Step11MetadataBuilder,
    ):
        """
        Initialize the orchestrator.

        Args:
            step_name: Step name for StepOutput
            range_calculator: RangeCalculator instance
            confidence_calculator: ConfidenceCalculator instance
            adjustment_calculator: AdjustmentCalculator instance
            validator: SynthesisValidator instance
            methodology_builder: MethodologyBuilder instance
            transparency_builder: TransparencyBuilder instance
            synthesis_orchestrator: SynthesisOrchestrator instance (from step_11_synthesis)
            get_previous_step_result_func: Function to get previous step result
            error_handler: Step11ErrorHandler instance
            result_builder: Step11ResultBuilder instance
            metadata_builder: Step11MetadataBuilder instance
        """
        self.step_name = step_name
        self.range_calculator = range_calculator
        self.confidence_calculator = confidence_calculator
        self.adjustment_calculator = adjustment_calculator
        self.validator = validator
        self.methodology_builder = methodology_builder
        self.transparency_builder = transparency_builder
        self.synthesis_orchestrator = synthesis_orchestrator
        self.get_previous_step_result = get_previous_step_result_func
        self.error_handler = error_handler
        self.result_builder = result_builder
        self.metadata_builder = metadata_builder

    @staticmethod
    def _normalize_confidence_score(raw_score: object, default: int = 66) -> int:
        """Normalize confidence score to integer percentage."""
        if raw_score is None:
            return default
        try:
            score_decimal = to_decimal(raw_score)
        except (ValueError, TypeError):
            return default
        if Decimal("0") <= score_decimal <= Decimal("1"):
            score = int(score_decimal * Decimal("100"))
        else:
            score = int(round(score_decimal))
        return max(0, min(100, score))

    @staticmethod
    def _first_present(*values: Any) -> Any:
        """Return the first explicitly present value, preserving zero."""
        for value in values:
            if value is not None:
                return value
        return None

    async def orchestrate_execution(
        self, input_data: StepInput, request: any, correlation_id: Optional[str]
    ) -> StepOutput:
        """
        Orchestrate the main execution flow.

        Args:
            input_data: StepInput with previous results
            request: Valuation request
            correlation_id: Correlation ID for tracing

        Returns:
            StepOutput with calculation results
        """
        try:
            logger.info(
                "🔍 Starting Step 11: Final Valuation Synthesis",
                extra={
                    "step_number": 11,
                    "step_name": self.step_name,
                    "company_name": getattr(request, "company_name", "N/A"),
                    "available_previous_steps": list(input_data.previous_results.keys()),
                    "dependencies": [10],
                },
            )

            # Extract valuation range using synthesis orchestrator
            step10_result = self.get_previous_step_result(10, input_data.previous_results)
            step10_output = input_data.previous_results.get(10)
            step10_failed = (
                step10_output is None
                or step10_output.status != StepStatus.COMPLETED
                or input_data.context.get("step10_failed", False)
            )

            use_fallback = not step10_result or step10_failed
            if use_fallback:
                logger.warning(
                    "⚠️ Step 10 results not available or Step 10 failed, using fallback logic",
                    extra={
                        "step_number": 11,
                        "available_steps": list(input_data.previous_results.keys()),
                        "step10_status": (
                            step10_output.status.value if step10_output else "not_found"
                        ),
                        "using_fallback": True,
                    },
                )

            (
                valuation_low,
                valuation_mid,
                valuation_high,
                use_fallback,
                step10_values_preserved,
                equity_source,
                equity_value_mid,
            ) = self.synthesis_orchestrator.extract_valuation_range(input_data, use_fallback)

            value_chain_validated = step10_values_preserved

            # Final validation - ensure we have valid values
            if valuation_mid <= 0:
                logger.error(
                    "❌ Step 11: No valid valuation could be determined",
                    extra={
                        "step_number": 11,
                        "use_fallback": use_fallback,
                        "available_steps": list(input_data.previous_results.keys()),
                    },
                )
                valuation_mid = Decimal("0.01")
                valuation_low = Decimal("0.0")
                valuation_high = Decimal("0.01")
                use_fallback = True

            # ─── SDE cross-check integration ───────────────────────────
            # If Step 2.7 produced an SDE valuation, blend it in.
            # When the user *explicitly* selected sde_multiple the SDE
            # valuation is the primary anchor (weight=1.0), not merely a
            # revenue-dependent cross-check.
            sde_cross_check = None
            active_method_key = resolve_effective_method_key(
                getattr(request, "selected_method", None),
                getattr(request, "method_override_selected_method", None),
                getattr(request, "primary_method_key", None),
            )
            user_selected_sde = is_sde_method_key(active_method_key)
            sde_low, sde_mid, sde_high, sde_source = (
                self.synthesis_orchestrator.extract_sde_valuation(input_data.previous_results)
            )
            sde_blend_applied = False
            if sde_mid is not None and sde_mid > 0:
                if user_selected_sde:
                    sde_weight = Decimal("1.0")
                else:
                    revenue = Decimal("0")
                    step1_result = self.get_previous_step_result(1, input_data.previous_results)
                    if step1_result:
                        revenue = to_decimal(step1_result.get("revenue", 0))

                    if revenue < Decimal("500000"):
                        sde_weight = Decimal("0.40")
                    elif revenue < Decimal("2000000"):
                        sde_weight = Decimal("0.25")
                    else:
                        sde_weight = Decimal("0")

                if sde_weight > 0:
                    sde_blend_applied = True
                    valuation_mid, valuation_low, valuation_high, sde_breakdown = (
                        self.synthesis_orchestrator.synthesize_with_sde(
                            valuation_mid,
                            valuation_low,
                            valuation_high,
                            sde_mid,
                            sde_low,
                            sde_high,
                            sde_weight=sde_weight,
                        )
                    )
                    # CRITICAL: SDE blend rewrites the entire (low, mid, high)
                    # band. The "Step 10 preserved" assumption from
                    # `extract_valuation_range` no longer holds — the band is
                    # now a weighted combination of EBITDA-equity and SDE-EV
                    # ranges, which can break the low <= mid <= high invariant
                    # (especially for micro-businesses where EBITDA mid and
                    # SDE mid diverge sharply). Force the ordering check to
                    # run by clearing the preserved flag. See the photography
                    # regression for the failure mode this guards against.
                    step10_values_preserved = False
                    value_chain_validated = False
                    sde_cross_check = {
                        "applied": True,
                        "user_selected_sde": user_selected_sde,
                        "sde_mid": float(sde_mid),
                        "sde_low": float(sde_low) if sde_low else None,
                        "sde_high": float(sde_high) if sde_high else None,
                        "sde_weight": float(sde_weight),
                        "source": sde_source,
                        "breakdown": sde_breakdown,
                    }
                else:
                    sde_cross_check = {
                        "applied": False,
                        "sde_mid": float(sde_mid),
                        "reason": "Revenue >= EUR 2M; SDE not weighted in",
                    }

            # Store original values before processing
            original_low = valuation_low
            original_mid = valuation_mid
            original_high = valuation_high

            # Log original values before any processing
            source_label = (
                "fallback"
                if use_fallback
                else ("SDE-blended Step 10" if sde_blend_applied else "Step 10")
            )
            logger.info(
                f"📊 Step 11: Original values from {source_label} (before rounding)",
                extra={
                    "valuation_low": valuation_low,
                    "valuation_mid": valuation_mid,
                    "valuation_high": valuation_high,
                    "source": source_label,
                    "sde_cross_check_applied": (
                        sde_cross_check.get("applied") if sde_cross_check else False
                    ),
                },
            )

            # Validate and fix ordering before rounding
            valuation_low, valuation_mid, valuation_high = (
                self.synthesis_orchestrator.validate_and_fix_ordering(
                    valuation_low,
                    valuation_mid,
                    valuation_high,
                    step10_values_preserved,
                    use_fallback,
                    step10_result,
                )
            )

            # Apply rounding
            rounding_anchor = valuation_mid if sde_blend_applied else equity_value_mid
            valuation_low, valuation_mid, valuation_high, rounding_details = (
                self.synthesis_orchestrator.apply_rounding(
                    valuation_low, valuation_mid, valuation_high, rounding_anchor
                )
            )

            # Final ordering validation after rounding (if needed)
            if not step10_values_preserved:
                valuation_low, valuation_mid, valuation_high = (
                    self.synthesis_orchestrator.validate_and_fix_ordering(
                        valuation_low,
                        valuation_mid,
                        valuation_high,
                        step10_values_preserved,
                        use_fallback,
                        step10_result,
                    )
                )

            # Extract confidence score (needed before asking price for markup fallback)
            confidence_data = self.confidence_calculator.extract_confidence(
                input_data.previous_results
            )
            confidence_score_raw = confidence_data.get("overall_score", 66)
            confidence_score = self._normalize_confidence_score(confidence_score_raw)
            confidence_level = confidence_data.get("level", "MEDIUM")

            # Calculate asking price -- use explicit markup from context, or fall back
            # to the confidence-based academic markup (Pratt & Niculita, IBBA 2024).
            # Pass-5: respect advisor override on the request when context didn't
            # already inject an explicit markup.
            raw_markup = input_data.context.get("asking_price_markup")
            asking_price_markup = (
                Decimal(str(raw_markup))
                if raw_markup is not None and raw_markup != 0
                else Decimal("0.0")
            )
            if asking_price_markup <= 0:
                from src.config.valuation_constants import get_asking_price_markup

                asking_price_markup = get_asking_price_markup(
                    confidence_level,
                    advisor_override_pct=getattr(request, "asking_price_buffer_pct", None),
                ) - Decimal("1")

            current_multiple = None
            step7_result = self.get_previous_step_result(7, input_data.previous_results)
            if step7_result:
                current_multiple = self._first_present(
                    step7_result.get("final_multiple"),
                    step7_result.get("adjusted_multiple"),
                )

            asking_price, asking_multiple = self.adjustment_calculator.calculate_asking_price(
                valuation_mid, asking_price_markup, current_multiple=current_multiple
            )

            # Extract methodology information
            methodologies = self.methodology_builder.extract_methodologies(
                input_data.previous_results
            )

            # Generate dynamic methodology statement and academic sources
            from src.domain.methodology_source_registry import get_methodology_source_registry

            source_registry = get_methodology_source_registry()
            methodology_statement = self.methodology_builder.generate_methodology_statement(
                methodologies, source_registry, input_data.previous_results, request=request
            )
            academic_sources = self.methodology_builder.generate_academic_sources(
                methodologies, source_registry
            )

            # Final quality checkpoint
            quality_checkpoint = self.validator.validate_quality_checkpoint(
                request, input_data.previous_results
            )

            # Assess professional review readiness
            professional_review_ready = (
                self.methodology_builder.assess_professional_review_readiness(
                    input_data.previous_results, quality_checkpoint
                )
            )

            # Generate transparency report with error handling
            transparency = self._generate_transparency_report(
                input_data,
                methodologies,
                methodology_statement,
                academic_sources,
                professional_review_ready,
            )

            logger.info(
                f"✓ Final valuation: €{valuation_low:,.0f} - €{valuation_high:,.0f}",
                extra={
                    "valuation_low": valuation_low,
                    "valuation_mid": valuation_mid,
                    "valuation_high": valuation_high,
                    "asking_price": asking_price,
                },
            )

            # Build multiple discount pipeline
            multiple_pipeline = self.transparency_builder.build_multiple_pipeline(
                input_data.previous_results, self.get_previous_step_result
            )

            # Perform validations
            multiple_range_validation, total_discount_validation = self._perform_validations(
                input_data, multiple_pipeline
            )

            # Build rounding details
            rounding_details_dict = self.metadata_builder.add_rounding_details(
                original_low,
                original_mid,
                original_high,
                valuation_low,
                valuation_mid,
                valuation_high,
            )

            # Build metadata
            metadata = self.metadata_builder.build_metadata_dict(
                valuation_low,
                valuation_mid,
                valuation_high,
                original_low,
                original_mid,
                original_high,
                rounding_details_dict,
                value_chain_validated,
                equity_value_mid,
                use_fallback,
                quality_checkpoint,
                methodologies,
                academic_sources,
                professional_review_ready,
            )

            # Build result
            result = self.result_builder.build_result_dict(
                valuation_low,
                valuation_mid,
                valuation_high,
                asking_price,
                confidence_score,
                confidence_level,
                methodology_statement,
                academic_sources,
                professional_review_ready,
                transparency,
                multiple_pipeline,
                multiple_range_validation,
                total_discount_validation,
                recommended_asking_multiple=asking_multiple,
                sde_cross_check=sde_cross_check,
                value_chain_validated=value_chain_validated,
            )

            # Comprehensive summary
            log_completion_summary(
                input_data=input_data,
                valuation_low=valuation_low,
                valuation_mid=valuation_mid,
                valuation_high=valuation_high,
                asking_price=asking_price,
                confidence_score=confidence_score,
                confidence_level=confidence_level,
                methodologies=methodologies,
                academic_sources=academic_sources,
                professional_review_ready=professional_review_ready,
                value_chain_validated=value_chain_validated,
                rounding_details=rounding_details_dict,
                use_fallback=use_fallback,
                request=request,
            )

            return StepOutput(
                step_number=11,
                step_name=self.step_name,
                status=StepStatus.COMPLETED,
                result=result,
                metadata=metadata,
            )

        except Exception as e:
            return self.error_handler.handle_execution_exception(
                e, request, input_data, self.range_calculator
            )

    def _generate_transparency_report(
        self,
        input_data: StepInput,
        methodologies: Dict[str, Any],
        methodology_statement: str,
        academic_sources: list,
        professional_review_ready: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate transparency report with error handling.

        Args:
            input_data: StepInput with previous results
            methodologies: Methodologies dict
            methodology_statement: Methodology statement
            academic_sources: List of academic sources
            professional_review_ready: Professional review readiness dict

        Returns:
            Transparency report dictionary
        """
        transparency = None
        transparency_generation_error = None
        try:
            # Log which steps are in previous_results
            steps_in_previous = list(input_data.previous_results.keys())
            steps_status = {
                step_num: {
                    "status": result.status.value,
                    "step_name": result.step_name,
                    "has_result": hasattr(result, "result") and bool(result.result),
                    "result_keys": (
                        list(result.result.keys())
                        if hasattr(result, "result") and isinstance(result.result, dict)
                        else []
                    ),
                }
                for step_num, result in input_data.previous_results.items()
            }

            logger.debug(
                "🔍 Generating transparency report for Step 11",
                extra={
                    "step_number": 11,
                    "previous_results_count": len(input_data.previous_results),
                    "steps_in_previous_results": steps_in_previous,
                    "steps_status": steps_status,
                    "has_methodologies": methodologies is not None,
                    "has_academic_sources": academic_sources is not None,
                    "missing_steps": [i for i in range(12) if i not in steps_in_previous],
                },
            )

            transparency = self.transparency_builder.generate_transparency_report(
                input_data.previous_results,
                methodologies,
                methodology_statement,
                academic_sources,
                professional_review_ready,
            )

            # Log detailed transparency report contents
            calculation_steps_count = (
                len(transparency.get("calculation_steps", [])) if transparency else 0
            )
            step_numbers_in_report = (
                [step.get("step") for step in transparency.get("calculation_steps", [])]
                if transparency
                else []
            )

            logger.info(
                "✅ Transparency report generated successfully",
                extra={
                    "step_number": 11,
                    "has_calculation_steps": (
                        "calculation_steps" in transparency if transparency else False
                    ),
                    "calculation_steps_count": calculation_steps_count,
                    "step_numbers_in_report": step_numbers_in_report,
                    "has_confidence_breakdown": (
                        "confidence_breakdown" in transparency if transparency else False
                    ),
                    "has_academic_sources": (
                        "academic_sources" in transparency if transparency else False
                    ),
                    "confidence_breakdown_keys": (
                        list(transparency.get("confidence_breakdown", {}).keys())
                        if transparency
                        else []
                    ),
                },
            )
        except TemplateRenderError as e:
            transparency_generation_error = str(e)
            logger.error(
                "❌ Failed to generate transparency report, creating fallback",
                extra={"step_number": 11, "error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            # Create minimal transparency report as fallback
            transparency = {
                "calculation_steps": [],
                "confidence_breakdown": {},
                "academic_sources": [],
                "data_sources": [],
                "methodology": "Fallback - generation failed",
                "error": str(e),
                "generated_at": datetime.now().isoformat(),
            }
            logger.warning(
                "⚠️ Using fallback transparency report",
                extra={"step_number": 11, "fallback_reason": transparency_generation_error},
            )

        return transparency

    def _perform_validations(
        self, input_data: StepInput, multiple_pipeline: Optional[Dict[str, Any]]
    ) -> tuple:
        """
        Perform multiple range and discount validations.

        Args:
            input_data: StepInput with previous results
            multiple_pipeline: Multiple pipeline dictionary

        Returns:
            Tuple of (multiple_range_validation, total_discount_validation)
        """
        multiple_range_validation = None
        total_discount_validation = None

        final_mult = (
            (
                self._first_present(
                    multiple_pipeline.get("final_multiple_mid"),
                    multiple_pipeline.get("final_multiple"),
                )
            )
            if multiple_pipeline
            else None
        )
        initial_mult = (
            (
                self._first_present(
                    multiple_pipeline.get("initial_multiple_mid"),
                    multiple_pipeline.get("initial_multiple"),
                )
            )
            if multiple_pipeline
            else None
        )
        metric_type = str((multiple_pipeline or {}).get("metric_type") or "").upper()
        is_ebitda_pipeline = "EBITDA" in metric_type

        if multiple_pipeline and final_mult:
            # Get revenue and industry from previous steps
            step1 = input_data.previous_results.get(1)
            step2 = input_data.previous_results.get(2)

            if step1 and step2:
                revenue = (
                    step1.result.get("revenue", Decimal("0.0")) if step1.result else Decimal("0.0")
                )
                industry = (
                    getattr(input_data.request, "industry", "unknown")
                    if hasattr(input_data, "request")
                    else "unknown"
                )
                business_category = step2.result.get("business_category") if step2.result else None

                if is_ebitda_pipeline:
                    multiple_range_validation = self.validator.validate_final_multiple_range(
                        final_multiple=final_mult,
                        revenue=revenue,
                        industry=industry,
                        business_category=business_category,
                    )
                else:
                    multiple_range_validation = {
                        "is_valid": True,
                        "skipped": True,
                        "reason": (
                            "EBITDA target-range validation does not apply to "
                            f"{metric_type or 'non-EBITDA'} multiple pipelines"
                        ),
                        "metric_type": metric_type,
                        "final_multiple": final_mult,
                    }
                    logger.info(
                        "Step 11 multiple range validation skipped for non-EBITDA pipeline",
                        extra={"step_number": 11, **multiple_range_validation},
                    )

        if multiple_pipeline and initial_mult and final_mult:
            step1 = input_data.previous_results.get(1)
            step4 = input_data.previous_results.get(4)

            if step1:
                revenue = (
                    step1.result.get("revenue", Decimal("0.0")) if step1.result else Decimal("0.0")
                )

                if is_ebitda_pipeline:
                    is_sole_trader = False
                    if step4 and step4.result:
                        risk_level = step4.result.get("risk_level", "")
                        is_sole_trader = risk_level == "SOLE_TRADER"

                    total_discount_validation = self.validator.validate_total_discount(
                        initial_multiple=initial_mult,
                        final_multiple=final_mult,
                        revenue=revenue,
                        is_sole_trader=is_sole_trader,
                    )
                else:
                    total_discount_validation = {
                        "is_valid": True,
                        "skipped": True,
                        "reason": (
                            "EBITDA discount-stack validation does not apply to "
                            f"{metric_type or 'non-EBITDA'} multiple pipelines"
                        ),
                        "metric_type": metric_type,
                        "initial_multiple": initial_mult,
                        "final_multiple": final_mult,
                        "revenue": revenue,
                    }
                    logger.info(
                        "Step 11 total discount validation skipped for non-EBITDA pipeline",
                        extra={"step_number": 11, **total_discount_validation},
                    )

        return multiple_range_validation, total_discount_validation
