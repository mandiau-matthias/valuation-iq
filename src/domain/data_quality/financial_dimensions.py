"""
Financial data quality dimensions.

Completeness and validity are kept here so DataQualityAssessor can stay focused
on orchestration, caching, and result assembly.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping

from src.utils.decimal_helpers import from_decimal, to_decimal

from ..data_quality_assessor import QualityWarning


@dataclass(frozen=True)
class ValidityBounds:
    """Numeric bounds used by the validity dimension."""

    revenue_min: Decimal
    revenue_max: Decimal
    margin_min: Decimal
    margin_max: Decimal


def assess_completeness_dimension(request: object, warnings: list[QualityWarning]) -> int:
    """Assess completeness dimension (30 points)."""
    current_year_data = _current_year_data(request)
    score = 0

    score += _score_revenue_completeness(current_year_data, warnings)
    score += _score_ebitda_completeness(current_year_data, warnings)
    score += _score_historical_completeness(request, warnings)
    score += _score_balance_sheet_completeness(current_year_data, warnings)

    return score


def assess_validity_dimension(
    request: object, warnings: list[QualityWarning], bounds: ValidityBounds
) -> int:
    """Assess validity dimension (20 points)."""
    current_year_data = _current_year_data(request)

    type_issues = _append_revenue_validity_warnings(
        current_year_data=current_year_data,
        warnings=warnings,
        bounds=bounds,
    )
    range_issues = _append_range_validity_warnings(
        current_year_data=current_year_data,
        warnings=warnings,
        bounds=bounds,
    )

    score = 20
    score -= _type_issue_deduction(type_issues)
    score -= _range_issue_deduction(range_issues)

    if type_issues > 0 or range_issues > 0:
        score -= min(5, (type_issues + range_issues) * 2)

    return max(0, score)


def assess_accuracy_dimension(
    request: object,
    warnings: list[QualityWarning],
    industry_margin_benchmarks: Mapping[str, Mapping[str, object]],
    growth_rate_min: Decimal,
    growth_rate_max: Decimal,
) -> int:
    """Assess accuracy dimension (20 points)."""
    score = 20
    score -= _append_margin_benchmark_warning(
        request=request,
        warnings=warnings,
        industry_margin_benchmarks=industry_margin_benchmarks,
    )
    score -= _append_growth_rate_warning(
        request=request,
        warnings=warnings,
        growth_rate_min=growth_rate_min,
        growth_rate_max=growth_rate_max,
    )
    return max(0, score)


def _current_year_data(request: object) -> object | None:
    current_year_data = getattr(request, "current_year_data", None)
    return current_year_data if current_year_data else None


def _score_revenue_completeness(
    current_year_data: object | None, warnings: list[QualityWarning]
) -> int:
    if current_year_data is None:
        return 0

    revenue = getattr(current_year_data, "revenue", None)
    if _positive_decimal_or_none(revenue) is not None:
        return 8

    warnings.append(
        QualityWarning(
            severity=QualityWarning.SEVERITY_CRITICAL,
            code="MISSING_REVENUE",
            message="Revenue data is missing or invalid",
            field="revenue",
            recommendation="Provide current year revenue",
            impact_score=8,
        )
    )
    return 0


def _score_ebitda_completeness(
    current_year_data: object | None, warnings: list[QualityWarning]
) -> int:
    if current_year_data is None:
        return 0

    if hasattr(current_year_data, "ebitda") and getattr(current_year_data, "ebitda") is not None:
        return 8

    warnings.append(
        QualityWarning(
            severity=QualityWarning.SEVERITY_HIGH,
            code="MISSING_EBITDA",
            message="EBITDA data is missing",
            field="ebitda",
            recommendation="Provide EBITDA or operating income",
            impact_score=8,
        )
    )
    return 0


def _score_historical_completeness(request: object, warnings: list[QualityWarning]) -> int:
    historical_count = _historical_year_count(request)

    if historical_count >= 3:
        return 10
    if historical_count == 2:
        warnings.append(
            QualityWarning(
                severity=QualityWarning.SEVERITY_MEDIUM,
                code="INSUFFICIENT_HISTORICAL",
                message="Only 2 years of historical data (3+ recommended for DCF)",
                field="historical_years",
                recommendation="Add 1 more year of historical data to improve quality score by 3 points",
                impact_score=3,
            )
        )
        return 7
    if historical_count == 1:
        warnings.append(
            QualityWarning(
                severity=QualityWarning.SEVERITY_HIGH,
                code="INSUFFICIENT_HISTORICAL",
                message="Only 1 year of historical data (3+ recommended for DCF)",
                field="historical_years",
                recommendation="Add 2 more years of historical data to improve quality score by 7 points",
                impact_score=7,
            )
        )
        return 3

    warnings.append(
        QualityWarning(
            severity=QualityWarning.SEVERITY_HIGH,
            code="NO_HISTORICAL_DATA",
            message="No historical data available",
            field="historical_years",
            recommendation="Add 3+ years of historical data to improve quality score by 10 points",
            impact_score=10,
        )
    )
    return 0


def _score_balance_sheet_completeness(
    current_year_data: object | None, warnings: list[QualityWarning]
) -> int:
    if current_year_data is None:
        return 0

    has_debt = (
        hasattr(current_year_data, "total_debt")
        and getattr(current_year_data, "total_debt") is not None
    )
    has_cash = hasattr(current_year_data, "cash") and getattr(current_year_data, "cash") is not None
    if has_debt and has_cash:
        return 4
    if has_debt or has_cash:
        warnings.append(
            QualityWarning(
                severity=QualityWarning.SEVERITY_LOW,
                code="INCOMPLETE_BALANCE_SHEET",
                message="Balance sheet data is incomplete",
                field="balance_sheet",
                recommendation="Provide both total debt and cash for complete balance sheet",
                impact_score=2,
            )
        )
        return 2
    return 0


def _append_revenue_validity_warnings(
    current_year_data: object | None,
    warnings: list[QualityWarning],
    bounds: ValidityBounds,
) -> int:
    if current_year_data is None:
        return 0

    revenue = getattr(current_year_data, "revenue", None)
    if revenue is None:
        return 0

    try:
        revenue_decimal = to_decimal(str(revenue))
    except (ValueError, TypeError):
        warnings.append(
            QualityWarning(
                severity=QualityWarning.SEVERITY_CRITICAL,
                code="INVALID_REVENUE_TYPE",
                message="Revenue is not a valid number",
                field="revenue",
                recommendation="Provide revenue as a valid number",
                impact_score=5,
            )
        )
        return 1

    if revenue_decimal < bounds.revenue_min or revenue_decimal > bounds.revenue_max:
        warnings.append(
            QualityWarning(
                severity=QualityWarning.SEVERITY_CRITICAL,
                code="INVALID_REVENUE_RANGE",
                message=f"Revenue {revenue} is outside valid range",
                field="revenue",
                recommendation=(
                    f"Revenue must be between {bounds.revenue_min} " f"and {bounds.revenue_max}"
                ),
                impact_score=10,
            )
        )
        return 1

    return 0


def _append_range_validity_warnings(
    current_year_data: object | None,
    warnings: list[QualityWarning],
    bounds: ValidityBounds,
) -> int:
    if current_year_data is None:
        return 0

    return _append_ebitda_range_warning(current_year_data, warnings) + (
        _append_margin_range_warning(current_year_data, warnings, bounds)
    )


def _append_ebitda_range_warning(current_year_data: object, warnings: list[QualityWarning]) -> int:
    ebitda = getattr(current_year_data, "ebitda", None)
    if ebitda is None:
        return 0

    try:
        ebitda_decimal = to_decimal(str(ebitda))
        revenue_decimal = _positive_numeric_decimal_or_none(
            getattr(current_year_data, "revenue", None)
        )
        if revenue_decimal is not None and ebitda_decimal > revenue_decimal:
            warnings.append(
                QualityWarning(
                    severity=QualityWarning.SEVERITY_HIGH,
                    code="UNREALISTIC_EBITDA",
                    message="EBITDA exceeds revenue (mathematically impossible)",
                    field="ebitda",
                    recommendation="Review EBITDA calculation",
                    impact_score=5,
                )
            )
            return 1
    except (ValueError, TypeError):
        return 1

    return 0


def _append_margin_range_warning(
    current_year_data: object,
    warnings: list[QualityWarning],
    bounds: ValidityBounds,
) -> int:
    revenue_decimal = _positive_numeric_decimal_or_none(getattr(current_year_data, "revenue", None))
    ebitda = getattr(current_year_data, "ebitda", None)
    if revenue_decimal is None or ebitda is None:
        return 0

    try:
        ebitda_decimal = to_decimal(str(ebitda))
        margin = ebitda_decimal / revenue_decimal
    except (ZeroDivisionError, ValueError, TypeError):
        return 0

    if bounds.margin_min <= margin <= bounds.margin_max:
        return 0

    warnings.append(
        QualityWarning(
            severity=QualityWarning.SEVERITY_MEDIUM,
            code="EXTREME_MARGIN",
            message=f"EBITDA margin {from_decimal(margin * to_decimal('100'), precision=1):.1f}% is extreme",
            field="ebitda_margin",
            recommendation="Verify margin calculation",
            impact_score=3,
        )
    )
    return 1


def _historical_year_count(request: object) -> int:
    historical_years = getattr(request, "historical_years_data", None) or getattr(
        request, "historical_years", []
    )
    if historical_years is None:
        historical_years = []
    return len(historical_years) if isinstance(historical_years, list) else 0


def _positive_decimal_or_none(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        decimal_value = to_decimal(str(value))
    except (ValueError, TypeError):
        return None
    return decimal_value if decimal_value > 0 else None


def _positive_numeric_decimal_or_none(value: object) -> Decimal | None:
    if not isinstance(value, (int, float, Decimal)) or value <= 0:
        return None
    try:
        return to_decimal(str(value))
    except (ValueError, TypeError):
        return None


def _append_margin_benchmark_warning(
    request: object,
    warnings: list[QualityWarning],
    industry_margin_benchmarks: Mapping[str, Mapping[str, object]],
) -> int:
    current_year_data = _current_year_data(request)
    if current_year_data is None:
        return 0

    revenue_decimal = _positive_numeric_decimal_or_none(getattr(current_year_data, "revenue", None))
    ebitda = getattr(current_year_data, "ebitda", None)
    if revenue_decimal is None or ebitda is None:
        return 0

    try:
        ebitda_decimal = to_decimal(str(ebitda))
        margin = ebitda_decimal / revenue_decimal
        benchmark = _industry_margin_benchmark(request, industry_margin_benchmarks)

        typical_margin = to_decimal(str(benchmark["typical"]))
        min_margin = to_decimal(str(benchmark["min"]))
        max_margin = to_decimal(str(benchmark["max"]))
    except (ValueError, TypeError, ZeroDivisionError, KeyError):
        return 0

    if margin < min_margin or margin > max_margin:
        warnings.append(
            QualityWarning(
                severity=QualityWarning.SEVERITY_MEDIUM,
                code="MARGIN_OUTSIDE_BENCHMARK",
                message=(
                    f"EBITDA margin {from_decimal(margin * to_decimal('100'), precision=1):.1f}% "
                    f"is outside typical industry range "
                    f"({from_decimal(min_margin * to_decimal('100'), precision=1):.1f}% "
                    f"to {from_decimal(max_margin * to_decimal('100'), precision=1):.1f}%)"
                ),
                field="ebitda_margin",
                recommendation=(
                    "Verify margin vs industry benchmark "
                    f"({from_decimal(typical_margin * to_decimal('100'), precision=1):.1f}%)"
                ),
                impact_score=5,
            )
        )
        return 5

    if abs(margin - typical_margin) <= to_decimal("0.10"):
        return 0

    warnings.append(
        QualityWarning(
            severity=QualityWarning.SEVERITY_LOW,
            code="MARGIN_DEVIATION",
            message=(
                f"EBITDA margin {from_decimal(margin * to_decimal('100'), precision=1):.1f}% "
                f"deviates from industry average "
                f"({from_decimal(typical_margin * to_decimal('100'), precision=1):.1f}%)"
            ),
            field="ebitda_margin",
            recommendation="Review margin calculation",
            impact_score=2,
        )
    )
    return 2


def _industry_margin_benchmark(
    request: object, industry_margin_benchmarks: Mapping[str, Mapping[str, object]]
) -> Mapping[str, object]:
    industry = getattr(request, "industry", None) or "default"
    industry_key = str(industry).lower().replace("-", "_").replace(" ", "_")
    return industry_margin_benchmarks.get(industry_key, industry_margin_benchmarks["default"])


def _append_growth_rate_warning(
    request: object,
    warnings: list[QualityWarning],
    growth_rate_min: Decimal,
    growth_rate_max: Decimal,
) -> int:
    projections = getattr(request, "projections", None)
    if not projections:
        return 0

    growth_rate = getattr(projections, "revenue_growth_rate", None)
    if growth_rate is None:
        return 0

    try:
        growth_decimal = to_decimal(str(growth_rate))
    except (ValueError, TypeError):
        return 0

    if growth_rate_min <= growth_decimal <= growth_rate_max:
        return 0

    warnings.append(
        QualityWarning(
            severity=QualityWarning.SEVERITY_HIGH,
            code="EXTREME_GROWTH_RATE",
            message=f"Growth rate {from_decimal(growth_decimal * to_decimal('100'), precision=1):.1f}% is extreme",
            field="revenue_growth_rate",
            recommendation="Verify growth rate is realistic (typical range: -50% to +500%)",
            impact_score=5,
        )
    )
    return 5


def _type_issue_deduction(type_issues: int) -> int:
    if type_issues == 0:
        return 0
    if type_issues == 1:
        return 3
    return 5


def _range_issue_deduction(range_issues: int) -> int:
    if range_issues == 0:
        return 0
    if range_issues == 1:
        return 5
    return 10
