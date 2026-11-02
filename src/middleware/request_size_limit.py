"""
Request Size Limit Middleware

This middleware enforces request size limits to prevent DoS attacks
and ensure system stability.

Author: Upswitch Engineering Team
Date: November 2025
Status: Production Ready
"""

import os
from typing import Callable
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
# CRITICAL FIX: Use custom JSONResponse that handles Decimal serialization
from starlette.responses import Response
from src.api.json_response import JSONResponse  # Custom JSONResponse with Decimal support
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Default max request size: 25MB
#
# Why 25MB (was 10MB):
#   /api/v1/reports/render is the canonical recovery path for a completed
#   valuation report whose persisted HTML is missing or stale. Titan ships
#   the full `valuation_result` JSONB blob as `valuation_data`. Larger
#   reports (multi-year financials + triangulation provenance + sellability
#   payload + business-type enrichment) legitimately exceed 10MB. A
#   413 here aborts the recovery and the user sees a blank report. 25MB
#   gives ~2.5× headroom; tune via VALUATION_IQ_MAX_REQUEST_SIZE_MB.
DEFAULT_MAX_REQUEST_SIZE = 25 * 1024 * 1024  # 25MB in bytes


def _resolve_max_request_size_from_env(default: int = DEFAULT_MAX_REQUEST_SIZE) -> int:
    """Resolve the max request size from VALUATION_IQ_MAX_REQUEST_SIZE_MB.

    Falls back to ``default`` when the env var is unset, blank, non-numeric,
    or non-positive. Logged once at startup via the middleware constructor.
    """
    raw = os.environ.get("VALUATION_IQ_MAX_REQUEST_SIZE_MB", "").strip()
    if not raw:
        return default
    try:
        mb = int(raw)
    except ValueError:
        logger.warning(
            "Invalid VALUATION_IQ_MAX_REQUEST_SIZE_MB=%r; falling back to default %dMB",
            raw,
            default // 1024 // 1024,
        )
        return default
    if mb <= 0:
        logger.warning(
            "Non-positive VALUATION_IQ_MAX_REQUEST_SIZE_MB=%d; falling back to default %dMB",
            mb,
            default // 1024 // 1024,
        )
        return default
    return mb * 1024 * 1024


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce request size limits.

    Prevents DoS attacks and ensures system stability by rejecting
    requests that exceed the configured size limit.
    """

    def __init__(self, app: Callable, max_request_size: int = DEFAULT_MAX_REQUEST_SIZE) -> None:
        """
        Initialize middleware.

        Args:
            app: FastAPI application
            max_request_size: Maximum request size in bytes (default: 10MB)
        """
        super().__init__(app)
        self.max_request_size = max_request_size
        logger.info(
            f"Request size limit middleware initialized: {max_request_size / 1024 / 1024:.1f}MB"
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and enforce size limit.

        Args:
            request: Incoming request
            call_next: Next middleware/handler in chain

        Returns:
            Response from next handler or error response
        """
        # Check Content-Length header
        content_length = request.headers.get("Content-Length")

        if content_length:
            try:
                content_length_int = int(content_length)

                if content_length_int > self.max_request_size:
                    logger.warning(
                        f"Request rejected: size {content_length_int / 1024 / 1024:.2f}MB exceeds limit {self.max_request_size / 1024 / 1024:.1f}MB",
                        extra={
                            'content_length': content_length_int,
                            'max_size': self.max_request_size,
                            'path': request.url.path,
                            'method': request.method
                        }
                    )

                    return JSONResponse(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        content={
                            "error": "Request too large",
                            "message": f"Request size {content_length_int / 1024 / 1024:.2f}MB exceeds maximum allowed size of {self.max_request_size / 1024 / 1024:.1f}MB",
                            "max_size_mb": self.max_request_size / 1024 / 1024
                        }
                    )
            except ValueError:
                logger.warning(
                    f"Invalid Content-Length header: {content_length}",
                    extra={'content_length': content_length}
                )

        # Proceed with request
        response = await call_next(request)
        return response


# ==================== EXPORT ====================

__all__ = [
    'RequestSizeLimitMiddleware',
    'DEFAULT_MAX_REQUEST_SIZE',
    '_resolve_max_request_size_from_env',
]

