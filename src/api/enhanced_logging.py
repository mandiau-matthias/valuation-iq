"""
Enhanced API Layer Logging

Comprehensive logging for all API requests, responses, and middleware operations.
Provides detailed tracking of API performance, security events, and user interactions.

ARCHITECTURE:
- Request/response logging with detailed context
- Authentication/authorization event logging
- Rate limiting and throttling logging
- Input validation and sanitization logging
- Performance metrics collection
- Security event monitoring
- Error response logging

FEATURES:
- Every API request logged with full context
- Response timing and performance metrics
- Security events and authentication tracking
- Input validation with business rules
- Error handling with user-friendly messages
- Audit trail for compliance
"""

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from src.api.enhanced_logging_context import (
    VERBOSE_LOGGING_EXCLUDED_PATHS,
    add_timing_headers,
)
from src.api.enhanced_logging_context import (
    api_middleware_mode_minimal as _api_middleware_mode_minimal,
)
from src.api.enhanced_logging_context import (
    audit_request_data,
    build_error_context,
    redacted_session_id,
    sanitized_request_info,
)

# CRITICAL FIX: Use custom JSONResponse that handles Decimal serialization
from src.api.json_response import (
    JSONResponse,
)  # Custom JSONResponse with Decimal support
from src.errors.error_handler import handle_error
from src.utils.exceptions import APIError, CacheError, DataValidationError
from src.utils.logging import log_audit_event, log_performance_metric
from src.utils.logging_context import (
    LoggingContext,
    clear_current_context,
    set_current_context,
)

logger = logging.getLogger(__name__)


class ModuleLoggerMiddleware(BaseHTTPMiddleware):
    """Base middleware that exposes the module logger on instances."""

    def __init__(self, app: Any) -> None:
        super().__init__(app)
        self.logger = logger


