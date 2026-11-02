"""
Sole Trader Detector Wrapper

Wraps sole trader detection logic for methodology statement generation.
"""

from typing import Any, Optional

from src.utils.core.data_extraction_helpers import extract_owner_employee_counts_from_request
from src.utils.sole_trader_detector import SoleTraderDetector


class SoleTraderDetectorWrapper:
    """Wraps sole trader detection for methodology statements."""
    
    @staticmethod
    def detect(request: Optional[Any]) -> bool:
        """
        Detect if business is a sole trader.
        
        Args:
            request: Valuation request
            
        Returns:
            True if sole trader, False otherwise
        """
        if not request:
            return False
        
        num_owners, num_employees = extract_owner_employee_counts_from_request(request)
        
        return SoleTraderDetector.detect(
            business_structure=getattr(request, "business_type", None),
            business_type=getattr(request, "business_type", None),
            number_of_owners=num_owners,
            number_of_employees=num_employees,
            is_sole_trader=getattr(request, "is_sole_trader", None),
            business_context=getattr(request, "business_context", None),
        )

