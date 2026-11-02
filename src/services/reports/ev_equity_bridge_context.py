"""EV-to-equity bridge policy for report aggregation."""

from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import Protocol, TypeAlias

from src.services.reports.balance_sheet_adjustment_context import (
    extract_balance_sheet_adjustments,
    extract_tax_latencies,
)
from src.services.reports.protocol_adapter import _attr
from src.services.reports.report_bridge_helpers import (
    build_bridge_residual_context,
    compute_ev_equity_bridge_residual,
)
from src.services.reports.report_metadata_access import get_metadata_bool
from src.services.reports.report_value_admission import report_decimal
from src.utils.decimal_helpers import safe_decimal_or_zero, safe_float

ReportMap: TypeAlias = dict[str, object]


class LoggerLike(Protocol):
    def info(self, msg: str, *args: object, **kwargs: object) -> object: ...

    def warning(self, msg: str, *args: object, **kwargs: object) -> object: ...


@dataclass(frozen=True)
class EvEquityBridgeResult:
    equity_value_low: Decimal | None
    equity_value: Decimal | None
    equity_value_high: Decimal | None
    net_debt: Decimal | None
    aligned_recommended_asking_price: Decimal | None
    asking_price_realigned: bool
    show_ev_equity_bridge: bool
    has_net_debt_adjustment: bool
    bridge_net_debt_operator: str
    bridge_net_debt_amount: Decimal
    # Compatibility field: report generation never redefines saved equity.
    phantom_bridge_suppressed: bool = False
    net_debt_known: bool = False


class BridgeContextBuilder(Protocol):
    def __call__(
        self,
        *,
        response: object,
        step_data: ReportMap,
        enterprise_value_mid: Decimal,
        equity_value_low: Decimal | None,
        equity_value: Decimal | None,
        equity_value_high: Decimal | None,
        tax_latency_net_impact: Decimal,
        balance_sheet_adjustments: list[ReportMap],
        has_balance_data: bool,
        is_dcf_only: bool,
        logger: LoggerLike | None = None,
    ) -> EvEquityBridgeResult: ...


@dataclass(frozen=True)
class PreparedEvEquityBridgeContext:
    tax_latencies: list[ReportMap]
    tax_latency_net_impact: object
    tax_latency_net_impact_decimal: Decimal
    balance_sheet_adjustments: list[ReportMap]
    bridge_context: EvEquityBridgeResult
    equity_value_low: Decimal | None
    equity_value: Decimal | None
    equity_value_high: Decimal | None
    net_debt_from_steps: Decimal | None
    aligned_recommended_asking_price: Decimal | None
    asking_price_realigned: bool
    show_ev_equity_bridge: bool
    show_enterprise_to_equity_bridge: bool
    has_net_debt_adjustment: bool
    bridge_net_debt_operator: str
    bridge_net_debt_amount: Decimal
    nwc_signed: Decimal
    displayed_net_debt: Decimal
    bridge_residual: Decimal
    show_bridge_cash_split: bool
    bridge_cash_total: Decimal
    bridge_operating_cash_held: Decimal
    bridge_excess_cash: Decimal
    bridge_ib_debt: Decimal


def _show_bridge(
    *,
    enterprise_value_mid: Decimal,
    equity_value: Decimal | None,
    net_debt: Decimal | None,
    tax_latency_net_impact: Decimal,
    balance_sheet_adjustments: list[ReportMap],
) -> bool:
    return equity_value is not None and (
        abs(enterprise_value_mid - equity_value) > Decimal("0.01")
        or (net_debt is not None and net_debt != Decimal("0"))
        or tax_latency_net_impact != Decimal("0")
        or len(balance_sheet_adjustments) > 0
    )


def _tax_latency_net_impact(
    step_data: ReportMap,
    tax_latencies: list[ReportMap],
) -> object:
    if step_data.get("tax_latency_total") is not None:
        return report_decimal(step_data["tax_latency_total"], "tax latency total")
    with localcontext() as context:
        context.prec = 100
        return sum(
            (report_decimal(row.get("amount"), "tax latency amount") for row in tax_latencies),
            Decimal("0"),
        )


def _seed_request_net_debt_if_missing(*, request: object | None, step_data: ReportMap) -> None:
    """Legacy compatibility: derive only from two complete, finite observations."""
    if step_data.get("net_debt") is not None or request is None:
        return
    year = getattr(request, "current_year_data", None)
    debt, cash = getattr(year, "total_debt", None), getattr(year, "cash", None)
    if debt is None or cash is None:
        return
    debt_amount = report_decimal(debt, "total debt")
    cash_amount = report_decimal(cash, "cash")
    with localcontext() as context:
        context.prec = 100
        step_data["net_debt"] = debt_amount - cash_amount
    step_data.setdefault("total_debt", debt_amount)
    step_data.setdefault("cash", cash_amount)


