"""
Error Types for Valuation Engine

Comprehensive error taxonomy with specific error types for different scenarios.
Each error type includes specific context, recovery suggestions, and user-friendly messages.

ARCHITECTURE:
- Import core exceptions from src.utils.exceptions (canonical source)
- Define specialized exceptions unique to this module
- Provide backward compatibility through re-exports

ERROR CATEGORIES:
- Core Exceptions: Imported from src.utils.exceptions
- Specialized Exceptions: Authentication, Authorization, Privacy, Rate Limiting
- Extended Functionality: ValuationError with metadata and recovery suggestions
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import abc
import traceback
import sys
from decimal import Decimal

# Import core exceptions from canonical source
from src.utils.exceptions import (
    # Base
    ValuationEngineError,
    
    # Calculation
    CalculationError,
    DCFCalculationError,
    MultiplesCalculationError,
    SynthesisError,
    ValuationRangeError,
    StepExecutionError,
    
    # Data
    DataQualityError,
    DataValidationError,
    MissingDataError,
    DataInconsistencyError,
    
    # External Services
    ExternalServiceError,
    DatabaseError,
    CacheError,
    APIError,
    MarketDataError,
    
    # Configuration
    ConfigurationError,
    DependencyError,
    BusinessTypeError,
    MethodologyError,
    
    # Business Logic
    BusinessLogicError,
    InvalidDiscountError,
    InvalidMultipleError,
    
    # Template & Rendering
    TemplateRenderError,
    DocumentGenerationError,
    
    # Timeout
    ValuationTimeoutError,
    StepTimeoutError,
    
    # Circuit Breaker
    CircuitBreakerError,
    
    # Aliases
    ValidationError,
)


# ==================== EXTENDED BASE CLASS ====================

class ValuationError(Exception, metaclass=abc.ABCMeta):
    """
    Extended base exception class for valuation engine errors.
    
    Provides enhanced functionality including:
    - Error context and metadata
    - Recovery strategy suggestions
    - User-friendly error messages
    - Audit trail information
    
    Uses ABCMeta to register ValuationEngineError (and all its subclasses)
    as virtual subclasses, unifying the two exception hierarchies.
    """

    def __init__(
        self,
        message: str,
        error_code: str = None,
        context: Dict[str, Any] = None,
        recovery_suggestion: str = None,
        severity: str = "error",
        is_retryable: bool = False,
        original_exception: Exception = None,
        correlation_id: str = None,
        request_id: str = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.context = context or {}
        self.recovery_suggestion = recovery_suggestion
        self.severity = severity
        self.is_retryable = is_retryable
        self.original_exception = original_exception
        self.correlation_id = correlation_id
        self.request_id = request_id
        self.timestamp = datetime.now(timezone.utc)
        self.stack_trace = traceback.format_exc()

        # Add correlation ID and request ID to context if provided
        if correlation_id:
            self.context['correlation_id'] = correlation_id
        if request_id:
            self.context['request_id'] = request_id

        # Add error metadata
        self.metadata = {
            'error_type': self.__class__.__name__,
            'error_code': self.error_code,
            'severity': self.severity,
            'is_retryable': self.is_retryable,
            'timestamp': self.timestamp.isoformat(),
            'context': self.context
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for logging"""
        return {
            'message': self.message,
            'error_code': self.error_code,
            'context': self.context,
            'recovery_suggestion': self.recovery_suggestion,
            'severity': self.severity,
            'is_retryable': self.is_retryable,
            'timestamp': self.timestamp.isoformat(),
            'stack_trace': self.stack_trace,
            'metadata': self.metadata
        }


# Register ValuationEngineError hierarchy as virtual subclasses of ValuationError.
# This allows isinstance(CalculationError(...), ValuationError) to return True,
# unifying the core exceptions with the extended error system.
ValuationError.register(ValuationEngineError)


# ==================== SPECIALIZED EXCEPTIONS (Unique to this module) ====================

class AuthenticationError(ValuationError):
    """Authentication error"""

    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            error_code="AUTHENTICATION_ERROR",
            severity="critical",
            recovery_suggestion="Check authentication credentials",
            **kwargs
        )


class AuthorizationError(ValuationError):
    """Authorization error"""

    def __init__(self, message: str, resource: str = None, **kwargs):
        super().__init__(
            message,
            error_code="AUTHORIZATION_ERROR",
            severity="critical",
            recovery_suggestion="Check user permissions",
            **kwargs
        )
        self.resource = resource
        if resource:
            self.context['resource'] = resource


class RateLimitError(ValuationError):
    """Rate limit exceeded error"""

    def __init__(self, message: str, limit: int = None, **kwargs):
        super().__init__(
            message,
            error_code="RATE_LIMIT_ERROR",
            is_retryable=True,
            recovery_suggestion="Wait and retry the operation",
            **kwargs
        )
        self.limit = limit
        if limit:
            self.context['rate_limit'] = limit


class PrivacyViolationError(ValuationError):
    """Privacy violation error"""

    def __init__(self, message: str, violation_type: str = None, **kwargs):
        super().__init__(
            message,
            error_code="PRIVACY_VIOLATION_ERROR",
            severity="critical",
            recovery_suggestion="Review data classification and privacy settings",
            **kwargs
        )
        self.violation_type = violation_type
        if violation_type:
            self.context['violation_type'] = violation_type


