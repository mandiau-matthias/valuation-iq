"""Read-only legacy headline projection; valuation arithmetic belongs to the engine.

Stored DCF horizons, blends, bridges and method bands are never reconstructed
by a report. Invalid financial contracts fail admission; historical artifacts
are untouched. Compatibility fields retain their original interface.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, TypeAlias

from src.services.reports.report_value_admission import admitted_band, admitted_optional_equity_band

ReportMap: TypeAlias = dict[str, object]


class LoggerLike(Protocol):
    def info(self, msg: str, *args: object, **kwargs: object) -> object: ...


@dataclass(frozen=True)
class ReportHeadlineValuationAlignment:
    enterprise_value_low: Decimal
    enterprise_value_mid: Decimal
    enterprise_value_high: Decimal
    equity_value_low: Decimal | None
    equity_value: Decimal | None
    equity_value_high: Decimal | None
    formula_metric_value: Decimal
    multiple_low: Decimal
    multiple_high: Decimal
    display_multiple: Decimal
    pre_synthesis_multiple: Decimal
    applied_multiple_rail: str
    ev_metric: Decimal
    is_multiples_only_ev: bool
    engine_synthesis_equity_anchored: bool


def _rebuilt_dcf_ev_if_needed(dcf_valuation: object, dcf_ev: Decimal) -> Decimal:
    """Legacy entry point: rendering never discounts or replaces a saved DCF."""
    return dcf_ev


def align_report_headline_valuation(
    *,
    response: object,
    step_data: ReportMap,
    multiple_context: Mapping[str, object],
    revenue_value: Decimal,
    sustainable_ebitda: Decimal,
    enterprise_value_low: Decimal,
    enterprise_value_mid: Decimal,
    enterprise_value_high: Decimal,
    equity_value_low: Decimal | None,
    equity_value: Decimal | None,
    equity_value_high: Decimal | None,
    formula_metric_value: Decimal,
    applied_multiple: Decimal,
    multiple_low: Decimal,
    multiple_high: Decimal,
    is_dcf_only: bool,
    is_asset_anchored: bool,
    has_weighted_synthesis_payload: bool,
    is_hybrid_method: bool,
    has_balance_data: bool,
    dcf_ineligible_forced_blend: bool = False,
    logger: LoggerLike | None = None,
) -> ReportHeadlineValuationAlignment:
    """Retain the admitted source amounts and priced basis without tie-out edits."""
    ev_low, ev_mid, ev_high = admitted_band(
        enterprise_value_low, enterprise_value_mid, enterprise_value_high
    )
    eq_low, eq_mid, eq_high = admitted_optional_equity_band(
        equity_value_low, equity_value, equity_value_high
    )
    metric_type = str(multiple_context["metric_type"]).upper()
    return ReportHeadlineValuationAlignment(
        enterprise_value_low=ev_low,
        enterprise_value_mid=ev_mid,
        enterprise_value_high=ev_high,
        equity_value_low=eq_low,
        equity_value=eq_mid,
        equity_value_high=eq_high,
        formula_metric_value=formula_metric_value,
        multiple_low=multiple_low,
        multiple_high=multiple_high,
        display_multiple=applied_multiple,
        pre_synthesis_multiple=applied_multiple,
        applied_multiple_rail="saved_method",
        ev_metric=revenue_value if metric_type == "REVENUE" else sustainable_ebitda,
        is_multiples_only_ev=not (
            is_dcf_only or is_asset_anchored or has_weighted_synthesis_payload or is_hybrid_method
        ),
        engine_synthesis_equity_anchored=False,
    )
