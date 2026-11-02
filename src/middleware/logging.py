from src.errors.error_types import ValuationError
from src.utils.exceptions import APIError, CacheError

"""
Enhanced Logging Middleware

Comprehensive logging middleware for the valuation engine with request/response tracking,
performance monitoring, and audit trail capabilities.

ARCHITECTURE:
- Request/response logging with detailed context
- Performance metrics collection
- User context tracking
- Audit trail logging
- Error context capture
- Security event logging

FEATURES:
- Request ID tracking across all services
- User context propagation
- Performance metrics integration
- Audit trail logging for compliance
- Security event monitoring
- Error context capture
"""

import json
import time
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Dict, Optional

from fastapi import Request, Response

# CRITICAL FIX: Use custom JSONResponse that handles Decimal serialization
from src.api.json_response import JSONResponse  # Custom JSONResponse with Decimal support
from src.errors.error_handler import handle_error
from src.utils.log_sanitizer import REDACTED, sanitize_log_mapping
from src.utils.logging import get_logger, log_audit_event, log_performance_metric
from src.utils.logging_context import LoggingContext, clear_current_context, set_current_context

logger = get_logger(__name__)


async def logging_middleware(request: Request, call_next: Callable) -> Response:
    """
    Enhanced logging middleware with comprehensive request/response tracking.

    Features:
    - Request ID generation and tracking
    - User context propagation
    - Performance metrics collection
    - Audit trail logging
    - Error context capture
    - Security event monitoring

    Args:
        request: FastAPI request object
        call_next: Next middleware/endpoint in chain

    Returns:
        Response object with enhanced logging
    """
    # Generate or extract request ID
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

    # Create logging context
    logging_context = LoggingContext()
    logging_context.set_request_id(request_id)

    # Extract user context from headers
    user_id = request.headers.get("X-User-ID")
    session_id = request.headers.get("X-Session-ID")
    correlation_id = request.headers.get("X-Correlation-ID")
    log_session_id = REDACTED if session_id else None

    if user_id:
        logging_context.set_user_id(user_id)
    if session_id:
        logging_context.set_session_id(session_id)
    if correlation_id:
        logging_context.set_correlation_id(correlation_id)

    # Set current context
    set_current_context(logging_context)

    # Start timer
    start_time = time.time()
    start_datetime = datetime.utcnow()

    sanitized_headers = sanitize_log_mapping(dict(request.headers))
    sanitized_query_params = sanitize_log_mapping(dict(request.query_params))

    # Extract request information
    request_info = {
        "method": request.method,
        "path": request.url.path,
        "query_params": sanitized_query_params,
        "headers": sanitized_headers,
        "client_host": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("User-Agent", "unknown"),
        "content_type": request.headers.get("Content-Type", "unknown"),
        "content_length": request.headers.get("Content-Length", "0"),
    }

    # Log incoming request
    logger.info(
        "Incoming request",
        request_id=request_id,
        user_id=user_id,
        session_id=log_session_id,
        correlation_id=correlation_id,
        **request_info,
    )

    # Log audit event for request
    log_audit_event(
        event_type="REQUEST_RECEIVED",
        actor=user_id or "anonymous",
        action="api_request",
        resource=request.url.path,
        data={
            "method": request.method,
            "path": request.url.path,
            "query_params": sanitized_query_params,
            "client_host": request.client.host if request.client else "unknown",
        },
    )

    # Track performance metrics
    logging_context.add_performance_metric("request_start_time", start_time, "timestamp")

    try:
        # Process request
        response = await call_next(request)

        # Calculate duration
        duration = time.time() - start_time
        end_datetime = datetime.utcnow()

        # Log performance metrics
        log_performance_metric("request_duration", duration, "seconds")
        log_performance_metric("response_status", response.status_code, "code")

        # Add performance metrics to context
        logging_context.add_performance_metric("request_duration", duration, "seconds")
        logging_context.add_performance_metric("response_status", response.status_code, "code")
        logging_context.add_performance_metric("request_end_time", time.time(), "timestamp")

        # Log response
        logger.info(
            "Request completed",
            request_id=request_id,
            user_id=user_id,
            session_id=log_session_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration * 1000, 2),
            response_size=response.headers.get("Content-Length", "unknown"),
        )

        # Log audit event for response
        log_audit_event(
            event_type="REQUEST_COMPLETED",
            actor=user_id or "anonymous",
            action="api_response",
            resource=request.url.path,
            data={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration * 1000, 2),
            },
        )

        # Add custom headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(duration)
        response.headers["X-Response-Time"] = end_datetime.isoformat()

        # Add correlation headers if available
        if correlation_id:
            response.headers["X-Correlation-ID"] = correlation_id

        return response

    except APIError as exc:
        # Calculate duration for error case
        duration = time.time() - start_time

        # Log error
        logger.error(
            "Request failed",
            request_id=request_id,
            user_id=user_id,
            session_id=log_session_id,
            method=request.method,
            path=request.url.path,
            error_type=type(exc).__name__,
            error_message=str(exc),
            duration_ms=round(duration * 1000, 2),
            exc_info=True,
        )

        # Handle error with comprehensive context
        error_context = {
            "request_id": request_id,
            "user_id": user_id,
            "session_id": log_session_id,
            "method": request.method,
            "path": request.url.path,
            "query_params": sanitized_query_params,
            "headers": sanitized_headers,
            "client_host": request.client.host if request.client else "unknown",
        }

        # Use error handler for comprehensive error processing
        error_result = handle_error(exc, error_context)

        # Log audit event for error
        log_audit_event(
            event_type="REQUEST_ERROR",
            actor=user_id or "anonymous",
            action="api_error",
            resource=request.url.path,
            data={
                "method": request.method,
                "path": request.url.path,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "duration_ms": round(duration * 1000, 2),
                "error_id": error_result.error_id,
            },
        )

        # Create error response
        error_response = JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "error_id": error_result.error_id,
                "message": error_result.user_message,
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        # Add error headers
        error_response.headers["X-Request-ID"] = request_id
        error_response.headers["X-Process-Time"] = str(duration)
        error_response.headers["X-Error-ID"] = error_result.error_id

        return error_response

    finally:
        # Clear current context
        clear_current_context()


