"""
DCF display reconciliation for report context assembly.

This module owns the report-layer accounting guard that reconciles displayed
DCF enterprise value, terminal value, hidden horizon tail, and sensitivity grid.
The public section builder should not carry this business math inline.
"""

import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from src.services.infrastructure.report_sections.dcf_context_support import (
    JsonMap,
    attr,
    sequence_or_empty,
    transform_2d_sensitivity_matrix,
    unwrap,
)
from src.utils.decimal_helpers import safe_float as _to_float

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DcfDisplayReconciliation:
    pv_fcf_clean_list: Sequence[object]
    enterprise_value: float
    equity_value: float
    terminal_value: float
    pv_terminal_value: float
    terminal_value_pct_of_total: float
    explicit_forecast_pct_of_total: float
    horizon_tail_pv: float
    horizon_years: int | None
    matrix_payload: JsonMap | None
    band_low: float | None
    band_high: float | None


@dataclass(frozen=True)
class _BaseDisplayValues:
    enterprise_value: float
    equity_value: float
    terminal_value: float
    pv_terminal_value: float
    terminal_value_pct_of_total: float
    explicit_forecast_pct_of_total: float


@dataclass(frozen=True)
class _HorizonInference:
    tail_pv: float
    years: int
    terminal_value_pct_of_total: float
    explicit_forecast_pct_of_total: float
    matrix_2d: JsonMap | None


@dataclass(frozen=True)
class _BrokenDisplayRebuild:
    values: _BaseDisplayValues
    matrix_2d: JsonMap | None


@dataclass(frozen=True)
class _GuardInputs:
    tv_d: Decimal
    cw_fcff: Decimal
    stored_ev: Decimal
    stored_pvt: Decimal


def reconcile_dcf_display(
    response: object,
    dcf: object,
    dcf_wacc_decimal: Decimal | None,
) -> DcfDisplayReconciliation:
    """Return display-safe DCF values and sensitivity metadata for the report page."""
    pv_fcf_clean_list = _pv_fcf_sequence(dcf)
    base = _base_display_values(dcf)
    matrix_2d: JsonMap | None = None
    horizon_tail_pv = 0.0
    horizon_years: int | None = None

    try:
        guard = _guard_inputs(dcf=dcf, pv_fcf_clean_list=pv_fcf_clean_list)
        if attr(dcf, "calculation_contract_version") == "dcf_calculation.v2":
            # The saved engine owns values and scenarios. A five-year preview
            # must not trigger a new model or synthetic forecast tail.
            full_pv = sequence_or_empty(attr(dcf, "pv_fcf_projections", None))
            if len(full_pv) > len(pv_fcf_clean_list):
                horizon_years = len(full_pv)
                horizon_tail_pv = float(
                    sum(
                        (Decimal(str(value)) for value in full_pv[len(pv_fcf_clean_list) :]),
                        Decimal("0"),
                    )
                )
        elif _guard_ready(guard=guard, dcf_wacc_decimal=dcf_wacc_decimal):
            base, matrix_2d, horizon_tail_pv, horizon_years = _apply_reconciliation_guard(
                response=response,
                dcf=dcf,
                dcf_wacc_decimal=dcf_wacc_decimal,
                pv_fcf_clean_list=pv_fcf_clean_list,
                guard=guard,
                base=base,
            )
    except (ValueError, TypeError, ZeroDivisionError, ArithmeticError):
        pass

    matrix_payload = transform_2d_sensitivity_matrix(
        matrix_2d if matrix_2d is not None else unwrap(attr(dcf, "sensitivity_matrix_2d", None))
    )
    band_low, band_high = _derive_matrix_band(matrix_payload)
    return DcfDisplayReconciliation(
        pv_fcf_clean_list=pv_fcf_clean_list,
        enterprise_value=base.enterprise_value,
        equity_value=base.equity_value,
        terminal_value=base.terminal_value,
        pv_terminal_value=base.pv_terminal_value,
        terminal_value_pct_of_total=base.terminal_value_pct_of_total,
        explicit_forecast_pct_of_total=base.explicit_forecast_pct_of_total,
        horizon_tail_pv=horizon_tail_pv,
        horizon_years=horizon_years,
        matrix_payload=matrix_payload,
        band_low=band_low,
        band_high=band_high,
    )


