"""
Base Methodology Executor

Base class for all methodology executors providing common execution patterns,
error handling, and logging.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from src.api.schemas import ValuationRequest
from src.utils.valuation_logger import ValuationLogger


class MethodologyExecutor(ABC):
    """
    Base class for methodology executors.

    Provides common patterns for:
    - Error handling
    - Performance monitoring
    - Result validation
    - Logging
    """

    def __init__(self, logger: Optional[ValuationLogger] = None):
        """
        Initialize executor.

        Args:
            logger: Optional logger instance (creates new one if not provided)
        """
        self.logger = logger or ValuationLogger(self.__class__.__name__)

    @abstractmethod
    async def execute(
        self, request: ValuationRequest, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute the methodology.

        Args:
            request: Valuation request
            context: Optional processing context

        Returns:
            Dictionary with valuation results

        Raises:
            Exception: If execution fails
        """
        pass

    def validate_request(self, request: ValuationRequest) -> None:
        """
        Validate request before execution.

        Args:
            request: Valuation request to validate

        Raises:
            ValueError: If request is invalid
        """
        if request is None:
            raise ValueError("ValuationRequest cannot be None")

        if not hasattr(request, "current_year_data") or request.current_year_data is None:
            raise ValueError("ValuationRequest must have current_year_data")

    def handle_execution_error(
        self, error: Exception, request: ValuationRequest, context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Handle execution errors with comprehensive logging.

        Args:
            error: Exception that occurred
            request: Valuation request
            context: Optional processing context
        """
        self.logger.error(
            f"❌ {self.__class__.__name__} execution failed",
            extra={
                "error_type": type(error).__name__,
                "error_message": str(error),
                "company_name": request.company_name if request else None,
                "correlation_id": context.get("correlation_id") if context else None,
            },
            exc_info=True,
        )
