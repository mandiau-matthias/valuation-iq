"""
Logging Context Manager

Provides comprehensive context management for structured logging across the valuation engine.
Supports request tracking, user context, calculation sessions, and nested context for complex workflows.

ARCHITECTURE:
- Request ID tracking across all services
- User context propagation
- Calculation session tracking
- Nested context support for complex workflows
- Performance metrics integration
- Correlation ID injection for distributed tracing

USAGE:
    Create LoggingContext, set request/user identifiers, obtain a logger via get_logger(__name__),
    and pass context.get_context() into structured log calls where needed.
"""

import json
import threading
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional, Union

# Thread-local storage for context
_context_var: ContextVar[Optional["LoggingContext"]] = ContextVar("logging_context", default=None)

# Avoid circular import by using basic logging
import logging

logger = logging.getLogger(__name__)


def get_logger(name: str):
    """Get a logger instance - delegates to the main logging module"""
    from src.utils.logging import get_logger as main_get_logger

    return main_get_logger(name)


@dataclass
class CalculationSession:
    """Represents a calculation session with timing and metadata"""

    session_id: str
    calculation_type: str
    start_time: datetime
    end_time: Optional[datetime] = None
    steps_completed: int = 0
    total_steps: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    steps: list = field(default_factory=list)

    def add_step(self, step_name: str, step_data: Dict[str, Any] = None):
        """Add a calculation step to the session"""
        self.steps_completed += 1
        step_entry = {"name": step_name, "data": step_data or {}}
        self.steps.append(step_entry)
        if step_data:
            self.metadata[f"step_{self.steps_completed}_{step_name}"] = step_data

    def complete(self):
        """Mark the calculation session as complete"""
        self.end_time = datetime.now(timezone.utc)

    @property
    def duration(self) -> Optional[float]:
        """Get session duration in seconds"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None


class LoggingContext:
    """
    Comprehensive logging context manager for the valuation engine.

    Provides:
    - Request ID tracking across all services
    - User context propagation
    - Calculation session tracking
    - Nested context support for complex workflows
    - Performance metrics integration
    - Correlation ID injection for distributed tracing
    """

    def __init__(self):
        self._request_id: Optional[str] = None
        self._user_id: Optional[str] = None
        self._session_id: Optional[str] = None
        self._calculation_sessions: Dict[str, CalculationSession] = {}
        self._context_data: Dict[str, Any] = {}
        self._nested_contexts: list = []
        self._performance_metrics: Dict[str, Any] = {}
        self._correlation_id: Optional[str] = None

        # Thread safety
        self._lock = threading.RLock()

    @property
    def request_id(self) -> Optional[str]:
        """Get the current request ID"""
        return self._request_id

    @property
    def user_id(self) -> Optional[str]:
        """Get the current user ID"""
        return self._user_id

    @property
    def session_id(self) -> Optional[str]:
        """Get the current session ID"""
        return self._session_id

    @property
    def correlation_id(self) -> Optional[str]:
        """Get the current correlation ID"""
        return self._correlation_id

    def set_request_id(self, request_id: str) -> "LoggingContext":
        """Set the request ID for this context"""
        with self._lock:
            self._request_id = request_id
            self._correlation_id = request_id
        return self

    def get_request_id(self) -> Optional[str]:
        """Get the current request ID"""
        return self._request_id

    def set_user_id(self, user_id: str) -> "LoggingContext":
        """Set the user ID for this context"""
        with self._lock:
            self._user_id = user_id
        return self

    def get_user_id(self) -> Optional[str]:
        """Get the current user ID"""
        return self._user_id

    def set_session_id(self, session_id: str) -> "LoggingContext":
        """Set the session ID for this context"""
        with self._lock:
            self._session_id = session_id
        return self

    def get_session_id(self) -> Optional[str]:
        """Get the current session ID"""
        return self._session_id

    def set_correlation_id(self, correlation_id: str) -> "LoggingContext":
        """Set the correlation ID for distributed tracing"""
        with self._lock:
            self._correlation_id = correlation_id
        return self

    def get_correlation_id(self) -> Optional[str]:
        """Get the current correlation ID"""
        return self._correlation_id

    def start_calculation_session(
        self,
        calculation_type: str,
        total_steps: int = 0,
        metadata: Dict[str, Any] = None,
    ) -> str:
        """Start a new calculation session"""
        with self._lock:
            session_id = str(uuid.uuid4())
            session = CalculationSession(
                session_id=session_id,
                calculation_type=calculation_type,
                start_time=datetime.now(timezone.utc),
                total_steps=total_steps,
                metadata=metadata or {},
            )
            self._calculation_sessions[session_id] = session
            return session_id

    def add_calculation_step(
        self, session_id: str, step_name: str, step_data: Dict[str, Any] = None
    ):
        """Add a step to a calculation session, auto-creating if needed"""
        with self._lock:
            if session_id not in self._calculation_sessions:
                self._calculation_sessions[session_id] = CalculationSession(
                    session_id=session_id,
                    calculation_type="auto",
                    start_time=datetime.now(timezone.utc),
                )
            self._calculation_sessions[session_id].add_step(step_name, step_data)

    def complete_calculation_session(self, session_id: str):
        """Complete a calculation session"""
        with self._lock:
            if session_id in self._calculation_sessions:
                self._calculation_sessions[session_id].complete()

    def get_calculation_session(self, session_id: str) -> Optional[CalculationSession]:
        """Get a calculation session by ID"""
        return self._calculation_sessions.get(session_id)

    def add_context_data(self, key: str, value: Any) -> "LoggingContext":
        """Add custom context data"""
        with self._lock:
            self._context_data[key] = value
        return self

    def get_context_data(self, key: str, default: Any = None) -> Any:
        """Get custom context data"""
        return self._context_data.get(key, default)

    def set_company_name(self, company_name: str) -> "LoggingContext":
        return self.add_context_data("company_name", company_name)

    def get_company_name(self) -> Optional[str]:
        return self.get_context_data("company_name")

    def is_calculation_session_active(self, session_id: str) -> bool:
        session = self.get_calculation_session(session_id)
        return session is not None and session.end_time is None

    def get_current_session_id(self) -> Optional[str]:
        with self._lock:
            if not self._calculation_sessions:
                return None
            return next(reversed(self._calculation_sessions))

    def push_nested_context(
        self, context_name: str, context_data: Dict[str, Any] = None
    ) -> "LoggingContext":
        """Push a nested context for complex workflows"""
        with self._lock:
            nested = {
                "name": context_name,
                "data": context_data or {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._nested_contexts.append(nested)
        return self

    def pop_nested_context(self) -> Optional[Dict[str, Any]]:
        """Pop the most recent nested context"""
        with self._lock:
            if self._nested_contexts:
                return self._nested_contexts.pop()
        return None

    def add_performance_metric(
        self, metric_name: str, value: Union[int, Decimal, str], unit: str = None
    ):
        """Add a performance metric"""
        with self._lock:
            self._performance_metrics[metric_name] = {
                "value": value,
                "unit": unit,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get all performance metrics"""
        return self._performance_metrics.copy()

    def get_context(self) -> Dict[str, Any]:
        """Get the complete context for logging"""
        with self._lock:
            context = {
                "request_id": self._request_id,
                "user_id": self._user_id,
                "session_id": self._session_id,
                "correlation_id": self._correlation_id,
                "context_data": self._context_data.copy(),
                "nested_contexts": self._nested_contexts.copy(),
                "performance_metrics": self._performance_metrics.copy(),
                "calculation_sessions": {
                    session_id: {
                        "session_id": session.session_id,
                        "calculation_type": session.calculation_type,
                        "start_time": session.start_time.isoformat(),
                        "end_time": session.end_time.isoformat() if session.end_time else None,
                        "duration": session.duration,
                        "steps_completed": session.steps_completed,
                        "total_steps": session.total_steps,
                        "metadata": session.metadata,
                    }
                    for session_id, session in self._calculation_sessions.items()
                },
            }
            return context

    def clear(self):
        """Clear all context data"""
        with self._lock:
            self._request_id = None
            self._user_id = None
            self._session_id = None
            self._calculation_sessions.clear()
            self._context_data.clear()
            self._nested_contexts.clear()
            self._performance_metrics.clear()
            self._correlation_id = None

    def clear_all_data(self):
        """Alias for clear() - clears all context data"""
        self.clear()


