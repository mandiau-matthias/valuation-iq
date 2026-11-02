"""ARR (Annual Recurring Revenue) multiple valuation method — SaaS only.

Eligibility, validation, and unavailability reasons are pre-computed in
``saas_valuation_adjuster.compute_saas_adjustment`` and surfaced here so
the orchestrator and report layers receive structured (not generic)
``MethodResult.unavailable_reason`` text.
"""

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Optional

from src.api.schemas.method_details import ArrMultipleDetails, build_arr_details
from src.api.schemas.stateless_api import MethodResult
from src.domain.financial_arithmetic import FinancialNumber, decimal_number, money
from src.domain.saas_valuation_adjuster import SaasAdjustmentResult
from src.domain.startup_valuation.cap_table import simulate_round
from src.domain.startup_valuation.schemas import CapTableSummary

from ._shared import debt_overhang_details, equity_from_ev


def _object_dict(payload: Mapping[str, object] | None) -> dict[str, object] | None:
    return dict(payload) if payload is not None else None


def _object_rows(
    rows: Sequence[Mapping[str, object]] | None,
) -> list[dict[str, object]] | None:
    return [dict(row) for row in rows] if rows is not None else None


def _details_payload(
    *,
    arr: FinancialNumber,
    enterprise_value: FinancialNumber,
    saas_adj: Optional[SaasAdjustmentResult],
    cap_table_simulator: Optional[dict[str, object]] = None,
    reference_enterprise_value: Optional[FinancialNumber] = None,
    reference_multiple: Optional[FinancialNumber] = None,
    method_adjustment_factor: Optional[FinancialNumber] = None,
) -> ArrMultipleDetails:
    return build_arr_details(
        arr=arr,
        enterprise_value=enterprise_value,
        saas_metrics=_object_dict(saas_adj.computed_metrics) if saas_adj else None,
        saas_adjustment_breakdown=(
            _object_rows(saas_adj.adjustment_breakdown) if saas_adj else None
        ),
        eligibility=(
            _object_dict(saas_adj.eligibility.as_dict())
            if saas_adj and saas_adj.eligibility
            else None
        ),
        validation_flags=_object_rows(
            saas_adj.validation.to_payload()
            if saas_adj and saas_adj.validation and saas_adj.validation.flags
            else None
        ),
        recurring_share=(
            float(saas_adj.eligibility.recurring_share)
            if saas_adj
            and saas_adj.eligibility
            and saas_adj.eligibility.recurring_share is not None
            else None
        ),
        cap_table_simulator=cap_table_simulator,
        reference_enterprise_value=reference_enterprise_value,
        reference_multiple=reference_multiple,
        method_adjustment_factor=method_adjustment_factor,
    )


def _build_unavailable(saas_adjustment: Optional[SaasAdjustmentResult]) -> MethodResult:
    """Construct an ``available=False`` result that explains *why* in the
    user's language, including the suggested alternative when one exists.
    """
    if saas_adjustment is None:
        # No SaaS adjustment at all → the method never computed an equity
        # value, so there is nothing to report (mirrors the eligibility-blocked
        # return below, which also uses ``value=None``). The previous code
        # referenced a bare ``equity`` name that does not exist in this scope,
        # so every non-SaaS valuation raised ``NameError: name 'equity' is not
        # defined`` here — caught by ``_safe_method`` and logged as
        # "ARR multiple calculation failed unexpectedly" on every run.
        return MethodResult(
            value=None,
            method_key="arr_multiple",
            label="ARR multiple",
            available=False,
            unavailable_reason="ARR multiple vereist SaaS-data (Annual Recurring Revenue).",
        )

    eligibility = saas_adjustment.eligibility
    if eligibility is not None and eligibility.blocking_reasons:
        reason = " ".join(eligibility.blocking_reasons)
        if eligibility.suggested_alternative_method:
            reason = (
                f"{reason} Aanbevolen alternatief: " f"{eligibility.suggested_alternative_method}."
            )
    else:
        reason = "ARR multiple vereist SaaS-data (Annual Recurring Revenue)."

    return MethodResult(
        value=None,
        method_key="arr_multiple",
        label="ARR multiple",
        available=False,
        unavailable_reason=reason,
        details=_details_payload(
            arr=float(saas_adjustment.arr) if saas_adjustment.arr else 0.0,
            enterprise_value=0.0,
            saas_adj=saas_adjustment,
        ),
    )


