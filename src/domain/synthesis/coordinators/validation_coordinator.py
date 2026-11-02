"""
Validation Coordinator

Handles validation logic for calculation results.
Extracted from synthesizer.py to improve modularity.

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive validation
- Detailed logging
"""

from decimal import Decimal
from typing import List, Optional

from src.domain.models import DCFResult, FinancialMetrics, ValidationWarning
from src.utils.decimal_helpers import to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ValidationCoordinator:
    """
    Coordinates validation logic for calculation results.
    
    Responsibilities:
    - Validate DCF results
    - Validate financial metrics
    - Generate validation warnings
    """
    
    def __init__(self):
        """Initialize validation coordinator."""
        self.logger = logger
    
    def validate_calculation_results(
        self, dcf_result: Optional[DCFResult], financial_metrics: FinancialMetrics
    ) -> List[ValidationWarning]:
        """
        Validate calculation results for sanity and flag unreasonable values.
        
        Checks:
        - WACC should be between 5-30% for SMEs
        - CAGR should be reasonable (< 200% for SMEs)
        - Growth rates should be consistent
        
        Args:
            dcf_result: DCF calculation results to validate
            financial_metrics: Calculated financial metrics
            
        Returns:
            List of structured ValidationWarning objects (empty if all checks pass)
        """
        from src.domain.models import (
            ValidationWarningSeverity,
            ValidationWarningType,
        )
        
        warnings = []
        
        # Validate WACC
        if dcf_result and dcf_result.wacc:
            wacc_percent = dcf_result.wacc * 100
            if wacc_percent < 5.0:
                warnings.append(
                    ValidationWarning(
                        type=ValidationWarningType.WACC,
                        severity=ValidationWarningSeverity.HIGH,
                        message=f"WACC of {wacc_percent:.1f}% is unusually low for SMEs",
                        details=f"Expected range: 5-30% for small and medium enterprises. Current: {wacc_percent:.1f}%",
                        recommended_action="Review cost of equity calculation, risk-free rate, and beta assumptions. Verify market risk premium is appropriate for SMEs.",
                    )
                )
                self.logger.warning(
                    "WACC validation failed - too low",
                    wacc=f"{wacc_percent:.1f}%",
                    expected_range="5-30%",
                )
            elif wacc_percent > Decimal("30.0"):
                warnings.append(
                    ValidationWarning(
                        type=ValidationWarningType.WACC,
                        severity=ValidationWarningSeverity.HIGH,
                        message=f"WACC of {wacc_percent:.1f}% is unusually high for SMEs",
                        details=f"Expected range: 5-30% for small and medium enterprises. Current: {wacc_percent:.1f}%",
                        recommended_action="Review risk factors, company-specific risk premium, and size adjustment. WACC above 30% indicates extreme risk perception.",
                    )
                )
                self.logger.warning(
                    "WACC validation failed - too high",
                    wacc=f"{wacc_percent:.1f}%",
                    expected_range="5-30%",
                )
        
        # Validate CAGR
        if financial_metrics.revenue_cagr_3y is not None:
            cagr_percent = financial_metrics.revenue_cagr_3y * 100
            if abs(cagr_percent) > 200:
                warnings.append(
                    ValidationWarning(
                        type=ValidationWarningType.CAGR,
                        severity=ValidationWarningSeverity.CRITICAL,
                        message=f"Revenue CAGR of {cagr_percent:.1f}% is exceptionally high",
                        details=f"Growth rates exceeding ±200% annually are rare for SMEs and often indicate data entry errors or exceptional circumstances. Current CAGR: {cagr_percent:.1f}%",
                        recommended_action="Verify historical revenue data for accuracy. If growth is legitimate, provide supporting documentation explaining the exceptional circumstances (e.g., rapid market expansion, acquisition, product launch).",
                    )
                )
                self.logger.warning(
                    "CAGR validation failed - extreme value",
                    cagr=f"{cagr_percent:.1f}%",
                    threshold="±200%",
                )
        
        # Validate revenue growth consistency
        if (
            financial_metrics.revenue_growth is not None
            and financial_metrics.revenue_cagr_3y is not None
        ):
            revenue_growth_percent = financial_metrics.revenue_growth * 100
            cagr_percent = financial_metrics.revenue_cagr_3y * 100
            
            # If single-year growth differs dramatically from CAGR, flag it
            if abs(revenue_growth_percent - cagr_percent) > 50:
                warnings.append(
                    ValidationWarning(
                        type=ValidationWarningType.GROWTH_CONSISTENCY,
                        severity=ValidationWarningSeverity.MEDIUM,
                        message=f"Single-year growth ({revenue_growth_percent:.1f}%) differs significantly from 3-year CAGR ({cagr_percent:.1f}%)",
                        details=f"Difference of {abs(revenue_growth_percent - cagr_percent):.1f} percentage points suggests volatile or inconsistent performance over time.",
                        recommended_action="Review historical performance trends. Large differences may indicate seasonal business, one-time events, or data inconsistencies. Consider providing context for exceptional years.",
                    )
                )
                self.logger.warning(
                    "Growth rate consistency check failed",
                    revenue_growth=f"{revenue_growth_percent:.1f}%",
                    cagr=f"{cagr_percent:.1f}%",
                    difference=f"{abs(revenue_growth_percent - cagr_percent):.1f}%",
                )
        
        return warnings

