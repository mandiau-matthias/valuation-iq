"""
Metrics Collector for Report Generation

Tracks success/failure rates, latency, error types, and resource usage
for comprehensive observability of the twin endpoint system.

BANK-GRADE DESIGN:
- Track success/failure rates per report type
- Measure latency (p50, p95, p99)
- Track error types and frequencies
- Monitor resource usage
- Export metrics in Prometheus format
"""

import time
from threading import Lock
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum

MetricsSnapshot = dict[str, str | int | float | dict[str, int]]


class MetricType(Enum):
    """Types of metrics."""

    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    CIRCUIT_BREAKER_OPEN = "circuit_breaker_open"
    FALLBACK_USED = "fallback_used"
    RETRY = "retry"


@dataclass
class ReportMetrics:
    """Metrics for a single report type."""

    report_type: str
    total_requests: int = 0
    successes: int = 0
    failures: int = 0
    timeouts: int = 0
    circuit_breaker_opens: int = 0
    fallbacks_used: int = 0
    retries: int = 0
    latency_samples: deque[float] = field(default_factory=lambda: deque(maxlen=1000))
    error_counts: defaultdict[str, int] = field(default_factory=lambda: defaultdict(int))

    def record_success(self, latency: float) -> None:
        """Record successful generation."""
        self.total_requests += 1
        self.successes += 1
        self.latency_samples.append(latency)

    def record_failure(self, error_type: str, latency: float) -> None:
        """Record failed generation."""
        self.total_requests += 1
        self.failures += 1
        self.error_counts[error_type] += 1
        self.latency_samples.append(latency)

    def record_timeout(self) -> None:
        """Record timeout."""
        self.timeouts += 1

    def record_circuit_breaker_open(self) -> None:
        """Record circuit breaker open."""
        self.circuit_breaker_opens += 1

    def record_fallback(self) -> None:
        """Record fallback usage."""
        self.fallbacks_used += 1

    def record_retry(self) -> None:
        """Record retry attempt."""
        self.retries += 1

    def get_latency_percentiles(self) -> dict[str, float]:
        """Calculate latency percentiles."""
        if not self.latency_samples:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0}

        sorted_samples = sorted(self.latency_samples)
        n = len(sorted_samples)

        return {
            "p50": sorted_samples[int(n * 0.50)] if n > 0 else 0.0,
            "p95": sorted_samples[int(n * 0.95)] if n > 1 else sorted_samples[-1],
            "p99": sorted_samples[int(n * 0.99)] if n > 1 else sorted_samples[-1],
        }

    def get_success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_requests == 0:
            return 0.0
        return self.successes / self.total_requests

    def to_dict(self) -> MetricsSnapshot:
        """Convert metrics to dictionary."""
        percentiles = self.get_latency_percentiles()
        return {
            "report_type": self.report_type,
            "total_requests": self.total_requests,
            "successes": self.successes,
            "failures": self.failures,
            "timeouts": self.timeouts,
            "circuit_breaker_opens": self.circuit_breaker_opens,
            "fallbacks_used": self.fallbacks_used,
            "retries": self.retries,
            "success_rate": self.get_success_rate(),
            "latency_p50": percentiles["p50"],
            "latency_p95": percentiles["p95"],
            "latency_p99": percentiles["p99"],
            "error_counts": dict(self.error_counts),
        }


