"""
Sentry Configuration for Error Tracking

This module configures Sentry for comprehensive error tracking
and performance monitoring in the valuation engine.
"""

import logging
import os
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.httpx import HttpxIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.stdlib import StdlibIntegration
from decimal import Decimal

logger = logging.getLogger(__name__)


def configure_sentry():
    """Configure Sentry for error tracking and performance monitoring."""

    # Get Sentry DSN from environment
    sentry_dsn = os.getenv("SENTRY_DSN")

    if not sentry_dsn:
        logger.warning("sentry_disabled", extra={"reason": "SENTRY_DSN not configured"})
        return False

    try:
        # Configure Sentry with integrations
        sentry_sdk.init(
            dsn=sentry_dsn,
            environment=os.getenv("ENVIRONMENT", "development"),
            release=os.getenv("APP_VERSION", "1.0.0"),
            # Performance monitoring
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.1")),
            # Error tracking
            send_default_pii=False,  # Don't send personally identifiable information
            attach_stacktrace=True,
            max_breadcrumbs=50,
            # Integrations
            integrations=[
                FastApiIntegration(auto_enable_instrumentations=True),
                SqlalchemyIntegration(),
                RedisIntegration(),
                AsyncioIntegration(),
                HttpxIntegration(),
                LoggingIntegration(
                    level=None,  # Capture all log levels
                    event_level=None,
                ),
                StdlibIntegration(),
            ],
            # Custom tags
            before_send=before_send_filter,
            # Custom context
            before_send_transaction=before_send_transaction_filter,
        )

        # Set custom tags
        sentry_sdk.set_tag("service", "upswitch-valuation-engine")
        sentry_sdk.set_tag("component", "api")

        # Set user context (if available)
        sentry_sdk.set_context(
            "app",
            {
                "name": "Upswitch Valuation Engine",
                "version": "1.0.0",
                "environment": os.getenv("ENVIRONMENT", "development"),
            },
        )

        logger.info("sentry_configured")
        return True

    except Exception as exc:
        logger.error("sentry_configuration_failed", extra={"error": str(exc)})
        return False


def before_send_filter(event, hint):
    """Filter events before sending to Sentry."""

    # Don't send certain types of errors
    if event.get("exception"):
        exc_type = event["exception"]["values"][0].get("type")

        # Skip common non-critical errors
        skip_errors = ["KeyboardInterrupt", "SystemExit", "asyncio.CancelledError"]

        if exc_type in skip_errors:
            return None

    # Filter out sensitive data
    if event.get("request"):
        # Remove sensitive headers
        headers = event["request"].get("headers", {})
        sensitive_headers = ["authorization", "cookie", "x-api-key"]

        for header in sensitive_headers:
            if header in headers:
                headers[header] = "[Filtered]"

    # Add custom context
    event.setdefault("tags", {}).update(
        {"service": "upswitch-valuation-engine", "component": "api"}
    )

    return event


def before_send_transaction_filter(event, hint):
    """Filter transactions before sending to Sentry."""

    # Add custom transaction tags
    event.setdefault("tags", {}).update(
        {"service": "upswitch-valuation-engine", "component": "api"}
    )

    return event


def capture_valuation_error(error: Exception, context: dict = None):
    """Capture valuation-specific errors with context."""

    with sentry_sdk.push_scope() as scope:
        # Set context
        if context:
            scope.set_context("valuation", context)

        # Set tags
        scope.set_tag("error_type", "valuation_error")
        scope.set_tag("component", "valuation_engine")

        # Capture the error
        sentry_sdk.capture_exception(error)


def capture_api_error(error: Exception, request_context: dict = None):
    """Capture API-specific errors with request context."""

    with sentry_sdk.push_scope() as scope:
        # Set context
        if request_context:
            scope.set_context("request", request_context)

        # Set tags
        scope.set_tag("error_type", "api_error")
        scope.set_tag("component", "api")

        # Capture the error
        sentry_sdk.capture_exception(error)


def capture_ai_error(error: Exception, ai_context: dict = None):
    """Capture AI-specific errors with context."""

    with sentry_sdk.push_scope() as scope:
        # Set context
        if ai_context:
            scope.set_context("ai", ai_context)

        # Set tags
        scope.set_tag("error_type", "ai_error")
        scope.set_tag("component", "ai_conversation")

        # Capture the error
        sentry_sdk.capture_exception(error)


def capture_performance_issue(
    operation: str, duration: Decimal, threshold: Decimal = 5.0
):
    """Capture performance issues."""

    if duration > threshold:
        sentry_sdk.capture_message(
            f"Performance issue: {operation} took {duration:.2f}s (threshold: {threshold}s)",
            level="warning",
        )


def set_user_context(user_id: str = None, session_id: str = None):
    """Set user context for error tracking."""

    if user_id:
        sentry_sdk.set_user({"id": user_id})

    if session_id:
        sentry_sdk.set_tag("session_id", session_id)


def add_breadcrumb(
    message: str, category: str = "info", level: str = "info", data: dict = None
):
    """Add breadcrumb for debugging."""

    sentry_sdk.add_breadcrumb(
        message=message, category=category, level=level, data=data
    )
