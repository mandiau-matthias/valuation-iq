"""Manual override policy for DCF calculator outputs.

The DCF engine owns the base financial math. This module owns the advisor-facing
override layer so WACC, terminal growth, and exit-multiple adjustments can evolve
without widening the calculator orchestrator.
"""

from decimal import Decimal
from typing import Optional, Protocol

from src.api.schemas import ValuationRequest
from src.domain.dcf.manual_assumption_validation import (
    require_override_cash_flows,
    require_positive_discount_rate,
    require_valid_gordon_growth,
)
from src.utils.adaptive_input_helpers import (
    get_dcf_exit_multiple_override,
    get_effective_dcf_wacc_override,
    get_percent_override,
)
from src.utils.decimal_helpers import to_decimal

from .dcf_calculation_inputs import resolve_terminal_ebitda_for_sensitivity
from .dcf_response_guards import safe_optional_decimal


class DCFOverrideLogger(Protocol):
    def info(self, message: str, *, extra: dict[str, object]) -> object: ...


def discount_to_present(
    value: Decimal,
    discount_rate: Decimal,
    period: Decimal,
) -> Decimal:
    discount_factor = (Decimal("1") + to_decimal(discount_rate)) ** to_decimal(period)
    return to_decimal(value) / discount_factor


def has_manual_dcf_overrides(request: ValuationRequest) -> bool:
    return (
        get_effective_dcf_wacc_override(request) is not None
        or get_percent_override(request, "dcf_terminal_growth_pct") is not None
        or get_dcf_exit_multiple_override(request) is not None
    )


def _resolve_terminal_ebitda(request: ValuationRequest) -> Optional[Decimal]:
    # Valuation and its sensitivity grid must price the same terminal period.
    return resolve_terminal_ebitda_for_sensitivity(request, safe_optional_decimal)


def apply_manual_dcf_overrides(
    request: ValuationRequest,
    *,
    enterprise_value: Decimal,
    equity_value: Decimal,
    wacc: Decimal,
    terminal_growth_rate: Decimal,
    terminal_value: Decimal,
    pv_terminal_value: Decimal,
    cash_flow_projections: list[Decimal],
    net_debt: Decimal,
    cash: Decimal,
    logger: DCFOverrideLogger,
    mid_year_discounting: bool = True,
) -> tuple[
    Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, list[Decimal], str, Decimal | None
]:
    override_wacc = get_effective_dcf_wacc_override(request)
    override_terminal_growth = get_percent_override(request, "dcf_terminal_growth_pct")
    override_exit_multiple = get_dcf_exit_multiple_override(request)

    if not has_manual_dcf_overrides(request):
        return (
            enterprise_value,
            equity_value,
            wacc,
            terminal_growth_rate,
            terminal_value,
            pv_terminal_value,
            [to_decimal(v) for v in cash_flow_projections],
            "gordon_growth",
            None,
        )

    applied_wacc = override_wacc if override_wacc is not None else wacc
    applied_growth = (
        override_terminal_growth if override_terminal_growth is not None else terminal_growth_rate
    )
    require_positive_discount_rate(applied_wacc)

    projected_fcfs = require_override_cash_flows(cash_flow_projections)

    def _discount_period(idx: int) -> Decimal:
        period = Decimal(str(idx))
        return period - Decimal("0.5") if mid_year_discounting else period

    pv_fcf_projections = [
        discount_to_present(
            fcf,
            applied_wacc,
            _discount_period(idx),
        )
        for idx, fcf in enumerate(projected_fcfs, start=1)
    ]

    terminal_ebitda = _resolve_terminal_ebitda(request)

    # Legacy FCFF-only rows do not establish terminal earnings. A signed,
    # reconciled forecast can supply them without falling back to historic EBITDA.
    dcf_input_mode = getattr(request, "dcf_input_mode", None)
    fcff_only = dcf_input_mode == "fcff_only"
    if fcff_only and override_exit_multiple is not None:
        from src.services.reports.verified_terminal_earnings import verified_fcff_terminal_ebitda

        terminal_ebitda = verified_fcff_terminal_ebitda(request)
    if terminal_ebitda is not None and terminal_ebitda <= 0:
        terminal_ebitda = None

    terminal_value_methodology = "gordon_growth"
    applied_exit_multiple = None
    use_exit_multiple = override_exit_multiple is not None and terminal_ebitda is not None
    if use_exit_multiple:
        recalculated_terminal_value = terminal_ebitda * override_exit_multiple
        terminal_value_methodology = "exit_multiple"
        applied_exit_multiple = override_exit_multiple
    else:
        require_valid_gordon_growth(applied_wacc, applied_growth)
        terminal_fcf = projected_fcfs[-1] * (Decimal("1") + applied_growth)
        terminal_spread = applied_wacc - applied_growth
        # Keep the engine's zero terminal-value policy for non-positive FCFF.
        # The explicit loss-making cash flows above remain fully priced.
        recalculated_terminal_value = (
            terminal_fcf / terminal_spread if projected_fcfs[-1] > 0 else Decimal("0")
        )

    recalculated_pv_terminal = discount_to_present(
        recalculated_terminal_value,
        applied_wacc,
        _discount_period(len(projected_fcfs)),
    )
    recalculated_enterprise = sum(pv_fcf_projections, Decimal("0")) + recalculated_pv_terminal
    recalculated_equity = recalculated_enterprise - net_debt + cash

    logger.info(
        "Applied manual DCF overrides from adaptive input studio",
        extra={
            "override_wacc": float(applied_wacc),
            "override_terminal_growth": float(applied_growth),
            "override_exit_multiple": (
                float(override_exit_multiple) if override_exit_multiple is not None else None
            ),
            "mid_year_discounting": mid_year_discounting,
            "recalculated_enterprise_value": float(recalculated_enterprise),
        },
    )

    return (
        recalculated_enterprise,
        recalculated_equity,
        applied_wacc,
        applied_growth,
        recalculated_terminal_value,
        recalculated_pv_terminal,
        pv_fcf_projections,
        terminal_value_methodology,
        applied_exit_multiple,
    )