def _displayed_net_debt(
    *,
    has_net_debt_adjustment: bool,
    bridge_net_debt_amount: Decimal | None,
    bridge_net_debt_operator: str,
) -> Decimal:
    if not has_net_debt_adjustment or bridge_net_debt_amount is None:
        return Decimal("0")
    amount = safe_decimal_or_zero(bridge_net_debt_amount)
    return -amount if bridge_net_debt_operator == "+" else amount


def _bridge_residual(
    *,
    enterprise_value_mid: Decimal,
    equity_value: Decimal | None,
    displayed_net_debt: Decimal,
    tax_latency_net_impact: Decimal,
    balance_sheet_adjustments: list[ReportMap],
    nwc_signed: Decimal,
) -> Decimal:
    return compute_ev_equity_bridge_residual(
        enterprise_value_mid=enterprise_value_mid,
        equity_value=equity_value,
        net_debt=displayed_net_debt,
        tax_latency_net_impact=tax_latency_net_impact,
        balance_sheet_adjustments=balance_sheet_adjustments,
        nwc_surplus_deficit=nwc_signed,
    )


def _log_bridge_residual(
    *,
    logger: LoggerLike | None,
    enterprise_value_mid: Decimal,
    equity_value: Decimal | None,
    net_debt_from_steps: Decimal | None,
    tax_latency_net_impact: Decimal,
    nwc_signed: Decimal,
    bridge_residual: Decimal,
) -> None:
    if logger is None or bridge_residual == Decimal("0"):
        return
    logger.info(
        "ev_equity_bridge_residual_surfaced",
        extra={
            "enterprise_value_mid": float(enterprise_value_mid),
            "equity_value": float(equity_value) if equity_value is not None else None,
            "net_debt": (str(net_debt_from_steps) if net_debt_from_steps is not None else None),
            "tax_latency_net_impact": float(tax_latency_net_impact),
            "nwc_surplus_deficit": float(nwc_signed),
            "residual": float(bridge_residual),
            "note": (
                "Engine produced an equity_value that does not match the sum of the "
                "rendered bridge rows. Template will surface the delta as a "
                "reconciling line so the printed math adds up."
            ),
        },
    )


def _cash_split_context(
    *,
    step_data: ReportMap,
    has_net_debt_adjustment: bool,
    net_debt_from_steps: Decimal | None,
) -> tuple[bool, Decimal, Decimal, Decimal, Decimal]:
    cash_total = safe_decimal_or_zero(step_data.get("cash", 0))
    excess_cash = safe_decimal_or_zero(step_data.get("excess_cash", 0))
    ib_debt = safe_decimal_or_zero(step_data.get("total_debt", 0))
    operating_cash_held = (
        cash_total - excess_cash
        if bool(step_data.get("exemption_applied")) and cash_total > excess_cash
        else Decimal("0")
    )
    show_cash_split = bool(
        has_net_debt_adjustment
        and net_debt_from_steps is not None
        and operating_cash_held > Decimal("1")
        and cash_total > Decimal("0")
        and abs((ib_debt - excess_cash) - net_debt_from_steps) <= Decimal("1")
    )
    return show_cash_split, cash_total, operating_cash_held, excess_cash, ib_debt


