from src.utils.exceptions import MethodologyError, ValuationRangeError

"""
Recovery Strategies for Error Handling

Comprehensive recovery strategies for different types of errors in the valuation engine.
Each strategy implements specific recovery logic based on error type and context.

ARCHITECTURE:
- Base RecoveryStrategy class with common functionality
- Specific strategies for different error scenarios
- Retry logic with exponential backoff
- Fallback mechanisms for service failures
- Graceful degradation for non-critical errors
- Circuit breaker pattern for service protection

STRATEGIES:
- RetryStrategy: Retry failed operations with backoff
- FallbackStrategy: Use alternative methods when primary fails
- GracefulDegradationStrategy: Continue with reduced functionality
- CircuitBreakerStrategy: Prevent cascade failures
"""

import time
import random
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import threading

from src.utils.logging import get_logger
from src.errors.error_context import ErrorContext
from decimal import Decimal

logger = get_logger(__name__)


class RecoveryResult(Enum):
    """Recovery strategy results"""
    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"
    FALLBACK = "fallback"
    CIRCUIT_OPEN = "circuit_open"


@dataclass
class RecoveryAttempt:
    """Represents a recovery attempt"""
    attempt_number: int
    timestamp: datetime
    strategy: str
    success: bool
    error: Optional[str] = None
    duration: Optional[Decimal] = None
    metadata: Dict[str, Any] = None