def _pv_fcf_sequence(dcf: object) -> Sequence[object]:
    return sequence_or_empty(
        attr(dcf, "pv_fcf_projections_5y", None) or attr(dcf, "pv_fcf_projections", []) or []
    )


def _base_display_values(dcf: object) -> _BaseDisplayValues:
    return _BaseDisplayValues(
        enterprise_value=_to_float(attr(dcf, "enterprise_value", 0)),
        equity_value=_to_float(attr(dcf, "equity_value", 0)),
        terminal_value=_to_float(attr(dcf, "terminal_value", 0)),
        pv_terminal_value=_to_float(attr(dcf, "pv_terminal_value", 0)),
        terminal_value_pct_of_total=_to_float(attr(dcf, "terminal_value_pct_of_total", 0)),
        explicit_forecast_pct_of_total=_to_float(attr(dcf, "explicit_forecast_pct_of_total", 0)),
    )


def _guard_inputs(*, dcf: object, pv_fcf_clean_list: Sequence[object]) -> _GuardInputs:
    return _GuardInputs(
        tv_d=Decimal(str(attr(dcf, "terminal_value", 0) or 0)),
        cw_fcff=sum((Decimal(str(x)) for x in pv_fcf_clean_list), Decimal("0")),
        stored_ev=Decimal(str(attr(dcf, "enterprise_value", 0) or 0)),
        stored_pvt=Decimal(str(attr(dcf, "pv_terminal_value", 0) or 0)),
    )


def _guard_ready(*, guard: _GuardInputs, dcf_wacc_decimal: Decimal | None) -> bool:
    return bool(dcf_wacc_decimal and dcf_wacc_decimal > 0 and guard.tv_d > 0 and guard.cw_fcff > 0)


def _apply_reconciliation_guard(
    *,
    response: object,
    dcf: object,
    dcf_wacc_decimal: Decimal | None,
    pv_fcf_clean_list: Sequence[object],
    guard: _GuardInputs,
    base: _BaseDisplayValues,
) -> tuple[_BaseDisplayValues, JsonMap | None, float, int | None]:
    if dcf_wacc_decimal is None:
        return base, None, 0.0, None
    reconciles = _stored_dcf_reconciles(
        stored_ev=guard.stored_ev,
        cw_fcff=guard.cw_fcff,
        stored_pvt=guard.stored_pvt,
    )
    horizon = _infer_hidden_horizon(
        dcf=dcf,
        dcf_wacc_decimal=dcf_wacc_decimal,
        pv_fcf_clean_list=pv_fcf_clean_list,
        tv_d=guard.tv_d,
        cw_fcff=guard.cw_fcff,
        stored_ev=guard.stored_ev,
        stored_pvt=guard.stored_pvt,
        reconciles=reconciles,
    )
    if horizon is not None:
        return (
            _base_with_horizon_pct(base, horizon),
            horizon.matrix_2d,
            horizon.tail_pv,
            horizon.years,
        )
    if reconciles:
        return base, None, 0.0, None
    rebuild = _rebuild_broken_display(
        response=response,
        dcf=dcf,
        dcf_wacc_decimal=dcf_wacc_decimal,
        pv_fcf_clean_list=pv_fcf_clean_list,
        tv_d=guard.tv_d,
        cw_fcff=guard.cw_fcff,
        stored_ev=guard.stored_ev,
        stored_pvt=guard.stored_pvt,
    )
    return (rebuild.values, rebuild.matrix_2d, 0.0, None) if rebuild else (base, None, 0.0, None)


def _base_with_horizon_pct(
    base: _BaseDisplayValues,
    horizon: _HorizonInference,
) -> _BaseDisplayValues:
    return _BaseDisplayValues(
        enterprise_value=base.enterprise_value,
        equity_value=base.equity_value,
        terminal_value=base.terminal_value,
        pv_terminal_value=base.pv_terminal_value,
        terminal_value_pct_of_total=horizon.terminal_value_pct_of_total,
        explicit_forecast_pct_of_total=horizon.explicit_forecast_pct_of_total,
    )


