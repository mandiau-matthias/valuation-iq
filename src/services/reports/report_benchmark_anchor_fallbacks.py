"""Sector benchmark anchor fallbacks for report benchmark context."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Optional, TypeAlias

from src.services.reports.protocol_adapter import _attr
from src.utils.decimal_helpers import safe_float

ReportMap: TypeAlias = dict[str, object]
BenchmarkBand: TypeAlias = tuple[float, Optional[float], Optional[float]]

# Honest provenance label for the engine's cached sector anchor (the same
# sector reference published on the public website). Deliberately NOT dressed
# up as a live, dated Upswitch Index contract.
_ENGINE_SECTOR_ANCHOR_SOURCE = "Upswitch sector benchmark (database anchor)"


def _synced_db_ev_ebitda_band(
    business_type_id: Optional[str],
    country_code: Optional[str],
) -> Optional[BenchmarkBand]:
    """Resolve the raw business-types DB EV/EBITDA anchor."""
    if not business_type_id:
        return None
    try:
        return _ev_ebitda_band_from_benchmarks(
            _business_type_benchmarks(str(business_type_id), str(country_code or "BE"))
        )
    except Exception:
        return None


def _business_type_benchmarks(business_type_id: str, country_code: str) -> Iterable[object]:
    from src.database.business_types_repository import get_business_types_repository

    with get_business_types_repository() as repo:
        return repo.get_benchmarks(business_type_id, country_code) or []


def _ev_ebitda_band_from_benchmarks(
    benchmarks: Iterable[object],
) -> Optional[BenchmarkBand]:
    for benchmark in benchmarks:
        if getattr(benchmark, "metric_name", "") != "ev_ebitda_multiple":
            continue
        return _ev_ebitda_band_from_benchmark(benchmark)
    return None


def _ev_ebitda_band_from_benchmark(benchmark: object) -> Optional[BenchmarkBand]:
    median = safe_float(getattr(benchmark, "median", None))
    if not median or median <= 0:
        return None
    p25 = safe_float(getattr(benchmark, "p25", None))
    p75 = safe_float(getattr(benchmark, "p75", None))
    if not (p25 and p75 and p25 <= median <= p75):
        p25 = p75 = None
    return median, p25, p75


def _positive_mix_segments(
    business_type_mix: Optional[list[dict[str, object]]],
) -> list[tuple[str, float]]:
    segments: list[tuple[str, float]] = []
    for segment in business_type_mix or []:
        business_type_id = str(segment.get("business_type_id") or "").strip()
        if not business_type_id:
            continue
        try:
            weight = float(segment.get("weight") or 0)
        except (TypeError, ValueError):
            continue
        if weight > 0:
            segments.append((business_type_id, weight / 100))
    return segments


def _synced_db_ev_ebitda_mix_band(
    business_type_mix: Optional[list[dict[str, object]]],
    country_code: Optional[str],
) -> Optional[BenchmarkBand]:
    segments = _positive_mix_segments(business_type_mix)
    if len(segments) <= 1:
        return None

    bands: list[tuple[float, BenchmarkBand]] = []
    for business_type_id, weight in segments:
        band = _synced_db_ev_ebitda_band(business_type_id, country_code)
        if band is None:
            return None
        bands.append((weight, band))

    def weighted(read: Callable[[BenchmarkBand], Optional[float]]) -> Optional[float]:
        total = 0.0
        weight_total = 0.0
        for weight, band in bands:
            value = read(band)
            if value is None:
                continue
            total += value * weight
            weight_total += weight
        return round(total / weight_total, 4) if weight_total > 0 else None

    median = weighted(lambda band: band[0])
    if median is None or median <= 0:
        return None
    return median, weighted(lambda band: band[1]), weighted(lambda band: band[2])


def _engine_ev_ebitda_band(response: object) -> Optional[tuple[float, float, float]]:
    """Return the sector EV/EBITDA percentile band the engine already computed."""
    multiples_valuation = _attr(response, "multiples_valuation", None)
    if not multiples_valuation:
        return None
    mid = safe_float(_attr(multiples_valuation, "p50_ebitda_multiple", None))
    if not mid or mid <= 0:
        return None
    low = safe_float(_attr(multiples_valuation, "p25_ebitda_multiple", None))
    high = safe_float(_attr(multiples_valuation, "p75_ebitda_multiple", None))
    if not low or low <= 0 or low > mid:
        low = mid * 0.8
    if not high or high <= 0 or high < mid:
        high = mid * 1.2
    return low, mid, high


def _apply_synced_db_anchor_fallback(
    benchmarks: ReportMap,
    *,
    business_type_id: Optional[str],
    business_type_mix: Optional[list[dict[str, object]]],
    country_code: Optional[str],
    response: object,
) -> None:
    if benchmarks.get("has_benchmarks"):
        return
    if not _attr(response, "multiples_valuation", None):
        return
    band = _synced_db_ev_ebitda_mix_band(
        business_type_mix, country_code
    ) or _synced_db_ev_ebitda_band(business_type_id, country_code)
    if band is None:
        return
    median, p25, p75 = band
    benchmarks["ev_ebitda_p50"] = median
    benchmarks["ev_ebitda_p25"] = p25 if p25 is not None else median * 0.8
    benchmarks["ev_ebitda_p75"] = p75 if p75 is not None else median * 1.2
    benchmarks["sample_size"] = None
    benchmarks["data_source"] = _ENGINE_SECTOR_ANCHOR_SOURCE
    if business_type_mix and len(business_type_mix) > 1:
        benchmarks["source_mix"] = {
            "strategy": "weighted_business_type_mix",
            "segments": business_type_mix,
        }
    benchmarks["has_benchmarks"] = True


def _apply_engine_band_fallback(benchmarks: ReportMap, *, response: object) -> None:
    if benchmarks.get("has_benchmarks"):
        return
    band = _engine_ev_ebitda_band(response)
    if band is None:
        return
    low, mid, high = band
    benchmarks["ev_ebitda_p25"] = low
    benchmarks["ev_ebitda_p50"] = mid
    benchmarks["ev_ebitda_p75"] = high
    benchmarks["sample_size"] = None
    benchmarks["data_source"] = _ENGINE_SECTOR_ANCHOR_SOURCE
    benchmarks["has_benchmarks"] = True


def apply_benchmark_anchor_fallbacks(
    benchmarks: ReportMap,
    *,
    business_type_id: Optional[str],
    business_type_mix: Optional[list[dict[str, object]]] = None,
    country_code: Optional[str],
    response: object,
) -> None:
    """Apply raw DB and engine sector-band fallbacks when no live contract resolved."""
    _apply_synced_db_anchor_fallback(
        benchmarks,
        business_type_id=business_type_id,
        business_type_mix=business_type_mix,
        country_code=country_code,
        response=response,
    )
    _apply_engine_band_fallback(benchmarks, response=response)
