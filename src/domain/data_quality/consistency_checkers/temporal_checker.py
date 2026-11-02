"""
Temporal Consistency Checker

Validates temporal consistency (e.g., unusual year-over-year declines).
"""

from decimal import Decimal

from src.utils.decimal_helpers import from_decimal, to_decimal
from ...data_quality_assessor import QualityWarning


class TemporalConsistencyChecker:
    """Checks temporal consistency for historical data."""
    
    def check(
        self, request: object, warnings: list[QualityWarning]
    ) -> int:
        """
        Check temporal consistency (5 points).
        
        Args:
            request: Valuation request
            warnings: list to append warnings to
            
        Returns:
            Points deducted (0-5)
        """
        historical_years = getattr(request, "historical_years_data", None) or getattr(
            request, "historical_years", []
        )
        
        if not historical_years:
            return 0
        
        try:
            revenues = self._extract_revenues(historical_years)
            
            if hasattr(request, "current_year_data") and request.current_year_data:
                current_revenue = getattr(request.current_year_data, "revenue", None)
                if current_revenue and isinstance(current_revenue, (int, float, Decimal)):
                    revenues.append(to_decimal(str(current_revenue)))
            
            if len(revenues) < 2:
                return 0
            
            # Check for >50% year-over-year decline (unusual without explanation)
            for i in range(1, len(revenues)):
                if revenues[i - 1] > 0:
                    decline = (revenues[i - 1] - revenues[i]) / revenues[i - 1]
                    if decline > to_decimal("0.50"):  # >50% decline
                        warnings.append(
                            QualityWarning(
                                severity=QualityWarning.SEVERITY_MEDIUM,
                                code="UNUSUAL_REVENUE_DECLINE",
                                message=f"Revenue declined by {from_decimal(decline * to_decimal('100'), precision=1):.1f}% year-over-year",
                                field="historical_years",
                                recommendation="Verify revenue decline is accurate",
                                impact_score=3,
                            )
                        )
                        return 3
        except (ValueError, TypeError, AttributeError):
            return 2
        
        return 0
    
    def _extract_revenues(self, historical_years: list[object]) -> list[Decimal]:
        """Extract revenue values from historical years."""
        revenues = []
        for year in historical_years:
            if hasattr(year, "revenue") and year.revenue:
                revenues.append(to_decimal(str(year.revenue)))
        return revenues
