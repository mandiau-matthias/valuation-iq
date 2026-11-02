"""Final valuation band invariants for report aggregation."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, TypeAlias

from src.services.reports.report_value_admission import admitted_band, admitted_optional_equity_band

ReportMap: TypeAlias = dict[str, object]


class LoggerLike(Protocol):
    def info(self, msg: str, *args: object, **kwargs: object) -> object: ...

    def warning(self, msg: str, *args: object, **kwargs: object) -> object: ...


@dataclass(frozen=True)
class ValuationBandContext:
    enterprise_value_low: Decimal
    enterprise_value_mid: Decimal
    enterprise_value_high: Decimal
    equity_value_low: Decimal | None
    equity_value: Decimal | None
    equity_value_high: Decimal | None
    ev_band_is_meaningful: bool
    equity_band_is_meaningful: bool


def finalize_valuation_bands(
    *,
    response: object,
    step_data: ReportMap,
    enterprise_value_low: Decimal,
    enterprise_value_mid: Decimal,
    enterprise_value_high: Decimal,
    equity_value_low: Decimal | None,
    equity_value: Decimal | None,
    equity_value_high: Decimal | None,
    logger: LoggerLike | None = None,
) -> ValuationBandContext:
    """Validate saved bounds without rounding, reordering or widening them.

    Compact formatting belongs in the renderer. An interval remains evidence
    even if compact labels coincide; a point-only tuple has no interval.
    """
    enterprise_value_low, enterprise_value_mid, enterprise_value_high = admitted_band(
        enterprise_value_low, enterprise_value_mid, enterprise_value_high
    )
    equity_value_low, equity_value, equity_value_high = admitted_optional_equity_band(
        equity_value_low, equity_value, equity_value_high
    )
    ev_band_is_meaningful = enterprise_value_low < enterprise_value_high
    equity_band_is_meaningful = (
        equity_value_low is not None
        and equity_value_high is not None
        and equity_value_low < equity_value_high
    )

    return ValuationBandContext(
        enterprise_value_low=enterprise_value_low,
        enterprise_value_mid=enterprise_value_mid,
        enterprise_value_high=enterprise_value_high,
        equity_value_low=equity_value_low,
        equity_value=equity_value,
        equity_value_high=equity_value_high,
        ev_band_is_meaningful=ev_band_is_meaningful,
        equity_band_is_meaningful=equity_band_is_meaningful,
    )
