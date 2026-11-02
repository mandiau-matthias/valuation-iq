"""
Request Processing Coordinator

Handles request normalization, validation, mode detection, and correlation ID setup.
Extracted from valuation.py calculate_valuation() function.

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive error handling
- Detailed logging
- No code duplication
"""

import asyncio
import os
from typing import Any, Dict, Optional, Tuple

import httpx
from fastapi import Request, Response
from pydantic import ValidationError

from src.api.schemas import ValuationRequest
from src.config import get_settings
from src.utils.correlation import ensure_correlation_id
from src.utils.correlation_context import set_correlation_id
from src.utils.exceptions import ConfigurationError
from src.utils.logging import get_logger

from ..business_logic_validator import BusinessLogicValidator
from ..utils.request_utils import (
    auto_enable_phase2_features,
    get_request_fingerprint,
    is_quick_mode,
    log_field_usage,
    normalize_request_fields,
)
from ..valuation_validators import ValuationValidator

logger = get_logger(__name__)
BUSINESS_TYPES_API_URL = os.getenv(
    "BUSINESS_TYPES_API_URL",
    "http://localhost:3000/api/business-types",
)

# Import metrics (lazy import to avoid circular dependencies)
try:
    from ..metrics import business_type_industry_derivations

    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    logger.warning("⚠️ Metrics not available for request processing coordinator")


