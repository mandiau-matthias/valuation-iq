"""
Response Building Coordinator

Handles response serialization, HTML report preservation, and response validation.
Extracted from valuation.py calculate_valuation() function.

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive error handling
- Detailed logging
- No code duplication
"""

import base64
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from decimal import Decimal
# CRITICAL FIX: Use custom JSONResponse that handles Decimal serialization
from src.api.json_response import JSONResponse  # Custom JSONResponse with Decimal support
from fastapi.encoders import jsonable_encoder

from src.api.schemas import ValuationResponse
from src.config import get_settings
from src.utils.logging import get_logger
from src.utils.exceptions import CalculationError

from ..utils.response_serializer import custom_serializer

logger = get_logger(__name__)


class ResponseBuildingCoordinator:
    """
    BANK-GRADE COORDINATOR for response building activities.

    RESPONSIBILITIES:
    - Response serialization (Pydantic → Dict → JSON)
    - HTML report preservation (ensures HTML survives serialization)
    - Response validation (data integrity checks)
    - Response size management (payload optimization)
    - Fallback response creation (graceful degradation)

    BANK-GRADE FEATURES:
    - Preserves HTML reports through serialization (critical for frontend)
    - Handles serialization errors gracefully
    - Validates response structure
    - Manages response size for API efficiency
    - Provides full audit trail of serialization process

    DESIGN PATTERN: Coordinator Pattern
    - Coordinates multiple response building steps
    - Handles edge cases (HTML lost during serialization)
    - Provides unified interface for response building
    """
    
    def __init__(self):
        """Initialize response building coordinator."""
        self.logger = logger
        self.max_response_size_mb = Decimal("10.0")
    
    async def build_response(
        self,
        valuation_response: ValuationResponse,
        correlation_id: str,
    ) -> JSONResponse:
        """
        Build and serialize valuation response.
        
        Uses PDFGenerationStrategy (metadata, bookmarks, PDF/A) with PDFGenerator fallback.
        
        Args:
            valuation_response: Valuation response object
            correlation_id: Correlation ID for logging
            
        Returns:
            JSONResponse with serialized response
            
        Raises:
            HTTPException: If serialization fails
        """
        # Step 1: Validate response exists
        if valuation_response is None:
            from fastapi import HTTPException
            
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "Valuation response is None",
                    "message": "Orchestrator returned None instead of ValuationResponse",
                    "correlation_id": correlation_id,
                },
            )
        
        # Step 2: Extract HTML reports before serialization
        original_html_report = (
            valuation_response.html_report
            if hasattr(valuation_response, "html_report")
            else None
        )
        original_html_report_length = len(original_html_report) if original_html_report else 0
        original_pdf_html_report = getattr(valuation_response, "pdf_html_report", None)
        original_pdf_html_report_length = (
            len(original_pdf_html_report) if original_pdf_html_report else 0
        )

        # DEBUG: per-stage HTML diagnostic; routes already log the canonical
        # AUDIT response line. Keeping at DEBUG for offline serialization debugging.
        self.logger.debug(
            "🔍 [RESPONSE-BUILD] HTML reports before serialization",
            extra={
                "correlation_id": correlation_id,
                "original_html_report_length": original_html_report_length,
                "original_pdf_html_report_length": original_pdf_html_report_length,
                "has_html_report_attr": hasattr(valuation_response, "html_report"),
            },
        )
        
        # Step 2.5: Generate inline PDF from pre-rendered pdf_html_report
        # pdf_html_report is generated during html_report_generator (main_report_pdf/ templates).
        # If available, use it directly; otherwise skip inline PDF (Titan will re-generate later).
        pdf_html = getattr(valuation_response, "pdf_html_report", None)
        if pdf_html and isinstance(pdf_html, str) and len(pdf_html) >= 500:
            try:
                from src.services.infrastructure.html_report_service import get_html_report_service

                html_service = get_html_report_service()
                company_name = getattr(valuation_response, "company_name", "Company")
                valuation_id = getattr(valuation_response, "valuation_id", correlation_id)
                valuation_date = getattr(
                    valuation_response, "valuation_date", None
                ) or datetime.now(timezone.utc).strftime("%Y-%m-%d")

                # DEBUG: pdf_strategy logs the canonical PDF gen success;
                # this entry log is plumbing detail.
                self.logger.debug(
                    "[PDF-GENERATION] Generating PDF from pre-rendered pdf_html_report",
                    extra={
                        "correlation_id": correlation_id,
                        "valuation_id": valuation_id,
                        "company_name": company_name,
                        "pdf_html_length": len(pdf_html),
                    },
                )

                template_data = {
                    "company_name": company_name,
                    "company_id": valuation_id,
                    "valuation_id": valuation_id,
                    "valuation_date": valuation_date,
                }
                pdf_bytes = await html_service.generate_accountant_view_pdf(
                    html_content=pdf_html,
                    template_data=template_data,
                    correlation_id=correlation_id,
                )

                if pdf_bytes:
                    pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
                    valuation_response.pdf_bytes = pdf_base64
                    # DEBUG: pdf_strategy already logged the canonical PDF gen
                    # success with size at INFO; this is layered plumbing ack.
                    self.logger.debug(
                        "[PDF-GENERATION] PDF bytes generated from pdf_html_report",
                        extra={
                            "correlation_id": correlation_id,
                            "valuation_id": valuation_id,
                            "pdf_bytes_length": len(pdf_bytes),
                        },
                    )
            except Exception as pdf_error:
                self.logger.warning(
                    "[PDF-GENERATION] Failed to generate inline PDF (non-critical)",
                    extra={
                        "correlation_id": correlation_id,
                        "error": str(pdf_error),
                        "error_type": type(pdf_error).__name__,
                    },
                )
        
        # Step 3: Serialize response
        try:
            response_dict = self._serialize_response(valuation_response, correlation_id)
        except (TypeError, ValueError, AttributeError, KeyError) as serialization_error:
            # Attempt fallback serialization
            return self._build_fallback_response(
                valuation_response, correlation_id, serialization_error
            )
        
        # DEBUG: per-stage HTML diagnostic.
        html_report_value = response_dict.get("html_report")
        response_dict_html_report_length = len(html_report_value) if html_report_value is not None else 0

        self.logger.debug(
            "🔍 [RESPONSE-BUILD] HTML report after serialization",
            extra={
                "correlation_id": correlation_id,
                "response_dict_html_report_length": response_dict_html_report_length,
                "html_report_in_dict": "html_report" in response_dict,
                "html_report_lost": original_html_report_length > 0 and response_dict_html_report_length == 0,
            },
        )
        
        # Step 4: Preserve HTML reports if lost during serialization
        response_dict = self._preserve_html_report(
            response_dict,
            original_html_report,
            original_html_report_length,
            correlation_id,
        )
        response_dict = self._preserve_pdf_html_report(
            response_dict,
            original_pdf_html_report,
            original_pdf_html_report_length,
            correlation_id,
        )
        
        # Step 5: Validate response
        self._validate_response(response_dict, correlation_id)
        
        # Step 6: Check response size and simplify if needed
        response_dict = self._manage_response_size(response_dict, correlation_id)
        
        # Step 7: Create JSONResponse
        return self._create_json_response(response_dict, correlation_id)
    
    def _serialize_response(
        self, valuation_response: ValuationResponse, correlation_id: str
    ) -> Dict[str, Any]:
        """
        Serialize valuation response to dictionary.
        
        Args:
            valuation_response: Valuation response object
            correlation_id: Correlation ID for logging
            
        Returns:
            Dictionary representation of response
            
        Raises:
            TypeError, ValueError: If serialization fails
        """
        # BANK-GRADE: Use structured logging instead of print statements
        self.logger.debug(
            "About to serialize ValuationResponse",
            extra={
                "correlation_id": correlation_id,
                "response_type": type(valuation_response).__name__,
            },
        )
        
        # BANK-GRADE: Use FastAPI's jsonable_encoder
        # Ensure all fields are included, even if None
        response_dict = jsonable_encoder(valuation_response, exclude_none=False)

        # Extract HTML value for safe length calculation
        html_report_value = response_dict.get("html_report")

        # DEBUG: per-stage HTML diagnostic.
        self.logger.debug(
            "🔍 [RESPONSE-BUILD] Response serialized successfully",
            extra={
                "correlation_id": correlation_id,
                "response_type": type(valuation_response).__name__,
                "has_html_report": "html_report" in response_dict,
                "html_report_length": len(html_report_value) if html_report_value is not None else 0,
                "html_report_is_none": html_report_value is None,
            },
        )
        
        return response_dict
    
    def _preserve_html_report(
        self,
        response_dict: Dict[str, Any],
        original_html_report: Optional[str],
        original_html_report_length: int,
        correlation_id: str,
    ) -> Dict[str, Any]:
        """
        Preserve HTML report if it was lost during serialization.
        
        Args:
            response_dict: Serialized response dictionary
            original_html_report: Original HTML report from response object
            original_html_report_length: Length of original HTML report
            correlation_id: Correlation ID for logging
            
        Returns:
            Response dictionary with HTML report preserved
        """
        # Preserve html_report
        if original_html_report and original_html_report_length > 0:
            response_dict_has_html_report = "html_report" in response_dict
            html_report_value = response_dict.get("html_report") if response_dict_has_html_report else None
            response_dict_html_report_length = (
                len(html_report_value) if html_report_value is not None else 0
            )
            
            # Check if HTML report was lost
            if not response_dict_has_html_report or response_dict_html_report_length == 0:
                self.logger.warning(
                    "CRITICAL: html_report lost during serialization, explicitly preserving",
                    extra={
                        "correlation_id": correlation_id,
                        "original_length": original_html_report_length,
                        "response_dict_has_html_report": response_dict_has_html_report,
                        "response_dict_html_report_length": response_dict_html_report_length,
                    },
                )
                response_dict["html_report"] = original_html_report
                html_report_preserved = response_dict.get("html_report")
                self.logger.info(
                    "html_report explicitly preserved in response_dict",
                    extra={
                        "correlation_id": correlation_id,
                        "html_report_length": len(html_report_preserved) if html_report_preserved is not None else 0,
                    },
                )
            else:
                self.logger.debug(
                    "html_report preserved during serialization",
                    extra={
                        "correlation_id": correlation_id,
                        "html_report_length": response_dict_html_report_length,
                    },
                )
        
        # DEBUG: per-stage HTML diagnostic.
        final_html_report = response_dict.get("html_report")
        final_html_report_length = len(final_html_report) if final_html_report is not None else 0

        self.logger.debug(
            "🔍 [RESPONSE-BUILD] HTML report after preservation",
            extra={
                "correlation_id": correlation_id,
                "final_html_report_length": final_html_report_length,
                "html_report_preserved": final_html_report_length > 0,
            },
        )

        return response_dict

    def _preserve_pdf_html_report(
        self,
        response_dict: Dict[str, Any],
        original_pdf_html_report: Optional[str],
        original_pdf_html_report_length: int,
        correlation_id: str,
    ) -> Dict[str, Any]:
        """
        Preserve pdf_html_report if lost during serialization.
        Critical for PDF export: Titan uses it when calling ValuationIQ /api/v1/reports/pdf.
        """
        if not original_pdf_html_report or original_pdf_html_report_length < 500:
            return response_dict

        existing = response_dict.get("pdf_html_report")
        existing_len = len(existing) if existing else 0

        if not existing or existing_len == 0:
            self.logger.warning(
                "CRITICAL: pdf_html_report lost during serialization, explicitly preserving",
                extra={
                    "correlation_id": correlation_id,
                    "original_length": original_pdf_html_report_length,
                },
            )
            response_dict["pdf_html_report"] = original_pdf_html_report

        return response_dict

    def _validate_response(
        self, response_dict: Dict[str, Any], correlation_id: str
    ) -> None:
        """
        Validate response dictionary.
        
        Args:
            response_dict: Response dictionary
            correlation_id: Correlation ID for logging
            
        Raises:
            HTTPException: If validation fails
        """
        if response_dict is None:
            from fastapi import HTTPException
            
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "Response serialization returned None",
                    "correlation_id": correlation_id,
                    "message": "Valuation completed but response serialization failed",
                },
            )
        
        if not isinstance(response_dict, dict):
            from fastapi import HTTPException
            
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "Response serialization returned invalid type",
                    "correlation_id": correlation_id,
                    "expected_type": "dict",
                    "actual_type": str(type(response_dict)),
                },
            )
        
        # Check for circular references
        try:
            import json
            
            json.dumps(response_dict, default=str)
        except (TypeError, ValueError) as json_error:
            error_msg = str(json_error)
            if "circular" in error_msg.lower() or "maximum recursion" in error_msg.lower():
                from fastapi import HTTPException
                
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error": "Circular reference detected in response",
                        "correlation_id": correlation_id,
                        "message": "Response contains circular references that prevent serialization",
                    },
                )
            raise
    
    def _manage_response_size(
        self, response_dict: Dict[str, Any], correlation_id: str
    ) -> Dict[str, Any]:
        """
        Manage response size and simplify if too large.
        
        Args:
            response_dict: Response dictionary
            correlation_id: Correlation ID for logging
            
        Returns:
            Response dictionary (simplified if needed)
        """
        # Calculate response size
        import json
        
        try:
            json_str = json.dumps(response_dict)
            response_size_bytes = len(json_str.encode("utf-8"))
            response_size_mb = Decimal(str(response_size_bytes)) / Decimal("1024") / Decimal("1024")
            
            # Warn if large
            if response_size_mb > Decimal("5.0"):
                self.logger.warning(
                    "Large response size detected",
                    extra={
                        "correlation_id": correlation_id,
                        "response_size_mb": float(response_size_mb),
                        "response_size_bytes": response_size_bytes,
                    },
                )
            
            # Simplify if exceeds max size
            if response_size_mb > self.max_response_size_mb:
                self.logger.warning(
                    "Response too large, creating simplified version",
                    extra={
                        "correlation_id": correlation_id,
                        "response_size_mb": float(response_size_mb),
                        "max_size_mb": float(self.max_response_size_mb),
                    },
                )
                return self._create_simplified_response(response_dict, correlation_id)
            
            return response_dict
        except (ValueError, TypeError, AttributeError, KeyError) as size_calc_err:
            self.logger.warning(
                "Failed to calculate response size",
                extra={"correlation_id": correlation_id, "error": str(size_calc_err)},
            )
            return response_dict
    
    def _create_simplified_response(
        self, response_dict: Dict[str, Any], correlation_id: str
    ) -> Dict[str, Any]:
        """
        Create simplified response with only essential fields.
        
        Args:
            response_dict: Full response dictionary
            correlation_id: Correlation ID for logging
            
        Returns:
            Simplified response dictionary
        """
        simplified_response = {
            "valuation_id": response_dict.get("valuation_id"),
            "company_name": response_dict.get("company_name"),
            "equity_value_mid": response_dict.get("equity_value_mid"),
            "equity_value_low": response_dict.get("equity_value_low"),
            "equity_value_high": response_dict.get("equity_value_high"),
            "confidence_score": response_dict.get("confidence_score"),
            "valuation_date": response_dict.get("valuation_date"),
            "methodology": response_dict.get("methodology"),
            "html_report": response_dict.get("html_report"),
            "pdf_html_report": response_dict.get("pdf_html_report"),
            "pdf_bytes": response_dict.get("pdf_bytes"),
            "pdf_url": response_dict.get("pdf_url"),
            "warning": f"Response simplified due to size. Some fields may be omitted.",
            "correlation_id": correlation_id,
        }
        
        self.logger.info(
            "Simplified response created successfully",
            extra={"correlation_id": correlation_id},
        )
        
        return simplified_response
    
    def _create_json_response(
        self, response_dict: Dict[str, Any], correlation_id: str
    ) -> JSONResponse:
        """
        Create JSONResponse from dictionary.
        
        Args:
            response_dict: Response dictionary
            correlation_id: Correlation ID for headers
            
        Returns:
            JSONResponse object
        """
        # DEBUG: per-stage HTML diagnostic.
        final_html_report = response_dict.get("html_report")
        final_html_report_length = len(final_html_report) if final_html_report is not None else 0

        self.logger.debug(
            "🔍 [RESPONSE-BUILD] Final response state before JSONResponse creation",
            extra={
                "correlation_id": correlation_id,
                "final_html_report_length": final_html_report_length,
                "has_html_report": "html_report" in response_dict,
                "has_pdf_bytes": "pdf_bytes" in response_dict and response_dict.get("pdf_bytes") is not None,
                "pdf_bytes_length": len(response_dict.get("pdf_bytes", "")) if response_dict.get("pdf_bytes") else 0,
                "response_dict_keys": list(response_dict.keys())[:20],  # First 20 keys for debugging
            },
        )
        
        return JSONResponse(
            content=response_dict,
            headers={
                "X-Correlation-ID": correlation_id,
                "Content-Type": "application/json",
            },
        )
    
    def _build_fallback_response(
        self,
        valuation_response: ValuationResponse,
        correlation_id: str,
        serialization_error: Exception,
    ) -> JSONResponse:
        """
        Build fallback response when serialization fails.
        
        Args:
            valuation_response: Valuation response object
            correlation_id: Correlation ID
            serialization_error: Original serialization error
            
        Returns:
            JSONResponse with minimal fallback data
        """
        import traceback
        
        error_traceback = traceback.format_exc()
        error_type = type(serialization_error).__name__
        error_message = str(serialization_error)
        
        self.logger.error(
            "CRITICAL: Response serialization failed",
            extra={
                "correlation_id": correlation_id,
                "error": error_message,
                "error_type": error_type,
                "traceback": error_traceback,
            },
            exc_info=True,
        )
        
        # Try to create minimal response
        try:
            import json
            
            fallback_response_dict = {
                "valuation_id": getattr(valuation_response, "valuation_id", "unknown"),
                "company_name": getattr(valuation_response, "company_name", "Unknown"),
                "equity_value_mid": getattr(valuation_response, "equity_value_mid", 0),
                "equity_value_low": getattr(valuation_response, "equity_value_low", None),
                "equity_value_high": getattr(valuation_response, "equity_value_high", None),
                "confidence_score": getattr(valuation_response, "confidence_score", None),
                "methodology": getattr(valuation_response, "methodology", None),
                "error": "Response serialization failed - returning minimal response",
                "correlation_id": correlation_id,
                "html_report": None,
            }
            
            # Validate fallback can be serialized
            json.dumps(fallback_response_dict, default=custom_serializer)
            
            self.logger.warning(
                "Using fallback minimal response due to serialization failure",
                extra={
                    "correlation_id": correlation_id,
                    "fallback_fields": list(fallback_response_dict.keys()),
                },
            )
            
            return JSONResponse(
                status_code=200,  # Return 200 with warning in response
                content=fallback_response_dict,
                headers={"X-Correlation-ID": correlation_id},
            )
        except (CalculationError, ValueError, TypeError, KeyError) as fallback_error:
            self.logger.error(
                "Fallback serialization also failed",
                extra={
                    "correlation_id": correlation_id,
                    "fallback_error": str(fallback_error),
                    "error_type": type(fallback_error).__name__,
                },
            )
            from fastapi import HTTPException
            
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "Response serialization failed",
                    "message": "Valuation completed but response could not be serialized",
                    "correlation_id": correlation_id,
                    "hint": "Check server logs for detailed error information",
                },
            )
