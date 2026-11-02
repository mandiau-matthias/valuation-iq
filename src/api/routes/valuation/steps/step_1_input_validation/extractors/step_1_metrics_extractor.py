"""
Step 1 Metrics Extractor

Extracts financial metrics (revenue, EBITDA) with fallback logic.
"""

from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from src.utils.decimal_helpers import to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class Step1MetricsExtractor:
    """Extracts financial metrics with fallback logic."""

    def __init__(self):
        """Initialize the metrics extractor."""
        pass

    def extract_financial_metrics(
        self, request: any, context: Dict[str, Any]
    ) -> Tuple[Decimal, Optional[Decimal], bool, str]:
        """
        Extract financial metrics with fallback logic.

        Priority (McKinsey standard — multi-year weighted average is the
        sustainable earnings basis when available):

        1. Multi-year weighted EBITDA when historical data exists, combined
           with current-year revenue (most recent top-line for sizing).
        2. Current year data only (single-year scenario).
        3. Weighted metrics fallback.
        4. No data (returns Decimal('0'), None).

        Per McKinsey *Valuation* (2020, Ch. 8) and Koller et al., the
        weighted average smooths cyclical volatility and better represents
        sustainable earnings power.  Revenue uses the current year because
        the most recent top-line is the relevant sizing metric for multiple
        selection and size-tier determination.

        Args:
            request: Valuation request
            context: Step context dictionary

        Returns:
            Tuple of (revenue, ebitda, using_weighted, weighting_method)
        """
        current_data = request.current_year_data
        weighted_metrics = context.get("weighted_metrics", {})
        _hist_raw = getattr(request, "historical_years_data", None)
        historical_data = list(_hist_raw) if isinstance(_hist_raw, (list, tuple)) else []
        has_multi_year = len(historical_data) >= 1
        weighted_ebitda_valid = (
            weighted_metrics
            and weighted_metrics.get("weighted_ebitda") is not None
        )

        _raw_rev = getattr(current_data, "revenue", None) if current_data else None
        current_revenue = _raw_rev if _raw_rev is not None else 0
        current_ebitda = getattr(current_data, "ebitda", None) if current_data else None
        try:
            _has_current_revenue = current_revenue is not None and float(current_revenue) > 0
        except (TypeError, ValueError):
            _has_current_revenue = False
        _has_current_ebitda = current_ebitda is not None
        current_year_has_data = current_data is not None and (
            _has_current_revenue or _has_current_ebitda
        )

        # DEBUG: input-source audit dump; the EBITDA-SOURCE-DECISION line
        # below records which source was selected at INFO.
        logger.debug(
            "🔍 [EBITDA-SOURCE-AUDIT] Extracting financial metrics - all sources",
            extra={
                "step_number": 1,
                "current_year_revenue": current_revenue if current_data else None,
                "current_year_ebitda": current_ebitda,
                "has_weighted_metrics": bool(weighted_metrics),
                "weighted_ebitda": weighted_metrics.get("weighted_ebitda") if weighted_metrics else None,
                "weighted_revenue": weighted_metrics.get("weighted_revenue") if weighted_metrics else None,
                "historical_years_count": len(historical_data),
                "has_multi_year": has_multi_year,
                "decision_priority": "Weighted EBITDA (multi-year) + current revenue > Current year only > Weighted fallback > None",
            },
        )

        logger.debug(
            "📥 Extracting financial metrics",
            extra={
                "step_number": 1,
                "has_current_year_data": bool(current_data),
                "has_weighted_metrics": bool(weighted_metrics),
                "weighted_metrics_keys": list(weighted_metrics.keys()) if weighted_metrics else [],
            },
        )

        # Priority 1: Multi-year weighted EBITDA + current-year revenue.
        # When we have multiple years, the weighted average is the
        # academically correct sustainable earnings basis (McKinsey Ch. 8).
        if current_year_has_data and has_multi_year and weighted_ebitda_valid:
            rev_source = current_revenue if _has_current_revenue else weighted_metrics.get("weighted_revenue", 0)
            revenue = to_decimal(rev_source)
            ebitda = weighted_metrics.get("weighted_ebitda")
            weighting_method = weighted_metrics.get("weighting_schema", {}).get(
                "method", "McKinsey weighted average"
            )

            # DEBUG: source-selection branch. The chosen EBITDA/revenue
            # surface on the Step 1 result and propagate to Step 3 INFO.
            logger.debug(
                "✅ [EBITDA-SOURCE-DECISION] Using WEIGHTED EBITDA + CURRENT YEAR REVENUE (multi-year)",
                extra={
                    "step_number": 1,
                    "selected_ebitda": ebitda,
                    "selected_revenue": revenue,
                    "current_year_ebitda_ignored": current_ebitda,
                    "rationale": "Multi-year weighted EBITDA for sustainable earnings; current-year revenue for sizing",
                    "weighting_method": weighting_method,
                    "historical_years": len(historical_data),
                    "note": "McKinsey standard: weighted average smooths cyclicality",
                },
            )
            return revenue, ebitda, True, weighting_method

        # Priority 2: Single-year scenario — use current year for both.
        if current_year_has_data:
            revenue, ebitda, using_weighted, weighting_method = self._extract_from_current_year(current_data)

            # DEBUG: source-selection branch (single-year fallback).
            logger.debug(
                "✅ [EBITDA-SOURCE-DECISION] Using CURRENT YEAR (single-year, no weighted data)",
                extra={
                    "step_number": 1,
                    "selected_ebitda": ebitda,
                    "selected_revenue": revenue,
                    "rationale": "Only one year of data — current year is the valuation basis",
                    "weighted_available": bool(weighted_metrics),
                    "historical_years": len(historical_data),
                    "note": "This EBITDA will be used in Step 3 for valuation",
                },
            )
            return revenue, ebitda, using_weighted, weighting_method

        # Priority 3: Weighted metrics when no current year data
        if weighted_ebitda_valid:
            revenue, ebitda, using_weighted, weighting_method = self._extract_from_weighted_metrics(weighted_metrics)

            # DEBUG: source-selection branch (historical-only).
            logger.debug(
                "✅ [EBITDA-SOURCE-DECISION] Using WEIGHTED METRICS (no current year data)",
                extra={
                    "step_number": 1,
                    "selected_ebitda": ebitda,
                    "selected_revenue": revenue,
                    "rationale": "No current year data — weighted average from historical years",
                    "weighting_method": weighting_method,
                    "historical_years": len(historical_data),
                    "note": "This weighted EBITDA will be used in Step 3 for valuation",
                },
            )
            return revenue, ebitda, using_weighted, weighting_method

        # Priority 4: No data available
        return self._extract_none()

    def _extract_from_current_year(
        self, current_data: any
    ) -> Tuple[Decimal, Optional[Decimal], bool, str]:
        """
        Extract metrics from current year data.

        Args:
            current_data: Current year data object

        Returns:
            Tuple of (revenue, ebitda, using_weighted, weighting_method)
        """
        revenue = to_decimal(getattr(current_data, "revenue", 0) or 0)
        ebitda = getattr(current_data, "ebitda", None)
        using_weighted = False
        weighting_method = "Current year only (most recent data)"

        # DEBUG: dup of the EBITDA-SOURCE-DECISION line above.
        logger.debug(
            "✅ Using current year metrics (prioritized for accuracy)",
            extra={
                "step_number": 1,
                "revenue": revenue,
                "ebitda": ebitda,
                "weighting_method": weighting_method,
                "rationale": "Current year data reflects most up-to-date performance",
            },
        )

        return revenue, ebitda, using_weighted, weighting_method

    def _extract_from_weighted_metrics(
        self, weighted_metrics: Dict[str, Any]
    ) -> Tuple[Decimal, Optional[Decimal], bool, str]:
        """
        Extract metrics from weighted metrics.

        Args:
            weighted_metrics: Weighted metrics dictionary from context

        Returns:
            Tuple of (revenue, ebitda, using_weighted, weighting_method)
        """
        revenue = to_decimal(weighted_metrics.get("weighted_revenue", 0) or 0)
        ebitda = weighted_metrics.get("weighted_ebitda", None)
        using_weighted = True
        weighting_method = weighted_metrics.get("weighting_schema", {}).get("method", "N/A")

        logger.info(
            "✅ Using weighted metrics (current year data not available)",
            extra={
                "step_number": 1,
                "weighted_revenue": revenue,
                "weighted_ebitda": ebitda,
                "weighting_method": weighting_method,
                "formula": "Weighted = Year1×1/6 + Year2×2/6 + Year3×3/6",
            },
        )

        return revenue, ebitda, using_weighted, weighting_method

    def _extract_none(self) -> Tuple[Decimal, Optional[Decimal], bool, str]:
        """
        Handle no data available scenario.

        Returns:
            Tuple of (revenue, ebitda, using_weighted, weighting_method)
        """
        revenue = Decimal("0")
        ebitda = None
        using_weighted = False
        weighting_method = "No data available"

        logger.warning(
            "⚠️ No financial data available",
            extra={
                "step_number": 1,
                "revenue": revenue,
                "ebitda": ebitda,
                "weighting_method": weighting_method,
            },
        )

        return revenue, ebitda, using_weighted, weighting_method