class ServiceIntegrationError(ValuationError):
    """Error in service integration (extended version with metadata)"""

    def __init__(self, message: str, service_name: str = None, **kwargs):
        super().__init__(
            message,
            error_code="SERVICE_INTEGRATION_ERROR",
            is_retryable=True,
            recovery_suggestion="Retry the operation or check service availability",
            **kwargs
        )
        self.service_name = service_name
        if service_name:
            self.context['service_name'] = service_name


# Register core DatabaseError and CacheError as virtual subclasses
ServiceIntegrationError.register(DatabaseError)
ServiceIntegrationError.register(CacheError)


class ExternalAPIError(ServiceIntegrationError):
    """External API error (extended version)"""

    def __init__(self, message: str, api_endpoint: str = None, status_code: int = None, **kwargs):
        super().__init__(
            message,
            service_name="External API",
            **kwargs
        )
        self.error_code = "EXTERNAL_API_ERROR"
        self.metadata['error_code'] = "EXTERNAL_API_ERROR"
        self.api_endpoint = api_endpoint
        self.status_code = status_code
        if api_endpoint:
            self.context['api_endpoint'] = api_endpoint
        if status_code:
            self.context['status_code'] = status_code


class DomainError(ValuationError):
    """Domain rule violation error"""

    def __init__(self, message: str, rule: str = None, **kwargs):
        super().__init__(
            message,
            error_code="DOMAIN_ERROR",
            recovery_suggestion="Check domain rules and business constraints",
            **kwargs
        )
        self.rule = rule
        if rule:
            self.context['domain_rule'] = rule


class TimeoutError(ValuationError):
    """Timeout error (extended version with metadata)"""

    def __init__(self, message: str, timeout_seconds: Decimal = None, **kwargs):
        super().__init__(
            message,
            error_code="SERVICE_INTEGRATION_ERROR",
            severity="warning",
            is_retryable=True,
            recovery_suggestion="Retry the operation with longer timeout",
            **kwargs
        )
        self.timeout_seconds = timeout_seconds
        if timeout_seconds:
            self.context['timeout_seconds'] = timeout_seconds


class DiscountCalculationError(CalculationError):
    """Error in discount calculations (size, liquidity, control, etc.)"""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("calculation_type", "Discount")
        super().__init__(message, **kwargs)


class RangeCalculationError(CalculationError):
    """Error in valuation range calculations"""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("calculation_type", "Range")
        super().__init__(message, **kwargs)


# Alias for backward compatibility
MultipleCalculationError = MultiplesCalculationError


# ==================== ERROR UTILITIES ====================

def classify_error(exception: Exception) -> str:
    """Classify an exception into error categories"""
    if isinstance(exception, ValuationError):
        return exception.error_code
    elif isinstance(exception, ValuationEngineError):
        return exception.__class__.__name__
    elif isinstance(exception, (ValueError, TypeError, AttributeError)):
        return "VALIDATION_ERROR"
    elif isinstance(exception, (ConnectionError, TimeoutError)):
        return "SERVICE_INTEGRATION_ERROR"
    elif isinstance(exception, (PermissionError, OSError)):
        return "AUTHORIZATION_ERROR"
    else:
        return "UNKNOWN_ERROR"


def is_retryable_error(exception: Exception) -> bool:
    """Determine if an error is retryable"""
    if isinstance(exception, ValuationError):
        return exception.is_retryable
    elif isinstance(exception, (ConnectionError, TimeoutError)):
        return True
    elif isinstance(exception, (ValueError, TypeError, AttributeError)):
        return False
    else:
        return False


def get_error_severity(exception: Exception) -> str:
    """Get the severity level of an error"""
    if isinstance(exception, ValuationError):
        return exception.severity
    elif isinstance(exception, (ValueError, TypeError, AttributeError)):
        return "error"
    elif isinstance(exception, (ConnectionError, TimeoutError)):
        return "warning"
    else:
        return "error"


# ==================== EXPORTS ====================

# Re-export all exceptions for backward compatibility
__all__ = [
    # Extended base class
    'ValuationError',
    
    # Core exceptions (imported from src.utils.exceptions)
    'ValuationEngineError',
    'CalculationError',
    'DCFCalculationError',
    'MultiplesCalculationError',
    'SynthesisError',
    'ValuationRangeError',
    'StepExecutionError',
    'DataQualityError',
    'DataValidationError',
    'MissingDataError',
    'DataInconsistencyError',
    'ExternalServiceError',
    'DatabaseError',
    'CacheError',
    'APIError',
    'MarketDataError',
    'ConfigurationError',
    'DependencyError',
    'BusinessTypeError',
    'MethodologyError',
    'BusinessLogicError',
    'InvalidDiscountError',
    'InvalidMultipleError',
    'TemplateRenderError',
    'DocumentGenerationError',
    'ValuationTimeoutError',
    'StepTimeoutError',
    'CircuitBreakerError',
    'ValidationError',
    
    # Specialized exceptions (unique to this module)
    'AuthenticationError',
    'AuthorizationError',
    'RateLimitError',
    'PrivacyViolationError',
    'ServiceIntegrationError',
    'ExternalAPIError',
    'DomainError',
    'TimeoutError',
    'DiscountCalculationError',
    'RangeCalculationError',
    'MultipleCalculationError',
    
    # Utilities
    'classify_error',
    'is_retryable_error',
    'get_error_severity'
]
