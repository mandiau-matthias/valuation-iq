"""
Error Handling Coordinator

Handles top-level error handling and error response formatting.
Extracted from valuation.py calculate_valuation() function.

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive error handling
- Detailed logging
- No code duplication
"""

import traceback
from typing import Optional, Dict, Any
from fastapi import HTTPException, Request
# CRITICAL FIX: Use custom JSONResponse that handles Decimal serialization
from src.api.json_response import JSONResponse  # Custom JSONResponse with Decimal support
from pydantic import ValidationError

from src.config import get_settings
from src.utils.logging import get_logger
from src.utils.exceptions import (
    CalculationError,
    ConfigurationError,
    DatabaseError,
    DataQualityError,
    MarketDataError,
    DCFCalculationError,
    MultiplesCalculationError,
    SynthesisError,
    APIError,
)
from src.errors import ValidationError as DomainValidationError
from src.errors.error_types import DomainError

logger = get_logger(__name__)


class ErrorHandlingCoordinator:
    """
    Coordinates error handling activities.
    
    Responsibilities:
    - Domain error handling
    - API error handling
    - Error response formatting
    - Error logging
    """
    
    def __init__(self):
        """Initialize error handling coordinator."""
        self.logger = logger
    
    def handle_domain_error(
        self,
        error: Exception,
        correlation_id: Optional[str],
        request: Request,
    ) -> HTTPException:
        """
        Handle domain-specific errors.

        The response body always carries `error_type` and `error_message`
        so the Titan pass-through and the FE can show the underlying cause
        instead of a generic 500 string. When the exception is a
        ValuationEngineError, also include `code` and a sanitized `context`
        (no PII / no large payloads) — that's what lets the calibration
        UI surface "BENCHMARK_CONTRACT_REQUIRED" instead of "Request failed".
        """
        top_level_correlation_id = correlation_id if correlation_id else "unknown"
        error_type = type(error).__name__
        error_message = str(error)

        # Pull structured fields off ValuationEngineError subclasses when present.
        # `code` lives inside `context` for the preflight raise sites
        # (e.g. {"code": "BENCHMARK_CONTRACT_REQUIRED"}). `error_code` is the
        # class-level fallback. Keep both so callers can pick.
        error_context = getattr(error, "context", None)
        if not isinstance(error_context, dict):
            error_context = {}
        structured_code = error_context.get("code") or getattr(error, "error_code", None)
        sanitized_context = self._sanitize_error_context(error_context)

        self.logger.error(
            "Domain error in valuation endpoint",
            extra={
                "correlation_id": top_level_correlation_id,
                "error": error_message,
                "error_type": error_type,
                "error_code": structured_code,
                "error_context": sanitized_context,
                "request_path": request.url.path if request else "unknown",
                "request_method": request.method if request else "unknown",
                "traceback": traceback.format_exc(),
            },
            exc_info=True,
        )

        detail: Dict[str, Any] = {
            "error": "Valuation calculation error",
            "message": "An internal error occurred during valuation calculation. Please try again or contact support.",
            "correlation_id": top_level_correlation_id,
            "error_type": error_type,
            "error_message": error_message,
        }
        if structured_code:
            detail["code"] = structured_code
        if sanitized_context:
            detail["context"] = sanitized_context

        return HTTPException(status_code=500, detail=detail)

    @staticmethod
    def _sanitize_error_context(context: Dict[str, Any]) -> Dict[str, Any]:
        """Whitelist small, non-sensitive keys for the wire response.

        We do not want to leak full request payloads or financial figures
        in error envelopes — only the identifiers and policy keys that
        explain *which* invariant fired.
        """
        allowed_keys = {
            "code",
            "country_code",
            "business_type_id",
            "methodology",
            "selected_method",
            "step",
            "calculation_type",
            "required_contract_fields",
            "missing_required_fields",
            "benchmark_contract_present",
            "benchmark_contract_status",
            "field",
            "reason",
            "scope_stage",
            "data_source",
            # APIError-specific (handle_api_error)
            "api_name",
            "upstream_status",
        }
        sanitized: Dict[str, Any] = {}
        for key, value in context.items():
            if key not in allowed_keys:
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                sanitized[key] = value
            elif isinstance(value, (list, tuple)):
                sanitized[key] = [
                    item
                    for item in value
                    if isinstance(item, (str, int, float, bool))
                ][:20]
        return sanitized

    def handle_valuation_result_error(
        self,
        error: ValueError,
        correlation_id: Optional[str],
        request: Request,
    ) -> HTTPException:
        """
        Map ValueError from result validation (e.g. ValuationValidator.validate_results)
        to HTTP 422 so clients get a structured message instead of an unhandled 500.

        The full internal error (raw values, field names) is logged
        server-side for engineering investigation, but only a generic
        user-friendly message + correlation_id is returned to the
        client. This avoids leaking implementation details into
        end-user UI and gives support staff a single ID to search by.
        """
        cid = correlation_id if correlation_id else "unknown"
        # Log the full internal detail server-side
        self.logger.error(
            "[VALIDATOR] Valuation result validation failed — internal detail",
            extra={
                "correlation_id": cid,
                "error": str(error),
                "error_type": type(error).__name__,
                "request_path": request.url.path if request else "unknown",
                "request_method": request.method if request else "unknown",
                "user_visible_message": (
                    "Generic message returned to client; raw error in logs only"
                ),
            },
        )
        # Classify so we can give a more useful hint when possible
        msg = str(error)
        if msg.startswith("Invalid range:"):
            user_message = (
                "We couldn't produce a defensible valuation band for this "
                "input. This is rare — please contact support with the "
                "reference below and we'll investigate."
            )
            error_kind = "range_consistency"
        elif "Missing required fields" in msg:
            user_message = (
                "Some required financial inputs are missing. Please "
                "review your input and try again."
            )
            error_kind = "missing_fields"
        elif "NaN" in msg or "Infinity" in msg:
            user_message = (
                "We detected invalid numeric inputs (e.g. NaN or "
                "infinity). Please review your financial inputs."
            )
            error_kind = "invalid_numerics"
        else:
            user_message = (
                "We couldn't complete this valuation. Please contact "
                "support with the reference below."
            )
            error_kind = "validation_failed"
        return HTTPException(
            status_code=422,
            detail={
                "error": "Valuation result validation failed",
                "error_kind": error_kind,
                "message": user_message,
                "correlation_id": cid,
                "support_reference": cid,
            },
        )

    def handle_api_error(
        self,
        error: APIError,
        correlation_id: Optional[str],
        request: Request,
    ) -> HTTPException:
        """
        Handle API-level errors.
        
        Args:
            error: API error exception
            correlation_id: Correlation ID for tracking
            request: FastAPI request object
            
        Returns:
            HTTPException with error details
        """
        top_level_correlation_id = correlation_id if correlation_id else "unknown"
        
        # Extract error context
        error_context = {}
        if hasattr(error, "__cause__") and error.__cause__:
            error_context["cause"] = str(error.__cause__)
        if hasattr(error, "__context__") and error.__context__:
            error_context["context"] = str(error.__context__)
        
        # Log via structured logger
        try:
            self.logger.error(
                "CRITICAL: Unhandled exception in valuation endpoint",
                extra={
                    "correlation_id": top_level_correlation_id,
                    "error": str(error),
                    "error_type": type(error).__name__,
                    "request_path": request.url.path if request else "unknown",
                    "request_method": request.method if request else "unknown",
                    "error_context": error_context if error_context else None,
                    "traceback": traceback.format_exc(),
                },
                exc_info=True,
            )
        except (ValueError, TypeError, AttributeError) as log_error:
            # Fallback: If logger fails, use basic print (should never happen)
            import sys
            
            sys.stderr.write(f"CRITICAL: Logger failed: {log_error}\n")
            sys.stderr.write(f"Original error: {error}\n")
            sys.stderr.flush()
        
        # Try to return proper HTTPException, but have fallback if that fails.
        # Envelope parity with `handle_domain_error`: include `error_type`,
        # `error_message`, structured `code`, and a sanitized context block so
        # the Titan pass-through and the FE can render a typed remediation
        # regardless of which handler caught the exception. APIError carries
        # `api_name` and `status_code` attributes worth surfacing.
        api_error_code = getattr(error, "error_code", None) or type(error).__name__
        api_status_code = getattr(error, "status_code", None)
        api_name = getattr(error, "api_name", None)
        api_inner_context = getattr(error, "context", None)
        if not isinstance(api_inner_context, dict):
            api_inner_context = {}
        sanitized_api_context = self._sanitize_error_context(
            {
                **api_inner_context,
                # Project the typed APIError attributes into the same allowlist
                # space so the FE sees them too. `api_name` and `upstream_status`
                # are explicitly added to the sanitizer below.
                **({"api_name": api_name} if api_name else {}),
                **({"upstream_status": api_status_code} if api_status_code is not None else {}),
            }
        )
        try:
            detail: Dict[str, Any] = {
                "error": "Internal server error",
                "message": "An unexpected error occurred during valuation calculation",
                "correlation_id": top_level_correlation_id,
                "error_type": type(error).__name__,
                "error_message": str(error),
            }
            if api_error_code:
                detail["code"] = api_error_code
            if sanitized_api_context:
                detail["context"] = sanitized_api_context
            return HTTPException(status_code=500, detail=detail)
        except (ValueError, TypeError, AttributeError) as http_exception_error:
            self.logger.error(
                "HTTPException creation failed, using fallback response",
                extra={
                    "http_exception_error": str(http_exception_error),
                    "original_error_type": type(error).__name__,
                    "original_error": str(error),
                },
                exc_info=True,
            )

            try:
                # Fallback: Return minimal error response as JSONResponse with error details
                error_message = str(error)[:500] if str(error) else "Unknown error"
                minimal_error_response = {
                    "error": "Internal server error",
                    "message": "An unexpected error occurred during valuation calculation",
                    "correlation_id": top_level_correlation_id,
                    "status": "error",
                    "error_type": type(error).__name__,
                    "error_message": error_message,
                }
                # Add debug info if available
                if get_settings().debug:
                    minimal_error_response["debug_info"] = {
                        "error_type": type(error).__name__,
                        "error_message": error_message,
                        "error_args": (
                            str(error.args) if hasattr(error, "args") else None
                        ),
                    }
                # Return JSONResponse directly (can't raise HTTPException)
                return JSONResponse(
                    status_code=500,
                    content=minimal_error_response,
                    headers={"X-Correlation-ID": top_level_correlation_id},
                )
            except (ValueError, TypeError, AttributeError, KeyError) as fallback_error:
                self.logger.critical(
                    "Fallback response also failed - re-raising original error",
                    extra={
                        "fallback_error": str(fallback_error),
                        "original_error": str(error),
                    },
                    exc_info=True,
                )
                raise error
    
    def get_domain_error_types(self) -> tuple:
        """
        Get tuple of domain error types for exception handling.
        
        Returns:
            Tuple of exception types
        """
        return (
            CalculationError,
            ValidationError,
            DomainValidationError,
            DataQualityError,
            MarketDataError,
            ConfigurationError,
            DatabaseError,
            DomainError,
            DCFCalculationError,
            MultiplesCalculationError,
            SynthesisError,
        )