class EnhancedAPILoggingMiddleware(ModuleLoggerMiddleware):
    """
    Enhanced API logging middleware with comprehensive request/response tracking.

    Features:
    - Request/response logging with detailed context
    - Performance metrics collection
    - Security event monitoring
    - Input validation logging
    - Error handling with context
    - Audit trail for compliance
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """
        Enhanced API request/response logging with comprehensive context.

        Features:
        - Request ID generation and tracking
        - User context propagation
        - Performance metrics collection
        - Security event monitoring
        - Input validation logging
        - Error handling with context
        """
        # Generate or extract request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Create logging context
        logging_context = LoggingContext()
        logging_context.set_request_id(request_id)

        # Extract user context from headers
        user_id = request.headers.get("X-User-ID")
        session_id = request.headers.get("X-Session-ID")
        # Every request receives an end-to-end correlation id. Titan's id is
        # preserved when supplied; direct calls use this service's request id.
        correlation_id = request.headers.get("X-Correlation-ID") or request_id
        log_session_id = redacted_session_id(session_id)

        if user_id:
            logging_context.set_user_id(user_id)
        if session_id:
            logging_context.set_session_id(session_id)
        logging_context.set_correlation_id(correlation_id)

        # Set current context
        set_current_context(logging_context)

        # Skip verbose logging for health checks, docs, metrics
        if request.url.path in VERBOSE_LOGGING_EXCLUDED_PATHS:
            try:
                response = await call_next(request)
                response.headers["X-Request-ID"] = request_id
                response.headers["X-Correlation-ID"] = correlation_id
                return response
            finally:
                clear_current_context()

        minimal = _api_middleware_mode_minimal()

        # Start timer
        start_time = time.time()
        request_info = sanitized_request_info(request)

        if not minimal:
            # Log incoming request
            self.logger.info(
                "API request received",
                extra={
                    "request_id": request_id,
                    "user_id": user_id,
                    "session_id": log_session_id,
                    "correlation_id": correlation_id,
                    **request_info,
                },
            )

            # Log audit event for request
            log_audit_event(
                event_type="API_REQUEST_RECEIVED",
                actor=user_id or "anonymous",
                action="api_request",
                resource=request.url.path,
                data=audit_request_data(request),
            )

        # Track performance metrics
        logging_context.add_performance_metric(
            "request_start_time", start_time, "timestamp"
        )

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration = time.time() - start_time
            end_datetime = datetime.now(timezone.utc)

            if not minimal:
                # Log performance metrics
                log_performance_metric("api_request_duration", duration, "seconds")
                log_performance_metric(
                    "api_response_status", response.status_code, "code"
                )

                # Add performance metrics to context
                logging_context.add_performance_metric(
                    "request_duration", duration, "seconds"
                )
                logging_context.add_performance_metric(
                    "response_status", response.status_code, "code"
                )
                logging_context.add_performance_metric(
                    "request_end_time", time.time(), "timestamp"
                )

                # Log response
                self.logger.info(
                    "API request completed",
                    extra={
                        "request_id": request_id,
                        "user_id": user_id,
                        "session_id": log_session_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "duration_ms": round(duration * 1000, 2),
                        "response_size": response.headers.get(
                            "Content-Length", "unknown"
                        ),
                    },
                )

                # Log audit event for response
                log_audit_event(
                    event_type="API_REQUEST_COMPLETED",
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
            else:
                self.logger.info(
                    "API access",
                    extra={
                        "request_id": request_id,
                        "user_id": user_id,
                        "session_id": log_session_id,
                        "correlation_id": correlation_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "duration_ms": round(duration * 1000, 2),
                    },
                )

            add_timing_headers(
                response,
                request_id=request_id,
                duration=duration,
                correlation_id=correlation_id,
                response_time=end_datetime,
            )

            return response

        except HTTPException as http_exc:
            # Handle HTTP exceptions
            duration = time.time() - start_time

            self.logger.warning(
                "API request failed with HTTP exception",
                extra={
                    "request_id": request_id,
                    "user_id": user_id,
                    "session_id": log_session_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": http_exc.status_code,
                    "error_message": http_exc.detail,
                    "duration_ms": round(duration * 1000, 2),
                },
            )

            if not minimal:
                log_audit_event(
                    event_type="API_REQUEST_HTTP_ERROR",
                    actor=user_id or "anonymous",
                    action="api_error",
                    resource=request.url.path,
                    data={
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": http_exc.status_code,
                        "error_message": http_exc.detail,
                        "duration_ms": round(duration * 1000, 2),
                    },
                )

            # Create error response
            error_response = JSONResponse(
                status_code=http_exc.status_code,
                content={
                    "error": http_exc.detail,
                    "request_id": request_id,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

            add_timing_headers(
                error_response,
                request_id=request_id,
                duration=duration,
                correlation_id=correlation_id,
            )

            return error_response

        except APIError as exc:
            # Calculate duration for error case
            duration = time.time() - start_time

            # Log error
            self.logger.error(
                "API request failed with exception",
                extra={
                    "request_id": request_id,
                    "user_id": user_id,
                    "session_id": log_session_id,
                    "method": request.method,
                    "path": request.url.path,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "duration_ms": round(duration * 1000, 2),
                },
                exc_info=True,
            )

            # Handle error with comprehensive context
            error_context = build_error_context(
                request,
                request_id=request_id,
                user_id=user_id,
                session_id=session_id,
            )

            # Use error handler for comprehensive error processing
            error_result = handle_error(exc, error_context)

            if not minimal:
                log_audit_event(
                    event_type="API_REQUEST_ERROR",
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

            add_timing_headers(
                error_response,
                request_id=request_id,
                duration=duration,
                correlation_id=correlation_id,
                error_id=error_result.error_id,
            )

            return error_response

        finally:
            # Clear current context
            clear_current_context()


class SecurityLoggingMiddleware(ModuleLoggerMiddleware):
    """
    Security-focused logging middleware for sensitive operations.

    Features:
    - Authentication/authorization event logging
    - Security violation detection
    - Rate limiting and throttling logging
    - Privacy event monitoring
    - Audit trail for compliance
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """
        Security-focused request/response logging.

        Features:
        - Authentication event logging
        - Authorization event logging
        - Security violation detection
        - Rate limiting logging
        - Privacy event monitoring
        """
        # Extract security context
        user_id = request.headers.get("X-User-ID")
        session_id = request.headers.get("X-Session-ID")
        auth_token = request.headers.get("Authorization")
        api_key = request.headers.get("X-API-Key")
        log_session_id = redacted_session_id(session_id)
        minimal = _api_middleware_mode_minimal()

        # Log authentication events (skipped in minimal mode to reduce log volume)
        if not minimal and auth_token:
            self.logger.info(
                "Authentication attempt",
                extra={
                    "user_id": user_id,
                    "session_id": log_session_id,
                    "method": request.method,
                    "path": request.url.path,
                    "has_token": True,
                    "token_type": "Bearer",
                },
            )

            log_audit_event(
                event_type="AUTHENTICATION_ATTEMPT",
                actor=user_id or "anonymous",
                action="authenticate",
                resource=request.url.path,
                data={
                    "method": request.method,
                    "path": request.url.path,
                    "token_type": "Bearer",
                    "has_token": True,
                },
            )

        if not minimal and api_key:
            self.logger.info(
                "API key authentication attempt",
                extra={
                    "user_id": user_id,
                    "session_id": log_session_id,
                    "method": request.method,
                    "path": request.url.path,
                    "has_api_key": True,
                },
            )

            log_audit_event(
                event_type="API_KEY_AUTHENTICATION_ATTEMPT",
                actor=user_id or "anonymous",
                action="api_key_authenticate",
                resource=request.url.path,
                data={
                    "method": request.method,
                    "path": request.url.path,
                    "has_api_key": True,
                },
            )

        # Process request
        response = await call_next(request)

        # Log security response
        if response.status_code == 401:
            self.logger.warning(
                "Authentication failed",
                extra={
                    "user_id": user_id,
                    "session_id": log_session_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                },
            )

            if not minimal:
                log_audit_event(
                    event_type="AUTHENTICATION_FAILED",
                    actor=user_id or "anonymous",
                    action="authentication_failed",
                    resource=request.url.path,
                    data={
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                    },
                )

        elif response.status_code == 403:
            self.logger.warning(
                "Authorization failed",
                extra={
                    "user_id": user_id,
                    "session_id": log_session_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                },
            )

            if not minimal:
                log_audit_event(
                    event_type="AUTHORIZATION_FAILED",
                    actor=user_id or "anonymous",
                    action="authorization_failed",
                    resource=request.url.path,
                    data={
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                    },
                )

        elif response.status_code == 429:
            self.logger.warning(
                "Rate limit exceeded",
                extra={
                    "user_id": user_id,
                    "session_id": log_session_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                },
            )

            if not minimal:
                log_audit_event(
                    event_type="RATE_LIMIT_EXCEEDED",
                    actor=user_id or "anonymous",
                    action="rate_limit_exceeded",
                    resource=request.url.path,
                    data={
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                    },
                )

        return response


