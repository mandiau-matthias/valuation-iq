"""
Custom Exception Classes for Valuation Engine

This module provides specific exception types for different error scenarios,
enabling more precise error handling and better error messages.

Author: Upswitch Engineering Team
Date: November 2025
Status: Production Ready
"""

from decimal import Decimal
from typing import Any, Dict, Optional

# ==================== BASE EXCEPTIONS ====================


class ValuationEngineError(Exception):
    """Base exception for all valuation engine errors."""

    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
        severity: str = "error",
        recovery_suggestion: Optional[str] = None,
        is_retryable: bool = False,
        **kwargs,
    ):
        self.message = message
        self.context = context or {}
        self.error_code = error_code or self.__class__.__name__
        self.severity = severity
        self.recovery_suggestion = recovery_suggestion
        self.is_retryable = is_retryable
        if kwargs:
            self.context.update(kwargs)
            for key, value in kwargs.items():
                if not hasattr(self, key):
                    setattr(self, key, value)
        super().__init__(self.message)

    def add_context(self, **kwargs) -> None:
        """Add additional context to the error."""
        self.context.update(kwargs)
        for key, value in kwargs.items():
            if not hasattr(self, key):
                setattr(self, key, value)

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for logging."""
        return {
            "message": self.message,
            "error_code": self.error_code,
            "context": self.context,
            "severity": self.severity,
            "recovery_suggestion": self.recovery_suggestion,
            "is_retryable": self.is_retryable,
        }


# ==================== DATA ERRORS ====================


class DataValidationError(ValuationEngineError):
    """Raised when input data fails validation."""

    pass


class DataQualityError(ValuationEngineError):
    """Raised when data quality is insufficient for calculation."""

    pass


class MissingDataError(ValuationEngineError):
    """Raised when required data is missing."""

    def __init__(
        self,
        message: str,
        missing_fields: Optional[list] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        self.missing_fields = missing_fields or []
        super().__init__(message, context)


class DataInconsistencyError(ValuationEngineError):
    """Raised when data contains logical inconsistencies."""

    pass


# ==================== CALCULATION ERRORS ====================


class CalculationError(ValuationEngineError):
    """Base exception for calculation-related errors."""

    pass


class StepExecutionError(CalculationError):
    """Raised when a calculation step fails to execute."""

    def __init__(
        self,
        message: str,
        step_number: Optional[int] = None,
        step_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        self.step_number = step_number
        self.step_name = step_name
        super().__init__(message, context)


class DependencyError(CalculationError):
    """Raised when step dependencies are not satisfied."""

    def __init__(
        self,
        message: str,
        missing_steps: Optional[list] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        self.missing_steps = missing_steps or []
        super().__init__(message, context)


class MultiplesCalculationError(CalculationError):
    """Raised when multiples calculation fails."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("calculation_type", "Multiples")
        super().__init__(message, **kwargs)


class DCFCalculationError(CalculationError):
    """Raised when DCF calculation fails."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("calculation_type", "DCF")
        super().__init__(message, **kwargs)


class ValuationRangeError(CalculationError):
    """Raised when valuation range calculation fails."""

    pass


class SynthesisError(CalculationError):
    """Error in valuation synthesis."""

    pass


# ==================== EXTERNAL SERVICE ERRORS ====================


class ExternalServiceError(ValuationEngineError):
    """Base exception for external service errors."""

    pass


class APIError(ExternalServiceError):
    """Raised when external API call fails."""

    def __init__(
        self,
        message: str,
        api_name: Optional[str] = None,
        status_code: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        self.api_name = api_name
        self.status_code = status_code
        super().__init__(message, context)


class DatabaseError(ExternalServiceError):
    """Raised when database operation fails."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("service_name", "Database")
        super().__init__(message, **kwargs)


class CacheError(ExternalServiceError):
    """Raised when cache operation fails."""

    pass


