"""Exception handler registration for the ValuationIQ API."""

import builtins
import logging
import math
import traceback
from datetime import date, datetime
from decimal import Decimal
from typing import TypeAlias

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError

from src.api.json_response import JSONResponse
from src.config import Settings
from src.database.connection import StatelessModeError

JsonSafeValue: TypeAlias = (
    str | int | float | bool | None | list["JsonSafeValue"] | dict[str, "JsonSafeValue"]
)
JsonSafeObject: TypeAlias = dict[str, JsonSafeValue]


def register_error_handlers(
    app: FastAPI,
    settings: Settings,
    logger: logging.Logger,
) -> None:
    """Register API exception handlers."""

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = _json_safe_validation_errors(exc.errors())
        error_summary = [
            {
                "field": ".".join(str(loc) for loc in err.get("loc", [])),
                "message": err.get("msg", "Unknown error"),
            }
            for err in errors
        ]
        error_lines = [f"{error['field']}: {error['message']}" for error in error_summary]
        msg_suffix = "; ".join(error_lines[:5]) if error_lines else "unknown"
        logger.warning(
            "Request validation failed: %s",
            msg_suffix,
            extra={
                "path": request.url.path,
                "method": request.method,
                "error_count": len(errors),
                "errors": error_summary,
            },
        )
        if settings.debug:
            for index, err in enumerate(errors, 1):
                field = ".".join(str(loc) for loc in err.get("loc", []))
                logger.debug(f"Validation error {index}: {field} - {err.get('msg', 'Unknown')}")

        return JSONResponse(
            status_code=422,
            content={
                "error": "Request validation failed",
                "errors": errors,
                "detail": errors,
                "status_code": 422,
                "timestamp": datetime.now().isoformat(),
            },
        )

    @app.exception_handler(StatelessModeError)
    async def stateless_mode_exception_handler(
        request: Request, exc: StatelessModeError
    ) -> JSONResponse:
        return _stateless_mode_response(request, exc, logger)

    # Python 3.11+: unwrap StatelessModeError from ExceptionGroup to avoid log spam.
    exception_group = getattr(builtins, "ExceptionGroup", None)
    if exception_group is not None and issubclass(exception_group, Exception):

        @app.exception_handler(exception_group)
        async def exception_group_handler(request: Request, exc: Exception) -> JSONResponse:
            for sub_exc in getattr(exc, "exceptions", ()):
                if isinstance(sub_exc, StatelessModeError):
                    return _stateless_mode_response(request, sub_exc, logger)
            logger.error("Unhandled ExceptionGroup: %s", exc, exc_info=True)
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "detail": str(exc),
                    "status_code": 500,
                    "timestamp": datetime.now().isoformat(),
                },
            )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "status_code": exc.status_code,
                "timestamp": datetime.now().isoformat(),
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        error_message = str(exc)
        error_type = type(exc).__name__
        stack_trace = traceback.format_exc()
        logger.error(
            f"Unhandled exception: {error_type}: {error_message}",
            exc_info=True,
            extra={
                "event": "valuation_engine_unhandled_exception",
                "http_path": getattr(request.url, "path", str(request.url)),
                "http_method": request.method,
            },
        )
        if settings.debug:
            logger.debug(f"Stack trace: {stack_trace}")

        response_content: JsonSafeObject = {
            "error": "Internal server error",
            "status_code": 500,
            "timestamp": datetime.now().isoformat(),
            "error_type": error_type,
        }
        if settings.debug:
            response_content["error_message"] = (
                error_message[:500] if error_message else "Unknown error"
            )
        elif error_type in ("ImportError", "ModuleNotFoundError"):
            response_content["error_message"] = (
                error_message[:500] if error_message else "Unknown import error (check server logs)"
            )
        return JSONResponse(status_code=500, content=response_content)

    logger.debug("Enhanced error handlers registered")


def _stateless_mode_response(
    request: Request,
    exc: StatelessModeError,
    logger: logging.Logger,
) -> JSONResponse:
    """Build the shared 503 response for stateful operations in stateless mode."""
    logger.info(
        "StatelessModeError: %s",
        str(exc),
        extra={"path": request.url.path, "method": request.method},
    )
    return JSONResponse(
        status_code=503,
        content={
            "error": "Registry search requires Titan. In stateless mode, use Titan's /registry/search endpoint.",
            "detail": str(exc),
            "status_code": 503,
            "timestamp": datetime.now().isoformat(),
        },
    )


def _json_safe_validation_errors(errors: list[object]) -> list[JsonSafeObject]:
    """Return Pydantic validation errors that can always be JSON-rendered."""
    safe_errors: list[JsonSafeObject] = []
    for error in errors:
        safe_error = _json_safe_value(error)
        if isinstance(safe_error, dict):
            safe_errors.append(safe_error)
        else:
            safe_errors.append({"msg": safe_error})
    return safe_errors


def _json_safe_value(value: object) -> JsonSafeValue:
    if isinstance(value, dict):
        return {str(key): _json_safe_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe_value(item) for item in value]
    if isinstance(value, Decimal):
        if value.is_nan() or value.is_infinite():
            return None
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)
