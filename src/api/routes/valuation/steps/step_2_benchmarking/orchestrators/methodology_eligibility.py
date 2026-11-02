"""
Methodology eligibility support for Step 2 benchmarking.

The orchestrator owns phase ordering; this module owns the data extraction and
logging around the methodology decider call.
"""

from __future__ import annotations

from collections.abc import Mapping


def determine_methodology_eligibility(
    *,
    request,
    step0_result: Mapping[str, object] | None,
    methodology_decider,
    logger,
):
    quality_score_from_step0 = step0_result.get("quality_score") if step0_result else None
    if quality_score_from_step0 is not None:
        logger.debug(
            "Step 2: Using Step 0 quality_score for methodology eligibility",
            extra={
                "step_number": 2,
                "quality_score": quality_score_from_step0,
                "source": "Step 0 (Data Quality Assessment)",
            },
        )

    eligibility_result = methodology_decider.decide_methodology(
        request, quality_score_from_step0=quality_score_from_step0
    )

    decision_value = (
        getattr(eligibility_result.decision, "value", "multiples_only")
        if eligibility_result and hasattr(eligibility_result, "decision")
        else "multiples_only"
    )
    logger.debug(
        "Step 2: Methodology decision determined",
        extra={
            "step_number": 2,
            "dcf_eligible": (
                getattr(eligibility_result, "should_calculate_dcf", False)
                if eligibility_result
                else False
            ),
            "recommended_methodology": decision_value,
        },
    )

    return eligibility_result
