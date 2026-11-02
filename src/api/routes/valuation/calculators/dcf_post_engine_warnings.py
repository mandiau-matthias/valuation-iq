"""Post-engine DCF warnings that depend on shaped engine outputs."""

from decimal import Decimal

from src.utils.decimal_helpers import to_decimal


def extend_post_engine_dcf_warnings(
    warnings: list[dict[str, object]],
    *,
    terminal_value_pct_of_total: object,
    explicit_forecast_pct_of_total: object,
    wacc: object,
    cost_of_equity: object,
) -> list[dict[str, object]]:
    """Add diagnostics that require both engine math and response shaping outputs."""
    extended = list(warnings)
    _append_terminal_value_concentration_warning(
        extended,
        terminal_value_pct_of_total=terminal_value_pct_of_total,
        explicit_forecast_pct_of_total=explicit_forecast_pct_of_total,
    )
    _append_wacc_ceiling_clamp_warning(extended, wacc=wacc, cost_of_equity=cost_of_equity)
    return extended


def _append_terminal_value_concentration_warning(
    warnings: list[dict[str, object]],
    *,
    terminal_value_pct_of_total: object,
    explicit_forecast_pct_of_total: object,
) -> None:
    if terminal_value_pct_of_total is None or explicit_forecast_pct_of_total is None:
        return

    try:
        tv_pct = float(terminal_value_pct_of_total)
    except (TypeError, ValueError):
        return

    if tv_pct > 85.0:
        warnings.append(
            {
                "type": "terminal_value_concentration",
                "severity": "high",
                "message": (
                    f"Terminal value accounts for {tv_pct:.0f}% of total enterprise value - "
                    f"the steady-state perpetuity dominates the explicit forecast period."
                ),
                "impact": (
                    "Sensitivity to the terminal growth rate and discount rate is concentrated; "
                    "a 1pp change in WACC or g can move EV materially."
                ),
                "recommendation": (
                    "Either extend the forecast horizon to 7-10 years so the firm reaches a "
                    "credible steady state, or switch the terminal value to an exit-multiple "
                    "anchored to peer EV/EBITDA."
                ),
            }
        )
        return

    if tv_pct > 75.0:
        warnings.append(
            {
                "type": "terminal_value_concentration",
                "severity": "medium",
                "message": (
                    f"Terminal value accounts for {tv_pct:.0f}% of total enterprise value, "
                    f"above the 75% threshold typical for fully-modelled forecasts."
                ),
                "impact": (
                    "Result is more sensitive to terminal-period assumptions than to the "
                    "explicit cash-flow projection."
                ),
                "recommendation": (
                    "Document why the firm hasn't yet reached steady state, or extend the "
                    "forecast horizon."
                ),
            }
        )


def _append_wacc_ceiling_clamp_warning(
    warnings: list[dict[str, object]],
    *,
    wacc: object,
    cost_of_equity: object,
) -> None:
    try:
        wacc_decimal = to_decimal(wacc) if wacc is not None else None
        cost_of_equity_decimal = to_decimal(cost_of_equity) if cost_of_equity is not None else None
    except (ArithmeticError, ValueError, TypeError):
        return

    if (
        cost_of_equity_decimal is not None
        and wacc_decimal is not None
        and cost_of_equity_decimal > Decimal("0.30") + Decimal("0.001")
        and abs(wacc_decimal - Decimal("0.30")) < Decimal("0.001")
    ):
        warnings.append(
            {
                "type": "wacc_ceiling_clamp",
                "severity": "high",
                "message": (
                    f"Academic build-up cost of equity ({float(cost_of_equity_decimal) * 100:.1f}%) "
                    f"exceeds the engine's WACC ceiling (30.0%) - the displayed WACC is a "
                    f"regulatory clamp, not the model output."
                ),
                "impact": (
                    "Discounting at 30% understates the firm's true cost of capital and "
                    "therefore overstates the DCF enterprise value. For ultra-micro firms "
                    "this is an academic limitation; consider a multiples-based approach as "
                    "primary methodology."
                ),
                "recommendation": (
                    "Review whether DCF is the right primary methodology for this profile, "
                    "or document the clamped WACC explicitly in the disclosure section."
                ),
            }
        )
