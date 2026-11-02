"""
Retry Handler with Exponential Backoff

Implements retry mechanism with exponential backoff for transient failures.
Handles retries for report generation operations.

BANK-GRADE DESIGN:
- Exponential backoff: 1s, 2s, 4s, 8s
- Max retries: 3 attempts
- Retry only on transient errors
- Don't retry on validation errors or template errors
- Thread-safe for concurrent requests
"""

import asyncio
import random
import time
from collections.abc import Awaitable, Callable, Mapping
from enum import Enum
from functools import wraps
from typing import Optional, ParamSpec, Protocol, TypeVar, cast

P = ParamSpec("P")
R = TypeVar("R")


class RetryLogger(Protocol):
    """Minimal logger surface used by retry handling."""

    def info(self, msg: object, *args: object, **kwargs: object) -> None: ...

    def warning(self, msg: object, *args: object, **kwargs: object) -> None: ...

    def error(self, msg: object, *args: object, **kwargs: object) -> None: ...


def _callable_name(func: Callable[..., object]) -> str:
    name = getattr(func, "__name__", None)
    if isinstance(name, str):
        return name
    return func.__class__.__name__


class RetryableErrorType(Enum):
    """Types of errors that should be retried."""

    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    TEMPLATE_SERVICE_ERROR = "template_service_error"
    TRANSIENT_ERROR = "transient_error"


class NonRetryableErrorType(Enum):
    """Types of errors that should NOT be retried."""

    VALIDATION_ERROR = "validation_error"
    TEMPLATE_ERROR = "template_error"
    DATA_TRANSFORMATION_ERROR = "data_transformation_error"
    CIRCUIT_BREAKER_OPEN = "circuit_breaker_open"


class RetryConfig:
    """Configuration for retry mechanism."""

    def __init__(
        self,
        max_attempts: int = 3,
        backoff_base: float = 1.0,
        max_backoff: float = 8.0,
        jitter: bool = True,
    ) -> None:
        """
        Initialize retry configuration.

        Args:
            max_attempts: Maximum number of retry attempts (default: 3)
            backoff_base: Base delay in seconds for exponential backoff (default: 1.0)
            max_backoff: Maximum backoff delay in seconds (default: 8.0)
            jitter: Whether to add random jitter to backoff (default: True)
        """
        self.max_attempts: int = max_attempts
        self.backoff_base: float = backoff_base
        self.max_backoff: float = max_backoff
        self.jitter: bool = jitter


