"""
Valuation Orchestrator Protocol

Protocol definition for valuation orchestrator functionality.
Services can use this protocol instead of importing from API layer.
"""

from typing import Protocol, Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.api.schemas import ValuationRequest, ValuationResponse

from .request_response_protocol import ValuationRequestProtocol, ValuationResponseProtocol


class ValuationOrchestratorProtocol(Protocol):
    """Protocol for valuation orchestrator."""
    
    async def calculate_valuation(
        self,
        request: ValuationRequestProtocol,
        mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Calculate valuation.
        
        Args:
            request: Valuation request
            mode: Optional mode (quick/comprehensive)
            
        Returns:
            Valuation results dictionary
        """
        ...
    
    async def calculate_quick_valuation(
        self,
        request: "QuickValuationRequestProtocol",
    ) -> Dict[str, Any]:
        """
        Calculate quick valuation.
        
        Args:
            request: Quick valuation request
            
        Returns:
            Quick valuation results dictionary
        """
        ...

