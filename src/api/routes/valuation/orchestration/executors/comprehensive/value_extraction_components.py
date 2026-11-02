"""Pure value extraction and equity-range normalization helpers."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from src.utils.equity_range_normalization import coerce_equity_range_triple

MIN_VALUATION = Decimal("1.0")
AUTHORITATIVE_EQUITY_SOURCES = frozenset(("Step 11", "Hybrid (DCF + Multiples)"))


@dataclass(frozen=True)
class RawEquityValues:
    enterprise_value: object
    equity_value: object
    equity_value_low: object
    equity_value_mid: object
    equity_value_high: object


@dataclass(frozen=True)
class NormalizedEquityRange:
    equity_value_low: Decimal
    equity_value_mid: Decimal
    equity_value_high: Decimal
    used_equity_value_mid_fallback: bool = False
    recovered_missing_mid: bool = False
    applied_minimum_floor: bool = False
    widened: bool = False


def _first_present(values: dict[str, object], *keys: str) -> object:
    """Return the first non-None value, preserving explicit zeros."""
    for key in keys:
        if key in values and values[key] is not None:
            return values[key]
    return None


def _mapping(value: object) -> Optional[dict[str, object]]:
    return value if isinstance(value, dict) else None


def extract_raw_equity_values(detailed_results: dict[str, object]) -> RawEquityValues:
    """Extract top-level values and nested multiples/DCF fallbacks without logging."""
    enterprise_value = detailed_results.get("enterprise_value", Decimal("0.0"))
    equity_value = detailed_results.get("equity_value", Decimal("0.0"))
    equity_value_low = detailed_results.get("equity_value_low")
    equity_value_mid = detailed_results.get("equity_value_mid")
    equity_value_high = detailed_results.get("equity_value_high")

    if equity_value_low is None or equity_value_mid is None or equity_value_high is None:
        multiples_valuation = _mapping(detailed_results.get("multiples_valuation", {}))
        if multiples_valuation is not None:
            equity_value_low, equity_value_mid, equity_value_high = _fill_from_mapping(
                values=multiples_valuation,
                equity_value_low=equity_value_low,
                equity_value_mid=equity_value_mid,
                equity_value_high=equity_value_high,
            )

    if equity_value_low is None or equity_value_mid is None or equity_value_high is None:
        dcf_valuation = _mapping(detailed_results.get("dcf_valuation", {}))
        if dcf_valuation is not None:
            equity_value_low, equity_value_mid, equity_value_high = _fill_from_mapping(
                values=dcf_valuation,
                equity_value_low=equity_value_low,
                equity_value_mid=equity_value_mid,
                equity_value_high=equity_value_high,
            )

    return RawEquityValues(
        enterprise_value=enterprise_value,
        equity_value=equity_value,
        equity_value_low=equity_value_low,
        equity_value_mid=equity_value_mid,
        equity_value_high=equity_value_high,
    )


def _fill_from_mapping(
    *,
    values: dict[str, object],
    equity_value_low: object,
    equity_value_mid: object,
    equity_value_high: object,
) -> tuple[object, object, object]:
    if equity_value_low is None:
        equity_value_low = values.get("equity_value_low")
    if equity_value_mid is None:
        equity_value_mid = _first_present(values, "equity_value_mid", "equity_value")
    if equity_value_high is None:
        equity_value_high = values.get("equity_value_high")
    return equity_value_low, equity_value_mid, equity_value_high


def normalize_equity_range(raw: RawEquityValues) -> NormalizedEquityRange:
    """Resolve missing/invalid range components and enforce low <= mid <= high."""
    equity_value_low = raw.equity_value_low
    equity_value_mid = raw.equity_value_mid
    equity_value_high = raw.equity_value_high
    used_equity_value_mid_fallback = False
    recovered_missing_mid = False
    applied_minimum_floor = False

    if equity_value_mid is None and raw.equity_value > 0:
        equity_value_mid = raw.equity_value
        used_equity_value_mid_fallback = True

    if equity_value_mid is None:
        recovered_missing_mid = True
        equity_value_mid = raw.equity_value if raw.equity_value > 0 else Decimal("0.0")
        equity_value_low = _default_low(equity_value_mid, equity_value_low)
        equity_value_high = _default_high(equity_value_mid, equity_value_high)

    equity_value_low = _default_low(equity_value_mid, equity_value_low)
    equity_value_high = _default_high(equity_value_mid, equity_value_high)

    if equity_value_mid <= 0:
        equity_value_mid = MIN_VALUATION
        equity_value_low = MIN_VALUATION * Decimal("0.8")
        equity_value_high = MIN_VALUATION * Decimal("1.2")
        applied_minimum_floor = True
    if equity_value_low <= 0:
        equity_value_low = equity_value_mid * Decimal("0.8")
    if equity_value_high <= 0:
        equity_value_high = equity_value_mid * Decimal("1.2")

    equity_value_low, equity_value_mid, equity_value_high, widened = coerce_equity_range_triple(
        equity_value_low, equity_value_mid, equity_value_high
    )
    return NormalizedEquityRange(
        equity_value_low=equity_value_low,
        equity_value_mid=equity_value_mid,
        equity_value_high=equity_value_high,
        used_equity_value_mid_fallback=used_equity_value_mid_fallback,
        recovered_missing_mid=recovered_missing_mid,
        applied_minimum_floor=applied_minimum_floor,
        widened=widened,
    )


def _default_low(equity_value_mid: object, equity_value_low: object) -> object:
    if equity_value_low is not None:
        return equity_value_low
    return equity_value_mid * Decimal("0.8") if equity_value_mid > 0 else Decimal("0.0")


def _default_high(equity_value_mid: object, equity_value_high: object) -> object:
    if equity_value_high is not None:
        return equity_value_high
    return equity_value_mid * Decimal("1.2") if equity_value_mid > 0 else Decimal("0.0")


def value_sources(detailed_results: dict[str, object]) -> dict[str, object]:
    source_payload = detailed_results.get("_value_sources", {})
    return source_payload if isinstance(source_payload, dict) else {}


def equity_sources_are_authoritative(sources: dict[str, object]) -> bool:
    return (
        sources.get("equity_value_low_source") in AUTHORITATIVE_EQUITY_SOURCES
        and sources.get("equity_value_mid_source") in AUTHORITATIVE_EQUITY_SOURCES
        and sources.get("equity_value_high_source") in AUTHORITATIVE_EQUITY_SOURCES
    )
