"""
Correlation Context Management

This module provides thread-safe correlation ID propagation using contextvars.
The correlation ID flows through the entire request lifecycle automatically,
enabling end-to-end request tracing.

Author: Upswitch Engineering Team
Date: November 2025
Status: Production Ready
"""

import uuid
from contextvars import ContextVar
from typing import Optional

# Context variable for correlation ID
# This is automatically copied to child tasks in async contexts
_correlation_id_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def set_correlation_id(correlation_id: str) -> None:
    """
    Set the correlation ID for the current context.

    This should be called at the API boundary when a request arrives.
    The correlation ID will automatically propagate to all child tasks
    and function calls within the async context.

    Args:
        correlation_id: Unique correlation ID for the request
    """
    _correlation_id_var.set(correlation_id)


def get_correlation_id() -> Optional[str]:
    """
    Get the correlation ID for the current context.

    Returns:
        Correlation ID if set, None otherwise
    """
    return _correlation_id_var.get()


def get_or_create_correlation_id() -> str:
    """
    Get the correlation ID for the current context, or create a new one if not set.

    Returns:
        Correlation ID (existing or newly created)
    """
    correlation_id = _correlation_id_var.get()
    if correlation_id is None:
        correlation_id = generate_correlation_id()
        _correlation_id_var.set(correlation_id)
    return correlation_id


def generate_correlation_id() -> str:
    """
    Generate a new correlation ID.

    Returns:
        UUID-based correlation ID
    """
    return str(uuid.uuid4())


def clear_correlation_id() -> None:
    """
    Clear the correlation ID for the current context.

    This is typically called at the end of request processing
    or in test cleanup.
    """
    _correlation_id_var.set(None)


def with_correlation_id(correlation_id: Optional[str] = None):
    """
    Context manager for setting correlation ID within a scope.

    Args:
        correlation_id: Correlation ID to set (generates new one if None)

    Usage:
        with with_correlation_id("my-request-id"):
            # All code here has access to correlation_id
            logger.info("Processing request")

        with with_correlation_id():  # Auto-generates ID
            # All code here has access to auto-generated correlation_id
            process_request()
    """

    class CorrelationContextManager:
        def __init__(self, corr_id: Optional[str]):
            self.correlation_id = corr_id or generate_correlation_id()
            self.token = None

        def __enter__(self):
            self.token = _correlation_id_var.set(self.correlation_id)
            return self.correlation_id

        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.token is not None:
                _correlation_id_var.reset(self.token)
            return False

    return CorrelationContextManager(correlation_id)


# ==================== EXPORT ====================

__all__ = [
    "set_correlation_id",
    "get_correlation_id",
    "get_or_create_correlation_id",
    "generate_correlation_id",
    "clear_correlation_id",
    "with_correlation_id",
]
