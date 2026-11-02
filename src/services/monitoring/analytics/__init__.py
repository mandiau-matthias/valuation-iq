"""
Analytics Services Package

This package provides comprehensive analytics and metrics collection services
for the Upswitch valuation system.
"""

from .conversation_metrics import (
    ConversationMetricsCollector,
    ConversationMetrics,
    ABTestConfig,
    ABTestResult,
    VariantType,
    DropOffReason
)

__all__ = [
    "ConversationMetricsCollector",
    "ConversationMetrics",
    "ABTestConfig", 
    "ABTestResult",
    "VariantType",
    "DropOffReason"
]
