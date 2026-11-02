"""
Valuation Orchestration Coordinator

Handles comprehensive valuation orchestration - deduplication, timeout, orchestrator calls.
Extracted from valuation.py calculate_valuation() function.

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive error handling
- Detailed logging
- No code duplication
"""

import asyncio
from typing import Optional
from fastapi import HTTPException, Request

from src.api.schemas import ValuationRequest, ValuationResponse
from src.config import get_settings
from src.utils.logging import get_logger
from src.utils.exceptions import ConfigurationError
from src.utils.request_deduplication import get_deduplicator

from ..valuation_orchestrator import ValuationOrchestrator

logger = get_logger(__name__)


class ValuationOrchestrationCoordinator:
    """
    Coordinates valuation orchestration activities.
    
    Responsibilities:
    - Diagnostic logging
    - Settings retrieval
    - Deduplication setup
    - Timeout handling
    - Orchestrator execution
    """
    
    def __init__(self, orchestrator: ValuationOrchestrator):
        """
        Initialize valuation orchestration coordinator.
        
        Args:
            orchestrator: ValuationOrchestrator instance
        """
        self.orchestrator = orchestrator
        self.logger = logger
    
    async def orchestrate_valuation(
        self,
        valuation_request: ValuationRequest,
        fingerprint: str,
        correlation_id: str,
        request: Request,
        valuation_id: Optional[str] = None,
    ) -> ValuationResponse:
        """
        Orchestrate comprehensive valuation calculation.
        
        Args:
            valuation_request: Valuation request
            fingerprint: Request fingerprint for deduplication
            correlation_id: Correlation ID for tracking
            request: FastAPI request object
            valuation_id: Optional client-provided valuation ID for idempotency
            
        Returns:
            ValuationResponse from orchestrator
            
        Raises:
            HTTPException: If orchestration fails or times out
        """
        # Diagnostic logging
        self._log_diagnostic_info(valuation_request)
        
        # Get timeout settings
        timeout_seconds = self._get_timeout_seconds()
        
        # Initialize deduplicator
        deduplicator = get_deduplicator()
        
        self.logger.debug(
            f"orchestrate_valuation() | company={valuation_request.company_name} | valuation_id={valuation_id} | fingerprint={fingerprint[:50]}..."
        )

        # Execute valuation with deduplication and timeout
        try:
            
            # Build context with valuation_id if provided
            context = {"correlation_id": correlation_id}
            if valuation_id:
                context["valuation_id"] = valuation_id
            
            valuation_response = await asyncio.wait_for(
                deduplicator.deduplicate(
                    fingerprint,
                    self.orchestrator.process_comprehensive_valuation,
                    valuation_request,
                    context=context,
                ),
                timeout=timeout_seconds,
            )

            return valuation_response
        
        except asyncio.TimeoutError:
            self.logger.error(
                f"Valuation calculation timeout (>{timeout_seconds}s)",
                extra={
                    "correlation_id": correlation_id,
                    "company_name": valuation_request.company_name,
                    "timeout_seconds": timeout_seconds,
                    "methodology": getattr(valuation_request, "methodology", "HYBRID"),
                },
            )
            raise HTTPException(
                status_code=504,
                detail={
                    "error": "Valuation calculation timeout",
                    "message": f"The valuation calculation took longer than {timeout_seconds} seconds. Please try again.",
                    "correlation_id": correlation_id,
                    "timeout_seconds": timeout_seconds,
                },
            )
    
    def _log_diagnostic_info(self, valuation_request: ValuationRequest) -> None:
        """
        Log diagnostic information about incoming request.
        """
        self.logger.debug(
            f"Incoming valuation request | company={valuation_request.company_name} | "
            f"business_type_id={getattr(valuation_request, 'business_type_id', None)} | "
            f"use_dcf={getattr(valuation_request, 'use_dcf', None)} | "
            f"use_multiples={getattr(valuation_request, 'use_multiples', None)} | "
            f"methodology={getattr(valuation_request, 'methodology', None)}"
        )
    
    def _get_timeout_seconds(self) -> float:
        """
        Get timeout seconds from settings.
        
        Returns:
            Timeout in seconds
            
        Raises:
            ConfigurationError: If settings cannot be loaded
        """
        try:
            settings = get_settings()
            return float(settings.valuation_timeout_seconds)
        except (ConfigurationError, AttributeError, ImportError) as settings_error:
            self.logger.error(
                f"Configuration error: {settings_error}",
                extra={"error_type": type(settings_error).__name__},
                exc_info=True,
            )
            raise ConfigurationError(
                f"Failed to load settings: {settings_error}"
            ) from settings_error
