"""
Ratio Stability Checker

Validates ratio stability (e.g., EBITDA margin volatility vs historical average).
"""

from decimal import Decimal

from src.utils.decimal_helpers import from_decimal, to_decimal

from ...data_quality_assessor import QualityWarning


class RatioStabilityChecker:
    """Checks ratio stability for financial metrics."""

    def check(
        self, request: object, historical_years: list[object], warnings: list[QualityWarning]
    ) -> int:
        """
        Check ratio stability (5 points).

        Args:
            request: Valuation request
            historical_years: Historical years data
            warnings: list to append warnings to

        Returns:
            Points deducted (0-5)
        """
        if not hasattr(request, "current_year_data") or not request.current_year_data:
            return 0

        revenue = getattr(request.current_year_data, "revenue", None)
        ebitda = getattr(request.current_year_data, "ebitda", None)

        if revenue is None or ebitda is None or not historical_years:
            return 0

        try:
            current_margin = self._calculate_margin(ebitda, revenue)
            historical_margins = self._extract_historical_margins(historical_years)

            if not historical_margins:
                return 0

            # Check margin stability (flag if >20% change vs historical average)
            avg_historical_margin = sum(historical_margins) / len(historical_margins)
            if avg_historical_margin != 0:
                margin_change = abs(current_margin - avg_historical_margin) / abs(
                    avg_historical_margin
                )
                if margin_change > to_decimal("0.20"):  # >20% change
                    warnings.append(
                        QualityWarning(
                            severity=QualityWarning.SEVERITY_LOW,
                            code="MARGIN_VOLATILITY",
                            message=f"EBITDA margin changed by {from_decimal(margin_change * to_decimal('100'), precision=1):.1f}% vs historical average",
                            field="ebitda_margin",
                            recommendation="Verify margin change is accurate",
                            impact_score=2,
                        )
                    )
                    return 2

            # Check historical margin spread (flag if range > 15pp)
            if len(historical_margins) >= 2:
                margin_spread = max(historical_margins) - min(historical_margins)
                if margin_spread > to_decimal("0.15"):
                    warnings.append(
                        QualityWarning(
                            severity=QualityWarning.SEVERITY_LOW,
                            code="MARGIN_VOLATILITY",
                            message=f"Historical EBITDA margin spread of {from_decimal(margin_spread * to_decimal('100'), precision=1):.1f}pp indicates volatility",
                            field="ebitda_margin",
                            recommendation="Verify historical margin data is accurate",
                            impact_score=2,
                        )
                    )
                    return 2
        except (ValueError, TypeError, ZeroDivisionError):
            pass

        return 0

    def _calculate_margin(self, ebitda: object, revenue: object) -> Decimal:
        """Calculate EBITDA margin."""
        revenue_decimal = to_decimal(str(revenue))
        if revenue_decimal <= 0:
            raise ValueError("Revenue must be positive to calculate margin")
        return to_decimal(str(ebitda)) / revenue_decimal

    def _extract_historical_margins(self, historical_years: list[object]) -> list[Decimal]:
        """Extract EBITDA margins from historical years."""
        margins = []
        for year in historical_years:
            revenue = getattr(year, "revenue", None)
            ebitda = getattr(year, "ebitda", None)
            if revenue is None or ebitda is None:
                continue
            try:
                revenue_decimal = to_decimal(str(revenue))
                if revenue_decimal > 0:
                    margins.append(to_decimal(str(ebitda)) / revenue_decimal)
            except (ValueError, TypeError, ZeroDivisionError):
                continue
        return margins