class RequestProcessingCoordinator:
    """
    Coordinates request processing activities.

    Responsibilities:
    - Request normalization
    - Field validation
    - Business logic validation
    - Correlation ID setup
    - Mode detection
    - Request fingerprinting
    """

    def __init__(
        self,
        validator: Optional[ValuationValidator] = None,
        business_logic_validator: Optional[BusinessLogicValidator] = None,
    ):
        """
        Initialize request processing coordinator.

        Args:
            validator: Optional ValuationValidator instance
            business_logic_validator: Optional BusinessLogicValidator instance
        """
        self.validator = validator or ValuationValidator()
        self.business_logic_validator = business_logic_validator or BusinessLogicValidator()
        self.logger = logger

    async def process_request(
        self,
        valuation_request: ValuationRequest,
        request: Request,
        response: Response,
        mode: Optional[str] = None,
    ) -> Tuple[ValuationRequest, str, str, bool]:
        """
        Process and validate incoming valuation request.

        Args:
            valuation_request: Incoming valuation request
            request: FastAPI request object
            response: FastAPI response object
            mode: Optional mode override ("quick" | "comprehensive" | None)

        Returns:
            Tuple of (processed_request, correlation_id, fingerprint, use_quick_mode)

        Raises:
            HTTPException: If validation fails
        """
        # Step 1: Generate correlation ID
        correlation_id = self._setup_correlation_id(request)

        # Step 2: Normalize request fields
        valuation_request = normalize_request_fields(valuation_request)

        # Step 3: Auto-enable Phase 2 features
        valuation_request = auto_enable_phase2_features(valuation_request)

        # Step 3.25: Hydrate missing business type metadata from Titan before local fallback.
        valuation_request = await self._hydrate_business_type_from_titan(
            valuation_request, correlation_id
        )

        # Step 3.5: Validate and enrich business type data (MANUAL FLOW INTEGRATION)
        valuation_request = await self._validate_business_type(valuation_request, correlation_id)

        # Step 4: Re-validate normalized request
        valuation_request = self._revalidate_request(valuation_request, correlation_id)

        # Step 5: Generate request fingerprint
        fingerprint = get_request_fingerprint(valuation_request)

        # Step 6: Set response headers
        self._set_response_headers(response, valuation_request, correlation_id, fingerprint)

        # Step 7: Detect mode
        use_quick_mode, selection_method = self._detect_mode(valuation_request, mode)

        # Step 8: Validate request
        await self._validate_request(valuation_request, correlation_id)

        # Step 9: Validate business logic
        self._validate_business_logic(valuation_request, correlation_id)

        # Step 10: Log field usage
        log_field_usage(valuation_request)

        return valuation_request, correlation_id, fingerprint, use_quick_mode

    def _setup_correlation_id(self, request: Request) -> str:
        """
        Setup correlation ID for request tracking.

        Args:
            request: FastAPI request object

        Returns:
            Correlation ID string
        """
        try:
            correlation_id = ensure_correlation_id(dict(request.headers))
        except (ValueError, TypeError, AttributeError, KeyError):
            import time

            correlation_id = f"corr_{int(time.time() * 1000)}"

        # Set in context for auto-injection into all logs
        set_correlation_id(correlation_id)

        return correlation_id

    async def _validate_business_type(
        self, valuation_request: ValuationRequest, correlation_id: str
    ) -> ValuationRequest:
        """
        Validate and enrich business type data (MANUAL FLOW - EXACT MATCH).

        ✅ EXACT MATCH: This flow receives pre-validated business_type_id from dropdown (UUID).
        ❌ NO FUZZY: User selected from fixed list, no fuzzy matching needed here.

        WHAT: Auto-derive industry from business_type_id using EXACT database lookup
        WHY: Ensure consistency between business_type_id and industry (manual flow sends both)
        HOW: business_type_id provided → EXACT DB lookup by UUID → auto-fill industry

        Flow:
        1. User selects from dropdown → business_type_id (UUID)
        2. Exact database lookup: repo.get_industry_for_business_type(uuid)
        3. Auto-fill industry in request

        PATTERN: Matches conversational flow business type handling (but uses EXACT lookup)
        - business_type_id is pre-validated against the governed business-type catalog
        - industry is auto-derived from business_type_id via EXACT lookup
        - Both stored in valuation request for downstream use

        Args:
            valuation_request: Valuation request
            correlation_id: Correlation ID for logging

        Returns:
            Enriched valuation request with industry auto-filled if needed
        """
        business_type_id = valuation_request.business_type_id
        current_industry = valuation_request.industry

        # If business_type_id is provided, validate and auto-derive industry
        if business_type_id:
            try:
                from src.database.business_types_repository import get_business_types_repository

                # Query database for industry mapping
                with get_business_types_repository() as repo:
                    industry = repo.get_industry_for_business_type(business_type_id)

                    if industry:
                        # Auto-fill industry only when missing. If the request already
                        # carries an industry, preserve it for valuation assumptions
                        # and store the repository mapping separately for provenance.
                        if not current_industry:
                            self.logger.info(
                                "✅ Auto-derived industry from business_type_id (MANUAL FLOW)",
                                extra={
                                    "correlation_id": correlation_id,
                                    "business_type_id": business_type_id,
                                    "industry_before": current_industry,
                                    "industry_after": industry,
                                    "source": "database_business_type_mapping",
                                    "flow_type": "manual",
                                },
                            )
                            valuation_request.industry = industry

                            # Track industry derivation metric
                            if METRICS_AVAILABLE:
                                business_type_industry_derivations.labels(source="database").inc()
                        elif current_industry != industry:
                            if not getattr(valuation_request, "industry_mapping", None):
                                valuation_request.industry_mapping = industry
                            self.logger.debug(
                                "ℹ️ Preserving request industry over repository mapping",
                                extra={
                                    "correlation_id": correlation_id,
                                    "business_type_id": business_type_id,
                                    "industry_request": current_industry,
                                    "industry_repository": industry,
                                    "industry_mapping_set": getattr(
                                        valuation_request, "industry_mapping", None
                                    ),
                                    "source": "database_business_type_mapping",
                                    "flow_type": "manual",
                                },
                            )
                        else:
                            self.logger.info(
                                "✅ Business type and industry already consistent",
                                extra={
                                    "correlation_id": correlation_id,
                                    "business_type_id": business_type_id,
                                    "industry": current_industry,
                                },
                            )
                    else:
                        self.logger.warning(
                            "⚠️ No industry found for business_type_id",
                            extra={
                                "correlation_id": correlation_id,
                                "business_type_id": business_type_id,
                                "current_industry": current_industry,
                            },
                        )
            except Exception as e:
                self.logger.error(
                    f"❌ Failed to auto-derive industry from business_type_id: {e}",
                    extra={
                        "correlation_id": correlation_id,
                        "business_type_id": business_type_id,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                    exc_info=True,
                )
                # Don't fail the request - industry might already be set
        else:
            # No business_type_id provided (old manual flow or missing data)
            if current_industry:
                self.logger.info(
                    "ℹ️ Industry provided without business_type_id (legacy flow)",
                    extra={"correlation_id": correlation_id, "industry": current_industry},
                )
            else:
                self.logger.warning(
                    "⚠️ Neither business_type_id nor industry provided",
                    extra={"correlation_id": correlation_id},
                )

        return valuation_request

    async def _hydrate_business_type_from_titan(
        self,
        valuation_request: ValuationRequest,
        correlation_id: str,
    ) -> ValuationRequest:
        """
        Hydrate missing business type metadata from Titan before local fallback.

        Titan remains the source of truth for business_types DB data. This method is
        intentionally request-scoped and stateless, so there is no shared mutable state
        or race-prone cache mutation inside the Python valuation process.
        """
        business_type_id = getattr(valuation_request, "business_type_id", None)
        if not business_type_id:
            return valuation_request

        has_authoritative_enrichment = any(
            getattr(valuation_request, field, None)
            for field in (
                "valuation_preferences",
                "sme_calibration",
                "sde_calibration",
                "ev_ebitda_multiple",
                "ev_revenue_multiple",
            )
        )
        if has_authoritative_enrichment:
            self.logger.debug(
                "Skipping Titan business type hydration - request already enriched",
                extra={
                    "correlation_id": correlation_id,
                    "business_type_id": business_type_id,
                },
            )
            return valuation_request

        async def _fetch_json(client: httpx.AsyncClient, url: str) -> Optional[Dict[str, Any]]:
            try:
                response = await client.get(url)
                response.raise_for_status()
                payload = response.json()
                if isinstance(payload, dict) and payload.get("success") is True:
                    data = payload.get("data")
                    return data if isinstance(data, dict) else None
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                self.logger.warning(
                    "Titan business type hydration request failed",
                    extra={
                        "correlation_id": correlation_id,
                        "business_type_id": business_type_id,
                        "url": url,
                        "error": str(exc),
                        "error_type": type(exc).__name__,
                    },
                )
            return None

        base_url = BUSINESS_TYPES_API_URL.rstrip("/")
        type_url = f"{base_url}/types/{business_type_id}"
        intelligence_url = f"{base_url}/intelligence/{business_type_id}"

        type_payload: Optional[Dict[str, Any]] = None
        intelligence_payload: Optional[Dict[str, Any]] = None

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                type_payload, intelligence_payload = await asyncio.gather(
                    _fetch_json(client, type_url),
                    _fetch_json(client, intelligence_url),
                )
        except Exception as exc:
            self.logger.warning(
                "Titan business type hydration unavailable",
                extra={
                    "correlation_id": correlation_id,
                    "business_type_id": business_type_id,
                    "base_url": base_url,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
            )
            return valuation_request

        if not type_payload and not intelligence_payload:
            return valuation_request

        valuation_preferences = dict(
            getattr(valuation_request, "valuation_preferences", None) or {}
        )
        type_payload = type_payload or {}
        intelligence_payload = intelligence_payload or {}

        if type_payload.get("dcfPreference") is not None:
            valuation_preferences["dcf_preference"] = type_payload["dcfPreference"]
        if intelligence_payload.get("dcf_preference") is not None:
            valuation_preferences["dcf_preference"] = intelligence_payload["dcf_preference"]
        if type_payload.get("multiplesPreference") is not None:
            valuation_preferences["multiples_preference"] = type_payload["multiplesPreference"]
        if intelligence_payload.get("multiples_preference") is not None:
            valuation_preferences["multiples_preference"] = intelligence_payload[
                "multiples_preference"
            ]
        if type_payload.get("ownerDependencyImpact") is not None:
            valuation_preferences["owner_dependency_impact"] = type_payload["ownerDependencyImpact"]
        if intelligence_payload.get("owner_dependency_impact") is not None:
            valuation_preferences["owner_dependency_impact"] = intelligence_payload[
                "owner_dependency_impact"
            ]

        if valuation_preferences and not getattr(valuation_request, "valuation_preferences", None):
            valuation_request.valuation_preferences = valuation_preferences

        titan_category_id = type_payload.get("category_id") or type_payload.get("category")
        titan_industry_mapping = type_payload.get("industryMapping")
        titan_industry = intelligence_payload.get("industry") or titan_industry_mapping
        titan_key_metrics = type_payload.get("keyMetrics") or intelligence_payload.get(
            "key_metrics"
        )
        titan_ev_ebitda = (
            type_payload.get("ev_ebitda_multiple")
            or type_payload.get("evEbitdaMultiple")
            or intelligence_payload.get("ev_ebitda_multiple")
            or intelligence_payload.get("evEbitdaMultiple")
        )
        titan_ev_revenue = (
            type_payload.get("ev_revenue_multiple")
            or type_payload.get("evRevenueMultiple")
            or intelligence_payload.get("ev_revenue_multiple")
            or intelligence_payload.get("evRevenueMultiple")
        )
        titan_pe_ratio = (
            type_payload.get("pe_ratio")
            or type_payload.get("peRatio")
            or intelligence_payload.get("pe_ratio")
            or intelligence_payload.get("peRatio")
        )
        titan_multiples_metadata = (
            type_payload.get("multiples_metadata")
            or type_payload.get("multiplesMetadata")
            or intelligence_payload.get("multiples_metadata")
            or intelligence_payload.get("multiplesMetadata")
        )
        titan_sme_calibration = (
            intelligence_payload.get("sme_calibration")
            or intelligence_payload.get("smeCalibration")
            or type_payload.get("sme_calibration")
            or type_payload.get("smeCalibration")
        )
        titan_sde_calibration = (
            intelligence_payload.get("sde_calibration")
            or intelligence_payload.get("sdeCalibration")
            or type_payload.get("sde_calibration")
            or type_payload.get("sdeCalibration")
        )
        titan_economic_context = (
            intelligence_payload.get("economic_context")
            or intelligence_payload.get("economicContext")
            or type_payload.get("economic_context")
            or type_payload.get("economicContext")
        )

        if titan_category_id and not getattr(valuation_request, "category_id", None):
            valuation_request.category_id = titan_category_id
        if titan_industry_mapping and not getattr(valuation_request, "industry_mapping", None):
            valuation_request.industry_mapping = titan_industry_mapping
        if titan_industry and not getattr(valuation_request, "industry", None):
            valuation_request.industry = titan_industry
        if titan_key_metrics and not getattr(valuation_request, "key_metrics", None):
            valuation_request.key_metrics = titan_key_metrics
        if titan_ev_ebitda and not getattr(valuation_request, "ev_ebitda_multiple", None):
            valuation_request.ev_ebitda_multiple = titan_ev_ebitda
        if titan_ev_revenue and not getattr(valuation_request, "ev_revenue_multiple", None):
            valuation_request.ev_revenue_multiple = titan_ev_revenue
        if titan_pe_ratio and not getattr(valuation_request, "pe_ratio", None):
            valuation_request.pe_ratio = titan_pe_ratio
        if titan_multiples_metadata and not getattr(valuation_request, "multiples_metadata", None):
            valuation_request.multiples_metadata = titan_multiples_metadata
        if titan_sme_calibration and not getattr(valuation_request, "sme_calibration", None):
            valuation_request.sme_calibration = titan_sme_calibration
        if titan_sde_calibration and not getattr(valuation_request, "sde_calibration", None):
            valuation_request.sde_calibration = titan_sde_calibration
        if titan_economic_context and not getattr(valuation_request, "economic_context", None):
            valuation_request.economic_context = titan_economic_context

        self.logger.info(
            "Hydrated business type metadata from Titan",
            extra={
                "correlation_id": correlation_id,
                "business_type_id": business_type_id,
                "hydrated_valuation_preferences": bool(valuation_preferences),
                "hydrated_category_id": bool(titan_category_id),
                "hydrated_industry": bool(titan_industry),
                "hydrated_key_metrics": bool(titan_key_metrics),
                "hydrated_ev_ebitda_multiple": bool(titan_ev_ebitda),
                "hydrated_ev_revenue_multiple": bool(titan_ev_revenue),
                "hydrated_sme_calibration": bool(titan_sme_calibration),
                "hydrated_economic_context": bool(titan_economic_context),
                "source": "titan_business_types_api",
            },
        )
        return valuation_request

    def _revalidate_request(
        self, valuation_request: ValuationRequest, correlation_id: str
    ) -> ValuationRequest:
        """
        Re-validate request after normalization.

        Args:
            valuation_request: Normalized request
            correlation_id: Correlation ID for logging

        Returns:
            Validated request

        Raises:
            HTTPException: If validation fails
        """
        try:
            # Use Pydantic's proper validation method to handle nested models correctly
            # This ensures YearDataInput and other nested models are properly reconstructed
            if hasattr(ValuationRequest, "model_validate"):
                # Pydantic v2: model_validate properly handles nested models
                validated_request = ValuationRequest.model_validate(
                    valuation_request.model_dump(mode="python")
                )
            else:
                # Pydantic v1: parse_obj properly handles nested models
                validated_request = ValuationRequest.parse_obj(valuation_request.dict())
            return validated_request
        except ValidationError as e:
            self.logger.error(
                f"Validation failed after normalization: {e.errors()}",
                extra={"correlation_id": correlation_id},
            )
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Validation failed after field normalization",
                    "errors": [
                        {"field": err["loc"][0] if err["loc"] else "unknown", "message": err["msg"]}
                        for err in e.errors()
                    ],
                    "hint": "Normalized values violated schema constraints",
                },
            )

    def _set_response_headers(
        self,
        response: Response,
        valuation_request: ValuationRequest,
        correlation_id: str,
        fingerprint: str,
    ) -> None:
        """
        Set response headers.

        Args:
            response: FastAPI response object
            valuation_request: Valuation request
            correlation_id: Correlation ID
            fingerprint: Request fingerprint
        """
        response.headers["X-Schema-Version"] = "2.1.0"
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Auto-Enable-Phase2"] = str(
            valuation_request.use_monte_carlo
            or valuation_request.use_intelligent_selection
            or valuation_request.use_asymmetric_ranges
        )
        response.headers["X-Request-Fingerprint"] = fingerprint

    def _detect_mode(
        self, valuation_request: ValuationRequest, mode: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Detect valuation mode (quick vs comprehensive).

        Args:
            valuation_request: Valuation request
            mode: Optional mode override

        Returns:
            Tuple of (use_quick_mode, selection_method)
        """
        if mode == "quick":
            self.logger.info(
                "Quick mode explicitly requested",
                extra={"company": valuation_request.company_name},
            )
            return True, "explicit"
        elif mode == "comprehensive":
            self.logger.info(
                "Comprehensive mode explicitly requested",
                extra={"company": valuation_request.company_name},
            )
            return False, "explicit"
        else:
            # Auto-detect based on data completeness. NOTE: per valuation.py:217
            # ("BANK-GRADE: All requests use comprehensive mode") the routing
            # ignores this verdict and always runs comprehensive. Kept at
            # DEBUG as a diagnostic of the heuristic's classification.
            use_quick_mode = is_quick_mode(valuation_request)
            selection_method = "auto"
            self.logger.debug(
                f"Auto-detect heuristic: {'quick' if use_quick_mode else 'comprehensive'}-mode profile "
                "(routing always uses comprehensive per bank-grade policy)",
                extra={
                    "company": valuation_request.company_name,
                    "has_historical": bool(valuation_request.historical_years_data),
                    "has_balance_sheet": bool(valuation_request.current_year_data.total_assets),
                    "methodology": valuation_request.methodology,
                },
            )
            return use_quick_mode, selection_method

    async def _validate_request(
        self, valuation_request: ValuationRequest, correlation_id: str
    ) -> None:
        """
        Validate request using validator.

        Args:
            valuation_request: Valuation request
            correlation_id: Correlation ID for logging

        Raises:
            HTTPException: If validation fails
        """
        # Validate required fields explicitly
        if not valuation_request.company_name:
            self.logger.warning(
                "Validation failed: Company name is required",
                extra={"correlation_id": correlation_id, "error_field": "company_name"},
            )
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Validation failed",
                    "errors": [{"field": "company_name", "message": "Company name is required"}],
                    "hint": "Check required fields and data types",
                },
            )

        if not valuation_request.current_year_data:
            self.logger.warning(
                "Validation failed: Current year financial data is required",
                extra={"correlation_id": correlation_id, "error_field": "current_year_data"},
            )
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Validation failed",
                    "errors": [
                        {
                            "field": "current_year_data",
                            "message": "Current year financial data is required",
                        }
                    ],
                    "hint": "Check required fields and data types",
                },
            )

        # Validate using validator
        validation_result = await self.validator.validate_valuation_request(valuation_request)
        if not validation_result.is_valid:
            self.logger.warning(
                "Request validation failed",
                extra={
                    "correlation_id": correlation_id,
                    "total_errors": len(validation_result.errors),
                    "error_fields": [e.field for e in validation_result.errors],
                    "error_messages": [e.message for e in validation_result.errors],
                },
            )
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "Validation failed",
                    "errors": [
                        {"field": e.field, "message": e.message} for e in validation_result.errors
                    ],
                },
            )

    def _validate_business_logic(
        self, valuation_request: ValuationRequest, correlation_id: str
    ) -> None:
        """
        Validate business logic constraints.

        Uses Titan-provided industry benchmarks when available for enhanced validation.

        Args:
            valuation_request: Valuation request
            correlation_id: Correlation ID for logging

        Raises:
            HTTPException: If business logic validation fails
        """
        # Extract Titan-provided industry benchmarks from request (if available).
        # These are context signals transported by Titan; valuation multiples
        # must still come from the resolved benchmark contract.
        titan_benchmarks = getattr(valuation_request, "industry_benchmarks", None)

        if titan_benchmarks:
            self.logger.debug(
                "✅ Using Titan-provided industry benchmarks for validation",
                extra={
                    "correlation_id": correlation_id,
                    "has_ebitda_margin": bool(titan_benchmarks.get("typical_ebitda_margin")),
                    "has_revenue": bool(titan_benchmarks.get("typical_revenue")),
                    "has_employee_count": bool(titan_benchmarks.get("typical_employee_count")),
                },
            )

        if hasattr(self.business_logic_validator, "validate_with_integrity_warnings"):
            (
                business_logic_errors,
                integrity_warnings,
            ) = self.business_logic_validator.validate_with_integrity_warnings(
                valuation_request,
                titan_benchmarks=titan_benchmarks,
            )
        else:
            business_logic_errors = self.business_logic_validator.validate(
                valuation_request,
                titan_benchmarks=titan_benchmarks,
            )
            # Legacy validators may still expose drain-on-read warnings.
            try:
                integrity_warnings = self.business_logic_validator.consume_integrity_warnings()
            except AttributeError:
                integrity_warnings = []

        # Pass-8: attach integrity warnings (e.g. EBITDA benchmark deviation)
        # directly from this validation pass. Avoid a shared drain-on-read buffer
        # so concurrent requests cannot steal or overwrite one another's warnings.
        if integrity_warnings:
            md = getattr(valuation_request, "metadata", None)
            if md is None:
                md = {}
            elif not isinstance(md, dict):
                md = {}
            existing = md.get("_integrity_warnings")
            if isinstance(existing, list):
                existing.extend(integrity_warnings)
            else:
                md["_integrity_warnings"] = list(integrity_warnings)
            try:
                valuation_request.metadata = md
            except (AttributeError, TypeError):
                # Pydantic frozen / validation refusal — skip rather than fail.
                pass

        if business_logic_errors:
            error_summary = self.business_logic_validator.get_error_summary(business_logic_errors)

            self.logger.warning(
                f"Business logic validation failed: {len(business_logic_errors)} error(s) for company={valuation_request.company_name}",
                extra={
                    "total_errors": len(business_logic_errors),
                    "error_fields": [e.field for e in business_logic_errors],
                    "error_messages": [e.message for e in business_logic_errors],
                    "error_summary": error_summary,
                    "company_name": valuation_request.company_name,
                    "correlation_id": correlation_id,
                },
            )

            # BANK-GRADE: Structured logging for validation errors (already logged above)
            # Additional detailed logging for each error
            for i, error in enumerate(business_logic_errors, 1):
                self.logger.error(
                    f"[VALIDATION-ERROR] Business logic validation error {i}/{len(business_logic_errors)}",
                    extra={
                        "error_index": i,
                        "total_errors": len(business_logic_errors),
                        "field": error.field,
                        "message": error.message,
                        "company_name": valuation_request.company_name,
                        "correlation_id": correlation_id,
                    },
                )

            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error_summary
            )
