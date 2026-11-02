"""
Methodology Determiner

WHAT: Determines valuation methodology from response weights
WHY: Separates methodology determination logic (SRP compliance)
HOW: Analyzes DCF/multiples weights to determine methodology

SINGLE RESPONSIBILITY: Methodology determination ONLY
"""

from typing import Optional, TYPE_CHECKING
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.api.schemas import ValuationResponse

from src.services.interfaces.request_response_protocol import ValuationResponseProtocol

logger = get_logger(__name__)


class MethodologyDeterminer:
    """
    Determines valuation methodology from response.
    
    SINGLE RESPONSIBILITY: Methodology determination ONLY
    
    NO extraction, NO validation, NO transformation - pure determination only.
    """
    
    def __init__(self):
        """Initialize methodology determiner."""
        self.logger = logger
    
    def determine_methodology(self, response: ValuationResponseProtocol) -> str:
        """
        Determine valuation methodology from response.
        
        WHAT: Analyzes response to determine DCF vs Multiples vs Hybrid
        WHY: Templates need to know which methodology was used
        HOW: Checks response.methodology or calculates from weights
        
        Args:
            response: ValuationResponse
        
        Returns:
            Methodology string: "Discounted Cash Flow (DCF)", "Market Multiples", or "Hybrid Valuation"
        
        Business Rules:
        - If DCF weight > 0.5: Use DCF
        - If Multiples weight > 0.5: Use Market Multiples
        - Otherwise: Hybrid Valuation
        """
        # Check if methodology already set
        if hasattr(response, 'methodology') and response.methodology:
            return response.methodology
        
        # Calculate from weights
        methodology = self.get_methodology_from_weights(response)
        
        self.logger.debug(
            "Methodology determined",
            extra={
                'methodology': methodology,
                'source': 'calculated_from_weights'
            }
        )
        
        return methodology
    
    def get_methodology_from_weights(self, response: ValuationResponseProtocol) -> str:
        """
        Calculate methodology from DCF/multiples weights.
        
        Args:
            response: ValuationResponse
        
        Returns:
            Methodology string based on weights
        """
        dcf_weight = response.dcf_weight if hasattr(response, 'dcf_weight') else 0.0
        multiples_weight = response.multiples_weight if hasattr(response, 'multiples_weight') else 1.0
        
        if dcf_weight > 0.5:
            return "Discounted Cash Flow (DCF)"
        elif multiples_weight > 0.5:
            return "Market Multiples"
        else:
            return "Hybrid Valuation"