class RecoveryStrategy:
    """
    Base class for all recovery strategies.

    Provides common functionality for:
    - Recovery attempt tracking
    - Success/failure logging
    - Metadata collection
    - Performance monitoring
    """

    def __init__(self, name: str, max_attempts: int = 1):
        self.name = name
        self.max_attempts = max_attempts
        self.attempts: List[RecoveryAttempt] = []
        self._lock = threading.Lock()

    def execute(self, exception: Exception, error_context: ErrorContext) -> Dict[str, Any]:
        """
        Execute the recovery strategy.

        Args:
            exception: The exception that occurred
            error_context: Context about the error

        Returns:
            Dictionary with recovery results
        """
        start_time = datetime.utcnow()

        try:
            result = self._execute_recovery(exception, error_context)

            actual_success = result.get('success', True)

            attempt = RecoveryAttempt(
                attempt_number=len(self.attempts) + 1,
                timestamp=start_time,
                strategy=self.name,
                success=actual_success,
                duration=(datetime.utcnow() - start_time).total_seconds(),
                metadata=result.get('metadata', {})
            )

            with self._lock:
                self.attempts.append(attempt)

            logger.info(
                f"Recovery strategy {self.name} succeeded",
                strategy=self.name,
                duration=attempt.duration,
                metadata=result.get('metadata', {})
            )

            outer = {
                'success': actual_success,
                'strategy': self.name,
                'attempts': len(self.attempts),
                'duration': attempt.duration,
            }
            outer.update(result)

            return outer

        except Exception as recovery_error:
            attempt = RecoveryAttempt(
                attempt_number=len(self.attempts) + 1,
                timestamp=start_time,
                strategy=self.name,
                success=False,
                error=str(recovery_error),
                duration=(datetime.utcnow() - start_time).total_seconds()
            )

            with self._lock:
                self.attempts.append(attempt)

            logger.error(
                f"Recovery strategy {self.name} failed: {recovery_error}",
                strategy=self.name,
                error=str(recovery_error),
                duration=attempt.duration,
                exc_info=True
            )

            return {
                'success': False,
                'strategy': self.name,
                'attempts': len(self.attempts),
                'duration': attempt.duration,
                'error': str(recovery_error)
            }

    def _execute_recovery(self, exception: Exception, error_context: ErrorContext) -> Dict[str, Any]:
        """
        Execute the specific recovery logic.
        Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement _execute_recovery")

    def get_statistics(self) -> Dict[str, Any]:
        """Get recovery strategy statistics"""
        with self._lock:
            total_attempts = len(self.attempts)
            successful_attempts = sum(1 for attempt in self.attempts if attempt.success)
            success_rate = successful_attempts / total_attempts if total_attempts > 0 else 0

            return {
                'strategy_name': self.name,
                'total_attempts': total_attempts,
                'successful_attempts': successful_attempts,
                'success_rate': success_rate,
                'recent_attempts': [
                    {
                        'attempt_number': attempt.attempt_number,
                        'timestamp': attempt.timestamp.isoformat(),
                        'success': attempt.success,
                        'duration': attempt.duration,
                        'error': attempt.error
                    }
                    for attempt in self.attempts[-10:]  # Last 10 attempts
                ]
            }


class RetryStrategy(RecoveryStrategy):
    """
    Retry strategy with exponential backoff.

    Features:
    - Configurable retry attempts
    - Exponential backoff with jitter
    - Retry condition evaluation
    - Performance monitoring
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: Decimal = 1.0,
        max_delay: Decimal = 60.0,
        backoff_factor: Decimal = 2.0,
        jitter: bool = True
    ):
        super().__init__("retry", max_retries)
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter

    def _execute_recovery(self, exception: Exception, error_context: ErrorContext) -> Dict[str, Any]:
        """Execute retry logic with exponential backoff"""
        for attempt in range(self.max_retries):
            try:
                # Calculate delay with exponential backoff
                delay = min(
                    self.base_delay * (self.backoff_factor ** attempt),
                    self.max_delay
                )

                # Add jitter to prevent thundering herd
                if self.jitter:
                    jitter_amount = delay * 0.1 * random.random()
                    delay += jitter_amount

                logger.info(
                    f"Retry attempt {attempt + 1}/{self.max_retries}",
                    attempt=attempt + 1,
                    max_retries=self.max_retries,
                    delay=delay,
                    error_type=type(exception).__name__
                )

                # Wait before retry
                if attempt > 0:  # Don't wait on first attempt
                    time.sleep(delay)

                # Attempt the operation (this would be the actual retry logic)
                # For now, we'll simulate a retry attempt
                success = self._attempt_operation(exception, error_context, attempt)

                if success:
                    return {
                        'success': True,
                        'attempts_used': attempt + 1,
                        'total_delay': sum(
                            min(
                                self.base_delay * (self.backoff_factor ** i),
                                self.max_delay
                            )
                            for i in range(attempt)
                        ),
                        'metadata': {
                            'retry_strategy': 'exponential_backoff',
                            'max_retries': self.max_retries,
                            'base_delay': self.base_delay,
                            'backoff_factor': self.backoff_factor
                        }
                    }

            except Exception as retry_error:
                logger.warning(
                    f"Retry attempt {attempt + 1} failed: {retry_error}",
                    attempt=attempt + 1,
                    retry_error=str(retry_error)
                )

                if attempt == self.max_retries - 1:
                    raise retry_error

        # All retries failed
        raise Exception(f"All {self.max_retries} retry attempts failed")

    def _attempt_operation(self, exception: Exception, error_context: ErrorContext, attempt: int) -> bool:
        """
        Attempt the operation that failed.
        This is a placeholder - in real implementation, this would retry the actual operation.
        """
        # Simulate retry logic based on error type
        if isinstance(exception, (ConnectionError, TimeoutError)):
            # For connection errors, simulate retry success after some attempts
            return attempt >= 1  # Succeed on second attempt
        elif isinstance(exception, ValueError):
            # For validation errors, retry won't help
            return False
        else:
            # For other errors, random success
            return random.random() > 0.5


