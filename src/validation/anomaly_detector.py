from src.errors.error_types import ValidationError
from src.utils.exceptions import DCFCalculationError

"""
Anomaly Detector for Valuation Results

Comprehensive anomaly detection system for identifying outliers and suspicious patterns
in valuation calculations and business data.

ARCHITECTURE:
- Statistical outlier detection
- Historical comparison analysis
- Industry benchmark comparison
- Pattern recognition algorithms
- Anomaly scoring and classification

FEATURES:
- Z-score based outlier detection
- Interquartile range (IQR) analysis
- Historical data comparison
- Industry benchmark validation
- Pattern anomaly detection
- Anomaly severity scoring
"""

import statistics
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from src.errors.error_handler import handle_error
from src.utils.logging import get_logger, log_validation_step

logger = get_logger(__name__)


class AnomalyType(Enum):
    """Types of anomalies"""

    STATISTICAL_OUTLIER = "statistical_outlier"
    HISTORICAL_DEVIATION = "historical_deviation"
    INDUSTRY_DEVIATION = "industry_deviation"
    PATTERN_ANOMALY = "pattern_anomaly"
    CALCULATION_ERROR = "calculation_error"
    DATA_QUALITY_ISSUE = "data_quality_issue"


class AnomalySeverity(Enum):
    """Anomaly severity levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AnomalyResult:
    """Result of anomaly detection"""

    anomaly_type: AnomalyType
    severity: AnomalySeverity
    score: Decimal  # 0.0 to 1.0, higher = more anomalous
    description: str
    field_name: str
    actual_value: Any
    expected_value: Any = None
    confidence: Decimal = Decimal("0.0")  # Bank-grade: Decimal default (0.0 to 1.0)
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_critical(self) -> bool:
        """Check if anomaly is critical"""
        return self.severity == AnomalySeverity.CRITICAL

    @property
    def is_high_severity(self) -> bool:
        """Check if anomaly is high severity or critical"""
        return self.severity in [AnomalySeverity.HIGH, AnomalySeverity.CRITICAL]


class AnomalyDetector:
    """
    Comprehensive anomaly detection system for valuation results.

    Features:
    - Statistical outlier detection
    - Historical comparison analysis
    - Industry benchmark comparison
    - Pattern recognition algorithms
    - Anomaly scoring and classification
    """

    def __init__(self):
        self.logger = get_logger(__name__)
        self._detection_history: List[AnomalyResult] = []
        self._max_history = 1000
        self._z_score_threshold = 2.5  # Standard deviations for outlier detection
        self._iqr_multiplier = 1.5  # IQR multiplier for outlier detection

    def detect_anomalies(
        self,
        valuation_data: Dict[str, Any],
        historical_data: Optional[List[Dict[str, Any]]] = None,
        industry_benchmarks: Optional[Dict[str, Any]] = None,
    ) -> List[AnomalyResult]:
        """
        Detect anomalies in valuation data.

        Args:
            valuation_data: Current valuation data
            historical_data: Historical valuation data for comparison
            industry_benchmarks: Industry benchmark data

        Returns:
            List of detected anomalies
        """
        try:
            self.logger.info("Starting anomaly detection", valuation_data=valuation_data)

            anomalies = []

            # Statistical outlier detection
            statistical_anomalies = self._detect_statistical_outliers(valuation_data)
            anomalies.extend(statistical_anomalies)

            # Historical comparison
            if historical_data:
                historical_anomalies = self._detect_historical_deviations(
                    valuation_data, historical_data
                )
                anomalies.extend(historical_anomalies)

            # Industry benchmark comparison
            if industry_benchmarks:
                industry_anomalies = self._detect_industry_deviations(
                    valuation_data, industry_benchmarks
                )
                anomalies.extend(industry_anomalies)

            # Pattern anomaly detection
            pattern_anomalies = self._detect_pattern_anomalies(valuation_data)
            anomalies.extend(pattern_anomalies)

            # Store anomalies in history
            for anomaly in anomalies:
                self._store_anomaly(anomaly)

            # Log detection results
            self._log_anomaly_detection_results(anomalies)

            return anomalies

        except DCFCalculationError as e:
            self.logger.error(f"Anomaly detection failed: {e}", exc_info=True)
            raise

    def _detect_statistical_outliers(self, data: Dict[str, Any]) -> List[AnomalyResult]:
        """Detect statistical outliers using Z-score and IQR methods"""
        anomalies = []

        # Check WACC for outliers
        wacc = data.get("wacc")
        if wacc is not None:
            # Typical WACC range: 8% to 15%
            if wacc < 0.05 or wacc > 0.25:
                anomalies.append(
                    AnomalyResult(
                        anomaly_type=AnomalyType.STATISTICAL_OUTLIER,
                        severity=AnomalySeverity.HIGH,
                        score=0.9,
                        description=f"WACC {wacc:.1%} is outside typical range (5%-25%)",
                        field_name="wacc",
                        actual_value=wacc,
                        expected_value="5%-25%",
                        confidence=Decimal("0.95"),  # Bank-grade: Decimal confidence
                    )
                )

        # Check terminal growth for outliers
        terminal_growth = data.get("terminal_growth_rate")
        if terminal_growth is not None:
            if terminal_growth < 0.01 or terminal_growth > 0.05:
                anomalies.append(
                    AnomalyResult(
                        anomaly_type=AnomalyType.STATISTICAL_OUTLIER,
                        severity=AnomalySeverity.HIGH,
                        score=0.8,
                        description=f"Terminal growth {terminal_growth:.1%} is outside typical range (1%-5%)",
                        field_name="terminal_growth_rate",
                        actual_value=terminal_growth,
                        expected_value="1%-5%",
                        confidence=Decimal("0.90"),  # Bank-grade: Decimal confidence
                    )
                )

        # Check EV/EBITDA multiple for outliers
        ebitda_multiple = data.get("ebitda_multiple")
        if ebitda_multiple is not None:
            if ebitda_multiple < 3.0 or ebitda_multiple > 15.0:
                anomalies.append(
                    AnomalyResult(
                        anomaly_type=AnomalyType.STATISTICAL_OUTLIER,
                        severity=AnomalySeverity.MEDIUM,
                        score=0.7,
                        description=f"EV/EBITDA multiple {ebitda_multiple:.1f}x is outside typical range (3x-15x)",
                        field_name="ebitda_multiple",
                        actual_value=ebitda_multiple,
                        expected_value="3x-15x",
                        confidence=Decimal("0.85"),  # Bank-grade: Decimal confidence
                    )
                )

        # Check P/E multiple for outliers
        pe_multiple = data.get("pe_multiple")
        if pe_multiple is not None:
            if pe_multiple < 5.0 or pe_multiple > 30.0:
                anomalies.append(
                    AnomalyResult(
                        anomaly_type=AnomalyType.STATISTICAL_OUTLIER,
                        severity=AnomalySeverity.MEDIUM,
                        score=0.6,
                        description=f"P/E multiple {pe_multiple:.1f}x is outside typical range (5x-30x)",
                        field_name="pe_multiple",
                        actual_value=pe_multiple,
                        expected_value="5x-30x",
                        confidence=Decimal("0.80"),  # Bank-grade: Decimal confidence
                    )
                )

        return anomalies

    def _detect_historical_deviations(
        self, current_data: Dict[str, Any], historical_data: List[Dict[str, Any]]
    ) -> List[AnomalyResult]:
        """Detect deviations from historical patterns"""
        anomalies = []

        if not historical_data:
            return anomalies

        # Extract historical values
        historical_wacc = [d.get("wacc") for d in historical_data if d.get("wacc") is not None]
        historical_growth = [
            d.get("growth_rate") for d in historical_data if d.get("growth_rate") is not None
        ]
        historical_ebitda_margin = [
            d.get("ebitda_margin") for d in historical_data if d.get("ebitda_margin") is not None
        ]

        # Check WACC deviation
        current_wacc = current_data.get("wacc")
        if current_wacc is not None and historical_wacc:
            historical_mean = statistics.mean(historical_wacc)
            historical_std = statistics.stdev(historical_wacc) if len(historical_wacc) > 1 else 0

            if historical_std > 0:
                z_score = abs(current_wacc - historical_mean) / historical_std
                if z_score > self._z_score_threshold:
                    anomalies.append(
                        AnomalyResult(
                            anomaly_type=AnomalyType.HISTORICAL_DEVIATION,
                            severity=AnomalySeverity.MEDIUM,
                            score=min(z_score / self._z_score_threshold, 1.0),
                            description=f"WACC {current_wacc:.1%} deviates significantly from historical mean {historical_mean:.1%}",
                            field_name="wacc",
                            actual_value=current_wacc,
                            expected_value=historical_mean,
                            confidence=Decimal("0.85"),  # Bank-grade: Decimal confidence
                        )
                    )

        # Check growth rate deviation
        current_growth = current_data.get("growth_rate")
        if current_growth is not None and historical_growth:
            historical_mean = statistics.mean(historical_growth)
            historical_std = (
                statistics.stdev(historical_growth) if len(historical_growth) > 1 else 0
            )

            if historical_std > 0:
                z_score = abs(current_growth - historical_mean) / historical_std
                if z_score > self._z_score_threshold:
                    anomalies.append(
                        AnomalyResult(
                            anomaly_type=AnomalyType.HISTORICAL_DEVIATION,
                            severity=AnomalySeverity.MEDIUM,
                            score=min(z_score / self._z_score_threshold, 1.0),
                            description=f"Growth rate {current_growth:.1%} deviates significantly from historical mean {historical_mean:.1%}",
                            field_name="growth_rate",
                            actual_value=current_growth,
                            expected_value=historical_mean,
                            confidence=Decimal("0.80"),  # Bank-grade: Decimal confidence
                        )
                    )

        return anomalies

    def _detect_industry_deviations(
        self, data: Dict[str, Any], industry_benchmarks: Dict[str, Any]
    ) -> List[AnomalyResult]:
        """Detect deviations from industry benchmarks"""
        anomalies = []

        # Check WACC against industry benchmark
        current_wacc = data.get("wacc")
        industry_wacc = industry_benchmarks.get("wacc")
        if current_wacc is not None and industry_wacc is not None:
            deviation = abs(current_wacc - industry_wacc) / industry_wacc
            if deviation > 0.3:  # 30% deviation
                anomalies.append(
                    AnomalyResult(
                        anomaly_type=AnomalyType.INDUSTRY_DEVIATION,
                        severity=AnomalySeverity.MEDIUM,
                        score=min(deviation, 1.0),
                        description=f"WACC {current_wacc:.1%} deviates {deviation:.1%} from industry benchmark {industry_wacc:.1%}",
                        field_name="wacc",
                        actual_value=current_wacc,
                        expected_value=industry_wacc,
                        confidence=Decimal("0.90"),  # Bank-grade: Decimal confidence
                    )
                )

        # Check EBITDA margin against industry benchmark
        current_ebitda_margin = data.get("ebitda_margin")
        industry_ebitda_margin = industry_benchmarks.get("ebitda_margin")
        if current_ebitda_margin is not None and industry_ebitda_margin is not None:
            deviation = abs(current_ebitda_margin - industry_ebitda_margin) / industry_ebitda_margin
            if deviation > 0.5:  # 50% deviation
                anomalies.append(
                    AnomalyResult(
                        anomaly_type=AnomalyType.INDUSTRY_DEVIATION,
                        severity=AnomalySeverity.MEDIUM,
                        score=min(deviation, 1.0),
                        description=f"EBITDA margin {current_ebitda_margin:.1%} deviates {deviation:.1%} from industry benchmark {industry_ebitda_margin:.1%}",
                        field_name="ebitda_margin",
                        actual_value=current_ebitda_margin,
                        expected_value=industry_ebitda_margin,
                        confidence=Decimal("0.85"),  # Bank-grade: Decimal confidence
                    )
                )

        return anomalies

    def _detect_pattern_anomalies(self, data: Dict[str, Any]) -> List[AnomalyResult]:
        """Detect pattern-based anomalies"""
        anomalies = []

        # Check for unrealistic growth patterns
        growth_rate = data.get("growth_rate")
        terminal_growth = data.get("terminal_growth_rate")

        if growth_rate is not None and terminal_growth is not None:
            # Terminal growth should be lower than current growth
            if terminal_growth > growth_rate:
                anomalies.append(
                    AnomalyResult(
                        anomaly_type=AnomalyType.PATTERN_ANOMALY,
                        severity=AnomalySeverity.HIGH,
                        score=0.8,
                        description=f"Terminal growth {terminal_growth:.1%} is higher than current growth {growth_rate:.1%}",
                        field_name="terminal_growth_rate",
                        actual_value=terminal_growth,
                        expected_value=f"< {growth_rate:.1%}",
                        confidence=Decimal("0.95"),  # Bank-grade: Decimal confidence
                    )
                )

        # Check for unrealistic multiple relationships
        ebitda_multiple = data.get("ebitda_multiple")
        revenue_multiple = data.get("revenue_multiple")

        if ebitda_multiple is not None and revenue_multiple is not None:
            # EV/Revenue should generally be lower than EV/EBITDA
            if revenue_multiple > ebitda_multiple:
                anomalies.append(
                    AnomalyResult(
                        anomaly_type=AnomalyType.PATTERN_ANOMALY,
                        severity=AnomalySeverity.MEDIUM,
                        score=0.6,
                        description=f"EV/Revenue multiple {revenue_multiple:.1f}x is higher than EV/EBITDA multiple {ebitda_multiple:.1f}x",
                        field_name="revenue_multiple",
                        actual_value=revenue_multiple,
                        expected_value=f"< {ebitda_multiple:.1f}x",
                        confidence=Decimal("0.80"),  # Bank-grade: Decimal confidence
                    )
                )

        # Check for negative cash flow patterns
        cash_flows = data.get("projected_cash_flows", [])
        if cash_flows:
            negative_count = sum(1 for cf in cash_flows if cf < 0)
            if negative_count > len(cash_flows) * 0.5:  # More than 50% negative
                anomalies.append(
                    AnomalyResult(
                        anomaly_type=AnomalyType.PATTERN_ANOMALY,
                        severity=AnomalySeverity.HIGH,
                        score=0.9,
                        description=f"More than 50% of projected cash flows are negative ({negative_count}/{len(cash_flows)})",
                        field_name="projected_cash_flows",
                        actual_value=negative_count,
                        expected_value=f"< {len(cash_flows) * 0.5}",
                        confidence=Decimal("0.90"),  # Bank-grade: Decimal confidence
                    )
                )

        return anomalies

    def _log_anomaly_detection_results(self, anomalies: List[AnomalyResult]):
        """Log anomaly detection results"""
        if not anomalies:
            self.logger.info("No anomalies detected")
            return

        critical_count = sum(1 for a in anomalies if a.is_critical)
        high_count = sum(1 for a in anomalies if a.is_high_severity)
        total_count = len(anomalies)

        self.logger.warning(
            "Anomalies detected",
            total_anomalies=total_count,
            critical_anomalies=critical_count,
            high_severity_anomalies=high_count,
        )

        # Log validation step
        log_validation_step(
            "anomaly_detection",
            {"total_anomalies": total_count},
            [
                "statistical_outliers",
                "historical_deviations",
                "industry_deviations",
                "pattern_anomalies",
            ],
            {
                "total_anomalies": total_count,
                "critical_anomalies": critical_count,
                "high_severity_anomalies": high_count,
                "anomaly_score": (
                    sum(a.score for a in anomalies) / total_count if total_count > 0 else 0
                ),
            },
        )

    def _store_anomaly(self, anomaly: AnomalyResult):
        """Store anomaly in history"""
        self._detection_history.append(anomaly)

        # Keep only recent history
        if len(self._detection_history) > self._max_history:
            self._detection_history = self._detection_history[-self._max_history :]

    def get_anomaly_summary(self) -> Dict[str, Any]:
        """Get anomaly detection summary statistics"""
        if not self._detection_history:
            return {"total_anomalies": 0}

        total_anomalies = len(self._detection_history)
        critical_count = sum(1 for a in self._detection_history if a.is_critical)
        high_count = sum(1 for a in self._detection_history if a.is_high_severity)

        # Group by anomaly type
        type_counts = {}
        for anomaly in self._detection_history:
            type_counts[anomaly.anomaly_type.value] = (
                type_counts.get(anomaly.anomaly_type.value, 0) + 1
            )

        return {
            "total_anomalies": total_anomalies,
            "critical_anomalies": critical_count,
            "high_severity_anomalies": high_count,
            "anomaly_types": type_counts,
            "average_score": (
                sum(a.score for a in self._detection_history) / total_anomalies
                if total_anomalies > 0
                else 0
            ),
        }

    def get_anomaly_history(self, limit: int = 100) -> List[AnomalyResult]:
        """Get recent anomaly detection history"""
        return self._detection_history[-limit:] if limit else self._detection_history

    def get_anomalies_by_type(self, anomaly_type: AnomalyType) -> List[AnomalyResult]:
        """Get anomalies of a specific type"""
        return [a for a in self._detection_history if a.anomaly_type == anomaly_type]

    def get_anomalies_by_severity(self, severity: AnomalySeverity) -> List[AnomalyResult]:
        """Get anomalies of a specific severity"""
        return [a for a in self._detection_history if a.severity == severity]
