"""
Validation Builder

Validates and sanitizes ValuationResponse objects.
Handles NaN/Infinity replacement and data quality checks.
"""

import math
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from src.api.schemas import ValuationResponse
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.valuation_logger import ValuationLogger


class ValidationBuilder:
    """
    Builder for response validation and sanitization.

    Responsibilities:
    - Validate ValuationResponse data
    - Sanitize NaN/Infinity values
    - Ensure data quality
    """

    def __init__(self, logger: Optional[ValuationLogger] = None):
        """
        Initialize validation builder.

        Args:
            logger: Optional logger instance
        """
        self.logger = logger or ValuationLogger(self.__class__.__name__)
        self.logger.debug("✅ ValidationBuilder initialized")

    def sanitize_valuation_response(
        self, response: ValuationResponse, nan_fields: List[str]
    ) -> ValuationResponse:
        """
        Sanitize ValuationResponse by replacing NaN/Infinity values with safe defaults.

        Args:
            response: ValuationResponse object with potential NaN/Infinity values
            nan_fields: List of field paths containing NaN/Infinity

        Returns:
            Sanitized ValuationResponse object
        """
        try:
            # Convert to dict for manipulation
            if hasattr(response, "model_dump"):
                response_dict = response.model_dump()
            elif hasattr(response, "dict"):
                response_dict = response.dict()
            else:
                self.logger.warning("Cannot sanitize response: not a Pydantic model")
                return response

            # Replace NaN/Infinity in critical fields with safe defaults
            defaults = {
                "equity_value_low": Decimal("10000.0"),
                "equity_value_mid": Decimal("100000.0"),
                "equity_value_high": Decimal("200000.0"),
                "equity_value": Decimal("100000.0"),
                "enterprise_value": Decimal("110000.0"),
                "confidence_score": 50,  # Default to medium confidence
            }

            def sanitize_value(value: Any, field_path: str) -> Any:
                """Recursively sanitize NaN/Infinity values"""
                if isinstance(value, Decimal):
                    if value.is_nan() or value.is_infinite():
                        field_name = field_path.split(".")[-1] if "." in field_path else field_path
                        default = defaults.get(field_name, Decimal("0.0"))
                        self.logger.warning(
                            f"⚠️ Replacing Decimal NaN/Infinity in {field_path} with default {default}",
                            extra={"field_path": field_path, "default": default},
                        )
                        return default
                    return value
                if isinstance(value, (int, float)):
                    if math.isnan(value) or math.isinf(value):
                        # Try to find a default for this field
                        field_name = field_path.split(".")[-1] if "." in field_path else field_path
                        default = defaults.get(field_name, Decimal("0.0"))
                        self.logger.warning(
                            f"⚠️ Replacing NaN/Infinity in {field_path} with default {default}",
                            extra={
                                "field_path": field_path,
                                "original_value": value,
                                "default": default,
                            },
                        )
                        return default
                elif isinstance(value, dict):
                    return {
                        k: sanitize_value(v, f"{field_path}.{k}" if field_path else k)
                        for k, v in value.items()
                    }
                elif isinstance(value, list):
                    return [
                        sanitize_value(item, f"{field_path}[{i}]") for i, item in enumerate(value)
                    ]
                return value

            # Sanitize the response dict
            sanitized_dict = sanitize_value(response_dict, "")

            # Recreate ValuationResponse from sanitized dict
            try:
                sanitized_response = ValuationResponse.model_validate(sanitized_dict)
                self.logger.info(
                    "✅ ValuationResponse sanitized successfully",
                    extra={"nan_fields_count": len(nan_fields)},
                )
                return sanitized_response
            except ValidationError as ve:
                self.logger.error(
                    "❌ Failed to recreate ValuationResponse after sanitization",
                    extra={"error": str(ve), "nan_fields": nan_fields},
                    exc_info=True,
                )
                # Return original response if sanitization fails
                return response

        except Exception as e:
            self.logger.error(
                "❌ Error during response sanitization",
                extra={"error": str(e), "nan_fields": nan_fields},
                exc_info=True,
            )
            return response

    def sanitize_for_json_serialization(self, obj: Any, field_path: str = "root") -> Any:
        """
        Recursively sanitize objects to ensure they are JSON-serializable.

        Args:
            obj: Object to sanitize
            field_path: Current field path for logging

        Returns:
            Sanitized object
        """
        if obj is None:
            return None

        if isinstance(obj, Decimal):
            if obj.is_nan() or obj.is_infinite():
                self.logger.warning(
                    f"⚠️ Replacing Decimal NaN/Infinity in {field_path} with 0",
                    extra={"field_path": field_path},
                )
                return Decimal("0.0")
            return obj

        if isinstance(obj, (int, float)):
            if math.isnan(obj) or math.isinf(obj):
                self.logger.warning(
                    f"⚠️ Replacing NaN/Infinity in {field_path} with 0",
                    extra={"field_path": field_path, "original_value": obj},
                )
                return Decimal("0.0")
            return obj

        if isinstance(obj, bool):
            return obj

        if isinstance(obj, str):
            return obj

        if isinstance(obj, dict):
            return {
                k: self.sanitize_for_json_serialization(v, f"{field_path}.{k}" if field_path else k)
                for k, v in obj.items()
            }

        if isinstance(obj, list):
            return [
                self.sanitize_for_json_serialization(item, f"{field_path}[{i}]")
                for i, item in enumerate(obj)
            ]

        # Check if it's a Pydantic model instance (has model_dump method)
        if hasattr(obj, 'model_dump'):
            try:
                return self.sanitize_for_json_serialization(
                    obj.model_dump(), f"{field_path}.model_dump()"
                )
            except Exception:
                pass
        
        # Check if it's a Pydantic v1 model (has dict method)
        if hasattr(obj, 'dict') and callable(getattr(obj, 'dict', None)):
            try:
                return self.sanitize_for_json_serialization(
                    obj.dict(), f"{field_path}.dict()"
                )
            except Exception:
                pass

        # For other types, convert to string
        try:
            return str(obj)
        except Exception:
            return None

    def validate_response_data(self, response_dict: Dict[str, Any]) -> List[str]:
        """
        Validate response data and return list of validation errors.

        Args:
            response_dict: Response dictionary to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Validate required fields
        required_fields = ["valuation_id", "company_name", "equity_value_mid"]
        for field in required_fields:
            if field not in response_dict or response_dict[field] is None:
                errors.append(f"Missing required field: {field}")

        # Validate equity values are positive
        if "equity_value_mid" in response_dict:
            if response_dict["equity_value_mid"] <= 0:
                errors.append("equity_value_mid must be positive")

        # Validate confidence score is in valid range
        if "confidence_score" in response_dict:
            score = response_dict["confidence_score"]
            if not isinstance(score, int) or score < 0 or score > 100:
                errors.append(f"confidence_score must be integer between 0-100, got {score}")

        return errors
