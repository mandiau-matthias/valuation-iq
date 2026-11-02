"""
Orchestration Monitor

This module handles performance monitoring, service health checks,
timeout management, and error recovery for valuation orchestration.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from src.utils.logging import get_logger
from .orchestration.orchestrator_types import ProcessingMetrics, ValuationContext, ServiceDependency
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal

logger = get_logger(__name__)


class OrchestrationMonitor:
    """
    Monitoring service for valuation orchestration

    Handles:
    - Performance monitoring
    - Service health checks
    - Timeout management
    - Error recovery
    """

    def __init__(self):
        """Initialize the orchestration monitor"""
        self.logger = logger
        self.processing_metrics: Dict[str, ProcessingMetrics] = {}
        self.service_health: Dict[str, bool] = {}
        self.error_counts: Dict[str, int] = {}

        self.logger.info("OrchestrationMonitor initialized")

    def start_monitoring(self, context: ValuationContext) -> ProcessingMetrics:
        """
        Start monitoring a valuation process

        Args:
            context: Valuation context

        Returns:
            ProcessingMetrics object
        """
        metrics = ProcessingMetrics(start_time=datetime.utcnow())
        self.processing_metrics[context.request_id] = metrics

        self.logger.info(
            "Started monitoring",
            request_id=context.request_id
        )

        return metrics

    def stop_monitoring(self, context: ValuationContext) -> ProcessingMetrics:
        """
        Stop monitoring and finalize metrics

        Args:
            context: Valuation context

        Returns:
            Final ProcessingMetrics
        """
        metrics = self.processing_metrics.get(context.request_id)
        if metrics:
            metrics.end_time = datetime.utcnow()
            metrics.calculate_processing_time()

            self.logger.info(
                "Stopped monitoring",
                request_id=context.request_id,
                processing_time=metrics.processing_time
            )

        return metrics

    def record_service_call(
        self,
        context: ValuationContext,
        service_name: str,
        duration: Decimal,
        success: bool
    ):
        """Record a service call"""
        metrics = self.processing_metrics.get(context.request_id)
        if metrics:
            metrics.total_api_calls += 1

            if not success:
                self.error_counts[service_name] = self.error_counts.get(service_name, 0) + 1

        self.logger.info(
            "Service call recorded",
            service=service_name,
            duration=duration,
            success=success
        )

    def check_service_health(self, service_name: str) -> bool:
        """
        Check service health status

        Args:
            service_name: Name of the service

        Returns:
            True if service is healthy
        """
        # Check error rate
        error_count = self.error_counts.get(service_name, 0)
        if error_count > 5:  # Threshold
            self.service_health[service_name] = False
            self.logger.warning(f"Service unhealthy: {service_name}")
            return False

        self.service_health[service_name] = True
        return True

    def get_performance_metrics(self, request_id: str) -> Optional[ProcessingMetrics]:
        """Get performance metrics for a request"""
        return self.processing_metrics.get(request_id)

    def get_service_health_status(self) -> Dict[str, bool]:
        """Get health status of all services"""
        return self.service_health.copy()

    def reset_error_counts(self):
        """Reset error counts"""
        self.error_counts.clear()
        self.logger.info("Error counts reset")

    def cleanup_old_metrics(self, max_age_hours: int = 24):
        """Clean up old metrics"""
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)

        to_remove = []
        for request_id, metrics in self.processing_metrics.items():
            if metrics.start_time < cutoff_time:
                to_remove.append(request_id)

        for request_id in to_remove:
            del self.processing_metrics[request_id]

        if to_remove:
            self.logger.info(f"Cleaned up {len(to_remove)} old metrics")
