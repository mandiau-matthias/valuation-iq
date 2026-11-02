"""
Circuit Breaker Pattern Implementation for Report Generation

Prevents cascading failures when template service degrades.
Implements independent circuit breakers per report type.

BANK-GRADE DESIGN:
- Tracks failure rates per report type
- Opens circuit after threshold failures
- Half-open state for recovery testing
- Automatic recovery when service restored
- Thread-safe for concurrent requests
- ASYNC-SAFE: Uses asyncio.Lock for async operations to prevent deadlocks

CRITICAL FIX (2024-12-04):
- Fixed deadlock issue when multiple async coroutines use circuit breaker concurrently
- Replaced threading.Lock with asyncio.Lock for async operations
- Maintains separate threading.Lock for sync operations (backward compatibility)
- This fix resolves the hanging issue in generate_both_reports() when running
  Accountant View and Info Tab generation in parallel via asyncio.gather()

WHY SEPARATE FROM src.utils.circuit_breaker?
============================================
This implementation is separate from the general-purpose circuit breaker in
src/utils/circuit_breaker.py for the following reasons:

1. **Different API**: This implementation uses `call_async()` method pattern,
   while the utils version uses decorator pattern (`@breaker`). The report
   generation strategies need programmatic control via `call_async()`.

2. **Advanced Features**: This implementation includes:
   - CircuitBreakerManager for managing multiple breakers per report type
   - More granular configuration (CircuitBreakerConfig dataclass)
   - Better statistics tracking (CircuitBreakerStats)
   - Async-safe locking (asyncio.Lock) for concurrent async operations

3. **Concurrency Requirements**: Report generation runs multiple coroutines
   in parallel via `asyncio.gather()`, requiring proper async-safe locking.
   The utils version is simpler and doesn't have async-safe locks.

4. **Domain-Specific**: This is tailored for report generation with specific
   error handling, retry integration, and metrics collection needs.

WHEN TO USE WHICH:
- Use THIS implementation (`src.services.infrastructure.report_generation.circuit_breaker`)
  for: Report generation, async operations with concurrent coroutines, when you need
  CircuitBreakerManager, or when you need programmatic `call_async()` control.

- Use `src.utils.circuit_breaker` for: Simple decorator-based protection of
  functions, general-purpose API/database protection, or when you don't need
  concurrent async safety (single-threaded or low-concurrency scenarios).
"""

