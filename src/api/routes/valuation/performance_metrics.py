"""
Performance Metrics for Valuation Engine

This module provides comprehensive Prometheus metrics for monitoring
the valuation engine's performance, reliability, and resource usage.

Author: Upswitch Engineering Team
Date: November 2025
Status: Production Ready
"""

from decimal import Decimal
from typing import Optional

from prometheus_client import Counter, Gauge, Histogram, Summary

from src.utils.decimal_helpers import from_decimal, to_decimal


def _decimal_buckets(*values: str) -> tuple[Decimal, ...]:
    return tuple(Decimal(value) for value in values)


SCORE_DISTRIBUTION_BUCKETS: tuple[Decimal, ...] = (
    Decimal("0.0"),
    Decimal("0.1"),
    Decimal("0.2"),
    Decimal("0.3"),
    Decimal("0.4"),
    Decimal("0.5"),
    Decimal("0.6"),
    Decimal("0.7"),
    Decimal("0.8"),
    Decimal("0.9"),
    Decimal("1.0"),
)

STEP_DURATION_BUCKETS = (
    *_decimal_buckets("0.01", "0.05", "0.1", "0.25", "0.5", "1.0"),
    *_decimal_buckets("2.5", "5.0", "10.0", "30.0"),
)

API_CALL_DURATION_BUCKETS = (
    *_decimal_buckets("0.1", "0.25", "0.5", "1.0", "2.0"),
    *_decimal_buckets("5.0", "10.0", "30.0"),
)

DATABASE_QUERY_DURATION_BUCKETS = (
    *_decimal_buckets("0.001", "0.005", "0.01", "0.025", "0.05"),
    *_decimal_buckets("0.1", "0.25", "0.5", "1.0", "2.0"),
)

# ==================== STEP EXECUTION METRICS ====================

step_duration_seconds = Histogram(
    "valuation_step_duration_seconds",
    "Step execution time in seconds",
    ["step_number", "step_name", "business_type", "status"],
    buckets=STEP_DURATION_BUCKETS,
)

step_execution_total = Counter(
    "valuation_step_execution_total",
    "Total number of step executions",
    ["step_number", "step_name", "status"],
)

step_failure_total = Counter(
    "valuation_step_failure_total",
    "Total number of step failures",
    ["step_number", "step_name", "error_type"],
)


# ==================== API CALL METRICS ====================

api_call_duration_seconds = Histogram(
    "external_api_call_duration_seconds",
    "External API call duration in seconds",
    ["api_name", "endpoint", "status"],
    buckets=API_CALL_DURATION_BUCKETS,
)

api_call_total = Counter(
    "external_api_call_total",
    "Total number of external API calls",
    ["api_name", "endpoint", "status"],
)

api_call_failures = Counter(
    "external_api_call_failures",
    "Total number of external API call failures",
    ["api_name", "endpoint", "error_type"],
)


# ==================== DATABASE METRICS ====================

database_query_duration_seconds = Histogram(
    "database_query_duration_seconds",
    "Database query execution time in seconds",
    ["query_type", "table", "status"],
    buckets=DATABASE_QUERY_DURATION_BUCKETS,
)

database_query_total = Counter(
    "database_query_total", "Total number of database queries", ["query_type", "table", "status"]
)

database_connection_pool_size = Gauge(
    "database_connection_pool_size", "Number of active database connections", []
)


# ==================== CACHE METRICS ====================

cache_hit_rate = Gauge("cache_hit_rate", "Cache hit rate percentage", ["cache_name"])

cache_operations_total = Counter(
    "cache_operations_total",
    "Total number of cache operations",
    ["cache_name", "operation", "status"],
)

cache_size_bytes = Gauge("cache_size_bytes", "Current cache size in bytes", ["cache_name"])

cache_evictions_total = Counter(
    "cache_evictions_total", "Total number of cache evictions", ["cache_name", "reason"]
)


# ==================== MEMORY METRICS ====================

memory_usage_bytes = Gauge("valuation_memory_usage_bytes", "Memory usage in bytes", ["component"])

memory_allocation_rate = Summary(
    "valuation_memory_allocation_rate_bytes", "Memory allocation rate in bytes per second", []
)


