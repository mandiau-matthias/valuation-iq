"""
Spread Calculator

Calculates valuation spread based on confidence score.
"""

from decimal import Decimal


class SpreadCalculator:
    """Calculates spread percentage based on confidence score."""
    
    HIGH_CONFIDENCE_THRESHOLD = 80
    MEDIUM_CONFIDENCE_THRESHOLD = 60
    
    HIGH_CONFIDENCE_SPREAD = Decimal("0.15")  # ±15%
    MEDIUM_CONFIDENCE_SPREAD = Decimal("0.20")  # ±20%
    LOW_CONFIDENCE_SPREAD = Decimal("0.30")  # ±30%
    
    @staticmethod
    def calculate(confidence_score: int) -> Decimal:
        """
        Calculate spread percentage based on confidence score.
        
        Args:
            confidence_score: Confidence score (0-100)
            
        Returns:
            Spread percentage (e.g., 0.15 for ±15%)
        """
        if confidence_score >= SpreadCalculator.HIGH_CONFIDENCE_THRESHOLD:
            return SpreadCalculator.HIGH_CONFIDENCE_SPREAD
        elif confidence_score >= SpreadCalculator.MEDIUM_CONFIDENCE_THRESHOLD:
            return SpreadCalculator.MEDIUM_CONFIDENCE_SPREAD
        else:
            return SpreadCalculator.LOW_CONFIDENCE_SPREAD
    
    @staticmethod
    def get_confidence_level(confidence_score: int) -> str:
        """
        Get confidence level string from score.
        
        Args:
            confidence_score: Confidence score (0-100)
            
        Returns:
            Confidence level ("HIGH", "MEDIUM", or "LOW")
        """
        if confidence_score >= SpreadCalculator.HIGH_CONFIDENCE_THRESHOLD:
            return "HIGH"
        elif confidence_score >= SpreadCalculator.MEDIUM_CONFIDENCE_THRESHOLD:
            return "MEDIUM"
        else:
            return "LOW"