def _stored_dcf_reconciles(
    *,
    stored_ev: Decimal,
    cw_fcff: Decimal,
    stored_pvt: Decimal,
) -> bool:
    return abs(stored_ev - (cw_fcff + stored_pvt)) <= max(
        Decimal("1"),
        stored_ev * Decimal("0.005"),
    )


def _infer_hidden_horizon(
    *,
    dcf: object,
    dcf_wacc_decimal: Decimal,
    pv_fcf_clean_list: Sequence[object],
    tv_d: Decimal,
    cw_fcff: Decimal,
    stored_ev: Decimal,
    stored_pvt: Decimal,
    reconciles: bool,
) -> _HorizonInference | None:
    if reconciles or stored_pvt <= 0 or tv_d <= stored_pvt:
        return None

    displayed_years = len(pv_fcf_clean_list)
    mid_year_flag = bool(attr(dcf, "mid_year_discounting", True))
    periods = math.log(float(tv_d / stored_pvt)) / math.log(1.0 + float(dcf_wacc_decimal))
    n_implied = periods + (0.5 if mid_year_flag else 0.0)
    n_int = int(round(n_implied))
    tail_d = stored_ev - stored_pvt - cw_fcff
    if abs(n_implied - n_int) >= 0.02 or n_int <= displayed_years or tail_d <= 0:
        return None

    tail_pv = float(
        stored_ev.quantize(Decimal("0.01"))
        - stored_pvt.quantize(Decimal("0.01"))
        - cw_fcff.quantize(Decimal("0.01"))
    )
    terminal_pct = _to_float(attr(dcf, "terminal_value_pct_of_total", 0))
    explicit_pct = _to_float(attr(dcf, "explicit_forecast_pct_of_total", 0))
    if stored_ev > 0:
        terminal_pct = float((stored_pvt / stored_ev * Decimal("100")).quantize(Decimal("0.01")))
        explicit_pct = round(100.0 - terminal_pct, 2)

    logger.info(
        "DCF horizon inference: engine EV spans %s explicit years, "
        "%s displayed; tail PV(years %s-%s)=%.2f keeps stored EV %.2f.",
        n_int,
        displayed_years,
        displayed_years + 1,
        n_int,
        tail_pv,
        float(stored_ev),
    )
    matrix_2d = _build_hidden_horizon_matrix(
        dcf=dcf,
        dcf_wacc_decimal=dcf_wacc_decimal,
        tv_d=tv_d,
        tail_d=tail_d,
        stored_ev=stored_ev,
        displayed_years=displayed_years,
        horizon_years=n_int,
        mid_year_flag=mid_year_flag,
    )
    return _HorizonInference(
        tail_pv=tail_pv,
        years=n_int,
        terminal_value_pct_of_total=terminal_pct,
        explicit_forecast_pct_of_total=explicit_pct,
        matrix_2d=matrix_2d,
    )


def _build_hidden_horizon_matrix(
    *,
    dcf: object,
    dcf_wacc_decimal: Decimal,
    tv_d: Decimal,
    tail_d: Decimal,
    stored_ev: Decimal,
    displayed_years: int,
    horizon_years: int,
    mid_year_flag: bool,
) -> JsonMap | None:
    g_tv = Decimal(str(attr(dcf, "terminal_growth_rate", 0) or 0))
    fcff_h = [float(Decimal(str(x))) for x in _fcf_sequence(dcf)]
    w0 = float(dcf_wacc_decimal)
    g0 = float(g_tv)
    delta = 0.5 if mid_year_flag else 0.0
    if not (
        len(fcff_h) == displayed_years
        and fcff_h
        and fcff_h[-1] > 0
        and w0 > g0
        and horizon_years > displayed_years
    ):
        return None

    fn = float(tv_d) * (w0 - g0) / (1.0 + g0)
    steps = horizon_years - displayed_years
    ratio_g = (fn / fcff_h[-1]) ** (1.0 / steps)
    tail_fcff = [fcff_h[-1] * (ratio_g**k) for k in range(1, steps + 1)]
    pv_tail_raw = sum(
        cf / ((1.0 + w0) ** ((displayed_years + i + 1) - delta)) for i, cf in enumerate(tail_fcff)
    )
    scale = float(tail_d) / pv_tail_raw if pv_tail_raw > 0 else 0.0
    if not 0.5 <= scale <= 2.0:
        logger.warning(
            "DCF horizon matrix rebuild skipped: tail scale %.3f out of sanity bounds; "
            "engine matrix left as-is.",
            scale,
        )
        return None

    full_fcff = fcff_h + [cf * scale for cf in tail_fcff]
    waccs = [w0 - 0.01, w0, w0 + 0.01]
    growths = [g0 - 0.005, g0, g0 + 0.005]
    matrix: list[list[float]] = []
    for wacc in waccs:
        row: list[float] = []
        for growth in growths:
            row.append(
                _hidden_horizon_ev_cell(
                    full_fcff=full_fcff,
                    terminal_fcf=fn,
                    wacc=wacc,
                    growth=growth,
                    horizon_years=horizon_years,
                    delta=delta,
                )
            )
        matrix.append(row)
    if abs(matrix[1][1] - float(stored_ev)) <= 2.0:
        matrix[1][1] = float(stored_ev.quantize(Decimal("0.01")))
    else:
        logger.warning(
            "DCF horizon matrix base cell %.2f drifted from stored EV %.2f beyond snap tolerance.",
            matrix[1][1],
            float(stored_ev),
        )
    return {
        "wacc_values": list(waccs),
        "growth_values": list(growths),
        "secondary_values": list(growths),
        "ev_matrix": matrix,
        "secondary_axis_key": "terminal_growth",
    }


