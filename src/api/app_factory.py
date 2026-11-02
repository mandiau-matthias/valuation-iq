"""FastAPI application factory for ValuationIQ."""

import logging
import os
from typing import Tuple

from fastapi import FastAPI, Request
from fastapi.responses import Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import RequestResponseEndpoint

from src.api.app_error_handlers import register_error_handlers
from src.api.app_lifecycle import AppReadiness, register_lifecycle_events
from src.api.app_middleware import register_api_middleware
from src.api.app_openapi import configure_openapi
from src.api.app_operational_endpoints import register_operational_endpoints
from src.api.app_routes import is_heavy_route, register_lightweight_routes
from src.api.json_response import JSONResponse
from src.config import get_settings
from src.monitoring.sentry_config import configure_sentry
from src.utils.exceptions import DataValidationError
from src.utils.logging import setup_logging


def create_app() -> Tuple[FastAPI, AppReadiness]:
    """Create and configure the ValuationIQ FastAPI application."""
    settings = get_settings()
    logger = logging.getLogger("src.api.main")
    setup_logging()
    configure_sentry()

    code_version = os.getenv("VALUATIONIQ_VERSION", "ValuationIQ-2.0.0")
    show_api_docs = settings.environment != "production" or settings.expose_openapi_in_production
    _log_deployment_banner(logger, code_version, settings.request_body_logging)
    logger.info(
        "ValuationIQ started",
        extra={
            "version": code_version,
            "environment": settings.environment,
            "openapi_docs_enabled": show_api_docs,
        },
    )

    limiter = Limiter(key_func=get_remote_address, default_limits=["100 per minute"])

    app = FastAPI(
        title="Upswitch Valuation Engine API",
        description="Comprehensive valuation engine with intelligent business type analysis and methodology selection",
        version="1.0.0",
        docs_url="/docs" if show_api_docs else None,
        redoc_url="/redoc" if show_api_docs else None,
        openapi_url="/openapi.json" if show_api_docs else None,
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    logger.debug("🔧 Enhanced logging system initialized")
    _verify_logging(logger)

    register_error_handlers(app, settings, logger)
    register_api_middleware(app, settings, logger)

    readiness = AppReadiness()

    @app.middleware("http")
    async def heavy_route_readiness_middleware(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """
        Gate heavy routes until startup has fully completed.

        Heavy valuation/report routers are loaded during startup. This safety
        net prevents requests from entering those handlers before startup marks
        the application ready.
        """
        if not readiness.is_ready() and is_heavy_route(request.url.path):
            return JSONResponse(status_code=503, content={"status": "starting"})

        return await call_next(request)

    register_lightweight_routes(app, logger, settings)
    register_operational_endpoints(
        app, settings, logger, readiness.is_ready, runtime_status=readiness.snapshot
    )
    register_lifecycle_events(app, logger, readiness)
    configure_openapi(app)

    return app, readiness


def _log_deployment_banner(
    logger: logging.Logger, code_version: str, request_body_logging: bool
) -> None:
    logger.debug(
        "Deployment banner",
        extra={
            "version": code_version,
            "request_body_logging": request_body_logging,
        },
    )


def _verify_logging(logger: logging.Logger) -> None:
    try:
        from src.utils.valuation_logger import verify_logging_at_startup

        verify_logging_at_startup()
    except DataValidationError as exc:
        logger.warning(f"⚠️ Logging verification failed: {str(exc)}")
