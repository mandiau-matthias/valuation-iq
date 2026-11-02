"""
Monitoring and Observability Package

Comprehensive monitoring system for the valuation engine including:
- Performance metrics collection
- Health checks and diagnostics
- System monitoring
- Alerting and notifications

ARCHITECTURE:
- Performance tracking for every service and calculation
- Health checks for all system components
- Metrics collection and aggregation
- Alerting based on thresholds
- Diagnostic tools for troubleshooting

USAGE:
    Import HealthChecker and PerformanceTracker from this package. Use HealthChecker to probe
    components, PerformanceTracker for timed operations, and (when available) a metrics collector
    for aggregated system metrics.
"""

from .health_checker import HealthChecker, HealthStatus, ComponentHealth
from src.services.ml.evaluation.performance_tracker import PerformanceTracker
# from .metrics_collector import MetricsCollector, SystemMetrics  # Module doesn't exist
# from .diagnostics import DiagnosticsEngine, DiagnosticReport  # Module doesn't exist

__all__ = [
    'HealthChecker',
    'HealthStatus', 
    'ComponentHealth',
    'PerformanceTracker'
]
