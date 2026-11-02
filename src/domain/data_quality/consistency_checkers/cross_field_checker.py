"""
Cross-Field Relationship Checker

Validates cross-field relationships (e.g., EBITDA should not exceed revenue).
"""

from src.utils.decimal_helpers import to_decimal

from ...data_quality_assessor import QualityWarning


class CrossFieldRelationshipChecker:
    """Checks cross-field relationships for consistency."""

    def check(self, request: object, warnings: list[QualityWarning]) -> int:
        """
        Check cross-field relationships (10 points).

        Args:
            request: Valuation request
            warnings: list to append warnings to

        Returns:
            Points deducted (0-10)
        """
        if not hasattr(request, "current_year_data") or not request.current_year_data:
            return 0

        revenue = getattr(request.current_year_data, "revenue", None)
        ebitda = getattr(request.current_year_data, "ebitda", None)

        if revenue is None or ebitda is None:
            return 0

        try:
            revenue_decimal = to_decimal(str(revenue))
            ebitda_decimal = to_decimal(str(ebitda))

            if revenue_decimal <= 0:
                return 0

            # EBITDA should not exceed revenue (if both positive)
            if ebitda_decimal > revenue_decimal:
                warnings.append(
                    QualityWarning(
                        severity=QualityWarning.SEVERITY_CRITICAL,
                        code="INCONSISTENT_EBITDA_REVENUE",
                        message="EBITDA exceeds revenue (inconsistent relationship)",
                        field="ebitda",
                        recommendation="Review financial data for consistency",
                        impact_score=10,
                    )
                )
                return 10
        except (ValueError, TypeError):
            return 5

        return 0
