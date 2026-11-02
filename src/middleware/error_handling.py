from src.utils.exceptions import APIError

"""
Error handling middleware

Provides centralized error handling and logging for all API requests.
"""

from typing import Callable
from fastapi import Request, Response
# CRITICAL FIX: Use custom JSONResponse that handles Decimal serialization
from src.api.json_response import JSONResponse  # Custom JSONResponse with Decimal support
from src.utils.logging import get_logger
import traceback

from src.config import get_settings

logger = get_logger(__name__)
settings = get_settings()


async def error_handling_middleware(request: Request, call_next: Callable) -> Response:
    """
    Error handling middleware

    Catches all unhandled exceptions and returns appropriate error responses.

    Args:
        request: FastAPI request object
        call_next: Next middleware/endpoint in chain

    Returns:
        Response object (normal response or error response)
    """
    try:
        response = await call_next(request)
        return response
    except APIError as exc:
        # Log the error with full context
        logger.error(
            "Unhandled exception in request",
            path=request.url.path,
            method=request.method,
            error=str(exc),
            exc_info=True if settings.debug else False
        )

        # Return appropriate error response
        error_detail = {
            "error": "Internal Server Error",
            "message": str(exc) if settings.debug else "An unexpected error occurred",
            "path": request.url.path,
        }

        # Include traceback in development mode
        if settings.debug:
            error_detail["traceback"] = traceback.format_exc()

        return JSONResponse(
            status_code=500,
            content=error_detail
        )

