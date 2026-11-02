"""
Quick Valuation Coordinator

Handling Coordinator

Handles quick valuation flow - conversion, processing, and response formatting.
Extracted from valuation.py calculate_valuation() function.

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive error handling
- Detailed logging
- No code duplication
"""

from typing import Dict, Any
from decimal import Decimal
from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder
# CRITICAL FIX: Use custom JSONResponse that handles Decimal serialization
from src.api.json_response import JSONResponse  # Custom JSONResponse with Decimal support
from pydantic import ValidationError

from src.api.schemas import ValuationRequest, QuickValuationRequest
from src.utils.logging import get_logger
from src.utils.exceptions import (
    CalculationError,
    DatabaseError,
    MarketDataError,
    ConfigurationError,
    DomainError,
)
from src.errors import ValidationError as DomainValidationError

from ..schema_adapter import SchemaAdapter
from ..valuation_orchestrator import ValuationOrchestrator

logger = get_logger(__name__)


class QuickValuationCoordinator:
    """
    Coordinates quick valuation activities.
    
    Responsibilities:
    - Convert ValuationRequest to QuickValuationRequest
    - Process quick valuation
    - Format response
    - Handle errors
    """
    
    def __init__(self, orchestrator: ValuationOrchestrator):
        """
        Initialize quick valuation coordinator.
        
        Args:
            orchestrator: ValuationOrchestrator instance
        """
        self.orchestrator = orchestrator
        self.logger = logger
    
    async def process_quick_valuation(
        self, valuation_request: ValuationRequest, start_time: float
    ) -> JSONResponse:
        """
        Process quick valuation request.
        
        Args:
            valuation_request: Valuation request
            start_time: Start time for duration calculation
            
        Returns:
            JSONResponse with quick valuation results
            
        Raises:
            HTTPException: If processing fails
        """
        try:
            # Create QuickValuationRequest from ValuationRequest
            quick_request = QuickValuationRequest(
                revenue=valuation_request.current_year_data.revenue,
                ebitda=valuation_request.current_year_data.ebitda or Decimal("0.0"),
                industry=valuation_request.industry,
                country_code=valuation_request.country_code,
                company_name=valuation_request.company_name,
                registration_number=getattr(valuation_request, "registration_number", None),
                kbo_number=getattr(valuation_request, "kbo_number", None),
                kvk_number=getattr(valuation_request, "kvk_number", None),
                vat_number=getattr(valuation_request, "vat_number", None),
                legal_form=getattr(valuation_request, "legal_form", None),
                postal_code=getattr(valuation_request, "postal_code", None),
                city=getattr(valuation_request, "city", None),
                founding_year=valuation_request.founding_year,
                total_debt=valuation_request.current_year_data.total_liabilities or Decimal("0.0"),
                cash=valuation_request.current_year_data.cash or Decimal("0.0"),
                business_type_id=valuation_request.business_type_id,
            )
            
            # Transform to legacy format and process
            legacy_request = SchemaAdapter.transform_quick_valuation_request(quick_request)
            valuation_response = await self.orchestrator.process_quick_valuation(legacy_request)
            
            # Convert QuickValuationResponse to JSONResponse format
            import uuid
            response_data = {
                "valuation_id": str(uuid.uuid4()),
                "company_name": valuation_request.company_name,
                "valuation_range_mid": valuation_response.valuation_range_mid,
                "valuation_range_low": valuation_response.valuation_range_low,
                "valuation_range_high": valuation_response.valuation_range_high,
                "confidence_score": valuation_response.confidence_score,
                "key_factors": valuation_response.key_factors,
                "recommendations": valuation_response.recommendations,
                "methodology": "QUICK",
                "mode": "quick",
            }
            
            import time
            
            self.logger.info(
                "Quick valuation completed",
                extra={
                    "company": valuation_request.company_name,
                    "valuation_mid": valuation_response.valuation_range_mid,
                    "duration_seconds": round(time.time() - start_time, 3),
                },
            )
            
            return JSONResponse(
                content=jsonable_encoder(response_data), status_code=status.HTTP_200_OK
            )
        
        except (CalculationError, ValidationError, DomainValidationError) as e:
            self.logger.error(
                f"Quick valuation failed: {e}",
                extra={"company": valuation_request.company_name},
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": "Quick valuation failed", "message": "An internal error occurred during quick valuation."},
            )
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            self.logger.error(
                f"Quick valuation validation error: {e}",
                extra={"company": valuation_request.company_name},
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": "Quick valuation validation failed", "message": "Invalid input data. Please check your request."},
            )
        except (DatabaseError, MarketDataError, ConfigurationError, DomainError) as e:
            self.logger.error(
                f"Quick valuation service error: {e}",
                extra={"company": valuation_request.company_name, "error_type": type(e).__name__},
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": "Quick valuation failed", "message": "A service error occurred. Please try again."},
            )