class FallbackStrategy(RecoveryStrategy):
    """
    Fallback strategy that uses alternative methods when primary fails.

    Features:
    - Multiple fallback options
    - Fallback selection logic
    - Performance comparison
    - Graceful degradation
    """

    def __init__(self, fallback_methods: List[Callable] = None):
        super().__init__("fallback", 1)
        self.fallback_methods = fallback_methods or []

    def _execute_recovery(self, exception: Exception, error_context: ErrorContext) -> Dict[str, Any]:
        """Execute fallback logic"""
        logger.info(
            f"Attempting fallback recovery for {type(exception).__name__}",
            error_type=type(exception).__name__,
            fallback_methods=len(self.fallback_methods)
        )

        if not self.fallback_methods:
            return {
                'success': False,
                'fallback_used': False,
                'metadata': {
                    'fallback_strategy': 'no_methods_available',
                    'total_fallback_methods': 0,
                }
            }

        for i, fallback_method in enumerate(self.fallback_methods):
            try:
                logger.info(f"Trying fallback method {i + 1}/{len(self.fallback_methods)}")

                result = fallback_method(exception, error_context)

                logger.info(
                    f"Fallback method {i + 1} succeeded",
                    fallback_method=i + 1,
                    result_type=type(result).__name__
                )

                return {
                    'success': True,
                    'fallback_method_used': i + 1,
                    'fallback_result': result,
                    'fallback_used': True,
                    'metadata': {
                        'fallback_strategy': 'alternative_method',
                        'total_fallback_methods': len(self.fallback_methods),
                        'method_used': i + 1
                    }
                }

            except Exception as fallback_error:
                logger.warning(
                    f"Fallback method {i + 1} failed: {fallback_error}",
                    fallback_method=i + 1,
                    fallback_error=str(fallback_error)
                )

                if i == len(self.fallback_methods) - 1:
                    return {
                        'success': False,
                        'fallback_used': True,
                        'metadata': {
                            'fallback_strategy': 'all_methods_failed',
                            'total_fallback_methods': len(self.fallback_methods),
                        }
                    }

        return {'success': False, 'fallback_used': False}


class GracefulDegradationStrategy(RecoveryStrategy):
    """
    Graceful degradation strategy that continues with reduced functionality.

    Features:
    - Reduced feature set
    - Performance optimization
    - User notification
    - Quality monitoring
    """

    def __init__(self, degradation_levels: List[str] = None):
        super().__init__("graceful_degradation", 1)
        self.degradation_levels = degradation_levels or [
            'full_functionality',
            'reduced_features',
            'basic_functionality',
            'minimal_functionality'
        ]

    def _execute_recovery(self, exception: Exception, error_context: ErrorContext) -> Dict[str, Any]:
        """Execute graceful degradation logic"""
        # Determine appropriate degradation level
        degradation_level = self._determine_degradation_level(exception, error_context)

        logger.info(
            f"Applying graceful degradation: {degradation_level}",
            degradation_level=degradation_level,
            error_type=type(exception).__name__
        )

        # Apply degradation measures
        degradation_result = self._apply_degradation(degradation_level, error_context)

        return {
            'success': True,
            'degradation_level': degradation_level,
            'degradation_result': degradation_result,
            'fallback_used': True,
            'metadata': {
                'degradation_strategy': 'reduced_functionality',
                'available_levels': self.degradation_levels,
                'level_used': degradation_level
            }
        }

    def _determine_degradation_level(self, exception: Exception, error_context: ErrorContext) -> str:
        """Determine appropriate degradation level based on error"""
        if isinstance(exception, (ConnectionError, TimeoutError)):
            return 'reduced_features'
        elif isinstance(exception, ValueError):
            return 'basic_functionality'
        elif isinstance(exception, (PermissionError, OSError)):
            return 'minimal_functionality'
        else:
            return 'reduced_features'

    def _apply_degradation(self, level: str, error_context: ErrorContext) -> Dict[str, Any]:
        """Apply degradation measures"""
        degradation_measures = {
            'reduced_features': {
                'disable_market_context': True,
                'disable_ml_analysis': True,
                'use_cached_data_only': True,
                'simplified_calculations': True
            },
            'basic_functionality': {
                'disable_market_context': True,
                'disable_ml_analysis': True,
                'use_cached_data_only': True,
                'simplified_calculations': True,
                'disable_advanced_validation': True
            },
            'minimal_functionality': {
                'disable_market_context': True,
                'disable_ml_analysis': True,
                'use_cached_data_only': True,
                'simplified_calculations': True,
                'disable_advanced_validation': True,
                'disable_performance_optimization': True,
                'basic_error_handling_only': True
            }
        }

        return degradation_measures.get(level, {})


