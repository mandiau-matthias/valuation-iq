from src.utils.exceptions import (
    APIError,
    CalculationError,
    DataQualityError,
    ValidationError,
    ValuationTimeoutError,
)

"""
Request Deduplication for Valuation Engine

This module provides request deduplication to avoid redundant calculations
for identical concurrent requests.

Author: Upswitch Engineering Team
Date: November 2025
Status: Production Ready
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

try:
    from prometheus_client import Counter, Gauge, Histogram
except ImportError:
    # Prometheus client is optional
    Counter = None
    Gauge = None
    Histogram = None

from decimal import Decimal

from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Metrics (optional - only if prometheus_client is available)
if Counter is not None:
    deduplication_hits = Counter(
        "valuation_deduplication_hits_total", "Number of deduplicated requests"
    )
    deduplication_cache_size = Gauge(
        "valuation_deduplication_cache_size", "Current size of deduplication cache"
    )
    deduplication_phase_duration = Histogram(
        "valuation_deduplication_phase_duration_seconds",
        "Duration of deduplication phases",
        ["phase"],
        buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0),
    )
else:
    # Dummy metrics that do nothing if prometheus_client is not available
    class DummyMetric:
        def inc(self, *args, **kwargs):
            pass

        def dec(self, *args, **kwargs):
            pass

        def labels(self, *args, **kwargs):
            return self

        def observe(self, *args, **kwargs):
            pass

    deduplication_hits = DummyMetric()
    deduplication_cache_size = DummyMetric()
    deduplication_phase_duration = DummyMetric()


@dataclass
class InFlightRequest:
    """Represents a request currently being processed."""

    fingerprint: str
    future: asyncio.Future
    started_at: float
    request_count: int = 1


class RequestDeduplicator:
    """
    Deduplicates identical concurrent requests to avoid redundant calculations.

    When multiple identical requests arrive concurrently, only the first one
    is processed. Subsequent identical requests wait for the first one to complete
    and receive the same result.
    """

    def __init__(self, ttl_seconds: int = 300):
        """
        Initialize request deduplicator.

        Args:
            ttl_seconds: Time-to-live for cached results (default: 5 minutes)
        """
        self.ttl_seconds = ttl_seconds
        self.in_flight: Dict[str, InFlightRequest] = {}
        self._lock: Optional[asyncio.Lock] = None
        self.logger = logger

        self._cleanup_task = None

    @property
    def lock(self) -> asyncio.Lock:
        """Lazy-initialize the asyncio lock (requires event loop in Python 3.9)."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def start_cleanup(self) -> None:
        """Start periodic cleanup of expired requests."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

    async def stop_cleanup(self) -> None:
        """Stop periodic cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    async def _periodic_cleanup(self):
        """Periodically clean up expired in-flight requests."""
        while True:
            try:
                await asyncio.sleep(60)  # Clean up every minute
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                # The periodic backstop must never die on a transient cleanup
                # error, or expired in-flight entries would leak until restart.
                self.logger.error(f"Error in deduplication cleanup: {e}")

    async def _cleanup_expired(self):
        """Remove expired requests from in-flight cache."""
        async with self.lock:
            now = time.time()
            expired = [
                fp for fp, req in self.in_flight.items() if now - req.started_at > self.ttl_seconds
            ]

            # Update metric when removing expired requests
            expired_count = len(expired)
            for fp in expired:
                del self.in_flight[fp]

            # Decrement gauge by the number of expired requests removed
            if expired_count > 0:
                deduplication_cache_size.dec(expired_count)
                self.logger.info(
                    f"Cleaned up {expired_count} expired requests from deduplication cache"
                )

    async def deduplicate(
        self, fingerprint: str, callable_func: Callable[[], Any], *args, **kwargs
    ) -> Any:
        """
        Deduplicate request execution.

        If an identical request (same fingerprint) is already in flight,
        wait for it to complete and return the same result. Otherwise,
        execute the callable.

        Args:
            fingerprint: Unique identifier for the request
            callable_func: Async function to execute
            *args: Arguments for callable_func
            **kwargs: Keyword arguments for callable_func

        Returns:
            Result from callable_func
        """
        # ========== PHASE 1: Check/Register (LOCK HELD) ==========
        # Minimize lock hold time - only for dictionary operations
        phase1_start = time.time()

        async with self.lock:
            if fingerprint in self.in_flight:
                # Request already in flight, wait for it
                in_flight_req = self.in_flight[fingerprint]
                in_flight_req.request_count += 1

                time_in_flight = time.time() - in_flight_req.started_at

                self.logger.info(
                    f"⚡ Request deduplicated (waiting for existing calculation)",
                    extra={
                        "fingerprint": fingerprint,
                        "identical_request_count": in_flight_req.request_count,
                        "time_in_flight": time_in_flight,
                    },
                )

                deduplication_hits.inc()

                # Get future and release lock immediately
                future = in_flight_req.future
                request_started_at = in_flight_req.started_at
                is_waiting_for_existing = True
            else:
                # First request with this fingerprint - register it
                future = asyncio.Future()
                request_start_time = time.time()
                self.in_flight[fingerprint] = InFlightRequest(
                    fingerprint=fingerprint, future=future, started_at=request_start_time
                )

                # DEBUG: dedup-layer entry; "🎬 ORCHESTRATOR START" is the
                # canonical request-start signal.
                self.logger.debug(
                    f"🚀 New unique request (starting calculation)",
                    extra={"fingerprint": fingerprint, "in_flight_count": len(self.in_flight)},
                )

                deduplication_cache_size.inc()  # Gauge can be incremented

                is_waiting_for_existing = False
                request_started_at = request_start_time

        # Lock released here - lock hold time is minimal (<1ms typically)
        phase1_duration = time.time() - phase1_start
        deduplication_phase_duration.labels(phase="check_register").observe(phase1_duration)

        # ========== PHASE 2: Execute (LOCK NOT HELD) ==========
        # Execute the callable WITHOUT holding the lock - allows concurrent operations
        if not is_waiting_for_existing:
            phase2_start = time.time()
            execution_start = time.time()
            try:
                result = await callable_func(*args, **kwargs)
                execution_duration = time.time() - execution_start
                phase2_duration = time.time() - phase2_start
                deduplication_phase_duration.labels(phase="execute").observe(phase2_duration)
                # Guard every resolution with done(): the follower-visible future
                # must be set exactly once. A late cancellation (see the
                # CancelledError handler / finally safety net) may already have
                # resolved it, and a second set_*() would raise InvalidStateError.
                if not future.done():
                    future.set_result(result)

                # Get execution time for logging (need to check if still in in_flight)
                async with self.lock:
                    if fingerprint in self.in_flight:
                        total_execution_time = time.time() - self.in_flight[fingerprint].started_at
                        total_served = self.in_flight[fingerprint].request_count
                    else:
                        total_execution_time = execution_duration
                        total_served = 1

                    # DEBUG: request-dedup completion notice; canonical
                    # request exit is the AUDIT log line.
                    self.logger.debug(
                        f"✅ Request completed successfully",
                        extra={
                            "fingerprint": fingerprint,
                            "execution_time": total_execution_time,
                            "total_served": total_served,
                        },
                    )

            except (ValueError, TypeError, AttributeError, KeyError) as e:
                # Data structure errors - re-raise as-is
                execution_duration = time.time() - execution_start
                phase2_duration = time.time() - phase2_start
                deduplication_phase_duration.labels(phase="execute").observe(phase2_duration)
                if not future.done():
                    future.set_exception(e)
            except (
                APIError,
                ValuationTimeoutError,
                CalculationError,
                DataQualityError,
                ValidationError,
            ) as e:
                # API, timeout, or calculation errors - re-raise as-is
                execution_duration = time.time() - execution_start
                phase2_duration = time.time() - phase2_start
                deduplication_phase_duration.labels(phase="execute").observe(phase2_duration)
                if not future.done():
                    future.set_exception(e)
            except (OSError, IOError, PermissionError, MemoryError) as e:
                # System errors - re-raise as-is
                execution_duration = time.time() - execution_start
                phase2_duration = time.time() - phase2_start
                deduplication_phase_duration.labels(phase="execute").observe(phase2_duration)
                if not future.done():
                    future.set_exception(e)
            except asyncio.CancelledError:
                # The leader was cancelled (e.g. an upstream asyncio.wait_for
                # timeout — see valuation_orchestration_coordinator — or a client
                # disconnect). CancelledError is a BaseException, so it bypasses
                # every handler above and would otherwise leave `future`
                # unresolved, making each deduplicated follower block on an
                # abandoned future until its own timeout. Wake followers with a
                # retryable error, then honour the cancellation for this task.
                phase2_duration = time.time() - phase2_start
                deduplication_phase_duration.labels(phase="execute").observe(phase2_duration)
                if not future.done():
                    future.set_exception(
                        ValuationTimeoutError(
                            "Deduplicated calculation was cancelled before completing; please retry"
                        )
                    )
                raise
            except Exception as e:
                # Catch-all for truly unexpected errors (after all specific exceptions handled)
                execution_duration = time.time() - execution_start
                phase2_duration = time.time() - phase2_start
                deduplication_phase_duration.labels(phase="execute").observe(phase2_duration)
                if not future.done():
                    future.set_exception(e)

                # Get request count for logging
                async with self.lock:
                    if fingerprint in self.in_flight:
                        total_attempted = self.in_flight[fingerprint].request_count
                    else:
                        total_attempted = 1

                    self.logger.error(
                        f"❌ Request failed",
                        extra={
                            "fingerprint": fingerprint,
                            "error": str(e),
                            "total_attempted": total_attempted,
                        },
                    )

            finally:
                # SAFETY NET: a deduplicated follower waits on `future`, so it must
                # always end up resolved — even if the leader exited via an
                # unexpected BaseException (e.g. KeyboardInterrupt/SystemExit) that
                # bypassed every handler above. Otherwise the follower hangs on an
                # abandoned in-flight future.
                if not future.done():
                    future.set_exception(
                        ValuationTimeoutError(
                            "Deduplicated calculation ended without a result; please retry"
                        )
                    )

                # ========== PHASE 3: Cleanup (LOCK HELD) ==========
                # Reacquire lock briefly for cleanup
                cleanup_timeout = 2.0  # 2 second timeout for cleanup lock acquisition
                cleanup_start = time.time()

                try:

                    async def cleanup_with_timeout() -> None:
                        async with self.lock:
                            if fingerprint in self.in_flight:
                                del self.in_flight[fingerprint]
                                deduplication_cache_size.dec()  # Gauge can be decremented

                    await asyncio.wait_for(cleanup_with_timeout(), timeout=cleanup_timeout)
                    cleanup_duration = time.time() - cleanup_start
                    deduplication_phase_duration.labels(phase="cleanup").observe(cleanup_duration)

                except asyncio.TimeoutError:
                    cleanup_duration = time.time() - cleanup_start
                    self.logger.warning(
                        f"⚠️ Deduplication cleanup lock timed out",
                        extra={"fingerprint": fingerprint, "cleanup_duration": cleanup_duration},
                    )
                    # Don't re-raise - cleanup timeout shouldn't mask successful execution

                except ValuationTimeoutError as cleanup_error:
                    cleanup_duration = time.time() - cleanup_start
                    deduplication_phase_duration.labels(phase="cleanup").observe(cleanup_duration)
                    # Log as WARNING since cleanup failure is non-critical
                    self.logger.warning(
                        f"⚠️ Deduplication cleanup failed (non-critical)",
                        extra={
                            "fingerprint": fingerprint,
                            "error": str(cleanup_error),
                            "error_type": type(cleanup_error).__name__,
                            "cleanup_duration": cleanup_duration,
                        },
                    )

        # ========== PHASE 4: Wait for result (LOCK NOT HELD) ==========
        try:
            if is_waiting_for_existing and request_started_at is not None:
                in_flight_age = time.time() - request_started_at
                if in_flight_age > 300:
                    self.logger.warning(
                        f"⚠️ Deduplication: waiting for very old request",
                        extra={"fingerprint": fingerprint, "age_seconds": in_flight_age},
                    )

            result = await future
            return result

        except asyncio.CancelledError:
            raise
        except (ValueError, TypeError, AttributeError, KeyError):
            raise
        except (
            APIError,
            ValuationTimeoutError,
            CalculationError,
            DataQualityError,
            ValidationError,
        ):
            raise
        except (OSError, IOError, PermissionError, MemoryError):
            raise
        except Exception:
            raise

    def get_stats(self) -> Dict[str, Any]:
        """
        Get current deduplication statistics.

        Returns:
            Dictionary with statistics
        """
        return {
            "in_flight_count": len(self.in_flight),
            "in_flight_requests": [
                {
                    "fingerprint": req.fingerprint,
                    "request_count": req.request_count,
                    "age_seconds": time.time() - req.started_at,
                }
                for req in self.in_flight.values()
            ],
        }


import threading

_global_deduplicator: Optional[RequestDeduplicator] = None
_deduplicator_lock = threading.Lock()


def get_deduplicator() -> RequestDeduplicator:
    """
    Get the global request deduplicator instance. Thread-safe.
    """
    global _global_deduplicator
    if _global_deduplicator is None:
        with _deduplicator_lock:
            if _global_deduplicator is None:
                _global_deduplicator = RequestDeduplicator(ttl_seconds=300)
    return _global_deduplicator


async def initialize_deduplicator() -> None:
    """Initialize and start the global deduplicator."""
    deduplicator = get_deduplicator()
    await deduplicator.start_cleanup()


async def shutdown_deduplicator() -> None:
    """Shutdown the global deduplicator."""
    global _global_deduplicator
    if _global_deduplicator:
        await _global_deduplicator.stop_cleanup()
        _global_deduplicator = None


# ==================== EXPORT ====================

__all__ = [
    "RequestDeduplicator",
    "InFlightRequest",
    "get_deduplicator",
    "initialize_deduplicator",
    "shutdown_deduplicator",
]
