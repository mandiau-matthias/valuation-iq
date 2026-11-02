"""
Confidence Calculation Coordinator

Handles confidence score calculation logic.
Extracted from synthesizer.py to improve modularity.

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive confidence scoring
- Detailed logging
"""

from decimal import Decimal
from typing import Optional, Tuple

from src.domain.models import ConfidenceLevel, DCFResult, FinancialMetrics, MultiplesResult
from src.utils.decimal_helpers import bank_round, from_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ConfidenceCalculationCoordinator:
    """
    Coordinates confidence score calculation logic.
    
    Responsibilities:
    - Calculate weighted average confidence scores
    - Adjust based on methodology agreement
    - Determine confidence level
    """
    
    def __init__(self):
        """Initialize confidence calculation coordinator."""
        self.logger = logger
    
    def calculate_overall_confidence(
        self,
        dcf_result: Optional[DCFResult],
        multiples_result: Optional[MultiplesResult],
        dcf_weight: Decimal,
        multiples_weight: Decimal,
        financial_metrics: FinancialMetrics,
    ) -> Tuple[ConfidenceLevel, int]:
        """
        Calculate overall confidence in synthesized valuation.
        
        Args:
            dcf_result: DCF calculation results
            multiples_result: Multiples calculation results
            dcf_weight: Weight for DCF methodology
            multiples_weight: Weight for multiples methodology
            financial_metrics: Calculated financial metrics
            
        Returns:
            Tuple of (confidence_level, confidence_score)
        """
        # Weighted average of methodology confidence scores
        scores = []
        weights = []
        
        if dcf_result:
            scores.append(dcf_result.confidence_score)
            weights.append(to_decimal(dcf_weight))
        
        if multiples_result:
            confidence_score = getattr(multiples_result, "confidence_score", None)
            if confidence_score is not None:
                scores.append(confidence_score)
                weights.append(to_decimal(multiples_weight))
            else:
                self.logger.warning(
                    "multiples_result.confidence_score missing, skipping from confidence calculation"
                )
        
        if not scores:
            return ConfidenceLevel.LOW, 0
        
        total_weight = sum(weights)
        if total_weight <= 0:
            return ConfidenceLevel.LOW, 0
        confidence_score_decimal = (
            sum(to_decimal(s) * w for s, w in zip(scores, weights)) / total_weight
        )
        confidence_score = int(from_decimal(bank_round(confidence_score_decimal, 0)))
        
        # Adjust based on agreement between methodologies
        if dcf_result and multiples_result:
            # Calculate variance between methodologies
            dcf_value_decimal = to_decimal(dcf_result.equity_value)
            multiples_value = getattr(multiples_result, "adjusted_equity_value", None)
            if multiples_value is None:
                # Fallback: skip variance calculation if attribute missing
                self.logger.warning(
                    "multiples_result.adjusted_equity_value missing, skipping variance calculation"
                )
                variance = Decimal("0.0")
            else:
                multiples_value_decimal = to_decimal(multiples_value)
                variance = abs(dcf_value_decimal - multiples_value_decimal) / max(
                    dcf_value_decimal, multiples_value_decimal
                )
            
            if variance < Decimal("0.20"):  # Within 20%
                confidence_score += 5  # Bonus for agreement
            elif variance > Decimal("0.50"):  # > 50% difference
                confidence_score -= 10  # Penalty for disagreement
        
        # Cap score at 100
        confidence_score = min(confidence_score, 100)
        
        # Determine confidence level
        if confidence_score >= 75:
            confidence = ConfidenceLevel.HIGH
        elif confidence_score >= 50:
            confidence = ConfidenceLevel.MEDIUM
        else:
            confidence = ConfidenceLevel.LOW
        
        return confidence, confidence_score

