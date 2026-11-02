"""
Error Handling Framework

Comprehensive error handling system for the valuation engine with detailed error taxonomy,
context capture, and recovery strategies.

ARCHITECTURE:
- Comprehensive error taxonomy with specific error types
- Error context capture with full stack trace and local variables
- Centralized error processing and classification
- Recovery strategy execution
- Error reporting and alerting
- Graceful degradation logic

USAGE:
    Import ValuationError, CalculationError, ErrorHandler, and related types from this package.
    In application code, catch CalculationError (and siblings) and route through ErrorHandler.handle
    with appropriate context (for example the inputs that triggered the failure).
"""

from src.errors.error_types import (
    ValuationError,
    CalculationError,
    DataQualityError,
    ServiceIntegrationError,
    PrivacyViolationError,
    BusinessLogicError,
    DCFCalculationError,
    MultiplesCalculationError,
    MultipleCalculationError,
    SynthesisError,
    DiscountCalculationError,
    RangeCalculationError,
    ValidationError,
    DatabaseError,
    ExternalAPIError,
    CacheError,
    AuthenticationError,
    AuthorizationError,
    RateLimitError,
    TimeoutError,
    ConfigurationError,
    DependencyError,
    MarketDataError,
    DomainError
)

from .error_context import (
    ErrorContext,
    ErrorContextCapture,
    create_error_context
)

from .error_handler import (
    ErrorHandler,
    handle_error,
    classify_error,
    get_recovery_strategy
)

from .recovery_strategies import (
    RecoveryStrategy,
    RetryStrategy,
    FallbackStrategy,
    GracefulDegradationStrategy,
    CircuitBreakerStrategy
)

__all__ = [
    # Error Types
    'ValuationError',
    'CalculationError', 
    'DataQualityError',
    'ServiceIntegrationError',
    'PrivacyViolationError',
    'BusinessLogicError',
    'DCFCalculationError',
    'MultiplesCalculationError',
    'MultipleCalculationError',
    'SynthesisError',
    'DiscountCalculationError',
    'RangeCalculationError',
    'ValidationError',
    'DatabaseError',
    'ExternalAPIError',
    'CacheError',
    'AuthenticationError',
    'AuthorizationError',
    'RateLimitError',
    'TimeoutError',
    'ConfigurationError',
    'DependencyError',
    'MarketDataError',
    'DomainError',
    'TemplateRenderError',

    # Error Context
    'ErrorContext',
    'ErrorContextCapture',
    'create_error_context',

    # Error Handler
    'ErrorHandler',
    'handle_error',
    'classify_error',
    'get_recovery_strategy',

    # Recovery Strategies
    'RecoveryStrategy',
    'RetryStrategy',
    'FallbackStrategy',
    'GracefulDegradationStrategy',
    'CircuitBreakerStrategy'
]
