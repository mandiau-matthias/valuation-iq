"""Sanitized request context helpers for enhanced API logging."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import Request, Response

from src.utils.log_sanitizer import REDACTED, sanitize_log_mapping

VERBOSE_LOGGING_EXCLUDED_PATHS = frozenset(
    {
        "/health",
        "/health/live",
        "/",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
    }
)


def api_middleware_mode_minimal() -> bool:
    """When True, middleware emits one access line per request."""
    try:
        from src.config import get_settings

        return get_settings().api_middleware_log_mode == "minimal"
    except Exception:
        return False


def redacted_session_id(session_id: Optional[str]) -> Optional[str]:
    return REDACTED if session_id else None


def client_host(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def sanitized_request_info(request: Request) -> dict[str, object]:
    """Return request metadata safe for structured logs."""
    return {
        "method": request.method,
        "path": request.url.path,
        "query_params": sanitize_log_mapping(dict(request.query_params)),
        "headers": sanitize_log_mapping(dict(request.headers)),
        "client_host": client_host(request),
        "user_agent": request.headers.get("User-Agent", "unknown"),
        "content_type": request.headers.get("Content-Type", "unknown"),
        "content_length": request.headers.get("Content-Length", "0"),
    }


def audit_request_data(request: Request) -> dict[str, object]:
    """Return the smaller sanitized request shape used in audit events."""
    return {
        "method": request.method,
        "path": request.url.path,
        "query_params": sanitize_log_mapping(dict(request.query_params)),
        "client_host": client_host(request),
    }


def build_error_context(
    request: Request,
    *,
    request_id: str,
    user_id: Optional[str],
    session_id: Optional[str],
) -> dict[str, object]:
    """Return sanitized request context for central error handling."""
    return {
        "request_id": request_id,
        "user_id": user_id,
        "session_id": redacted_session_id(session_id),
        "method": request.method,
        "path": request.url.path,
        "query_params": sanitize_log_mapping(dict(request.query_params)),
        "headers": sanitize_log_mapping(dict(request.headers)),
        "client_host": client_host(request),
    }


def add_timing_headers(
    response: Response,
    *,
    request_id: str,
    duration: float,
    correlation_id: Optional[str] = None,
    response_time: Optional[datetime] = None,
    error_id: Optional[str] = None,
) -> None:
    """Attach standard timing/correlation headers to API responses."""
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = str(duration)
    if response_time is not None:
        response.headers["X-Response-Time"] = response_time.isoformat()
    if correlation_id:
        response.headers["X-Correlation-ID"] = correlation_id
    if error_id:
        response.headers["X-Error-ID"] = error_id
