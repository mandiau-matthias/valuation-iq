"""
Value Drivers Extraction Coordinator

Handles value drivers extraction logic.
Extracted from summary_generator.py to improve modularity.

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive value drivers extraction
- Detailed logging
"""

from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.api.routes.valuation.shared.historical_years import oldest_historical_year
from src.api.schemas import ValuationRequest
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ValueDriversExtractionCoordinator:
    """
    Coordinates value drivers extraction logic.

    Responsibilities:
    - Extract value drivers from synthesizer data
    - Extract value drivers from financial metrics
    - Extract value drivers from request data
    - Ensure at least one driver is always returned
    """

    def __init__(self, logger_instance=None):
        """
        Initialize value drivers extraction coordinator.

        Args:
            logger_instance: Logger instance (optional)
        """
        self.logger = logger_instance or logger

    def extract_value_drivers(
        self, request: ValuationRequest, results: Dict[str, Any]
    ) -> List[str]:
        """
        Extract key value drivers.

        Priority:
        1. Use synthesizer data if available (quantitative, sophisticated)
        2. Calculate from financial metrics (quantitative)
        3. Fallback to basic logic

        Args:
            request: Valuation request
            results: Valuation results

        Returns:
            List of value driver descriptions
        """
        try:
            # DEBUG: lifecycle breadcrumb; "Extracted N value drivers" carries the summary.
            self.logger.debug("🎯 Extracting value drivers")

            # PRIORITY 1: Check for synthesizer data
            synthesizer_drivers = self._extract_drivers_from_synthesizer(results)
            if synthesizer_drivers:
                return synthesizer_drivers

            drivers = []

            # PRIORITY 2: Calculate from financial metrics
            financial_metrics = results.get("financial_metrics")
            if financial_metrics:
                drivers.extend(self._extract_drivers_from_financial_metrics(financial_metrics))

            # PRIORITY 3: Deterministic extraction from request data
            if len(drivers) == 0:
                self.logger.debug("Using deterministic value driver extraction")
                drivers.extend(self._extract_drivers_from_request_data(request, financial_metrics))

            # ENSURE at least 1 driver always returned
            if len(drivers) == 0:
                revenue = request.current_year_data.revenue or 0
                drivers.append(f"Operating business with €{revenue:,.0f} in annual revenue")

            self.logger.info(
                f"✅ Extracted {len(drivers)} value drivers",
                extra={
                    "driver_count": len(drivers),
                    "source": (
                        "synthesizer"
                        if synthesizer_drivers
                        else ("financial_metrics" if financial_metrics else "request_data")
                    ),
                },
            )

            return drivers[:5]  # Return top 5

        except Exception as e:
            self.logger.error(
                f"❌ Value driver extraction failed: {e}",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            return []

    def _extract_drivers_from_synthesizer(self, results: Dict[str, Any]) -> Optional[List[str]]:
        """
        Extract value drivers from synthesizer data (Priority 1).

        Args:
            results: Valuation results

        Returns:
            List of value drivers if found, None otherwise
        """
        synthesized_valuation = results.get("synthesized_valuation")
        if not synthesized_valuation:
            return None

        # Check if it's an object with key_value_drivers attribute
        if hasattr(synthesized_valuation, "key_value_drivers"):
            drivers = synthesized_valuation.key_value_drivers
            if drivers and len(drivers) > 0:
                self.logger.info(f"✅ Using synthesizer value drivers ({len(drivers)} drivers)")
                return drivers[:5]

        # Check if it's a dict
        if isinstance(synthesized_valuation, dict) and "key_value_drivers" in synthesized_valuation:
            drivers = synthesized_valuation["key_value_drivers"]
            if drivers and len(drivers) > 0:
                self.logger.info(
                    f"✅ Using synthesizer value drivers from dict ({len(drivers)} drivers)"
                )
                return drivers[:5]

        return None

    def _extract_drivers_from_financial_metrics(
        self, financial_metrics: Dict[str, Any]
    ) -> List[str]:
        """
        Extract value drivers from financial metrics (Priority 2).

        Args:
            financial_metrics: Financial metrics dictionary

        Returns:
            List of value driver descriptions
        """
        from .value_drivers.drivers import (
            CapitalStructureDriverExtractor,
            CashFlowDriverExtractor,
            FinancialHealthDriverExtractor,
            GrowthDriverExtractor,
            ProfitabilityDriverExtractor,
        )

        if not financial_metrics or not isinstance(financial_metrics, dict):
            return []

        drivers = []

        # Extract drivers from each category
        drivers.extend(ProfitabilityDriverExtractor.extract(financial_metrics))
        drivers.extend(GrowthDriverExtractor.extract(financial_metrics))
        drivers.extend(FinancialHealthDriverExtractor.extract(financial_metrics))
        drivers.extend(CapitalStructureDriverExtractor.extract(financial_metrics))
        drivers.extend(CashFlowDriverExtractor.extract(financial_metrics))

        return drivers

    def _extract_drivers_from_request_data(
        self, request: ValuationRequest, financial_metrics: Optional[Dict[str, Any]]
    ) -> List[str]:
        """
        Extract value drivers from request data (Priority 3).

        Args:
            request: Valuation request
            financial_metrics: Optional financial metrics

        Returns:
            List of value driver descriptions
        """
        drivers = []
        revenue = request.current_year_data.revenue or 0
        ebitda = request.current_year_data.ebitda or 0

        # 1. Check profitability
        if ebitda > 0 and revenue > 0:
            margin = ebitda / revenue
            if margin > 0.15:
                drivers.append(
                    f"Strong profitability: EBITDA margin {margin:.1%} "
                    + ("exceeds" if margin > Decimal("0.20") else "approaches")
                    + " industry benchmarks"
                )

        # 2. Check business maturity
        if request.founding_year:
            years = date.today().year - request.founding_year
            if years >= 5:
                drivers.append(
                    f"Established business: {years} years of operational history demonstrates market validation and business sustainability"
                )

        # 3. Check financial health
        financial_health = (
            financial_metrics.get("financial_health_score", 0) if financial_metrics else 0
        )
        if financial_health >= 70:
            drivers.append(
                f"Excellent financial health and low bankruptcy risk (score: {financial_health}/100)"
            )

        # 4. Industry position
        if revenue >= 1_000_000:
            drivers.append(
                f"Established market presence with scale (€{revenue:,.0f} annual revenue)"
            )

        # 5. Growth trajectory
        if request.historical_years_data and len(request.historical_years_data) > 0:
            oldest_year = oldest_historical_year(request.historical_years_data)
            oldest_revenue = getattr(oldest_year, "revenue", 0) or 0
            if oldest_revenue > 0:
                growth = (revenue - oldest_revenue) / oldest_revenue
                if growth > 0.10:
                    drivers.append(
                        f"Positive revenue growth trajectory ({growth:.1%} compound growth)"
                    )

        return drivers
