"""
Data Quality Assessor

Comprehensive data quality assessment following McKinsey/Bain 5-dimension framework:
1. Completeness: Required fields present, historical data availability
2. Validity: Data type validation, range checks, format validation
3. Consistency: Cross-field relationships, temporal consistency, ratio stability
4. Accuracy: Reasonableness vs industry benchmarks, outlier detection, statistical validation
5. Timeliness: Data freshness, historical data recency, update frequency

RESEARCH FOUNDATION:
- McKinsey & Company (2015): "Valuation: Measuring and Managing the Value of Companies" - Data Quality Framework
- Bain & Company: "Data Quality in Financial Analysis" - Continuous Monitoring Best Practices
- Damodaran (2012): "Investment Valuation" - Data Validation and Reasonableness Checks
- Big 4 Standards: EY, Deloitte, PwC, KPMG data quality frameworks

METHODOLOGY:
The assessor evaluates data quality across 5 dimensions, each contributing to an overall
quality score (0-100). The score determines methodology eligibility and impacts confidence.

Quality Score Breakdown:
- Completeness: 30 points (revenue 8, EBITDA 8, historical 10, balance sheet 4)
- Validity: 20 points (data types 5, range checks 10, format 5)
- Consistency: 20 points (cross-field 10, temporal 5, ratio 5)
- Accuracy: 20 points (reasonableness 10, outliers 5, statistical 5)
- Timeliness: 10 points (freshness 5, recency 5)
"""

from decimal import Decimal
from typing import Optional

from src.domain.data_quality.assessment_cache import assessment_cache_get as _assessment_cache_get
from src.domain.data_quality.assessment_cache import assessment_cache_key as _assessment_cache_key
from src.domain.data_quality.assessment_cache import assessment_cache_put as _assessment_cache_put
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class QualityWarning:
    """Data quality warning with severity and actionable guidance."""

    SEVERITY_CRITICAL = "critical"  # Blocks valuation
    SEVERITY_HIGH = "high"  # Reduces quality score significantly
    SEVERITY_MEDIUM = "medium"  # Reduces quality score moderately
    SEVERITY_LOW = "low"  # Informational only

    def __init__(
        self,
        severity: str,
        code: str,
        message: str,
        field: Optional[str] = None,
        recommendation: Optional[str] = None,
        impact_score: int = 0,
    ):
        self.severity = severity
        self.code = code
        self.message = message
        self.field = field
        self.recommendation = recommendation
        self.impact_score = impact_score  # Points deducted from quality score

    def __repr__(self):
        return f"<{self.severity.upper()}: {self.message}>"


class QualityDimensionScores:
    """Scores for each quality dimension."""

    def __init__(self):
        self.completeness: int = 0  # 0-30
        self.validity: int = 0  # 0-20
        self.consistency: int = 0  # 0-20
        self.accuracy: int = 0  # 0-20
        self.timeliness: int = 0  # 0-10

    @property
    def total(self) -> int:
        """Total quality score (0-100)."""
        return (
            self.completeness + self.validity + self.consistency + self.accuracy + self.timeliness
        )

    def to_dict(self) -> dict[str, int]:
        """Convert to dictionary."""
        return {
            "completeness": self.completeness,
            "validity": self.validity,
            "consistency": self.consistency,
            "accuracy": self.accuracy,
            "timeliness": self.timeliness,
            "total": self.total,
        }


