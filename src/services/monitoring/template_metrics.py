"""
Template Service Monitoring and Metrics

BANK-GRADE: Production monitoring for template service health
Tracks template rendering performance, failures, and health status
"""

import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
import logging
from typing import Optional, TypedDict

logger = logging.getLogger(__name__)

TemplateSummaryValue = int | float | str | None | dict[str, int]
TemplateSummary = dict[str, TemplateSummaryValue]


class TemplateAlert(TypedDict):
    severity: str
    type: str
    message: str
    metric: str
    value: int | float
    threshold: int | float


class TemplateAlertState(TypedDict):
    has_alerts: bool
    alerts: list[TemplateAlert]


@dataclass
class TemplateMetrics:
    """
    Metrics tracker for template service operations

    Tracks:
    - Render success/failure rates
    - Performance (render duration)
    - Fallback usage
    - Template discovery issues
    """

    # Success metrics
    render_success_count: int = 0
    render_failure_count: int = 0
    fallback_used_count: int = 0

    # Performance metrics
    total_render_duration_ms: float = 0.0
    render_count: int = 0
    slowest_render_ms: float = 0.0
    fastest_render_ms: float = float("inf")

    # Discovery metrics
    template_not_found_count: int = 0
    directory_not_found_count: int = 0

    # Health metrics
    template_health_checks: int = 0
    template_health_failures: int = 0

    # Error tracking
    error_types: dict[str, int] = field(default_factory=dict)

    # Timestamps
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    last_health_check: Optional[datetime] = None

    def record_success(self, duration_ms: float, template_name: str) -> None:
        """Record successful template render"""
        self.render_success_count += 1
        self.render_count += 1
        self.total_render_duration_ms += duration_ms
        self.slowest_render_ms = max(self.slowest_render_ms, duration_ms)
        self.fastest_render_ms = min(self.fastest_render_ms, duration_ms)
        self.last_success = datetime.utcnow()

        logger.debug(
            f"✅ [METRICS] Template render success: {template_name}",
            extra={
                "template": template_name,
                "duration_ms": duration_ms,
                "total_successes": self.render_success_count,
            },
        )

    def record_failure(self, error_type: str, template_name: str) -> None:
        """Record failed template render"""
        self.render_failure_count += 1
        self.render_count += 1
        self.error_types[error_type] = self.error_types.get(error_type, 0) + 1
        self.last_failure = datetime.utcnow()

        logger.warning(
            f"❌ [METRICS] Template render failure: {template_name}",
            extra={
                "template": template_name,
                "error_type": error_type,
                "total_failures": self.render_failure_count,
                "failure_rate": self.get_failure_rate(),
            },
        )

    def record_fallback_used(self, template_name: str) -> None:
        """Record fallback HTML generation used"""
        self.fallback_used_count += 1

        logger.info(
            f"⚠️ [METRICS] Fallback HTML used: {template_name}",
            extra={
                "template": template_name,
                "total_fallbacks": self.fallback_used_count,
                "fallback_rate": self.get_fallback_rate(),
            },
        )

    def record_template_not_found(self, template_name: str) -> None:
        """Record template file not found"""
        self.template_not_found_count += 1

        logger.error(
            f"❌ [METRICS] Template not found: {template_name}",
            extra={
                "template": template_name,
                "total_not_found": self.template_not_found_count,
                "severity": "HIGH",
            },
        )

    def record_directory_not_found(self, directory_path: str) -> None:
        """Record template directory not found"""
        self.directory_not_found_count += 1

        logger.error(
            f"❌ [METRICS] Template directory not found: {directory_path}",
            extra={
                "directory": directory_path,
                "total_dir_not_found": self.directory_not_found_count,
                "severity": "CRITICAL",
            },
        )

    def record_health_check(self, success: bool, health_data: Mapping[str, object]) -> None:
        """Record template health check result"""
        self.template_health_checks += 1
        if not success:
            self.template_health_failures += 1
        self.last_health_check = datetime.utcnow()

        logger.info(
            f"{'✅' if success else '❌'} [METRICS] Template health check",
            extra={
                "health_status": "PASS" if success else "FAIL",
                "health_data": health_data,
                "total_checks": self.template_health_checks,
                "total_failures": self.template_health_failures,
            },
        )

    def get_success_rate(self) -> float:
        """Calculate template render success rate"""
        if self.render_count == 0:
            return 1.0
        return self.render_success_count / self.render_count

    def get_failure_rate(self) -> float:
        """Calculate template render failure rate"""
        if self.render_count == 0:
            return 0.0
        return self.render_failure_count / self.render_count

    def get_fallback_rate(self) -> float:
        """Calculate fallback usage rate"""
        if self.render_count == 0:
            return 0.0
        return self.fallback_used_count / self.render_count

    def get_avg_render_duration_ms(self) -> float:
        """Calculate average render duration"""
        if self.render_count == 0:
            return 0.0
        return self.total_render_duration_ms / self.render_count

    def get_summary(self) -> TemplateSummary:
        """Get comprehensive metrics summary"""
        return {
            # Success metrics
            "render_success_count": self.render_success_count,
            "render_failure_count": self.render_failure_count,
            "render_total_count": self.render_count,
            "success_rate": round(self.get_success_rate() * 100, 2),
            "failure_rate": round(self.get_failure_rate() * 100, 2),
            # Fallback metrics
            "fallback_used_count": self.fallback_used_count,
            "fallback_rate": round(self.get_fallback_rate() * 100, 2),
            # Performance metrics
            "avg_render_duration_ms": round(self.get_avg_render_duration_ms(), 2),
            "slowest_render_ms": (
                round(self.slowest_render_ms, 2) if self.slowest_render_ms > 0 else None
            ),
            "fastest_render_ms": (
                round(self.fastest_render_ms, 2) if self.fastest_render_ms < float("inf") else None
            ),
            # Discovery metrics
            "template_not_found_count": self.template_not_found_count,
            "directory_not_found_count": self.directory_not_found_count,
            # Health metrics
            "health_checks_total": self.template_health_checks,
            "health_check_failures": self.template_health_failures,
            # Error tracking
            "error_types": dict(self.error_types),
            # Timestamps
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "last_failure": self.last_failure.isoformat() if self.last_failure else None,
            "last_health_check": (
                self.last_health_check.isoformat() if self.last_health_check else None
            ),
        }

    def get_prometheus_metrics(self) -> str:
        """
        Export metrics in Prometheus format

        Returns:
            Prometheus-formatted metrics string
        """
        metrics = []

        # Success/failure counters
        metrics.append(f"template_render_success_total {self.render_success_count}")
        metrics.append(f"template_render_failure_total {self.render_failure_count}")
        metrics.append(f"template_fallback_used_total {self.fallback_used_count}")

        # Rates (as gauges)
        metrics.append(f"template_render_success_rate {self.get_success_rate()}")
        metrics.append(f"template_render_failure_rate {self.get_failure_rate()}")
        metrics.append(f"template_fallback_rate {self.get_fallback_rate()}")

        # Performance metrics
        metrics.append(f"template_render_duration_ms_avg {self.get_avg_render_duration_ms()}")
        if self.slowest_render_ms > 0:
            metrics.append(f"template_render_duration_ms_max {self.slowest_render_ms}")
        if self.fastest_render_ms < float("inf"):
            metrics.append(f"template_render_duration_ms_min {self.fastest_render_ms}")

        # Discovery issues
        metrics.append(f"template_not_found_total {self.template_not_found_count}")
        metrics.append(f"template_directory_not_found_total {self.directory_not_found_count}")

        # Health checks
        metrics.append(f"template_health_checks_total {self.template_health_checks}")
        metrics.append(f"template_health_check_failures_total {self.template_health_failures}")

        # Error types (as labeled metrics)
        for error_type, count in self.error_types.items():
            metrics.append(f'template_errors_total{{error_type="{error_type}"}} {count}')

        return "\n".join(metrics)

    def should_alert(self) -> TemplateAlertState:
        """
        Check if any metrics warrant alerts

        Returns:
            Dictionary with alert status and details
        """
        alerts: TemplateAlertState = {"has_alerts": False, "alerts": []}

        # Alert if failure rate > 5%
        if self.render_count > 10 and self.get_failure_rate() > 0.05:
            alerts["has_alerts"] = True
            alerts["alerts"].append(
                {
                    "severity": "HIGH",
                    "type": "high_failure_rate",
                    "message": f"Template render failure rate {self.get_failure_rate()*100:.1f}% exceeds 5% threshold",
                    "metric": "failure_rate",
                    "value": self.get_failure_rate(),
                    "threshold": 0.05,
                }
            )

        # Alert if fallback rate > 10%
        if self.render_count > 10 and self.get_fallback_rate() > 0.10:
            alerts["has_alerts"] = True
            alerts["alerts"].append(
                {
                    "severity": "MEDIUM",
                    "type": "high_fallback_rate",
                    "message": f"Fallback usage rate {self.get_fallback_rate()*100:.1f}% exceeds 10% threshold",
                    "metric": "fallback_rate",
                    "value": self.get_fallback_rate(),
                    "threshold": 0.10,
                }
            )

        # Alert if average render time > 2000ms
        avg_duration = self.get_avg_render_duration_ms()
        if self.render_count > 5 and avg_duration > 2000:
            alerts["has_alerts"] = True
            alerts["alerts"].append(
                {
                    "severity": "MEDIUM",
                    "type": "slow_render",
                    "message": f"Average render time {avg_duration:.0f}ms exceeds 2000ms threshold",
                    "metric": "avg_render_duration_ms",
                    "value": avg_duration,
                    "threshold": 2000,
                }
            )

        # Alert if directory not found
        if self.directory_not_found_count > 0:
            alerts["has_alerts"] = True
            alerts["alerts"].append(
                {
                    "severity": "CRITICAL",
                    "type": "directory_not_found",
                    "message": f"Template directory not found {self.directory_not_found_count} time(s)",
                    "metric": "directory_not_found_count",
                    "value": self.directory_not_found_count,
                    "threshold": 0,
                }
            )

        return alerts


# Global metrics instance
_global_metrics = TemplateMetrics()


def get_global_metrics() -> TemplateMetrics:
    """Get global template metrics instance"""
    return _global_metrics


def record_template_render(
    template_name: str,
    success: bool,
    duration_ms: Optional[float] = None,
    error_type: Optional[str] = None,
) -> None:
    """
    Convenience function to record template render

    Args:
        template_name: Name of template rendered
        success: Whether render succeeded
        duration_ms: Render duration in milliseconds (for successes)
        error_type: Type of error (for failures)
    """
    metrics = get_global_metrics()

    if success and duration_ms is not None:
        metrics.record_success(duration_ms, template_name)
    elif not success and error_type is not None:
        metrics.record_failure(error_type, template_name)


def get_metrics_summary() -> TemplateSummary:
    """Get summary of all template metrics"""
    return get_global_metrics().get_summary()


def export_prometheus() -> str:
    """Export metrics in Prometheus format"""
    return get_global_metrics().get_prometheus_metrics()


def check_alerts() -> TemplateAlertState:
    """Check for any active alerts"""
    return get_global_metrics().should_alert()
