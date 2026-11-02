"""
Validation and Quality Assurance Package

Comprehensive validation system for the valuation engine including:
- Calculation validation with business rules
- Anomaly detection and outlier identification
- Data quality tracking and metrics
- Cross-validation between methodologies
- Business rule enforcement

ARCHITECTURE:
- Rules engine for validation logic
- Anomaly detector for outlier identification
- Data quality tracker for metrics collection
- Cross-validation framework for methodology comparison
- Business rule enforcement for compliance

USAGE:
    Use ValidationEngine for methodology validation, AnomalyDetector for outlier detection on
    valuation results, and DataQualityTracker to assess input financial data quality.
"""

from .anomaly_detector import AnomalyDetector, AnomalyResult, AnomalyType
from .data_quality_tracker import DataQualityMetrics, DataQualityTracker, QualityDimension
from .validation_engine import ValidationEngine, ValidationResult, ValidationRule

__all__ = [
    "ValidationEngine",
    "ValidationResult",
    "ValidationRule",
    "AnomalyDetector",
    "AnomalyResult",
    "AnomalyType",
    "DataQualityTracker",
    "DataQualityMetrics",
    "QualityDimension",
]