def prepare_ev_equity_bridge_context(
    *,
    response: object,
    request: object | None,
    step_data: ReportMap,
    enterprise_value_mid: Decimal,
    equity_value_low: Decimal | None,
    equity_value: Decimal | None,
    equity_value_high: Decimal | None,
    has_balance_data: bool,
    is_dcf_only: bool,
    logger: LoggerLike | None = None,
    bridge_context_builder: BridgeContextBuilder | None = None,
) -> PreparedEvEquityBridgeContext:
    """Resolve report-facing EV/equity bridge state before context flattening."""
    tax_latencies = extract_tax_latencies(request=request, step_data=step_data)
    tax_latency_net_impact = _tax_latency_net_impact(step_data, tax_latencies)
    tax_latency_net_impact_decimal = safe_decimal_or_zero(tax_latency_net_impact)
    balance_sheet_adjustments = extract_balance_sheet_adjustments(
        request=request,
        step_data=step_data,
    )
    # Tax-category adjustments are already projected into tax_latencies above.
    # Keep their provenance in that section, but never subtract the same input
    # again as a generic balance-sheet adjustment in the bridge/waterfall.
    balance_sheet_adjustments = [
        row for row in balance_sheet_adjustments if row.get("category") != "tax_latency"
    ]

    build_bridge_context = bridge_context_builder or build_ev_equity_bridge_context
    bridge_context = build_bridge_context(
        response=response,
        step_data=step_data,
        enterprise_value_mid=enterprise_value_mid,
        equity_value_low=equity_value_low,
        equity_value=equity_value,
        equity_value_high=equity_value_high,
        tax_latency_net_impact=tax_latency_net_impact_decimal,
        balance_sheet_adjustments=balance_sheet_adjustments,
        has_balance_data=has_balance_data,
        is_dcf_only=is_dcf_only,
        logger=logger,
    )

    equity_value_low = bridge_context.equity_value_low
    equity_value = bridge_context.equity_value
    equity_value_high = bridge_context.equity_value_high
    net_debt_from_steps = bridge_context.net_debt
    show_enterprise_to_equity_bridge = get_metadata_bool(
        request,
        "show_enterprise_to_equity_bridge",
        True,
    )
    nwc_signed = safe_decimal_or_zero(step_data.get("nwc_surplus_deficit", 0))
    displayed_net_debt = _displayed_net_debt(
        has_net_debt_adjustment=bridge_context.has_net_debt_adjustment,
        bridge_net_debt_amount=bridge_context.bridge_net_debt_amount,
        bridge_net_debt_operator=bridge_context.bridge_net_debt_operator,
    )
    bridge_residual = _bridge_residual(
        enterprise_value_mid=enterprise_value_mid,
        equity_value=equity_value,
        displayed_net_debt=displayed_net_debt,
        tax_latency_net_impact=tax_latency_net_impact_decimal,
        balance_sheet_adjustments=balance_sheet_adjustments,
        nwc_signed=nwc_signed,
    )
    if not bridge_context.net_debt_known:
        # The unknown bridge has no reconciling amount, including a fabricated
        # residual interpreted as an "other adjustment".
        bridge_residual = Decimal("0")
    _log_bridge_residual(
        logger=logger,
        enterprise_value_mid=enterprise_value_mid,
        equity_value=equity_value,
        net_debt_from_steps=net_debt_from_steps,
        tax_latency_net_impact=tax_latency_net_impact_decimal,
        nwc_signed=nwc_signed,
        bridge_residual=bridge_residual,
    )
    (
        show_bridge_cash_split,
        bridge_cash_total,
        bridge_operating_cash_held,
        bridge_excess_cash,
        bridge_ib_debt,
    ) = _cash_split_context(
        step_data=step_data,
        has_net_debt_adjustment=bridge_context.has_net_debt_adjustment,
        net_debt_from_steps=net_debt_from_steps,
    )

    return PreparedEvEquityBridgeContext(
        tax_latencies=tax_latencies,
        tax_latency_net_impact=tax_latency_net_impact,
        tax_latency_net_impact_decimal=tax_latency_net_impact_decimal,
        balance_sheet_adjustments=balance_sheet_adjustments,
        bridge_context=bridge_context,
        equity_value_low=equity_value_low,
        equity_value=equity_value,
        equity_value_high=equity_value_high,
        net_debt_from_steps=net_debt_from_steps,
        aligned_recommended_asking_price=bridge_context.aligned_recommended_asking_price,
        asking_price_realigned=bridge_context.asking_price_realigned,
        show_ev_equity_bridge=bridge_context.show_ev_equity_bridge,
        show_enterprise_to_equity_bridge=show_enterprise_to_equity_bridge,
        has_net_debt_adjustment=bridge_context.has_net_debt_adjustment,
        bridge_net_debt_operator=bridge_context.bridge_net_debt_operator,
        bridge_net_debt_amount=bridge_context.bridge_net_debt_amount,
        nwc_signed=nwc_signed,
        displayed_net_debt=displayed_net_debt,
        bridge_residual=bridge_residual,
        show_bridge_cash_split=show_bridge_cash_split,
        bridge_cash_total=bridge_cash_total,
        bridge_operating_cash_held=bridge_operating_cash_held,
        bridge_excess_cash=bridge_excess_cash,
        bridge_ib_debt=bridge_ib_debt,
    )


