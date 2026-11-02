"""
Legacy Response Transformer

Extracted from MultiplesCalculator to follow Single Responsibility Principle.
Handles transformation of modular step results to legacy API format.

Author: Upswitch CTO Team
Date: December 2025
Status: Production Ready
"""

from decimal import Decimal
from typing import Dict, Optional, TypeAlias, cast

from src.api.schemas import ValuationRequest
from src.api.routes.valuation.benchmark_contract_utils import (
    extract_request_resolved_benchmark_contract,
)
from src.domain.models import ConfidenceLevel
from src.domain.multiples.advisor_controls import (
    build_multiple_type_blend,
    build_pipeline_multiple_build_up,
    build_sotp_segments,
    infer_sector_multiple_type_weights,
    normalize_earnings_basis,
)
from src.utils.data_flow_tracer import get_tracer
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.valuation_logger import ValuationLogger
from src.utils.exceptions import MultiplesCalculationError

from ..steps import StepOutput, StepStatus
from .valuation_extractor import ValuationExtractor
from .legacy_response_helpers import (
    get_primary_method_reason,
    build_owner_concentration_dict,
    map_confidence_level,
)

logger = ValuationLogger(__name__)

JsonMap: TypeAlias = Dict[str, object]
StepOutputMap: TypeAlias = Dict[int, StepOutput]
ExtractedStepResults: TypeAlias = Dict[int, JsonMap]


def _as_json_map(value: object) -> JsonMap:
    """Return a dict-shaped payload when legacy data is map-like."""
    return cast(JsonMap, value) if isinstance(value, dict) else {}


def _normalize_primary_method(raw: object) -> str:
    """Normalize primary_method to canonical 'EV/Revenue' or 'EV/EBITDA'."""
    if raw is None:
        return "EV/EBITDA"
    token = str(raw).strip().upper()
    if token in {"EV/REVENUE", "REVENUE_MULTIPLE", "REVENUE", "EV_REVENUE"}:
        return "EV/Revenue"
    return "EV/EBITDA"