import time
import asyncio
import logging
from collections.abc import Awaitable, Callable
from enum import Enum
from typing import Optional, ParamSpec, TypeVar
from threading import Lock as ThreadingLock
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")
CircuitBreakerStatsSnapshot = dict[str, str | int | float | None]


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, requests pass through
    OPEN = "open"  # Circuit open, requests fail fast
    HALF_OPEN = "half_open"  # Testing recovery, limited requests allowed


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5  # Number of failures before opening circuit
    timeout_seconds: float = 60.0  # Time before attempting recovery (half-open)
    success_threshold: int = 2  # Successes needed in half-open to close circuit
    failure_window_seconds: float = 60.0  # Time window for counting failures


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker."""

    failures: int = 0
    successes: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    state: CircuitState = CircuitState.CLOSED
    state_changed_at: float = field(default_factory=time.time)
    total_requests: int = 0
    total_failures: int = 0
    total_successes: int = 0


class CircuitBreaker:
    """
    Circuit breaker for report generation.

    BANK-GRADE IMPLEMENTATION:
    - Thread-safe operations
    - Independent state per report type
    - Automatic failure recovery
    - Comprehensive statistics tracking

    DESIGN PATTERN: Circuit Breaker
    - Prevents cascading failures
    - Fast failure when service degraded
    - Automatic recovery when service restored
    """

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ) -> None:
        """
        Initialize circuit breaker.

        Args:
            name: Name identifier for this circuit breaker (e.g., "accountant_view", "info_tab")
            config: Circuit breaker configuration (uses defaults if not provided)
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.stats = CircuitBreakerStats()
        self._sync_lock = ThreadingLock()  # For sync call() method
        self._async_lock: Optional[asyncio.Lock] = None  # Lazy initialized for async operations

    @property
    def async_lock(self) -> asyncio.Lock:
        """
        Get async lock, creating it lazily if needed.

        This ensures asyncio.Lock is created within an active event loop,
        preventing "RuntimeError: There is no current event loop" during initialization.
        Uses double-checked locking with _sync_lock for thread safety.
        """
        if self._async_lock is None:
            with self._sync_lock:
                if self._async_lock is None:
                    self._async_lock = asyncio.Lock()
        return self._async_lock

    def call(self, func: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
        """
        Execute function with circuit breaker protection (sync version).

        Args:
            func: Function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Function result

        Raises:
            CircuitBreakerOpenError: If circuit is open
            Original exception: If function execution fails
        """
        with self._sync_lock:
            # Check circuit state
            if self.stats.state == CircuitState.OPEN:
                # Check if timeout has passed (attempt recovery)
                if time.time() - self.stats.state_changed_at >= self.config.timeout_seconds:
                    self.stats.state = CircuitState.HALF_OPEN
                    self.stats.state_changed_at = time.time()
                    self.stats.successes = 0  # Reset success counter for half-open
                else:
                    # Circuit still open, fail fast
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is OPEN. "
                        f"Last failure: {self.stats.last_failure_time}. "
                        f"Will retry after: {self.config.timeout_seconds}s"
                    )

            self.stats.total_requests += 1

        # Execute function
        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except Exception as e:
            self._record_failure()
            raise

    async def call_async(
        self,
        coro: Callable[P, Awaitable[R]],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> R:
        """
        Execute async coroutine with circuit breaker protection.

        Args:
            coro: Coroutine function to execute (will be called with args/kwargs)
            *args: Positional arguments for coroutine
            **kwargs: Keyword arguments for coroutine

        Returns:
            Coroutine result

        Raises:
            CircuitBreakerOpenError: If circuit is open
            Original exception: If coroutine execution fails
        """
        async with self.async_lock:  # FIXED: Use lazy-loaded async_lock
            # Check circuit state
            if self.stats.state == CircuitState.OPEN:
                # Check if timeout has passed (attempt recovery)
                if time.time() - self.stats.state_changed_at >= self.config.timeout_seconds:
                    self.stats.state = CircuitState.HALF_OPEN
                    self.stats.state_changed_at = time.time()
                    self.stats.successes = 0  # Reset success counter for half-open
                else:
                    # Circuit still open, fail fast
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is OPEN. "
                        f"Last failure: {self.stats.last_failure_time}. "
                        f"Will retry after: {self.config.timeout_seconds}s"
                    )

            self.stats.total_requests += 1

        # Execute coroutine (release lock before executing to prevent deadlock)
        try:
            result = await coro(*args, **kwargs)
            # BANK-GRADE: Record success separately to avoid misclassifying
            # successful executions as failures if _record_success_async() throws
            try:
                await self._record_success_async()
            except Exception as record_error:
                # Log the error but don't fail the request - coroutine succeeded
                # This prevents successful executions from being recorded as failures
                logger.error(
                    f"Circuit breaker '{self.name}' failed to record success (coroutine succeeded)",
                    extra={
                        "circuit_breaker_name": self.name,
                        "error_type": type(record_error).__name__,
                        "error_message": str(record_error),
                        "coroutine_succeeded": True,
                    },
                    exc_info=True,
                )
            return result
        except Exception as e:
            # Only record failure if the coroutine itself failed
            try:
                await self._record_failure_async()
            except Exception as record_error:
                # Log the error but still raise the original exception
                logger.error(
                    f"Circuit breaker '{self.name}' failed to record failure",
                    extra={
                        "circuit_breaker_name": self.name,
                        "error_type": type(record_error).__name__,
                        "error_message": str(record_error),
                        "original_error_type": type(e).__name__,
                        "original_error_message": str(e),
                    },
                    exc_info=True,
                )
            raise

    def _record_success(self) -> None:
        """Record successful execution (sync version for sync calls)."""
        with self._sync_lock:
            self.stats.total_successes += 1
            self.stats.last_success_time = time.time()

            if self.stats.state == CircuitState.HALF_OPEN:
                self.stats.successes += 1
                # If enough successes in half-open, close circuit
                if self.stats.successes >= self.config.success_threshold:
                    self.stats.state = CircuitState.CLOSED
                    self.stats.state_changed_at = time.time()
                    self.stats.failures = 0  # Reset failure counter
                    self.stats.successes = 0
            elif self.stats.state == CircuitState.CLOSED:
                # Reset failure counter on success (sliding window)
                self.stats.failures = 0

    async def _record_success_async(self) -> None:
        """Record successful execution (async version)."""
        async with self.async_lock:
            self.stats.total_successes += 1
            self.stats.last_success_time = time.time()

            if self.stats.state == CircuitState.HALF_OPEN:
                self.stats.successes += 1
                # If enough successes in half-open, close circuit
                if self.stats.successes >= self.config.success_threshold:
                    self.stats.state = CircuitState.CLOSED
                    self.stats.state_changed_at = time.time()
                    self.stats.failures = 0  # Reset failure counter
                    self.stats.successes = 0
            elif self.stats.state == CircuitState.CLOSED:
                # Reset failure counter on success (sliding window)
                self.stats.failures = 0

    def _record_failure(self) -> None:
        """Record failed execution (sync version for sync calls)."""
        with self._sync_lock:
            self.stats.total_failures += 1
            self.stats.last_failure_time = time.time()

            if self.stats.state == CircuitState.HALF_OPEN:
                # Failure in half-open state, open circuit again
                self.stats.state = CircuitState.OPEN
                self.stats.state_changed_at = time.time()
                self.stats.failures = 1
                self.stats.successes = 0
            elif self.stats.state == CircuitState.CLOSED:
                # Increment failure counter
                self.stats.failures += 1

                # Check if we need to open circuit
                # Reset failures outside the time window
                if self.stats.last_failure_time:
                    window_start = time.time() - self.config.failure_window_seconds
                    if self.stats.last_failure_time < window_start:
                        # Failures are outside window, reset counter
                        self.stats.failures = 1

                if self.stats.failures >= self.config.failure_threshold:
                    self.stats.state = CircuitState.OPEN
                    self.stats.state_changed_at = time.time()

    async def _record_failure_async(self) -> None:
        """Record failed execution (async version)."""
        async with self.async_lock:
            self.stats.total_failures += 1
            self.stats.last_failure_time = time.time()

            if self.stats.state == CircuitState.HALF_OPEN:
                # Failure in half-open state, open circuit again
                self.stats.state = CircuitState.OPEN
                self.stats.state_changed_at = time.time()
                self.stats.failures = 1
                self.stats.successes = 0
            elif self.stats.state == CircuitState.CLOSED:
                # Increment failure counter
                self.stats.failures += 1

                # Check if we need to open circuit
                # Reset failures outside the time window
                if self.stats.last_failure_time:
                    window_start = time.time() - self.config.failure_window_seconds
                    if self.stats.last_failure_time < window_start:
                        # Failures are outside window, reset counter
                        self.stats.failures = 1

                if self.stats.failures >= self.config.failure_threshold:
                    self.stats.state = CircuitState.OPEN
                    self.stats.state_changed_at = time.time()

    def get_state(self) -> CircuitState:
        """
        Get current circuit state (lock-free for read-only access).

        NOTE: This is safe to call without locking since it's just reading a single enum value.
        Python's GIL ensures this is atomic.
        """
        return self.stats.state

    def get_stats(self) -> CircuitBreakerStatsSnapshot:
        """
        Get circuit breaker statistics (lock-free snapshot).

        NOTE: This creates a snapshot of stats without locking. Individual values might be
        slightly inconsistent if updated during read, but this is acceptable for monitoring.
        """
        return {
            "name": self.name,
            "state": self.stats.state.value,
            "failures": self.stats.failures,
            "successes": self.stats.successes,
            "total_requests": self.stats.total_requests,
            "total_failures": self.stats.total_failures,
            "total_successes": self.stats.total_successes,
            "last_failure_time": self.stats.last_failure_time,
            "last_success_time": self.stats.last_success_time,
            "state_changed_at": self.stats.state_changed_at,
            "failure_rate": (
                self.stats.total_failures / self.stats.total_requests
                if self.stats.total_requests > 0
                else 0.0
            ),
        }

    async def reset(self) -> None:
        """Reset circuit breaker to closed state (for testing/recovery)."""
        async with self.async_lock:
            self.stats.state = CircuitState.CLOSED
            self.stats.failures = 0
            self.stats.successes = 0
            self.stats.state_changed_at = time.time()


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and request is rejected."""

    pass


class CircuitBreakerManager:
    """
    Manages multiple circuit breakers (one per report type).

    BANK-GRADE MANAGER:
    - Centralized circuit breaker management
    - Independent breakers per report type
    - Statistics aggregation
    """

    def __init__(self) -> None:
        """Initialize circuit breaker manager."""
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = ThreadingLock()  # FIXED: Use ThreadingLock instead of undefined Lock

    def get_breaker(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ) -> CircuitBreaker:
        """
        Get or create circuit breaker for given name.

        Args:
            name: Circuit breaker name (e.g., "accountant_view", "info_tab")
            config: Optional configuration (uses defaults if not provided)

        Returns:
            CircuitBreaker instance
        """
        with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(name, config)
            return self._breakers[name]

    def get_all_stats(self) -> dict[str, CircuitBreakerStatsSnapshot]:
        """Get statistics for all circuit breakers."""
        with self._lock:
            return {name: breaker.get_stats() for name, breaker in self._breakers.items()}

    async def reset_all(self) -> None:
        """Reset all circuit breakers (for testing/recovery)."""
        # NOTE: This method is async because CircuitBreaker.reset() is async
        # Since this is only used for testing/recovery, async is acceptable
        # FIXED: Collect breakers first, release lock, then await async operations
        # This prevents blocking the event loop with a threading lock
        with self._lock:
            breakers = list(self._breakers.values())
        # Now await outside the lock to avoid blocking the event loop
        for breaker in breakers:
            await breaker.reset()
