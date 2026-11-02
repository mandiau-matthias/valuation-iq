"""
Report Generation Module - Rocket-Grade Twin Endpoint Architecture

This module provides a robust, bank-grade implementation for generating
dual HTML report streams (Accountant View and Info Tab) with independent
failure isolation, circuit breakers, retry mechanisms, and comprehensive
observability.

ARCHITECTURE:
- Strategy Pattern: Each report type has its own generation strategy
- Circuit Breaker: Prevents cascading failures
- Retry Mechanism: Handles transient failures
- Timeout Management: Individual timeouts per report type
- Graceful Degradation: Fallback content when generation fails
- Comprehensive Observability: Metrics, tracing, audit trails

DESIGN PRINCIPLES:
- Independent Failure Isolation: Each report stream fails independently
- Single Responsibility: Each strategy handles one report type
- Open/Closed: Easy to extend with new report types
- Dependency Inversion: Depend on abstractions, not concretions
"""

from src.services.infrastructure.report_generation.strategies.base_report_strategy import (
    ReportStrategy,
    BaseReportStrategy,
)
from src.services.infrastructure.report_generation.strategies.accountant_view_strategy import (
    AccountantViewStrategy,
)
from src.services.infrastructure.report_generation.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerManager,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
)
from src.services.infrastructure.report_generation.retry_handler import (
    RetryHandler,
    RetryConfig,
)
from src.services.infrastructure.report_generation.fallback_generator import (
    FallbackGenerator,
)
from src.services.infrastructure.report_generation.shared_transformer import (
    SharedDataTransformer,
    TransformationCache,
)
from src.services.infrastructure.report_generation.metrics_collector import (
    MetricsCollector,
)
from src.services.infrastructure.report_generation.health_checker import (
    HealthChecker,
    HealthStatus,
)
from src.services.infrastructure.report_generation.config import (
    ReportGenerationConfig,
)
from src.services.infrastructure.report_generation.parallel_report_orchestrator import (
    ParallelReportOrchestrator,
)

__all__ = [
    # Strategies
    "ReportStrategy",
    "BaseReportStrategy",
    "AccountantViewStrategy",
    # Circuit Breaker
    "CircuitBreaker",
    "CircuitBreakerManager",
    "CircuitBreakerConfig",
    "CircuitBreakerOpenError",
    # Retry Handler
    "RetryHandler",
    "RetryConfig",
    # Fallback Generator
    "FallbackGenerator",
    # Shared Transformer
    "SharedDataTransformer",
    "TransformationCache",
    # Metrics Collector
    "MetricsCollector",
    # Health Checker
    "HealthChecker",
    "HealthStatus",
    # Parallel Orchestrator
    "ParallelReportOrchestrator",
    # Config
    "ReportGenerationConfig",
]