class RetryHandler:
    """
    Retry handler with exponential backoff.

    BANK-GRADE IMPLEMENTATION:
    - Exponential backoff with jitter
    - Retry only on transient errors
    - Comprehensive logging of retry attempts
    - Thread-safe for concurrent requests
    """

    def __init__(
        self,
        config: Optional[RetryConfig] = None,
        logger: RetryLogger | None = None,
    ) -> None:
        """
        Initialize retry handler.

        Args:
            config: Retry configuration (uses defaults if not provided)
            logger: Logger instance for logging retry attempts
        """
        self.config = config or RetryConfig()
        self.logger = logger

    def _is_retryable_error(self, error: Exception) -> bool:
        """
        Determine if error is retryable.

        Args:
            error: Exception to check

        Returns:
            True if error is retryable, False otherwise
        """
        error_type = type(error).__name__
        error_str = str(error).lower()

        # Check for non-retryable errors first
        if any(non_retryable.value in error_str for non_retryable in NonRetryableErrorType):
            return False

        # Check for retryable errors
        retryable_patterns = [
            "timeout",
            "connection",
            "network",
            "temporary",
            "transient",
            "service unavailable",
            "circuit breaker",
        ]

        if any(pattern in error_str for pattern in retryable_patterns):
            return True

        # Check specific exception types
        retryable_exceptions = (
            asyncio.TimeoutError,
            ConnectionError,
            OSError,  # Network errors
        )

        return isinstance(error, retryable_exceptions)

    def _calculate_backoff(self, attempt: int) -> float:
        """
        Calculate backoff delay for given attempt.

        Args:
            attempt: Current attempt number (0-indexed)

        Returns:
            Backoff delay in seconds
        """
        # Exponential backoff: base * 2^attempt
        delay: float = self.config.backoff_base * (2**attempt)

        # Cap at max_backoff
        delay = min(delay, self.config.max_backoff)

        # Add jitter if enabled (random value between 0 and delay * 0.1)
        if self.config.jitter:
            jitter_amount = delay * 0.1 * random.random()
            delay += jitter_amount

        return float(delay)

    async def retry_async(
        self,
        func: Callable[..., Awaitable[R]],
        *args: object,
        context: Mapping[str, object] | None = None,
        **kwargs: object,
    ) -> R:
        """
        Execute async function with retry logic.

        BANK-GRADE EXECUTION:
        - Retries on transient errors only
        - Exponential backoff between attempts
        - Logs all retry attempts
        - Raises last exception if all retries fail

        Args:
            func: Async function to execute
            *args: Positional arguments for function
            context: Optional context dictionary for logging
            **kwargs: Keyword arguments for function

        Returns:
            Function result

        Raises:
            Last exception if all retries fail
        """
        last_exception: BaseException | None = None
        context = context or {}
        function_name = _callable_name(func)

        for attempt in range(self.config.max_attempts):
            try:
                # Execute function
                result = await func(*args, **kwargs)

                # If successful and not first attempt, log success after retry
                if attempt > 0 and self.logger:
                    self.logger.info(
                        f"✅ [RETRY] Function succeeded after {attempt} retry attempts",
                        extra={
                            **context,
                            "attempt": attempt + 1,
                            "total_attempts": attempt + 1,
                            "function": function_name,
                        },
                    )

                return result

            except Exception as e:
                last_exception = e

                # Check if error is retryable
                if not self._is_retryable_error(e):
                    if self.logger:
                        self.logger.warning(
                            f"⚠️ [RETRY] Non-retryable error encountered, not retrying",
                            extra={
                                **context,
                                "attempt": attempt + 1,
                                "error_type": type(e).__name__,
                                "error_message": str(e),
                                "function": function_name,
                            },
                        )
                    raise

                # Check if we have more attempts
                if attempt < self.config.max_attempts - 1:
                    backoff_delay = self._calculate_backoff(attempt)

                    if self.logger:
                        self.logger.warning(
                            f"⚠️ [RETRY] Attempt {attempt + 1} failed, retrying after {backoff_delay:.2f}s",
                            extra={
                                **context,
                                "attempt": attempt + 1,
                                "max_attempts": self.config.max_attempts,
                                "backoff_delay": backoff_delay,
                                "error_type": type(e).__name__,
                                "error_message": str(e),
                                "function": function_name,
                            },
                        )

                    # Wait before retrying
                    await asyncio.sleep(backoff_delay)
                else:
                    # Last attempt failed
                    if self.logger:
                        self.logger.error(
                            f"❌ [RETRY] All {self.config.max_attempts} attempts failed",
                            extra={
                                **context,
                                "attempt": attempt + 1,
                                "max_attempts": self.config.max_attempts,
                                "error_type": type(last_exception).__name__,
                                "error_message": str(last_exception),
                                "function": function_name,
                            },
                            exc_info=last_exception,
                        )

        # All retries exhausted, raise last exception
        if last_exception is not None:
            raise last_exception
        raise RuntimeError("Retry attempts exhausted without capturing an exception")

    def retry_sync(
        self,
        func: Callable[..., R],
        *args: object,
        context: Mapping[str, object] | None = None,
        **kwargs: object,
    ) -> R:
        """
        Execute sync function with retry logic.

        BANK-GRADE EXECUTION:
        - Retries on transient errors only
        - Exponential backoff between attempts
        - Logs all retry attempts
        - Raises last exception if all retries fail

        Args:
            func: Sync function to execute
            *args: Positional arguments for function
            context: Optional context dictionary for logging
            **kwargs: Keyword arguments for function

        Returns:
            Function result

        Raises:
            Last exception if all retries fail
        """
        last_exception: BaseException | None = None
        context = context or {}
        function_name = _callable_name(func)

        for attempt in range(self.config.max_attempts):
            try:
                # Execute function
                result = func(*args, **kwargs)

                # If successful and not first attempt, log success after retry
                if attempt > 0 and self.logger:
                    self.logger.info(
                        f"✅ [RETRY] Function succeeded after {attempt} retry attempts",
                        extra={
                            **context,
                            "attempt": attempt + 1,
                            "total_attempts": attempt + 1,
                            "function": function_name,
                        },
                    )

                return result

            except Exception as e:
                last_exception = e

                # Check if error is retryable
                if not self._is_retryable_error(e):
                    if self.logger:
                        self.logger.warning(
                            f"⚠️ [RETRY] Non-retryable error encountered, not retrying",
                            extra={
                                **context,
                                "attempt": attempt + 1,
                                "error_type": type(e).__name__,
                                "error_message": str(e),
                                "function": function_name,
                            },
                        )
                    raise

                # Check if we have more attempts
                if attempt < self.config.max_attempts - 1:
                    backoff_delay = self._calculate_backoff(attempt)

                    if self.logger:
                        self.logger.warning(
                            f"⚠️ [RETRY] Attempt {attempt + 1} failed, retrying after {backoff_delay:.2f}s",
                            extra={
                                **context,
                                "attempt": attempt + 1,
                                "max_attempts": self.config.max_attempts,
                                "backoff_delay": backoff_delay,
                                "error_type": type(e).__name__,
                                "error_message": str(e),
                                "function": function_name,
                            },
                        )

                    # Wait before retrying (sync sleep)
                    time.sleep(backoff_delay)
                else:
                    # Last attempt failed
                    if self.logger:
                        self.logger.error(
                            f"❌ [RETRY] All {self.config.max_attempts} attempts failed",
                            extra={
                                **context,
                                "attempt": attempt + 1,
                                "max_attempts": self.config.max_attempts,
                                "error_type": type(last_exception).__name__,
                                "error_message": str(last_exception),
                                "function": function_name,
                            },
                            exc_info=last_exception,
                        )

        # All retries exhausted, raise last exception
        if last_exception is not None:
            raise last_exception
        raise RuntimeError("Retry attempts exhausted without capturing an exception")


def retry_with_backoff(
    max_attempts: int = 3,
    backoff_base: float = 1.0,
    max_backoff: float = 8.0,
    jitter: bool = True,
    logger: RetryLogger | None = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """
    Decorator for retrying async functions with exponential backoff.

    BANK-GRADE DECORATOR:
    - Wraps async function with retry logic
    - Exponential backoff between attempts
    - Retries only on transient errors

    Args:
        max_attempts: Maximum number of retry attempts
        backoff_base: Base delay in seconds for exponential backoff
        max_backoff: Maximum backoff delay in seconds
        jitter: Whether to add random jitter to backoff
        logger: Logger instance for logging retry attempts

    Returns:
        Decorated function
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        backoff_base=backoff_base,
        max_backoff=max_backoff,
        jitter=jitter,
    )
    retry_handler = RetryHandler(config, logger)

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # Extract context from kwargs if available
            kwargs_mapping = cast(Mapping[str, object], kwargs)
            context_value = kwargs_mapping.get("context", {})
            context = context_value if isinstance(context_value, Mapping) else {}
            return await retry_handler.retry_async(func, *args, context=context, **kwargs)

        return wrapper

    return decorator
