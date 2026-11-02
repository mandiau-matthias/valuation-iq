"""Percentile-band assembly for Step 2 selected multiples."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping, Optional


@dataclass(frozen=True)
class MultiplesPercentiles:
    ev_ebitda_p10: Optional[Decimal]
    ev_ebitda_p25: Optional[Decimal]
    ev_ebitda_p50: Optional[Decimal]
    ev_ebitda_p75: Optional[Decimal]
    ev_ebitda_p90: Optional[Decimal]
    ev_ebitda_percentile_source: str
    ev_revenue_p25: Optional[Decimal]
    ev_revenue_p50: Optional[Decimal]
    ev_revenue_p75: Optional[Decimal]
    ev_revenue_percentile_source: str


@dataclass(frozen=True)
class PercentileBand:
    p25: Optional[Decimal]
    p50: Optional[Decimal]
    p75: Optional[Decimal]
    source: str


def decimal_or_none(value: object) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _comparable_decimal(
    comparables_data: Mapping[str, object],
    key: str,
) -> Optional[Decimal]:
    return decimal_or_none(comparables_data.get(key))


def _synthetic_band(anchor: Optional[Decimal]) -> PercentileBand:
    return PercentileBand(
        p25=anchor * Decimal("0.8") if anchor else None,
        p50=anchor,
        p75=anchor * Decimal("1.2") if anchor else None,
        source="synthetic_20pct",
    )


def _market_or_synthetic_band(
    *,
    comparables_data: Mapping[str, object],
    prefix: str,
    fallback_mid: Optional[Decimal],
) -> PercentileBand:
    p50 = _comparable_decimal(comparables_data, f"{prefix}_p50")
    if comparables_data and p50 is not None:
        p25 = _comparable_decimal(comparables_data, f"{prefix}_p25")
        p75 = _comparable_decimal(comparables_data, f"{prefix}_p75")
        source = "market_derived" if p25 is not None and p75 is not None else "synthetic_20pct"
        return PercentileBand(p25=p25, p50=p50, p75=p75, source=source)
    return _synthetic_band(fallback_mid)


def _fill_positive_synthetic_gaps(
    band: PercentileBand,
    fallback_mid: Optional[Decimal],
) -> PercentileBand:
    if fallback_mid is None or fallback_mid <= 0:
        return band
    return PercentileBand(
        p25=band.p25 or fallback_mid * Decimal("0.8"),
        p50=band.p50 or fallback_mid,
        p75=band.p75 or fallback_mid * Decimal("1.2"),
        source=band.source,
    )


def _ebitda_tail_percentiles(
    *,
    comparables_data: Mapping[str, object],
    band: PercentileBand,
    fallback_mid: Optional[Decimal],
) -> tuple[Optional[Decimal], Optional[Decimal]]:
    p10 = _comparable_decimal(comparables_data, "ev_ebitda_p10")
    p90 = _comparable_decimal(comparables_data, "ev_ebitda_p90")
    if (
        fallback_mid is not None
        and fallback_mid > 0
        and band.p25 is not None
        and band.p75 is not None
    ):
        p10 = p10 or band.p25 * Decimal("0.9")
        p90 = p90 or band.p75 * Decimal("1.1")
    return p10, p90


def build_multiples_percentiles(
    *,
    ev_ebitda_ratio: Optional[Decimal],
    revenue_multiple: Optional[Decimal],
    comparables_data: Optional[Mapping[str, object]],
) -> MultiplesPercentiles:
    """Build market-derived or synthetic 20% percentile bands for selected multiples."""
    data = comparables_data or {}
    ebitda_band = _market_or_synthetic_band(
        comparables_data=data,
        prefix="ev_ebitda",
        fallback_mid=ev_ebitda_ratio,
    )
    ebitda_band = _fill_positive_synthetic_gaps(ebitda_band, ev_ebitda_ratio)
    ev_ebitda_p10, ev_ebitda_p90 = _ebitda_tail_percentiles(
        comparables_data=data,
        band=ebitda_band,
        fallback_mid=ev_ebitda_ratio,
    )

    revenue_band = _market_or_synthetic_band(
        comparables_data=data,
        prefix="ev_revenue",
        fallback_mid=revenue_multiple,
    )
    revenue_band = _fill_positive_synthetic_gaps(revenue_band, revenue_multiple)

    return MultiplesPercentiles(
        ev_ebitda_p10=ev_ebitda_p10,
        ev_ebitda_p25=ebitda_band.p25,
        ev_ebitda_p50=ebitda_band.p50,
        ev_ebitda_p75=ebitda_band.p75,
        ev_ebitda_p90=ev_ebitda_p90,
        ev_ebitda_percentile_source=ebitda_band.source,
        ev_revenue_p25=revenue_band.p25,
        ev_revenue_p50=revenue_band.p50,
        ev_revenue_p75=revenue_band.p75,
        ev_revenue_percentile_source=revenue_band.source,
    )