class LegacyResponseTransformer:
    """
    Transforms modular step results to legacy API format.

    Single Responsibility: Legacy format transformation only.
    Ensures 100% backward compatibility with existing API consumers.
    """

    def __init__(self, valuation_extractor: ValuationExtractor):
        """
        Initialize legacy response transformer.

        Args:
            valuation_extractor: ValuationExtractor instance for extracting values
        """
        self.valuation_extractor = valuation_extractor
        self.logger = logger

    def extract_step_results(self, step_results: StepOutputMap) -> ExtractedStepResults:
        """
        Extract results from all step outputs.

        Args:
            step_results: Dictionary mapping step numbers to StepOutput objects

        Returns:
            Dictionary mapping step numbers to their result dictionaries
        """
        extracted: ExtractedStepResults = {}
        for step_num in range(12):  # Steps 0-11
            if step_num in step_results:
                step_output = step_results[step_num]
                if hasattr(step_output, "result") and isinstance(step_output.result, dict):
                    extracted[step_num] = step_output.result
                else:
                    extracted[step_num] = {}
            else:
                extracted[step_num] = {}
        return extracted

    def validate_step_2_result(self, step_2: JsonMap) -> bool:
        """
        Validate that step_2 result has required fields.

        Args:
            step_2: Step 2 result dictionary

        Returns:
            True if all required fields are present
        """
        required_fields = [
            "ev_revenue_multiple",
            "ev_ebitda_multiple",
            "data_source",
            "primary_method",
        ]
        return all(field in step_2 for field in required_fields) and len(step_2) > 0

    def build_legacy_response(
        self,
        step_results: StepOutputMap,
        extracted_results: ExtractedStepResults,
        step_2: JsonMap,
        valuation_values: Dict[str, Decimal],
        multiples: JsonMap,
        request: ValuationRequest,
    ) -> JsonMap:
        """
        Build legacy format response dictionary.

        Args:
            step_results: Dictionary mapping step numbers to StepOutput objects
            extracted_results: Dictionary mapping step numbers to result dictionaries
            step_2: Step 2 result dictionary
            valuation_values: Dictionary with enterprise_value, equity_value, valuation_low/mid/high
            multiples: Dictionary with revenue_multiple_raw, ebitda_multiple_raw
            request: Valuation request

        Returns:
            Legacy format response dictionary
        """
        step_4 = extracted_results.get(4, {})
        step_3 = extracted_results.get(3, {})
        step_8 = extracted_results.get(8, {})
        step_11 = extracted_results.get(11, {})

        primary_method = _normalize_primary_method(step_2.get("primary_method"))
        raw_multiple_pipeline = step_11.get("multiple_pipeline")
        multiple_pipeline = (
            raw_multiple_pipeline if isinstance(raw_multiple_pipeline, dict) else None
        )
        metric_type = step_11.get("earnings_basis")
        if not metric_type and multiple_pipeline:
            metric_type = multiple_pipeline.get("metric_type")
        if not metric_type:
            metric_type = step_3.get("primary_metric") or primary_method
        earnings_basis = normalize_earnings_basis(metric_type)
        advisor_override = {
            "label": (
                "advisor-adjusted"
                if getattr(request, "multiple_calibration_adjustment", None)
                else "Upswitch model"
            ),
            "index_protected": True,
            "requires_rationale": True,
            "rationale": getattr(request, "multiple_calibration_note", None),
            "multiple_calibration_adjustment": getattr(
                request, "multiple_calibration_adjustment", None
            ),
        }
        segment_valuation = build_sotp_segments(getattr(request, "business_type_segments", None))
        multiple_build_up = (
            step_11.get("multiple_build_up")
            if isinstance(step_11.get("multiple_build_up"), dict)
            else build_pipeline_multiple_build_up(
                multiple_pipeline,
                advisor_override=advisor_override,
                segment_valuation=segment_valuation,
            )
        )
        default_type_weights, default_type_source = infer_sector_multiple_type_weights(
            revenue=getattr(request, "revenue", None),
            ebitda=getattr(request, "ebitda", None),
            benchmark_contract=extract_request_resolved_benchmark_contract(request),
        )
        multiple_type_blend = build_multiple_type_blend(
            {
                "ev_ebitda": (
                    valuation_values["enterprise_value"] if primary_method == "EV/EBITDA" else None
                ),
                "ev_revenue": (
                    valuation_values["enterprise_value"] if primary_method == "EV/Revenue" else None
                ),
                "pe": None,
            },
            getattr(request, "multiple_type_weights", None),
            default_weights=default_type_weights,
            default_source=default_type_source,
        )

        result: JsonMap = {
            "methodology": "Multiples",
            "enterprise_value": valuation_values["enterprise_value"],
            "equity_value": valuation_values["equity_value"],
            "equity_value_low": valuation_values["valuation_low"],
            "equity_value_mid": valuation_values["valuation_mid"],
            "equity_value_high": valuation_values["valuation_high"],
            "per_share_value": None,
            "ev_ebitda_valuation": (
                valuation_values["enterprise_value"] if primary_method == "EV/EBITDA" else None
            ),
            "ev_revenue_valuation": (
                valuation_values["enterprise_value"] if primary_method == "EV/Revenue" else None
            ),
            "pe_valuation": None,
            "ebitda_multiple": multiples["ebitda_multiple_raw"],
            "revenue_multiple": multiples["revenue_multiple_raw"],
            "pe_multiple": step_2.get("pe_ratio", Decimal("15.0")),
            "unadjusted_ebitda_multiple": multiples["ebitda_multiple_raw"],
            "unadjusted_revenue_multiple": multiples["revenue_multiple_raw"],
            "primary_multiple_method": (
                "revenue_multiple" if primary_method == "EV/Revenue" else "ebitda_multiple"
            ),
            "primary_multiple_reason": get_primary_method_reason(primary_method),
            "primary_method": primary_method,
            "earnings_basis": earnings_basis,
            "data_source": step_2.get("data_source", "unknown"),
            "owner_concentration": (
                build_owner_concentration_dict(step_4, request) if step_4 else None
            ),
            "size_discount": (
                step_results[5].result.get("size_discount_percentage", 0.0)
                if 5 in step_results
                else Decimal("0.0")
            ),
            "liquidity_discount": (
                step_results[6].result.get("total_discount_percentage", 0.0)
                if 6 in step_results
                else Decimal("0.0")
            ),
            "country_adjustment": Decimal("0.0"),
            "growth_premium": Decimal("0.0"),
            "total_adjustment": Decimal("0.0"),
            "adjusted_equity_value": valuation_values["equity_value"],
            "multiple_type_blend": multiple_type_blend,
            "discount_build_up": (
                {
                    "composition": "step_pipeline",
                    "waterfall": multiple_pipeline.get("discount_waterfall", []),
                    "floor_policy": "validated_in_step_pipeline",
                }
                if multiple_pipeline
                else None
            ),
            "multiple_build_up": multiple_build_up,
            "advisor_override_governance": advisor_override,
            "segment_valuation": segment_valuation,
            "comparables_count": 0,
            "comparables_quality": ConfidenceLevel.MEDIUM,
            "confidence": map_confidence_level(step_8.get("confidence_level", "MEDIUM")),
            "confidence_score": step_8.get("overall_confidence_score", 65),
            "p10_ebitda_multiple": step_2.get("ev_ebitda_p10"),
            "p25_ebitda_multiple": step_2.get("ev_ebitda_p25"),
            "p50_ebitda_multiple": step_2.get("ev_ebitda_p50"),
            "p75_ebitda_multiple": step_2.get("ev_ebitda_p75"),
            "p90_ebitda_multiple": step_2.get("ev_ebitda_p90"),
            "p25_revenue_multiple": step_2.get("ev_revenue_p25"),
            "p50_revenue_multiple": step_2.get("ev_revenue_p50"),
            "p75_revenue_multiple": step_2.get("ev_revenue_p75"),
            "modular_system": {
                "enabled": True,
                "total_steps": len(step_results),
                "steps_completed": sum(
                    1 for r in step_results.values() if r.status == StepStatus.COMPLETED
                ),
                "steps_skipped": sum(
                    1 for r in step_results.values() if r.status == StepStatus.SKIPPED
                ),
                "total_execution_time_ms": sum(
                    (
                        Decimal(str(r.execution_time_ms))
                        for r in step_results.values()
                        if hasattr(r, "execution_time_ms") and r.execution_time_ms is not None
                    ),
                    Decimal("0"),
                ),
                "step_details": [
                    {
                        "step": r.step_number,
                        "name": r.step_name,
                        "status": r.status.value,
                        "execution_time_ms": r.execution_time_ms,
                        "error": r.error if r.error else None,
                        "reason": (
                            r.metadata.get("reason")
                            if hasattr(r, "metadata") and r.metadata
                            else None
                        ),
                    }
                    for r in step_results.values()
                ],
            },
            "transparency_report": step_11.get("transparency_report") if step_11 else None,
            "_step_results": step_results,
        }

        return result

    def log_transformation_summary(
        self,
        request: ValuationRequest,
        step_2: JsonMap,
        valuation_values: Dict[str, Decimal],
        multiples: JsonMap,
        extracted_results: ExtractedStepResults,
        result: JsonMap,
    ) -> None:
        """
        Log comprehensive final valuation summary.

        Args:
            request: Valuation request
            step_2: Step 2 result dictionary
            valuation_values: Valuation values dictionary
            multiples: Multiples dictionary
            extracted_results: Extracted step results
            result: Final result dictionary
        """
        modular_system = _as_json_map(result.get("modular_system"))
        # DEBUG: legacy-response-transformer summary; canonical exit is
        # "✅ Multiples valuation completed" in multiples_executor.
        self.logger.debug(
            "📊 Final Valuation Summary - Multiples Calculation Complete",
            extra={
                "company": request.company_name,
                "methodology": "Multiples",
                "core_values": {
                    "enterprise_value": valuation_values["enterprise_value"],
                    "equity_value": valuation_values["equity_value"],
                    "equity_value_low": valuation_values["valuation_low"],
                    "equity_value_mid": valuation_values["valuation_mid"],
                    "equity_value_high": valuation_values["valuation_high"],
                },
                "multiples": {
                    "ev_ebitda_multiple": step_2.get("ev_ebitda_multiple"),
                    "ev_revenue_multiple": step_2.get("ev_revenue_multiple"),
                    "primary_method": step_2.get("primary_method", "EV/EBITDA"),
                    "data_source": step_2.get("data_source", "unknown"),
                },
                "adjustments": {
                    "size_discount_pct": result.get("size_discount", Decimal("0.0")),
                    "liquidity_discount_pct": result.get("liquidity_discount", Decimal("0.0")),
                    "owner_concentration": result.get("owner_concentration"),
                    "total_adjustment": result.get("total_adjustment", Decimal("0.0")),
                },
                "confidence": {
                    "confidence_score": result.get("confidence_score", 0),
                    "confidence_level": result.get("confidence", "MEDIUM"),
                },
                "comparables": {
                    "comparables_count": result.get("comparables_count", 0),
                    "comparables_quality": str(result.get("comparables_quality", "MEDIUM")),
                },
                "modular_system": {
                    "total_steps": modular_system.get("total_steps", 0),
                    "steps_completed": modular_system.get("steps_completed", 0),
                    "total_execution_time_ms": modular_system.get("total_execution_time_ms", 0),
                },
                "transparency_report_available": bool(
                    extracted_results.get(11, {}).get("transparency_report")
                ),
            },
        )

        # Log transparency report extraction
        step_11 = extracted_results.get(11, {})
        transparency_report = _as_json_map(step_11.get("transparency_report"))
        if step_11 and transparency_report:
            calculation_steps_raw = transparency_report.get("calculation_steps", [])
            calculation_steps = (
                calculation_steps_raw if isinstance(calculation_steps_raw, list) else []
            )
            step_numbers_in_report = (
                [step.get("step") for step in calculation_steps if isinstance(step, dict)]
                if isinstance(calculation_steps, list)
                else []
            )

            self.logger.debug(
                "✅ Transparency report extracted from Step 11",
                extra={
                    "has_calculation_steps": "calculation_steps" in transparency_report,
                    "calculation_steps_count": len(calculation_steps),
                    "step_numbers_in_report": step_numbers_in_report,
                    "has_confidence_breakdown": "confidence_breakdown" in transparency_report,
                    "has_academic_sources": "academic_sources" in transparency_report,
                    "confidence_breakdown_keys": list(
                        _as_json_map(transparency_report.get("confidence_breakdown")).keys()
                    ),
                    "has_data_quality": (
                        any(
                            isinstance(step, dict) and step.get("step") == 0
                            for step in calculation_steps
                        )
                        if calculation_steps
                        else False
                    ),
                },
            )
        else:
            self.logger.warning(
                "⚠️ No transparency report found in Step 11",
                extra={
                    "step_11_exists": bool(step_11),
                    "step_11_keys": list(step_11.keys()) if step_11 else [],
                },
            )

    def add_tracer_checkpoint(
        self,
        step_2: JsonMap,
        multiples: JsonMap,
    ) -> None:
        """
        Add data flow tracer checkpoint.

        Args:
            step_2: Step 2 result dictionary
            multiples: Multiples dictionary
        """
        try:
            tracer = get_tracer()
            tracer.checkpoint(
                "multiples_calculator_mapping",
                revenue_multiple=multiples["revenue_multiple_raw"],
                ev_ebitda_ratio=multiples["ebitda_multiple_raw"],
                context={
                    "step_2_revenue_multiple": (
                        step_2.get("ev_revenue_multiple") if step_2 else None
                    ),
                    "step_2_ebitda_multiple": step_2.get("ev_ebitda_multiple") if step_2 else None,
                    "revenue_field_found": multiples["revenue_field_found"],
                    "ebitda_field_found": multiples["ebitda_field_found"],
                    "used_fallback": multiples["revenue_multiple_raw"]
                    != (step_2.get("ev_revenue_multiple") if step_2 else None),
                },
                notes="Mapping multiples from step_2 to result dict",
            )
        except (ValueError, TypeError, AttributeError, KeyError):
            logger.debug("Tracer checkpoint failed (non-critical)", exc_info=True)
        except MultiplesCalculationError:
            logger.debug("Unexpected error in tracer checkpoint (non-critical)", exc_info=True)
