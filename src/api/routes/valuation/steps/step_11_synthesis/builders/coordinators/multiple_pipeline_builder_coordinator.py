"""
Multiple Pipeline Builder Coordinator

Orchestrates multiple pipeline building from step results for transparency reporting.
"""

from collections.abc import Mapping
from typing import Optional

from src.errors import ValidationError
from src.utils.logging import get_logger

from .multiple_pipeline_assembly import (
    build_pipeline_context,
    build_pipeline_result,
    collect_pipeline_steps,
    first_present,
)
from .types import GetPreviousStepResultFunc, MultiplePipeline, PreviousResults
from .validation import BankGradeValidator

logger = get_logger(__name__)


class MultiplePipelineBuilderCoordinator:
    """
    Coordinates multiple pipeline building from step results.
    """

    def __init__(self) -> None:
        self.logger = logger

    @staticmethod
    def _first_present(mapping: Mapping[str, object], *keys: str, default: object = None) -> object:
        """Return the first present, non-None value while preserving explicit zeroes."""
        return first_present(mapping, *keys, default=default)

    def build_multiple_pipeline(
        self,
        previous_results: PreviousResults,
        get_previous_step_result_func: GetPreviousStepResultFunc,
    ) -> Optional[MultiplePipeline]:
        """
        Build complete multiple discount pipeline from all steps.

        Coordinates validation, state assembly, and audit logging while the pure
        pipeline state transitions live in ``multiple_pipeline_assembly``.
        """
        try:
            BankGradeValidator.validate_previous_results(previous_results, required_steps=[3])
        except ValidationError as error:
            self.logger.error(
                f"❌ CRITICAL: Invalid previous_results structure: {error}",
                extra={"step_number": 11},
            )
            raise

        self.logger.debug(
            "🔍 Starting multiple pipeline building (bank-grade audit trail)",
            extra={
                "step_number": 11,
                "previous_results_count": len(previous_results),
                "available_steps": sorted(previous_results.keys()),
            },
        )

        step3 = get_previous_step_result_func(3, previous_results)
        if not step3:
            self.logger.warning(
                "⚠️ Step 11: Cannot build multiple pipeline - Step 3 not available",
                extra={"step_number": 11},
            )
            return None
        if not isinstance(step3, Mapping):
            self.logger.warning(
                "⚠️ Step 11: Cannot build multiple pipeline - Step 3 shape invalid",
                extra={"step_number": 11, "step3_type": type(step3).__name__},
            )
            return None

        context = build_pipeline_context(step3)
        if context is None:
            self.logger.warning(
                "⚠️ Step 11: Cannot build multiple pipeline - missing initial_multiple or metric_value from Step 3",
                extra={
                    "step_number": 11,
                    "has_initial_multiple": first_present(
                        step3, "initial_multiple_mid", "multiple_p50"
                    )
                    is not None,
                    "has_metric_value": step3.get("primary_metric_value") is not None,
                },
            )
            return None

        collect_pipeline_steps(
            context,
            previous_results,
            get_previous_step_result_func,
            self.logger,
        )
        pipeline = build_pipeline_result(context, self.logger)
        self._log_pipeline_provenance(pipeline)
        self._log_pipeline_completion(pipeline)
        return pipeline

    def _log_pipeline_provenance(self, pipeline: MultiplePipeline) -> None:
        BankGradeValidator.log_calculation_provenance(
            "Multiple Pipeline Building",
            {
                "initial_multiple_mid": str(pipeline["initial_multiple_mid"]),
                "metric_type": pipeline["metric_type"],
                "metric_value": str(pipeline["metric_value"]),
                "stages_count": len(pipeline["stages"]),
            },
            {
                "final_multiple_mid": str(pipeline["final_multiple_mid"]),
                "total_reduction_pct": str(pipeline["total_reduction_percentage"]),
                "waterfall_steps": len(pipeline["discount_waterfall"]),
            },
            11,
        )

    def _log_pipeline_completion(self, pipeline: MultiplePipeline) -> None:
        self.logger.debug(
            "✅ Step 11: Multiple pipeline consolidated with complete waterfall (bank-grade audit trail)",
            extra={
                "step_number": 11,
                "initial_multiple_low": _optional_str(pipeline["initial_multiple_low"]),
                "initial_multiple_mid": str(pipeline["initial_multiple_mid"]),
                "initial_multiple_high": _optional_str(pipeline["initial_multiple_high"]),
                "final_multiple_low": _optional_str(pipeline["final_multiple_low"]),
                "final_multiple_mid": str(pipeline["final_multiple_mid"]),
                "final_multiple_high": _optional_str(pipeline["final_multiple_high"]),
                "total_reduction_pct": str(pipeline["total_reduction_percentage"]),
                "stages_count": len(pipeline["stages"]),
                "waterfall_steps": len(pipeline["discount_waterfall"]),
                "metric_type": pipeline["metric_type"],
                "metric_value": _optional_str(pipeline["metric_value"]),
                "multiple_progression": (
                    f"{pipeline['initial_multiple_mid']:.2f}x → "
                    f"{pipeline['final_multiple_mid']:.2f}x "
                    f"({pipeline['total_reduction_percentage']:.1f}% reduction)"
                ),
            },
        )


def _optional_str(value: object) -> Optional[str]:
    return str(value) if value else None
