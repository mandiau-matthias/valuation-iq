"""
Report Data Validator

Provides comprehensive validation for report data with tiered validation levels
following Big 4 and McKinsey quality assurance standards.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, TypeAlias

from src.utils.exceptions import DataValidationError
from src.utils.logging import get_logger

JsonMap: TypeAlias = dict[str, object]


class ValidationLevel(Enum):
    """Validation severity levels"""

    CRITICAL = "critical"  # Stop generation - fatal errors
    WARNING = "warning"  # Log but continue - missing optional data
    INFO = "info"  # Audit trail - successful validations


@dataclass
class ValidationResult:
    """Result of a single validation check"""

    level: ValidationLevel
    field_path: str
    message: str
    value: object = None
    expected: Optional[str] = None


class ReportDataValidator:
    """
    Validates report data before template rendering.

    Implements tiered validation approach:
    - CRITICAL: Blocks report generation (missing core data, type errors)
    - WARNING: Logs issues but continues (missing optional fields)
    - INFO: Logs successful validations (audit trail)
    """

    def __init__(self):
        self.logger = get_logger(__name__)

    def validate_valuation_response(self, data: JsonMap) -> list[ValidationResult]:
        """
        Validate complete report data structure.

        Args:
            data: Complete template data dictionary

        Returns:
            List of ValidationResult objects

        Raises:
            TypeError: If data is not a dictionary
        """
        # Validate input type
        if not isinstance(data, dict):
            raise TypeError(f"Expected dict, got {type(data).__name__}")

        results = []

        # CRITICAL: Core valuation data
        results.extend(self._validate_core_valuation_data(data))

        # CRITICAL: Company identification
        results.extend(self._validate_company_data(data))

        # WARNING: Optional sections
        results.extend(self._validate_optional_sections(data))

        # INFO: Data completeness audit
        results.extend(self._audit_data_completeness(data))

        return results

    def validate_section_data(self, section: str, data: JsonMap) -> list[ValidationResult]:
        """
        Validate data for a specific report section.

        Args:
            section: Section name (e.g., 'executive_summary', 'financial_analysis')
            data: Section-specific data

        Returns:
            List of ValidationResult objects
        """
        results = []

        if section == "executive_summary":
            results.extend(self._validate_executive_summary(data))
        elif section == "financial_analysis":
            results.extend(self._validate_financial_analysis(data))
        elif section == "valuation_methodologies":
            results.extend(self._validate_valuation_methodologies(data))
        elif section == "valuation_conclusion":
            results.extend(self._validate_valuation_conclusion(data))
        elif section == "company_overview":
            results.extend(self._validate_company_overview(data))
        elif section == "description_of_assignment":
            results.extend(self._validate_description_of_assignment(data))
        elif section == "information_sources":
            results.extend(self._validate_information_sources(data))
        elif section == "appendices":
            results.extend(self._validate_appendices(data))

        return results

    def validate_field_presence(
        self, field_path: str, data: JsonMap, required: bool = True
    ) -> ValidationResult:
        """
        Validate presence of a specific field.

        Args:
            field_path: Dot-notation path to field (e.g., 'valuation_range.mid')
            data: Data dictionary
            required: Whether field is required (CRITICAL) or optional (WARNING)

        Returns:
            ValidationResult
        """
        keys = field_path.split(".")
        current = data

        try:
            for key in keys:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    # Field not found
                    level = ValidationLevel.CRITICAL if required else ValidationLevel.WARNING
                    return ValidationResult(
                        level=level,
                        field_path=field_path,
                        message=f"Field missing: {field_path}",
                        value=None,
                        expected="Present value",
                    )

            # Field found
            if current is None:
                level = ValidationLevel.CRITICAL if required else ValidationLevel.WARNING
                return ValidationResult(
                    level=level,
                    field_path=field_path,
                    message=f"Field is None: {field_path}",
                    value=None,
                    expected="Non-null value",
                )

            # Success
            return ValidationResult(
                level=ValidationLevel.INFO,
                field_path=field_path,
                message=f"Field present: {field_path}",
                value=current,
                expected=None,
            )

        except (KeyError, AttributeError, TypeError) as e:
            level = ValidationLevel.CRITICAL if required else ValidationLevel.WARNING
            return ValidationResult(
                level=level,
                field_path=field_path,
                message=f"Data structure error accessing field: {field_path} - {str(e)}",
                value=None,
                expected="Accessible value",
            )
        except DataValidationError as e:
            level = ValidationLevel.CRITICAL if required else ValidationLevel.WARNING
            return ValidationResult(
                level=level,
                field_path=field_path,
                message=f"Unexpected error accessing field: {field_path} - {str(e)}",
                value=None,
                expected="Accessible value",
            )

    def log_validation_results(self, results: list[ValidationResult], context: str = ""):
        """
        Log validation results with appropriate severity levels.

        Args:
            results: List of ValidationResult objects
            context: Context description for logging
        """
        if not results:
            self.logger.info(f"Validation ({context}): No results")
            return

        # Count by level
        critical = [r for r in results if r.level == ValidationLevel.CRITICAL]
        warnings = [r for r in results if r.level == ValidationLevel.WARNING]
        info = [r for r in results if r.level == ValidationLevel.INFO]

        # Log summary
        self.logger.info(f"Validation Results ({context}):")
        self.logger.info(f"  - CRITICAL: {len(critical)}")
        self.logger.info(f"  - WARNING: {len(warnings)}")
        self.logger.info(f"  - INFO: {len(info)}")

        # Log critical failures
        if critical:
            self.logger.error(f"  CRITICAL FAILURES ({len(critical)}):")
            for result in critical:
                self.logger.error(f"    ✗ {result.field_path}: {result.message}")

        # Log warnings
        if warnings:
            self.logger.warning(f"  WARNINGS ({len(warnings)}):")
            for result in warnings:
                self.logger.warning(f"    ⚠ {result.field_path}: {result.message}")

        # Log info (only first 10 for brevity)
        if info:
            self.logger.info(f"  INFO ({len(info)} validations passed)")
            for result in info[:10]:
                self.logger.info(f"    ✓ {result.field_path}")
            if len(info) > 10:
                self.logger.info(f"    ... and {len(info) - 10} more")

    # ========== Private Validation Methods ==========

    def _validate_core_valuation_data(self, data: JsonMap) -> list[ValidationResult]:
        """Validate core valuation data (CRITICAL)"""
        results = []

        # Valuation range — accept both legacy format (valuation_range dict) and
        # new MainReportAggregator format (valuation / valuation_low / valuation_high)
        if "valuation_range" in data and data["valuation_range"]:
            results.append(self.validate_field_presence("valuation_range.low", data, required=True))
            results.append(self.validate_field_presence("valuation_range.mid", data, required=True))
            results.append(
                self.validate_field_presence("valuation_range.high", data, required=True)
            )
        elif data.get("valuation") is not None:
            results.append(
                ValidationResult(
                    level=ValidationLevel.INFO,
                    field_path="valuation_range",
                    message="valuation_range present via new-format fields (valuation/valuation_low/valuation_high)",
                    value=data.get("valuation"),
                    expected=None,
                )
            )
        else:
            results.append(
                ValidationResult(
                    level=ValidationLevel.CRITICAL,
                    field_path="valuation_range",
                    message="Field missing: valuation_range",
                    value=None,
                    expected="Present value",
                )
            )

        # Methodology — accept 'methodology' (legacy) or 'valuation_methodology' (new aggregator)
        if data.get("methodology") is not None:
            results.append(self.validate_field_presence("methodology", data, required=True))
        elif data.get("valuation_methodology") is not None:
            results.append(
                ValidationResult(
                    level=ValidationLevel.INFO,
                    field_path="methodology",
                    message="methodology present via new-format field (valuation_methodology)",
                    value=data.get("valuation_methodology"),
                    expected=None,
                )
            )
        else:
            results.append(
                ValidationResult(
                    level=ValidationLevel.CRITICAL,
                    field_path="methodology",
                    message="Field missing: methodology",
                    value=None,
                    expected="Present value",
                )
            )

        # Confidence score — accept 'confidence_score' (legacy) or 'overall_confidence_score' (new aggregator)
        if data.get("confidence_score") is not None:
            results.append(self.validate_field_presence("confidence_score", data, required=True))
        elif data.get("overall_confidence_score") is not None:
            results.append(
                ValidationResult(
                    level=ValidationLevel.INFO,
                    field_path="confidence_score",
                    message="confidence_score present via new-format field (overall_confidence_score)",
                    value=data.get("overall_confidence_score"),
                    expected=None,
                )
            )
        else:
            results.append(
                ValidationResult(
                    level=ValidationLevel.CRITICAL,
                    field_path="confidence_score",
                    message="Field missing: confidence_score",
                    value=None,
                    expected="Present value",
                )
            )

        return results

    def _validate_company_data(self, data: JsonMap) -> list[ValidationResult]:
        """Validate company identification data (CRITICAL)"""
        results = []

        # Company name (required)
        results.append(self.validate_field_presence("company_name", data, required=True))

        # Industry (required)
        results.append(self.validate_field_presence("industry", data, required=True))

        # Valuation date (required)
        results.append(self.validate_field_presence("valuation_date", data, required=True))

        return results

    def _validate_optional_sections(self, data: JsonMap) -> list[ValidationResult]:
        """Validate optional sections (WARNING if missing)"""
        results = []

        # Optional sections
        optional_sections = [
            "executive_summary",
            "company_overview",
            "financial_analysis",
            "valuation_methodologies",
            "valuation_conclusion",
            "appendices",
        ]

        for section in optional_sections:
            results.append(self.validate_field_presence(section, data, required=False))

        return results

    def _audit_data_completeness(self, data: JsonMap) -> list[ValidationResult]:
        """Audit overall data completeness (INFO)"""
        results = []

        # Count top-level keys
        total_keys = len(data.keys())
        non_null_keys = sum(1 for v in data.values() if v is not None)

        results.append(
            ValidationResult(
                level=ValidationLevel.INFO,
                field_path="_root",
                message=f"Data completeness: {non_null_keys}/{total_keys} non-null top-level keys",
                value=non_null_keys,
                expected=str(total_keys),
            )
        )

        return results

    def _validate_executive_summary(self, data: JsonMap) -> list[ValidationResult]:
        """Validate executive summary data"""
        results = []

        if "response" in data:
            results.append(
                ValidationResult(
                    level=ValidationLevel.INFO,
                    field_path="executive_summary.response",
                    message="Response object present",
                    value=True,
                )
            )

        if "request" in data:
            results.append(
                ValidationResult(
                    level=ValidationLevel.INFO,
                    field_path="executive_summary.request",
                    message="Request object present",
                    value=True,
                )
            )

        if "valuation_range" in data:
            results.append(
                ValidationResult(
                    level=ValidationLevel.INFO,
                    field_path="executive_summary.valuation_range",
                    message="Valuation range present",
                    value=True,
                )
            )

        return results

    def _validate_financial_analysis(self, data: JsonMap) -> list[ValidationResult]:
        """Validate financial analysis data"""
        results = []

        if "response" in data:
            results.append(
                ValidationResult(
                    level=ValidationLevel.INFO,
                    field_path="financial_analysis.response",
                    message="Response object present",
                    value=True,
                )
            )

        return results

    def _validate_valuation_methodologies(self, data: JsonMap) -> list[ValidationResult]:
        """Validate valuation methodologies data"""
        results = []

        if "response" in data:
            results.append(
                ValidationResult(
                    level=ValidationLevel.INFO,
                    field_path="valuation_methodologies.response",
                    message="Response object present",
                    value=True,
                )
            )

        return results

    def _validate_valuation_conclusion(self, data: JsonMap) -> list[ValidationResult]:
        """Validate valuation conclusion data"""
        results = []

        if "response" in data:
            results.append(
                ValidationResult(
                    level=ValidationLevel.INFO,
                    field_path="valuation_conclusion.response",
                    message="Response object present",
                    value=True,
                )
            )

        if "valuation_range" in data:
            results.append(
                ValidationResult(
                    level=ValidationLevel.INFO,
                    field_path="valuation_conclusion.valuation_range",
                    message="Valuation range present",
                    value=True,
                )
            )

        return results

    def _validate_company_overview(self, data: JsonMap) -> list[ValidationResult]:
        """Validate company overview data"""
        results = []

        if "response" in data:
            results.append(
                ValidationResult(
                    level=ValidationLevel.INFO,
                    field_path="company_overview.response",
                    message="Response object present",
                    value=True,
                )
            )

        return results

    def _validate_description_of_assignment(self, data: JsonMap) -> list[ValidationResult]:
        """Validate description of assignment data"""
        results = []

        if "response" in data:
            results.append(
                ValidationResult(
                    level=ValidationLevel.INFO,
                    field_path="description_of_assignment.response",
                    message="Response object present",
                    value=True,
                )
            )

        return results

    def _validate_information_sources(self, data: JsonMap) -> list[ValidationResult]:
        """Validate information sources data"""
        results = []

        if "response" in data:
            results.append(
                ValidationResult(
                    level=ValidationLevel.INFO,
                    field_path="information_sources.response",
                    message="Response object present",
                    value=True,
                )
            )

        return results

    def _validate_appendices(self, data: JsonMap) -> list[ValidationResult]:
        """Validate appendices data"""
        results = []

        if "response" in data:
            results.append(
                ValidationResult(
                    level=ValidationLevel.INFO,
                    field_path="appendices.response",
                    message="Response object present",
                    value=True,
                )
            )

        return results
