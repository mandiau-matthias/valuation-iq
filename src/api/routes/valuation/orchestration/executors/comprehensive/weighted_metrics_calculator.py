"""
Weighted Metrics Calculator for Comprehensive Valuation Orchestrator

Handles weighted metrics calculation (McKinsey standard).
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from src.api.schemas import ValuationRequest
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.valuation_logger import ValuationLogger

from .performance_monitor import PerformanceMonitor


class WeightedMetricsCalculator:
    """Calculates weighted metrics using academic valuation standards (Koller, Goedhart & Wessels 2020)."""

    def __init__(
        self, weighted_calculator, performance_monitor: PerformanceMonitor, logger: ValuationLogger
    ):
        """
        Initialize the weighted metrics calculator.

        Args:
            weighted_calculator: Weighted calculator instance
            performance_monitor: Performance monitor instance
            logger: Logger instance
        """
        self.weighted_calculator = weighted_calculator
        self.performance_monitor = performance_monitor
        self.logger = logger

    def calculate_weighted_metrics(
        self,
        request: ValuationRequest,
        context: Optional[Dict[str, Any]],
        correlation_id: str,
        stage_timings: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Calculate weighted metrics (McKinsey standard: Year1×1/6 + Year2×2/6 + Year3×3/6).

        Args:
            request: The valuation request
            context: Processing context (will be updated with weighted_metrics)
            correlation_id: Correlation ID for logging
            stage_timings: Dictionary to track stage timings

        Returns:
            Weighted metrics dictionary
        """
        # Ensure context exists
        if context is None:
            context = {}

        # Calculate weighted metrics
        weighted_metrics_start = self.performance_monitor.start_timing()
        weighted_metrics = self.weighted_calculator.calculate_all_weighted_metrics(request)
        weighted_metrics_duration = self.performance_monitor.record_stage_timing(
            stage_timings, "weighted_metrics", weighted_metrics_start
        )

        self.performance_monitor.log_slow_operation(
            "weighted_metrics",
            weighted_metrics_duration,
            threshold=Decimal("1.0"),
            context={"correlation_id": correlation_id},
        )

        # Add to context for downstream use
        context["weighted_metrics"] = weighted_metrics

        # Log weighted metrics
        self.logger.info(
            "📊 Weighted metrics calculated (McKinsey standard)",
            extra={
                "weighted_ebitda": weighted_metrics["weighted_ebitda"],
                "weighted_revenue": weighted_metrics["weighted_revenue"],
                "ebitda_cagr": round(weighted_metrics["ebitda_cagr"] * 100, 2),
                "revenue_cagr": round(weighted_metrics["revenue_cagr"] * 100, 2),
                "weighting_method": weighted_metrics["weighting_schema"]["method"],
            },
        )

        return weighted_metrics
