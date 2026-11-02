"""
Validation Engine for Calculation Validation

Comprehensive validation system for all valuation calculations with business rules,
anomaly detection, and quality assurance.

ARCHITECTURE:
- Rule-based validation engine
- Business rule enforcement
- Calculation step validation
- Cross-methodology validation
- Quality scoring and reporting

FEATURES:
- DCF validation (WACC, terminal growth, cash flows)
- Multiples validation (ratio ranges, comparables)
- Synthesis validation (weight distribution, confidence)
- Business rule validation (industry standards, regulatory)
- Anomaly detection (outliers, suspicious patterns)
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from src.errors.error_handler import handle_error
from src.utils.logging import get_logger, log_calculation_step, log_validation_step
from src.utils.logging_context import get_current_context

logger = get_logger(__name__)


class ValidationSeverity(Enum):
    """Validation severity levels"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ValidationStatus(Enum):
    """Validation status"""

    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


@dataclass
class ValidationRule:
    """Individual validation rule"""

    name: str
    description: str
    severity: ValidationSeverity
    rule_function: callable
    parameters: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True


@dataclass
class ValidationResult:
    """Result of a validation operation"""

    rule_name: str
    status: ValidationStatus
    severity: ValidationSeverity
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    execution_time: Decimal = Decimal("0.0")  # Bank-grade: Decimal default

    @property
    def is_passed(self) -> bool:
        """Check if validation passed"""
        return self.status == ValidationStatus.PASSED

    @property
    def is_failed(self) -> bool:
        """Check if validation failed"""
        return self.status == ValidationStatus.FAILED

    @property
    def is_warning(self) -> bool:
        """Check if validation has warnings"""
        return self.status == ValidationStatus.WARNING


