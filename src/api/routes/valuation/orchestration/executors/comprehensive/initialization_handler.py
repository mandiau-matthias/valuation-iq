"""
Initialization Handler for Comprehensive Valuation Orchestrator

Handles initialization, diagnostic logging, and cache setup.
"""

from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from src.api.schemas import ValuationRequest
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.valuation_logger import ValuationLogger

from .performance_monitor import PerformanceMonitor


class InitializationHandler:
    """Handles initialization and setup for comprehensive valuation."""

    def __init__(
        self,
        cache_manager,
        cache_service,
        multiples_calculator,
        context_manager,
        performance_monitor: PerformanceMonitor,
        logger: ValuationLogger,
    ):
        """
        Initialize the initialization handler.

        Args:
            cache_manager: Cache manager instance
            cache_service: Cache service instance
            multiples_calculator: Multiples calculator instance
            context_manager: Context manager instance
            performance_monitor: Performance monitor instance
            logger: Logger instance
        """
        self.cache_manager = cache_manager
        self.cache_service = cache_service
        self.multiples_calculator = multiples_calculator
        self.context_manager = context_manager
        self.performance_monitor = performance_monitor
        self.logger = logger

    async def initialize(
        self,
        request: ValuationRequest,
        context: Optional[Dict[str, Any]],
        overall_start_time: Decimal,
    ) -> Tuple[Dict[str, Any], str, float]:
        """
        Initialize processing context and cache service.

        Args:
            request: The valuation request
            context: Optional processing context
            overall_start_time: Overall start time for performance monitoring

        Returns:
            Tuple of (stage_timings, correlation_id, cache_init_duration):
            - stage_timings: Dictionary to track stage timings
            - correlation_id: Correlation ID for request tracking
            - cache_init_duration: Cache initialization duration
        """
        # Diagnostic logging
        self._log_diagnostic_entry(request)

        # Initialize performance monitoring
        stage_timings = {}
        correlation_id = self.context_manager.get_correlation_id(context)

        # Initialize cache service
        cache_init_duration = await self._initialize_cache_service(correlation_id, stage_timings)

        # Log entry point
        self._log_orchestrator_start(request, correlation_id)

        return stage_timings, correlation_id, cache_init_duration

    def _log_diagnostic_entry(self, request: ValuationRequest) -> None:
        """Log diagnostic entry information."""
        has_context = (
            hasattr(request, "business_context") and request.business_context is not None
        )
        self.logger.debug(
            "Orchestrator entry",
            extra={
                "use_dcf": request.use_dcf,
                "use_multiples": request.use_multiples,
                "methodology": getattr(request, "methodology", "HYBRID"),
                "business_type_id": getattr(request, "business_type_id", None),
                "has_business_context": has_context,
                "company_name": request.company_name,
            },
        )

    async def _initialize_cache_service(
        self, correlation_id: str, stage_timings: Dict[str, Any]
    ) -> Decimal:
        """
        Initialize cache service.

        Args:
            correlation_id: Correlation ID for logging
            stage_timings: Dictionary to track stage timings

        Returns:
            Cache initialization duration in seconds
        """
        cache_init_start = self.performance_monitor.start_timing()
        self.cache_service = await self.cache_manager.ensure_cache_service_initialized(
            self.cache_service, self.multiples_calculator
        )
        cache_init_duration = self.performance_monitor.record_stage_timing(
            stage_timings, "cache_initialization", cache_init_start
        )

        self.logger.debug(f"Cache initialization completed in {cache_init_duration:.3f}s")

        self.performance_monitor.log_slow_operation(
            "cache_initialization",
            cache_init_duration,
            threshold=Decimal("1.0"),
            context={"correlation_id": correlation_id},
        )

        return cache_init_duration

    def _log_orchestrator_start(self, request: ValuationRequest, correlation_id: str) -> None:
        """Log orchestrator start information."""
        self.logger.info(
            f"🎬 ORCHESTRATOR START | "
            f"use_dcf={request.use_dcf} | "
            f"use_multiples={request.use_multiples} | "
            f"methodology={getattr(request, 'methodology', 'HYBRID')} | "
            f"business_type_id={getattr(request, 'business_type_id', None)} | "
            f"has_business_context={hasattr(request, 'business_context') and request.business_context is not None}"
        )

        # DEBUG: dup of "🎬 ORCHESTRATOR START" emitted by the comprehensive orchestrator.
        self.logger.debug(
            "🚀 Processing comprehensive valuation (refactored)",
            extra={"company": request.company_name},
        )
