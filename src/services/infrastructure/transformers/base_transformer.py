"""
Base transformer class for all section transformers.

Provides common utilities and interface for transforming valuation data.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.api.schemas import ValuationResponse, ValuationRequest

from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)
from src.services.infrastructure.transformer_base import get_ebitda_value, get_ebitda_margin
from src.services.infrastructure.exceptions import DataTransformationError, MissingDataError
from src.utils.logging import get_logger
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal


class BaseTransformer(ABC):
    """Base class for all section transformers."""
    
    def __init__(self):
        """Initialize transformer with logger."""
        self.logger = get_logger(self.__class__.__name__)
    
    def _validate_inputs(
        self,
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol
    ) -> None:
        """
        Validate input parameters for transformation.
        
        Args:
            response: ValuationResponse to validate
            request: ValuationRequest to validate
            
        Raises:
            MissingDataError: If required fields are missing
            DataTransformationError: If data structure is invalid
        """
        if response is None:
            raise MissingDataError(
                "ValuationResponse is required but was None",
                missing_fields=['response']
            )
        
        if request is None:
            raise MissingDataError(
                "ValuationRequest is required but was None",
                missing_fields=['request']
            )
        
        # Validate critical response fields
        if not hasattr(response, 'company_name') or not response.company_name:
            raise MissingDataError(
                "ValuationResponse missing required field: company_name",
                missing_fields=['company_name']
            )
        
        if not hasattr(response, 'valuation_id'):
            self.logger.warning(
                "ValuationResponse missing valuation_id",
                extra={'company_name': getattr(response, 'company_name', 'Unknown')}
            )
    
    @abstractmethod
    def transform(
        self,
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol
    ) -> Dict[str, Any]:
        """
        Transform data for a specific report section.
        
        Args:
            response: ValuationResponse containing calculation results
            request: Original ValuationRequest for context
            
        Returns:
            Dictionary with section data for template rendering
            
        Raises:
            MissingDataError: If required data is missing
            DataTransformationError: If transformation fails
        """
        pass
    
    def get_ebitda_value(
        self,
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol
    ) -> Optional[Decimal]:
        """
        Helper to get EBITDA value safely.
        
        Args:
            response: ValuationResponse containing financial data
            request: ValuationRequest with current year data
            
        Returns:
            EBITDA value as float, or None if not available
        """
        try:
            return get_ebitda_value(response, request)
        except (AttributeError, TypeError, ValueError) as e:
            self.logger.debug(
                "Could not extract EBITDA value",
                extra={'error_type': type(e).__name__, 'error': str(e)},
                exc_info=False
            )
            return None
    
    def get_ebitda_margin(
        self,
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol
    ) -> Optional[Decimal]:
        """
        Helper to get EBITDA margin safely.
        
        Args:
            response: ValuationResponse containing financial data
            request: ValuationRequest with current year data
            
        Returns:
            EBITDA margin as to_decimal(percentage), or None if not available
        """
        try:
            return get_ebitda_margin(response, request)
        except (AttributeError, TypeError, ValueError, ZeroDivisionError) as e:
            self.logger.debug(
                "Could not extract EBITDA margin",
                extra={'error_type': type(e).__name__, 'error': str(e)},
                exc_info=False
            )
            return None
    
    def safe_divide(
        self,
        numerator: Decimal,
        denominator: Decimal,
        default: Optional[Decimal] = None
    ) -> Optional[Decimal]:
        """
        Safely divide two numbers, handling zero denominator.
        
        Delegates to unified utility from src.utils.core.
        
        Args:
            numerator: Numerator value
            denominator: Denominator value
            default: Value to return if division fails (default: None)
            
        Returns:
            Division result or default value
        """
        from src.utils.core import safe_divide as core_safe_divide
        return core_safe_divide(numerator, denominator, default)

