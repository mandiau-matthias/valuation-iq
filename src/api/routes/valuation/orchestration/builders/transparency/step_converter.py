"""
Step Converter

Handles conversion of StepOutput to CalculationStep objects.
Refactored from TransparencyBuilder.convert_step_output_to_calculation_step
to reduce complexity from 30 to <8.
"""

from decimal import Decimal
from typing import Dict, Any, Optional

from src.api.routes.valuation.steps.base_step import StepOutput, StepStatus
from src.domain.transparency import CalculationStep
from src.utils.core import format_currency
from src.utils.decimal_helpers import to_decimal


class FormulaExtractor:
    """Extracts formula from step output metadata."""

    @staticmethod
    def extract(step_output: StepOutput) -> str:
        """Extract formula from metadata or construct from step name."""
        formula = (
            step_output.metadata.get("formula")
            or step_output.metadata.get("calculation", "")
        )
        if not formula:
            formula = f"{step_output.step_name} calculation"
        return formula


class RationaleExtractor:
    """Extracts rationale/explanation from step output metadata."""

    @staticmethod
    def extract(step_output: StepOutput) -> str:
        """Extract rationale from metadata."""
        return (
            step_output.metadata.get("rationale")
            or step_output.metadata.get("explanation", "")
        )


class InputOutputExtractor:
    """Extracts inputs and outputs from step output."""

    @staticmethod
    def extract_inputs(step_output: StepOutput) -> Dict[str, Decimal]:
        """Extract numeric inputs from metadata and result."""
        inputs = {}
        metadata_inputs = step_output.metadata.get("inputs", {})
        if isinstance(metadata_inputs, dict):
            for k, v in metadata_inputs.items():
                if isinstance(v, (int, float, Decimal)) and not isinstance(v, bool):
                    inputs[k] = to_decimal(v)

        # Also extract numeric inputs from result if available
        if isinstance(step_output.result, dict):
            for k, v in step_output.result.items():
                if (
                    isinstance(v, (int, float, Decimal))
                    and not isinstance(v, bool)
                    and k not in inputs
                ):
                    inputs[k] = to_decimal(v)

        return inputs

    @staticmethod
    def extract_outputs(step_output: StepOutput) -> Dict[str, Any]:
        """Extract outputs dictionary from step output."""
        return (
            step_output.result.copy()
            if isinstance(step_output.result, dict)
            else {}
        )

    @staticmethod
    def extract_output_value(outputs: Dict[str, Any]) -> Decimal:
        """Extract single output value for backward compatibility."""
        output_value = Decimal("0.0")
        if isinstance(outputs, dict):
            output_value = to_decimal(
                outputs.get("output", 0)
                or outputs.get("value", 0)
                or outputs.get("enterprise_value_mid", 0)
                or outputs.get("equity_value_mid", 0)
                or outputs.get("adjusted_value", 0)
                or 0
            )
        return output_value

    @staticmethod
    def format_output(output_value: Decimal) -> str:
        """Format output value for display."""
        if abs(output_value) < 1:
            return f"{output_value * 100:.2f}%"
        elif output_value >= 1000:
            return format_currency(output_value, currency="EUR", precision=0)
        else:
            return f"{output_value:.2f}"


class StatusHandler:
    """Handles status, skip_reason, and error extraction."""

    @staticmethod
    def extract_status(step_output: StepOutput) -> str:
        """Extract status as string."""
        return (
            step_output.status.value
            if isinstance(step_output.status, StepStatus)
            else str(step_output.status)
        )

    @staticmethod
    def extract_skip_reason(step_output: StepOutput) -> Optional[str]:
        """Extract skip_reason if step is skipped."""
        if step_output.status != StepStatus.SKIPPED:
            return None

        skip_reason = (
            step_output.metadata.get("skip_reason")
            or step_output.metadata.get("reason")
            or step_output.metadata.get("explanation")
        )
        if not skip_reason and step_output.error:
            skip_reason = step_output.error
        return skip_reason

    @staticmethod
    def extract_error(step_output: StepOutput) -> Optional[str]:
        """Extract error if step failed."""
        if step_output.status != StepStatus.FAILED:
            return None

        return (
            step_output.error
            or step_output.metadata.get("error")
            or step_output.metadata.get("error_message")
        )


class CalculationStepBuilder:
    """Builds CalculationStep object from extracted components."""

    @staticmethod
    def build(
        step_number: int,
        step_output: StepOutput,
        formula: str,
        rationale: str,
        inputs: Dict[str, Decimal],
        outputs: Dict[str, Any],
        output_value: Decimal,
        output_formatted: str,
        status_str: str,
        skip_reason: Optional[str],
        error: Optional[str],
    ) -> CalculationStep:
        """Build CalculationStep from all extracted components."""
        execution_time_ms = (
            step_output.execution_time_ms
            if hasattr(step_output, "execution_time_ms")
            else None
        )

        metadata = (
            step_output.metadata.copy()
            if hasattr(step_output, "metadata")
            else {}
        )

        return CalculationStep(
            step_number=step_number,
            calculation_name=step_output.step_name,
            formula=formula,
            inputs=inputs,
            output=output_value,
            output_formatted=output_formatted,
            explanation=rationale or step_output.metadata.get("explanation", ""),
            calculation_type=step_output.metadata.get(
                "calculation_type", f"step_{step_number}"
            ),
            status=status_str,
            skip_reason=skip_reason,
            error=error,
            execution_time_ms=execution_time_ms,
            metadata=metadata,
            rationale=rationale,
            outputs=outputs,
        )


class StepConverter:
    """
    Converts StepOutput to CalculationStep.

    Refactored from TransparencyBuilder.convert_step_output_to_calculation_step
    to reduce complexity from 30 to ~5.
    """

    @staticmethod
    def convert(step_output: StepOutput, step_number: int) -> CalculationStep:
        """
        Convert StepOutput from CalculationTriage to CalculationStep schema.

        Args:
            step_output: StepOutput object from CalculationTriage
            step_number: Step number (0-11)

        Returns:
            CalculationStep object with all fields populated
        """
        # Extract formula
        formula = FormulaExtractor.extract(step_output)

        # Extract rationale
        rationale = RationaleExtractor.extract(step_output)

        # Extract inputs and outputs
        inputs = InputOutputExtractor.extract_inputs(step_output)
        outputs = InputOutputExtractor.extract_outputs(step_output)
        output_value = InputOutputExtractor.extract_output_value(outputs)
        output_formatted = InputOutputExtractor.format_output(output_value)

        # Extract status and errors
        status_str = StatusHandler.extract_status(step_output)
        skip_reason = StatusHandler.extract_skip_reason(step_output)
        error = StatusHandler.extract_error(step_output)

        # Build CalculationStep
        return CalculationStepBuilder.build(
            step_number=step_number,
            step_output=step_output,
            formula=formula,
            rationale=rationale,
            inputs=inputs,
            outputs=outputs,
            output_value=output_value,
            output_formatted=output_formatted,
            status_str=status_str,
            skip_reason=skip_reason,
            error=error,
        )
