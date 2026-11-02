"""
Performance Handler

Performance monitoring for valuation orchestration.
Tracks timing, metrics, and resource usage.
"""

import time
from decimal import Decimal
from typing import Any, Dict, Optional

from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.valuation_logger import ValuationLogger


class PerformanceHandler:
    """
    Handler for performance monitoring in valuation orchestration.

    Responsibilities:
    - Performance monitoring (timing, metrics)
    - Stage timing collection
    - Performance logging
    """

    def __init__(self, logger: Optional[ValuationLogger] = None):
        """
        Initialize performance handler.

        Args:
            logger: Optional logger instance
        """
        self.logger = logger or ValuationLogger(self.__class__.__name__)
        self.logger.debug("✅ PerformanceHandler initialized")

    def start_timing(self) -> Decimal:
        """
        Start timing measurement.

        Returns:
            Start time (timestamp) as Decimal for type consistency
        """
        # Return as Decimal for type consistency, but note that time.time() returns float
        # This is handled in post_processing_handler.py with safe type conversion
        return Decimal(str(time.time()))

    def record_stage_timing(
        self, stage_timings: Dict[str, Decimal], stage_name: str, start_time: Decimal
    ) -> Decimal:
        """
        Record timing for a stage.

        Args:
            stage_timings: Dictionary to store stage timings
            stage_name: Name of the stage
            start_time: Start time for the stage

        Returns:
            Duration of the stage
        """
        # CRITICAL FIX: Convert start_time to float if it's Decimal to match time.time() return type
        # Then convert result back to Decimal to match return type and stage_timings dict type
        start_time_float = float(start_time) if isinstance(start_time, Decimal) else start_time
        duration_float = time.time() - start_time_float
        duration = Decimal(str(duration_float))
        stage_timings[stage_name] = duration
        return duration

    def log_slow_operation(
        self,
        operation_name: str,
        duration: Decimal,
        threshold: Decimal = Decimal("5.0"),
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log slow operations that exceed threshold.

        Args:
            operation_name: Name of the operation
            duration: Duration in seconds
            threshold: Threshold for slow operations (default: 5.0s)
            context: Optional context for logging
        """
        if duration > threshold:
            self.logger.warning(
                f"⚠️ Slow {operation_name}: {duration:.2f}s",
                extra={
                    "duration_seconds": duration,
                    "operation": operation_name,
                    "threshold": threshold,
                    **(context or {}),
                },
            )
        else:
            # DEBUG: every operation logs its own duration; AUDIT line at the
            # end of the request shows the total wall time. Per-operation
            # timings are routinely <0.1s and produce noise; keep them at
            # DEBUG and only WARN when an operation exceeds the threshold.
            self.logger.debug(
                f"✅ {operation_name} completed: {duration:.2f}s",
                extra={
                    "duration_seconds": duration,
                    "operation": operation_name,
                    **(context or {}),
                },
            )

    def log_valuation_calculation_timing(
        self, duration: Decimal, methodology: str, correlation_id: Optional[str] = None
    ) -> None:
        """
        Log valuation calculation timing.

        Args:
            duration: Duration in seconds
            methodology: Methodology used
            correlation_id: Optional correlation ID
        """
        self.log_slow_operation(
            "Valuation calculation",
            duration,
            threshold=Decimal("5.0"),
            context={"methodology": methodology, "correlation_id": correlation_id},
        )

    def log_response_building_timing(
        self, duration: Decimal, correlation_id: Optional[str] = None
    ) -> None:
        """
        Log response building timing.

        Args:
            duration: Duration in seconds
            correlation_id: Optional correlation ID
        """
        self.log_slow_operation(
            "Response building",
            duration,
            threshold=Decimal("2.0"),
            context={"correlation_id": correlation_id},
        )
