"""Enterprise-value range resolution for report aggregation."""

from decimal import Decimal, localcontext
from typing import Protocol, TypeAlias, cast

from src.services.reports.engine_warning_context import append_engine_warning
from src.services.reports.protocol_adapter import _attr
from src.services.reports.report_value_admission import (
    admitted_band,
    admitted_point_or_band,
    report_decimal,
)
from src.utils.decimal_helpers import EV_BAND_SOURCE_ENGINE_EQUITY

ReportMap: TypeAlias = dict[str, object]
EVBand: TypeAlias = tuple[Decimal, Decimal, Decimal]


class LoggerLike(Protocol):
    def info(self, msg: str, *args: object, **kwargs: object) -> object: ...


def deterministic_ev_range(ev_mid: Decimal) -> EVBand:
    """Legacy tuple adapter for a point; no evidence supports an invented spread."""
    point = report_decimal(ev_mid, "enterprise_value")
    return point, point, point


def _dcf_enterprise_value_range(
    response: object,
    step_data: ReportMap,
) -> EVBand | None:
    dcf_valuation = getattr(response, "dcf_valuation", None)
    if not dcf_valuation:
        return None

    dcf_ev = report_decimal(_attr(dcf_valuation, "enterprise_value", None), "enterprise_value")
    low = _attr(dcf_valuation, "enterprise_value_low", None)
    high = _attr(dcf_valuation, "enterprise_value_high", None)
    if low is not None or high is not None:
        step_data["_ev_band_source"] = "dcf_enterprise_value_band"
        return admitted_band(low, dcf_ev, high)

    equity_low = _attr(dcf_valuation, "equity_value_low", None)
    equity_high = _attr(dcf_valuation, "equity_value_high", None)
    if equity_low is not None or equity_high is not None:
        debt = report_decimal(step_data.get("net_debt"), "net_debt")
        with localcontext() as ctx:
            ctx.prec = 100
            band = admitted_band(
                report_decimal(equity_low, "equity_value_low") + debt,
                dcf_ev,
                report_decimal(equity_high, "equity_value_high") + debt,
            )
        step_data["_ev_band_source"] = "dcf_equity_plus_net_debt"
        return band
    step_data["_ev_band_source"] = "dcf_point_only"
    return deterministic_ev_range(dcf_ev)


def _engine_equity_ev_band(
    *,
    step_data: ReportMap,
    equity_value_low: Decimal,
    equity_value_mid: Decimal,
    equity_value_high: Decimal,
) -> EVBand:
    net_debt = report_decimal(step_data.get("net_debt"), "net_debt")
    equity_band = admitted_band(equity_value_low, equity_value_mid, equity_value_high)
    with localcontext() as ctx:
        ctx.prec = 100
        return admitted_band(*(value + net_debt for value in equity_band))


def _record_engine_equity_source(
    *,
    step_data: ReportMap,
    logger: LoggerLike | None,
    pipeline_band: EVBand,
    engine_band: EVBand,
    chosen_source: str,
) -> None:
    step_data["_ev_band_source"] = chosen_source
    if chosen_source != EV_BAND_SOURCE_ENGINE_EQUITY:
        return

    append_engine_warning(
        step_data,
        key="ev_band_sourced_from_engine_equity",
        severity="info",
        message=(
            "Displayed EV band sourced from the engine's equity output because "
            "the saved equity bridge and multiple pipeline have the same point value. "
            "This is the saved valuation range, not a statistically calibrated interval."
        ),
        message_nl=(
            "Getoonde EV-bandbreedte komt uit de equity-output van de motor "
            "omdat de opgeslagen aandelenwaardebrug en multiple-pijplijn dezelfde puntwaarde hebben. "
            "Dit is het opgeslagen waarderingsbereik, geen statistisch gekalibreerd interval."
        ),
    )
    if logger:
        logger.info(
            "ev_band_sourced_from_engine_equity",
            extra={
                "pipeline_low": str(pipeline_band[0]),
                "pipeline_mid": str(pipeline_band[1]),
                "pipeline_high": str(pipeline_band[2]),
                "engine_ev_low": str(engine_band[0]),
                "engine_ev_mid": str(engine_band[1]),
                "engine_ev_high": str(engine_band[2]),
            },
        )


