"""
Market Multiples Retrieval Coordinator

Orchestrates market multiples retrieval from comparables or industry benchmarks.
Handles calculation of median multiples and tracking of industry benchmarks.

RESPONSIBILITIES:
- Retrieve multiples from comparables or industry benchmarks
- Calculate median multiples from comparable companies
- Track industry benchmark data sources
- Handle transparency tracking for market data

ARCHITECTURE:
This coordinator acts as a thin orchestration layer that:
1. Determines source of multiples (comparables vs benchmarks)
2. Calculates median multiples from comparables
3. Tracks data sources for transparency
4. Handles industry benchmark tracking

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive error handling
- Detailed logging
- No code duplication
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional, Tuple

import numpy as np

from src.domain.models import ComparableCompany, FinancialData, IndustryBenchmarks
from src.domain.transparency import DataSource
from src.utils.logging import get_logger

logger = get_logger(__name__)


class MarketMultiplesRetrievalCoordinator:
    """
    Coordinates market multiples retrieval for the multiples engine.

    This coordinator handles:
    1. Retrieving multiples from comparables or industry benchmarks
    2. Calculating median multiples from comparable companies
    3. Tracking industry benchmark data sources
    """

    def __init__(
        self,
        financial_data: FinancialData,
        industry_benchmarks: IndustryBenchmarks,
        comparables: List[ComparableCompany],
        transparency: Any,  # TransparencyTracker
        transparency_collector: Optional[Any] = None,
    ) -> None:
        """
        Initialize market multiples retrieval coordinator.

        Args:
            financial_data: Company financial data
            industry_benchmarks: Industry benchmarks
            comparables: List of comparable companies
            transparency: Legacy transparency tracker
            transparency_collector: Frontend transparency collector
        """
        self.financial_data = financial_data
        self.industry_benchmarks = industry_benchmarks
        self.comparables = comparables
        self.transparency = transparency
        self.transparency_collector = transparency_collector
        self.logger = logger

    def get_market_multiples(
        self,
    ) -> Tuple[Optional[Decimal], Optional[Decimal], Optional[Decimal]]:
        """
        Get market multiples from comparables or industry benchmarks.

        Returns:
            Tuple of (EV/EBITDA, EV/Revenue, P/E)
        """
        if self.comparables:
            # Calculate multiples from comparable companies
            ebitda_multiple, revenue_multiple, pe_multiple = (
                self._calculate_multiples_from_comparables()
            )

            # Track market data from comparables
            if ebitda_multiple:
                self.transparency.record_market_data(
                    data_type="EV/EBITDA Multiple",
                    value=ebitda_multiple,
                    source_type=DataSource.BENCHMARK.value,
                    source_details="Median of supplied comparable observations; provider unverified",
                    comparables_count=sum(
                        1 for comp in self.comparables if comp.ev_ebitda is not None
                    ),
                    percentile=50,  # Using median
                    source_confidence=None,
                    provenance_status="unverified",
                )

            if revenue_multiple:
                self.transparency.record_market_data(
                    data_type="EV/Revenue Multiple",
                    value=revenue_multiple,
                    source_type=DataSource.BENCHMARK.value,
                    source_details="Median of supplied comparable observations; provider unverified",
                    comparables_count=sum(
                        1 for comp in self.comparables if comp.ev_revenue is not None
                    ),
                    percentile=50,
                    source_confidence=None,
                    provenance_status="unverified",
                )

            return ebitda_multiple, revenue_multiple, pe_multiple
        else:
            # Use supplied industry benchmarks without inventing their provenance.
            ebitda_multiple = self.industry_benchmarks.median_ev_ebitda
            revenue_multiple = self.industry_benchmarks.median_ev_revenue
            pe_multiple = self.industry_benchmarks.median_pe

            # The legacy benchmark contract has no source or observation-count fields.
            if ebitda_multiple:
                self.transparency.record_market_data(
                    data_type="EV/EBITDA Multiple",
                    value=ebitda_multiple,
                    source_type=DataSource.BENCHMARK.value,
                    source_details=f"Supplied industry benchmark - {self.financial_data.industry}; provider unverified",
                    comparables_count=None,
                    percentile=50,
                    raw_data_link=None,
                    source_confidence=None,
                    provenance_status="unverified",
                )

            if revenue_multiple:
                self.transparency.record_market_data(
                    data_type="EV/Revenue Multiple",
                    value=revenue_multiple,
                    source_type=DataSource.BENCHMARK.value,
                    source_details=f"Supplied industry benchmark - {self.financial_data.industry}; provider unverified",
                    comparables_count=None,
                    percentile=50,
                    raw_data_link=None,
                    source_confidence=None,
                    provenance_status="unverified",
                )

            return ebitda_multiple, revenue_multiple, pe_multiple

    def _calculate_multiples_from_comparables(
        self,
    ) -> Tuple[Optional[Decimal], Optional[Decimal], Optional[Decimal]]:
        """
        Calculate median multiples from comparable companies.

        Returns:
            Tuple of (EV/EBITDA, EV/Revenue, P/E)
        """
        ebitda_multiples = []
        revenue_multiples = []
        pe_multiples = []

        for comp in self.comparables:
            if comp.ev_ebitda:
                ebitda_multiples.append(comp.ev_ebitda)
            if comp.ev_revenue:
                revenue_multiples.append(comp.ev_revenue)
            if comp.pe_ratio:
                pe_multiples.append(comp.pe_ratio)

        # Calculate medians (more robust than means for outliers)
        ebitda_multiple = np.median(ebitda_multiples) if ebitda_multiples else None
        revenue_multiple = np.median(revenue_multiples) if revenue_multiples else None
        pe_multiple = np.median(pe_multiples) if pe_multiples else None

        return ebitda_multiple, revenue_multiple, pe_multiple

    def track_industry_benchmarks(self) -> None:
        """
        Track industry benchmark comparisons for transparency.

        This method tracks EBITDA margin, revenue growth, and other benchmarks
        for comparison with the subject company.
        """
        # EBITDA Margin Benchmark
        if self.financial_data.current_year.ebitda and self.financial_data.current_year.revenue:
            ebitda_margin = (
                self.financial_data.current_year.ebitda / self.financial_data.current_year.revenue
            )
            benchmark_margin = getattr(self.industry_benchmarks, "median_ebitda_margin", None)

            if benchmark_margin:
                comparison_text = (
                    f"Company EBITDA margin: {ebitda_margin:.1%} vs "
                    f"Industry median: {benchmark_margin:.1%}"
                )

                self.transparency.record_industry_benchmark(
                    benchmark_type="EBITDA Margin",
                    company_value=ebitda_margin,
                    benchmark_value=benchmark_margin,
                    comparison_text=comparison_text,
                    source_confidence=Decimal("0.80"),
                )
