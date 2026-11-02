from src.errors import ValidationError as DomainValidationError
from src.utils.exceptions import APIError

"""
Valuation API Routes - Refactored

This is the main orchestrator for the refactored valuation API routes.
It integrates all the modular components to provide comprehensive valuation
API endpoints.

Author: Upswitch Engineering Team
Date: October 2025
Status: Production Ready
"""

import asyncio
import hashlib
import time
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder

# CRITICAL FIX: Use custom JSONResponse that handles Decimal serialization
from fastapi.responses import Response, StreamingResponse
from pydantic import ValidationError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from src.api.json_response import JSONResponse  # Custom JSONResponse with Decimal support

# Import response schemas from unified schemas
# Import request schemas from the new unified schemas
from src.api.schemas import (
    MonteCarloResults,
    QuickValuationRequest,
    QuickValuationResponse,
    ValuationRequest,
    ValuationResponse,
)
from src.config import get_settings
from src.errors.error_types import DomainError

# Authentication
from src.middleware.auth import ServiceAccount, User, require_auth_or_service
from src.utils.correlation import ensure_correlation_id
from src.utils.correlation_context import set_correlation_id
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.exceptions import (
    CalculationError,
    ConfigurationError,
    DatabaseError,
    DataQualityError,
    DCFCalculationError,
    MarketDataError,
    MultiplesCalculationError,
    SynthesisError,
)
from src.utils.logging import get_logger
from src.utils.request_deduplication import get_deduplicator

from .business_logic_validator import BusinessLogicValidator
from .coordinators import (
    ErrorHandlingCoordinator,
    MetricsLoggingCoordinator,
    QuickValuationCoordinator,
    RequestProcessingCoordinator,
    ResponseBuildingCoordinator,
    StreamingCoordinator,
    ValuationOrchestrationCoordinator,
)

# Import moved inside function to avoid circular import
# from .valuation_stream import create_manual_streaming_response
from .metrics import (
    auto_enable_counter,
    data_quality_gauge,
    deprecation_warning_counter,
    endpoint_usage_counter,
    mode_selection_counter,
    normalization_counter,
    optional_fields_gauge,
    validation_error_counter,
    valuation_duration_seconds,
    valuation_failure_counter,
    valuation_requests_total,
    valuation_success_counter,
)
from .schema_adapter import SchemaAdapter
from .utils.request_utils import (
    auto_enable_phase2_features,
    get_request_fingerprint,
    is_quick_mode,
    log_field_usage,
    normalize_request_fields,
)
from .valuation_orchestrator import get_valuation_orchestrator
from .valuation_processor import ValuationProcessor

# Import other response schemas from valuation_types
from .valuation_types import (
    ErrorResponse,
    FinancialMetricsResponse,
    MCPInsightsResponse,
    ValidationResponse,
)
from .valuation_validators import ValuationValidator

logger = get_logger(__name__)

# Standardized HTTP error status code mapping
ERROR_STATUS_MAP = {
    "ValidationError": 422,
    "ValueError": 422,
    "KeyError": 400,
    "PermissionError": 403,
    "NotFoundError": 404,
    "FileNotFoundError": 404,
    "TimeoutError": 504,
    "ConnectionError": 503,
    "DatabaseError": 503,
}


# Create router with /valuation prefix
# This combines with /api/v1 prefix in main.py to create /api/v1/valuation/*
# Route structure: /api/v1 + /valuation + /endpoint = /api/v1/valuation/endpoint
router = APIRouter(prefix="/valuation", tags=["valuation"])

# Include PDF report routes
from src.api.routes.valuation_pdf import router as pdf_router

router.include_router(pdf_router, prefix="/pdf", tags=["reports"])

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["100 per minute"])

# Initialize components
validator = ValuationValidator()
business_logic_validator = BusinessLogicValidator()
orchestrator = get_valuation_orchestrator()
processor = ValuationProcessor()

# Initialize coordinators
request_coordinator = RequestProcessingCoordinator(validator, business_logic_validator)
metrics_coordinator = MetricsLoggingCoordinator()
response_coordinator = ResponseBuildingCoordinator()
quick_valuation_coordinator = QuickValuationCoordinator(orchestrator)
orchestration_coordinator = ValuationOrchestrationCoordinator(orchestrator)
error_coordinator = ErrorHandlingCoordinator()
streaming_coordinator = StreamingCoordinator(validator, business_logic_validator)


