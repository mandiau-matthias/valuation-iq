"""
Error Context Capture

Comprehensive error context capture system that collects detailed information
about the system state when an error occurs.

ARCHITECTURE:
- Full stack trace with local variables
- Input data snapshot (sanitized if needed)
- Service state at error time
- Calculation step identifier
- Suggested recovery actions
- Performance metrics at error time
- User context and session information

FEATURES:
- Automatic context capture on error
- Sanitization of sensitive data
- Performance impact tracking
- Audit trail integration
- Recovery strategy suggestions
"""

import inspect
import json
import sys
import threading
import traceback
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from src.utils.log_sanitizer import sanitize_log_value
from src.utils.logging_context import get_current_context

# Thread-local storage for error context
_error_context_var: ContextVar[Optional["ErrorContext"]] = ContextVar("error_context", default=None)


@dataclass
class ErrorContext:
    """
    Comprehensive error context with system state and metadata.

    Captures:
    - Full stack trace with local variables
    - Input data snapshot (sanitized)
    - Service state at error time
    - Calculation step identifier
    - Performance metrics
    - User context and session information
    """

    # Error identification
    error_id: str
    error_type: str
    error_message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Stack trace information
    stack_trace: str = ""
    local_variables: Dict[str, Any] = field(default_factory=dict)
    global_variables: Dict[str, Any] = field(default_factory=dict)

    # System state
    service_state: Dict[str, Any] = field(default_factory=dict)
    calculation_step: Optional[str] = None
    request_context: Dict[str, Any] = field(default_factory=dict)

    # Performance metrics
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    memory_usage: Optional[Decimal] = None
    cpu_usage: Optional[Decimal] = None

    # User context
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None

    # Recovery information
    recovery_suggestions: List[str] = field(default_factory=list)
    is_retryable: bool = False
    retry_count: int = 0

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert error context to dictionary for logging"""
        return {
            "error_id": self.error_id,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat(),
            "stack_trace": self.stack_trace,
            "local_variables": self._sanitize_variables(self.local_variables),
            "global_variables": self._sanitize_variables(self.global_variables),
            "service_state": sanitize_log_value(self.service_state),
            "calculation_step": self.calculation_step,
            "request_context": sanitize_log_value(self.request_context),
            "performance_metrics": self.performance_metrics,
            "memory_usage": self.memory_usage,
            "cpu_usage": self.cpu_usage,
            "user_id": self.user_id,
            "session_id": (
                sanitize_log_value(self.session_id, key="session_id") if self.session_id else None
            ),
            "request_id": self.request_id,
            "recovery_suggestions": self.recovery_suggestions,
            "is_retryable": self.is_retryable,
            "retry_count": self.retry_count,
            "metadata": sanitize_log_value(self.metadata),
        }

    def _sanitize_variables(self, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize variables to remove sensitive information"""
        if not isinstance(variables, dict):
            return {}
        sanitized = sanitize_log_value(variables)
        return sanitized if isinstance(sanitized, dict) else {}


