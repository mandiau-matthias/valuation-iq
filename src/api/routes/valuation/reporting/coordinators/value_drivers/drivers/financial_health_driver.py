"""
Financial Health Driver Extractor

Extracts financial health-related value drivers.
"""

from typing import Any, Dict, List


class FinancialHealthDriverExtractor:
    """Extracts financial health value drivers."""
    
    MIN_HEALTH_SCORE = 75
    
    @staticmethod
    def extract(financial_metrics: Dict[str, Any]) -> List[str]:
        """
        Extract financial health drivers (e.g., health score >=75).
        
        Args:
            financial_metrics: Financial metrics dictionary
            
        Returns:
            List of financial health driver descriptions
        """
        drivers = []
        
        financial_health_score = financial_metrics.get("financial_health_score")
        if financial_health_score and financial_health_score >= FinancialHealthDriverExtractor.MIN_HEALTH_SCORE:
            drivers.append(
                f"Excellent financial health and low bankruptcy risk (score: {financial_health_score:.0f}/100)"
            )
        
        return drivers