@router.post("/calculate")  # Removed response_model to allow JSONResponse return
@limiter.limit("20 per minute")
async def calculate_valuation(
    valuation_request: ValuationRequest,
    request: Request,
    response: Response,
    auth: Union[User, ServiceAccount] = Depends(require_auth_or_service),
    mode: Optional[str] = None,  # Optional: "quick" | "comprehensive" | None (auto-detect)
) -> JSONResponse:
    """
    Unified valuation endpoint - handles both quick and comprehensive valuations.

    **Auto-Detection:**
    - Automatically detects quick mode if only basic data (revenue, EBITDA) is provided
    - Uses comprehensive mode if historical data, balance sheet, or explicit methodology is provided

    **Manual Override:**
    - `mode="quick"`: Force quick valuation (fast, multiples-only, no HTML reports)
    - `mode="comprehensive"`: Force comprehensive valuation (DCF + Multiples + HTML reports)
    - `mode=None`: Auto-detect based on data completeness

    **Auto-Enable Phase 2 Features (Comprehensive Mode Only):**
    - **Monte Carlo Simulation**: Automatically enabled when ≥2 years of historical data provided
    - **Asymmetric Ranges**: Automatically enabled for SMEs (<50 employees)
    - **Intelligent Selection**: Automatically enabled with complete balance sheet + historical data

    **Field Normalization:**
    - `employee_count` → `number_of_employees`
    - Top-level `revenue` → `current_year_data.revenue`
    - Missing `methodology` → defaults to "HYBRID"
    - `shares_for_sale` supports partial-stake valuations and scales equity outputs proportionally

    Route: POST /api/v1/valuation/calculate
    """
    # Start timing
    start_time = time.time()

    # Track endpoint usage
    endpoint_usage_counter.labels(endpoint="calculate").inc()

    # Process request using coordinator
    try:
        valuation_request, correlation_id, fingerprint, use_quick_mode = (
            await request_coordinator.process_request(valuation_request, request, response, mode)
        )
        selection_method = "explicit" if mode else "auto"

        # Track mode selection
        metrics_coordinator.track_mode_selection(use_quick_mode, selection_method)

        # Track request metrics
        metrics_coordinator.track_request(valuation_request)

        # Log raw request
        await metrics_coordinator.log_raw_request(request)
    except HTTPException:
        # Re-raise HTTP exceptions (validation errors, etc.)
        raise

    # BANK-GRADE: All requests use comprehensive mode (quick mode disabled)
    # Comprehensive mode always generates HTML reports (html_report)
    # Comprehensive mode: Use orchestration coordinator
    try:
        # Extract client-provided ID if present, otherwise generate
        valuation_id = (
            valuation_request.valuation_id or f"val_{int(time.time() * 1000)}_{fingerprint[:9]}"
        )

        # Orchestrate comprehensive valuation with explicit ID
        valuation_response = await orchestration_coordinator.orchestrate_valuation(
            valuation_request, fingerprint, correlation_id, request, valuation_id
        )

        # Track success
        metrics_coordinator.track_success(valuation_request, valuation_response)

        # Build and return response using coordinator (async for PDFGenerationStrategy)
        return await response_coordinator.build_response(valuation_response, correlation_id)

    # Top-level exception handler - catches ANY exception not caught above
    except HTTPException as http_exc:
        # HTTPException should propagate to FastAPI
        raise http_exc
    except (
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
    ) as top_level_error:
        # Handle domain-specific errors
        raise error_coordinator.handle_domain_error(top_level_error, correlation_id, request)
    except APIError as top_level_error:
        # Handle API-level errors
        result = error_coordinator.handle_api_error(top_level_error, correlation_id, request)
        # If result is JSONResponse, return it directly; otherwise raise HTTPException
        if isinstance(result, JSONResponse):
            return result
        raise result
    except ValueError as top_level_error:
        # ValuationValidator (result checks: required fields, range, NaN) — not generic ValueError
        msg = str(top_level_error)
        if msg.startswith("Valuation failed:") or msg.startswith("Invalid range:"):
            raise error_coordinator.handle_valuation_result_error(
                top_level_error, correlation_id, request
            )
        raise

    finally:
        # Track duration - always executes regardless of success or failure
        duration = time.time() - start_time
        valuation_duration_seconds.labels(
            methodology=getattr(valuation_request, "methodology", "HYBRID")
        ).observe(duration)


