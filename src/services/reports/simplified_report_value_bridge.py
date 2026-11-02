"""Read saved values for the legacy simplified report without repricing them."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import Protocol

from src.domain.financial_arithmetic import money
from src.services.reports.report_value_admission import admitted_band, report_decimal


class LoggerLike(Protocol):
    def info(self, msg: str, *args: object, **kwargs: object) -> object: ...


@dataclass(frozen=True)
class SimplifiedReportValueBridge:
    valuation_mid: Decimal | None
    valuation_low: Decimal | None
    valuation_high: Decimal | None
    multiple_low: Decimal | None
    multiple_high: Decimal | None
    equity_value: Decimal | None
    has_net_debt_adjustment: bool
    bridge_net_debt_amount: Decimal | None
    bridge_net_debt_operator: str
    bridge_uses_net_cash_label: bool
    has_weighted_synthesis: bool
    synthesis_formula_display: str | None
    is_dcf_only: bool
    value_basis: str | None
    enterprise_value_mid: Decimal | None
    formula_reconciles: bool


def _read(source: object, name: str) -> object:
    return source.get(name) if isinstance(source, Mapping) else getattr(source, name, None)


def _optional(source: object, name: str) -> Decimal | None:
    value = _read(source, name)
    return report_decimal(value, name) if value is not None else None


def _point(source: object, *names: str) -> Decimal | None:
    for name in names:
        value = _optional(source, name)
        if value is not None:
            return value
    return None


def _bounds(
    source: object, mid: Decimal | None, low: str, high: str
) -> tuple[Decimal | None, Decimal | None]:
    lower, upper = _optional(source, low), _optional(source, high)
    if lower is None and upper is None:
        return None, None
    band = admitted_band(lower, mid, upper)
    return band[0], band[2]


def _enterprise_source(response: object) -> tuple[object, Decimal | None]:
    top = _optional(response, "enterprise_value_mid")
    if top is not None:
        return response, top
    methodology = str(_read(response, "methodology") or "").upper()
    # An independently priced comparison leg cannot replace a hybrid headline.
    if "HYBRID" in methodology or _read(response, "weighted_valuation") is not None:
        return response, None
    key = "dcf_valuation" if "DCF" in methodology else "multiples_valuation"
    method = _read(response, key)
    return method, _point(method, "enterprise_value", "enterprise_value_mid", "ev_mid")


def get_simplified_enterprise_value(response: object) -> Decimal | None:
    """Read EV, including zero/losses; equity plus an unknown bridge is not EV."""
    return _enterprise_source(response)[1]


def _saved_net_debt(response: object) -> Decimal | None:
    details = _read(response, "detailed_results")
    debt = _optional(details, "net_debt")
    if debt is not None:
        return debt
    return _optional(_read(details, "step_7"), "net_debt")


def has_simplified_balance_inputs(response: object, request: object | None) -> bool:
    """Compatibility presence check; it does not authorize a report calculation."""
    details = _read(response, "detailed_results")
    step = _read(details, "step_7")
    for source in (details, step, _read(step, "inputs"), _read(request, "current_year_data")):
        if _optional(source, "net_debt") is not None:
            return True
        debt = _point(source, "total_debt", "debt", "total_debt_amount")
        cash = _point(source, "cash", "cash_and_equivalents", "cash_amount")
        if debt is not None and cash is not None:
            return True
    return False


def build_simplified_report_value_bridge(
    *,
    response: object,
    request: object | None,
    metric_value: Decimal,
    multiple: Decimal | None,
    multiple_low: Decimal | None,
    multiple_high: Decimal | None,
    get_request_locale: Callable[[object | None], str],
    logger: LoggerLike | None = None,
) -> SimplifiedReportValueBridge:
    """Project the saved band and basis, with no formula or spread fallback.

    Legacy weighted payloads explicitly named ``blended_equity_value`` retain
    that basis unless their version supplies ``value_basis=enterprise_value``.
    Contributions are method comparisons; their extremes are not saved bounds.
    """
    ev_source, ev = _enterprise_source(response)
    equity = _optional(response, "equity_value_mid")
    weighted = _read(response, "weighted_valuation")
    weighted_point = _point(weighted, "blended_equity_value")
    has_weighted = weighted_point is not None
    if has_weighted:
        basis = str(_read(weighted, "value_basis") or "equity_value")
        if basis not in {"equity_value", "enterprise_value"}:
            raise ValueError("Unsupported saved weighted valuation basis")
        mid = weighted_point
        low, high = _bounds(weighted, mid, "valuation_range_low", "valuation_range_high")
        if basis == "equity_value":
            equity = mid
        else:
            ev = mid
    elif ev is not None:
        mid, basis = ev, "enterprise_value"
        low, high = _bounds(ev_source, mid, "enterprise_value_low", "enterprise_value_high")
    elif equity is not None:
        mid, basis = equity, "equity_value"
        low, high = _bounds(response, mid, "equity_value_low", "equity_value_high")
    else:
        mid, low, high, basis = None, None, None, None

    # Admit, never sort or synthesize, a supplied pricing-multiple range.
    lower, upper = multiple_low, multiple_high
    if lower is not None or upper is not None:
        lower, _, upper = admitted_band(lower, multiple, upper)
        if lower < 0:
            raise ValueError("Multiple bounds cannot be negative")
    debt = _saved_net_debt(response)
    with localcontext() as ctx:
        ctx.prec = 100
        bridge_reconciles = (
            basis == "enterprise_value"
            and ev is not None
            and equity is not None
            and debt is not None
            and ev - debt == equity
        )
        formula_reconciles = (
            not has_weighted
            and basis == "enterprise_value"
            and ev is not None
            and multiple is not None
            and money(
                report_decimal(metric_value, "metric_value") * report_decimal(multiple, "multiple")
            )
            == ev
        )
    show_debt = bridge_reconciles and debt is not None and debt != 0
    methodology = str(_read(response, "methodology") or "").upper()
    return SimplifiedReportValueBridge(
        valuation_mid=mid,
        valuation_low=low,
        valuation_high=high,
        multiple_low=lower,
        multiple_high=upper,
        equity_value=equity,
        has_net_debt_adjustment=show_debt,
        bridge_net_debt_amount=abs(debt) if show_debt and debt is not None else Decimal("0"),
        bridge_net_debt_operator="+" if debt is not None and debt < 0 else "−",
        bridge_uses_net_cash_label=show_debt and debt is not None and debt < 0,
        has_weighted_synthesis=has_weighted,
        synthesis_formula_display=None,
        is_dcf_only="DCF" in methodology and "HYBRID" not in methodology,
        value_basis=basis,
        enterprise_value_mid=ev,
        formula_reconciles=formula_reconciles,
    )
