"""
Centralized Error Handler

Comprehensive error handling system that processes, classifies, and manages
all errors in the valuation engine with recovery strategies and alerting.

ARCHITECTURE:
- Centralized error processing and classification
- Error routing and recovery strategy execution
- Error reporting and alerting
- Graceful degradation logic
- Audit trail integration
- Performance impact tracking

FEATURES:
- Automatic error classification
- Recovery strategy execution
- Error reporting and alerting
- Graceful degradation
- Audit trail logging
- Performance monitoring
"""

import sys
import traceback
from typing import Dict, Any, Optional, List, Union, Callable
from datetime import datetime, timezone
from dataclasses import dataclass, field
import threading
from enum import Enum

from src.utils.logging import get_logger, log_audit_event
from src.utils.logging_context import get_current_context
from src.utils.exceptions import ValuationEngineError, MethodologyError
from src.errors.error_context import create_error_context, ErrorContext
from src.errors.error_types import ValuationError, is_retryable_error
from src.errors.recovery_strategies import (
    RecoveryStrategy, RetryStrategy, FallbackStrategy, 
    GracefulDegradationStrategy, CircuitBreakerStrategy
)

logger = get_logger(__name__)


_SEVERITY_ORDER = ["low", "medium", "high", "critical"]


class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    def __lt__(self, other):
        if not isinstance(other, ErrorSeverity):
            return NotImplemented
        return _SEVERITY_ORDER.index(self.value) < _SEVERITY_ORDER.index(other.value)

    def __le__(self, other):
        if not isinstance(other, ErrorSeverity):
            return NotImplemented
        return _SEVERITY_ORDER.index(self.value) <= _SEVERITY_ORDER.index(other.value)

    def __gt__(self, other):
        if not isinstance(other, ErrorSeverity):
            return NotImplemented
        return _SEVERITY_ORDER.index(self.value) > _SEVERITY_ORDER.index(other.value)

    def __ge__(self, other):
        if not isinstance(other, ErrorSeverity):
            return NotImplemented
        return _SEVERITY_ORDER.index(self.value) >= _SEVERITY_ORDER.index(other.value)


class ErrorCategory(Enum):
    """Error categories for classification"""
    CALCULATION = "calculation"
    DATA_QUALITY = "data_quality"
    SERVICE_INTEGRATION = "service_integration"
    PRIVACY_VIOLATION = "privacy_violation"
    BUSINESS_LOGIC = "business_logic"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    SYSTEM = "system"
    UNKNOWN = "unknown"


@dataclass
class ErrorHandlingResult:
    """Result of error handling operation"""
    success: bool
    error_id: str
    error_type: str
    severity: ErrorSeverity
    category: ErrorCategory
    is_retryable: bool
    recovery_strategy: Optional[str] = None
    recovery_attempted: bool = False
    recovery_successful: bool = False
    fallback_used: bool = False
    user_message: Optional[str] = None
    technical_details: Optional[str] = None
    audit_logged: bool = False
    alert_sent: bool = False
    context: Dict[str, Any] = field(default_factory=dict)


