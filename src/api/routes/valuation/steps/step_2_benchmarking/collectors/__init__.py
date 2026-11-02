"""
Collectors module for Step 2 Benchmarking.

This module contains classes responsible for collecting benchmark data from
various sources (FMP API, cache, database, business rules).

Priority Cascade:
0. Titan-provided enrichment (ev_ebitda_multiple dict on request) — HIGHEST
1. Database Business Types (DB-driven multiples via adapter)
2. FMP API (real-time market data)
3. Redis Cache (cached market data)
4. Business-type specific defaults (hardcoded)
5. Industry defaults (fallback)
6. Generic defaults (last resort)
"""

from .comparable_companies_collector import ComparableCompaniesCollector
from .industry_benchmark_collector import IndustryBenchmarkCollector
from .industry_benchmark_defaults import BUSINESS_TYPE_DEFAULTS, INDUSTRY_DEFAULTS
from .market_data_collector import MarketDataCollector

__all__ = [
    "IndustryBenchmarkCollector",
    "MarketDataCollector",
    "ComparableCompaniesCollector",
    "BUSINESS_TYPE_DEFAULTS",
    "INDUSTRY_DEFAULTS",
]
