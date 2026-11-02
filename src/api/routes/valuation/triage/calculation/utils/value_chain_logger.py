"""
Value Chain Logger Utility

Provides logging for value chain transformations between steps.
"""

from typing import Dict

from src.api.routes.valuation.steps.base_step import CalculationStep, StepOutput, StepStatus
from src.utils.valuation_logger import ValuationLogger

logger = ValuationLogger(__name__)


class ValueChainLogger:
    """
    Utility class for logging value chain transformations.

    Responsibilities:
    - Log value chain transformations showing how values flow between steps
    - Track enterprise value and equity value changes
    """

    def __init__(self):
        """Initialize ValueChainLogger."""
        self.logger = logger

    def log_value_chain_transformation(
        self, step: CalculationStep, previous_results: Dict[int, StepOutput], output: StepOutput
    ) -> None:
        """
        Log value chain transformation showing how values flow between steps.

        This helps trace how enterprise value and equity value transform through the calculation.

        Args:
            step: The calculation step
            previous_results: Results from previous steps
            output: The output from the current step
        """
        input_ev = self._latest_completed_value(previous_results, ("enterprise_value_mid",))
        input_equity = self._latest_completed_value(
            previous_results, ("equity_value_mid", "ownership_adjusted_equity_mid")
        )
        output_ev = self._result_value(output.result, ("enterprise_value_mid",))
        output_equity = self._result_value(
            output.result, ("equity_value_mid", "ownership_adjusted_equity_mid")
        )

        if not self._has_any_value(input_ev, output_ev, input_equity, output_equity):
            return

        self.logger.debug(
            f"🔄 Value chain transformation for Step {step.step_number}",
            extra=self._transformation_payload(
                step=step,
                input_ev=input_ev,
                output_ev=output_ev,
                input_equity=input_equity,
                output_equity=output_equity,
            ),
        )

    def _latest_completed_value(
        self, previous_results: Dict[int, StepOutput], keys: tuple[str, ...]
    ) -> object | None:
        for step_num in sorted(previous_results.keys(), reverse=True):
            prev_output = previous_results[step_num]
            if prev_output.status != StepStatus.COMPLETED:
                continue

            value = self._result_value(prev_output.result, keys)
            if value is not None:
                return value
        return None

    def _result_value(
        self, result: dict[str, object] | None, keys: tuple[str, ...]
    ) -> object | None:
        if not result:
            return None

        for key in keys:
            value = result.get(key)
            if value is not None:
                return value
        return None

    def _transformation_payload(
        self,
        *,
        step: CalculationStep,
        input_ev: object | None,
        output_ev: object | None,
        input_equity: object | None,
        output_equity: object | None,
    ) -> dict[str, object]:
        return {
            "step_number": step.step_number,
            "step_name": step.step_name,
            "input_ev": input_ev,
            "output_ev": output_ev,
            "ev_change": self._change(input_ev, output_ev),
            "ev_change_pct": self._change_pct(input_ev, output_ev),
            "input_equity": input_equity,
            "output_equity": output_equity,
            "equity_change": self._change(input_equity, output_equity),
            "equity_change_pct": self._change_pct(input_equity, output_equity),
        }

    def _has_any_value(self, *values: object | None) -> bool:
        return any(value is not None for value in values)

    def _change(self, input_value, output_value):
        if input_value is None or output_value is None:
            return None
        return output_value - input_value

    def _change_pct(self, input_value, output_value):
        if input_value is None or output_value is None or input_value == 0:
            return None
        return (output_value - input_value) / input_value * 100