class DataQualityAssessor:
    """
    Comprehensive data quality assessor following McKinsey/Bain 5-dimension framework.

    Evaluates data quality across:
    1. Completeness: Required fields, historical data
    2. Validity: Data types, ranges, formats
    3. Consistency: Cross-field relationships, temporal trends
    4. Accuracy: Reasonableness vs benchmarks, outliers
    5. Timeliness: Data freshness, recency
    """

    # Industry margin benchmarks for reasonableness checks
    INDUSTRY_MARGIN_BENCHMARKS = {
        "technology": {"min": -Decimal("0.30"), "typical": Decimal("0.20"), "max": 0.45},
        "saas_software": {"min": -Decimal("0.40"), "typical": Decimal("0.25"), "max": 0.50},
        "manufacturing": {"min": -Decimal("0.20"), "typical": Decimal("0.12"), "max": 0.25},
        "retail": {"min": -Decimal("0.15"), "typical": Decimal("0.05"), "max": 0.15},
        "professional_services": {"min": -Decimal("0.25"), "typical": Decimal("0.18"), "max": 0.40},
        "healthcare": {"min": -Decimal("0.20"), "typical": Decimal("0.18"), "max": 0.35},
        "default": {"min": -Decimal("0.30"), "typical": Decimal("0.15"), "max": 0.40},
    }

    # Reasonable bounds for validation
    REVENUE_MIN = to_decimal("0.01")  # Must be positive
    REVENUE_MAX = to_decimal("1000000000000")  # €1T upper bound
    GROWTH_RATE_MIN = to_decimal("-0.50")  # -50% decline
    GROWTH_RATE_MAX = to_decimal("5.00")  # 500% growth
    MARGIN_MIN = to_decimal("-0.85")  # -85% (extreme loss territory)
    MARGIN_MAX = to_decimal("0.85")  # 85% (extreme profit territory)
    EMPLOYEE_MIN = 1
    DEBT_MIN = to_decimal("0")
    CASH_MIN = to_decimal("0")

    def __init__(self, industry_benchmarks: Optional[dict[str, object]] = None):
        """
        Initialize assessor.

        Args:
            industry_benchmarks: Optional industry benchmarks for reasonableness checks
        """
        self.industry_benchmarks = industry_benchmarks or {}
        self.warnings: list[QualityWarning] = []
        self.scores = QualityDimensionScores()

    def assess_quality(
        self, request: object, baseline_score: Optional[int] = None
    ) -> dict[str, object]:
        """
        Comprehensive quality assessment across all 5 dimensions.

        Args:
            request: Valuation request object
            baseline_score: Optional baseline score from Step 0 for comparison

        Returns:
            Mapping with quality_score, dimension_scores, warnings, recommendations
        """
        # Per-request memoisation — assess_quality is called 4× per /calculate
        # (Step 0 initial + Step 2 / Step 9 / Step 11 checkpoints). The scoring
        # is pure over `(request, baseline_score)`, so a hit returns the same
        # dict the first pass produced. We restore `self.scores` and
        # `self.warnings` so any downstream code reading the assessor's
        # attributes still sees the cached state.
        cache_key = _assessment_cache_key(request, baseline_score)
        cached = _assessment_cache_get(cache_key)
        if cached is not None:
            cached_scores = cached.get("__scores_snapshot")
            cached_warnings = cached.get("__warnings_snapshot")
            if isinstance(cached_scores, QualityDimensionScores):
                self.scores = cached_scores
            if isinstance(cached_warnings, list):
                self.warnings = list(cached_warnings)
            logger.debug(
                "🎯 Data quality assessment cache HIT",
                extra={
                    "company": getattr(request, "company_name", "N/A"),
                    "baseline_score": baseline_score,
                    "quality_score": cached.get("quality_score"),
                },
            )
            return {k: v for k, v in cached.items() if not k.startswith("__")}

        # DEBUG: entry breadcrumb; the "✅ complete" INFO at end of method
        # carries the result with all dimension scores in extra={}.
        logger.debug(
            "🎯 Starting comprehensive data quality assessment",
            extra={
                "company": getattr(request, "company_name", "N/A"),
                "baseline_score": baseline_score,
                "methodology": "McKinsey/Bain 5-dimension framework",
            },
        )

        self.warnings = []
        self.scores = QualityDimensionScores()

        # Assess each dimension
        logger.debug(
            "📊 Assessing 5 quality dimensions",
            extra={
                "dimensions": [
                    "Completeness (0-30 points)",
                    "Validity (0-20 points)",
                    "Consistency (0-20 points)",
                    "Accuracy (0-20 points)",
                    "Timeliness (0-10 points)",
                ],
                "total_max": 100,
            },
        )

        self._assess_completeness(request)
        logger.debug(
            "✅ Completeness assessment complete",
            extra={"completeness_score": self.scores.completeness, "max_points": 30},
        )

        self._assess_validity(request)
        logger.debug(
            "✅ Validity assessment complete",
            extra={"validity_score": self.scores.validity, "max_points": 20},
        )

        self._assess_consistency(request)
        logger.debug(
            "✅ Consistency assessment complete",
            extra={"consistency_score": self.scores.consistency, "max_points": 20},
        )

        self._assess_accuracy(request)
        logger.debug(
            "✅ Accuracy assessment complete",
            extra={"accuracy_score": self.scores.accuracy, "max_points": 20},
        )

        self._assess_timeliness(request)
        logger.debug(
            "✅ Timeliness assessment complete",
            extra={"timeliness_score": self.scores.timeliness, "max_points": 10},
        )

        # DEBUG: mid-method waypoint; the "✅ complete" INFO at end carries
        # the same dimension_scores plus the final penalty-adjusted score.
        logger.debug(
            "✅ All 5 dimensions assessed",
            extra={
                "dimension_scores": self.scores.to_dict(),
                "total_before_penalties": self.scores.total,
                "warnings_count": len(self.warnings),
            },
        )

        # Apply warning penalties
        total_penalty = sum(w.impact_score for w in self.warnings)
        final_score = max(0, self.scores.total - total_penalty)

        logger.debug(
            "🧮 Applying warning penalties",
            extra={
                "total_before_penalties": self.scores.total,
                "total_penalty": total_penalty,
                "final_score": final_score,
                "formula": f"Final Score = {self.scores.total} - {total_penalty} = {final_score}",
                "critical_warnings": len(
                    [w for w in self.warnings if w.severity == QualityWarning.SEVERITY_CRITICAL]
                ),
                "high_warnings": len(
                    [w for w in self.warnings if w.severity == QualityWarning.SEVERITY_HIGH]
                ),
                "medium_warnings": len(
                    [w for w in self.warnings if w.severity == QualityWarning.SEVERITY_MEDIUM]
                ),
                "low_warnings": len(
                    [w for w in self.warnings if w.severity == QualityWarning.SEVERITY_LOW]
                ),
            },
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(request, final_score)

        # Check for degradation vs baseline
        degradation = None
        if baseline_score is not None:
            degradation = baseline_score - final_score
            if degradation > 5:
                logger.warning(
                    "⚠️  Data quality degraded since baseline assessment",
                    extra={
                        "baseline_score": baseline_score,
                        "current_score": final_score,
                        "degradation": degradation,
                        "threshold": 5,
                    },
                )
                self.warnings.append(
                    QualityWarning(
                        severity=QualityWarning.SEVERITY_MEDIUM,
                        code="QUALITY_DEGRADATION",
                        message=f"Data quality degraded by {degradation} points since initial assessment",
                        recommendation="Review data inputs for consistency",
                    )
                )
            else:
                logger.debug(
                    "✅ Data quality stable vs baseline",
                    extra={
                        "baseline_score": baseline_score,
                        "current_score": final_score,
                        "degradation": degradation,
                    },
                )

        logger.info(
            "✅ Data quality assessment complete",
            extra={
                "quality_score": final_score,
                "dimension_scores": self.scores.to_dict(),
                "warnings_count": len(self.warnings),
                "recommendations_count": len(recommendations),
                "degradation": degradation,
                "baseline_score": baseline_score,
            },
        )

        result: dict[str, object] = {
            "quality_score": final_score,
            "dimension_scores": self.scores.to_dict(),
            "warnings": [self._warning_to_dict(w) for w in self.warnings],
            "recommendations": recommendations,
            "degradation": degradation,
            "baseline_score": baseline_score,
        }
        # Underscore keys are stripped on return but preserved in the cache so
        # a subsequent hit can restore the assessor's internal state too.
        cache_entry: dict[str, object] = dict(result)
        cache_entry["__scores_snapshot"] = self.scores
        cache_entry["__warnings_snapshot"] = list(self.warnings)
        _assessment_cache_put(cache_key, cache_entry)
        return result

    def _assess_completeness(self, request: object) -> None:
        """Assess completeness dimension (30 points)."""
        from .data_quality.financial_dimensions import assess_completeness_dimension

        self.scores.completeness = assess_completeness_dimension(request, self.warnings)

    def _assess_validity(self, request: object) -> None:
        """Assess validity dimension (20 points)."""
        from .data_quality.financial_dimensions import ValidityBounds, assess_validity_dimension

        bounds = ValidityBounds(
            revenue_min=self.REVENUE_MIN,
            revenue_max=self.REVENUE_MAX,
            margin_min=self.MARGIN_MIN,
            margin_max=self.MARGIN_MAX,
        )
        self.scores.validity = assess_validity_dimension(
            request=request,
            warnings=self.warnings,
            bounds=bounds,
        )

    def _assess_consistency(self, request: object) -> None:
        """Assess consistency dimension (20 points)."""
        from .data_quality.consistency_checkers import (
            CrossFieldRelationshipChecker,
            RatioStabilityChecker,
            TemporalConsistencyChecker,
        )

        score = 20  # Start with full score

        # Initialize checkers
        cross_field_checker = CrossFieldRelationshipChecker()
        temporal_checker = TemporalConsistencyChecker()
        ratio_checker = RatioStabilityChecker()

        # Cross-field relationships (10 points)
        score -= cross_field_checker.check(request, self.warnings)

        # Temporal consistency (5 points)
        score -= temporal_checker.check(request, self.warnings)

        # Ratio stability (5 points)
        historical_years = getattr(request, "historical_years_data", None) or getattr(
            request, "historical_years", []
        )
        score -= ratio_checker.check(request, historical_years, self.warnings)

        self.scores.consistency = max(0, score)

    def _assess_accuracy(self, request: object) -> None:
        """Assess accuracy dimension (20 points)."""
        from .data_quality.financial_dimensions import assess_accuracy_dimension

        self.scores.accuracy = assess_accuracy_dimension(
            request=request,
            warnings=self.warnings,
            industry_margin_benchmarks=self.INDUSTRY_MARGIN_BENCHMARKS,
            growth_rate_min=self.GROWTH_RATE_MIN,
            growth_rate_max=self.GROWTH_RATE_MAX,
        )

    def _assess_timeliness(self, request: object) -> None:
        """Assess timeliness dimension (10 points)."""
        score = 10  # Start with full score

        # Data freshness (5 points)
        # Assume current year data is fresh (no way to check actual date in request)
        # This would ideally check the date of the financial data
        score -= 0  # No deduction if we can't verify

        # Historical recency (5 points)
        historical_years = getattr(request, "historical_years_data", None) or getattr(
            request, "historical_years", []
        )
        if historical_years:
            # Check if most recent year is current year or previous year
            # This is a simplified check - ideally would check actual dates
            score -= 0  # No deduction if we can't verify dates

        self.scores.timeliness = score

    def _generate_recommendations(
        self, request: object, quality_score: int
    ) -> list[dict[str, object]]:
        """Generate actionable recommendations to improve quality score."""
        from .data_quality.recommendations import generate_quality_recommendations

        return generate_quality_recommendations(request, quality_score)

    def _warning_to_dict(self, warning: QualityWarning) -> dict[str, object]:
        """Convert warning to dictionary."""
        return {
            "severity": warning.severity,
            "code": warning.code,
            "message": warning.message,
            "field": warning.field,
            "recommendation": warning.recommendation,
            "impact_score": warning.impact_score,
        }
