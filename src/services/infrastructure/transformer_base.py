"""
Base Transformer Module

Shared helper functions used across all transformer modules.
"""

from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.api.schemas import ValuationResponse, ValuationRequest

from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)
from decimal import Decimal
from src.utils.logging import get_logger
from src.utils.decimal_helpers import to_decimal, from_decimal

logger = get_logger(__name__)


def get_ebitda_value(response: ValuationResponseProtocol, request: ValuationRequestProtocol) -> Optional[Decimal]:
    """
    Get EBITDA value from request or response.
    
    Args:
        response: ValuationResponse containing current_year_data
        request: ValuationRequest containing current_year_data
        
    Returns:
        EBITDA value as float, or None if not available
    """
    # Try request first (preferred source)
    if request.current_year_data and hasattr(request.current_year_data, 'ebitda'):
        ebitda = request.current_year_data.ebitda
        if ebitda is not None:
            return from_decimal(to_decimal(ebitda))
    
    # Fallback to response
    if response.current_year_data and hasattr(response.current_year_data, 'ebitda'):
        ebitda = response.current_year_data.ebitda
        if ebitda is not None:
            return from_decimal(to_decimal(ebitda))
    
    return None


def get_ebitda_margin(response: ValuationResponseProtocol, request: ValuationRequestProtocol) -> Optional[Decimal]:
    """
    Calculate EBITDA margin from request or response data.
    
    Args:
        response: ValuationResponse containing current_year_data
        request: ValuationRequest containing current_year_data
        
    Returns:
        EBITDA margin as percentage (e.g., 17.1 for 17.1%), or None if not available
    """
    # Try request first (preferred source)
    if request.current_year_data:
        ebitda = getattr(request.current_year_data, 'ebitda', None)
        revenue = getattr(request.current_year_data, 'revenue', None)
        if ebitda is not None and revenue is not None:
            ebitda_decimal = to_decimal(ebitda)
            revenue_decimal = to_decimal(revenue)
            if revenue_decimal > Decimal('0'):
                margin_decimal = (ebitda_decimal / revenue_decimal) * Decimal('100')
                return from_decimal(margin_decimal)
    
    # Fallback to response
    if response.current_year_data:
        ebitda = getattr(response.current_year_data, 'ebitda', None)
        revenue = getattr(response.current_year_data, 'revenue', None)
        if ebitda is not None and revenue is not None:
            ebitda_decimal = to_decimal(ebitda)
            revenue_decimal = to_decimal(revenue)
            if revenue_decimal > Decimal('0'):
                margin_decimal = (ebitda_decimal / revenue_decimal) * Decimal('100')
                return from_decimal(margin_decimal)
    
    return None