def calculate_arr_result(
    *,
    arr: FinancialNumber,
    arr_multiple: FinancialNumber,
    total_adjustment: FinancialNumber,
    total_debt: FinancialNumber,
    cash: FinancialNumber,
    ownership_multiplier: FinancialNumber,
    saas_adjustment: object | None,
    nwc_adjustment: FinancialNumber = 0.0,
    cap_table: Optional[CapTableSummary] = None,
    investment_amount_sought: Optional[Decimal] = None,
) -> MethodResult:
    """Compute the ARR-multiple valuation.

    When ``cap_table`` and/or ``investment_amount_sought`` are supplied
    AND the method produces a positive equity value, a cap-table
    simulation is attached to ``MethodResult.details.cap_table_simulator``.
    The simulator anchors at the post-debt **equity value** (not enterprise
    value): for cap-table purposes the founder's "pre-money today" is
    what the equity is worth net of debt, which is exactly what
    :func:`equity_from_ev` returns.  The simulator math itself is the
    single source of truth in
    :mod:`src.domain.startup_valuation.cap_table` — same code path the
    startup engine uses, so identical inputs produce identical outputs
    regardless of which valuation method routed here.

    All cap-table parameters are optional and default to ``None``;
    callers that don't pass them get the same ``MethodResult`` shape they
    got before this change (no ``cap_table_simulator`` key in details).
    """
    saas_adj: Optional[SaasAdjustmentResult] = (
        saas_adjustment if isinstance(saas_adjustment, SaasAdjustmentResult) else None
    )

    # Strict eligibility gate: even when ARR + multiple are present,
    # block if the SaaS adjuster decided the recurring share, validation,
    # or growth/retention signals are insufficient.
    if (
        saas_adj is not None
        and saas_adj.eligibility is not None
        and not saas_adj.eligibility.eligible
    ):
        return _build_unavailable(saas_adj)

    try:
        arr = decimal_number(arr, "ARR")
        arr_multiple = decimal_number(arr_multiple, "ARR multiple")
    except ValueError:
        return _build_unavailable(saas_adj)
    if arr <= 0 or arr_multiple <= 0:
        return _build_unavailable(saas_adj)
    reference_ev = arr * arr_multiple
    method_adjustment_factor = Decimal(1) - decimal_number(total_adjustment, "risk adjustment")
    if not 0 < method_adjustment_factor <= 1:
        return MethodResult(
            value=None,
            method_key="arr_multiple",
            label="ARR multiple",
            available=False,
            unavailable_reason="De methodologische aanpassing elimineert de ondernemingswaarde.",
        )
    ev = reference_ev * method_adjustment_factor
    equity = equity_from_ev(
        ev,
        total_adjustment=0.0,
        total_debt=total_debt,
        cash=cash,
        ownership_multiplier=ownership_multiplier,
        nwc_adjustment=nwc_adjustment,
    )

    if equity <= 0:
        return MethodResult(
            value=Decimal(str(round(equity, 2))),
            method_key="arr_multiple",
            label="ARR multiple",
            available=False,
            unavailable_reason="Na aftrek van schulden resteert er geen positieve aandeelhouderswaarde.",
            details={
                **_details_payload(
                    arr=round(arr, 2),
                    enterprise_value=round(ev, 2),
                    saas_adj=saas_adj,
                    reference_enterprise_value=round(reference_ev, 2),
                    reference_multiple=round(arr_multiple, 4),
                    method_adjustment_factor=round(method_adjustment_factor, 6),
                ),
                **debt_overhang_details(
                    enterprise_value=ev,
                    equity_value=equity,
                    total_debt=total_debt,
                    cash=cash,
                    ownership_multiplier=ownership_multiplier,
                    nwc_adjustment=nwc_adjustment,
                    total_adjustment=0.0,
                ),
            },
        )

    # Cap-table simulator — opt-in, runs only when the caller supplied
    # cap-table inputs OR an investment ask.  Uses the equity value as
    # the pre-money anchor (not EV), so post-money + dilution always
    # reconcile to the headline equity number on the report cover.
    cap_table_simulator_payload: Optional[dict[str, object]] = None
    if cap_table is not None or investment_amount_sought is not None:
        simulation = simulate_round(
            pre_money=Decimal(str(round(equity, 2))),
            investment_amount_sought=investment_amount_sought,
            cap_table=cap_table,
        )
        if simulation is not None:
            cap_table_simulator_payload = _object_dict(simulation.to_payload())

    return MethodResult(
        value=money(equity),
        equity_value=money(equity),
        enterprise_value=money(ev),
        method_key="arr_multiple",
        label="ARR multiple",
        multiple_used=Decimal(str(round(arr_multiple * method_adjustment_factor, 4))),
        available=True,
        details=_details_payload(
            arr=round(arr, 2),
            enterprise_value=round(ev, 2),
            saas_adj=saas_adj,
            cap_table_simulator=cap_table_simulator_payload,
            reference_enterprise_value=round(reference_ev, 2),
            reference_multiple=round(arr_multiple, 4),
            method_adjustment_factor=round(method_adjustment_factor, 6),
        ),
    )
