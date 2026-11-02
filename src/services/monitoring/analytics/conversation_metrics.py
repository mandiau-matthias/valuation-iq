"""
Conversation Metrics and A/B Testing Framework

BRAIN & MUSCLE ARCHITECTURE NOTE:
This service is DEPRECATED for use in ValuationIQ.
Metrics collection and A/B testing belong in Titan (The Brain).

In STATELESS_MODE=true:
- All metrics methods return early without storing state
- A/B variant assignment is deterministic from request data only
- No session-based state is maintained

Titan should handle all conversation tracking and A/B testing.
This module is kept for backward compatibility and local testing.

Author: Upswitch Engineering Team
Date: October 2025
"""

import logging
import random
import hashlib
from decimal import Decimal
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json
import uuid
from src.utils.decimal_helpers import to_decimal, from_decimal
from src.database.connection import is_stateless_mode

logger = logging.getLogger(__name__)


class VariantType(Enum):
    """A/B test variant types"""

    CONTROL = "control"
    VARIANT_A = "variant_a"
    VARIANT_B = "variant_b"
    VARIANT_C = "variant_c"


class DropOffReason(Enum):
    """Reasons for user drop-off"""

    TIMEOUT = "timeout"
    ERROR = "error"
    USER_EXIT = "user_exit"
    VALIDATION_FAILED = "validation_failed"
    TECHNICAL_ISSUE = "technical_issue"


@dataclass
class ConversationMetrics:
    """Comprehensive conversation metrics"""

    session_id: str
    variant: VariantType
    user_id: Optional[str] = None

    # Engagement metrics
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    time_to_complete: Optional[Decimal] = None  # seconds
    total_questions_asked: int = 0
    questions_skipped: int = 0  # due to business card

    # Interaction metrics
    corrections_made: int = 0  # how many times user edited
    validation_failed: int = 0  # how many times user said "no"
    help_text_views: int = 0  # how many times user clicked help
    uncertainty_detected: int = 0  # how many uncertain responses

    # Quality metrics
    data_completeness: Decimal = Decimal("0.0")
    data_confidence: Decimal = Decimal("0.0")
    validation_errors: int = 0
    validation_warnings: int = 0

    # Conversion metrics
    completed_valuation: bool = False
    drop_off_point: Optional[str] = None  # which question caused drop-off
    drop_off_reason: Optional[DropOffReason] = None

    # User satisfaction
    user_satisfaction: Optional[int] = None  # 1-5 rating
    feedback_text: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "session_id": self.session_id,
            "variant": self.variant.value,
            "user_id": self.user_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "time_to_complete": self.time_to_complete,
            "total_questions_asked": self.total_questions_asked,
            "questions_skipped": self.questions_skipped,
            "corrections_made": self.corrections_made,
            "validation_failed": self.validation_failed,
            "help_text_views": self.help_text_views,
            "uncertainty_detected": self.uncertainty_detected,
            "data_completeness": self.data_completeness,
            "data_confidence": self.data_confidence,
            "validation_errors": self.validation_errors,
            "validation_warnings": self.validation_warnings,
            "completed_valuation": self.completed_valuation,
            "drop_off_point": self.drop_off_point,
            "drop_off_reason": self.drop_off_reason.value if self.drop_off_reason else None,
            "user_satisfaction": self.user_satisfaction,
            "feedback_text": self.feedback_text,
        }


@dataclass
class ABTestConfig:
    """A/B test configuration"""

    test_name: str
    variants: Dict[VariantType, Decimal]  # variant -> traffic percentage
    start_date: datetime
    end_date: Optional[datetime] = None
    target_metrics: List[str] = field(
        default_factory=lambda: ["completion_rate", "time_to_complete"]
    )
    minimum_sample_size: int = 100
    significance_level: Decimal = Decimal("0.05")


@dataclass
class ABTestResult:
    """A/B test statistical result"""

    test_name: str
    variant_a: VariantType
    variant_b: VariantType
    metric: str
    variant_a_value: Decimal
    variant_b_value: Decimal
    improvement: Decimal  # percentage improvement
    p_value: Decimal
    is_significant: bool
    confidence_interval: tuple
    sample_size_a: int
    sample_size_b: int