class MarketDataError(ExternalServiceError):
    """Market data retrieval or processing error."""

    pass


# ==================== CONFIGURATION ERRORS ====================


class ConfigurationError(ValuationEngineError):
    """Raised when configuration is invalid or missing."""

    pass


class BusinessTypeError(ConfigurationError):
    """Raised when business type is invalid or not supported."""

    pass


class MethodologyError(ConfigurationError):
    """Raised when valuation methodology is invalid or not applicable."""

    pass


# ==================== TIMEOUT ERRORS ====================


class ValuationTimeoutError(ValuationEngineError):
    """Raised when valuation calculation exceeds timeout."""

    def __init__(
        self,
        message: str,
        timeout_seconds: Optional[Decimal] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        self.timeout_seconds = timeout_seconds
        super().__init__(message, context)


class StepTimeoutError(ValuationTimeoutError):
    """Raised when a specific step exceeds timeout."""

    def __init__(
        self,
        message: str,
        step_number: Optional[int] = None,
        step_name: Optional[str] = None,
        timeout_seconds: Optional[Decimal] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        self.step_number = step_number
        self.step_name = step_name
        super().__init__(message, timeout_seconds, context)


# ==================== CIRCUIT BREAKER ERRORS ====================


class CircuitBreakerError(ExternalServiceError):
    """Raised when circuit breaker is open."""

    def __init__(
        self,
        message: str,
        circuit_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        self.circuit_name = circuit_name
        super().__init__(message, context)


# ==================== BUSINESS LOGIC ERRORS ====================


class BusinessLogicError(ValuationEngineError):
    """Raised when business logic validation fails."""

    pass


class DomainError(BusinessLogicError):
    """Raised when domain rule validation fails."""

    pass


class InvalidDiscountError(BusinessLogicError):
    """Raised when discount calculation produces invalid result."""

    pass


class InvalidMultipleError(BusinessLogicError):
    """Raised when market multiple is invalid or unrealistic."""

    def __init__(
        self,
        message: str,
        multiple_type: Optional[str] = None,
        value: Optional[Any] = None,
        valid_range: Optional[tuple] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize invalid multiple error with rich context.

        Args:
            message: Error message
            multiple_type: Type of multiple (e.g., "EV/EBITDA", "EV/Revenue")
            value: The invalid value
            valid_range: Tuple of (min, max) valid range
            context: Additional context
        """
        self.multiple_type = multiple_type
        self.value = value
        self.valid_range = valid_range
        super().__init__(message, context)


# ==================== TEMPLATE & RENDERING ERRORS ====================


class TemplateRenderError(ValuationEngineError):
    """Template rendering error."""

    pass


class DocumentGenerationError(ValuationEngineError):
    """Document generation error."""

    pass


# ==================== ALIASES ====================

# Alias for backward compatibility
ValidationError = DataValidationError


# ==================== EXPORT ====================

__all__ = [
    # Base
    "ValuationEngineError",
    # Data
    "DataValidationError",
    "DataQualityError",
    "MissingDataError",
    "DataInconsistencyError",
    # Calculation
    "CalculationError",
    "StepExecutionError",
    "DependencyError",
    "MultiplesCalculationError",
    "DCFCalculationError",
    "ValuationRangeError",
    "SynthesisError",
    # External Services
    "ExternalServiceError",
    "APIError",
    "DatabaseError",
    "CacheError",
    "MarketDataError",
    # Configuration
    "ConfigurationError",
    "BusinessTypeError",
    "MethodologyError",
    # Timeout
    "ValuationTimeoutError",
    "StepTimeoutError",
    # Circuit Breaker
    "CircuitBreakerError",
    # Business Logic
    "BusinessLogicError",
    "DomainError",
    "InvalidDiscountError",
    "InvalidMultipleError",
    # Template & Rendering
    "TemplateRenderError",
    "DocumentGenerationError",
    # Aliases
    "ValidationError",
]
