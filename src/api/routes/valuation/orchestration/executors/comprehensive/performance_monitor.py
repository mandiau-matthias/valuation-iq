"""
Performance Monitor for Comprehensive Valuation

Tracks and logs performance metrics for comprehensive valuation orchestration.
"""

import time
from decimal import Decimal
from typing import Any, Dict, Optional

from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.valuation_logger import ValuationLogger


class PerformanceMonitor:
    """
    Monitors performance for comprehensive valuation.

    Responsibilities:
    - Track stage timings
    - Log slow operations
    - Generate performance summaries
    """

    def __init__(
        self,
        performance_handler,  # Existing PerformanceHandler
        logger: Optional[ValuationLogger] = None,
    ):
        """
        Initialize performance monitor.

        Args:
            performance_handler: Existing PerformanceHandler instance
            logger: Optional logger instance
        """
        self.performance_handler = performance_handler
        self.logger = logger or ValuationLogger(self.__class__.__name__)

    def start_timing(self) -> Decimal:
        """
        Start timing for a stage.

        Returns:
            Start time
        """
        return self.performance_handler.start_timing()

    def record_stage_timing(
        self, stage_timings: Dict[str, Decimal], stage_name: str, start_time: Decimal
    ) -> Decimal:
        """
        Record stage timing.

        Args:
            stage_timings: Dictionary to store timings
            stage_name: Name of the stage
            start_time: Start time for the stage

        Returns:
            Duration of the stage
        """
        return self.performance_handler.record_stage_timing(stage_timings, stage_name, start_time)

    def log_slow_operation(
        self,
        operation_name: str,
        duration: Decimal,
        threshold: Decimal,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log slow operation.

        Args:
            operation_name: Name of the operation
            duration: Duration in seconds
            threshold: Threshold for slow operation
            context: Optional context dictionary
        """
        self.performance_handler.log_slow_operation(operation_name, duration, threshold, context)

    def log_performance_summary(
        self,
        valuation_id: str,
        equity_value_mid: Decimal,
        quality_rating_value: str,
        correlation_id: str,
        stage_timings: Dict[str, Decimal],
        overall_duration: Decimal,
    ) -> None:
        """
        Log performance summary.

        Args:
            valuation_id: Valuation ID
            equity_value_mid: Mid equity value
            quality_rating_value: Quality rating value
            correlation_id: Correlation ID
            stage_timings: Dictionary of stage timings
            overall_duration: Overall duration
        """
        # DEBUG: per-phase summary; the canonical request exit is the AUDIT
        # line "POST /api/v1/valuation/calculate → 200 (Xms)".
        self.logger.debug(
            "✅ Comprehensive valuation completed",
            extra={
                "valuation_id": valuation_id,
                "equity_value": equity_value_mid,
                "quality": quality_rating_value,
                "correlation_id": correlation_id,
                "performance_summary": {
                    "total_duration_seconds": round(overall_duration, 2),
                    "cache_init_seconds": round(stage_timings.get("cache_initialization", 0), 2),
                    "methodology_determination_seconds": round(
                        stage_timings.get("methodology_determination", 0), 2
                    ),
                    "weighted_metrics_seconds": round(stage_timings.get("weighted_metrics", 0), 2),
                    "valuation_calculation_seconds": round(
                        stage_timings.get("valuation_calculation", 0), 2
                    ),
                    "response_building_seconds": round(
                        stage_timings.get("response_building", 0), 2
                    ),
                },
            },
        )

        # Log warning if total duration is concerning
        if overall_duration > 20.0:
            self.logger.warning(
                f"⚠️ Slow overall valuation: {overall_duration:.2f}s",
                extra={
                    "total_duration_seconds": overall_duration,
                    "correlation_id": correlation_id,
                    "methodology": stage_timings.get("methodology", "unknown"),
                    "stage_breakdown": stage_timings,
                },
            )
