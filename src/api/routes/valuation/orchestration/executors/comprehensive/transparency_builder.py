"""
Transparency Builder for Comprehensive Valuation

Builds TransparencyData from Step 11 transparency reports, step results,
and valuation data. Handles Step 11 transparency report processing,
StepOutput to CalculationStep conversion, and fallback transparency generation.
"""

from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.api.routes.valuation.steps.base_step import StepOutput, StepStatus
from src.api.schemas import ValuationRequest
from src.config import get_settings
from src.domain.transparency import (
    CalculationStep,
    MarketDataDetails,
    TransparencyData,
    ValidationCheck,
    ValidationReport,
)
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.valuation_logger import ValuationLogger

from .transparency_validation_checks import build_validation_checks


class TransparencyBuilder:
    """
    Builds transparency data for comprehensive valuation.

    Responsibilities:
    - Process Step 11 transparency reports
    - Convert StepOutput to CalculationStep objects
    - Build MarketDataDetails
    - Build ValidationReport
    - Handle fallback transparency generation
    """

    def __init__(
        self,
        transparency_builder,  # Existing TransparencyBuilder from orchestration/builders
        logger: Optional[ValuationLogger] = None,
    ):
        """
        Initialize comprehensive transparency builder.

        Args:
            transparency_builder: Existing TransparencyBuilder instance
            logger: Optional logger instance
        """
        self.transparency_builder = transparency_builder
        self.logger = logger or ValuationLogger(self.__class__.__name__)

    def build_transparency_data(
        self,
        request: ValuationRequest,
        detailed_results: Dict[str, Any],
        confidence_score: Decimal,
        correlation_id: str,
    ) -> TransparencyData:
        """
        Build transparency data from Step 11 report or step results.

        Args:
            request: Valuation request
            detailed_results: Detailed valuation results
            confidence_score: Confidence score
            correlation_id: Correlation ID

        Returns:
            TransparencyData object
        """
        multiples_results = detailed_results.get("multiples_valuation", {})
        revenue = request.current_year_data.revenue
        ebitda = request.current_year_data.ebitda

        # Check if multiples_results contains Step 11's transparency report
        step_11_transparency = (
            multiples_results.get("transparency_report")
            if isinstance(multiples_results, dict)
            else None
        )

        try:
            if step_11_transparency and isinstance(step_11_transparency, dict):
                return self._build_from_step_11_report(
                    request,
                    detailed_results,
                    step_11_transparency,
                    multiples_results,
                    revenue,
                    ebitda,
                    confidence_score,
                )
            else:
                # Extract step_results from multiples_results and convert to CalculationStep objects
                step_results = (
                    multiples_results.get("_step_results")
                    if isinstance(multiples_results, dict)
                    else None
                )
                if step_results:
                    return self._build_from_step_results(
                        request,
                        detailed_results,
                        step_results,
                        multiples_results,
                        revenue,
                        ebitda,
                        confidence_score,
                    )
                else:
                    # Fallback: Build transparency manually
                    return self._build_fallback_transparency(
                        request,
                        detailed_results,
                        multiples_results,
                        revenue,
                        ebitda,
                        confidence_score,
                    )
        except Exception as transparency_error:
            error_msg = (
                str(transparency_error) if transparency_error else "Unknown transparency error"
            )
            self.logger.error(
                "❌ Transparency building failed",
                extra={
                    "error": error_msg,
                    "error_type": type(transparency_error).__name__ if transparency_error else None,
                },
                exc_info=True,
            )
            return self._build_minimal_fallback(request, detailed_results, confidence_score)

    def _extract_market_assumptions(
        self, request: ValuationRequest, detailed_results: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        dcf_valuation = (
            detailed_results.get("dcf_valuation", {}) if isinstance(detailed_results, dict) else {}
        )
        if isinstance(dcf_valuation, dict):
            market_assumptions = dcf_valuation.get("market_assumptions")
            if isinstance(market_assumptions, dict) and market_assumptions:
                return market_assumptions

        economic_context = getattr(request, "economic_context", None) or {}
        if hasattr(economic_context, "model_dump"):
            economic_context = economic_context.model_dump()
        elif not isinstance(economic_context, dict):
            economic_context = {}

        risk_free_rate = (
            getattr(request, "government_bond_yield", None)
            if getattr(request, "government_bond_yield", None) is not None
            else economic_context.get("risk_free_rate")
        )
        equity_risk_premium = (
            getattr(request, "equity_risk_premium", None)
            if getattr(request, "equity_risk_premium", None) is not None
            else (
                economic_context.get("equity_risk_premium")
                if economic_context.get("equity_risk_premium") is not None
                else (
                    economic_context.get("market_risk_premium")
                    if economic_context.get("market_risk_premium") is not None
                    else economic_context.get("erp")
                )
            )
        )
        gdp_growth_rate = (
            getattr(request, "long_term_gdp_growth", None)
            if getattr(request, "long_term_gdp_growth", None) is not None
            else (
                economic_context.get("gdp_growth_rate")
                if economic_context.get("gdp_growth_rate") is not None
                else economic_context.get("terminal_growth_rate")
            )
        )

        return {
            "risk_free_rate": risk_free_rate,
            "risk_free_rate_source": (
                "request_override"
                if getattr(request, "government_bond_yield", None) is not None
                else (
                    economic_context.get("risk_free_rate_source")
                    if risk_free_rate is not None
                    else None
                )
            ),
            "equity_risk_premium": equity_risk_premium,
            "equity_risk_premium_source": (
                "request_override"
                if getattr(request, "equity_risk_premium", None) is not None
                else economic_context.get("source") if equity_risk_premium is not None else None
            ),
            "gdp_growth_rate": gdp_growth_rate,
            "gdp_growth_source": (
                "request_override"
                if getattr(request, "long_term_gdp_growth", None) is not None
                else economic_context.get("source") if gdp_growth_rate is not None else None
            ),
            "inflation_rate": economic_context.get("inflation_rate"),
            "valuation_date": None,
        }

    def _build_market_data_details(
        self,
        *,
        request: ValuationRequest,
        detailed_results: Optional[Dict[str, Any]],
        multiples_results: Dict[str, Any],
        multiples_source: str,
    ) -> MarketDataDetails:
        revenue_multiple = multiples_results.get("revenue_multiple", Decimal("0.5"))
        ebitda_multiple = multiples_results.get("ebitda_multiple", Decimal("5.0"))
        market_assumptions = self._extract_market_assumptions(request, detailed_results)
        # A governed risk-free observation has its own measurement date.  It
        # must not be relabelled with the report generation date or a resolver
        # clock when the sealed DCF input already supplies the exact date.
        valuation_date = market_assumptions.get(
            "risk_free_rate_observed_at"
        ) or market_assumptions.get("valuation_date")
        try:
            rate_date = date.fromisoformat(valuation_date) if valuation_date else date.today()
        except (TypeError, ValueError):
            rate_date = date.today()

        return MarketDataDetails(
            industry_multiples={
                "ev_ebitda_median": to_decimal(ebitda_multiple),
                "ev_revenue_median": to_decimal(revenue_multiple),
            },
            multiples_source=multiples_source,
            multiples_date=date.today(),
            multiples_sample_size=multiples_results.get("comparables_count", 0) or 0,
            risk_free_rate=to_decimal(market_assumptions.get("risk_free_rate") or 0),
            risk_free_rate_source=str(
                market_assumptions.get("risk_free_rate_source") or "unresolved"
            ),
            risk_free_rate_date=rate_date,
            market_risk_premium=to_decimal(market_assumptions.get("equity_risk_premium") or 0),
            market_risk_premium_source=str(
                market_assumptions.get("equity_risk_premium_source") or "unresolved"
            ),
            gdp_growth_rate=(
                to_decimal(market_assumptions.get("gdp_growth_rate"))
                if market_assumptions.get("gdp_growth_rate") is not None
                else None
            ),
            gdp_growth_source=str(market_assumptions.get("gdp_growth_source") or "unresolved"),
            comparable_companies=[],
        )

    def _build_from_step_11_report(
        self,
        request: ValuationRequest,
        detailed_results: Dict[str, Any],
        step_11_transparency: Dict[str, Any],
        multiples_results: Dict[str, Any],
        revenue: Decimal,
        ebitda: Optional[Decimal],
        confidence_score: Decimal,
    ) -> TransparencyData:
        """Build transparency from Step 11 transparency report."""
        self.logger.debug(
            "✅ Using Step 11 transparency report (includes Step 0 data quality)",
            extra={
                "has_calculation_steps": "calculation_steps" in step_11_transparency,
                "calculation_steps_count": len(step_11_transparency.get("calculation_steps", [])),
                "has_step_0": any(
                    step.get("step") == 0
                    for step in step_11_transparency.get("calculation_steps", [])
                ),
            },
        )

        # Extract Step 0 data quality from Step 11's transparency report
        calculation_steps = step_11_transparency.get("calculation_steps", [])
        step_0_data = None
        for step in calculation_steps:
            if step.get("step") == 0:
                step_0_data = step.get("key_outputs", {})
                self.logger.debug(
                    "✅ Step 0 data quality found in transparency report",
                    extra={
                        "quality_score": step_0_data.get("quality_score"),
                        "dcf_eligible": step_0_data.get("dcf_eligible"),
                        "quality_level": step_0_data.get("quality_level"),
                    },
                )
                break

        # Convert Step 11's transparency report to CalculationStep objects
        calculation_step_objects = []
        steps_processed = []
        steps_failed = []

        self.logger.debug(
            "🔍 Processing transparency calculation steps",
            extra={
                "total_steps_received": len(calculation_steps),
                "step_numbers_received": [step.get("step") for step in calculation_steps],
                "expected_steps": list(range(12)),
            },
        )

        for step in calculation_steps:
            try:
                step_num = step.get("step")
                steps_processed.append(step_num)

                key_outputs = step.get("key_outputs", {})
                # For Step 0, extract quality_score as output
                if step_num == 0:
                    output_value = to_decimal(key_outputs.get("quality_score", 0))
                else:
                    # For other steps, try to extract numeric output
                    output_value = Decimal("0.0")
                    if isinstance(key_outputs, dict):
                        # Try common output field names
                        for field in [
                            "equity_value_mid",
                            "enterprise_value_mid",
                            "valuation_mid",
                            "output",
                        ]:
                            if field in key_outputs and isinstance(
                                key_outputs[field], (int, float)
                            ):
                                output_value = to_decimal(key_outputs[field])
                                break

                calc_step = CalculationStep(
                    step_number=int(step_num),
                    calculation_name=str(step.get("name", f"Step {step_num}")),
                    formula=str(step.get("description", "")),
                    inputs={},  # Step 11's transparency doesn't include detailed inputs
                    output=output_value,
                    output_formatted=(
                        f"{output_value:.1f}%"
                        if step_num == 0
                        else f"€{output_value:,.0f}" if output_value > 0 else "€0"
                    ),
                    explanation=str(step.get("description", "")),
                    calculation_type=str(step.get("name", "unknown")).lower().replace(" ", "_"),
                )
                calculation_step_objects.append(calc_step)
            except Exception as step_error:
                steps_failed.append(step.get("step"))
                self.logger.warning(
                    f"Failed to convert transparency step to CalculationStep: {step_error}",
                    extra={
                        "step": step,
                        "error_type": type(step_error).__name__,
                        "error_message": str(step_error),
                    },
                )

        # Verify we processed all expected steps
        expected_steps = set(range(12))
        processed_steps = set(steps_processed)
        missing_steps = expected_steps - processed_steps

        if missing_steps:
            self.logger.error(
                "❌ CRITICAL: Not all steps were processed from transparency report!",
                extra={
                    "expected_steps": sorted(expected_steps),
                    "processed_steps": sorted(processed_steps),
                    "missing_steps": sorted(missing_steps),
                    "steps_failed": steps_failed,
                    "total_processed": len(calculation_step_objects),
                },
            )
        else:
            self.logger.debug(
                "✅ All 12 steps processed from transparency report",
                extra={
                    "total_steps_processed": len(calculation_step_objects),
                    "steps_processed": sorted(steps_processed),
                    "steps_failed": steps_failed,
                },
            )

        # Create MarketDataDetails
        data_sources = step_11_transparency.get("data_sources", [])
        data_source = "unknown"
        if data_sources:
            first_source = data_sources[0] if isinstance(data_sources, list) else data_sources
            if isinstance(first_source, dict):
                data_source = first_source.get("source", "unknown")

        market_data = self._build_market_data_details(
            request=request,
            detailed_results=detailed_results,
            multiples_results=multiples_results,
            multiples_source=(
                data_source
                if data_source != "unknown"
                else multiples_results.get("data_source", "industry_defaults")
            ),
        )

        # Create ValidationReport with Step 0 data quality information
        validation_checks = self._build_validation_checks(
            step_0_data, revenue, ebitda, confidence_score
        )

        validation_report = ValidationReport(
            total_checks=len(validation_checks),
            passed=len([c for c in validation_checks if c.status == "passed"]),
            warnings=len([c for c in validation_checks if c.status == "warning"]),
            failed=len([c for c in validation_checks if c.status == "failed"]),
            checks=validation_checks,
            overall_status="passed" if len(validation_checks) > 0 else "passed_with_warnings",
            validation_score=(
                int(step_0_data.get("quality_score", confidence_score * 100))
                if step_0_data
                else int(confidence_score * 100)
            ),
            summary=(
                f"Data quality validation completed. Quality score: {step_0_data.get('quality_score', 'N/A')}%."
                if step_0_data
                else f"Data quality validation completed. {len(validation_checks)} checks performed."
            ),
        )

        # Build transparency object using Step 11's data
        transparency_data = TransparencyData(
            data_provenance={},
            market_data=market_data,
            industry_benchmarks={},
            calculation_steps={"multiples": calculation_step_objects},
            validation_report=validation_report,
        )

        self.logger.debug(
            "✅ Transparency object built from Step 11 report (includes Step 0)",
            extra={
                "steps_count": len(calculation_step_objects),
                "expected_steps": 12,
                "all_steps_present": len(calculation_step_objects) == 12,
                "has_step_0": step_0_data is not None,
                "quality_score": step_0_data.get("quality_score") if step_0_data else None,
                "step_numbers": sorted([step.step_number for step in calculation_step_objects]),
            },
        )

        return transparency_data

    def _build_from_step_results(
        self,
        request: ValuationRequest,
        detailed_results: Dict[str, Any],
        step_results: Dict[int, StepOutput],
        multiples_results: Dict[str, Any],
        revenue: Decimal,
        ebitda: Optional[Decimal],
        confidence_score: Decimal,
    ) -> TransparencyData:
        """Build transparency from step results."""
        self.logger.debug(
            "✅ Converting StepOutput objects to CalculationStep from triage system",
            extra={
                "total_steps": len(step_results),
                "steps_available": list(step_results.keys()),
                "step_types": {k: type(v).__name__ for k, v in step_results.items()},
            },
        )

        # Convert all StepOutput objects (0-11) to CalculationStep
        calculation_step_objects = []
        for step_num in range(12):  # Steps 0-11 (all 12 steps)
            if step_num in step_results:
                step_output = step_results[step_num]
                try:
                    # Verify step_output is a StepOutput object
                    if not hasattr(step_output, "step_number"):
                        self.logger.warning(
                            f"Step {step_num} output is not a StepOutput object",
                            extra={
                                "step_number": step_num,
                                "output_type": type(step_output).__name__,
                                "output_keys": (
                                    list(step_output.keys())
                                    if isinstance(step_output, dict)
                                    else None
                                ),
                            },
                        )
                        # Try to extract from dict if it's a dict
                        if isinstance(step_output, dict):
                            # Create StepOutput from dict
                            step_output = StepOutput(
                                step_number=step_num,
                                step_name=step_output.get("step_name", f"Step {step_num}"),
                                status=StepStatus(step_output.get("status", "completed")),
                                result=step_output.get("result", {}),
                                metadata=step_output.get("metadata", {}),
                                error=step_output.get("error"),
                                execution_time_ms=step_output.get(
                                    "execution_time_ms", Decimal("0.0")
                                ),
                            )

                    calc_step = self.transparency_builder.convert_step_output_to_calculation_step(
                        step_output, step_num
                    )
                    calculation_step_objects.append(calc_step)

                    self.logger.debug(
                        f"✅ Converted Step {step_num} to CalculationStep",
                        extra={
                            "step_number": step_num,
                            "step_name": calc_step.calculation_name,
                            "status": calc_step.status,
                            "has_output": calc_step.output != Decimal("0.0"),
                        },
                    )
                except Exception as conversion_error:
                    self.logger.warning(
                        f"Failed to convert StepOutput for step {step_num}",
                        extra={
                            "step_number": step_num,
                            "error": str(conversion_error),
                            "error_type": type(conversion_error).__name__,
                            "step_output_type": type(step_output).__name__,
                            "step_output_attrs": (
                                [attr for attr in dir(step_output) if not attr.startswith("_")]
                                if hasattr(step_output, "__dict__")
                                else None
                            ),
                        },
                        exc_info=True,
                    )
                    # Create a minimal CalculationStep for failed conversion
                    calc_step = CalculationStep(
                        step_number=step_num,
                        calculation_name=(
                            step_output.step_name
                            if hasattr(step_output, "step_name")
                            else f"Step {step_num}"
                        ),
                        formula="Conversion failed",
                        inputs={},
                        output=Decimal("0.0"),
                        output_formatted="€0",
                        explanation=f"Step conversion failed: {str(conversion_error)}",
                        calculation_type=f"step_{step_num}",
                        status="failed",
                        error=str(conversion_error),
                    )
                    calculation_step_objects.append(calc_step)
            else:
                # Step was not executed - create skipped step
                step_details = multiples_results.get("modular_system", {}).get("step_details", [])
                step_detail = next((s for s in step_details if s.get("step") == step_num), None)

                skip_reason = "Step not executed by triage system"
                if step_detail:
                    skip_reason = (
                        step_detail.get("reason") or step_detail.get("error") or skip_reason
                    )

                calc_step = CalculationStep(
                    step_number=step_num,
                    calculation_name=f"Step {step_num}",
                    formula="N/A",
                    inputs={},
                    output=Decimal("0.0"),
                    output_formatted="N/A",
                    explanation=skip_reason,
                    calculation_type=f"step_{step_num}",
                    status="skipped",
                    skip_reason=skip_reason,
                )
                calculation_step_objects.append(calc_step)

        # Ensure Step 3 is present (add if missing)
        step_numbers = {s.step_number for s in calculation_step_objects}
        if 3 not in step_numbers:
            self.logger.warning(
                "⚠️ Step 3 missing from calculation_step_objects, adding placeholder",
                extra={
                    "existing_steps": sorted(step_numbers),
                    "step_results_keys": sorted(step_results.keys()) if step_results else [],
                },
            )
            calc_step = CalculationStep(
                step_number=3,
                calculation_name="Base Enterprise Value",
                formula="N/A",
                inputs={},
                output=Decimal("0.0"),
                output_formatted="N/A",
                explanation="Step 3 not executed or result not available",
                calculation_type="step_3",
                status="not_executed",
            )
            calculation_step_objects.append(calc_step)

        # Build MarketDataDetails and ValidationReport
        market_data = self._build_market_data_details(
            request=request,
            detailed_results=detailed_results,
            multiples_results=multiples_results,
            multiples_source=multiples_results.get("data_source", "industry_defaults"),
        )

        validation_checks = self._build_validation_checks(None, revenue, ebitda, confidence_score)

        validation_report = ValidationReport(
            total_checks=len(validation_checks),
            passed=len([c for c in validation_checks if c.status == "passed"]),
            warnings=len([c for c in validation_checks if c.status == "warning"]),
            failed=len([c for c in validation_checks if c.status == "failed"]),
            checks=validation_checks,
            overall_status="passed" if len(validation_checks) > 0 else "passed_with_warnings",
            validation_score=int(confidence_score * 100),
            summary=f"Data quality validation completed. {len(validation_checks)} checks performed.",
        )

        transparency_data = TransparencyData(
            data_provenance={},
            market_data=market_data,
            industry_benchmarks={},
            calculation_steps={"multiples": calculation_step_objects},
            validation_report=validation_report,
        )

        # BANK-GRADE: Verify Step 11 is included
        step_numbers = {s.step_number for s in calculation_step_objects}
        has_step_11 = 11 in step_numbers
        step_11_status = None
        step_11_name = None
        if has_step_11:
            step_11_obj = next((s for s in calculation_step_objects if s.step_number == 11), None)
            if step_11_obj:
                step_11_status = step_11_obj.status
                step_11_name = step_11_obj.calculation_name

        self.logger.debug(
            "✅ Converted all StepOutput objects to CalculationStep",
            extra={
                "total_steps_converted": len(calculation_step_objects),
                "steps_completed": sum(
                    1 for s in calculation_step_objects if s.status == "completed"
                ),
                "steps_skipped": sum(1 for s in calculation_step_objects if s.status == "skipped"),
                "steps_failed": sum(1 for s in calculation_step_objects if s.status == "failed"),
                "has_step_11": has_step_11,
                "step_11_status": step_11_status,
                "step_11_name": step_11_name,
                "all_step_numbers": sorted(step_numbers),
                "expected_step_count": 12,
                "step_numbers": sorted([s.step_number for s in calculation_step_objects]),
                "step3_included": 3 in {s.step_number for s in calculation_step_objects},
            },
        )

        return transparency_data

    def _build_fallback_transparency(
        self,
        request: ValuationRequest,
        detailed_results: Dict[str, Any],
        multiples_results: Dict[str, Any],
        revenue: Decimal,
        ebitda: Optional[Decimal],
        confidence_score: Decimal,
    ) -> TransparencyData:
        """Build fallback transparency manually."""
        self.logger.warning(
            "⚠️ Step 11 transparency report not available and step_results not found, building transparency manually",
            extra={"has_transparency_report": False, "has_step_results": False},
        )

        # Build minimal transparency
        market_data = self._build_market_data_details(
            request=request,
            detailed_results=detailed_results,
            multiples_results=multiples_results if isinstance(multiples_results, dict) else {},
            multiples_source="industry_defaults",
        )

        validation_checks = self._build_validation_checks(None, revenue, ebitda, confidence_score)

        validation_report = ValidationReport(
            total_checks=len(validation_checks),
            passed=len([c for c in validation_checks if c.status == "passed"]),
            warnings=len([c for c in validation_checks if c.status == "warning"]),
            failed=len([c for c in validation_checks if c.status == "failed"]),
            checks=validation_checks,
            overall_status="passed" if len(validation_checks) > 0 else "passed_with_warnings",
            validation_score=int(confidence_score * 100),
            summary=f"Data quality validation completed. {len(validation_checks)} checks performed.",
        )

        return TransparencyData(
            data_provenance={},
            market_data=market_data,
            industry_benchmarks={},
            calculation_steps={},
            validation_report=validation_report,
        )

    def _build_minimal_fallback(
        self,
        request: ValuationRequest,
        detailed_results: Dict[str, Any],
        confidence_score: Decimal,
    ) -> TransparencyData:
        """Build minimal fallback transparency."""
        fallback_market_data = self._build_market_data_details(
            request=request,
            detailed_results=detailed_results,
            multiples_results={},
            multiples_source="fallback",
        )

        fallback_validation = ValidationReport(
            total_checks=0,
            passed=0,
            warnings=0,
            failed=0,
            checks=[],
            overall_status="passed_with_warnings",
            validation_score=int(confidence_score * 100) if confidence_score is not None else 50,
            summary="Minimal validation due to transparency build failure",
        )

        return TransparencyData(
            data_provenance={},
            market_data=fallback_market_data,
            industry_benchmarks={},
            calculation_steps={},
            validation_report=fallback_validation,
        )

    def _build_validation_checks(
        self,
        step_0_data: Optional[Dict[str, Any]],
        revenue: Decimal,
        ebitda: Optional[Decimal],
        confidence_score: Decimal,
    ) -> List[ValidationCheck]:
        """Compatibility wrapper for focused validation-check construction."""
        return build_validation_checks(step_0_data, revenue, ebitda, confidence_score)