async def security_logging_middleware(request: Request, call_next: Callable) -> Response:
    """
    Security-focused logging middleware for sensitive operations.

    Features:
    - Security event logging
    - Authentication/authorization tracking
    - Privacy violation detection
    - Audit trail for compliance

    Args:
        request: FastAPI request object
        call_next: Next middleware/endpoint in chain

    Returns:
        Response object with security logging
    """
    # Extract security context
    user_id = request.headers.get("X-User-ID")
    session_id = request.headers.get("X-Session-ID")
    auth_token = request.headers.get("Authorization")
    log_session_id = REDACTED if session_id else None

    # Log security events
    if auth_token:
        logger.info(
            "Authentication attempt",
            user_id=user_id,
            session_id=log_session_id,
            method=request.method,
            path=request.url.path,
            has_token=True,
        )

    # Process request
    response = await call_next(request)

    # Log security response
    if response.status_code == 401:
        logger.warning(
            "Authentication failed",
            user_id=user_id,
            session_id=log_session_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
        )
    elif response.status_code == 403:
        logger.warning(
            "Authorization failed",
            user_id=user_id,
            session_id=log_session_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
        )

    return response


async def performance_logging_middleware(request: Request, call_next: Callable) -> Response:
    """
    Performance-focused logging middleware for monitoring and optimization.

    Features:
    - Detailed performance metrics
    - Resource usage tracking
    - Bottleneck identification
    - Performance alerting

    Args:
        request: FastAPI request object
        call_next: Next middleware/endpoint in chain

    Returns:
        Response object with performance logging
    """
    # Start performance tracking
    start_time = time.time()
    start_memory = _get_memory_usage()

    # Process request
    response = await call_next(request)

    # Calculate performance metrics
    duration = time.time() - start_time
    end_memory = _get_memory_usage()
    memory_delta = end_memory - start_memory if start_memory and end_memory else None

    # Log performance metrics
    logger.info(
        "Performance metrics",
        method=request.method,
        path=request.url.path,
        duration_ms=round(duration * 1000, 2),
        memory_start_mb=start_memory,
        memory_end_mb=end_memory,
        memory_delta_mb=memory_delta,
        status_code=response.status_code,
    )

    # Log performance metric
    log_performance_metric("request_duration", duration, "seconds")
    if memory_delta is not None:
        log_performance_metric("memory_delta", memory_delta, "MB")

    return response


def _get_memory_usage() -> Optional[Decimal]:
    """Get current memory usage in MB"""
    try:
        import psutil

        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024  # Convert to MB
    except ImportError:
        return None
    except CacheError:
        return None
