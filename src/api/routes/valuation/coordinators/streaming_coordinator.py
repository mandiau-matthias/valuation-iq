"""
Streaming Coordinator

Handles streaming valuation endpoint - request processing, validation, and stream setup.
Extracted from valuation.py stream_manual_valuation_endpoint() function.

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive error handling
- Detailed logging
- No code duplication
"""

import uuid
from typing import Dict, Optional, Tuple
from fastapi import HTTPException, Request, status
from pydantic import ValidationError

from src.api.schemas import ValuationRequest
from src.utils.correlation import ensure_correlation_id
from src.utils.correlation_context import set_correlation_id
from src.utils.logging import get_logger
from src.utils.exceptions import CalculationError
from src.errors import ValidationError as DomainValidationError

from ..valuation_validators import ValuationValidator
from ..business_logic_validator import BusinessLogicValidator
from ..utils.request_utils import (
    normalize_request_fields,
    auto_enable_phase2_features,
)

logger = get_logger(__name__)


class StreamingCoordinator:
    """
    Coordinates streaming valuation activities.
    
    Responsibilities:
    - Request normalization
    - Request validation
    - Business logic validation
    - Correlation ID setup
    - Stream initialization
    """
    
    def __init__(
        self,
        validator: ValuationValidator,
        business_logic_validator: BusinessLogicValidator,
    ):
        """
        Initialize streaming coordinator.
        
        Args:
            validator: ValuationValidator instance
            business_logic_validator: BusinessLogicValidator instance
        """
        self.validator = validator
        self.business_logic_validator = business_logic_validator
        self.logger = logger
    
    async def prepare_streaming_request(
        self,
        valuation_request: ValuationRequest,
        request: Request,
        correlation_id: Optional[str] = None,
    ) -> Tuple[ValuationRequest, str, str]:
        """
        Prepare request for streaming valuation.
        
        Args:
            valuation_request: Valuation request
            request: FastAPI request object
            correlation_id: Optional correlation ID
            
        Returns:
            Tuple of (normalized_request, correlation_id, request_id)
            
        Raises:
            HTTPException: If validation fails
        """
        # Extract correlation ID from headers if not provided
        if not correlation_id:
            correlation_id = request.headers.get("X-Correlation-ID")
        
        # Ensure correlation ID exists
        if not correlation_id:
            try:
                correlation_id = ensure_correlation_id(dict(request.headers))
            except (ValueError, TypeError, AttributeError, KeyError):
                import time
                
                correlation_id = f"corr_{int(time.time() * 1000)}"
        
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        
        # Set correlation ID in context for auto-injection into all logs
        set_correlation_id(correlation_id)
        
        # Normalize duplicate fields from different frontend sources
        valuation_request = normalize_request_fields(valuation_request)
        
        # Auto-enable Phase 2 features based on data quality
        valuation_request = auto_enable_phase2_features(valuation_request)
        
        # Validate request
        validation_result = await self.validator.validate_valuation_request(valuation_request)
        if not validation_result.is_valid:
            self.logger.warning(
                "Stream request validation failed",
                extra={
                    "correlation_id": correlation_id,
                    "request_id": request_id,
                    "total_errors": len(validation_result.errors),
                    "error_fields": [e.field for e in validation_result.errors],
                    "error_messages": [e.message for e in validation_result.errors],
                    "company_name": getattr(valuation_request, "company_name", "N/A"),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "Validation failed",
                    "errors": [
                        {"field": e.field, "message": e.message}
                        for e in validation_result.errors
                    ],
                },
            )
        
        # Business logic validation. Prefer the request-scoped API so streaming
        # requests do not mutate the shared validator warning buffer.
        if hasattr(self.business_logic_validator, "validate_with_integrity_warnings"):
            (
                business_logic_errors,
                integrity_warnings,
            ) = self.business_logic_validator.validate_with_integrity_warnings(valuation_request)
        else:
            business_logic_errors = self.business_logic_validator.validate(valuation_request)
            try:
                integrity_warnings = self.business_logic_validator.consume_integrity_warnings()
            except AttributeError:
                integrity_warnings = []
        if integrity_warnings:
            self._attach_integrity_warnings(valuation_request, integrity_warnings)
        if business_logic_errors:
            error_summary = self.business_logic_validator.get_error_summary(business_logic_errors)
            self.logger.warning(
                "Stream request business logic validation failed",
                extra={
                    "correlation_id": correlation_id,
                    "request_id": request_id,
                    "business_logic_errors": error_summary,
                    "company_name": getattr(valuation_request, "company_name", "N/A"),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": "Business logic validation failed", "errors": error_summary},
            )
        
        self.logger.info(
            "Starting manual valuation stream",
            extra={
                "request_id": request_id,
                "correlation_id": correlation_id,
                "company_name": valuation_request.company_name,
            },
        )
        
        return valuation_request, correlation_id, request_id

    @staticmethod
    def _attach_integrity_warnings(
        valuation_request: ValuationRequest,
        integrity_warnings: list[Dict[str, object]],
    ) -> None:
        metadata = getattr(valuation_request, "metadata", None)
        if not isinstance(metadata, dict):
            metadata = {}

        existing = metadata.get("_integrity_warnings")
        if isinstance(existing, list):
            existing.extend(integrity_warnings)
        else:
            metadata["_integrity_warnings"] = list(integrity_warnings)

        try:
            valuation_request.metadata = metadata
        except (AttributeError, TypeError):
            pass
