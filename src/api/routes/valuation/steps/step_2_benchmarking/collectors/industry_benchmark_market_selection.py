"""Disclosed market-data fallback selection for Step 2 benchmarks."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Optional, Protocol

from src.utils.decimal_helpers import to_decimal

from ..utils.data_source_formatter import DataSourceFormatter


class LoggerLike(Protocol):
    def info(self, msg: str, *args: object, **kwargs: object) -> object: ...

    def warning(self, msg: str, *args: object, **kwargs: object) -> object: ...


class MarketDataCollectorLike(Protocol):
    async def fetch_from_fmp_api(
        self, request: object, industry: Optional[str]
    ) -> Optional[Dict[str, object]]: ...

    async def fetch_from_cache(
        self, request: object, industry: Optional[str]
    ) -> Optional[Dict[str, object]]: ...


@dataclass(frozen=True)
class MarketDataBenchmarkSelection:
    ev_ebitda_ratio: Optional[Decimal]
    revenue_multiple: Optional[Decimal]
    pe_ratio: Decimal
    data_source: str
    data_source_details: Dict[str, object]


async def apply_market_data_benchmark_selection(
    *,
    data_source: str,
    market_data_collector: Optional[MarketDataCollectorLike],
    allow_untrusted_multiples_fallback: bool,
    request: object,
    industry: Optional[str],
    ev_ebitda_ratio: Optional[Decimal],
    revenue_multiple: Optional[Decimal],
    pe_ratio: Decimal,
    data_source_details: Dict[str, object],
    logger: LoggerLike,
) -> MarketDataBenchmarkSelection:
    """Apply FMP/cache fallbacks only after explicit untrusted-fallback consent."""
    if data_source == "unknown" and market_data_collector and allow_untrusted_multiples_fallback:
        try:
            fmp_multiples = await asyncio.wait_for(
                market_data_collector.fetch_from_fmp_api(request, industry),
                timeout=8.0,
            )
            if fmp_multiples:
                raw_ebitda = fmp_multiples.get("ev_ebitda_median")
                raw_revenue = fmp_multiples.get("ev_revenue_median")
                raw_pe = fmp_multiples.get("pe_median")
                ev_ebitda_ratio = to_decimal(raw_ebitda) if raw_ebitda is not None else None
                revenue_multiple = to_decimal(raw_revenue) if raw_revenue is not None else None
                pe_ratio = to_decimal(raw_pe) if raw_pe is not None else Decimal("15.0")
                data_source = "fmp_api"
                data_source_details = {
                    "api_provider": "FMP",
                    "fallback_disclosure_required": True,
                    "sector": industry,
                    "company_count": fmp_multiples.get("company_count", 0),
                    "source": "fmp_api_direct",
                    "academic_sources": DataSourceFormatter.get_academic_sources_for_data_source(
                        "fmp_api"
                    ),
                    "academic_citations": DataSourceFormatter.format_academic_citations("fmp_api"),
                    "source_explanation": DataSourceFormatter.generate_source_explanation(
                        "fmp_api",
                        None,
                        {
                            "sector": industry,
                            "company_count": fmp_multiples.get("company_count", 0),
                        },
                    ),
                    "calibration_methodology": (
                        "SME size calibration per Koller, Goedhart & Wessels (2020) "
                        "and Trugman (2017)"
                    ),
                }
                logger.info(
                    f"Using FMP API multiples for {industry}",
                    extra={
                        "ev_ebitda_ratio": ev_ebitda_ratio,
                        "revenue_multiple": revenue_multiple,
                        "pe_ratio": pe_ratio,
                    },
                )
        except Exception as error:
            logger.warning(f"FMP API fetch failed: {error}, falling back to cache/DB")

    if (
        data_source == "unknown"
        and (not ev_ebitda_ratio or ev_ebitda_ratio <= 0)
        and market_data_collector
        and allow_untrusted_multiples_fallback
    ):
        try:
            cached_multiples = await market_data_collector.fetch_from_cache(request, industry)
            if cached_multiples:
                raw_ebitda = cached_multiples.get("ev_ebitda_median")
                raw_revenue = cached_multiples.get("ev_revenue_median")
                ev_ebitda_ratio = to_decimal(raw_ebitda) if raw_ebitda is not None else None
                revenue_multiple = to_decimal(raw_revenue) if raw_revenue is not None else None
                pe_ratio = to_decimal(cached_multiples.get("pe_median", Decimal("15.0")))
                data_source = "cache"
                data_source_details = {
                    "api_provider": "FMP",
                    "cache_hit": True,
                    "sector": industry,
                    "source": "redis_cache",
                    "academic_sources": DataSourceFormatter.get_academic_sources_for_data_source(
                        "cache"
                    ),
                    "academic_citations": DataSourceFormatter.format_academic_citations("cache"),
                    "source_explanation": DataSourceFormatter.generate_source_explanation(
                        "cache",
                        None,
                        {"sector": industry},
                    ),
                }
                logger.info(
                    f"Using cached multiples for {industry}",
                    extra={
                        "ev_ebitda_ratio": ev_ebitda_ratio,
                        "revenue_multiple": revenue_multiple,
                        "pe_ratio": pe_ratio,
                    },
                )
        except Exception as error:
            logger.warning(f"Cache fetch failed: {error}, falling back to DB")

    return MarketDataBenchmarkSelection(
        ev_ebitda_ratio=ev_ebitda_ratio,
        revenue_multiple=revenue_multiple,
        pe_ratio=pe_ratio,
        data_source=data_source,
        data_source_details=data_source_details,
    )