class ErrorHandler:
    """
    Centralized error handler for the valuation engine.

    Features:
    - Automatic error classification
    - Recovery strategy execution
    - Error reporting and alerting
    - Graceful degradation
    - Audit trail logging
    - Performance monitoring
    """

    def __init__(self):
        self._error_counts: Dict[str, int] = {}
        self._recovery_strategies: Dict[str, RecoveryStrategy] = {}
        self._alert_thresholds: Dict[ErrorSeverity, int] = {
            ErrorSeverity.LOW: 100,
            ErrorSeverity.MEDIUM: 50,
            ErrorSeverity.HIGH: 10,
            ErrorSeverity.CRITICAL: 1
        }
        self._lock = threading.RLock()

        # Initialize recovery strategies
        self._initialize_recovery_strategies()

    def _initialize_recovery_strategies(self):
        """Initialize recovery strategies for different error types"""
        self._recovery_strategies = {
            'retry': RetryStrategy(max_retries=3, backoff_factor=2.0),
            'fallback': FallbackStrategy(fallback_methods=[self._default_fallback]),
            'graceful_degradation': GracefulDegradationStrategy(),
            'circuit_breaker': CircuitBreakerStrategy(failure_threshold=5, timeout=60)
        }

    def _default_fallback(self, exception, error_context):
        """Default fallback that gracefully handles errors without specific fallback logic"""
        return {'handled': True, 'method': 'default_error_handling'}

    def handle_error(
        self,
        exception: Exception,
        context: Dict[str, Any] = None,
        recovery_strategy: str = None,
        user_message: str = None,
        alert: bool = None
    ) -> ErrorHandlingResult:
        """
        Handle an error with comprehensive processing.

        Args:
            exception: The exception to handle
            context: Additional context information
            recovery_strategy: Specific recovery strategy to use
            user_message: User-friendly error message
            alert: Whether to send alerts (auto-determined if None)

        Returns:
            ErrorHandlingResult with handling details
        """
        if exception is None:
            return ErrorHandlingResult(
                success=False,
                error_id=f"err_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_none",
                error_type="ERROR_HANDLER_FAILURE",
                severity=ErrorSeverity.CRITICAL,
                category=ErrorCategory.SYSTEM,
                is_retryable=False,
                user_message="Invalid error: None exception provided"
            )

        try:
            # Create error context
            error_context = create_error_context(exception, context)

            # Classify error
            error_type = type(exception).__name__
            severity = self._determine_severity(exception)
            category = self._categorize_error(exception)
            is_retryable = is_retryable_error(exception)

            # Update error counts
            with self._lock:
                self._error_counts[error_type] = self._error_counts.get(error_type, 0) + 1

            # Determine recovery strategy
            if not recovery_strategy:
                recovery_strategy = self._determine_recovery_strategy(exception, category)

            # Execute recovery strategy
            recovery_result = self._execute_recovery_strategy(
                exception, recovery_strategy, error_context
            )

            # Generate user message
            if not user_message:
                user_message = self._generate_user_message(exception, severity)

            # Determine if alert should be sent
            if alert is None:
                alert = self._should_send_alert(severity, error_type)

            # Send alert if needed
            alert_sent = False
            if alert:
                alert_sent = self._send_alert(exception, severity, error_context)

            # Log audit event
            audit_logged = self._log_audit_event(exception, error_context, severity)

            # Build result context by merging error context, handler context, and exception context
            result_context = error_context.to_dict()
            if context:
                result_context.update(context)
            if hasattr(exception, 'context') and isinstance(exception.context, dict):
                result_context.update(exception.context)

            # Create result
            result = ErrorHandlingResult(
                success=recovery_result.get('success', False),
                error_id=error_context.error_id,
                error_type=error_type,
                severity=severity,
                category=category,
                is_retryable=is_retryable,
                recovery_strategy=recovery_strategy,
                recovery_attempted=recovery_result.get('attempted', False),
                recovery_successful=recovery_result.get('successful', False),
                fallback_used=recovery_result.get('fallback_used', False),
                user_message=user_message,
                technical_details=self._generate_technical_details(exception, error_context),
                audit_logged=audit_logged,
                alert_sent=alert_sent,
                context=result_context,
            )

            # Log the error handling result
            logger.error(
                f"Error handled: {error_type}",
                error_id=error_context.error_id,
                error_type=error_type,
                severity=severity.value,
                category=category.value,
                is_retryable=is_retryable,
                recovery_strategy=recovery_strategy,
                recovery_successful=recovery_result.get('successful', False),
                alert_sent=alert_sent,
                audit_logged=audit_logged
            )

            return result

        except Exception as handler_error:
            # If error handling itself fails, log and return basic result
            logger.critical(
                f"Error handler failed: {handler_error}",
                original_error=str(exception),
                handler_error=str(handler_error),
                exc_info=True
            )

            return ErrorHandlingResult(
                success=False,
                error_id=f"handler_fail_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                error_type="ERROR_HANDLER_FAILURE",
                severity=ErrorSeverity.CRITICAL,
                category=ErrorCategory.SYSTEM,
                is_retryable=False,
                user_message="An unexpected error occurred in the error handling system",
                technical_details=f"Handler error: {str(handler_error)}"
            )

    def _determine_severity(self, exception: Exception) -> ErrorSeverity:
        """Determine error severity based on exception type and context"""
        if isinstance(exception, ValuationError):
            severity_map = {
                'critical': ErrorSeverity.CRITICAL,
                'error': ErrorSeverity.HIGH,
                'warning': ErrorSeverity.MEDIUM,
                'info': ErrorSeverity.LOW
            }
            return severity_map.get(exception.severity, ErrorSeverity.HIGH)
        elif isinstance(exception, (ValueError, TypeError, AttributeError)):
            return ErrorSeverity.MEDIUM
        elif isinstance(exception, (ConnectionError, TimeoutError)):
            return ErrorSeverity.HIGH
        elif isinstance(exception, (PermissionError, OSError)):
            return ErrorSeverity.CRITICAL
        else:
            return ErrorSeverity.MEDIUM

    def _categorize_error(self, exception: Exception) -> ErrorCategory:
        """Categorize error based on exception type"""
        if isinstance(exception, ValuationError):
            if 'calculation' in exception.error_code.lower():
                return ErrorCategory.CALCULATION
            elif 'data' in exception.error_code.lower():
                return ErrorCategory.DATA_QUALITY
            elif 'service' in exception.error_code.lower():
                return ErrorCategory.SERVICE_INTEGRATION
            elif 'privacy' in exception.error_code.lower():
                return ErrorCategory.PRIVACY_VIOLATION
            elif 'business' in exception.error_code.lower():
                return ErrorCategory.BUSINESS_LOGIC
            elif 'auth' in exception.error_code.lower():
                return ErrorCategory.AUTHENTICATION
            else:
                return ErrorCategory.SYSTEM
        elif isinstance(exception, (ValueError, TypeError, AttributeError)):
            return ErrorCategory.DATA_QUALITY
        elif isinstance(exception, (ConnectionError, TimeoutError)):
            return ErrorCategory.SERVICE_INTEGRATION
        elif isinstance(exception, (PermissionError, OSError)):
            return ErrorCategory.AUTHORIZATION
        else:
            return ErrorCategory.UNKNOWN

    def _determine_recovery_strategy(self, exception: Exception, category: ErrorCategory) -> str:
        """Determine appropriate recovery strategy based on error type"""
        if category == ErrorCategory.SERVICE_INTEGRATION:
            return 'retry'
        elif category == ErrorCategory.CALCULATION:
            return 'fallback'
        elif category == ErrorCategory.DATA_QUALITY:
            return 'graceful_degradation'
        elif category == ErrorCategory.PRIVACY_VIOLATION:
            return 'circuit_breaker'
        else:
            return 'fallback'

    def _execute_recovery_strategy(
        self, 
        exception: Exception, 
        strategy_name: str, 
        error_context: ErrorContext
    ) -> Dict[str, Any]:
        """Execute the specified recovery strategy"""
        try:
            strategy = self._recovery_strategies.get(strategy_name)
            if not strategy:
                return {'success': False, 'attempted': False, 'error': 'Strategy not found'}

            result = strategy.execute(exception, error_context)
            return {
                'success': result.get('success', False),
                'attempted': True,
                'successful': result.get('success', False),
                'fallback_used': result.get('fallback_used', False),
                'details': result
            }
        except Exception as recovery_error:
            logger.error(
                f"Recovery strategy failed: {recovery_error}",
                strategy=strategy_name,
                original_error=str(exception),
                recovery_error=str(recovery_error)
            )
            return {
                'success': False,
                'attempted': True,
                'successful': False,
                'error': str(recovery_error)
            }

    def _generate_user_message(self, exception: Exception, severity: ErrorSeverity) -> str:
        """Generate user-friendly error message"""
        if isinstance(exception, ValuationError) and exception.recovery_suggestion:
            return f"{exception.message}. {exception.recovery_suggestion}"
        elif severity == ErrorSeverity.CRITICAL:
            return "A critical error occurred. Please contact support immediately."
        elif severity == ErrorSeverity.HIGH:
            return "An error occurred. Please try again or contact support if the problem persists."
        else:
            return "A minor issue occurred. The system will attempt to continue."

    def _generate_technical_details(self, exception: Exception, error_context: ErrorContext) -> str:
        """Generate technical details for debugging"""
        details = [
            f"Error Type: {type(exception).__name__}",
            f"Error Message: {str(exception)}",
            f"Error ID: {error_context.error_id}",
            f"Timestamp: {error_context.timestamp.isoformat()}"
        ]

        if error_context.calculation_step:
            details.append(f"Calculation Step: {error_context.calculation_step}")

        if error_context.performance_metrics:
            details.append(f"Performance: {error_context.performance_metrics}")

        return " | ".join(details)

    def _should_send_alert(self, severity: ErrorSeverity, error_type: str) -> bool:
        """Determine if an alert should be sent based on severity and frequency"""
        with self._lock:
            error_count = self._error_counts.get(error_type, 0)
            threshold = self._alert_thresholds.get(severity, 10)
            return error_count >= threshold

    def _send_alert(self, exception: Exception, severity: ErrorSeverity, error_context: ErrorContext) -> bool:
        """Send alert for critical errors"""
        try:
            # In a real implementation, this would send alerts to monitoring systems
            # For now, we'll just log the alert
            logger.critical(
                f"ALERT: {severity.value.upper()} error occurred",
                error_type=type(exception).__name__,
                error_message=str(exception),
                error_id=error_context.error_id,
                severity=severity.value,
                timestamp=error_context.timestamp.isoformat()
            )
            return True
        except Exception as alert_error:
            logger.error(f"Failed to send alert: {alert_error}")
            return False

    def _log_audit_event(self, exception: Exception, error_context: ErrorContext, severity: ErrorSeverity) -> bool:
        """Log audit event for error"""
        try:
            log_audit_event(
                event_type="ERROR_OCCURRED",
                actor="system",
                action="error_handling",
                resource="valuation_engine",
                data={
                    'error_type': type(exception).__name__,
                    'error_message': str(exception),
                    'severity': severity.value,
                    'error_id': error_context.error_id,
                    'timestamp': error_context.timestamp.isoformat()
                }
            )
            return True
        except Exception as audit_error:
            logger.error(f"Failed to log audit event: {audit_error}")
            return False

    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics for monitoring"""
        with self._lock:
            return {
                'error_counts': self._error_counts.copy(),
                'total_errors': sum(self._error_counts.values()),
                'unique_error_types': len(self._error_counts),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

    def reset_error_counts(self):
        """Reset error counts (useful for testing)"""
        with self._lock:
            self._error_counts.clear()


# Global error handler instance
_error_handler = ErrorHandler()


def handle_error(
    exception: Exception,
    context: Dict[str, Any] = None,
    recovery_strategy: str = None,
    user_message: str = None,
    alert: bool = None
) -> ErrorHandlingResult:
    """
    Handle an error using the global error handler.

    Args:
        exception: The exception to handle
        context: Additional context information
        recovery_strategy: Specific recovery strategy to use
        user_message: User-friendly error message
        alert: Whether to send alerts

    Returns:
        ErrorHandlingResult with handling details
    """
    try:
        return _error_handler.handle_error(
            exception, context, recovery_strategy, user_message, alert
        )
    except Exception as handler_error:
        logger.critical(
            f"Global error handler failed: {handler_error}",
            exc_info=True
        )
        return ErrorHandlingResult(
            success=False,
            error_id=f"handler_fail_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            error_type="ERROR_HANDLER_FAILURE",
            severity=ErrorSeverity.CRITICAL,
            category=ErrorCategory.SYSTEM,
            is_retryable=False,
            user_message="An unexpected error occurred in the error handling system",
            technical_details=f"Handler error: {str(handler_error)}"
        )


def classify_error(exception: Exception) -> str:
    """Classify an error using the global error handler"""
    return _error_handler._categorize_error(exception).value


def get_recovery_strategy(exception: Exception) -> str:
    """Get recommended recovery strategy for an error"""
    category = _error_handler._categorize_error(exception)
    return _error_handler._determine_recovery_strategy(exception, category)


# Export main classes and functions
__all__ = [
    'ErrorHandler',
    'ErrorHandlingResult',
    'ErrorSeverity',
    'ErrorCategory',
    'handle_error',
    'classify_error',
    'get_recovery_strategy'
]