@router.get("/financial-metrics/{valuation_id}", response_model=FinancialMetricsResponse)
async def get_financial_metrics(
    valuation_id: str,
    http_request: Request,
    auth: Union[User, ServiceAccount] = Depends(require_auth_or_service),
) -> FinancialMetricsResponse:
    """
    Get financial metrics for a valuation

    This endpoint provides detailed financial analysis and metrics
    for a completed valuation.
    """
    try:
        logger.info("Retrieving financial metrics", valuation_id=valuation_id)

        # This would typically retrieve from database
        # For now, return mock data
        response = FinancialMetricsResponse(
            valuation_id=valuation_id,
            profitability_metrics={
                "gross_margin": Decimal("0.65"),
                "ebitda_margin": Decimal("0.25"),
                "net_margin": Decimal("0.15"),
                "roa": Decimal("0.12"),
                "roe": Decimal("0.18"),
            },
            liquidity_metrics={
                "current_ratio": Decimal("2.5"),
                "quick_ratio": Decimal("1.8"),
                "cash_ratio": Decimal("0.5"),
            },
            efficiency_metrics={
                "asset_turnover": Decimal("1.2"),
                "inventory_turnover": Decimal("6.0"),
                "receivables_turnover": Decimal("8.0"),
            },
            leverage_metrics={
                "debt_to_equity": Decimal("0.4"),
                "debt_to_assets": Decimal("0.3"),
                "interest_coverage": Decimal("5.0"),
            },
            growth_metrics={
                "revenue_growth": Decimal("0.15"),
                "ebitda_growth": Decimal("0.20"),
                "asset_growth": Decimal("0.10"),
            },
            industry_benchmarks={
                "industry_avg_margin": Decimal("0.20"),
                "industry_avg_roa": Decimal("0.10"),
                "industry_avg_roe": Decimal("0.15"),
            },
            created_at=datetime.now(),
        )

        logger.info("Financial metrics retrieved successfully", valuation_id=valuation_id)

        return response

    except (
        ValidationError,
        CalculationError,
        DatabaseError,
        ValueError,
        TypeError,
        AttributeError,
    ) as e:
        logger.error(
            f"Error retrieving financial metrics: {e}",
            extra={"error_type": type(e).__name__, "valuation_id": valuation_id},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal server error",
                "message": "Failed to retrieve financial metrics.",
            },
        )


@router.get("/mcp-insights/{valuation_id}", response_model=MCPInsightsResponse)
async def get_mcp_insights(
    valuation_id: str,
    http_request: Request,
    auth: Union[User, ServiceAccount] = Depends(require_auth_or_service),
) -> MCPInsightsResponse:
    """
    Get MCP (Market Context and Performance) insights for a valuation

    This endpoint provides market intelligence and insights
    for a completed valuation.
    """
    try:
        logger.info("Retrieving MCP insights", valuation_id=valuation_id)

        # This would typically retrieve from MCP service
        # For now, return mock data
        response = MCPInsightsResponse(
            valuation_id=valuation_id,
            market_insights=[
                "Market showing strong growth in technology sector",
                "Increased competition from new entrants",
                "Regulatory changes affecting industry dynamics",
            ],
            industry_trends=[
                "Digital transformation accelerating",
                "Sustainability focus increasing",
                "Remote work trends continuing",
            ],
            competitive_analysis=[
                "Strong market position in core segments",
                "Competitive advantage in technology",
                "Pricing pressure from new competitors",
            ],
            risk_factors=["Economic uncertainty", "Regulatory changes", "Technology disruption"],
            opportunities=[
                "Market expansion opportunities",
                "Technology innovation potential",
                "Strategic partnership possibilities",
            ],
            recommendations=[
                "Focus on digital transformation",
                "Strengthen competitive positioning",
                "Monitor market trends closely",
            ],
            created_at=datetime.now(),
        )

        logger.info("MCP insights retrieved successfully", valuation_id=valuation_id)

        return response

    except (
        ValidationError,
        MarketDataError,
        DatabaseError,
        ValueError,
        TypeError,
        AttributeError,
    ) as e:
        logger.error(
            f"Error retrieving MCP insights: {e}",
            extra={"error_type": type(e).__name__, "valuation_id": valuation_id},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal server error",
                "message": "Failed to retrieve MCP insights.",
            },
        )


