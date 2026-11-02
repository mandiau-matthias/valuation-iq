"""Multiples-only EV/equity headline tie-out helpers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, TypeAlias

from src.utils.decimal_helpers import safe_decimal_or_zero

ReportMap: TypeAlias = dict[str, object]
HeadlineTieOut: TypeAlias = tuple[Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal]


class LoggerLike(Protocol):
    def info(self, msg: str, *args: object, **kwargs: object) -> object: ...


@dataclass(frozen=True)
class MultiplesOnlyTieOutLegs:
    multiples_ev: Decimal
    multiples_equity: Decimal
    net_debt_bridge: Decimal


@dataclass(frozen=True)
class MultiplesOnlyRebuildBasis:
    rebuilt_mid: Decimal
    rebuild_ratio: Decimal
    net_debt_bridge: Decimal


def _decimal(value: object) -> Decimal:
    return safe_decimal_or_zero(value)


def _value(source: object, key: str) -> object | None:
    if source is None:
        return None
    if isinstance(source, Mapping):
        return source.get(key)
    return getattr(source, key, None)


def _pipeline_effective_multiple(step_data: ReportMap) -> Decimal | None:
    pipeline = step_data.get("multiple_pipeline")
    if not isinstance(pipeline, Mapping):
        return None

    final_multiple = pipeline.get("final_multiple_mid")
    if final_multiple is None:
        final_multiple = pipeline.get("final_multiple")
    if final_multiple is None:
        return None
    return _decimal(final_multiple)


def _headline_tie_out(
    *,
    enterprise_value_low: Decimal,
    enterprise_value_mid: Decimal,
    enterprise_value_high: Decimal,
    equity_value_low: Decimal,
    equity_value: Decimal,
    equity_value_high: Decimal,
    formula_metric_value: Decimal,
) -> HeadlineTieOut:
    return (
        enterprise_value_low,
        enterprise_value_mid,
        enterprise_value_high,
        equity_value_low,
        equity_value,
        equity_value_high,
        formula_metric_value,
    )


def apply_multiples_only_tie_out(
    *,
    response: object,
    step_data: ReportMap,
    logger: LoggerLike | None,
    enterprise_value_low: Decimal,
    enterprise_value_mid: Decimal,
    enterprise_value_high: Decimal,
    equity_value_low: Decimal,
    equity_value: Decimal,
    equity_value_high: Decimal,
    formula_metric_value: Decimal,
    ev_metric: Decimal,
    applied_multiple: Decimal,
    multiple_low: Decimal,
    multiple_high: Decimal,
    is_multiples_only_ev: bool,
) -> HeadlineTieOut:
    unchanged = _headline_tie_out(
        enterprise_value_low=enterprise_value_low,
        enterprise_value_mid=enterprise_value_mid,
        enterprise_value_high=enterprise_value_high,
        equity_value_low=equity_value_low,
        equity_value=equity_value,
        equity_value_high=equity_value_high,
        formula_metric_value=formula_metric_value,
    )
    if not (is_multiples_only_ev and applied_multiple > 0 and ev_metric > 0):
        return unchanged

    rebuilt_mid = (ev_metric * applied_multiple).quantize(Decimal("0.01"))
    legs = _multiples_only_tie_out_legs(
        response=response,
        enterprise_value_mid=enterprise_value_mid,
        equity_value=equity_value,
    )
    rebuild_basis = _multiples_only_rebuild_basis(
        step_data=step_data,
        ev_metric=ev_metric,
        applied_multiple=applied_multiple,
        rebuilt_mid=rebuilt_mid,
        legs=legs,
    )
    if not _should_apply_multiples_only_tie_out(
        rebuilt_mid=rebuild_basis.rebuilt_mid,
        enterprise_value_mid=enterprise_value_mid,
        equity_value=equity_value,
        net_debt_bridge=rebuild_basis.net_debt_bridge,
    ):
        return unchanged

    values = _rebuilt_multiples_only_tie_out_values(
        rebuilt_mid=rebuild_basis.rebuilt_mid,
        rebuild_ratio=rebuild_basis.rebuild_ratio,
        net_debt_bridge=rebuild_basis.net_debt_bridge,
        ev_metric=ev_metric,
        multiple_low=multiple_low,
        multiple_high=multiple_high,
    )
    _log_multiples_only_tie_out(
        logger=logger,
        enterprise_value_mid=enterprise_value_mid,
        rebuilt_mid=rebuild_basis.rebuilt_mid,
        multiples_ev=legs.multiples_ev,
        applied_multiple=applied_multiple,
        ev_metric=ev_metric,
        net_debt_bridge=rebuild_basis.net_debt_bridge,
    )
    return values


def _multiples_only_tie_out_legs(
    *,
    response: object,
    enterprise_value_mid: Decimal,
    equity_value: Decimal,
) -> MultiplesOnlyTieOutLegs:
    multiples_valuation = getattr(response, "multiples_valuation", None)
    multiples_ev = _decimal(_value(multiples_valuation, "enterprise_value"))
    multiples_equity = _decimal(_value(multiples_valuation, "equity_value"))
    net_debt_bridge = (
        multiples_ev - multiples_equity
        if multiples_ev > 0 and multiples_equity > 0
        else enterprise_value_mid - equity_value
    )
    return MultiplesOnlyTieOutLegs(
        multiples_ev=multiples_ev,
        multiples_equity=multiples_equity,
        net_debt_bridge=net_debt_bridge,
    )


def _multiples_only_rebuild_basis(
    *,
    step_data: ReportMap,
    ev_metric: Decimal,
    applied_multiple: Decimal,
    rebuilt_mid: Decimal,
    legs: MultiplesOnlyTieOutLegs,
) -> MultiplesOnlyRebuildBasis:
    net_debt_bridge = legs.net_debt_bridge

    rebuild_ratio = Decimal("1")
    effective_multiple = _pipeline_effective_multiple(step_data)
    applied_is_gross = (
        effective_multiple is not None
        and effective_multiple > 0
        and legs.multiples_equity > 0
        and abs(effective_multiple - applied_multiple) > Decimal("0.01")
    )
    if applied_is_gross:
        effective_ev_mid = (ev_metric * effective_multiple).quantize(Decimal("0.01"))
        if effective_ev_mid > 0 and rebuilt_mid > 0:
            rebuild_ratio = effective_ev_mid / rebuilt_mid
            rebuilt_mid = effective_ev_mid
            net_debt_bridge = (effective_ev_mid - legs.multiples_equity).quantize(Decimal("0.01"))
            step_data["effective_multiple"] = effective_multiple
    return MultiplesOnlyRebuildBasis(
        rebuilt_mid=rebuilt_mid,
        rebuild_ratio=rebuild_ratio,
        net_debt_bridge=net_debt_bridge,
    )


def _should_apply_multiples_only_tie_out(
    *,
    rebuilt_mid: Decimal,
    enterprise_value_mid: Decimal,
    equity_value: Decimal,
    net_debt_bridge: Decimal,
) -> bool:
    tolerance = max(Decimal("1"), enterprise_value_mid * Decimal("0.005"))
    slot_is_wrong = abs(rebuilt_mid - enterprise_value_mid) > Decimal("1")
    ev_holds_equity = abs(enterprise_value_mid - equity_value) <= tolerance
    net_bridge_material = abs(net_debt_bridge) > tolerance
    return rebuilt_mid > 0 and slot_is_wrong and ev_holds_equity and net_bridge_material


def _rebuilt_multiples_only_tie_out_values(
    *,
    rebuilt_mid: Decimal,
    rebuild_ratio: Decimal,
    net_debt_bridge: Decimal,
    ev_metric: Decimal,
    multiple_low: Decimal,
    multiple_high: Decimal,
) -> HeadlineTieOut:
    rebuilt_low = (
        (multiple_low * ev_metric * rebuild_ratio).quantize(Decimal("0.01"))
        if multiple_low > 0
        else (rebuilt_mid * Decimal("0.85")).quantize(Decimal("0.01"))
    )
    rebuilt_high = (
        (multiple_high * ev_metric * rebuild_ratio).quantize(Decimal("0.01"))
        if multiple_high > 0
        else (rebuilt_mid * Decimal("1.15")).quantize(Decimal("0.01"))
    )
    return _headline_tie_out(
        enterprise_value_low=rebuilt_low,
        enterprise_value_mid=rebuilt_mid,
        enterprise_value_high=rebuilt_high,
        equity_value_low=(rebuilt_low - net_debt_bridge).quantize(Decimal("0.01")),
        equity_value=(rebuilt_mid - net_debt_bridge).quantize(Decimal("0.01")),
        equity_value_high=(rebuilt_high - net_debt_bridge).quantize(Decimal("0.01")),
        formula_metric_value=ev_metric,
    )


def _log_multiples_only_tie_out(
    *,
    logger: LoggerLike | None,
    enterprise_value_mid: Decimal,
    rebuilt_mid: Decimal,
    multiples_ev: Decimal,
    applied_multiple: Decimal,
    ev_metric: Decimal,
    net_debt_bridge: Decimal,
) -> None:
    if not logger:
        return
    logger.info(
        "Multiples-only EV tie-out: rebuilt EV from displayed multiple x metric",
        extra={
            "prior_ev_mid": float(enterprise_value_mid),
            "rebuilt_ev_mid": float(rebuilt_mid),
            "leg_ev": float(multiples_ev),
            "applied_multiple": float(applied_multiple),
            "metric": float(ev_metric),
            "net_debt_bridge": float(net_debt_bridge),
        },
    )