# ==================== BUSINESS METRICS ====================

valuation_calculations_in_progress = Gauge(
    "valuation_calculations_in_progress", "Number of valuations currently being calculated", []
)

valuation_confidence_score = Histogram(
    "valuation_confidence_score",
    "Distribution of valuation confidence scores",
    ["business_type", "methodology"],
    buckets=SCORE_DISTRIBUTION_BUCKETS,
)

valuation_range_spread = Histogram(
    "valuation_range_spread_percentage",
    "Distribution of valuation range spreads (high-low)",
    ["business_type"],
    buckets=(5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 75, 100),
)

data_quality_score_distribution = Histogram(
    "data_quality_score_distribution",
    "Distribution of data quality scores",
    [],
    buckets=SCORE_DISTRIBUTION_BUCKETS,
)


# ==================== CIRCUIT BREAKER METRICS ====================

circuit_breaker_state = Gauge(
    "circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half_open)",
    ["circuit_name"],
)

circuit_breaker_trips_total = Counter(
    "circuit_breaker_trips_total", "Total number of circuit breaker trips", ["circuit_name"]
)

circuit_breaker_rejected_calls_total = Counter(
    "circuit_breaker_rejected_calls_total",
    "Total number of rejected calls due to open circuit",
    ["circuit_name"],
)


# ==================== INPUT VALIDATION METRICS ====================

validation_errors_total = Counter(
    "validation_errors_total", "Total number of validation errors", ["validation_type", "field"]
)

business_logic_validation_failures = Counter(
    "business_logic_validation_failures",
    "Total number of business logic validation failures",
    ["failure_type"],
)


# ==================== HELPER FUNCTIONS ====================


def track_step_execution(
    step_number: int,
    step_name: str,
    duration: Decimal,
    business_type: Optional[str] = None,
    status: str = "completed",
):
    """
    Track step execution metrics.

    Args:
        step_number: Step number
        step_name: Step name
        duration: Execution duration in seconds
        business_type: Business type category
        status: Execution status
    """
    business_type = business_type or "unknown"
    step_duration_seconds.labels(
        step_number=str(step_number),
        step_name=step_name,
        business_type=business_type,
        status=status,
    ).observe(duration)

    step_execution_total.labels(
        step_number=str(step_number), step_name=step_name, status=status
    ).inc()


def track_api_call(api_name: str, endpoint: str, duration: Decimal, status: str = "success"):
    """
    Track external API call metrics.

    Args:
        api_name: Name of the API (e.g., 'FMP', 'Database')
        endpoint: API endpoint
        duration: Call duration in seconds
        status: Call status
    """
    api_call_duration_seconds.labels(api_name=api_name, endpoint=endpoint, status=status).observe(
        duration
    )

    api_call_total.labels(api_name=api_name, endpoint=endpoint, status=status).inc()


def track_cache_operation(cache_name: str, operation: str, hit: bool):
    """
    Track cache operation metrics.

    Args:
        cache_name: Name of the cache
        operation: Operation type ('get', 'set', 'delete')
        hit: Whether the operation was a cache hit
    """
    status = "hit" if hit else "miss"
    cache_operations_total.labels(cache_name=cache_name, operation=operation, status=status).inc()


# ==================== EXPORT ====================

__all__ = [
    "step_duration_seconds",
    "step_execution_total",
    "step_failure_total",
    "api_call_duration_seconds",
    "api_call_total",
    "api_call_failures",
    "database_query_duration_seconds",
    "database_query_total",
    "database_connection_pool_size",
    "cache_hit_rate",
    "cache_operations_total",
    "cache_size_bytes",
    "cache_evictions_total",
    "memory_usage_bytes",
    "memory_allocation_rate",
    "valuation_calculations_in_progress",
    "valuation_confidence_score",
    "valuation_range_spread",
    "data_quality_score_distribution",
    "circuit_breaker_state",
    "circuit_breaker_trips_total",
    "circuit_breaker_rejected_calls_total",
    "validation_errors_total",
    "business_logic_validation_failures",
    "track_step_execution",
    "track_api_call",
    "track_cache_operation",
]