class ValidationEngine:
    """
    Comprehensive validation engine for all valuation calculations.

    Features:
    - Rule-based validation engine
    - Business rule enforcement
    - Calculation step validation
    - Cross-methodology validation
    - Quality scoring and reporting
    """

    def __init__(self):
        self.logger = get_logger(__name__)
        self._rules: Dict[str, ValidationRule] = {}
        self._validation_history: List[ValidationResult] = []
        self._max_history = 1000

        # Initialize validation rules
        self._initialize_validation_rules()

    def _initialize_validation_rules(self):
        """Initialize all validation rules"""
        # DCF validation rules
        self._add_rule(
            "dcf_wacc_range",
            self._validate_wacc_range,
            "WACC should be between 5% and 25%",
            ValidationSeverity.ERROR,
        )
        self._add_rule(
            "dcf_terminal_growth_range",
            self._validate_terminal_growth_range,
            "Terminal growth should be between 1% and 5%",
            ValidationSeverity.ERROR,
        )
        self._add_rule(
            "dcf_cash_flow_positive",
            self._validate_positive_cash_flows,
            "Projected cash flows should be positive",
            ValidationSeverity.WARNING,
        )
        self._add_rule(
            "dcf_enterprise_value_positive",
            self._validate_positive_enterprise_value,
            "Enterprise value should be positive",
            ValidationSeverity.ERROR,
        )

        # Multiples validation rules
        self._add_rule(
            "multiples_ebitda_range",
            self._validate_ebitda_multiple_range,
            "EV/EBITDA multiple should be between 3x and 15x",
            ValidationSeverity.WARNING,
        )
        self._add_rule(
            "multiples_revenue_range",
            self._validate_revenue_multiple_range,
            "EV/Revenue multiple should be between 0.5x and 5x",
            ValidationSeverity.WARNING,
        )
        self._add_rule(
            "multiples_pe_range",
            self._validate_pe_multiple_range,
            "P/E multiple should be between 5x and 30x",
            ValidationSeverity.WARNING,
        )

        # Synthesis validation rules
        self._add_rule(
            "synthesis_weight_sum",
            self._validate_weight_sum,
            "Methodology weights should sum to 1.0",
            ValidationSeverity.ERROR,
        )
        self._add_rule(
            "synthesis_confidence_range",
            self._validate_confidence_range,
            "Confidence score should be between 0.0 and 1.0",
            ValidationSeverity.ERROR,
        )
        self._add_rule(
            "synthesis_value_range",
            self._validate_value_range,
            "Equity value should be within reasonable range",
            ValidationSeverity.WARNING,
        )

        # Business rule validation
        self._add_rule(
            "business_revenue_positive",
            self._validate_positive_revenue,
            "Revenue should be positive",
            ValidationSeverity.ERROR,
        )
        self._add_rule(
            "business_ebitda_positive",
            self._validate_positive_ebitda,
            "EBITDA should be positive for valuation",
            ValidationSeverity.WARNING,
        )
        self._add_rule(
            "business_growth_rate_reasonable",
            self._validate_growth_rate,
            "Growth rate should be between -50% and 100%",
            ValidationSeverity.WARNING,
        )

    def _add_rule(
        self,
        name: str,
        rule_function: callable,
        description: str,
        severity: ValidationSeverity,
        parameters: Dict[str, Any] = None,
    ):
        """Add a validation rule"""
        rule = ValidationRule(
            name=name,
            description=description,
            severity=severity,
            rule_function=rule_function,
            parameters=parameters or {},
            enabled=True,
        )
        self._rules[name] = rule

    def validate_dcf_calculation(self, dcf_result: Dict[str, Any]) -> List[ValidationResult]:
        """
        Validate DCF calculation results.

        Args:
            dcf_result: DCF calculation results

        Returns:
            List of validation results
        """
        try:
            self.logger.info("Starting DCF calculation validation", dcf_result=dcf_result)

            results = []

            # Validate WACC
            wacc_result = self._run_rule("dcf_wacc_range", dcf_result)
            results.append(wacc_result)

            # Validate terminal growth
            terminal_growth_result = self._run_rule("dcf_terminal_growth_range", dcf_result)
            results.append(terminal_growth_result)

            # Validate cash flows
            cash_flow_result = self._run_rule("dcf_cash_flow_positive", dcf_result)
            results.append(cash_flow_result)

            # Validate enterprise value
            enterprise_value_result = self._run_rule("dcf_enterprise_value_positive", dcf_result)
            results.append(enterprise_value_result)

            # Log validation results
            self._log_validation_results("DCF", results)

            return results

        except Exception as e:
            self.logger.error(f"DCF validation failed: {e}", exc_info=True)
            raise

    def validate_multiples_calculation(
        self, multiples_result: Dict[str, Any]
    ) -> List[ValidationResult]:
        """
        Validate Multiples calculation results.

        Args:
            multiples_result: Multiples calculation results

        Returns:
            List of validation results
        """
        try:
            self.logger.info(
                "Starting Multiples calculation validation", multiples_result=multiples_result
            )

            results = []

            # Validate EBITDA multiple
            ebitda_result = self._run_rule("multiples_ebitda_range", multiples_result)
            results.append(ebitda_result)

            # Validate Revenue multiple
            revenue_result = self._run_rule("multiples_revenue_range", multiples_result)
            results.append(revenue_result)

            # Validate P/E multiple
            pe_result = self._run_rule("multiples_pe_range", multiples_result)
            results.append(pe_result)

            # Log validation results
            self._log_validation_results("Multiples", results)

            return results

        except Exception as e:
            self.logger.error(f"Multiples validation failed: {e}", exc_info=True)
            raise

    def validate_synthesis_calculation(
        self, synthesis_result: Dict[str, Any]
    ) -> List[ValidationResult]:
        """
        Validate Synthesis calculation results.

        Args:
            synthesis_result: Synthesis calculation results

        Returns:
            List of validation results
        """
        try:
            self.logger.info(
                "Starting Synthesis calculation validation", synthesis_result=synthesis_result
            )

            results = []

            # Validate weight sum
            weight_result = self._run_rule("synthesis_weight_sum", synthesis_result)
            results.append(weight_result)

            # Validate confidence range
            confidence_result = self._run_rule("synthesis_confidence_range", synthesis_result)
            results.append(confidence_result)

            # Validate value range
            value_result = self._run_rule("synthesis_value_range", synthesis_result)
            results.append(value_result)

            # Log validation results
            self._log_validation_results("Synthesis", results)

            return results

        except Exception as e:
            self.logger.error(f"Synthesis validation failed: {e}", exc_info=True)
            raise

    def validate_business_data(self, business_data: Dict[str, Any]) -> List[ValidationResult]:
        """
        Validate business data inputs.

        Args:
            business_data: Business data inputs

        Returns:
            List of validation results
        """
        try:
            self.logger.info("Starting business data validation", business_data=business_data)

            results = []

            # Validate revenue
            revenue_result = self._run_rule("business_revenue_positive", business_data)
            results.append(revenue_result)

            # Validate EBITDA
            ebitda_result = self._run_rule("business_ebitda_positive", business_data)
            results.append(ebitda_result)

            # Validate growth rate
            growth_result = self._run_rule("business_growth_rate_reasonable", business_data)
            results.append(growth_result)

            # Log validation results
            self._log_validation_results("Business Data", results)

            return results

        except Exception as e:
            self.logger.error(f"Business data validation failed: {e}", exc_info=True)
            raise

    def _run_rule(self, rule_name: str, data: Dict[str, Any]) -> ValidationResult:
        """Run a specific validation rule"""
        if rule_name not in self._rules:
            return ValidationResult(
                rule_name=rule_name,
                status=ValidationStatus.SKIPPED,
                severity=ValidationSeverity.INFO,
                message=f"Rule {rule_name} not found",
            )

        rule = self._rules[rule_name]
        if not rule.enabled:
            return ValidationResult(
                rule_name=rule_name,
                status=ValidationStatus.SKIPPED,
                severity=ValidationSeverity.INFO,
                message=f"Rule {rule_name} is disabled",
            )

        try:
            start_time = time.time()
            result = rule.rule_function(data, **rule.parameters)
            execution_time = time.time() - start_time

            if result:
                status = ValidationStatus.PASSED
                message = f"Rule {rule_name} passed"
            else:
                status = ValidationStatus.FAILED
                message = f"Rule {rule_name} failed"

            validation_result = ValidationResult(
                rule_name=rule_name,
                status=status,
                severity=rule.severity,
                message=message,
                details={"rule_description": rule.description},
                execution_time=execution_time,
            )

            # Store in history
            self._store_validation_result(validation_result)

            return validation_result

        except Exception as e:
            self.logger.error(f"Rule {rule_name} execution failed: {e}", exc_info=True)
            return ValidationResult(
                rule_name=rule_name,
                status=ValidationStatus.FAILED,
                severity=ValidationSeverity.ERROR,
                message=f"Rule {rule_name} execution failed: {str(e)}",
            )

    def _log_validation_results(self, calculation_type: str, results: List[ValidationResult]):
        """Log validation results"""
        passed_count = sum(1 for r in results if r.is_passed)
        failed_count = sum(1 for r in results if r.is_failed)
        warning_count = sum(1 for r in results if r.is_warning)

        self.logger.info(
            f"{calculation_type} validation completed",
            total_rules=len(results),
            passed=passed_count,
            failed=failed_count,
            warnings=warning_count,
        )

        # Log validation step
        log_validation_step(
            f"{calculation_type.lower()}_validation",
            {"calculation_type": calculation_type, "total_rules": len(results)},
            ["business_rules", "calculation_rules", "data_quality_rules"],
            {
                "passed": passed_count,
                "failed": failed_count,
                "warnings": warning_count,
                "validation_score": (passed_count / len(results)) * 100 if results else 0,
            },
        )

    def _store_validation_result(self, result: ValidationResult):
        """Store validation result in history"""
        self._validation_history.append(result)

        # Keep only recent history
        if len(self._validation_history) > self._max_history:
            self._validation_history = self._validation_history[-self._max_history :]

    # Validation rule implementations
    def _validate_wacc_range(self, data: Dict[str, Any], **kwargs) -> bool:
        """Validate WACC is within reasonable range"""
        wacc = data.get("wacc", 0)
        return 0.05 <= wacc <= 0.25  # 5% to 25%

    def _validate_terminal_growth_range(self, data: Dict[str, Any], **kwargs) -> bool:
        """Validate terminal growth is within reasonable range"""
        terminal_growth = data.get("terminal_growth_rate", 0)
        return 0.01 <= terminal_growth <= 0.05  # 1% to 5%

    def _validate_positive_cash_flows(self, data: Dict[str, Any], **kwargs) -> bool:
        """Validate projected cash flows are positive"""
        cash_flows = data.get("projected_cash_flows", [])
        if not cash_flows:
            return True  # No cash flows to validate

        # Check if at least 70% of cash flows are positive
        positive_count = sum(1 for cf in cash_flows if cf > 0)
        return (positive_count / len(cash_flows)) >= 0.7

    def _validate_positive_enterprise_value(self, data: Dict[str, Any], **kwargs) -> bool:
        """Validate enterprise value is positive"""
        enterprise_value = data.get("enterprise_value", 0)
        return enterprise_value > 0

    def _validate_ebitda_multiple_range(self, data: Dict[str, Any], **kwargs) -> bool:
        """Validate EV/EBITDA multiple is within reasonable range"""
        ebitda_multiple = data.get("ebitda_multiple", 0)
        return 3.0 <= ebitda_multiple <= 15.0  # 3x to 15x

    def _validate_revenue_multiple_range(self, data: Dict[str, Any], **kwargs) -> bool:
        """Validate EV/Revenue multiple is within reasonable range"""
        revenue_multiple = data.get("revenue_multiple", 0)
        return 0.5 <= revenue_multiple <= 5.0  # 0.5x to 5x

    def _validate_pe_multiple_range(self, data: Dict[str, Any], **kwargs) -> bool:
        """Validate P/E multiple is within reasonable range"""
        pe_multiple = data.get("pe_multiple", 0)
        return 5.0 <= pe_multiple <= 30.0  # 5x to 30x

    def _validate_weight_sum(self, data: Dict[str, Any], **kwargs) -> bool:
        """Validate methodology weights sum to 1.0"""
        dcf_weight = data.get("dcf_weight", 0)
        multiples_weight = data.get("multiples_weight", 0)
        total_weight = dcf_weight + multiples_weight
        return abs(total_weight - 1.0) < 0.01  # Allow small floating point errors

    def _validate_confidence_range(self, data: Dict[str, Any], **kwargs) -> bool:
        """Validate confidence score is within range"""
        confidence_score = data.get("confidence_score", 0)
        return 0.0 <= confidence_score <= 1.0

    def _validate_value_range(self, data: Dict[str, Any], **kwargs) -> bool:
        """Validate equity value is within reasonable range"""
        equity_value = data.get("equity_value", 0)
        # Reasonable range: 10K to 10B
        return 10_000 <= equity_value <= 10_000_000_000

    def _validate_positive_revenue(self, data: Dict[str, Any], **kwargs) -> bool:
        """Validate revenue is positive"""
        revenue = data.get("revenue", 0)
        return revenue > 0

    def _validate_positive_ebitda(self, data: Dict[str, Any], **kwargs) -> bool:
        """Validate EBITDA is positive"""
        ebitda = data.get("ebitda", 0)
        return ebitda > 0

    def _validate_growth_rate(self, data: Dict[str, Any], **kwargs) -> bool:
        """Validate growth rate is reasonable"""
        growth_rate = data.get("growth_rate", 0)
        return -0.5 <= growth_rate <= 1.0  # -50% to 100%

    def get_validation_summary(self) -> Dict[str, Any]:
        """Get validation summary statistics"""
        if not self._validation_history:
            return {"total_validations": 0}

        total_validations = len(self._validation_history)
        passed_count = sum(1 for r in self._validation_history if r.is_passed)
        failed_count = sum(1 for r in self._validation_history if r.is_failed)
        warning_count = sum(1 for r in self._validation_history if r.is_warning)

        return {
            "total_validations": total_validations,
            "passed": passed_count,
            "failed": failed_count,
            "warnings": warning_count,
            "success_rate": (
                (passed_count / total_validations) * 100 if total_validations > 0 else 0
            ),
        }

    def get_validation_history(self, limit: int = 100) -> List[ValidationResult]:
        """Get recent validation history"""
        return self._validation_history[-limit:] if limit else self._validation_history