class CircuitBreakerStrategy(RecoveryStrategy):
    """
    Circuit breaker strategy to prevent cascade failures.

    Features:
    - Failure threshold monitoring
    - Circuit state management (CLOSED, OPEN, HALF_OPEN)
    - Timeout-based recovery
    - Performance monitoring
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: int = 60,
        success_threshold: int = 3
    ):
        super().__init__("circuit_breaker", 1)
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.success_threshold = success_threshold
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.circuit_state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self._lock = threading.Lock()

    def _execute_recovery(self, exception: Exception, error_context: ErrorContext) -> Dict[str, Any]:
        """Execute circuit breaker logic"""
        with self._lock:
            current_time = datetime.utcnow()

            # Check if circuit should be opened
            if self.circuit_state == "CLOSED":
                self.failure_count += 1
                self.last_failure_time = current_time

                if self.failure_count >= self.failure_threshold:
                    self.circuit_state = "OPEN"
                    logger.warning(
                        f"Circuit breaker opened after {self.failure_count} failures",
                        failure_count=self.failure_count,
                        failure_threshold=self.failure_threshold
                    )

            # Check if circuit should transition to HALF_OPEN
            elif self.circuit_state == "OPEN":
                if self.last_failure_time and \
                   (current_time - self.last_failure_time).total_seconds() >= self.timeout:
                    self.circuit_state = "HALF_OPEN"
                    self.success_count = 0
                    logger.info("Circuit breaker transitioning to HALF_OPEN")

            # Handle circuit states
            if self.circuit_state == "OPEN":
                return {
                    'success': False,
                    'circuit_state': 'OPEN',
                    'message': 'Circuit breaker is open - operation blocked',
                    'metadata': {
                        'circuit_breaker_strategy': 'block_requests',
                        'failure_count': self.failure_count,
                        'timeout_remaining': self.timeout - (current_time - self.last_failure_time).total_seconds()
                    }
                }

            elif self.circuit_state == "HALF_OPEN":
                # Allow limited requests to test if service is recovered
                if self.success_count < self.success_threshold:
                    # Simulate service test
                    service_recovered = self._test_service_health()

                    if service_recovered:
                        self.success_count += 1
                        if self.success_count >= self.success_threshold:
                            self.circuit_state = "CLOSED"
                            self.failure_count = 0
                            logger.info("Circuit breaker closed - service recovered")

                        return {
                            'success': True,
                            'circuit_state': 'HALF_OPEN',
                            'message': 'Service test successful',
                            'metadata': {
                                'circuit_breaker_strategy': 'test_service',
                                'success_count': self.success_count,
                                'success_threshold': self.success_threshold
                            }
                        }
                    else:
                        self.circuit_state = "OPEN"
                        self.last_failure_time = current_time
                        return {
                            'success': False,
                            'circuit_state': 'OPEN',
                            'message': 'Service test failed - circuit reopened',
                            'metadata': {
                                'circuit_breaker_strategy': 'test_service_failed',
                                'failure_count': self.failure_count
                            }
                        }

            # Circuit is CLOSED - allow normal operation
            return {
                'success': True,
                'circuit_state': 'CLOSED',
                'message': 'Circuit breaker is closed - normal operation',
                'metadata': {
                    'circuit_breaker_strategy': 'normal_operation',
                    'failure_count': self.failure_count
                }
            }

    def _test_service_health(self) -> bool:
        """Test if the service is healthy"""
        # Simulate service health check
        # In real implementation, this would ping the service
        return random.random() > 0.3  # 70% chance of success

    def get_circuit_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state"""
        with self._lock:
            return {
                'state': self.circuit_state,
                'failure_count': self.failure_count,
                'success_count': self.success_count,
                'last_failure_time': self.last_failure_time.isoformat() if self.last_failure_time else None,
                'failure_threshold': self.failure_threshold,
                'success_threshold': self.success_threshold,
                'timeout': self.timeout
            }


# Export all classes
__all__ = [
    'RecoveryStrategy',
    'RetryStrategy',
    'FallbackStrategy',
    'GracefulDegradationStrategy',
    'CircuitBreakerStrategy',
    'RecoveryResult',
    'RecoveryAttempt'
]