# Global context management
def get_current_context() -> Optional[LoggingContext]:
    """Get the current logging context"""
    return _context_var.get()


def set_current_context(context: LoggingContext) -> None:
    """Set the current logging context"""
    _context_var.set(context)


def clear_current_context() -> None:
    """Clear the current logging context"""
    _context_var.set(None)


def create_context(
    request_id: str = None, user_id: str = None, session_id: str = None
) -> LoggingContext:
    """Create a new logging context with optional initial values"""
    context = LoggingContext()
    if request_id:
        context.set_request_id(request_id)
    if user_id:
        context.set_user_id(user_id)
    if session_id:
        context.set_session_id(session_id)
    return context


# Context manager for automatic context management
class LoggingContextManager:
    """Context manager for automatic logging context management"""

    def __init__(self, request_id: str = None, user_id: str = None, session_id: str = None):
        self.context = create_context(request_id, user_id, session_id)
        self.previous_context = None

    def __enter__(self) -> LoggingContext:
        self.previous_context = get_current_context()
        set_current_context(self.context)
        return self.context

    def __exit__(self, exc_type, exc_val, exc_tb):
        set_current_context(self.previous_context)


# Utility functions for common logging patterns
def log_calculation_step(step_name: str, step_data: Dict[str, Any] = None, session_id: str = None):
    """Log a calculation step with context"""
    context = get_current_context()
    if context and session_id:
        context.add_calculation_step(session_id, step_name, step_data)

    # Also log to the logger
    logger = get_logger(__name__)
    logger.info(
        f"Calculation step: {step_name}",
        step_data=step_data,
        session_id=session_id,
        context=context.get_context() if context else None,
    )


def log_performance_metric(metric_name: str, value: Union[int, Decimal, str], unit: str = None):
    """Log a performance metric with context"""
    context = get_current_context()
    if context:
        context.add_performance_metric(metric_name, value, unit)

    # Also log to the logger
    logger = get_logger(__name__)
    logger.info(
        f"Performance metric: {metric_name}",
        metric_name=metric_name,
        value=value,
        unit=unit,
        context=context.get_context() if context else None,
    )


def log_financial_data(operation: str, data: Dict[str, Any], precision: int = 2):
    """Log financial data with proper formatting and context"""
    context = get_current_context()

    # Format financial data with precision
    formatted_data = {}
    for key, value in data.items():
        if isinstance(value, (int, float)):
            formatted_data[key] = round(value, precision)
        else:
            formatted_data[key] = value

    logger = get_logger(__name__)
    logger.info(
        f"Financial operation: {operation}",
        operation=operation,
        data=formatted_data,
        context=context.get_context() if context else None,
    )


# Export the main classes and functions
__all__ = [
    "LoggingContext",
    "CalculationSession",
    "LoggingContextManager",
    "get_current_context",
    "set_current_context",
    "clear_current_context",
    "create_context",
    "log_calculation_step",
    "log_performance_metric",
    "log_financial_data",
]
