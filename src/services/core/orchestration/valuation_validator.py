"""
Valuation Validator — DEPRECATED / LEGACY

.. deprecated::
    Production validation uses
    ``src.api.routes.valuation.orchestration.builders.validation_builder``
    and ``src.api.routes.valuation.valuation_validators``.
    This module belongs to the legacy ``services/core/orchestration/``
    stack and should not receive new features.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from src.utils.logging import get_logger
from src.utils.exceptions import (
    ValuationEngineError,
    ValidationError,
    DataValidationError,
    CalculationError,
)
from .orchestrator_types import ValuationResult
from src.validation.validation_engine import ValidationEngine
from src.validation.anomaly_detector import AnomalyDetector

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    """Result of validation check"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]


class ValuationValidator:
    """
    Validates valuation results and detects anomalies.
    
    Single Responsibility: Validation and anomaly detection only.
    """

    def __init__(
        self,
        validation_engine: Optional[ValidationEngine] = None,
        anomaly_detector: Optional[AnomalyDetector] = None,
    ):
        """
        Initialize validator with injected dependencies
        
        Args:
            validation_engine: Validation engine instance
            anomaly_detector: Anomaly detector instance
        """
        self.validation_engine = validation_engine or ValidationEngine()
        self.anomaly_detector = anomaly_detector or AnomalyDetector()
        self.logger = logger

    def validate_comprehensive_valuation(self, result: ValuationResult) -> ValidationResult:
        """
        Validate comprehensive valuation result
        
        Args:
            result: Valuation result to validate
            
        Returns:
            Validation result with errors and warnings
        """
        try:
            validation_result = self.validation_engine.validate_comprehensive_valuation(result)
            
            return ValidationResult(
                is_valid=validation_result.is_valid,
                errors=validation_result.errors if hasattr(validation_result, 'errors') else [],
                warnings=validation_result.warnings if hasattr(validation_result, 'warnings') else [],
            )
        except (ValidationError, DataValidationError) as e:
            # Re-raise validation errors
            self.logger.error(f"Validation failed: {e}", exc_info=True)
            raise
        except ValuationEngineError as e:
            # Re-raise valuation engine errors
            self.logger.error(f"Valuation engine error during validation: {e}", exc_info=True)
            raise
        except (AttributeError, TypeError, KeyError) as e:
            # Handle data structure errors gracefully
            self.logger.error(f"Validation failed due to data structure error: {e}", exc_info=True)
            return ValidationResult(
                is_valid=False,
                errors=[f"Data structure error: {str(e)}"],
                warnings=[],
            )

    def detect_anomalies(self, result: ValuationResult) -> List[Dict[str, Any]]:
        """
        Detect anomalies in valuation result
        
        Args:
            result: Valuation result to check
            
        Returns:
            List of detected anomalies
        """
        try:
            anomalies = self.anomaly_detector.detect_anomalies(result)
            return anomalies if anomalies else []
        except (ValidationError, DataValidationError, CalculationError) as e:
            # Re-raise specific errors
            self.logger.error(f"Anomaly detection failed: {e}", exc_info=True)
            raise
        except ValuationEngineError as e:
            # Re-raise valuation engine errors
            self.logger.error(f"Valuation engine error during anomaly detection: {e}", exc_info=True)
            raise
        except (AttributeError, TypeError, KeyError) as e:
            # Handle data structure errors gracefully
            self.logger.error(f"Anomaly detection failed due to data structure error: {e}", exc_info=True)
            return []

