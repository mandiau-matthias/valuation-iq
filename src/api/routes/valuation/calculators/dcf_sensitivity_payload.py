"""Sensitivity payload builders and guards for DCF API responses."""

import math
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Optional, SupportsFloat, SupportsIndex, cast

SENSITIVITY_MATRIX_2D_STRING_KEYS = frozenset(
    {"secondary_axis_key", "secondary_axis_format", "terminal_value_policy"}
)


def sensitivity_scenario_values_are_finite(obj: object) -> bool:
    """
    True if nested structure contains only finite numerics and containers.

    Non-numeric strings are treated as opaque labels. Numeric strings, including
    "nan" and "inf", are checked for finiteness.
    """
    if obj is None:
        return True
    if isinstance(obj, Mapping):
        return all(sensitivity_scenario_values_are_finite(value) for value in obj.values())
    if isinstance(obj, Sequence) and not isinstance(obj, (str, bytes, bytearray)):
        return all(sensitivity_scenario_values_are_finite(value) for value in obj)
    if isinstance(obj, str):
        try:
            return math.isfinite(float(obj))
        except ValueError:
            return True
    try:
        if isinstance(obj, Decimal):
            return obj.is_finite()
        numeric_candidate = cast(str | bytes | bytearray | SupportsFloat | SupportsIndex, obj)
        return math.isfinite(float(numeric_candidate))
    except (TypeError, ValueError, OverflowError):
        return False


def sensitivity_matrix_2d_payload_is_finite(matrix: Mapping[str, object]) -> bool:
    """Full 2D matrix dict: numeric subtrees finite; metadata keys string or None."""
    for key, value in matrix.items():
        if key in SENSITIVITY_MATRIX_2D_STRING_KEYS:
            if value is not None and not isinstance(value, str):
                return False
            continue
        if not sensitivity_scenario_values_are_finite(value):
            return False
    return True


def sanitize_sensitivity_matrix_2d(matrix: object) -> Optional[dict[str, object]]:
    """
    Return matrix unchanged if the full payload is validator-safe; else None.

    Non-dict payloads are dropped so callers never pass corrupted coordinator
    output into ValuationValidator.
    """
    if matrix is None:
        return None
    if not isinstance(matrix, dict):
        return None
    if sensitivity_matrix_2d_payload_is_finite(matrix):
        return cast(dict[str, object], matrix)
    return None


def build_dcf_sensitivity_payload(
    *,
    fcf_values: list[Decimal],
    wacc: Decimal,
    terminal_growth_rate: Decimal,
    terminal_value: Decimal,
    terminal_value_methodology: str = "gordon_growth",
    terminal_exit_multiple: Decimal | None = None,
    terminal_ebitda: Decimal | None = None,
    mid_year_discounting: bool = True,
) -> tuple[dict[object, object], dict[object, object], Optional[dict[str, object]]]:
    """Build enterprise-value sensitivities from the priced DCF cash flows.

    ``terminal_value`` remains a compatibility argument; the scenario model
    derives each terminal value from its growth or exit-multiple assumptions.
    Nominal terminal-value sensitivities cannot replace enterprise values.
    """
    if not fcf_values:
        return {}, {}, None

    from src.domain.dcf.coordinators.sensitivity_analysis_coordinator import (
        SensitivityAnalysisCoordinator,
    )
    from src.domain.dcf_types import DCFConfiguration
    from src.domain.terminal_value_calculator import TerminalValueCalculator

    coordinator = SensitivityAnalysisCoordinator(
        terminal_value_calculator=TerminalValueCalculator(
            config=DCFConfiguration(mid_year_discounting=mid_year_discounting)
        )
    )
    is_exit_multiple = terminal_value_methodology == "exit_multiple"
    if is_exit_multiple and (terminal_exit_multiple is None or terminal_ebitda is None):
        raise ValueError("exit-multiple sensitivities require terminal EBITDA and multiple")
    sensitivity_results = coordinator.perform_enterprise_sensitivity_analysis(
        fcf_values=fcf_values,
        final_fcf=fcf_values[-1],
        base_wacc=wacc,
        base_growth=terminal_growth_rate,
        projection_years=len(fcf_values),
        terminal_ebitda=terminal_ebitda if is_exit_multiple else None,
        exit_multiple=terminal_exit_multiple if is_exit_multiple else None,
    )
    if is_exit_multiple:
        # Narrow after the completeness check above for the strict API boundary.
        assert terminal_exit_multiple is not None and terminal_ebitda is not None
        sensitivity_matrix_2d = coordinator.perform_exit_multiple_sensitivity_analysis(
            fcf_values=fcf_values,
            terminal_ebitda=terminal_ebitda,
            base_wacc=wacc,
            base_exit_multiple=terminal_exit_multiple,
            projection_years=len(fcf_values),
        )
    else:
        sensitivity_matrix_2d = coordinator.perform_2d_sensitivity_analysis(
            fcf_values=fcf_values,
            final_fcf=fcf_values[-1],
            base_wacc=wacc,
            base_growth=terminal_growth_rate,
            projection_years=len(fcf_values),
        )
    raw_wacc = sensitivity_results.get("sensitivity_wacc", {})
    raw_growth = sensitivity_results.get("sensitivity_growth", {})
    return (
        {str(key): value for key, value in raw_wacc.items()} if isinstance(raw_wacc, dict) else {},
        (
            {str(key): value for key, value in raw_growth.items()}
            if isinstance(raw_growth, dict)
            else {}
        ),
        sanitize_sensitivity_matrix_2d(sensitivity_matrix_2d),
    )
