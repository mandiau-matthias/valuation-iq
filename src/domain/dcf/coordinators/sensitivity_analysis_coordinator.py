"""
Sensitivity Analysis Coordinator

Orchestrates sensitivity analysis for the DCF engine.
Handles WACC and growth rate scenario modeling.

RESPONSIBILITIES:
- Coordinate sensitivity analysis
- Generate WACC and growth rate scenarios
- Calculate scenario matrix

ARCHITECTURE:
This coordinator acts as a thin orchestration layer that:
1. Delegates to TerminalValueCalculator for sensitivity analysis
2. Formats sensitivity results

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive error handling
- Detailed logging
- No code duplication
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from src.domain.dcf_types import SENSITIVITY_RANGES, SensitivityType
from src.domain.terminal_value_calculator import TerminalValueCalculator
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SensitivityAnalysisCoordinator:
    """
    Coordinates sensitivity analysis for the DCF engine.

    This coordinator handles:
    1. Sensitivity analysis execution
    2. Scenario matrix generation
    """

    def __init__(
        self,
        terminal_value_calculator: TerminalValueCalculator,
    ) -> None:
        """
        Initialize sensitivity analysis coordinator.

        Args:
            terminal_value_calculator: Terminal value calculator instance
        """
        self.terminal_value_calculator = terminal_value_calculator
        self.logger = logger

    def perform_sensitivity_analysis(
        self,
        terminal_value: Decimal,
        wacc: Decimal,
        terminal_growth_rate: Decimal,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Perform sensitivity analysis on WACC and terminal growth rate.

        Args:
            terminal_value: Base terminal value
            wacc: Base WACC
            terminal_growth_rate: Base terminal growth rate

        Returns:
            Dictionary with sensitivity_wacc and sensitivity_growth scenarios
        """
        sensitivity_results = self.terminal_value_calculator.perform_sensitivity_analysis(
            terminal_value,
            wacc,
            terminal_growth_rate,
        )

        sensitivity_wacc = (
            sensitivity_results.get(SensitivityType.WACC, {}).scenarios
            if SensitivityType.WACC in sensitivity_results
            else {}
        )
        sensitivity_growth = (
            sensitivity_results.get(SensitivityType.TERMINAL_GROWTH, {}).scenarios
            if SensitivityType.TERMINAL_GROWTH in sensitivity_results
            else {}
        )

        return {
            "sensitivity_wacc": sensitivity_wacc,
            "sensitivity_growth": sensitivity_growth,
        }

    def _explicit_fcf_discount_period(self, index: int) -> Decimal:
        """Return the configured discount period for a zero-based projection row."""
        offset = (
            Decimal("0.5")
            if self.terminal_value_calculator.config.mid_year_discounting
            else Decimal("1")
        )
        return Decimal(str(index)) + offset

    def perform_enterprise_sensitivity_analysis(
        self,
        *,
        fcf_values: list[Decimal],
        final_fcf: Decimal,
        base_wacc: Decimal,
        base_growth: Decimal,
        projection_years: int,
        terminal_ebitda: Optional[Decimal] = None,
        exit_multiple: Optional[Decimal] = None,
    ) -> Dict[str, Dict[Decimal, Decimal]]:
        """Return EV scenarios using the same cash flows and timing as the DCF.

        TerminalValueCalculator's sensitivities are nominal terminal values.
        Published DCF sensitivities also need explicit cash flows and terminal
        discounting, including re-discounting every cash flow when WACC changes.
        """

        def scenario_values(kind: SensitivityType, base: Decimal) -> list[Decimal]:
            bounds = SENSITIVITY_RANGES[kind]
            value = Decimal(str(bounds.min_value))
            values = {base}
            while value <= Decimal(str(bounds.max_value)):
                values.add(value)
                value += Decimal(str(bounds.step_size))
            return sorted(values)

        wacc_values = [
            value for value in scenario_values(SensitivityType.WACC, base_wacc) if value > 0
        ]
        if exit_multiple is not None and terminal_ebitda is not None:
            grid = self.perform_exit_multiple_sensitivity_analysis(
                fcf_values=fcf_values,
                terminal_ebitda=terminal_ebitda,
                base_wacc=base_wacc,
                base_exit_multiple=exit_multiple,
                projection_years=projection_years,
                wacc_steps=[value - base_wacc for value in wacc_values],
                multiple_steps=[Decimal("0")],
            )
            return {
                "sensitivity_wacc": dict(
                    zip(grid["wacc_values"], (row[0] for row in grid["ev_matrix"]))
                ),
                "sensitivity_growth": {},  # Growth is not an input to exit-multiple TV.
            }

        wacc_values = [value for value in wacc_values if value > base_growth]
        growth_values = [
            value
            for value in scenario_values(SensitivityType.TERMINAL_GROWTH, base_growth)
            if Decimal("-1") < value < base_wacc
        ]
        wacc_grid = self.perform_2d_sensitivity_analysis(
            fcf_values=fcf_values,
            final_fcf=final_fcf,
            base_wacc=base_wacc,
            base_growth=base_growth,
            projection_years=projection_years,
            wacc_steps=[value - base_wacc for value in wacc_values],
            growth_steps=[Decimal("0")],
        )
        growth_grid = self.perform_2d_sensitivity_analysis(
            fcf_values=fcf_values,
            final_fcf=final_fcf,
            base_wacc=base_wacc,
            base_growth=base_growth,
            projection_years=projection_years,
            wacc_steps=[Decimal("0")],
            growth_steps=[value - base_growth for value in growth_values],
        )
        return {
            "sensitivity_wacc": dict(
                zip(wacc_grid["wacc_values"], (row[0] for row in wacc_grid["ev_matrix"]))
            ),
            "sensitivity_growth": dict(
                zip(growth_grid["growth_values"], growth_grid["ev_matrix"][0])
            ),
        }

    def perform_2d_sensitivity_analysis(
        self,
        *,
        fcf_values: list[Decimal],
        final_fcf: Decimal,
        base_wacc: Decimal,
        base_growth: Decimal,
        projection_years: int,
        wacc_steps: Optional[list[Decimal]] = None,
        growth_steps: Optional[list[Decimal]] = None,
    ) -> Dict[str, Any]:
        """Price labelled scenarios exactly; inadmissible cells remain unavailable."""
        wacc_steps = wacc_steps or [Decimal("-0.01"), Decimal("0"), Decimal("0.01")]
        growth_steps = growth_steps or [Decimal("-0.01"), Decimal("0"), Decimal("0.01")]

        wacc_values = [base_wacc + step for step in wacc_steps]
        growth_values = [base_growth + step for step in growth_steps]
        ev_matrix: list[list[Decimal | None]] = []
        unavailable_reasons: list[list[str | None]] = []
        terminal_value_eligible = final_fcf > 0

        for wacc in wacc_values:
            row: list[Decimal | None] = []
            reasons: list[str | None] = []
            if not wacc.is_finite() or wacc <= 0:
                ev_matrix.append([None] * len(growth_values))
                unavailable_reasons.append(["discount_rate_not_positive"] * len(growth_values))
                continue
            discount_base = Decimal("1") + wacc
            pv_fcf_sum = sum(
                fcf / (discount_base ** self._explicit_fcf_discount_period(i))
                for i, fcf in enumerate(fcf_values)
            )
            for growth in growth_values:
                if not growth.is_finite() or not Decimal("-1") < growth < wacc:
                    row.append(None)
                    reasons.append("terminal_growth_outside_model_domain")
                    continue

                # Match the canonical terminal-value policy exactly. A
                # non-positive terminal FCFF cannot support a Gordon-growth
                # perpetuity, so the sensitivity grid holds terminal value at
                # zero rather than subtracting a fabricated negative perpetuity.
                terminal_value = (
                    final_fcf * (Decimal("1") + growth) / (wacc - growth)
                    if terminal_value_eligible
                    else Decimal("0")
                )
                pv_terminal_value = self.terminal_value_calculator.discount_terminal_value(
                    terminal_value,
                    wacc,
                    projection_years,
                )
                enterprise_value = pv_fcf_sum + pv_terminal_value
                row.append(enterprise_value)
                reasons.append(None)
            ev_matrix.append(row)
            unavailable_reasons.append(reasons)

        return {
            "schema_version": "dcf_sensitivity.v2",
            "unavailable_reasons": unavailable_reasons,
            "base_wacc": base_wacc,
            "base_secondary_value": base_growth,
            "wacc_values": wacc_values,
            "growth_values": growth_values,
            "secondary_values": growth_values,
            "secondary_axis_key": "terminal_growth",
            "secondary_axis_format": "percent",
            "ev_matrix": ev_matrix,
            "terminal_value_policy": (
                "gordon_growth" if terminal_value_eligible else "zero_non_positive_terminal_fcff"
            ),
        }

    def perform_exit_multiple_sensitivity_analysis(
        self,
        *,
        fcf_values: list[Decimal],
        terminal_ebitda: Decimal,
        base_wacc: Decimal,
        base_exit_multiple: Decimal,
        projection_years: int,
        wacc_steps: Optional[list[Decimal]] = None,
        multiple_steps: Optional[list[Decimal]] = None,
    ) -> Dict[str, Any]:
        """Return a WACC x exit-multiple EV matrix when exit multiple drives terminal value."""
        wacc_steps = wacc_steps or [Decimal("-0.01"), Decimal("0"), Decimal("0.01")]
        multiple_steps = multiple_steps or [Decimal("-1"), Decimal("0"), Decimal("1")]

        wacc_values = [base_wacc + step for step in wacc_steps]
        exit_multiple_values = [base_exit_multiple + step for step in multiple_steps]
        ev_matrix: list[list[Decimal | None]] = []
        unavailable_reasons: list[list[str | None]] = []

        for wacc in wacc_values:
            if not wacc.is_finite() or wacc <= 0:
                ev_matrix.append([None] * len(exit_multiple_values))
                unavailable_reasons.append(
                    ["discount_rate_not_positive"] * len(exit_multiple_values)
                )
                continue
            pv_fcf_sum = sum(
                fcf / ((Decimal("1") + wacc) ** self._explicit_fcf_discount_period(i))
                for i, fcf in enumerate(fcf_values)
            )
            row: list[Decimal | None] = []
            reasons: list[str | None] = []
            for exit_multiple in exit_multiple_values:
                if not exit_multiple.is_finite() or exit_multiple <= 0:
                    row.append(None)
                    reasons.append("exit_multiple_not_positive")
                    continue
                terminal_value = terminal_ebitda * exit_multiple
                pv_terminal_value = self.terminal_value_calculator.discount_terminal_value(
                    terminal_value,
                    wacc,
                    projection_years,
                )
                row.append(pv_fcf_sum + pv_terminal_value)
                reasons.append(None)
            ev_matrix.append(row)
            unavailable_reasons.append(reasons)

        return {
            "schema_version": "dcf_sensitivity.v2",
            "unavailable_reasons": unavailable_reasons,
            "base_wacc": base_wacc,
            "base_secondary_value": base_exit_multiple,
            "wacc_values": wacc_values,
            "secondary_values": exit_multiple_values,
            "secondary_axis_key": "exit_multiple",
            "secondary_axis_format": "multiple",
            "ev_matrix": ev_matrix,
        }