@router.post("/calculate/stream")
@limiter.limit("20 per minute")
async def stream_manual_valuation_endpoint(
    valuation_request: ValuationRequest,
    request: Request,
    auth: Union[User, ServiceAccount] = Depends(require_auth_or_service),
    correlation_id: Optional[str] = None,
):
    """
    Stream manual valuation calculation with progressive HTML report generation

    This endpoint streams HTML sections as they're generated, providing
    instant feedback and progressive rendering similar to AI-guided flow.

    **Progressive Rendering:**
    - Section-by-section HTML generation
    - Real-time progress updates (0%, 25%, 50%, 75%, 100%)
    - SSE streaming for instant updates

    **Use Cases:**
    - Manual form submissions
    - Long-running calculations
    - Better UX with instant feedback

    Route: POST /api/v1/valuation/calculate/stream
    """
    # Lazy import to avoid circular dependency
    from .valuation_stream import create_manual_streaming_response

    try:
        # Prepare streaming request using coordinator
        valuation_request, correlation_id, request_id = (
            await streaming_coordinator.prepare_streaming_request(
                valuation_request, request, correlation_id
            )
        )

        # Extract origin from request for CORS headers
        origin = request.headers.get("origin")

        return create_manual_streaming_response(
            valuation_request, request_id=request_id, correlation_id=correlation_id, origin=origin
        )

    except HTTPException:
        # Re-raise HTTP exceptions (validation errors, etc.)
        raise
    except ValidationError as validation_error:
        # Handle Pydantic validation errors from FastAPI's automatic validation
        logger.error(
            "Pydantic validation error in stream endpoint",
            extra={
                "correlation_id": correlation_id if "correlation_id" in locals() else "unknown",
                "request_id": request_id if "request_id" in locals() else "unknown",
                "error": str(validation_error),
                "error_type": type(validation_error).__name__,
                "errors": validation_error.errors() if hasattr(validation_error, "errors") else [],
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "Request validation failed",
                "errors": (
                    validation_error.errors()
                    if hasattr(validation_error, "errors")
                    else [{"field": "unknown", "message": str(validation_error)}]
                ),
            },
        )
    except (
        CalculationError,
        DomainValidationError,
        ValueError,
        TypeError,
        AttributeError,
    ) as e:
        logger.error(
            "Failed to start manual valuation stream",
            extra={
                "correlation_id": correlation_id if "correlation_id" in locals() else "unknown",
                "request_id": request_id if "request_id" in locals() else "unknown",
                "error": str(e),
                "error_type": type(e).__name__,
                "company_name": getattr(valuation_request, "company_name", "N/A"),
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to start valuation stream",
                "message": "An internal error prevented the valuation stream from starting.",
                "correlation_id": correlation_id if "correlation_id" in locals() else "unknown",
            },
        )


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint for valuation service

    Returns the health status of the valuation service and its components.
    """
    try:
        logger.info("Performing health check")

        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "components": {
                "validator": "healthy",
                "orchestrator": "healthy",
                "processor": "healthy",
            },
            "version": "1.0.0",
        }

        logger.info("Health check completed successfully")

        return health_status

    except (ConfigurationError, DatabaseError, ValueError, TypeError, AttributeError) as e:
        logger.error(
            f"Error in health check: {e}", extra={"error_type": type(e).__name__}, exc_info=True
        )
        return {"status": "unhealthy", "timestamp": datetime.now().isoformat(), "error": str(e)}


# Error handlers are handled by the main FastAPI app, not individual routers
