"""Step 2 validation helpers for foundation-step execution."""

from __future__ import annotations

from collections.abc import Mapping

from src.api.routes.valuation.steps.base_step import StepOutput, StepStatus

from .step2_storage_validation import (
    STEP_1_PAYLOAD_KEYS,
    STEP_2_EXPECTED_KEYS,
    validate_step_2_storage,
)


class Step2FoundationValidator:
    """Validate Step 2 output without bloating the foundation coordinator."""

    def __init__(self, logger_instance):
        self.logger = logger_instance

    def validate_output(
        self, output: StepOutput, step: object, context: Mapping[str, object] | None
    ) -> StepOutput:
        """
        Validate Step 2 output before storage.

        Args:
            output: StepOutput from Step 2 execution
            step: Step object
            context: Execution context

        Returns:
            Validated StepOutput (may be modified if validation fails)
        """
        correlation_id = context.get("correlation_id") if context else None

        # Verify output has correct step_number
        if hasattr(output, "step_number") and output.step_number != 2:
            self.logger.error(
                "❌ CRITICAL: Step 2 output has wrong step_number!",
                extra={
                    "step_number": 2,
                    "output_step_number": output.step_number,
                    "correlation_id": correlation_id,
                    "operation": "step_number_mismatch",
                    "output_type": type(output).__name__,
                },
            )

        # Get actual result keys
        actual_result_keys = []
        if hasattr(output, "result") and isinstance(output.result, dict):
            actual_result_keys = list(output.result.keys())

        # Check if result has Step 1's keys (wrong!)
        has_step_1_keys = any(key in actual_result_keys for key in STEP_1_PAYLOAD_KEYS)
        has_step_2_keys = any(key in actual_result_keys for key in STEP_2_EXPECTED_KEYS)

        # DEFENSIVE CHECK: Verify result has Step 2's keys, not Step 1's
        if has_step_1_keys and not has_step_2_keys:
            self.logger.error(
                "❌ CRITICAL: Step 2 output has Step 1's keys instead of Step 2's keys!",
                extra={
                    "step_number": 2,
                    "correlation_id": correlation_id,
                    "operation": "wrong_keys_detected",
                    "actual_keys": actual_result_keys,
                    "expected_keys": list(STEP_2_EXPECTED_KEYS),
                    "step_1_keys_found": [
                        k for k in STEP_1_PAYLOAD_KEYS if k in actual_result_keys
                    ],
                    "output_step_number": (
                        output.step_number if hasattr(output, "step_number") else None
                    ),
                    "output_status": (output.status.value if hasattr(output, "status") else None),
                },
            )
            # Don't store wrong result - create a failed StepOutput
            return StepOutput(
                step_number=2,
                step_name=step.step_name if step else "Unknown",
                status=StepStatus.FAILED,
                result={},
                error="Step 2 output contained Step 1's result keys instead of Step 2's keys",
                metadata={
                    "detected_keys": actual_result_keys,
                    "expected_keys": list(STEP_2_EXPECTED_KEYS),
                    "error_type": "result_key_mismatch",
                },
            )

        return output

    def validate_storage(self, output: StepOutput, context: Mapping[str, object] | None) -> None:
        """
        Validate Step 2 result after storage.

        Args:
            output: StepOutput that was stored
            context: Execution context
        """
        validate_step_2_storage(self.logger, output, context)