class ErrorContextCapture:
    """
    Automatic error context capture system.

    Features:
    - Automatic context capture on exception
    - Local variable inspection
    - Performance metrics collection
    - Service state snapshot
    - Recovery strategy suggestions
    """

    def __init__(self):
        self._capture_enabled = True

    def capture_context(
        self,
        exception: Exception,
        additional_context: Optional[Dict[str, Any]] = None,
        capture_locals: bool = True,
        capture_globals: bool = False,
    ) -> ErrorContext:
        """
        Capture comprehensive error context.

        Args:
            exception: The exception that occurred
            additional_context: Additional context to include
            capture_locals: Whether to capture local variables
            capture_globals: Whether to capture global variables

        Returns:
            ErrorContext with comprehensive error information
        """
        # Generate unique error ID
        error_id = f"err_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{id(exception)}"

        # Get current logging context
        logging_context = get_current_context()

        # Create error context
        context = ErrorContext(
            error_id=error_id,
            error_type=type(exception).__name__,
            error_message=str(exception),
            stack_trace=traceback.format_exc(),
            local_variables=self._capture_local_variables() if capture_locals else {},
            global_variables=self._capture_global_variables() if capture_globals else {},
            service_state=self._capture_service_state(),
            performance_metrics=self._capture_performance_metrics(),
            memory_usage=self._get_memory_usage(),
            cpu_usage=self._get_cpu_usage(),
            user_id=logging_context.get_user_id() if logging_context else None,
            session_id=logging_context.get_session_id() if logging_context else None,
            request_id=logging_context.get_request_id() if logging_context else None,
            recovery_suggestions=self._get_recovery_suggestions(exception),
            is_retryable=self._is_retryable(exception),
            metadata=additional_context or {},
        )

        # Set current error context
        _error_context_var.set(context)

        return context

    def _capture_local_variables(self) -> Dict[str, Any]:
        """Capture local variables from the current frame"""
        try:
            frame = sys._getframe(2)  # Go up 2 frames to get caller's locals
            return self._sanitize_variables(frame.f_locals)
        except Exception:
            return {}

    def _capture_global_variables(self) -> Dict[str, Any]:
        """Capture global variables from the current frame"""
        try:
            frame = sys._getframe(2)  # Go up 2 frames to get caller's globals
            return self._sanitize_variables(frame.f_globals)
        except Exception:
            return {}

    def _capture_service_state(self) -> Dict[str, Any]:
        """Capture current service state"""
        try:
            # Get current logging context for service state
            logging_context = get_current_context()
            if logging_context:
                return {
                    "calculation_sessions": logging_context.get_context().get(
                        "calculation_sessions", {}
                    ),
                    "performance_metrics": logging_context.get_performance_metrics(),
                    "context_data": logging_context.get_context().get("context_data", {}),
                }
            return {}
        except Exception:
            return {}

    def _capture_performance_metrics(self) -> Dict[str, Any]:
        """Capture current performance metrics"""
        try:
            import psutil

            process = psutil.Process()
            return {
                "cpu_percent": process.cpu_percent(),
                "memory_percent": process.memory_percent(),
                "memory_info": process.memory_info()._asdict(),
                "thread_count": process.num_threads(),
                "open_files": len(process.open_files()),
            }
        except ImportError:
            return {"note": "psutil not available for performance metrics"}
        except Exception:
            return {}

    def _get_memory_usage(self) -> Optional[Decimal]:
        """Get current memory usage in MB"""
        try:
            import psutil

            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024  # Convert to MB
        except Exception:
            return None

    def _get_cpu_usage(self) -> Optional[Decimal]:
        """Get current CPU usage percentage"""
        try:
            import psutil

            return psutil.cpu_percent()
        except Exception:
            return None

    def _sanitize_variables(self, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize variables to remove sensitive information"""
        sanitized = sanitize_log_value(variables)
        return sanitized if isinstance(sanitized, dict) else {}

    def _sanitize_value(self, value: Any) -> Any:
        """Sanitize a single value"""
        return sanitize_log_value(value)

    def _get_recovery_suggestions(self, exception: Exception) -> List[str]:
        """Get recovery suggestions based on exception type"""
        suggestions = []

        if isinstance(exception, (ConnectionError, TimeoutError)):
            suggestions.extend(
                ["Check network connectivity", "Retry the operation", "Check service availability"]
            )
        elif isinstance(exception, (ValueError, TypeError)):
            suggestions.extend(
                ["Check input data format", "Validate data types", "Review calculation parameters"]
            )
        elif isinstance(exception, (PermissionError, OSError)):
            suggestions.extend(
                ["Check file permissions", "Verify system access rights", "Check disk space"]
            )
        else:
            suggestions.append("Review error details and system logs")

        return suggestions

    def _is_retryable(self, exception: Exception) -> bool:
        """Determine if an error is retryable"""
        retryable_types = (
            ConnectionError,
            TimeoutError,
            OSError,
            # Add more retryable exception types as needed
        )
        return isinstance(exception, retryable_types)


def create_error_context(
    exception: Exception,
    additional_context: Optional[Dict[str, Any]] = None,
    capture_locals: bool = True,
    capture_globals: bool = False,
    **kwargs,
) -> ErrorContext:
    """
    Create error context for an exception.

    Args:
        exception: The exception that occurred
        additional_context: Additional context to include
        capture_locals: Whether to capture local variables
        capture_globals: Whether to capture global variables
        **kwargs: Additional fields to set on the ErrorContext (e.g. calculation_step, request_id)

    Returns:
        ErrorContext with comprehensive error information
    """
    capture = ErrorContextCapture()
    context = capture.capture_context(
        exception, additional_context, capture_locals, capture_globals
    )
    for key, value in kwargs.items():
        if hasattr(context, key):
            object.__setattr__(context, key, value)
    return context


def get_current_error_context() -> Optional[ErrorContext]:
    """Get the current error context"""
    return _error_context_var.get()


def set_current_error_context(context: ErrorContext) -> None:
    """Set the current error context"""
    _error_context_var.set(context)


def clear_current_error_context() -> None:
    """Clear the current error context"""
    _error_context_var.set(None)


# Context manager for automatic error context capture
class ErrorContextManager:
    """Context manager for automatic error context capture"""

    def __init__(self, capture_locals: bool = True, capture_globals: bool = False):
        self.capture_locals = capture_locals
        self.capture_globals = capture_globals
        self.capture = ErrorContextCapture()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # Capture error context
            context = self.capture.capture_context(
                exc_val, capture_locals=self.capture_locals, capture_globals=self.capture_globals
            )
            # Store in current context
            set_current_error_context(context)


# Export main classes and functions
__all__ = [
    "ErrorContext",
    "ErrorContextCapture",
    "create_error_context",
    "get_current_error_context",
    "set_current_error_context",
    "clear_current_error_context",
    "ErrorContextManager",
]
