"""
Step Data Builder Module

Functions and classes for building the 12-step calculation journey from
transparency data.
"""

from typing import Any, Dict, List

from src.services.infrastructure.exceptions import MissingDataError, StepDataError
from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)
from src.utils.logging import get_logger

from .step_input_validator import StepInputValidator
from .step_journey_validator import StepJourneyValidator
from .step_output_lookup import get_step_output
from .step_placeholder_creator import StepPlaceholderCreator
from .step_processor import StepProcessor
from .utils import ensure_step_outputs_defaults

logger = get_logger(__name__)


def build_12_step_calculation_journey(
    response: ValuationResponseProtocol,
    request: ValuationRequestProtocol,
) -> List[Dict[str, Any]]:
    """
    Build 12-step calculation journey from transparency data.

    Validates step data integrity and ensures all steps (0-11) are present.
    Creates placeholder steps for missing data with appropriate status.
    Ensures all template-accessed fields exist with safe defaults.

    Args:
        response: ValuationResponse containing transparency data
        request: Original ValuationRequest for context

    Returns:
        List of 12 step dictionaries, one for each step (0-11)

    Raises:
        MissingDataError: If required inputs are missing
        StepDataError: If step data cannot be built
        ValueError: If step count or sequence is invalid
    """
    StepInputValidator.validate(response, request)

    logger.info(
        "Building 12-step calculation journey from transparency data",
        extra={
            "company_name": getattr(response, "company_name", None),
            "valuation_id": getattr(response, "valuation_id", None),
            "has_transparency": response.transparency is not None,
        },
    )

    calculation_steps = []
    step_status_counts = {
        "completed": 0,
        "skipped": 0,
        "failed": 0,
        "not_executed": 0,
    }
    steps_found = []
    steps_missing = []

    for step_num in range(12):
        step_output = get_step_output(response, step_num)
        if step_output:
            processed_step = StepProcessor.process_step(step_output, step_num)
            step_status = processed_step.get("status", "completed")
            step_status_counts[step_status] = step_status_counts.get(step_status, 0) + 1
            calculation_steps.append(processed_step)
            steps_found.append(step_num)
            if step_num >= 10:
                logger.debug(
                    f"✅ Step {step_num} extracted successfully",
                    extra={
                        "step_number": step_num,
                        "step_name": processed_step.get("step_name", "N/A"),
                        "status": step_status,
                        "has_rationale": bool(processed_step.get("rationale")),
                        "has_explanation": bool(processed_step.get("explanation")),
                    },
                )
        else:
            placeholder = StepPlaceholderCreator.create_placeholder(step_num)
            step_status_counts["not_executed"] += 1
            calculation_steps.append(placeholder)
            steps_missing.append(step_num)
            if step_num >= 10:
                logger.warning(
                    f"⚠️ Step {step_num} not found in transparency data - using placeholder",
                    extra={
                        "step_number": step_num,
                        "has_transparency": response.transparency is not None,
                        "has_calculation_steps": (
                            hasattr(response.transparency, "calculation_steps")
                            if response.transparency
                            else False
                        ),
                    },
                )

    StepJourneyValidator.validate(calculation_steps)

    logger.info(
        "12-step calculation journey built successfully",
        extra={
            "total_steps": len(calculation_steps),
            "status_distribution": step_status_counts,
            "completed_count": step_status_counts["completed"],
            "skipped_count": step_status_counts["skipped"],
            "failed_count": step_status_counts["failed"],
            "not_executed_count": step_status_counts["not_executed"],
            "steps_found": sorted(steps_found),
            "steps_missing": sorted(steps_missing),
            "has_step_10": 10 in steps_found,
            "has_step_11": 11 in steps_found,
            "step_10_status": next(
                (s.get("status") for s in calculation_steps if s.get("step_number") == 10),
                None,
            ),
            "step_11_status": next(
                (s.get("status") for s in calculation_steps if s.get("step_number") == 11),
                None,
            ),
            "step_10_name": next(
                (s.get("step_name") for s in calculation_steps if s.get("step_number") == 10),
                None,
            ),
            "step_11_name": next(
                (s.get("step_name") for s in calculation_steps if s.get("step_number") == 11),
                None,
            ),
        },
    )

    return calculation_steps


__all__ = [
    "ensure_step_outputs_defaults",
    "get_step_output",
    "build_12_step_calculation_journey",
]
