from src.utils.exceptions import ValuationTimeoutError

"""
Circuit Breaker Pattern Implementation

This module provides a circuit breaker to prevent cascading failures when
external services (APIs, databases) are slow or unavailable.

The circuit breaker has three states:
- CLOSED: Normal operation, requests pass through
- OPEN: Service is failing, requests fail immediately without trying
- HALF_OPEN: Testing if service has recovered

Author: Upswitch Engineering Team
Date: November 2025
Status: Production Ready

WHY SEPARATE FROM REPORT GENERATION CIRCUIT BREAKER?
====================================================
This is a general-purpose circuit breaker implementation using a decorator
pattern. There is a separate, more advanced circuit breaker implementation
in `src.services.infrastructure.report_generation.circuit_breaker` that is
used specifically for HTML report generation.

KEY DIFFERENCES:
- This implementation: Decorator-based (`@breaker`), simpler API, suitable
  for single-threaded or low-concurrency scenarios
- Report generation implementation: Programmatic `call_async()` method,
  async-safe locks for concurrent coroutines, CircuitBreakerManager for
  managing multiple breakers

WHEN TO USE THIS vs REPORT GENERATION CIRCUIT BREAKER:
- Use THIS (`src.utils.circuit_breaker`) for:
  * Simple function protection with decorators
  * General API/database protection
  * Single-threaded or low-concurrency scenarios
  * When you prefer decorator syntax: `@fmp_circuit_breaker`

- Use REPORT GENERATION circuit breaker for:
  * Concurrent async operations (asyncio.gather with multiple coroutines)
  * When you need programmatic control via `call_async()`
  * When you need CircuitBreakerManager for multiple breakers
  * Report generation or other high-concurrency async scenarios

NOTE: The async path now uses asyncio.Lock for safe concurrent access within
a single event loop. For multi-threaded access, use the report generation
circuit breaker implementation instead.
"""

import asyncio
import threading
import time
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, Optional

from src.utils.decimal_helpers import from_decimal, to_decimal


class CircuitState(Enum):
    """Circuit breaker states"""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open"""

    pass


class CircuitBreaker:
    """
    Circuit breaker implementation for protecting against cascading failures.

    Usage:
        breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60,
            expected_exception=RequestException
        )

        @breaker
        async def call_external_api():
            response = await api.get("/data")
            return response
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
        name: Optional[str] = None,
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before testing recovery (half-open)
            expected_exception: Exception type that counts as failure
            name: Optional name for logging
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name or "CircuitBreaker"

        self.failure_count = 0
        self.last_failure_time: Optional[Decimal] = None
        self.state = CircuitState.CLOSED

        # Statistics
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.rejected_calls = 0

        self._async_lock: Optional[asyncio.Lock] = None
        self._sync_lock = threading.Lock()

    def _should_attempt_reset(self) -> bool:
        """
        Check if enough time has passed to attempt recovery.

        Returns:
            True if should attempt reset (move to HALF_OPEN)
        """
        if self.last_failure_time is None:
            return False

        return time.time() - self.last_failure_time >= self.recovery_timeout

    def _record_success(self):
        """Record a successful call"""
        self.failure_count = 0
        self.successful_calls += 1

        if self.state == CircuitState.HALF_OPEN:
            # Recovery successful, close circuit
            self.state = CircuitState.CLOSED

    def _record_failure(self):
        """Record a failed call"""
        self.failure_count += 1
        self.failed_calls += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            # Open the circuit
            self.state = CircuitState.OPEN

    def _can_execute(self) -> bool:
        """
        Check if the call should be executed.

        Returns:
            True if call should be executed, False if circuit is open
        """
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                # Move to half-open to test recovery
                self.state = CircuitState.HALF_OPEN
                return True
            else:
                # Circuit is open, reject request
                self.rejected_calls += 1
                return False

        # HALF_OPEN: allow one test request
        return True

    def __call__(self, func: Callable) -> Callable:
        """
        Decorator to wrap a function with circuit breaker.

        Args:
            func: Function to protect

        Returns:
            Wrapped function
        """
        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await self._execute_async(func, *args, **kwargs)

            return async_wrapper
        else:

            @wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                return self._execute_sync(func, *args, **kwargs)

            return sync_wrapper

    def _get_async_lock(self) -> asyncio.Lock:
        """Lazy-init an asyncio.Lock bound to the current event loop."""
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()
        return self._async_lock

    async def _execute_async(self, func: Callable, *args, **kwargs) -> Any:
        """Execute async function with circuit breaker (async-safe)."""
        async with self._get_async_lock():
            self.total_calls += 1

            if not self._can_execute():
                raise CircuitBreakerError(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Failed {self.failure_count} times. "
                    f"Will retry after {self.recovery_timeout}s."
                )

        try:
            result = await func(*args, **kwargs)
        except self.expected_exception:
            async with self._get_async_lock():
                self._record_failure()
            raise
        except ValuationTimeoutError:
            raise
        else:
            async with self._get_async_lock():
                self._record_success()
            return result

    def _execute_sync(self, func: Callable, *args, **kwargs) -> Any:
        """Execute sync function with circuit breaker (thread-safe)."""
        with self._sync_lock:
            self.total_calls += 1

            if not self._can_execute():
                raise CircuitBreakerError(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Failed {self.failure_count} times. "
                    f"Will retry after {self.recovery_timeout}s."
                )

        try:
            result = func(*args, **kwargs)
        except self.expected_exception:
            with self._sync_lock:
                self._record_failure()
            raise
        except ValuationTimeoutError:
            raise
        else:
            with self._sync_lock:
                self._record_success()
            return result

    def get_state(self) -> CircuitState:
        """Get current circuit state"""
        return self.state

    def get_stats(self) -> Dict[str, Any]:
        """
        Get circuit breaker statistics.

        Returns:
            Dictionary with statistics
        """
        return {
            "name": self.name,
            "state": self.state.value,
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "rejected_calls": self.rejected_calls,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure_time": (
                datetime.fromtimestamp(self.last_failure_time).isoformat()
                if self.last_failure_time
                else None
            ),
            "success_rate": (
                f"{(self.successful_calls / self.total_calls * 100):.1f}%"
                if self.total_calls > 0
                else "N/A"
            ),
        }

    def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED state"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None


# ==================== PRE-CONFIGURED CIRCUIT BREAKERS ====================

# Circuit breaker for FMP API calls
fmp_circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60, name="FMP_API")

# Circuit breaker for database calls
database_circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30, name="Database")

# Circuit breaker for cache service
cache_circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30, name="Cache")


# ==================== USAGE EXAMPLES ====================

# Example 1: Protect async function
# @fmp_circuit_breaker
# async def fetch_market_data(symbol: str):
#     response = await fmp_api.get_quote(symbol)
#     return response

# Example 2: Protect sync function
# @database_circuit_breaker
# def query_database(query: str):
#     return db.execute(query)

# Example 3: Manual usage
# breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
# try:
#     result = await breaker._execute_async(my_async_function, arg1, arg2)
# except CircuitBreakerError:
#     # Circuit is open, use fallback
#     result = get_fallback_data()


# ==================== EXPORT ====================

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerError",
    "CircuitState",
    "fmp_circuit_breaker",
    "database_circuit_breaker",
    "cache_circuit_breaker",
]