class PerformanceLoggingMiddleware(ModuleLoggerMiddleware):
    """
    Performance-focused logging middleware for monitoring and optimization.

    Features:
    - Detailed performance metrics
    - Resource usage tracking
    - Bottleneck identification
    - Performance alerting
    - Throughput monitoring
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """
        Performance-focused request/response logging.

        Features:
        - Detailed performance metrics
        - Resource usage tracking
        - Bottleneck identification
        - Performance alerting
        """
        if request.url.path in VERBOSE_LOGGING_EXCLUDED_PATHS:
            return await call_next(request)

        if _api_middleware_mode_minimal():
            start_time = time.time()
            start_memory = self._get_memory_usage()
            start_cpu = self._get_cpu_usage()
            response = await call_next(request)
            duration = time.time() - start_time
            end_memory = self._get_memory_usage()
            end_cpu = self._get_cpu_usage()
            memory_delta = (
                end_memory - start_memory if start_memory and end_memory else None
            )
            cpu_delta = end_cpu - start_cpu if start_cpu and end_cpu else None
            if duration > 5.0:
                self.logger.warning(
                    "Slow API request detected",
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "duration_ms": round(duration * 1000, 2),
                        "threshold_ms": 5000,
                    },
                )
            if memory_delta and memory_delta > 100:
                self.logger.warning(
                    "High memory usage detected",
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "memory_delta_mb": memory_delta,
                        "threshold_mb": 100,
                    },
                )
            return response

        # Start performance tracking
        start_time = time.time()
        start_memory = self._get_memory_usage()
        start_cpu = self._get_cpu_usage()

        # Process request
        response = await call_next(request)

        # Calculate performance metrics
        duration = time.time() - start_time
        end_memory = self._get_memory_usage()
        end_cpu = self._get_cpu_usage()
        memory_delta = (
            end_memory - start_memory if start_memory and end_memory else None
        )
        cpu_delta = end_cpu - start_cpu if start_cpu and end_cpu else None

        # Log performance metrics
        self.logger.info(
            "API performance metrics",
            extra={
                "method": request.method,
                "path": request.url.path,
                "duration_ms": round(duration * 1000, 2),
                "memory_start_mb": start_memory,
                "memory_end_mb": end_memory,
                "memory_delta_mb": memory_delta,
                "cpu_start_percent": start_cpu,
                "cpu_end_percent": end_cpu,
                "cpu_delta_percent": cpu_delta,
                "status_code": response.status_code,
            },
        )

        # Log performance metrics
        log_performance_metric("api_request_duration", duration, "seconds")
        if memory_delta is not None:
            log_performance_metric("api_memory_delta", memory_delta, "MB")
        if cpu_delta is not None:
            log_performance_metric("api_cpu_delta", cpu_delta, "percent")

        # Check for performance issues
        if duration > 5.0:  # 5 seconds threshold
            self.logger.warning(
                "Slow API request detected",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(duration * 1000, 2),
                    "threshold_ms": 5000,
                },
            )

        if memory_delta and memory_delta > 100:  # 100MB threshold
            self.logger.warning(
                "High memory usage detected",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "memory_delta_mb": memory_delta,
                    "threshold_mb": 100,
                },
            )

        return response

    def _get_memory_usage(self) -> Optional[float]:
        """Get current memory usage in MB"""
        try:
            import psutil

            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024  # Convert to MB
        except ImportError:
            return None
        except CacheError:
            return None

    def _get_cpu_usage(self) -> Optional[float]:
        """Get current CPU usage percentage"""
        try:
            import psutil

            return psutil.cpu_percent()
        except ImportError:
            return None
        except DataValidationError:
            return None


class InputValidationLoggingMiddleware(ModuleLoggerMiddleware):
    """
    Input validation logging middleware for API requests.

    Features:
    - Input validation logging
    - Business rule validation
    - Data sanitization logging
    - Validation error tracking
    - Compliance logging
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """
        Input validation logging for API requests.

        Features:
        - Input validation logging
        - Business rule validation
        - Data sanitization logging
        - Validation error tracking
        """
        if request.url.path in VERBOSE_LOGGING_EXCLUDED_PATHS:
            return await call_next(request)

        if _api_middleware_mode_minimal():
            return await call_next(request)

        # Log input validation
        self.logger.info(
            "API input validation",
            extra={
                "method": request.method,
                "path": request.url.path,
                "content_type": request.headers.get("Content-Type", "unknown"),
                "content_length": request.headers.get("Content-Length", "0"),
                "query_params_count": len(request.query_params),
                "headers_count": len(request.headers),
            },
        )

        # Validate request method
        if request.method not in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
            self.logger.warning(
                "Invalid HTTP method",
                extra={"method": request.method, "path": request.url.path},
            )

        # Validate content type for POST/PUT requests (include multipart uploads)
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get("Content-Type", "")
            allowed_prefixes = (
                "application/json",
                "application/x-www-form-urlencoded",
                "multipart/form-data",
            )
            if not any(content_type.startswith(p) for p in allowed_prefixes):
                self.logger.warning(
                    "Invalid content type for request body",
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "content_type": content_type,
                    },
                )

        # Process request
        response = await call_next(request)

        # Log validation results
        self.logger.info(
            "API input validation completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "validation_success": response.status_code < 400,
            },
        )

        return response


def setup_enhanced_api_logging(app: Any) -> None:
    """
    Setup enhanced API logging middleware.

    Args:
        app: FastAPI application instance
    """
    # Add enhanced logging middleware
    app.add_middleware(EnhancedAPILoggingMiddleware)
    app.add_middleware(SecurityLoggingMiddleware)
    app.add_middleware(PerformanceLoggingMiddleware)
    app.add_middleware(InputValidationLoggingMiddleware)

    logger.debug("Enhanced API logging middleware configured")
