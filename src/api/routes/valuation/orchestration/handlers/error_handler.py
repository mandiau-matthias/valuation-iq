"""
Error Handler

Centralized error handling for valuation orchestration.
Provides error recovery strategies and comprehensive error logging.
"""

import traceback
from typing import Any, Dict, Optional

from src.api.schemas import ValuationRequest
from src.config import get_settings
from src.utils.valuation_logger import ValuationLogger


class ErrorHandler:
    """
    Handler for error management in valuation orchestration.

    Responsibilities:
    - Centralized exception handling
    - Error recovery strategies
    - Comprehensive error logging
    """

    def __init__(self, logger: Optional[ValuationLogger] = None):
        """
        Initialize error handler.

        Args:
            logger: Optional logger instance
        """
        self.logger = logger or ValuationLogger(self.__class__.__name__)
        self.logger.debug("✅ ErrorHandler initialized")

    def handle_methodology_execution_error(
        self,
        error: Exception,
        methodology: str,
        request: ValuationRequest,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Handle errors during methodology execution.

        Args:
            error: Exception that occurred
            methodology: Methodology that was being executed
            request: Valuation request
            context: Optional processing context
        """
        error_traceback = traceback.format_exc()
        error_msg = str(error) if error else "Unknown error"
        error_type = type(error).__name__ if error else "UnknownType"

        self.logger.error(
            f"❌ Methodology execution failed: {methodology}",
            extra={
                "methodology": methodology,
                "error_type": error_type,
                "error_message": error_msg,
                "error_traceback": error_traceback,
                "company_name": request.company_name,
                "correlation_id": context.get("correlation_id") if context else None,
            },
            exc_info=True,
        )

        # Print to stdout for visibility in logs
        if get_settings().debug:
            print(f"[ERROR-LOGGING] ========== METHODOLOGY EXECUTION FAILED ==========")
            print(f"[ERROR-LOGGING] methodology={methodology}")
            print(f"[ERROR-LOGGING] error_type={error_type}")
            print(f"[ERROR-LOGGING] error_message={error_msg}")
            print(f"[ERROR-LOGGING] FULL TRACEBACK:\n{error_traceback}")
            print(f"[ERROR-LOGGING] ==============================================================")
            import sys

            sys.stdout.flush()

    def handle_response_building_error(
        self, error: Exception, request: ValuationRequest, context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Handle errors during response building.

        Args:
            error: Exception that occurred
            request: Valuation request
            context: Optional processing context
        """
        self.logger.error(
            "❌ Response building failed",
            extra={
                "error_type": type(error).__name__,
                "error_message": str(error),
                "company_name": request.company_name,
                "correlation_id": context.get("correlation_id") if context else None,
            },
            exc_info=True,
        )

    def handle_transparency_generation_error(
        self, error: Exception, request: ValuationRequest, context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Handle errors during transparency data generation.

        Args:
            error: Exception that occurred
            request: Valuation request
            context: Optional processing context
        """
        self.logger.warning(
            "⚠️ Transparency generation failed",
            extra={
                "error_type": type(error).__name__,
                "error_message": str(error),
                "company_name": request.company_name,
            },
            exc_info=True,
        )
