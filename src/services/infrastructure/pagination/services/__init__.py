"""
Pagination Services Package

BANK-GRADE: SRP-compliant pagination quality services

This package contains specialized services for pagination quality:
- PaginationErrorHandler: Error handling ONLY
- PaginationMetricsService: Performance metrics ONLY

Each service has a single, focused responsibility following the
Single Responsibility Principle (SOLID-S).
"""

from .pagination_error_handler import (
    PaginationErrorHandler,
    PaginationError,
    PaginationErrorType,
    ContentTooLargeError,
    InvalidContentError,
    ParsingError,
    RenderingError,
    OverflowError,
    OrphanViolationError,
)
from .pagination_metrics_service import (
    PaginationMetricsService,
    PaginationMetrics,
)

__all__ = [
    'PaginationErrorHandler',
    'PaginationError',
    'PaginationErrorType',
    'ContentTooLargeError',
    'InvalidContentError',
    'ParsingError',
    'RenderingError',
    'OverflowError',
    'OrphanViolationError',
    'PaginationMetricsService',
    'PaginationMetrics',
]
