"""
Pagination Error Handler

BANK-GRADE: Single Responsibility - Handle pagination errors

RESPONSIBILITY:
- Define pagination-specific exceptions
- Handle pagination errors
- Provide error context
- Generate error recovery strategies

DOES NOT:
- Perform pagination (delegated to PaginationService)
- Parse content (delegated to ContentBlockParser)
- Render pages (delegated to PageRenderer)

SRP Compliance: This service has ONE reason to change - error handling requirements
"""

from typing import Dict, Any, Optional
from enum import Enum

from src.utils.logging import get_logger

logger = get_logger(__name__)


class PaginationErrorType(Enum):
    """Types of pagination errors"""
    CONTENT_TOO_LARGE = "content_too_large"
    INVALID_CONTENT = "invalid_content"
    PARSING_FAILED = "parsing_failed"
    RENDERING_FAILED = "rendering_failed"
    OVERFLOW = "overflow"
    ORPHAN_VIOLATION = "orphan_violation"
    CONFIGURATION_ERROR = "configuration_error"


class PaginationError(Exception):
    """
    Base exception for pagination errors.
    
    BANK-GRADE: Rich error context for debugging
    """
    
    def __init__(
        self,
        message: str,
        error_type: PaginationErrorType,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize pagination error.
        
        Args:
            message: Error message
            error_type: Type of error
            context: Additional error context
        """
        super().__init__(message)
        self.error_type = error_type
        self.context = context or {}


class ContentTooLargeError(PaginationError):
    """Content exceeds maximum size for pagination"""
    
    def __init__(self, content_size: int, max_size: int):
        super().__init__(
            f"Content size ({content_size} bytes) exceeds maximum ({max_size} bytes)",
            PaginationErrorType.CONTENT_TOO_LARGE,
            {'content_size': content_size, 'max_size': max_size}
        )


class InvalidContentError(PaginationError):
    """Content is invalid or malformed"""
    
    def __init__(self, reason: str):
        super().__init__(
            f"Invalid content: {reason}",
            PaginationErrorType.INVALID_CONTENT,
            {'reason': reason}
        )


class ParsingError(PaginationError):
    """Content parsing failed"""
    
    def __init__(self, reason: str):
        super().__init__(
            f"Content parsing failed: {reason}",
            PaginationErrorType.PARSING_FAILED,
            {'reason': reason}
        )


class RenderingError(PaginationError):
    """Page rendering failed"""
    
    def __init__(self, page_number: int, reason: str):
        super().__init__(
            f"Page {page_number} rendering failed: {reason}",
            PaginationErrorType.RENDERING_FAILED,
            {'page_number': page_number, 'reason': reason}
        )


class OverflowError(PaginationError):
    """Content overflows page boundaries"""
    
    def __init__(self, block_id: str, block_height: float, page_height: float):
        super().__init__(
            f"Block {block_id} ({block_height}mm) exceeds page height ({page_height}mm)",
            PaginationErrorType.OVERFLOW,
            {
                'block_id': block_id,
                'block_height': block_height,
                'page_height': page_height
            }
        )


class OrphanViolationError(PaginationError):
    """Orphan/widow control violated"""
    
    def __init__(self, lines_left: int, min_lines: int):
        super().__init__(
            f"Orphan violation: {lines_left} lines left, minimum {min_lines} required",
            PaginationErrorType.ORPHAN_VIOLATION,
            {'lines_left': lines_left, 'min_lines': min_lines}
        )


class PaginationErrorHandler:
    """
    BANK-GRADE SRP-COMPLIANT: Handles pagination errors.
    
    SINGLE RESPONSIBILITY: Error handling and recovery
    
    This service focuses solely on error management:
    - Catching pagination errors
    - Providing rich error context
    - Suggesting recovery strategies
    - Logging errors appropriately
    
    Design Pattern: Service Pattern
    - Separates error handling from pagination logic
    - Enables testing error scenarios independently
    - Allows extending with new error types
    """
    
    def __init__(self):
        """Initialize pagination error handler."""
        self.logger = logger
        self.logger.info("✅ [PAGINATION-ERROR] PaginationErrorHandler initialized (SRP-compliant)")
    
    def handle_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Handle pagination error and provide recovery strategy.
        
        BANK-GRADE: Comprehensive error context and recovery
        
        Args:
            error: Exception that occurred
            context: Additional context
            
        Returns:
            Error response with recovery strategy
        """
        if isinstance(error, PaginationError):
            return self._handle_pagination_error(error, context)
        else:
            return self._handle_unexpected_error(error, context)
    
    def _handle_pagination_error(
        self,
        error: PaginationError,
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Handle known pagination error.
        
        Args:
            error: PaginationError instance
            context: Additional context
            
        Returns:
            Error response dictionary
        """
        self.logger.error(
            f"❌ [PAGINATION-ERROR] {error.error_type.value}: {str(error)}",
            extra={
                'error_type': error.error_type.value,
                'error_context': error.context,
                'additional_context': context
            }
        )
        
        # Generate recovery strategy
        recovery_strategy = self._generate_recovery_strategy(error)
        
        return {
            'error_type': error.error_type.value,
            'message': str(error),
            'context': {**error.context, **(context or {})},
            'recovery_strategy': recovery_strategy,
            'is_recoverable': recovery_strategy is not None
        }
    
    def _handle_unexpected_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Handle unexpected error.
        
        Args:
            error: Generic Exception
            context: Additional context
            
        Returns:
            Error response dictionary
        """
        self.logger.error(
            f"❌ [PAGINATION-ERROR] Unexpected error: {str(error)}",
            exc_info=True,
            extra={'additional_context': context}
        )
        
        return {
            'error_type': 'unexpected',
            'message': str(error),
            'context': context or {},
            'recovery_strategy': None,
            'is_recoverable': False
        }
    
    def _generate_recovery_strategy(self, error: PaginationError) -> Optional[str]:
        """
        Generate recovery strategy for error.
        
        Args:
            error: PaginationError instance
            
        Returns:
            Recovery strategy string or None
        """
        strategies = {
            PaginationErrorType.CONTENT_TOO_LARGE: (
                "Reduce content size or increase page limit. "
                "Consider splitting content into multiple reports."
            ),
            PaginationErrorType.INVALID_CONTENT: (
                "Validate HTML content structure. "
                "Ensure all tags are properly closed and nested."
            ),
            PaginationErrorType.PARSING_FAILED: (
                "Check HTML syntax. "
                "Try simplifying content structure."
            ),
            PaginationErrorType.RENDERING_FAILED: (
                "Verify page template is valid. "
                "Check for missing CSS or invalid HTML."
            ),
            PaginationErrorType.OVERFLOW: (
                "Content block is too large for single page. "
                "Consider breaking into smaller sections or increasing page height."
            ),
            PaginationErrorType.ORPHAN_VIOLATION: (
                "Adjust orphan/widow control settings. "
                "Or increase minimum lines per page."
            ),
            PaginationErrorType.CONFIGURATION_ERROR: (
                "Check pagination configuration. "
                "Ensure all required settings are provided."
            )
        }
        
        return strategies.get(error.error_type)
    
    def validate_configuration(self, config: Dict[str, Any]) -> None:
        """
        Validate pagination configuration.
        
        Args:
            config: Pagination configuration
            
        Raises:
            PaginationError: If configuration is invalid
        """
        required_fields = ['page_height', 'page_width', 'margin_top', 'margin_bottom']
        
        for field in required_fields:
            if field not in config:
                raise PaginationError(
                    f"Missing required configuration field: {field}",
                    PaginationErrorType.CONFIGURATION_ERROR,
                    {'missing_field': field}
                )
        
        # Validate numeric fields
        for field in ['page_height', 'page_width', 'margin_top', 'margin_bottom']:
            value = config.get(field)
            if not isinstance(value, (int, float)) or value <= 0:
                raise PaginationError(
                    f"Invalid value for {field}: {value}",
                    PaginationErrorType.CONFIGURATION_ERROR,
                    {'field': field, 'value': value}
                )
