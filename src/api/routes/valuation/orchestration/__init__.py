"""
Orchestration Module

Specialized modules for valuation orchestration, including executors, builders,
handlers, and utilities. This module extracts complex orchestration logic from
the main ValuationOrchestrator class.

Structure:
- executors/: Methodology execution (DCF, Multiples, Hybrid)
- builders/: Response and transparency data construction
- handlers/: Error handling and performance monitoring
- utils/: Cache management, context management, adjustment helpers
"""

from .builders import ResponseBuilder, TransparencyBuilder, ValidationBuilder
from .executors import DCFExecutor, HybridExecutor, MethodologyExecutor, MultiplesExecutor
from .handlers import ErrorHandler, PerformanceHandler
from .utils import AdjustmentHelpers, CacheManager, ContextManager

__all__ = [
    # Executors
    "MethodologyExecutor",
    "DCFExecutor",
    "MultiplesExecutor",
    "HybridExecutor",
    # Builders
    "ResponseBuilder",
    "TransparencyBuilder",
    "ValidationBuilder",
    # Handlers
    "ErrorHandler",
    "PerformanceHandler",
    # Utils
    "CacheManager",
    "ContextManager",
    "AdjustmentHelpers",
]
