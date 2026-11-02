"""
Adjustments Builder

Builds adjustments summary from response data.
"""

from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.api.schemas import ValuationResponse

from src.services.interfaces.request_response_protocol import ValuationResponseProtocol
from src.services.infrastructure.waterfall_builder import get_owner_concentration_adjustment
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal


class AdjustmentsBuilder:
    """
    Builds adjustments summary from response.
    """
    
    @staticmethod
    def build_adjustments_summary(response: ValuationResponseProtocol) -> Optional[Dict[str, Any]]:
        """
        Build adjustments summary from response.
        
        Args:
            response: ValuationResponse containing adjustment data
            
        Returns:
            Dictionary with adjustments summary, or None if no adjustments
        """
        adjustments = []
        
        if response.multiples_valuation:
            owner_conc_adjustment = get_owner_concentration_adjustment(response)
            if owner_conc_adjustment is not None:
                adjustment_percentage = None
                if response.multiples_valuation.owner_concentration and isinstance(response.multiples_valuation.owner_concentration, dict):
                    adjustment_percentage = response.multiples_valuation.owner_concentration.get('adjustment_percentage', None)
                    if adjustment_percentage is None:
                        adjustment_factor = response.multiples_valuation.owner_concentration.get('adjustment_factor', None)
                        if adjustment_factor is not None:
                            adjustment_percentage = adjustment_factor * 100
                
                adjustments.append({
                    'name': 'Owner Concentration',
                    'percentage': adjustment_percentage,
                    'amount': owner_conc_adjustment,
                    'explanation': 'Owner concentration risk adjustment'
                })
            
            if response.multiples_valuation.size_discount:
                adjustments.append({
                    'name': 'Size Discount',
                    'percentage': response.multiples_valuation.size_discount_percentage if hasattr(response.multiples_valuation, 'size_discount_percentage') else None,
                    'amount': response.multiples_valuation.size_discount,
                    'explanation': 'Company size discount'
                })
            
            if response.multiples_valuation.liquidity_discount:
                adjustments.append({
                    'name': 'Liquidity Discount',
                    'percentage': response.multiples_valuation.liquidity_discount_percentage if hasattr(response.multiples_valuation, 'liquidity_discount_percentage') else None,
                    'amount': response.multiples_valuation.liquidity_discount,
                    'explanation': 'Market liquidity discount'
                })
        
        if response.owner_dependency_adjustment:
            adjustments.append({
                'name': 'Ownership Adjustment',
                'percentage': None,
                'amount': response.owner_dependency_adjustment,
                'explanation': 'Owner dependency adjustment'
            })
        
        if not adjustments:
            return None
        
        return {
            'adjustments': adjustments,
            'total_adjustment': sum(
                adj.get('amount', 0) 
                for adj in adjustments 
                if isinstance(adj, dict) and 'amount' in adj and adj.get('amount') is not None
            ),
            'total_adjustment_percentage': None
        }

