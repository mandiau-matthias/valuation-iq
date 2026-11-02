"""Completion logging for Step 11 final synthesis."""

from decimal import Decimal
from typing import Dict

from src.utils.logging import get_logger

from ...base_step import StepInput, StepStatus

logger = get_logger(__name__)


def log_completion_summary(
    *,
    input_data: StepInput,
    valuation_low: Decimal,
    valuation_mid: Decimal,
    valuation_high: Decimal,
    asking_price: Decimal,
    confidence_score: int,
    confidence_level: str,
    methodologies: Dict[str, object],
    academic_sources: list,
    professional_review_ready: Dict[str, object],
    value_chain_validated: bool,
    rounding_details: Dict[str, object],
    use_fallback: bool,
    request: object,
) -> None:
    """Log the Step 11 completion summary without bloating orchestration flow."""
    completed_steps = _steps_with_status(input_data, StepStatus.COMPLETED)
    skipped_steps = _steps_with_status(input_data, StepStatus.SKIPPED)
    methodologies_used = list(set(methodologies.get("used_methodologies", [])))

    logger.debug(
        "📊 Step 11: Final Valuation Synthesis - Calculation Complete",
        extra={
            "step_number": 11,
            "step_name": "Final Valuation Synthesis",
            "status": "COMPLETED",
            "inputs": {
                "previous_steps_count": len(input_data.previous_results),
                "completed_steps": completed_steps,
                "has_step10": 10 in input_data.previous_results,
                "has_step9": 9 in input_data.previous_results,
                "has_step8": 8 in input_data.previous_results,
                "has_step7": 7 in input_data.previous_results,
            },
            "calculation": {
                "methodology": "12-step modular valuation system (academic standards)",
                "formula": "Final Valuation = Step 10 Range (or Step 7/8 Equity with confidence spread)",
                "use_fallback": use_fallback,
                "rounding_applied": True,
                "value_chain_validated": value_chain_validated,
            },
            "outputs": {
                "valuation_low": valuation_low,
                "valuation_mid": valuation_mid,
                "valuation_high": valuation_high,
                "asking_price": asking_price,
                "confidence_score": confidence_score,
                "confidence_level": confidence_level,
            },
            "metadata": {
                "methodologies_used": methodologies_used,
                "primary_method": methodologies.get("primary_method"),
                "range_methodology": methodologies.get("range_methodology"),
                "academic_sources_count": len(academic_sources),
                "professional_review_ready": professional_review_ready.get("ready", False),
                "transparency_report_generated": True,
                "total_steps_executed": len(completed_steps),
                "academic_reference": "IFRS 13, IVS 2017, Big 4 methodologies",
            },
        },
    )

    logger.debug(
        "✅ Step 11: Final Valuation Synthesis Complete",
        extra={
            "step_number": 11,
            "valuation_low": valuation_low,
            "valuation_mid": valuation_mid,
            "valuation_high": valuation_high,
            "range_spread_pct": (
                ((valuation_high - valuation_low) / valuation_mid * 100)
                if valuation_mid > 0
                else 0
            ),
            "asking_price": asking_price,
            "confidence_score": confidence_score,
            "confidence_level": confidence_level,
            "methodologies_used": methodologies_used,
            "primary_method": methodologies.get("primary_method"),
            "range_methodology": methodologies.get("range_methodology"),
            "academic_sources_count": len(academic_sources),
            "professional_review_ready": professional_review_ready.get("ready", False),
            "value_chain_validated": value_chain_validated,
            "rounding_impact_mid_pct": rounding_details.get("rounding_impact_mid_pct", 0),
            "transparency_report_generated": True,
            "total_steps_executed": len(completed_steps),
        },
    )

    logger.info(
        "🎉 Complete Valuation Calculation Journey Finished",
        extra={
            "step_number": 11,
            "company_name": getattr(request, "company_name", "N/A"),
            "final_valuation_mid": valuation_mid,
            "final_valuation_range": f"{valuation_low:,.0f} - {valuation_high:,.0f}",
            "confidence_score": confidence_score,
            "methodologies": methodologies_used,
            "total_steps_completed": len(completed_steps),
            "total_steps_skipped": len(skipped_steps),
            "value_chain_validated": value_chain_validated,
        },
    )


def _steps_with_status(input_data: StepInput, status: StepStatus) -> list:
    return [
        step_number
        for step_number, step_output in input_data.previous_results.items()
        if step_output.status == status
    ]
