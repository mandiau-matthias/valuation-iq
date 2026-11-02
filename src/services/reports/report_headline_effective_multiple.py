"""Effective multiple display derivation for report headline valuation."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol, TypeAlias

from src.utils.decimal_helpers import safe_decimal_or_zero

ReportMap: TypeAlias = dict[str, object]


class LoggerLike(Protocol):
    def info(self, msg: str, *args: object, **kwargs: object) -> object: ...


def _decimal(value: object) -> Decimal:
    return safe_decimal_or_zero(value)


def derive_effective_multiple_display(
    *,
    step_data: ReportMap,
    logger: LoggerLike | None,
    enterprise_value_low: Decimal,
    enterprise_value_mid: Decimal,
    enterprise_value_high: Decimal,
    equity_value: Decimal,
    formula_metric_value: Decimal,
    ev_metric: Decimal,
    applied_multiple: Decimal,
    multiple_low: Decimal,
    multiple_high: Decimal,
    is_multiples_only_ev: bool,
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal]:
    bridge_effective = step_data.get("effective_multiple")
    derived_effective = _effective_multiple_to_derive(
        step_data=step_data,
        bridge_effective=bridge_effective,
        enterprise_value_mid=enterprise_value_mid,
        ev_metric=ev_metric,
        applied_multiple=applied_multiple,
        is_multiples_only_ev=is_multiples_only_ev,
    )
    if derived_effective is not None:
        bridge_effective = derived_effective
        step_data["effective_multiple"] = derived_effective
        pre_derivation_enterprise_value_mid = enterprise_value_mid
        (
            enterprise_value_low,
            enterprise_value_mid,
            enterprise_value_high,
            equity_value,
        ) = _apply_effective_multiple_rounding_adjustment(
            enterprise_value_low=enterprise_value_low,
            enterprise_value_mid=enterprise_value_mid,
            enterprise_value_high=enterprise_value_high,
            equity_value=equity_value,
            ev_metric=ev_metric,
            derived_effective=derived_effective,
        )
        formula_metric_value = ev_metric
        multiple_low, multiple_high = _rescale_effective_multiple_band(
            multiple_low=multiple_low,
            multiple_high=multiple_high,
            derived_effective=derived_effective,
            applied_multiple=applied_multiple,
        )
        _log_effective_multiple_derivation(
            logger=logger,
            applied_multiple=applied_multiple,
            derived_effective=derived_effective,
            enterprise_value_mid=pre_derivation_enterprise_value_mid,
            ev_metric=ev_metric,
        )

    display_multiple = (
        _decimal(bridge_effective) if bridge_effective is not None else applied_multiple
    )
    return (
        enterprise_value_low,
        enterprise_value_mid,
        enterprise_value_high,
        equity_value,
        formula_metric_value,
        multiple_low,
        multiple_high,
        display_multiple,
    )


def _ev_discount_applied(step_data: ReportMap) -> bool:
    threshold = Decimal("0.0001")
    return any(
        (
            abs(_decimal(step_data.get("total_discount_percentage") or 0)) > threshold,
            abs(_decimal(step_data.get("size_discount_percentage") or 0)) > threshold,
            bool(step_data.get("multiple_pipeline")),
        )
    )


def _effective_multiple_to_derive(
    *,
    step_data: ReportMap,
    bridge_effective: object,
    enterprise_value_mid: Decimal,
    ev_metric: Decimal,
    applied_multiple: Decimal,
    is_multiples_only_ev: bool,
) -> Decimal | None:
    if not (
        bridge_effective is None
        and is_multiples_only_ev
        and _ev_discount_applied(step_data)
        and applied_multiple > 0
        and ev_metric > 0
        and enterprise_value_mid > 0
    ):
        return None

    derived_effective = (enterprise_value_mid / ev_metric).quantize(Decimal("0.0001"))
    if abs(derived_effective - applied_multiple) <= Decimal("0.01"):
        return None
    return derived_effective


def _apply_effective_multiple_rounding_adjustment(
    *,
    enterprise_value_low: Decimal,
    enterprise_value_mid: Decimal,
    enterprise_value_high: Decimal,
    equity_value: Decimal,
    ev_metric: Decimal,
    derived_effective: Decimal,
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    effective_ev_anchored = (ev_metric * derived_effective).quantize(Decimal("0.01"))
    effective_delta = effective_ev_anchored - enterprise_value_mid
    if effective_delta == 0 or abs(effective_delta) > Decimal("250"):
        return enterprise_value_low, enterprise_value_mid, enterprise_value_high, equity_value

    adjusted_low = (
        (enterprise_value_low + effective_delta).quantize(Decimal("0.01"))
        if enterprise_value_low > 0
        else enterprise_value_low
    )
    adjusted_high = (
        (enterprise_value_high + effective_delta).quantize(Decimal("0.01"))
        if enterprise_value_high > 0
        else enterprise_value_high
    )
    adjusted_equity = (equity_value + effective_delta).quantize(Decimal("0.01"))
    return adjusted_low, effective_ev_anchored, adjusted_high, adjusted_equity


def _rescale_effective_multiple_band(
    *,
    multiple_low: Decimal,
    multiple_high: Decimal,
    derived_effective: Decimal,
    applied_multiple: Decimal,
) -> tuple[Decimal, Decimal]:
    effective_band_ratio = derived_effective / applied_multiple
    return (
        (
            (multiple_low * effective_band_ratio).quantize(Decimal("0.0001"))
            if multiple_low > 0
            else multiple_low
        ),
        (
            (multiple_high * effective_band_ratio).quantize(Decimal("0.0001"))
            if multiple_high > 0
            else multiple_high
        ),
    )


def _log_effective_multiple_derivation(
    *,
    logger: LoggerLike | None,
    applied_multiple: Decimal,
    derived_effective: Decimal,
    enterprise_value_mid: Decimal,
    ev_metric: Decimal,
) -> None:
    if not logger:
        return
    logger.info(
        "effective_multiple_derived_from_ev",
        extra={
            "applied_multiple_gross": float(applied_multiple),
            "effective_multiple": float(derived_effective),
            "enterprise_value_mid": float(enterprise_value_mid),
            "metric": float(ev_metric),
            "note": (
                "multiple_pipeline payload absent; derived effective "
                "multiple from post-bridge EV so metric x multiple = EV foots"
            ),
        },
    )