def _pipeline_enterprise_value_range(
    *,
    pipeline: ReportMap,
    step_data: ReportMap,
    equity_value_low: Decimal,
    equity_value_mid: Decimal,
    equity_value_high: Decimal,
    logger: LoggerLike | None,
) -> EVBand | None:
    raw_metric = pipeline.get("metric_value")
    final_mid_raw = (
        pipeline.get("final_multiple_mid")
        if pipeline.get("final_multiple_mid") is not None
        else pipeline.get("final_multiple")
    )
    if raw_metric is None or final_mid_raw is None:
        return None
    metric_value = report_decimal(raw_metric, "metric_value")
    final_mid = report_decimal(final_mid_raw, "final_multiple_mid")
    if metric_value <= Decimal("0") or final_mid <= Decimal("0"):
        return None

    low = pipeline.get("final_multiple_low")
    high = pipeline.get("final_multiple_high")
    point_only = low is None and high is None
    multiples = admitted_band(
        final_mid if point_only else low, final_mid, final_mid if point_only else high
    )
    if multiples[0] < 0:
        raise ValueError("Multiple bounds cannot be negative")
    with localcontext() as ctx:
        ctx.prec = 100
        pipeline_band = admitted_band(*(metric_value * value for value in multiples))
    step_data["_ev_band_source"] = (
        "multiple_pipeline_point_only" if point_only else "multiple_pipeline"
    )
    # Unknown net debt cannot support a translated equity band. Display width
    # does not determine which financial evidence is authoritative.
    if step_data.get("net_debt") is not None:
        engine_band = _engine_equity_ev_band(
            step_data=step_data,
            equity_value_low=equity_value_low,
            equity_value_mid=equity_value_mid,
            equity_value_high=equity_value_high,
        )
        if engine_band[1] == pipeline_band[1]:
            _record_engine_equity_source(
                step_data=step_data,
                logger=logger,
                pipeline_band=pipeline_band,
                engine_band=engine_band,
                chosen_source=EV_BAND_SOURCE_ENGINE_EQUITY,
            )
            return engine_band
    return pipeline_band


def _equity_plus_net_debt_range(
    *,
    step_data: ReportMap,
    equity_value_low: Decimal,
    equity_value_mid: Decimal,
    equity_value_high: Decimal,
) -> EVBand:
    step_data["_ev_band_source"] = "equity_plus_net_debt_fallback"
    return _engine_equity_ev_band(
        step_data=step_data,
        equity_value_low=equity_value_low,
        equity_value_mid=equity_value_mid,
        equity_value_high=equity_value_high,
    )


def extract_enterprise_value_range(
    *,
    response: object,
    step_data: ReportMap,
    equity_value_low: Decimal | None,
    equity_value_mid: Decimal | None,
    equity_value_high: Decimal | None,
    is_hybrid: bool,
    is_dcf_only: bool,
    is_asset_anchored: bool,
    logger: LoggerLike | None = None,
) -> EVBand:
    """Resolve EV consistently for report contexts."""
    if equity_value_mid is None:
        if equity_value_low is not None or equity_value_high is not None:
            raise ValueError("An incomplete equity band cannot support a report")
        band = admitted_point_or_band(
            getattr(response, "enterprise_value_low", None),
            getattr(response, "enterprise_value_mid", None),
            getattr(response, "enterprise_value_high", None),
        )
        step_data["_ev_band_source"] = "saved_enterprise_value_band"
        return band
    if equity_value_low is None or equity_value_high is None:
        raise ValueError("An incomplete equity band cannot support a report")
    if is_dcf_only:
        dcf_range = _dcf_enterprise_value_range(response, step_data)
        if dcf_range is not None:
            return dcf_range

    pipeline = step_data.get("multiple_pipeline", {}) if step_data else {}
    if not is_hybrid and not is_dcf_only and not is_asset_anchored and isinstance(pipeline, dict):
        pipeline_range = _pipeline_enterprise_value_range(
            pipeline=cast(ReportMap, pipeline),
            step_data=step_data,
            equity_value_low=equity_value_low,
            equity_value_mid=equity_value_mid,
            equity_value_high=equity_value_high,
            logger=logger,
        )
        if pipeline_range is not None:
            return pipeline_range

    return _equity_plus_net_debt_range(
        step_data=step_data,
        equity_value_low=equity_value_low,
        equity_value_mid=equity_value_mid,
        equity_value_high=equity_value_high,
    )
