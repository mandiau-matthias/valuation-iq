"""
Bank-Grade Validation Utilities for Step 11 Synthesis Coordinators

Provides comprehensive validation functions following bank-grade standards:
- Input validation at boundaries
- Data integrity checks
- Decimal type validation
- Range validation
- Null/None handling
"""

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Union

from src.errors import DataQualityError, ValidationError
from src.utils.logging import get_logger

logger = get_logger(__name__)


class BankGradeValidator:
    """
    Bank-grade validation utilities for coordinators.
    
    Provides comprehensive validation following bank-grade standards:
    - Zero tolerance for calculation errors
    - Full audit trails
    - Complete data integrity checks
    """

    @staticmethod
    def validate_decimal(
        value: Any,
        field_name: str,
        allow_none: bool = False,
        min_value: Optional[Decimal] = None,
        max_value: Optional[Decimal] = None,
    ) -> Optional[Decimal]:
        """
        Validate that value is a Decimal (bank-grade requirement).
        
        Args:
            value: Value to validate
            field_name: Name of field for error messages
            allow_none: Whether None is acceptable
            min_value: Minimum allowed value
            max_value: Maximum allowed value
            
        Returns:
            Decimal value or None if allow_none=True
            
        Raises:
            ValidationError: If value is not Decimal or violates constraints
        """
        if value is None:
            if allow_none:
                return None
            raise ValidationError(f"{field_name} cannot be None")
        
        # Check if already Decimal
        if isinstance(value, Decimal):
            decimal_value = value
        elif isinstance(value, (int, float, str)):
            try:
                decimal_value = Decimal(str(value))
            except (InvalidOperation, ValueError, TypeError) as e:
                raise ValidationError(
                    f"{field_name} must be a valid Decimal, got {type(value).__name__}: {value}"
                ) from e
        else:
            raise ValidationError(
                f"{field_name} must be Decimal, got {type(value).__name__}"
            )
        
        # Validate range
        if min_value is not None and decimal_value < min_value:
            raise ValidationError(
                f"{field_name} ({decimal_value}) is below minimum ({min_value})"
            )
        
        if max_value is not None and decimal_value > max_value:
            raise ValidationError(
                f"{field_name} ({decimal_value}) is above maximum ({max_value})"
            )
        
        return decimal_value

    @staticmethod
    def validate_step_result(
        result: Any,
        step_number: int,
        required_fields: Optional[List[str]] = None,
    ) -> None:
        """
        Validate step result structure (bank-grade data integrity check).
        
        Args:
            result: Step result to validate
            step_number: Expected step number
            required_fields: List of required fields in result.result
            
        Raises:
            ValidationError: If result structure is invalid
        """
        if result is None:
            raise ValidationError(f"Step {step_number} result cannot be None")
        
        # Check required attributes
        if not hasattr(result, "step_number"):
            raise ValidationError(f"Step {step_number} result missing step_number attribute")
        
        if not hasattr(result, "status"):
            raise ValidationError(f"Step {step_number} result missing status attribute")
        
        if not hasattr(result, "result"):
            raise ValidationError(f"Step {step_number} result missing result attribute")
        
        if not hasattr(result, "metadata"):
            raise ValidationError(f"Step {step_number} result missing metadata attribute")
        
        # Validate step number matches
        if result.step_number != step_number:
            logger.warning(
                f"Step number mismatch: expected {step_number}, got {result.step_number}",
                extra={"expected_step": step_number, "actual_step": result.step_number},
            )
        
        # Validate result is dict
        if not isinstance(result.result, dict):
            raise ValidationError(
                f"Step {step_number} result.result must be dict, got {type(result.result).__name__}"
            )
        
        # Validate required fields
        if required_fields:
            missing_fields = [field for field in required_fields if field not in result.result]
            if missing_fields:
                logger.warning(
                    f"Step {step_number} missing required fields: {missing_fields}",
                    extra={
                        "step_number": step_number,
                        "missing_fields": missing_fields,
                        "available_fields": list(result.result.keys()),
                    },
                )

    @staticmethod
    def validate_previous_results(
        previous_results: Dict[int, Any],
        required_steps: Optional[List[int]] = None,
    ) -> None:
        """
        Validate previous_results dictionary structure (bank-grade data integrity).
        
        Args:
            previous_results: Dictionary of step results
            required_steps: List of step numbers that must be present
            
        Raises:
            ValidationError: If structure is invalid
        """
        if not isinstance(previous_results, dict):
            raise ValidationError(
                f"previous_results must be dict, got {type(previous_results).__name__}"
            )
        
        # Validate all keys are numeric (int or float) - modular system uses fractional steps (2.5, 4.5)
        invalid_keys = [k for k in previous_results.keys() if not isinstance(k, (int, float))]
        if invalid_keys:
            raise ValidationError(
                f"previous_results keys must be integers or numeric step ids (e.g. 2.5, 4.5), got invalid keys: {invalid_keys}"
            )
        
        # Validate required steps are present
        if required_steps:
            missing_steps = [step for step in required_steps if step not in previous_results]
            if missing_steps:
                logger.warning(
                    f"Missing required steps: {missing_steps}",
                    extra={
                        "required_steps": required_steps,
                        "missing_steps": missing_steps,
                        "available_steps": list(previous_results.keys()),
                    },
                )

    @staticmethod
    def validate_range(
        low: Decimal,
        mid: Decimal,
        high: Decimal,
        field_prefix: str = "value",
    ) -> None:
        """
        Validate that low <= mid <= high (bank-grade range validation).
        
        Args:
            low: Low value
            mid: Mid value
            high: High value
            field_prefix: Prefix for field names in error messages
            
        Raises:
            ValidationError: If range ordering is invalid
        """
        if low > mid:
            raise ValidationError(
                f"{field_prefix}_low ({low}) must be <= {field_prefix}_mid ({mid})"
            )
        
        if mid > high:
            raise ValidationError(
                f"{field_prefix}_mid ({mid}) must be <= {field_prefix}_high ({high})"
            )
        
        if low > high:
            raise ValidationError(
                f"{field_prefix}_low ({low}) must be <= {field_prefix}_high ({high})"
            )

    @staticmethod
    def validate_percentage(
        value: Decimal,
        field_name: str,
        allow_negative: bool = True,
        min_value: Optional[Decimal] = None,
        max_value: Optional[Decimal] = None,
    ) -> Decimal:
        """
        Validate percentage value (bank-grade precision).
        
        Args:
            value: Percentage value (as decimal, e.g., 0.15 for 15%)
            field_name: Name of field for error messages
            allow_negative: Whether negative percentages are allowed
            min_value: Minimum allowed value
            max_value: Maximum allowed value
            
        Returns:
            Validated Decimal percentage
            
        Raises:
            ValidationError: If percentage is invalid
        """
        validated = BankGradeValidator.validate_decimal(value, field_name)
        
        if validated is None:
            raise ValidationError(f"{field_name} cannot be None")
        
        # Validate percentage range (typically -1.0 to 1.0 for -100% to +100%)
        if not allow_negative and validated < 0:
            raise ValidationError(f"{field_name} cannot be negative, got {validated}")
        
        if min_value is not None and validated < min_value:
            raise ValidationError(
                f"{field_name} ({validated}) is below minimum ({min_value})"
            )
        
        if max_value is not None and validated > max_value:
            raise ValidationError(
                f"{field_name} ({validated}) is above maximum ({max_value})"
            )
        
        return validated

    @staticmethod
    def ensure_decimal(
        value: Any,
        field_name: str,
        default: Optional[Decimal] = None,
    ) -> Optional[Decimal]:
        """
        Ensure value is Decimal, converting if necessary (bank-grade type safety).
        
        Args:
            value: Value to convert
            field_name: Name of field for logging
            default: Default value if conversion fails (None means None is acceptable)
            
        Returns:
            Decimal value, or None if value is None and default is None (for optional fields)
            
        Raises:
            ValidationError: If conversion fails and default is not None (required field)
        """
        if value is None:
            # If default is None, return None (optional field)
            # If default is not None, return the default (required field with fallback)
            return default
        
        if isinstance(value, Decimal):
            return value
        
        if isinstance(value, (int, float, str)):
            try:
                return Decimal(str(value))
            except (InvalidOperation, ValueError, TypeError) as e:
                if default is not None:
                    logger.warning(
                        f"Failed to convert {field_name} to Decimal, using default",
                        extra={"field_name": field_name, "value": value, "error": str(e)},
                    )
                    return default
                raise ValidationError(
                    f"{field_name} must be convertible to Decimal, got {type(value).__name__}: {value}"
                ) from e
        
        if default is not None:
            logger.warning(
                f"Cannot convert {field_name} to Decimal, using default",
                extra={"field_name": field_name, "value_type": type(value).__name__},
            )
            return default
        
        raise ValidationError(
            f"{field_name} must be Decimal or convertible, got {type(value).__name__}"
        )

    @staticmethod
    def log_calculation_provenance(
        calculation_name: str,
        inputs: Dict[str, Any],
        outputs: Dict[str, Any],
        step_number: int,
    ) -> None:
        """
        Log calculation provenance for audit trail (bank-grade transparency).
        
        Args:
            calculation_name: Name of calculation
            inputs: Input values
            outputs: Output values
            step_number: Step number
        """
        # DEBUG: per-sub-calculation provenance dump (fires ~4× per Step 11
        # transparency build). The Step 11 EXECUTION COMPLETE log carries the
        # aggregate provenance summary.
        logger.debug(
            f"📊 Calculation Provenance: {calculation_name}",
            extra={
                "step_number": step_number,
                "calculation_name": calculation_name,
                "inputs": {
                    k: str(v) if isinstance(v, Decimal) else v
                    for k, v in inputs.items()
                },
                "outputs": {
                    k: str(v) if isinstance(v, Decimal) else v
                    for k, v in outputs.items()
                },
            },
        )

