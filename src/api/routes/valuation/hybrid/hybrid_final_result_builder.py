"""Final-result assembly for the hybrid valuation orchestrator."""

from decimal import Decimal
from typing import Dict, Optional

from src.api.schemas import ValuationRequest
from src.domain.hybrid_types import (
    AggregatedValuation,
    MethodologyDecision,
    MethodologyEligibilityResult,
    WeightResult,
)
from src.utils.decimal_helpers import pin_band_monotone, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


def build_hybrid_final_result(
    *,
    aggregated: AggregatedValuation,
    eligibility: MethodologyEligibilityResult,
    weights: WeightResult,
    confidence_data: Dict[str, object],
    range_result: Dict[str, object],
    request: ValuationRequest,
    dcf_failure_reason: Optional[str] = None,
    multiples_result: Optional[Dict[str, object]] = None,
    dcf_result: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    """Build the legacy API result shape for a completed hybrid valuation."""
    equity_value = aggregated.equity_value
    equity_value_low = range_result.get("equity_value_low", aggregated.equity_value_low)
    equity_value_high = range_result.get("equity_value_high", aggregated.equity_value_high)
    enterprise_value = aggregated.enterprise_value
    enterprise_value_low = range_result.get(
        "enterprise_value_low", aggregated.enterprise_value_low
    )
    enterprise_value_high = range_result.get(
        "enterprise_value_high", aggregated.enterprise_value_high
    )
    confidence_score = confidence_data.get("overall_confidence", Decimal("0.66"))

    (
        equity_value_low,
        equity_value_high,
    ) = _pin_band(
        event_name="hybrid_orchestrator_equity_band_pinned",
        low=equity_value_low,
        mid=equity_value,
        high=equity_value_high,
        reason=(
            "aggregated.equity_value (mid) and range_result low/high came from "
            "different sub-computations"
        ),
    )
    (
        enterprise_value_low,
        enterprise_value_high,
    ) = _pin_band(
        event_name="hybrid_orchestrator_ev_band_pinned",
        low=enterprise_value_low,
        mid=enterprise_value,
        high=enterprise_value_high,
        reason=(
            "aggregated.enterprise_value (mid) and range_result EV low/high came "
            "from different sub-computations"
        ),
    )

    methodology_details = _build_methodology_details(eligibility, weights)
    if dcf_failure_reason:
        methodology_details["dcf_failure_reason"] = dcf_failure_reason
        methodology_details["dcf_fallback"] = (
            "Multiples-only valuation used due to DCF calculation failure"
        )
        methodology_details["weights"]["dcf"] = Decimal("0")
        methodology_details["weights"]["multiples"] = Decimal("1")
        weights = WeightResult(
            dcf_weight=Decimal("0"),
            multiples_weight=Decimal("1"),
            source="dcf_failure_fallback",
            rationale="DCF calculation failed — 100% Multiples",
            base_dcf_weight=weights.base_dcf_weight,
            base_multiples_weight=weights.base_multiples_weight,
            adjustments_applied=weights.adjustments_applied + ["dcf_failure_override"],
        )

    result = {
        "equity_value": equity_value,
        "equity_value_mid": equity_value,
        "equity_value_low": equity_value_low,
        "equity_value_high": equity_value_high,
        "enterprise_value": enterprise_value,
        "enterprise_value_low": enterprise_value_low,
        "enterprise_value_high": enterprise_value_high,
        "methodology": aggregated.methodology,
        "methodology_details": methodology_details,
        "confidence_score": confidence_score,
        "confidence_factors": confidence_data.get("factors", {}),
        "range_methodology": aggregated.range_methodology or range_result.get("methodology"),
        "component_results": _build_component_results(aggregated),
        "weights": {
            "dcf_weight": weights.dcf_weight,
            "multiples_weight": weights.multiples_weight,
            "source": weights.source,
        },
        "dcf_weight": weights.dcf_weight,
        "multiples_weight": weights.multiples_weight,
        "warnings": aggregated.warnings,
        "notes": build_hybrid_notes(eligibility, weights, aggregated),
        "calculation_timestamp": aggregated.calculation_timestamp,
        "company_name": request.company_name,
    }

    if multiples_result:
        result["multiples_valuation"] = multiples_result
    if dcf_result:
        result["dcf_valuation"] = dcf_result

    result["_value_sources"] = _build_value_sources(eligibility, multiples_result)
    return result


def coerce_confidence_score(raw_score: object) -> tuple[Decimal, bool]:
    """Return a Decimal confidence score in [0, 1], or the default fallback."""
    try:
        if isinstance(raw_score, bool):
            raise TypeError("boolean confidence score is not valid")
        confidence_score = raw_score if isinstance(raw_score, Decimal) else to_decimal(str(raw_score))
    except (ArithmeticError, TypeError, ValueError):
        return Decimal("0.66"), False

    if confidence_score < Decimal("0") or confidence_score > Decimal("1"):
        return Decimal("0.66"), False
    return confidence_score, True


def build_hybrid_notes(
    eligibility: MethodologyEligibilityResult,
    weights: WeightResult,
    aggregated: AggregatedValuation,
) -> list:
    """Build explanatory notes for the user."""
    notes = []

    if eligibility.decision == MethodologyDecision.MULTIPLES_ONLY:
        notes.append(
            "DCF methodology excluded. Multiples valuation provides the most reliable "
            "estimate for your company's size and characteristics."
        )
    elif eligibility.decision == MethodologyDecision.HYBRID_MULTIPLES_PRIMARY:
        notes.append(
            f"Hybrid valuation with Multiples as primary methodology ({weights.multiples_weight:.0%}). "
            "This is common for growth companies in the €1M-€5M range."
        )
    elif eligibility.decision == MethodologyDecision.HYBRID_DCF_PRIMARY:
        notes.append(
            f"Hybrid valuation with DCF as primary methodology ({weights.dcf_weight:.0%}). "
            "Your company's size and data quality make DCF highly reliable."
        )

    if weights.source in ["business_context", "database"]:
        notes.append(f"Methodology weights customized for your business type ({weights.source}).")

    growth_adjustments = [
        adjustment
        for adjustment in weights.adjustments_applied
        if "growth" in adjustment.lower() or "declining" in adjustment.lower()
    ]
    if growth_adjustments:
        notes.append(
            "Weights adjusted based on your company's growth trajectory to better capture valuation drivers."
        )

    notes.extend(aggregated.warnings)
    return notes


def _pin_band(
    *,
    event_name: str,
    low: object,
    mid: object,
    high: object,
    reason: str,
) -> tuple[object, object]:
    low_decimal = to_decimal(low) if low is not None else Decimal("0")
    mid_decimal = to_decimal(mid) if mid is not None else Decimal("0")
    high_decimal = to_decimal(high) if high is not None else Decimal("0")
    pinned_low, _, pinned_high = pin_band_monotone(low_decimal, mid_decimal, high_decimal)

    if pinned_low == low_decimal and pinned_high == high_decimal:
        return low, high

    logger.warning(
        event_name,
        extra={
            "before_low": str(low_decimal),
            "before_mid": str(mid_decimal),
            "before_high": str(high_decimal),
            "after_low": str(pinned_low),
            "after_high": str(pinned_high),
            "reason": reason,
        },
    )
    return (pinned_low if low is not None else low, pinned_high if high is not None else high)


def _build_methodology_details(
    eligibility: MethodologyEligibilityResult, weights: WeightResult
) -> Dict[str, object]:
    return {
        "decision": eligibility.decision.value,
        "suitability_score": eligibility.suitability_score.total_score,
        "should_calculate_dcf": eligibility.should_calculate_dcf,
        "explanation": eligibility.explanation,
        "weights": {
            "dcf": weights.dcf_weight,
            "multiples": weights.multiples_weight,
            "source": weights.source,
            "rationale": weights.rationale,
            "adjustments_applied": weights.adjustments_applied,
        },
        "suitability_breakdown": eligibility.suitability_score.breakdown,
    }


def _build_component_results(aggregated: AggregatedValuation) -> Dict[str, Dict[str, object]]:
    component_results = {}
    if aggregated.component_results.get("dcf"):
        component_results["dcf"] = {
            "equity_value": aggregated.component_results["dcf"].get("equity_value"),
            "enterprise_value": aggregated.component_results["dcf"].get("enterprise_value"),
            "confidence_score": aggregated.component_results["dcf"].get("confidence_score"),
        }

    if aggregated.component_results.get("multiples"):
        multiples = aggregated.component_results["multiples"]
        adjusted_equity_value = multiples.get("adjusted_equity_value")
        equity_value_mid = multiples.get("equity_value_mid")
        equity_value = (
            adjusted_equity_value
            if adjusted_equity_value is not None
            else (equity_value_mid if equity_value_mid is not None else multiples.get("equity_value"))
        )
        enterprise_value = multiples.get("enterprise_value")
        enterprise_value_mid = (
            enterprise_value if enterprise_value is not None else multiples.get("enterprise_value_mid")
        )
        component_results["multiples"] = {
            "equity_value": equity_value,
            "enterprise_value": enterprise_value_mid,
            "confidence_score": multiples.get("confidence_score"),
        }

    return component_results


def _build_value_sources(
    eligibility: MethodologyEligibilityResult,
    multiples_result: Optional[Dict[str, object]],
) -> Dict[str, object]:
    step_results = multiples_result.get("_step_results", {}) if multiples_result else {}
    step_11_output = None
    if isinstance(step_results, dict):
        for key in (11, 11.0, "11"):
            step_11_output = step_results.get(key)
            if step_11_output is not None:
                break

    has_step_11 = (
        step_11_output is not None
        and hasattr(step_11_output, "result")
        and step_11_output.result
    )
    sources = {"step_11_available": has_step_11}

    if eligibility.decision == MethodologyDecision.MULTIPLES_ONLY and has_step_11:
        source = "Step 11"
    else:
        source = "Hybrid (DCF + Multiples)"
    sources["equity_value_low_source"] = source
    sources["equity_value_mid_source"] = source
    sources["equity_value_high_source"] = source
    return sources
