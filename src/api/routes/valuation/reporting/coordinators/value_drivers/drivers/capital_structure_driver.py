"""
Capital Structure Driver Extractor

Extracts capital structure-related value drivers.
"""

from typing import Any, Dict, List


class CapitalStructureDriverExtractor:
    """Extracts capital structure value drivers."""
    
    MAX_DEBT_TO_EQUITY = 1.0
    
    @staticmethod
    def extract(financial_metrics: Dict[str, Any]) -> List[str]:
        """
        Extract capital structure drivers (e.g., debt-to-equity <1.0).
        
        Args:
            financial_metrics: Financial metrics dictionary
            
        Returns:
            List of capital structure driver descriptions
        """
        drivers = []
        
        debt_to_equity = financial_metrics.get("debt_to_equity")
        if debt_to_equity is not None and debt_to_equity < CapitalStructureDriverExtractor.MAX_DEBT_TO_EQUITY:
            drivers.append("Conservative capital structure with manageable debt levels")
        
        return drivers

