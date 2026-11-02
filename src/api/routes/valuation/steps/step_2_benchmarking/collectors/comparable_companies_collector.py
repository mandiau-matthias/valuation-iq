"""
Comparable Companies Collector for Step 2 Benchmarking

This module can find public-company comparables from FMP API, but only when
the caller explicitly accepts untrusted market-data fallback context.

Author: Upswitch Engineering Team
Date: January 2025
Status: Production Ready
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.config.countries import peer_region_for_country
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.valuation_logger import ValuationLogger

from ..calculators.percentile_calculator import calculate_p25_p50_p75
from ..utils.benchmark_helpers import map_industry_to_sector

logger = ValuationLogger(__name__)

# Phase 3: Market Data Integration - Optional imports
try:
    from src.adapters.fmp_adapter import FMPAdapter

    MARKET_DATA_AVAILABLE = True
except ImportError:
    MARKET_DATA_AVAILABLE = False
    logger.warning("FMP adapter not available - comparable companies collection disabled")


def _request_allows_untrusted_multiples_fallback(request: Any) -> bool:
    if getattr(request, "allow_untrusted_multiples_fallback", False) is True:
        return True
    metadata = getattr(request, "metadata", None)
    return isinstance(metadata, dict) and metadata.get("allow_untrusted_multiples_fallback") is True


class ComparableCompaniesCollector:
    """
    Finds comparable companies from FMP API and calculates percentiles.

    Reuses existing services:
    - FMPAdapter for comparable company search
    - PercentileCalculator for percentile calculations

    Dependencies:
    - fmp_adapter: FMPAdapter instance (optional)
    """

    def __init__(self, fmp_adapter: Optional[Any] = None):
        """
        Initialize ComparableCompaniesCollector.

        Args:
            fmp_adapter: FMPAdapter instance for comparable company search (optional)
        """
        self.fmp_adapter = fmp_adapter
        self.market_data_available = MARKET_DATA_AVAILABLE and fmp_adapter is not None
        self.logger = logger

    async def find_comparable_companies(self, request, revenue: Decimal) -> Dict[str, Any]:
        """
        Find comparable companies for analysis (Phase 4).

        Implementation:
        1. Return empty context unless allow_untrusted_multiples_fallback=true
        2. Search FMP API for comparable companies only under that opt-in
        3. Filter by industry, size, business model
        4. Calculate percentiles from comparables using PercentileCalculator
        5. Determine if sufficient for dispersion method (>=5)

        Args:
            request: ValuationRequest object
            revenue: Company revenue for size matching

        Returns:
            Dict with count, comparables list, percentiles, and sufficient flag

        Examples:
            >>> collector = ComparableCompaniesCollector(fmp_adapter=my_fmp_adapter)
            >>> comparables = await collector.find_comparable_companies(request, Decimal('1000000.0'))
            >>> print(f"Found {comparables['count']} comparables")
            >>> print(f"EV/EBITDA P50: {comparables['ev_ebitda_p50']}")
        """
        comparables_count = 0
        comparables_list = []
        sufficient = False
        ev_ebitda_p25 = None
        ev_ebitda_p50 = None
        ev_ebitda_p75 = None
        ev_revenue_p25 = None
        ev_revenue_p50 = None
        ev_revenue_p75 = None

        if not _request_allows_untrusted_multiples_fallback(request):
            return {
                "count": comparables_count,
                "comparables": comparables_list,
                "sufficient": sufficient,
                "ev_ebitda_p25": ev_ebitda_p25,
                "ev_ebitda_p50": ev_ebitda_p50,
                "ev_ebitda_p75": ev_ebitda_p75,
                "ev_revenue_p25": ev_revenue_p25,
                "ev_revenue_p50": ev_revenue_p50,
                "ev_revenue_p75": ev_revenue_p75,
                "data_source": "none",
                "reason": "public_company_comparables_require_explicit_fallback_opt_in",
            }

        # Phase 4: Find public-company comparables from FMP API after opt-in
        if self.market_data_available and self.fmp_adapter:
            try:
                industry = getattr(request, "industry", None)
                country_code = getattr(request, "country_code", "BE") or "BE"

                if industry:
                    sector = map_industry_to_sector(industry)

                    # Search for comparable companies
                    # Revenue range: 50% to 200% of target revenue
                    revenue_min = revenue * Decimal("0.5")
                    revenue_max = revenue * Decimal("2.0")

                    comparables = await self.fmp_adapter.find_comparable_companies(
                        sector=sector,
                        revenue_min=revenue_min,
                        revenue_max=revenue_max,
                        country=peer_region_for_country(country_code),
                        limit=20,  # Get more to filter
                    )

                    if comparables and len(comparables) > 0:
                        comparables_count = len(comparables)
                        comparables_list = comparables[:10]  # Top 10 for transparency
                        sufficient = comparables_count >= 5

                        # Extract multiples from comparables
                        ev_ebitda_multiples = [
                            c.get("ev_ebitda", 0)
                            for c in comparables
                            if c.get("ev_ebitda") and c.get("ev_ebitda") > 0
                        ]
                        ev_revenue_multiples = [
                            c.get("ev_revenue", 0)
                            for c in comparables
                            if c.get("ev_revenue") and c.get("ev_revenue") > 0
                        ]

                        # Calculate percentiles using PercentileCalculator
                        if len(ev_ebitda_multiples) >= 3:
                            ebitda_percentiles = calculate_p25_p50_p75(ev_ebitda_multiples)
                            ev_ebitda_p25 = ebitda_percentiles.get("p25")
                            ev_ebitda_p50 = ebitda_percentiles.get("p50")
                            ev_ebitda_p75 = ebitda_percentiles.get("p75")

                        if len(ev_revenue_multiples) >= 3:
                            revenue_percentiles = calculate_p25_p50_p75(ev_revenue_multiples)
                            ev_revenue_p25 = revenue_percentiles.get("p25")
                            ev_revenue_p50 = revenue_percentiles.get("p50")
                            ev_revenue_p75 = revenue_percentiles.get("p75")

                        self.logger.info(
                            f"✓ Found {comparables_count} comparable companies",
                            extra={
                                "sector": sector,
                                "revenue_range": f"€{revenue_min:,.0f}-€{revenue_max:,.0f}",
                                "sufficient": sufficient,
                                "ev_ebitda_count": len(ev_ebitda_multiples),
                                "ev_revenue_count": len(ev_revenue_multiples),
                            },
                        )
            except Exception as e:
                self.logger.warning(
                    f"Failed to find comparable companies: {e}",
                    extra={"error": str(e), "error_type": type(e).__name__, "revenue": revenue},
                )

        return {
            "count": comparables_count,
            "comparables": comparables_list,
            "sufficient": sufficient,
            "ev_ebitda_p25": ev_ebitda_p25,
            "ev_ebitda_p50": ev_ebitda_p50,
            "ev_ebitda_p75": ev_ebitda_p75,
            "ev_revenue_p25": ev_revenue_p25,
            "ev_revenue_p50": ev_revenue_p50,
            "ev_revenue_p75": ev_revenue_p75,
            "data_source": "fmp_api" if comparables_count > 0 else "none",
        }
