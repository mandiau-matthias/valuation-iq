"""
Market Data Collector for Step 2 Benchmarking

This module collects market data from FMP API and Redis cache.
Reuses existing FMPAdapter and MarketDataCacheService to avoid duplication.

Author: Upswitch Engineering Team
Date: January 2025
Status: Production Ready
"""

from typing import Any, Dict, Optional

from src.config.countries import peer_region_for_country
from src.utils.valuation_logger import ValuationLogger

from ..utils.benchmark_helpers import map_industry_to_sector

logger = ValuationLogger(__name__)

# Phase 3: Market Data Integration - Optional imports
try:
    from src.adapters.fmp_adapter import FMPAdapter
    from src.services.market.market_cache_service import CacheDataType, MarketDataCacheService

    MARKET_DATA_AVAILABLE = True
except ImportError:
    MARKET_DATA_AVAILABLE = False
    logger.warning("Market data services not available - using fallback defaults")


class MarketDataCollector:
    """
    Collects market data from FMP API and Redis cache.

    Reuses existing services:
    - FMPAdapter for FMP API calls
    - MarketDataCacheService for caching

    Dependencies:
    - fmp_adapter: FMPAdapter instance (optional)
    - cache_service: MarketDataCacheService instance (optional)
    """

    def __init__(self, fmp_adapter: Optional[Any] = None, cache_service: Optional[Any] = None):
        """
        Initialize MarketDataCollector.

        Args:
            fmp_adapter: FMPAdapter instance for FMP API calls (optional)
            cache_service: MarketDataCacheService instance for caching (optional)
        """
        self.fmp_adapter = fmp_adapter
        self.cache_service = cache_service
        self.market_data_available = MARKET_DATA_AVAILABLE and (
            fmp_adapter is not None or cache_service is not None
        )
        self.logger = logger

    async def fetch_from_fmp_api(
        self, request, industry: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch industry multiples from FMP API (Phase 3).

        Args:
            request: ValuationRequest object
            industry: Industry identifier

        Returns:
            Dict with multiples or None if unavailable

        Examples:
            >>> collector = MarketDataCollector(fmp_adapter=my_fmp_adapter)
            >>> multiples = await collector.fetch_from_fmp_api(request, "technology")
            >>> if multiples:
            ...     print(f"EV/EBITDA: {multiples.get('ev_ebitda_median')}")
        """
        if not self.fmp_adapter or not industry:
            return None

        try:
            # Map industry to FMP sector
            sector = map_industry_to_sector(industry)
            country_code = getattr(request, "country_code", "BE") or "BE"
            region = peer_region_for_country(country_code)

            # Fetch from FMP API
            multiples_data = await self.fmp_adapter.get_industry_multiples(
                sector=sector, region=region
            )

            if multiples_data and multiples_data.get("multiples"):
                self.logger.info(
                    f"✓ Fetched multiples from FMP API for sector {sector}",
                    extra={
                        "sector": sector,
                        "region": region,
                        "has_multiples": bool(multiples_data.get("multiples")),
                    },
                )
                return multiples_data["multiples"]

            return None
        except Exception as e:
            self.logger.warning(
                f"FMP API fetch failed: {e}",
                extra={"industry": industry, "error": str(e), "error_type": type(e).__name__},
            )
            return None

    async def fetch_from_cache(self, request, industry: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Fetch industry multiples from Redis cache (Phase 3).

        Args:
            request: ValuationRequest object
            industry: Industry identifier

        Returns:
            Dict with multiples or None if not cached

        Examples:
            >>> collector = MarketDataCollector(cache_service=my_cache_service, fmp_adapter=my_fmp_adapter)
            >>> cached = await collector.fetch_from_cache(request, "technology")
            >>> if cached:
            ...     print(f"Cached EV/EBITDA: {cached.get('ev_ebitda_median')}")
        """
        if not self.cache_service or not industry:
            return None

        try:
            sector = map_industry_to_sector(industry)
            country_code = getattr(request, "country_code", "BE") or "BE"

            # Try to get from cache
            cached_data = await self.cache_service.get_or_fetch(
                data_type=CacheDataType.INDUSTRY_MULTIPLES,
                primary_key=sector,
                fetch_function=(
                    self.fmp_adapter.get_industry_multiples if self.fmp_adapter else None
                ),
                query_params={
                    "sector": sector,
                    "region": peer_region_for_country(country_code),
                },
                force_refresh=False,
            )

            if cached_data and isinstance(cached_data, dict):
                # Handle both direct multiples and wrapped cache responses
                if "multiples" in cached_data:
                    self.logger.info(
                        f"✓ Retrieved multiples from cache for sector {sector}",
                        extra={"sector": sector, "cache_hit": True},
                    )
                    return cached_data["multiples"]
                elif "ev_ebitda_median" in cached_data:
                    self.logger.info(
                        f"✓ Retrieved multiples from cache (direct format) for sector {sector}",
                        extra={"sector": sector, "cache_hit": True},
                    )
                    return cached_data
                elif "data" in cached_data:
                    # Cache wrapper format
                    multiples = cached_data.get("data", {}).get("multiples")
                    if multiples:
                        self.logger.info(
                            f"✓ Retrieved multiples from cache (wrapped format) for sector {sector}",
                            extra={"sector": sector, "cache_hit": True},
                        )
                    return multiples

            return None
        except Exception as e:
            self.logger.warning(
                f"Cache fetch failed: {e}",
                extra={"industry": industry, "error": str(e), "error_type": type(e).__name__},
            )
            return None