def _hidden_horizon_ev_cell(
    *,
    full_fcff: Sequence[float],
    terminal_fcf: float,
    wacc: float,
    growth: float,
    horizon_years: int,
    delta: float,
) -> float:
    if wacc <= growth:
        return 0.0
    pv_sum = sum(cf / ((1.0 + wacc) ** ((i + 1) - delta)) for i, cf in enumerate(full_fcff))
    tv_w = terminal_fcf * (1.0 + growth) / (wacc - growth)
    pv_tv_w = tv_w / ((1.0 + wacc) ** (horizon_years - delta))
    return round(pv_sum + pv_tv_w, 2)


def _rebuild_broken_display(
    *,
    response: object,
    dcf: object,
    dcf_wacc_decimal: Decimal,
    pv_fcf_clean_list: Sequence[object],
    tv_d: Decimal,
    cw_fcff: Decimal,
    stored_ev: Decimal,
    stored_pvt: Decimal,
) -> _BrokenDisplayRebuild | None:
    projection_years = attr(dcf, "projection_years", None) or len(pv_fcf_clean_list) or 5
    disc_period = Decimal(str(projection_years)) - Decimal("0.5")
    disc_factor = Decimal(str(float(Decimal("1") + dcf_wacc_decimal) ** float(disc_period)))
    fcf_raw = _fcf_sequence(dcf)
    g_tv = Decimal(str(attr(dcf, "terminal_growth_rate", 0) or 0))
    fcf_n = Decimal(str(fcf_raw[-1])) if fcf_raw else Decimal("0")
    tv_gordon = (
        (fcf_n * (Decimal("1") + g_tv) / (dcf_wacc_decimal - g_tv))
        if (dcf_wacc_decimal > g_tv and fcf_n > 0)
        else tv_d
    ).quantize(Decimal("0.01"))
    pv_terminal_clean = (tv_gordon / disc_factor).quantize(Decimal("0.01"))
    ev_clean = (cw_fcff + pv_terminal_clean).quantize(Decimal("0.01"))
    net_debt = _net_debt_from_multiples_or_dcf(response, dcf, stored_ev)
    eq_clean = (ev_clean - net_debt).quantize(Decimal("0.01"))
    terminal_pct = (
        float((pv_terminal_clean / ev_clean * Decimal("100")).quantize(Decimal("0.01")))
        if ev_clean > 0
        else 0.0
    )
    values = _BaseDisplayValues(
        enterprise_value=float(ev_clean),
        equity_value=float(eq_clean),
        terminal_value=float(tv_gordon),
        pv_terminal_value=float(pv_terminal_clean),
        terminal_value_pct_of_total=terminal_pct,
        explicit_forecast_pct_of_total=round(100.0 - terminal_pct, 2),
    )
    logger.info(
        "DCF tie-out guard: recomputed EV from PV(FCFF)+PV(terminal). "
        "stored_ev=%.0f rebuilt_ev=%.0f pv_terminal=%.0f->%.0f net_debt=%.0f",
        float(stored_ev),
        values.enterprise_value,
        float(stored_pvt),
        values.pv_terminal_value,
        float(net_debt),
    )
    return _BrokenDisplayRebuild(
        values=values,
        matrix_2d=_build_reconciled_matrix(
            dcf=dcf,
            dcf_wacc_decimal=dcf_wacc_decimal,
            terminal_growth=g_tv,
        ),
    )


