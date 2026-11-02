"""
Monitoring Decorators and Utilities

Provides decorators and utilities for optional, non-critical monitoring.
All monitoring is designed to be fire-and-forget and never break application logic.
"""

import functools
import inspect
from types import TracebackType
from typing import Any, Callable
import structlog

logger = structlog.get_logger(__name__)


def optional_monitoring(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator to make monitoring functions completely optional.

    Wraps any monitoring function to ensure:
    - Exceptions are caught and logged
    - No exception propagates to caller
    - Original function continues normally even if monitoring fails

    Usage:
        @optional_monitoring
        async def track_something(self, data):
            # Monitoring code that might fail
            await store_in_database(data)

    If store_in_database fails, the error is logged but not raised.
    """

    @functools.wraps(func)
    async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.warning(
                f"optional_monitoring_failed",
                function=func.__name__,
                error=str(e),
                note="Application continues normally despite monitoring failure",
            )
            return None  # Return None instead of raising

    @functools.wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.warning(
                f"optional_monitoring_failed",
                function=func.__name__,
                error=str(e),
                note="Application continues normally despite monitoring failure",
            )
            return None  # Return None instead of raising

    # Return appropriate wrapper based on whether function is async
    if inspect.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


def safe_track(tracker: Any, method: str, *args: Any, **kwargs: Any) -> None:
    """
    Safely call a tracking method without raising exceptions.

    Usage:
        # Instead of:
        await tracker.track_attempt(calc_id, ...)  # Might raise

        # Use:
        safe_track(tracker, 'track_attempt', calc_id, ...)  # Never raises

    Args:
        tracker: The tracker instance
        method: Name of the method to call
        *args: Positional arguments for the method
        **kwargs: Keyword arguments for the method
    """
    try:
        if hasattr(tracker, method):
            track_method = getattr(tracker, method)

            # Call async or sync method appropriately
            if inspect.iscoroutinefunction(track_method):
                import asyncio

                try:
                    # Try to get running loop
                    loop = asyncio.get_running_loop()
                    # Create task but don't await it (fire and forget)
                    loop.create_task(track_method(*args, **kwargs))
                except RuntimeError:
                    # No running loop, just skip tracking
                    logger.debug(f"skipping_async_tracking_no_loop", method=method)
            else:
                track_method(*args, **kwargs)
    except Exception as e:
        logger.warning(
            "safe_track_failed",
            method=method,
            error=str(e),
            note="Tracking skipped but application continues",
        )


class MonitoringContext:
    """
    Context manager for optional monitoring.

    Ensures that any monitoring code within the context:
    - Never breaks the main application flow
    - Logs errors but doesn't raise them
    - Can be disabled globally

    Usage:
        with MonitoringContext():
            # Monitoring code here
            tracker.track_attempt(calc_id, ...)
            tracker.track_success(calc_id, result, time_ms)

        # If any monitoring fails, execution continues here normally
    """

    def __init__(self, description: str = "monitoring"):
        self.description = description

    def __enter__(self) -> "MonitoringContext":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        if exc_type is not None:
            # An exception occurred in monitoring code
            logger.warning(
                "monitoring_context_error",
                description=self.description,
                error_type=exc_type.__name__,
                error=str(exc_val),
                note="Error in monitoring suppressed - application continues",
            )
            # Suppress the exception (return True)
            return True
        return False
