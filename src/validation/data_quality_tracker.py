from src.utils.exceptions import DataQualityError, DataValidationError

"""
Data Quality Tracker for Valuation Data

Comprehensive data quality tracking system for monitoring and assessing
the quality of financial data throughout the valuation process.

ARCHITECTURE:
- Multi-dimensional quality assessment
- Real-time quality monitoring
- Quality trend analysis
- Data lineage tracking
- Quality scoring and reporting

FEATURES:
- Completeness assessment
- Freshness validation
- Consistency checking
- Accuracy verification
- Source reliability tracking
- Quality trend analysis
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from src.errors.error_handler import handle_error
from src.utils.logging import get_logger, log_validation_step

logger = get_logger(__name__)


class QualityDimension(Enum):
    """Data quality dimensions"""

    COMPLETENESS = "completeness"
    FRESHNESS = "freshness"
    CONSISTENCY = "consistency"
    ACCURACY = "accuracy"
    RELIABILITY = "reliability"
    VALIDITY = "validity"


class QualityLevel(Enum):
    """Quality levels"""

    EXCELLENT = "excellent"  # 90-100%
    GOOD = "good"  # 70-89%
    FAIR = "fair"  # 50-69%
    POOR = "poor"  # 30-49%
    CRITICAL = "critical"  # 0-29%


@dataclass
class QualityMetric:
    """Individual quality metric"""

    dimension: QualityDimension
    score: Decimal  # 0.0 to 1.0
    level: QualityLevel
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_excellent(self) -> bool:
        """Check if quality is excellent"""
        return self.level == QualityLevel.EXCELLENT

    @property
    def is_good(self) -> bool:
        """Check if quality is good or excellent"""
        return self.level in [QualityLevel.GOOD, QualityLevel.EXCELLENT]

    @property
    def is_critical(self) -> bool:
        """Check if quality is critical"""
        return self.level == QualityLevel.CRITICAL


@dataclass
class DataQualityMetrics:
    """Comprehensive data quality metrics"""

    overall_score: Decimal
    overall_level: QualityLevel
    dimension_scores: Dict[QualityDimension, Decimal]
    metrics: List[QualityMetric]
    data_source: str
    assessment_timestamp: datetime = field(default_factory=datetime.utcnow)
    assessment_duration: Decimal = Decimal("0.0")  # Bank-grade: Decimal default

    @property
    def is_high_quality(self) -> bool:
        """Check if data quality is high"""
        return self.overall_level in [QualityLevel.EXCELLENT, QualityLevel.GOOD]

    @property
    def is_low_quality(self) -> bool:
        """Check if data quality is low"""
        return self.overall_level in [QualityLevel.POOR, QualityLevel.CRITICAL]


class DataQualityTracker:
    """
    Comprehensive data quality tracking system.

    Features:
    - Multi-dimensional quality assessment
    - Real-time quality monitoring
    - Quality trend analysis
    - Data lineage tracking
    - Quality scoring and reporting
    """

    def __init__(self):
        self.logger = get_logger(__name__)
        self._quality_history: List[DataQualityMetrics] = []
        self._max_history = 1000
        self._required_fields = ["revenue", "ebitda", "net_income", "growth_rate", "industry"]
        self._freshness_thresholds = {
            "financial_data": 365,  # days
            "market_data": 30,  # days
            "industry_data": 90,  # days
        }

    def assess_data_quality(
        self, data: Dict[str, Any], data_source: str = "unknown"
    ) -> DataQualityMetrics:
        """
        Assess data quality across multiple dimensions.

        Args:
            data: Data to assess
            data_source: Source of the data

        Returns:
            Comprehensive quality metrics
        """
        try:
            start_time = time.time()

            self.logger.info("Starting data quality assessment", data_source=data_source)

            # Assess each quality dimension
            completeness_score = self._assess_completeness(data)
            freshness_score = self._assess_freshness(data)
            consistency_score = self._assess_consistency(data)
            accuracy_score = self._assess_accuracy(data)
            reliability_score = self._assess_reliability(data, data_source)
            validity_score = self._assess_validity(data)

            # Create quality metrics (convert float to Decimal for QualityMetric)
            metrics = [
                QualityMetric(
                    QualityDimension.COMPLETENESS,
                    Decimal(str(completeness_score)),
                    self._get_quality_level(completeness_score),
                ),
                QualityMetric(
                    QualityDimension.FRESHNESS,
                    Decimal(str(freshness_score)),
                    self._get_quality_level(freshness_score),
                ),
                QualityMetric(
                    QualityDimension.CONSISTENCY,
                    Decimal(str(consistency_score)),
                    self._get_quality_level(consistency_score),
                ),
                QualityMetric(
                    QualityDimension.ACCURACY,
                    Decimal(str(accuracy_score)),
                    self._get_quality_level(accuracy_score),
                ),
                QualityMetric(
                    QualityDimension.RELIABILITY,
                    Decimal(str(reliability_score)),
                    self._get_quality_level(reliability_score),
                ),
                QualityMetric(
                    QualityDimension.VALIDITY,
                    Decimal(str(validity_score)),
                    self._get_quality_level(validity_score),
                ),
            ]

            # Calculate overall score
            dimension_scores = {
                QualityDimension.COMPLETENESS: completeness_score,
                QualityDimension.FRESHNESS: freshness_score,
                QualityDimension.CONSISTENCY: consistency_score,
                QualityDimension.ACCURACY: accuracy_score,
                QualityDimension.RELIABILITY: reliability_score,
                QualityDimension.VALIDITY: validity_score,
            }

            overall_score = sum(dimension_scores.values()) / len(dimension_scores)
            overall_level = self._get_quality_level(overall_score)

            # Create quality metrics (convert float to Decimal for bank-grade precision)
            quality_metrics = DataQualityMetrics(
                overall_score=Decimal(str(overall_score)),
                overall_level=overall_level,
                dimension_scores={k: Decimal(str(v)) for k, v in dimension_scores.items()},
                metrics=metrics,
                data_source=data_source,
                assessment_duration=Decimal(str(time.time() - start_time)),
            )

            # Store in history
            self._store_quality_metrics(quality_metrics)

            # Log assessment results
            self._log_quality_assessment_results(quality_metrics)

            return quality_metrics

        except DataValidationError as e:
            self.logger.error(f"Data quality assessment failed: {e}", exc_info=True)
            raise

    def _assess_completeness(self, data: Dict[str, Any]) -> Decimal:
        """Assess data completeness"""
        if not data:
            return 0.0

        # Check required fields
        present_fields = sum(
            1 for field in self._required_fields if field in data and data[field] is not None
        )
        completeness_score = present_fields / len(self._required_fields)

        # Check for empty values
        non_empty_values = sum(1 for value in data.values() if value is not None and value != "")
        total_fields = len(data)
        non_empty_ratio = non_empty_values / total_fields if total_fields > 0 else 0

        # Combine scores
        final_score = (completeness_score * 0.7) + (non_empty_ratio * 0.3)

        return min(final_score, 1.0)

    def _assess_freshness(self, data: Dict[str, Any]) -> Decimal:
        """Assess data freshness"""
        freshness_scores = []

        # Check financial data freshness
        if "financial_data_date" in data:
            data_date = data["financial_data_date"]
            if isinstance(data_date, str):
                try:
                    data_date = datetime.fromisoformat(data_date.replace("Z", "+00:00"))
                except (ValueError, TypeError, AttributeError):
                    data_date = datetime.now(timezone.utc)
            # Ensure both are timezone-aware for comparison
            now = datetime.now(timezone.utc)
            if data_date.tzinfo is None:
                data_date = data_date.replace(tzinfo=timezone.utc)

            days_old = (now - data_date).days
            financial_freshness = max(
                0, 1 - (days_old / self._freshness_thresholds["financial_data"])
            )
            freshness_scores.append(financial_freshness)

        # Check market data freshness
        if "market_data_date" in data:
            data_date = data["market_data_date"]
            if isinstance(data_date, str):
                try:
                    data_date = datetime.fromisoformat(data_date.replace("Z", "+00:00"))
                except (ValueError, TypeError, AttributeError):
                    data_date = datetime.now(timezone.utc)
            now = datetime.now(timezone.utc)
            if data_date.tzinfo is None:
                data_date = data_date.replace(tzinfo=timezone.utc)

            days_old = (now - data_date).days
            market_freshness = max(0, 1 - (days_old / self._freshness_thresholds["market_data"]))
            freshness_scores.append(market_freshness)

        # Default freshness if no dates provided
        if not freshness_scores:
            freshness_scores.append(0.5)  # Assume moderate freshness

        return sum(freshness_scores) / len(freshness_scores)

    def _assess_consistency(self, data: Dict[str, Any]) -> Decimal:
        """Assess data consistency"""
        consistency_checks = []

        # Check revenue vs EBITDA consistency
        revenue = data.get("revenue", 0)
        ebitda = data.get("ebitda", 0)
        if revenue > 0 and ebitda is not None:
            ebitda_margin = ebitda / revenue
            # EBITDA margin should be between 5% and 50%
            if 0.05 <= ebitda_margin <= 0.50:
                consistency_checks.append(1.0)
            else:
                consistency_checks.append(0.5)

        # Check EBITDA vs Net Income consistency
        net_income = data.get("net_income", 0)
        if ebitda is not None and net_income is not None:
            # Net income should be less than EBITDA
            if net_income <= ebitda:
                consistency_checks.append(1.0)
            else:
                consistency_checks.append(0.3)

        # Check growth rate consistency
        growth_rate = data.get("growth_rate", 0)
        if growth_rate is not None:
            # Growth rate should be reasonable (-50% to 100%)
            if -0.5 <= growth_rate <= 1.0:
                consistency_checks.append(1.0)
            else:
                consistency_checks.append(0.2)

        return sum(consistency_checks) / len(consistency_checks) if consistency_checks else 0.5

    def _assess_accuracy(self, data: Dict[str, Any]) -> Decimal:
        """Assess data accuracy"""
        accuracy_checks = []

        # Check for reasonable values
        revenue = data.get("revenue", 0)
        if revenue > 0:
            accuracy_checks.append(1.0)
        else:
            accuracy_checks.append(0.0)

        ebitda = data.get("ebitda", 0)
        if ebitda is not None and ebitda >= 0:
            accuracy_checks.append(1.0)
        else:
            accuracy_checks.append(0.5)

        # Check for data type consistency
        numeric_fields = ["revenue", "ebitda", "net_income", "growth_rate"]
        type_consistency = sum(
            1 for field in numeric_fields if field in data and isinstance(data[field], (int, float))
        )
        type_score = type_consistency / len(numeric_fields) if numeric_fields else 0.5
        accuracy_checks.append(type_score)

        return sum(accuracy_checks) / len(accuracy_checks) if accuracy_checks else 0.5

    def _assess_reliability(self, data: Dict[str, Any], data_source: str) -> Decimal:
        """Assess data source reliability"""
        # Source reliability scores
        source_scores = {
            "kbo_database": 0.95,
            "fmp_api": 0.90,
            "oecd_api": 0.85,
            "ecb_api": 0.90,
            "user_input": 0.70,
            "estimated": 0.50,
            "unknown": 0.30,
        }

        return source_scores.get((data_source or "unknown").lower(), 0.50)

    def _assess_validity(self, data: Dict[str, Any]) -> Decimal:
        """Assess data validity"""
        validity_checks = []

        # Check for positive values where expected
        revenue = data.get("revenue", 0)
        if revenue > 0:
            validity_checks.append(1.0)
        else:
            validity_checks.append(0.0)

        # Check for reasonable ranges
        growth_rate = data.get("growth_rate")
        if growth_rate is None:
            growth_rate = 0
        if -1.0 <= growth_rate <= 2.0:  # -100% to 200%
            validity_checks.append(1.0)
        else:
            validity_checks.append(0.0)

        # Check for non-null critical fields
        critical_fields = ["revenue", "industry"]
        non_null_count = sum(
            1 for field in critical_fields if field in data and data[field] is not None
        )
        null_score = non_null_count / len(critical_fields) if critical_fields else 0.5
        validity_checks.append(null_score)

        return sum(validity_checks) / len(validity_checks) if validity_checks else 0.5

    def _get_quality_level(self, score: Decimal) -> QualityLevel:
        """Convert score to quality level"""
        if score >= 0.9:
            return QualityLevel.EXCELLENT
        elif score >= 0.7:
            return QualityLevel.GOOD
        elif score >= 0.5:
            return QualityLevel.FAIR
        elif score >= 0.3:
            return QualityLevel.POOR
        else:
            return QualityLevel.CRITICAL

    def _log_quality_assessment_results(self, metrics: DataQualityMetrics):
        """Log quality assessment results.

        DEBUG: paired with the canonical "✅ Data quality assessment complete"
        INFO emitted by DataQualityAssessor; duplicate emission noise.
        """
        self.logger.debug(
            "Data quality assessment completed",
            overall_score=metrics.overall_score,
            overall_level=metrics.overall_level.value,
            data_source=metrics.data_source,
            assessment_duration=metrics.assessment_duration,
        )

        # Log validation step
        log_validation_step(
            "data_quality_assessment",
            {"data_source": metrics.data_source, "total_dimensions": len(metrics.dimension_scores)},
            ["completeness", "freshness", "consistency", "accuracy", "reliability", "validity"],
            {
                "overall_score": metrics.overall_score,
                "overall_level": metrics.overall_level.value,
                "dimension_scores": {
                    dim.value: score for dim, score in metrics.dimension_scores.items()
                },
                "assessment_duration": metrics.assessment_duration,
            },
        )

    def _store_quality_metrics(self, metrics: DataQualityMetrics):
        """Store quality metrics in history"""
        self._quality_history.append(metrics)

        # Keep only recent history
        if len(self._quality_history) > self._max_history:
            self._quality_history = self._quality_history[-self._max_history :]

    def get_quality_trends(self, days: int = 30) -> Dict[str, Any]:
        """Get quality trends over time"""
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_metrics = [m for m in self._quality_history if m.assessment_timestamp >= cutoff_date]

        if not recent_metrics:
            return {"trend": "unknown", "stability": 0.0}

        # Calculate trends
        scores = [m.overall_score for m in recent_metrics]
        if len(scores) < 2:
            return {"trend": "unknown", "stability": 0.0}

        # Calculate trend (improving, declining, stable)
        score_change = scores[-1] - scores[0]
        if score_change > 0.1:
            trend = "improving"
        elif score_change < -0.1:
            trend = "declining"
        else:
            trend = "stable"

        # Calculate stability (lower variance = more stable)
        score_variance = sum((score - sum(scores) / len(scores)) ** 2 for score in scores) / len(
            scores
        )
        stability = max(0, 1 - score_variance)  # Convert to 0-1 scale

        return {
            "trend": trend,
            "stability": stability,
            "average_score": sum(scores) / len(scores),
            "score_change": score_change,
            "data_points": len(scores),
        }

    def get_quality_summary(self) -> Dict[str, Any]:
        """Get quality summary statistics"""
        if not self._quality_history:
            return {"total_assessments": 0}

        total_assessments = len(self._quality_history)
        high_quality_count = sum(1 for m in self._quality_history if m.is_high_quality)
        low_quality_count = sum(1 for m in self._quality_history if m.is_low_quality)

        # Group by data source
        source_counts = {}
        for metrics in self._quality_history:
            source_counts[metrics.data_source] = source_counts.get(metrics.data_source, 0) + 1

        return {
            "total_assessments": total_assessments,
            "high_quality_count": high_quality_count,
            "low_quality_count": low_quality_count,
            "average_score": sum(m.overall_score for m in self._quality_history)
            / total_assessments,
            "data_sources": source_counts,
        }

    def get_quality_history(self, limit: int = 100) -> List[DataQualityMetrics]:
        """Get recent quality assessment history"""
        return self._quality_history[-limit:] if limit else self._quality_history

    def get_quality_by_source(self, data_source: str) -> List[DataQualityMetrics]:
        """Get quality metrics for a specific data source"""
        return [m for m in self._quality_history if m.data_source == data_source]

    def get_quality_by_level(self, level: QualityLevel) -> List[DataQualityMetrics]:
        """Get quality metrics for a specific quality level"""
        return [m for m in self._quality_history if m.overall_level == level]