class MetricsCollector:
    """
    Collects metrics for report generation.

    BANK-GRADE IMPLEMENTATION:
    - Thread-safe operations
    - Per-report-type metrics
    - Latency percentiles
    - Error categorization
    - Prometheus-compatible export
    """

    def __init__(self) -> None:
        """Initialize metrics collector."""
        self._metrics: dict[str, ReportMetrics] = {}
        self._lock = Lock()

    def get_metrics(self, report_type: str) -> ReportMetrics:
        """
        Get or create metrics for report type.

        Args:
            report_type: Type of report ("Accountant View" or "Info Tab")

        Returns:
            ReportMetrics instance
        """
        with self._lock:
            if report_type not in self._metrics:
                self._metrics[report_type] = ReportMetrics(report_type=report_type)
            return self._metrics[report_type]

    def record_success(self, report_type: str, latency: float) -> None:
        """
        Record successful report generation.

        Args:
            report_type: Type of report
            latency: Generation latency in seconds
        """
        with self._lock:
            metrics = self._metrics.setdefault(
                report_type, ReportMetrics(report_type=report_type)
            )
            metrics.record_success(latency)

    def record_failure(self, report_type: str, error_type: str, latency: float) -> None:
        """
        Record failed report generation.

        Args:
            report_type: Type of report
            error_type: Type of error
            latency: Generation latency in seconds
        """
        with self._lock:
            metrics = self._metrics.setdefault(
                report_type, ReportMetrics(report_type=report_type)
            )
            metrics.record_failure(error_type, latency)

    def record_timeout(self, report_type: str) -> None:
        """Record timeout for report type."""
        with self._lock:
            metrics = self._metrics.setdefault(
                report_type, ReportMetrics(report_type=report_type)
            )
            metrics.record_timeout()

    def record_circuit_breaker_open(self, report_type: str) -> None:
        """Record circuit breaker open for report type."""
        with self._lock:
            metrics = self._metrics.setdefault(
                report_type, ReportMetrics(report_type=report_type)
            )
            metrics.record_circuit_breaker_open()

    def record_fallback(self, report_type: str) -> None:
        """Record fallback usage for report type."""
        with self._lock:
            metrics = self._metrics.setdefault(
                report_type, ReportMetrics(report_type=report_type)
            )
            metrics.record_fallback()

    def record_retry(self, report_type: str) -> None:
        """Record retry attempt for report type."""
        with self._lock:
            metrics = self._metrics.setdefault(
                report_type, ReportMetrics(report_type=report_type)
            )
            metrics.record_retry()

    def get_all_metrics(self) -> dict[str, MetricsSnapshot]:
        """Get all metrics as dictionary."""
        with self._lock:
            return {
                report_type: metrics.to_dict() for report_type, metrics in self._metrics.items()
            }

    def export_prometheus(self) -> str:
        """
        Export metrics in Prometheus format.

        Returns:
            Prometheus-formatted metrics string
        """
        lines: list[str] = []

        with self._lock:
            for report_type, metrics in self._metrics.items():
                # Normalize report type for Prometheus labels
                label = report_type.lower().replace(" ", "_")

                # Success rate
                lines.append(
                    f'report_generation_success_rate{{report_type="{label}"}} {metrics.get_success_rate():.4f}'
                )

                # Total requests
                lines.append(
                    f'report_generation_total_requests{{report_type="{label}"}} {metrics.total_requests}'
                )

                # Successes
                lines.append(
                    f'report_generation_success_total{{report_type="{label}"}} {metrics.successes}'
                )

                # Failures
                lines.append(
                    f'report_generation_failure_total{{report_type="{label}"}} {metrics.failures}'
                )

                # Timeouts
                lines.append(
                    f'report_generation_timeout_total{{report_type="{label}"}} {metrics.timeouts}'
                )

                # Circuit breaker opens
                lines.append(
                    f'report_generation_circuit_breaker_open_total{{report_type="{label}"}} {metrics.circuit_breaker_opens}'
                )

                # Fallbacks
                lines.append(
                    f'report_generation_fallback_total{{report_type="{label}"}} {metrics.fallbacks_used}'
                )

                # Retries
                lines.append(
                    f'report_generation_retry_total{{report_type="{label}"}} {metrics.retries}'
                )

                # Latency percentiles
                percentiles = metrics.get_latency_percentiles()
                lines.append(
                    f'report_generation_latency_seconds{{report_type="{label}",percentile="p50"}} {percentiles["p50"]:.4f}'
                )
                lines.append(
                    f'report_generation_latency_seconds{{report_type="{label}",percentile="p95"}} {percentiles["p95"]:.4f}'
                )
                lines.append(
                    f'report_generation_latency_seconds{{report_type="{label}",percentile="p99"}} {percentiles["p99"]:.4f}'
                )

                # Error counts
                for error_type, count in metrics.error_counts.items():
                    error_label = error_type.lower().replace(" ", "_")
                    lines.append(
                        f'report_generation_error_total{{report_type="{label}",error_type="{error_label}"}} {count}'
                    )

        return "\n".join(lines)

    def reset(self) -> None:
        """Reset all metrics (for testing)."""
        with self._lock:
            self._metrics.clear()
