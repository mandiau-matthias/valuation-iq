"""
Step 2 Validators

Input validation, range validation, and type validation for Step 2.
Bank-grade validation at all boundaries.
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from src.utils.exceptions import (
    DataValidationError,
    InvalidMultipleError,
    MissingDataError,
)

from ..constants import Step2ValidationThresholds


class Step2InputValidator:
    """Validates inputs at Step 2 boundaries."""
    
    @staticmethod
    def validate_step1_result(step1_result: Dict[str, Any]) -> None:
        """
        Validate Step 1 result has required fields.
        
        Raises:
            MissingDataError: If required fields are missing
            DataValidationError: If data is invalid
        """
        if not step1_result:
            raise MissingDataError(
                "Step 1 result is required",
                missing_fields=["step1_result"],
            )
        
        required_fields = ["revenue"]
        missing_fields = [field for field in required_fields if field not in step1_result]
        
        if missing_fields:
            raise MissingDataError(
                f"Step 1 result missing required fields: {missing_fields}",
                missing_fields=missing_fields,
            )
        
        # Validate revenue
        revenue = step1_result.get("revenue")
        if revenue is None:
            raise DataValidationError("Revenue cannot be None")
        
        try:
            revenue_decimal = Decimal(str(revenue))
            if revenue_decimal < Step2ValidationThresholds.MIN_REVENUE:
                raise DataValidationError(
                    f"Revenue {revenue_decimal} below minimum {Step2ValidationThresholds.MIN_REVENUE}"
                )
            if revenue_decimal > Step2ValidationThresholds.MAX_REVENUE:
                raise DataValidationError(
                    f"Revenue {revenue_decimal} above maximum {Step2ValidationThresholds.MAX_REVENUE}"
                )
        except (ValueError, TypeError) as e:
            raise DataValidationError(f"Invalid revenue value: {revenue}") from e
    
    @staticmethod
    def validate_multiples_data(multiples_data: Dict[str, Any]) -> None:
        """
        Validate multiples data structure and values.
        
        Raises:
            MissingDataError: If multiples_data is missing
            DataValidationError: If structure is invalid
            InvalidMultipleError: If values are out of range
        """
        if not multiples_data:
            raise MissingDataError("multiples_data is required")
        
        if not isinstance(multiples_data, dict):
            raise DataValidationError(f"multiples_data must be dict, got {type(multiples_data)}")
        
        # Validate multiples if present
        if "ev_ebitda" in multiples_data and multiples_data["ev_ebitda"] is not None:
            Step2RangeValidator.validate_ev_ebitda(multiples_data["ev_ebitda"])
        
        if "ev_revenue" in multiples_data and multiples_data["ev_revenue"] is not None:
            Step2RangeValidator.validate_ev_revenue(multiples_data["ev_revenue"])
        
        if "pe_ratio" in multiples_data and multiples_data["pe_ratio"] is not None:
            Step2RangeValidator.validate_pe_ratio(multiples_data["pe_ratio"])


class Step2RangeValidator:
    """Validates ranges for Step 2 calculations."""
    
    @staticmethod
    def validate_ev_ebitda(value: Any) -> None:
        """
        Validate EV/EBITDA multiple is within realistic range.
        
        Raises:
            InvalidMultipleError: If value is out of range
        """
        try:
            decimal_value = Decimal(str(value))
            if not (Step2ValidationThresholds.MIN_EV_EBITDA <= decimal_value <= Step2ValidationThresholds.MAX_EV_EBITDA):
                raise InvalidMultipleError(
                    f"EV/EBITDA multiple {decimal_value} out of valid range "
                    f"[{Step2ValidationThresholds.MIN_EV_EBITDA}, {Step2ValidationThresholds.MAX_EV_EBITDA}]"
                )
        except (ValueError, TypeError, ArithmeticError) as e:
            raise InvalidMultipleError(f"Invalid EV/EBITDA value: {value}") from e
    
    @staticmethod
    def validate_ev_revenue(value: Any) -> None:
        """
        Validate EV/Revenue multiple is within realistic range.
        
        Raises:
            InvalidMultipleError: If value is out of range
        """
        try:
            decimal_value = Decimal(str(value))
            if not (Step2ValidationThresholds.MIN_EV_REVENUE <= decimal_value <= Step2ValidationThresholds.MAX_EV_REVENUE):
                raise InvalidMultipleError(
                    f"EV/Revenue multiple {decimal_value} out of valid range "
                    f"[{Step2ValidationThresholds.MIN_EV_REVENUE}, {Step2ValidationThresholds.MAX_EV_REVENUE}]"
                )
        except (ValueError, TypeError, ArithmeticError) as e:
            raise InvalidMultipleError(f"Invalid EV/Revenue value: {value}") from e
    
    @staticmethod
    def validate_pe_ratio(value: Any) -> None:
        """
        Validate PE ratio is within realistic range.
        
        Raises:
            InvalidMultipleError: If value is out of range
        """
        try:
            decimal_value = Decimal(str(value))
            if not (Step2ValidationThresholds.MIN_PE_RATIO <= decimal_value <= Step2ValidationThresholds.MAX_PE_RATIO):
                raise InvalidMultipleError(
                    f"PE ratio {decimal_value} out of valid range "
                    f"[{Step2ValidationThresholds.MIN_PE_RATIO}, {Step2ValidationThresholds.MAX_PE_RATIO}]"
                )
        except (ValueError, TypeError, ArithmeticError) as e:
            raise InvalidMultipleError(f"Invalid PE ratio value: {value}") from e

