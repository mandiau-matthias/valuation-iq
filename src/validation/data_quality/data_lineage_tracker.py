"""
Data Lineage and Quality Tracking Service

This service tracks the provenance and quality of all data points collected
during the valuation conversation process. It provides:

1. Data Lineage Tracking - Where each data point came from
2. Quality Scoring - Confidence and accuracy metrics
3. Audit Trail - Complete history of data changes
4. Compliance Support - GDPR and data regulation compliance

Author: Upswitch Engineering Team
Date: October 2025
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from src.utils.logging import get_logger

logger = get_logger(__name__)


class DataSource(Enum):
    """Sources of data in the system"""

    USER_INPUT = "user_input"
    BUSINESS_CARD = "business_card"
    REGISTRY = "registry"
    ML_INFERENCE = "ml_inference"
    BUSINESS_PROFILE = "business_profile"
    VALIDATION_CORRECTION = "validation_correction"


class ValidationStatus(Enum):
    """Validation status of data points"""

    PENDING = "pending"
    VALIDATED = "validated"
    FLAGGED = "flagged"
    REJECTED = "rejected"


class InputMethod(Enum):
    """Method used to input data"""

    TYPED = "typed"
    SELECTED = "selected"
    VOICE = "voice"
    IMPORTED = "imported"
    AUTO_FILLED = "auto_filled"


@dataclass
class DataPoint:
    """Individual data point with full lineage tracking"""

    field_name: str
    value: Any
    source: DataSource
    timestamp: datetime
    confidence: Decimal
    validation_status: ValidationStatus = ValidationStatus.PENDING

    # Audit trail
    created_by: Optional[str] = None  # user_id
    updated_by: Optional[str] = None  # user_id
    update_reason: Optional[str] = None  # "correction" | "validation" | "refresh"
    previous_value: Optional[Any] = None

    # ML features
    input_method: InputMethod = InputMethod.TYPED
    time_to_input: Optional[Decimal] = None  # seconds (hesitation = uncertainty)
    edit_count: int = 0
    validation_errors: List[str] = field(default_factory=list)
    validation_warnings: List[str] = field(default_factory=list)

    # Quality metrics
    completeness_score: Decimal = Decimal("1.0")
    consistency_score: Decimal = Decimal("1.0")
    recency_score: Decimal = Decimal("1.0")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "field_name": self.field_name,
            "value": self.value,
            "source": self.source.value,
            "timestamp": self.timestamp.isoformat(),
            "confidence": (
                str(self.confidence) if isinstance(self.confidence, Decimal) else self.confidence
            ),
            "validation_status": self.validation_status.value,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
            "update_reason": self.update_reason,
            "previous_value": self.previous_value,
            "input_method": self.input_method.value,
            "time_to_input": (
                str(self.time_to_input)
                if isinstance(self.time_to_input, Decimal)
                else self.time_to_input
            ),
            "edit_count": self.edit_count,
            "validation_errors": self.validation_errors,
            "validation_warnings": self.validation_warnings,
            "completeness_score": (
                str(self.completeness_score)
                if isinstance(self.completeness_score, Decimal)
                else self.completeness_score
            ),
            "consistency_score": (
                str(self.consistency_score)
                if isinstance(self.consistency_score, Decimal)
                else self.consistency_score
            ),
            "recency_score": (
                str(self.recency_score)
                if isinstance(self.recency_score, Decimal)
                else self.recency_score
            ),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DataPoint":
        """Create from dictionary"""

        # Helper to convert to Decimal
        def to_decimal(val, default="1.0"):
            if val is None:
                return Decimal(default)
            if isinstance(val, Decimal):
                return val
            return Decimal(str(val))

        return cls(
            field_name=data["field_name"],
            value=data["value"],
            source=DataSource(data["source"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            confidence=to_decimal(data.get("confidence"), "1.0"),
            validation_status=ValidationStatus(data["validation_status"]),
            created_by=data.get("created_by"),
            updated_by=data.get("updated_by"),
            update_reason=data.get("update_reason"),
            previous_value=data.get("previous_value"),
            input_method=InputMethod(data.get("input_method", "typed")),
            time_to_input=(
                to_decimal(data.get("time_to_input"))
                if data.get("time_to_input") is not None
                else None
            ),
            edit_count=data.get("edit_count", 0),
            validation_errors=data.get("validation_errors", []),
            validation_warnings=data.get("validation_warnings", []),
            completeness_score=to_decimal(data.get("completeness_score"), "1.0"),
            consistency_score=to_decimal(data.get("consistency_score"), "1.0"),
            recency_score=to_decimal(data.get("recency_score"), "1.0"),
        )


@dataclass
class QualityReport:
    """Comprehensive data quality assessment"""

    completeness: Decimal  # % of required fields filled
    accuracy: Decimal  # Confidence that data is correct
    consistency: Decimal  # Cross-field validation
    timeliness: Decimal  # How recent the data is
    validity: Decimal  # Format and range validation
    uniqueness: Decimal  # No duplicate or conflicting data

    overall_score: Decimal = Decimal("0.0")

    def __post_init__(self):
        """Calculate overall quality score"""
        # Bank-grade: Use Decimal arithmetic for precision
        self.overall_score = (
            self.completeness * Decimal("0.25")
            + self.accuracy * Decimal("0.25")
            + self.consistency * Decimal("0.20")
            + self.timeliness * Decimal("0.15")
            + self.validity * Decimal("0.10")
            + self.uniqueness * Decimal("0.05")
        )


class DataLineageTracker:
    """
    Track data lineage and quality throughout the conversation process

    Provides comprehensive tracking of:
    - Data provenance (where data came from)
    - Quality metrics (confidence, completeness, consistency)
    - Audit trail (who changed what when)
    - Compliance support (GDPR, data regulations)
    """

    def __init__(self):
        """Initialize the data lineage tracker"""
        self.data_points: Dict[str, DataPoint] = {}  # field_name -> DataPoint
        self.conversation_id: str = str(uuid.uuid4())
        self.session_start: datetime = datetime.now()

        logger.info("✅ DataLineageTracker initialized", conversation_id=self.conversation_id)

    def track_data_point(
        self,
        field_name: str,
        value: Any,
        source: DataSource,
        user_id: Optional[str] = None,
        input_method: InputMethod = InputMethod.TYPED,
        time_to_input: Optional[Decimal] = None,
        confidence: Decimal = Decimal("1.0"),
        validation_errors: Optional[List[str]] = None,
        validation_warnings: Optional[List[str]] = None,
    ) -> DataPoint:
        """
        Track a new data point with full lineage information

        Args:
            field_name: Name of the field
            value: The data value
            source: Where the data came from
            user_id: ID of the user who provided/updated the data
            input_method: How the data was input
            time_to_input: Time taken to input (seconds)
            confidence: Confidence score (0.0-1.0)
            validation_errors: List of validation errors
            validation_warnings: List of validation warnings

        Returns:
            DataPoint object with full lineage information
        """
        # Check if this field already exists
        existing_point = self.data_points.get(field_name)

        if existing_point:
            # Update existing data point
            existing_point.previous_value = existing_point.value
            existing_point.value = value
            existing_point.updated_by = user_id
            existing_point.update_reason = "correction"
            existing_point.edit_count += 1
            existing_point.timestamp = datetime.now()
            existing_point.confidence = confidence
            existing_point.validation_errors = validation_errors or []
            existing_point.validation_warnings = validation_warnings or []

            # Update quality scores
            self._update_quality_scores(existing_point)

            logger.info(
                "Data point updated",
                extra={
                    "field": field_name,
                    "previous_value": existing_point.previous_value,
                    "new_value": value,
                    "source": source.value,
                    "edit_count": existing_point.edit_count,
                },
            )

            return existing_point

        else:
            # Create new data point
            data_point = DataPoint(
                field_name=field_name,
                value=value,
                source=source,
                timestamp=datetime.now(),
                confidence=confidence,
                created_by=user_id,
                input_method=input_method,
                time_to_input=time_to_input,
                validation_errors=validation_errors or [],
                validation_warnings=validation_warnings or [],
            )

            # Calculate quality scores
            self._calculate_quality_scores(data_point)

            self.data_points[field_name] = data_point

            logger.info(
                "Data point created",
                extra={
                    "field": field_name,
                    "value": value,
                    "source": source.value,
                    "confidence": confidence,
                },
            )

            return data_point

    def get_data_point(self, field_name: str) -> Optional[DataPoint]:
        """Get a specific data point by field name"""
        return self.data_points.get(field_name)

    def get_all_data_points(self) -> Dict[str, DataPoint]:
        """Get all tracked data points"""
        return self.data_points.copy()

    def assess_quality(self, required_fields: List[str] = None) -> QualityReport:
        """
        Assess overall data quality

        Args:
            required_fields: List of required fields for completeness calculation

        Returns:
            QualityReport with comprehensive quality metrics
        """
        if not self.data_points:
            return QualityReport(
                completeness=Decimal("0.0"),
                accuracy=Decimal("0.0"),
                consistency=Decimal("0.0"),
                timeliness=Decimal("0.0"),
                validity=Decimal("0.0"),
                uniqueness=Decimal("0.0"),
            )

        # Calculate completeness
        if required_fields:
            filled_fields = sum(1 for field in required_fields if field in self.data_points)
            completeness = Decimal(str(filled_fields)) / Decimal(str(len(required_fields)))
        else:
            # Use all fields as required
            completeness = Decimal("1.0") if self.data_points else Decimal("0.0")

        # Calculate accuracy (average confidence) - Bank-grade Decimal arithmetic
        total_confidence = sum(dp.confidence for dp in self.data_points.values())
        accuracy = total_confidence / Decimal(str(len(self.data_points)))

        # Calculate consistency (average consistency score) - Bank-grade Decimal arithmetic
        total_consistency = sum(dp.consistency_score for dp in self.data_points.values())
        consistency = total_consistency / Decimal(str(len(self.data_points)))

        # Calculate timeliness (average recency score) - Bank-grade Decimal arithmetic
        total_recency = sum(dp.recency_score for dp in self.data_points.values())
        timeliness = total_recency / Decimal(str(len(self.data_points)))

        # Calculate validity (based on validation errors)
        total_errors = sum(len(dp.validation_errors) for dp in self.data_points.values())
        validity = max(
            Decimal("0.0"), Decimal("1.0") - Decimal(str(total_errors / len(self.data_points)))
        )

        # Calculate uniqueness (no duplicate values)
        values = [dp.value for dp in self.data_points.values()]
        unique_values = len(set(str(v) for v in values))
        uniqueness = (
            Decimal(str(unique_values)) / Decimal(str(len(values))) if values else Decimal("1.0")
        )

        return QualityReport(
            completeness=completeness,
            accuracy=accuracy,
            consistency=consistency,
            timeliness=timeliness,
            validity=validity,
            uniqueness=uniqueness,
        )

    def get_audit_trail(self) -> List[Dict[str, Any]]:
        """Get complete audit trail of all data changes"""
        audit_trail = []

        for field_name, data_point in self.data_points.items():
            audit_entry = {
                "field_name": field_name,
                "current_value": data_point.value,
                "source": data_point.source.value,
                "timestamp": data_point.timestamp.isoformat(),
                "created_by": data_point.created_by,
                "updated_by": data_point.updated_by,
                "edit_count": data_point.edit_count,
                "validation_status": data_point.validation_status.value,
                "confidence": data_point.confidence,
            }

            if data_point.previous_value is not None:
                audit_entry["previous_value"] = data_point.previous_value
                audit_entry["update_reason"] = data_point.update_reason

            audit_trail.append(audit_entry)

        # Sort by timestamp
        audit_trail.sort(key=lambda x: x["timestamp"])

        return audit_trail

    def export_for_compliance(self) -> Dict[str, Any]:
        """Export data for compliance purposes (GDPR, etc.)"""
        return {
            "conversation_id": self.conversation_id,
            "session_start": self.session_start.isoformat(),
            "session_end": datetime.now().isoformat(),
            "data_points": {name: dp.to_dict() for name, dp in self.data_points.items()},
            "audit_trail": self.get_audit_trail(),
            "quality_report": self.assess_quality().__dict__,
        }

    def _calculate_quality_scores(self, data_point: DataPoint):
        """Calculate quality scores for a data point"""
        # Completeness score (always 1.0 for individual points)
        data_point.completeness_score = Decimal("1.0")

        # Consistency score (based on validation warnings)
        warning_count = len(data_point.validation_warnings)
        data_point.consistency_score = max(
            Decimal("0.0"), Decimal("1.0") - Decimal(str(warning_count * 0.1))
        )

        # Recency score (based on how recent the data is)
        days_old = (datetime.now() - data_point.timestamp).days
        if days_old < 1:
            data_point.recency_score = Decimal("1.0")
        elif days_old < 7:
            data_point.recency_score = Decimal("0.9")
        elif days_old < 30:
            data_point.recency_score = Decimal("0.8")
        elif days_old < 90:
            data_point.recency_score = Decimal("0.7")
        else:
            data_point.recency_score = max(
                Decimal("0.5"), Decimal("1.0") - Decimal(str(days_old / 365))
            )

    def _update_quality_scores(self, data_point: DataPoint):
        """Update quality scores for an existing data point"""
        # Recalculate all scores
        self._calculate_quality_scores(data_point)

        # Adjust confidence based on edit count
        if data_point.edit_count > 1:
            # Multiple edits suggest uncertainty
            # Bank-grade: Use Decimal arithmetic for precision
            decay_factor = Decimal("0.9") ** (data_point.edit_count - 1)
            data_point.confidence *= decay_factor
            data_point.confidence = max(Decimal("0.1"), data_point.confidence)

    def get_source_breakdown(self) -> Dict[str, int]:
        """Get breakdown of data sources"""
        source_counts = {}
        for data_point in self.data_points.values():
            source = data_point.source.value
            source_counts[source] = source_counts.get(source, 0) + 1
        return source_counts

    def get_confidence_distribution(self) -> Dict[str, int]:
        """Get distribution of confidence scores"""
        confidence_ranges = {"high (0.8-1.0)": 0, "medium (0.5-0.8)": 0, "low (0.0-0.5)": 0}

        for data_point in self.data_points.values():
            confidence = data_point.confidence
            if confidence >= 0.8:
                confidence_ranges["high (0.8-1.0)"] += 1
            elif confidence >= 0.5:
                confidence_ranges["medium (0.5-0.8)"] += 1
            else:
                confidence_ranges["low (0.0-0.5)"] += 1

        return confidence_ranges