def build_ev_equity_bridge_context(
    *,
    response: object,
    step_data: ReportMap,
    enterprise_value_mid: Decimal,
    equity_value_low: Decimal | None,
    equity_value: Decimal | None,
    equity_value_high: Decimal | None,
    tax_latency_net_impact: Decimal,
    balance_sheet_adjustments: list[ReportMap],
    has_balance_data: bool,
    is_dcf_only: bool,
    logger: LoggerLike | None = None,
) -> EvEquityBridgeResult:
    """Resolve report-facing EV/equity bridge values without fabricating balance data."""
    asking = getattr(response, "recommended_asking_price", None)
    aligned_recommended_asking_price = (
        (report_decimal(asking, "asking price") if asking is not None else Decimal("0"))
        if equity_value is not None
        else None
    )
    asking_price_realigned = False
    phantom_bridge_suppressed = False
    # Absence is not zero, and a valuation gap is not evidence of debt.
    # Financing, leases, cash restrictions and completion adjustments belong
    # to the saved calculation bridge; rebuilding it here would reprice a run.
    raw_net_debt = step_data.get("net_debt")
    net_debt = report_decimal(raw_net_debt, "net_debt") if raw_net_debt is not None else None
    net_debt_known = net_debt is not None and equity_value is not None
    has_net_debt_adjustment = net_debt_known and net_debt != 0
    bridge_net_debt_operator = "−" if net_debt is not None and net_debt > 0 else "+"
    return EvEquityBridgeResult(
        equity_value_low=equity_value_low,
        equity_value=equity_value,
        equity_value_high=equity_value_high,
        net_debt=net_debt,
        aligned_recommended_asking_price=aligned_recommended_asking_price,
        asking_price_realigned=asking_price_realigned,
        phantom_bridge_suppressed=phantom_bridge_suppressed,
        net_debt_known=net_debt_known,
        show_ev_equity_bridge=net_debt_known
        and _show_bridge(
            enterprise_value_mid=enterprise_value_mid,
            equity_value=equity_value,
            net_debt=net_debt,
            tax_latency_net_impact=tax_latency_net_impact,
            balance_sheet_adjustments=balance_sheet_adjustments,
        ),
        has_net_debt_adjustment=has_net_debt_adjustment,
        bridge_net_debt_operator=bridge_net_debt_operator,
        bridge_net_debt_amount=abs(net_debt) if net_debt is not None else Decimal("0"),
    )


def build_ev_equity_bridge_report_context(
    *,
    step_data: ReportMap,
    request: object | None,
    enterprise_value_mid: Decimal,
    enterprise_value_low: Decimal,
    enterprise_value_high: Decimal,
    net_debt: Decimal | None,
    show_ev_equity_bridge: bool,
    show_enterprise_to_equity_bridge: bool,
    has_net_debt_adjustment: bool,
    bridge_net_debt_amount: Decimal,
    bridge_net_debt_operator: str,
    bridge_residual: Decimal,
    tax_latencies: list[ReportMap],
    tax_latency_net_impact: object,
    balance_sheet_adjustments: list[ReportMap],
) -> dict[str, object]:
    """Flatten EV-to-equity bridge state into the main report template contract."""
    return {
        "enterprise_value_mid": safe_float(enterprise_value_mid),
        "enterprise_value_low": safe_float(enterprise_value_low),
        "enterprise_value_high": safe_float(enterprise_value_high),
        "net_debt": net_debt,
        "total_debt": step_data.get("total_debt", 0.0),
        "cash_balance": step_data.get("cash", 0.0),
        "excess_cash": step_data.get("excess_cash", 0.0),
        "exemption_applied": bool(step_data.get("exemption_applied")),
        "show_ev_equity_bridge": show_ev_equity_bridge,
        "show_enterprise_to_equity_bridge": show_enterprise_to_equity_bridge,
        "has_net_debt_adjustment": has_net_debt_adjustment,
        "bridge_net_debt_amount": (
            bridge_net_debt_amount if step_data.get("net_debt") is not None else None
        ),
        "bridge_net_debt_operator": bridge_net_debt_operator,
        "bridge_uses_net_cash_label": net_debt is not None and net_debt < 0,
        **build_bridge_residual_context(
            bridge_residual,
            enterprise_value_mid=enterprise_value_mid,
        ),
        "tax_latencies": tax_latencies,
        "tax_latency_net_impact": tax_latency_net_impact,
        "has_tax_latencies": len(tax_latencies) > 0,
        "balance_sheet_adjustments": balance_sheet_adjustments,
        "has_balance_sheet_adjustments": len(balance_sheet_adjustments) > 0,
        "bridge_nwc_adjustment": safe_float(
            safe_decimal_or_zero(step_data.get("nwc_surplus_deficit", 0))
        ),
        "exclude_real_estate": (
            bool(_attr(request, "exclude_real_estate", False)) if request else False
        ),
        "real_estate_book_value": (
            safe_float(_attr(request, "real_estate_book_value", 0)) if request else 0.0
        ),
        "estimated_market_rent": (
            safe_float(_attr(request, "estimated_market_rent", 0)) if request else 0.0
        ),
    }
