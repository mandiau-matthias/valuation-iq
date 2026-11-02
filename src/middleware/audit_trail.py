"""
Audit Trail Logging Middleware

This middleware provides comprehensive audit logging for all API requests,
recording user actions, request details, and outcomes for compliance and debugging.

Author: Upswitch Engineering Team
Date: November 2025
Status: Production Ready
"""

import json
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from src.utils.correlation import ensure_correlation_id
from src.utils.log_sanitizer import sanitize_log_mapping, sanitize_log_value
from src.utils.logging import get_logger

logger = get_logger(__name__)


class AuditTrailMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log comprehensive audit trail for all API requests.

    Logs include:
    - Request timestamp
    - HTTP method and path
    - Request headers (excluding sensitive data)
    - Request body (sanitized)
    - Response status code
    - Response time
    - User identification (if available)
    - Correlation ID for tracing
    """

    def __init__(self, app: Callable, excluded_paths: Optional[List[str]] = None) -> None:
        """
        Initialize middleware.

        Args:
            app: FastAPI application
            excluded_paths: List of paths to exclude from audit logging (e.g., health checks)
        """
        super().__init__(app)
        self.excluded_paths = excluded_paths or [
            "/health",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json",
        ]
        logger.debug(
            f"Audit trail middleware initialized, excluding {len(self.excluded_paths)} paths"
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and log audit trail.

        Args:
            request: Incoming request
            call_next: Next middleware/handler in chain

        Returns:
            Response from next handler
        """
        # Skip excluded paths
        if request.url.path in self.excluded_paths:
            return await call_next(request)

        # Record start time
        start_time = time.time()
        timestamp = datetime.now(timezone.utc).isoformat()

        # Get or generate correlation ID
        correlation_id = ensure_correlation_id(dict(request.headers))

        # Extract request details
        audit_log = {
            "timestamp": timestamp,
            "correlation_id": correlation_id,
            "method": request.method,
            "path": request.url.path,
            "query_params": sanitize_log_mapping(dict(request.query_params)),
            "client_host": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        }

        # Extract user info if available (from auth headers)
        auth_header = request.headers.get("authorization")
        if auth_header:
            audit_log["auth_type"] = auth_header.split(" ")[0] if " " in auth_header else "Unknown"
            # Don't log the actual token, just the presence
            audit_log["authenticated"] = True
        else:
            audit_log["authenticated"] = False

        # Try to get request body for POST/PUT/PATCH requests.
        # Audit logging is best-effort and MUST be fail-open: a malformed,
        # compressed, or binary body can never be allowed to crash the
        # request it is meant to observe.
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if body:
                    audit_log["request_body_size"] = len(body)
                    content_encoding = (
                        (request.headers.get("content-encoding") or "").strip().lower()
                    )
                    content_type = (request.headers.get("content-type") or "").lower()
                    # Compressed bodies (e.g. gzip uploads — magic byte 0x8b)
                    # are not UTF-8/JSON; attempting json.loads raised an
                    # uncaught UnicodeDecodeError and 500'd the request. Skip
                    # parsing for compressed or non-text/non-JSON payloads.
                    if request.url.path.rstrip("/") == "/api/v1/acquisition/scenarios":
                        # Free-text evidence/assumptions are private even when
                        # their field names are not in a generic redaction list.
                        audit_log["request_body_type"] = "private_acquisition_case"
                    elif content_encoding:
                        audit_log["request_body_type"] = f"encoded:{content_encoding}"
                    elif content_type and "json" not in content_type and "text" not in content_type:
                        audit_log["request_body_type"] = "non-json"
                    else:
                        try:
                            body_json = json.loads(body)
                            # Sanitize sensitive fields
                            sanitized_body = self._sanitize_request_body(body_json)
                            audit_log["request_body_preview"] = json.dumps(sanitized_body)[:500]
                        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
                            audit_log["request_body_type"] = "non-json"

                # Re-wrap body for downstream handlers
                async def receive() -> Dict[str, Any]:
                    return {"type": "http.request", "body": body}

                request._receive = receive
            except Exception as e:  # noqa: BLE001 - audit logging must never break the request
                logger.warning(f"Failed to read request body for audit: {e}")

        # Process request
        try:
            response = await call_next(request)

            # Record response details
            duration_ms = (time.time() - start_time) * 1000
            audit_log["status_code"] = response.status_code
            audit_log["duration_ms"] = round(duration_ms, 2)
            audit_log["success"] = 200 <= response.status_code < 400

            # Log audit trail
            log_level = "info" if audit_log["success"] else "warning"
            log_message = (
                f"AUDIT: {audit_log['method']} {audit_log['path']} "
                f"→ {audit_log['status_code']} ({audit_log['duration_ms']}ms)"
            )

            if log_level == "info":
                logger.info(log_message, extra=audit_log)
            else:
                logger.warning(log_message, extra=audit_log)

            return response

        except Exception as e:
            # Log ANY failed request (not just APIError) so the audit trail
            # never has a silent gap, then re-raise so the registered error
            # handlers still own the response.
            duration_ms = (time.time() - start_time) * 1000
            audit_log["error"] = str(e)
            audit_log["error_type"] = type(e).__name__
            audit_log["duration_ms"] = round(duration_ms, 2)
            audit_log["success"] = False

            logger.error(
                f"AUDIT ERROR: {audit_log['method']} {audit_log['path']} failed: {e}",
                extra=audit_log,
                exc_info=True,
            )

            # Re-raise to let error handlers deal with it
            raise

    def _sanitize_request_body(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize request body to remove sensitive information.

        Args:
            body: Request body as dictionary

        Returns:
            Sanitized body with sensitive fields masked
        """
        sanitized = sanitize_log_value(body, max_items=10)
        return sanitized if isinstance(sanitized, dict) else {}


# ==================== EXPORT ====================

__all__ = [
    "AuditTrailMiddleware",
]
