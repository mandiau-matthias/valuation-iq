"""
Range Calculation Coordinator

Handles valuation range calculation logic.
Extracted from synthesizer.py to improve modularity.

BANK-GRADE QUALITY:
- Full type hints
- Big 4 methodology compliance
- Detailed logging
"""

from decimal import Decimal
from typing import Optional, Tuple

from src.domain.models import ConfidenceLevel, DCFResult, FinancialData, MultiplesResult
from src.utils.decimal_helpers import to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class RangeCalculationCoordinator:
    """
    Coordinates valuation range calculation logic.
    
    Responsibilities:
    - Calculate weighted average (mid-point)
    - Determine range width based on confidence and methodology agreement
    - Calculate low/mid/high equity values
    """
    
    def __init__(self, financial_data: FinancialData):
        """
        Initialize range calculation coordinator.
        
        Args:
            financial_data: Company financial data
        """
        self.logger = logger
        self.financial_data = financial_data
    
    def calculate_valuation_range(
        self,
        dcf_result: Optional[DCFResult],
        multiples_result: Optional[MultiplesResult],
        dcf_weight: Decimal,
        multiples_weight: Decimal,
    ) -> Tuple[Decimal, Decimal, Decimal]:
        """
        Calculate valuation range using Big 4 methodology.
        
        Key Principle: Range width depends on confidence and methodology agreement,
        not on raw min/max values. Follows Deloitte/PwC/KPMG/EY standards.
        
        Typical ranges:
        - High confidence/agreement: ±10-12% (20-24% spread)
        - Medium confidence/agreement: ±15-18% (30-36% spread)
        - Low confidence/disagreement: ±20-22% (40-44% spread)
        
        Maximum spread: 2x (never 4-5x like old logic)
        
        Args:
            dcf_result: DCF calculation results
            multiples_result: Multiples calculation results
            dcf_weight: Weight for DCF methodology
            multiples_weight: Weight for multiples methodology
            
        Returns:
            Tuple of (low, mid, high) equity values
        """
        # Collect all valuations
        valuations = []
        
        if dcf_result:
            valuations.append((dcf_result.equity_value, dcf_weight))
        
        if multiples_result:
            adjusted_value = getattr(multiples_result, "adjusted_equity_value", None)
            if adjusted_value is not None:
                valuations.append((adjusted_value, multiples_weight))
            else:
                self.logger.warning(
                    "multiples_result.adjusted_equity_value missing, skipping multiples valuation"
                )
        
        if not valuations:
            # Fallback: use simple revenue multiple with ±15% range
            fallback_value_decimal = to_decimal(self.financial_data.latest_revenue) * Decimal("2.0")
            return (
                fallback_value_decimal * Decimal("0.85"),
                fallback_value_decimal,
                fallback_value_decimal * Decimal("1.15"),
            )
        
        # 1. Calculate weighted average (mid-point) - THIS IS THE TRUE VALUATION
        # Convert valuations to Decimal
        valuations_decimal = [(to_decimal(v), to_decimal(w)) for v, w in valuations]
        total_weight = sum(w for v, w in valuations_decimal)
        equity_value_mid = sum(v * w for v, w in valuations_decimal) / total_weight
        
        # 2. Determine range width based on confidence and methodology agreement
        range_pct = self._determine_range_percentage(dcf_result, multiples_result)
        
        # 3. Calculate range around weighted midpoint
        equity_value_low = equity_value_mid * (Decimal("1") - range_pct)
        equity_value_high = equity_value_mid * (Decimal("1") + range_pct)
        
        return equity_value_low, equity_value_mid, equity_value_high
    
    def _determine_range_percentage(
        self,
        dcf_result: Optional[DCFResult],
        multiples_result: Optional[MultiplesResult],
    ) -> Decimal:
        """
        Determine range percentage based on confidence and methodology agreement.
        
        Args:
            dcf_result: DCF calculation results
            multiples_result: Multiples calculation results
            
        Returns:
            Range percentage (e.g., Decimal("0.12") for ±12%)
        """
        if dcf_result and multiples_result:
            # Both methodologies available - assess agreement
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
                max_val = max(dcf_value_decimal, multiples_value_decimal)
                if max_val > 0:
                    variance = abs(dcf_value_decimal - multiples_value_decimal) / max_val
                else:
                    variance = Decimal("0.0")
            
            # Range based on methodology agreement (Big 4 standard)
            if variance < Decimal("0.15"):  # Strong agreement (<15% difference)
                return Decimal("0.12")  # ±12% → 1.27x spread
            elif variance < Decimal("0.30"):  # Moderate agreement (<30% difference)
                return Decimal("0.18")  # ±18% → 1.44x spread
            else:  # Significant divergence (>30% difference)
                return Decimal("0.22")  # ±22% → 1.56x spread
        else:
            # Single methodology - use its confidence level
            if dcf_result:
                confidence = dcf_result.confidence
            elif multiples_result:
                confidence = getattr(multiples_result, "confidence", None)
                if confidence is None:
                    # Fallback: use MEDIUM confidence if attribute missing
                    confidence = ConfidenceLevel.MEDIUM
                    self.logger.warning("multiples_result.confidence missing, using MEDIUM confidence")
            else:
                confidence = ConfidenceLevel.MEDIUM
            
            if confidence == ConfidenceLevel.HIGH:
                return Decimal("0.12")  # ±12%
            elif confidence == ConfidenceLevel.MEDIUM:
                return Decimal("0.18")  # ±18%
            else:
                return Decimal("0.22")  # ±22%