class ConversationMetricsCollector:
    """
    Collect and analyze conversation metrics for optimization

    BRAIN & MUSCLE ARCHITECTURE:
    In STATELESS_MODE=true, this collector is disabled.
    Titan (The Brain) handles all metrics collection and A/B testing.

    This class is kept for backward compatibility and local testing.
    """

    def __init__(self):
        """Initialize the metrics collector"""
        self._stateless_mode = is_stateless_mode()

        if self._stateless_mode:
            logger.info(
                "🔒 ConversationMetricsCollector: STATELESS_MODE=true - metrics disabled, use Titan"
            )
            self.active_tests = {}
            self.metrics_storage = {}
            return

        self.active_tests: Dict[str, ABTestConfig] = {}
        self.metrics_storage: Dict[str, ConversationMetrics] = {}

        # Initialize default A/B tests
        self._initialize_default_tests()

        logger.info("✅ ConversationMetricsCollector initialized")

    def start_conversation_tracking(
        self, session_id: str, user_id: Optional[str] = None, test_name: Optional[str] = None
    ) -> ConversationMetrics:
        """
        Start tracking a new conversation

        BRAIN & MUSCLE: Disabled in STATELESS_MODE - returns dummy metrics.
        """
        # In stateless mode, return a dummy metrics object
        if self._stateless_mode:
            logger.debug("start_conversation_tracking skipped in STATELESS_MODE")
            return ConversationMetrics(
                session_id=session_id, variant=VariantType.CONTROL, user_id=user_id
            )

        # Determine variant for A/B testing
        variant = self._assign_variant(session_id, user_id, test_name)

        # Create metrics object
        metrics = ConversationMetrics(session_id=session_id, variant=variant, user_id=user_id)

        # Store metrics
        self.metrics_storage[session_id] = metrics

        logger.info(
            "Conversation tracking started",
            extra={
                "session_id": session_id,
                "variant": variant.value,
                "user_id": user_id,
                "test_name": test_name,
            },
        )

        return metrics

    def track_question_asked(self, session_id: str, question_type: str) -> None:
        """Track that a question was asked (disabled in STATELESS_MODE)"""
        if self._stateless_mode:
            return  # Skip tracking in stateless mode

        metrics = self.metrics_storage.get(session_id)
        if metrics:
            metrics.total_questions_asked += 1

            logger.debug(
                "Question asked tracked",
                extra={
                    "session_id": session_id,
                    "question_type": question_type,
                    "total_questions": metrics.total_questions_asked,
                },
            )

    def track_question_skipped(self, session_id: str, reason: str) -> None:
        """Track that a question was skipped"""
        metrics = self.metrics_storage.get(session_id)
        if metrics:
            metrics.questions_skipped += 1

            logger.debug(
                "Question skipped tracked",
                extra={
                    "session_id": session_id,
                    "reason": reason,
                    "questions_skipped": metrics.questions_skipped,
                },
            )

    def track_correction_made(self, session_id: str, field_name: str) -> None:
        """Track that user made a correction"""
        metrics = self.metrics_storage.get(session_id)
        if metrics:
            metrics.corrections_made += 1

            logger.debug(
                "Correction made tracked",
                extra={
                    "session_id": session_id,
                    "field_name": field_name,
                    "corrections_made": metrics.corrections_made,
                },
            )

    def track_validation_failed(self, session_id: str, field_name: str) -> None:
        """Track that validation failed"""
        metrics = self.metrics_storage.get(session_id)
        if metrics:
            metrics.validation_failed += 1

            logger.debug(
                "Validation failed tracked",
                extra={
                    "session_id": session_id,
                    "field_name": field_name,
                    "validation_failed": metrics.validation_failed,
                },
            )

    def track_help_viewed(self, session_id: str, help_topic: str) -> None:
        """Track that user viewed help text"""
        metrics = self.metrics_storage.get(session_id)
        if metrics:
            metrics.help_text_views += 1

            logger.debug(
                "Help viewed tracked",
                extra={
                    "session_id": session_id,
                    "help_topic": help_topic,
                    "help_views": metrics.help_text_views,
                },
            )

    def track_uncertainty_detected(self, session_id: str, field_name: str) -> None:
        """Track that uncertainty was detected in user response"""
        metrics = self.metrics_storage.get(session_id)
        if metrics:
            metrics.uncertainty_detected += 1

            logger.debug(
                "Uncertainty detected tracked",
                extra={
                    "session_id": session_id,
                    "field_name": field_name,
                    "uncertainty_count": metrics.uncertainty_detected,
                },
            )

    def track_data_quality(
        self,
        session_id: str,
        completeness: Decimal,
        confidence: Decimal,
        validation_errors: int,
        validation_warnings: int,
    ) -> None:
        """Track data quality metrics"""
        metrics = self.metrics_storage.get(session_id)
        if metrics:
            metrics.data_completeness = completeness
            metrics.data_confidence = confidence
            metrics.validation_errors = validation_errors
            metrics.validation_warnings = validation_warnings

            logger.debug(
                "Data quality tracked",
                extra={
                    "session_id": session_id,
                    "completeness": completeness,
                    "confidence": confidence,
                    "errors": validation_errors,
                    "warnings": validation_warnings,
                },
            )

    def track_drop_off(self, session_id: str, drop_off_point: str, reason: DropOffReason) -> None:
        """Track user drop-off"""
        metrics = self.metrics_storage.get(session_id)
        if metrics:
            metrics.drop_off_point = drop_off_point
            metrics.drop_off_reason = reason

            logger.info(
                "Drop-off tracked",
                extra={
                    "session_id": session_id,
                    "drop_off_point": drop_off_point,
                    "reason": reason.value,
                },
            )

    def complete_conversation(
        self,
        session_id: str,
        success: bool = True,
        user_satisfaction: Optional[int] = None,
        feedback_text: Optional[str] = None,
    ) -> None:
        """Mark conversation as completed"""
        metrics = self.metrics_storage.get(session_id)
        if metrics:
            metrics.completed_at = datetime.now()
            metrics.time_to_complete = (metrics.completed_at - metrics.started_at).total_seconds()
            metrics.completed_valuation = success
            metrics.user_satisfaction = user_satisfaction
            metrics.feedback_text = feedback_text

            logger.info(
                "Conversation completed",
                extra={
                    "session_id": session_id,
                    "success": success,
                    "time_to_complete": metrics.time_to_complete,
                    "user_satisfaction": user_satisfaction,
                },
            )

    def get_metrics(self, session_id: str) -> Optional[ConversationMetrics]:
        """Get metrics for a specific session"""
        return self.metrics_storage.get(session_id)

    def get_all_metrics(self) -> Dict[str, ConversationMetrics]:
        """Get all collected metrics"""
        return self.metrics_storage.copy()

    def analyze_conversion_funnel(self, time_period: Optional[timedelta] = None) -> Dict[str, Any]:
        """
        Analyze conversion funnel metrics

        Args:
            time_period: Optional time period to filter metrics

        Returns:
            Dictionary with funnel analysis
        """
        metrics_list = list(self.metrics_storage.values())

        # Filter by time period if specified
        if time_period:
            cutoff_date = datetime.now() - time_period
            metrics_list = [m for m in metrics_list if m.started_at >= cutoff_date]

        if not metrics_list:
            return {"error": "No metrics available for analysis"}

        total_sessions = len(metrics_list)
        completed_sessions = sum(1 for m in metrics_list if m.completed_valuation)
        avg_time_to_complete = sum(
            m.time_to_complete for m in metrics_list if m.time_to_complete
        ) / len([m for m in metrics_list if m.time_to_complete])
        avg_questions_asked = sum(m.total_questions_asked for m in metrics_list) / total_sessions
        avg_corrections = sum(m.corrections_made for m in metrics_list) / total_sessions
        avg_help_views = sum(m.help_text_views for m in metrics_list) / total_sessions

        # Drop-off analysis
        drop_off_points = {}
        for metrics in metrics_list:
            if metrics.drop_off_point:
                drop_off_points[metrics.drop_off_point] = (
                    drop_off_points.get(metrics.drop_off_point, 0) + 1
                )

        return {
            "total_sessions": total_sessions,
            "completion_rate": completed_sessions / total_sessions,
            "avg_time_to_complete": avg_time_to_complete,
            "avg_questions_asked": avg_questions_asked,
            "avg_corrections_made": avg_corrections,
            "avg_help_views": avg_help_views,
            "drop_off_points": drop_off_points,
            "data_quality": {
                "avg_completeness": sum(m.data_completeness for m in metrics_list) / total_sessions,
                "avg_confidence": sum(m.data_confidence for m in metrics_list) / total_sessions,
                "avg_validation_errors": sum(m.validation_errors for m in metrics_list)
                / total_sessions,
                "avg_validation_warnings": sum(m.validation_warnings for m in metrics_list)
                / total_sessions,
            },
        }

    def run_ab_test_analysis(self, test_name: str) -> Optional[ABTestResult]:
        """
        Run statistical analysis for an A/B test

        Args:
            test_name: Name of the A/B test

        Returns:
            ABTestResult with statistical analysis
        """
        test_config = self.active_tests.get(test_name)
        if not test_config:
            logger.warning(f"A/B test '{test_name}' not found")
            return None

        # Get metrics for this test
        test_metrics = [
            m for m in self.metrics_storage.values() if m.variant in test_config.variants
        ]

        if len(test_metrics) < test_config.minimum_sample_size:
            logger.warning(
                f"Insufficient sample size for test '{test_name}': {len(test_metrics)} < {test_config.minimum_sample_size}"
            )
            return None

        # Analyze primary metric (completion rate)
        control_metrics = [m for m in test_metrics if m.variant == VariantType.CONTROL]
        variant_metrics = [m for m in test_metrics if m.variant != VariantType.CONTROL]

        if not control_metrics or not variant_metrics:
            logger.warning(f"Insufficient data for test '{test_name}'")
            return None

        # Calculate completion rates
        control_completion_rate = sum(1 for m in control_metrics if m.completed_valuation) / len(
            control_metrics
        )
        variant_completion_rate = sum(1 for m in variant_metrics if m.completed_valuation) / len(
            variant_metrics
        )

        # Calculate improvement
        improvement = (
            (variant_completion_rate - control_completion_rate) / control_completion_rate
        ) * 100

        # Simple statistical significance test (chi-square approximation)
        # This is a simplified version - in production, use proper statistical libraries
        p_value = self._calculate_p_value(control_metrics, variant_metrics)
        is_significant = p_value < test_config.significance_level

        return ABTestResult(
            test_name=test_name,
            variant_a=VariantType.CONTROL,
            variant_b=variant_metrics[0].variant,
            metric="completion_rate",
            variant_a_value=control_completion_rate,
            variant_b_value=variant_completion_rate,
            improvement=improvement,
            p_value=p_value,
            is_significant=is_significant,
            confidence_interval=(
                Decimal("0.0"),
                Decimal("0.0"),
            ),  # Simplified - would need proper calculation
            sample_size_a=len(control_metrics),
            sample_size_b=len(variant_metrics),
        )

    def _assign_variant(
        self, session_id: str, user_id: Optional[str], test_name: Optional[str]
    ) -> VariantType:
        """Assign A/B test variant based on session/user ID"""
        if not test_name or test_name not in self.active_tests:
            return VariantType.CONTROL

        test_config = self.active_tests[test_name]

        # Use deterministic assignment based on session ID
        hash_input = f"{session_id}_{test_name}"
        if user_id:
            hash_input = f"{user_id}_{test_name}"

        hash_value = int(
            hashlib.md5(hash_input.encode(), usedforsecurity=False).hexdigest(),
            16,
        )
        random_value = (hash_value % 100) / Decimal("100.0")

        # Assign variant based on traffic percentages
        cumulative = Decimal("0.0")
        for variant, percentage in test_config.variants.items():
            cumulative += percentage
            if random_value <= cumulative:
                return variant

        return VariantType.CONTROL

    def _calculate_p_value(
        self, control_metrics: List[ConversationMetrics], variant_metrics: List[ConversationMetrics]
    ) -> Decimal:
        """Calculate p-value for statistical significance (simplified)"""
        # This is a simplified chi-square test
        # In production, use proper statistical libraries like scipy.stats

        control_successes = sum(1 for m in control_metrics if m.completed_valuation)
        control_failures = len(control_metrics) - control_successes
        variant_successes = sum(1 for m in variant_metrics if m.completed_valuation)
        variant_failures = len(variant_metrics) - variant_successes

        # Simplified p-value calculation
        # In reality, this would be a proper chi-square test
        if control_successes + variant_successes == 0:
            return Decimal("1.0")

        # Very simplified approximation using Decimal
        total_successes = control_successes + variant_successes
        total_metrics_decimal = Decimal(str(len(control_metrics) + len(variant_metrics)))
        control_len_decimal = Decimal(str(len(control_metrics)))

        if total_metrics_decimal > Decimal("0"):
            expected_control_successes_decimal = (
                Decimal(str(total_successes)) * control_len_decimal
            ) / total_metrics_decimal
        else:
            return Decimal("1.0")

        if expected_control_successes_decimal == Decimal("0"):
            return Decimal("1.0")

        # Simplified chi-square statistic using Decimal
        diff_decimal = Decimal(str(control_successes)) - expected_control_successes_decimal
        chi_square_decimal = (diff_decimal**2) / expected_control_successes_decimal
        chi_square = from_decimal(chi_square_decimal)

        # Very rough p-value approximation
        if chi_square > 3.84:  # 95% confidence threshold
            return Decimal("0.05")
        elif chi_square > 2.71:  # 90% confidence threshold
            return Decimal("0.10")
        else:
            return Decimal("0.20")

    def _initialize_default_tests(self):
        """Initialize default A/B tests"""
        # Question flow optimization test
        self.active_tests["question_flow_optimization"] = ABTestConfig(
            test_name="question_flow_optimization",
            variants={VariantType.CONTROL: Decimal("0.5"), VariantType.VARIANT_A: Decimal("0.5")},
            start_date=datetime.now(),
            target_metrics=["completion_rate", "time_to_complete"],
            minimum_sample_size=50,
        )

        # Validation flow test
        self.active_tests["validation_flow"] = ABTestConfig(
            test_name="validation_flow",
            variants={VariantType.CONTROL: Decimal("0.5"), VariantType.VARIANT_A: Decimal("0.5")},
            start_date=datetime.now(),
            target_metrics=["completion_rate", "validation_failed"],
            minimum_sample_size=50,
        )

        logger.info(f"Initialized {len(self.active_tests)} default A/B tests")
