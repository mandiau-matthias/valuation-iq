"""FastAPI middleware registration for the ValuationIQ API."""

import json
import logging
from typing import List, Union

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from src.api.enhanced_logging import setup_enhanced_api_logging
from src.api.json_response import JSONResponse
from src.config import Settings
from src.middleware.audit_trail import AuditTrailMiddleware
from src.middleware.request_size_limit import (
    RequestSizeLimitMiddleware,
    _resolve_max_request_size_from_env,
)


def normalize_allowed_origins(allowed_origins: Union[List[str], str]) -> List[str]:
    """Normalize CORS origin settings to the list FastAPI expects."""
    if isinstance(allowed_origins, str):
        return [origin.strip() for origin in allowed_origins.split(",") if origin.strip()]
    return allowed_origins


def register_api_middleware(
    app: FastAPI,
    settings: Settings,
    logger: logging.Logger,
) -> None:
    """Register cross-cutting API middleware in the historical execution order."""
    setup_enhanced_api_logging(app)
    logger.debug("🔧 Enhanced API logging middleware registered")

    allowed_origins_list = normalize_allowed_origins(settings.allowed_origins)
    logger.debug(
        "🔧 CORS middleware configured",
        extra={
            "allowed_origins": allowed_origins_list,
            "allow_credentials": settings.cors_allow_credentials,
            "origin_count": len(allowed_origins_list),
        },
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins_list,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
        expose_headers=[
            "Content-Type",
            "Cache-Control",
            "Connection",
            "Access-Control-Allow-Origin",
            "Access-Control-Allow-Headers",
        ],
    )

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

    max_request_size_bytes = _resolve_max_request_size_from_env()
    app.add_middleware(RequestSizeLimitMiddleware, max_request_size=max_request_size_bytes)
    logger.debug(
        "🔧 Request size limit middleware registered (%dMB)",
        max_request_size_bytes // 1024 // 1024,
    )

    if settings.request_body_logging:
        _register_request_body_logging_middleware(app, logger)

    register_service_request_signature_middleware(app, logger)
    _register_auth_logging_middleware(app, logger)

    app.add_middleware(
        AuditTrailMiddleware,
        excluded_paths=["/health", "/health/live", "/metrics", "/docs", "/redoc", "/openapi.json"],
    )
    logger.debug("🔧 Audit trail middleware registered")


def _register_request_body_logging_middleware(
    app: FastAPI,
    logger: logging.Logger,
) -> None:
    @app.middleware("http")
    async def request_body_logging_middleware(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Log raw request body for debugging validation errors."""
        if request.method == "POST" and "/valuation" in request.url.path:
            try:
                body = await request.body()
                if body:
                    try:
                        body_json = json.loads(body.decode("utf-8"))
                        logger.info(
                            "Request body (debug)",
                            extra={
                                "path": request.url.path,
                                "body_keys": (
                                    list(body_json.keys()) if isinstance(body_json, dict) else None
                                ),
                                "body_size_bytes": len(body),
                            },
                        )
                    except Exception as exc:
                        logger.warning(f"Could not parse request body as JSON: {exc}")
            except Exception as exc:
                logger.warning(f"Could not read request body: {exc}")
        return await call_next(request)


def register_service_request_signature_middleware(
    app: FastAPI,
    logger: logging.Logger,
) -> None:
    @app.middleware("http")
    async def service_request_signature_middleware(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """
        Require HMAC integrity for any request that presents a service JWT.

        Route dependencies still own authorization. This guard makes the
        service-token transport contract global so public or optional-auth
        routes cannot accidentally accept unsigned service credentials.
        """
        from src.middleware.auth import (
            extract_bearer_token_from_request,
            is_service_token,
            require_request_signature,
        )

        token = extract_bearer_token_from_request(request)
        try:
            if token and is_service_token(token):
                await require_request_signature(request)
        except HTTPException as exc:
            logger.warning(
                "Service request rejected by signature guard",
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "status_code": exc.status_code,
                },
            )
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=exc.headers,
            )

        return await call_next(request)

    logger.debug("🔧 Service request signature guard registered")


def _register_auth_logging_middleware(
    app: FastAPI,
    logger: logging.Logger,
) -> None:
    @app.middleware("http")
    async def auth_logging_middleware(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """
        Log authentication context without enforcing authentication.

        Route dependencies remain responsible for auth decisions.
        """
        try:
            from src.middleware.auth import get_current_user_optional

            user = await get_current_user_optional(request)
            if user:
                request.state.user = user
                logger.info(
                    "Request authenticated",
                    extra={
                        "user_id": user.id,
                        "has_email": bool(user.email),
                        "path": request.url.path,
                        "method": request.method,
                    },
                )
        except Exception as exc:
            logger.debug(f"Auth check skipped: {str(exc)}")

        return await call_next(request)

    logger.debug("🔧 Authentication logging middleware registered")