def _net_debt_from_multiples_or_dcf(
    response: object,
    dcf: object,
    stored_ev: Decimal,
) -> Decimal:
    mv = getattr(response, "multiples_valuation", None)
    mv_ev = _decimal_member(mv, "enterprise_value") if mv is not None else Decimal("0")
    mv_eq = _decimal_member(mv, "equity_value") if mv is not None else Decimal("0")
    if mv_ev > 0 and mv_eq > 0:
        return mv_ev - mv_eq
    return stored_ev - Decimal(str(attr(dcf, "equity_value", 0) or 0))


def _decimal_member(obj: object, name: str) -> Decimal:
    if isinstance(obj, dict):
        value = obj.get(name, 0)
    else:
        value = getattr(obj, name, 0)
    return Decimal(str(value or 0))


def _build_reconciled_matrix(
    *,
    dcf: object,
    dcf_wacc_decimal: Decimal,
    terminal_growth: Decimal,
) -> JsonMap | None:
    fcff_d = [Decimal(str(x)) for x in _fcf_sequence(dcf)]
    if not fcff_d:
        return None

    nf = len(fcff_d)
    base_tfcff = fcff_d[-1]
    waccs = [
        dcf_wacc_decimal - Decimal("0.01"),
        dcf_wacc_decimal,
        dcf_wacc_decimal + Decimal("0.01"),
    ]
    growths = [
        terminal_growth - Decimal("0.005"),
        terminal_growth,
        terminal_growth + Decimal("0.005"),
    ]
    matrix: list[list[float]] = []
    for wacc in waccs:
        row: list[float] = []
        for growth in growths:
            row.append(
                _reconciled_ev_cell(
                    fcff_d=fcff_d,
                    base_tfcff=base_tfcff,
                    wacc=wacc,
                    growth=growth,
                    periods=nf,
                )
            )
        matrix.append(row)
    return {
        "wacc_values": [float(w) for w in waccs],
        "growth_values": [float(g) for g in growths],
        "secondary_values": [float(g) for g in growths],
        "ev_matrix": matrix,
        "secondary_axis_key": "terminal_growth",
    }


def _reconciled_ev_cell(
    *,
    fcff_d: Sequence[Decimal],
    base_tfcff: Decimal,
    wacc: Decimal,
    growth: Decimal,
    periods: int,
) -> float:
    if wacc <= growth:
        return 0.0
    pvf_w = sum(
        (
            fcff_d[i]
            / Decimal(
                str(float(Decimal("1") + wacc) ** float(Decimal(str(i + 1)) - Decimal("0.5")))
            )
            for i in range(periods)
        ),
        Decimal("0"),
    )
    tv_w = base_tfcff * (Decimal("1") + growth) / (wacc - growth)
    pvt_w = tv_w / Decimal(
        str(float(Decimal("1") + wacc) ** float(Decimal(str(periods)) - Decimal("0.5")))
    )
    return float((pvf_w + pvt_w).quantize(Decimal("1")))


def _fcf_sequence(dcf: object) -> Sequence[object]:
    return sequence_or_empty(
        attr(dcf, "fcf_projections_5y", None) or attr(dcf, "fcf_projections", []) or []
    )


def _derive_matrix_band(matrix_payload: JsonMap | None) -> tuple[float | None, float | None]:
    if not matrix_payload or not isinstance(matrix_payload.get("matrix"), dict):
        return None, None
    cells = [
        float(value)
        for row in matrix_payload["matrix"].values()
        if isinstance(row, dict)
        for value in row.values()
        if isinstance(value, (int, float)) and float(value) > 0
    ]
    if len(cells) >= 2 and min(cells) < max(cells):
        return min(cells), max(cells)
    return None, None
