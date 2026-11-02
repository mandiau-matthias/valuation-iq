from src.utils.exceptions import DataValidationError

"""
Response Validator for Comprehensive Valuation

Validates ValuationResponse objects with comprehensive checks including
nested model validation, JSON serialization validation, timeout protection,
and NaN/Infinity sanitization.
"""

import asyncio
import json
import time
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from src.api.routes.valuation.orchestration.executors.comprehensive.response_nested_validation import (
    validate_nested_model,
)
from src.api.schemas import (
    DCFValuationResponse,
    FinancialMetricsResponse,
    MultiplesValuationResponse,
    ValuationResponse,
)
from src.domain.transparency import TransparencyData
from src.utils.valuation_logger import ValuationLogger


class ResponseValidator:
    """
    Validates ValuationResponse objects.

    Responsibilities:
    - Validate critical fields
    - Validate nested models
    - Validate JSON serialization
    - Create ValuationResponse with timeout protection
    - Sanitize NaN/Infinity values
    """

    def __init__(
        self,
        validator,  # Existing ValuationValidator
        validation_builder,  # Existing ValidationBuilder
        logger: Optional[ValuationLogger] = None,
    ):
        """
        Initialize response validator.

        Args:
            validator: Existing ValuationValidator instance
            validation_builder: Existing ValidationBuilder instance
            logger: Optional logger instance
        """
        self.validator = validator
        self.validation_builder = validation_builder
        self.logger = logger or ValuationLogger(self.__class__.__name__)

    def validate_critical_fields(self, response_dict: Dict[str, Any]) -> List[str]:
        """
        Validate critical fields in response dictionary.

        Args:
            response_dict: Response dictionary to validate

        Returns:
            List of validation errors (empty if valid)
        """
        validation_errors = []

        if not response_dict.get("transparency"):
            validation_errors.append("transparency is missing")

        if not response_dict.get("key_value_drivers"):
            validation_errors.append("key_value_drivers is empty")

        if not response_dict.get("risk_factors"):
            validation_errors.append("risk_factors is empty")

        if not response_dict.get("methodology"):
            validation_errors.append("methodology is missing")

        multiples_val = response_dict.get("multiples_valuation")
        if multiples_val:
            if not getattr(multiples_val, "revenue_multiple", None):
                validation_errors.append("revenue_multiple is None")
            if not getattr(multiples_val, "ebitda_multiple", None):
                validation_errors.append("ebitda_multiple is None")

        if validation_errors:
            self.logger.error(
                "❌ VALIDATION FAILED: Critical fields missing/invalid",
                extra={"validation_errors": validation_errors},
            )
        else:
            self.logger.debug(
                "✅ Response validation passed",
                extra={
                    "has_transparency": bool(response_dict.get("transparency")),
                    "value_drivers_count": len(response_dict.get("key_value_drivers", [])),
                    "risk_factors_count": len(response_dict.get("risk_factors", [])),
                    "has_methodology": bool(response_dict.get("methodology")),
                },
            )

        return validation_errors

    def validate_nested_models(
        self, response_dict: Dict[str, Any], correlation_id: str
    ) -> List[str]:
        """
        Validate nested models individually.

        Args:
            response_dict: Response dictionary
            correlation_id: Correlation ID

        Returns:
            List of problematic fields
        """
        problematic_fields = []

        # Log nested field sizes before validation
        self.logger.debug(
            "Pre-validation field check",
            extra={
                "has_transparency": bool(response_dict.get("transparency")),
                "has_financial_metrics": bool(response_dict.get("financial_metrics")),
                "has_multiples_valuation": bool(response_dict.get("multiples_valuation")),
                "has_dcf_valuation": bool(response_dict.get("dcf_valuation")),
                "transparency_type": (
                    type(response_dict.get("transparency")).__name__
                    if response_dict.get("transparency")
                    else None
                ),
                "financial_metrics_type": (
                    type(response_dict.get("financial_metrics")).__name__
                    if response_dict.get("financial_metrics")
                    else None
                ),
                "multiples_valuation_type": (
                    type(response_dict.get("multiples_valuation")).__name__
                    if response_dict.get("multiples_valuation")
                    else None
                ),
                "correlation_id": correlation_id,
            },
        )

        for field_name, model_type in (
            ("financial_metrics", FinancialMetricsResponse),
            ("multiples_valuation", MultiplesValuationResponse),
            ("dcf_valuation", DCFValuationResponse),
            ("transparency", TransparencyData),
        ):
            issue = validate_nested_model(
                field_name=field_name,
                value=response_dict.get(field_name),
                model_type=model_type,
            )
            if issue is None:
                continue
            problematic_fields.append(issue.message)
            self.logger.warning(
                f"{field_name} validation issue: {issue.error}",
                exc_info=True,
            )

        if problematic_fields:
            self.logger.warning(
                "Some nested fields have validation issues",
                extra={"problematic_fields": problematic_fields, "correlation_id": correlation_id},
            )

        return problematic_fields

    async def create_valuation_response(
        self, response_dict: Dict[str, Any], correlation_id: str, valuation_id: str
    ) -> ValuationResponse:
        """
        Create ValuationResponse with timeout protection.

        Args:
            response_dict: Response dictionary
            correlation_id: Correlation ID
            valuation_id: Valuation ID

        Returns:
            ValuationResponse object

        Raises:
            TimeoutError: If validation times out
            ValidationError: If validation fails
        """
        VALIDATION_TIMEOUT_SECONDS = 10.0  # 10 second timeout for validation

        # Log response_dict size and structure before validation
        response_dict_size = len(str(response_dict))
        response_dict_keys_count = len(response_dict.keys())
        self.logger.debug(
            "Pre-validation response_dict diagnostics",
            extra={
                "response_dict_size_chars": response_dict_size,
                "response_dict_keys_count": response_dict_keys_count,
                "has_transparency": bool(response_dict.get("transparency")),
                "has_financial_metrics": bool(response_dict.get("financial_metrics")),
                "has_multiples_valuation": bool(response_dict.get("multiples_valuation")),
                "has_dcf_valuation": bool(response_dict.get("dcf_valuation")),
                "correlation_id": correlation_id,
            },
        )

        validation_start_time = time.time()
        problematic_fields = []

        def create_response():
            """Synchronous function to create ValuationResponse"""
            nonlocal response_dict
            func_start_time = time.time()

            # Validate JSON serialization before creating response
            serialization_errors = []
            try:
                # Use default=str to allow date/decimal objects which Pydantic handles fine
                json.dumps(response_dict, default=str)
            except (TypeError, ValueError) as serialization_error:
                serialization_errors.append(str(serialization_error))
                self.logger.error(
                    "❌ CRITICAL: response_dict is not JSON-serializable before ValuationResponse creation",
                    extra={
                        "error": str(serialization_error),
                        "error_type": type(serialization_error).__name__,
                        "correlation_id": correlation_id,
                        "response_dict_keys": (
                            list(response_dict.keys()) if isinstance(response_dict, dict) else None
                        ),
                    },
                    exc_info=True,
                )
                # Try to sanitize response_dict before proceeding
                try:
                    response_dict_sanitized = (
                        self.validation_builder.sanitize_for_json_serialization(
                            response_dict, "response_dict"
                        )
                    )
                    json.dumps(response_dict_sanitized)
                    response_dict = response_dict_sanitized
                    self.logger.warning(
                        "⚠️ Sanitized response_dict to make it JSON-serializable",
                        extra={
                            "correlation_id": correlation_id,
                            "original_error": (
                                serialization_errors[0] if serialization_errors else None
                            ),
                        },
                    )
                except Exception as sanitization_error:
                    self.logger.error(
                        "❌ CRITICAL: Failed to sanitize response_dict for JSON serialization",
                        extra={
                            "sanitization_error": str(sanitization_error),
                            "original_serialization_error": (
                                serialization_errors[0] if serialization_errors else None
                            ),
                            "correlation_id": correlation_id,
                        },
                        exc_info=True,
                    )
                    raise ValueError(
                        f"Response dict is not JSON-serializable: {serialization_errors[0] if serialization_errors else 'Unknown error'}"
                    ) from sanitization_error

            try:
                validate_start = time.time()
                response = ValuationResponse.model_validate(response_dict)
                validate_duration = time.time() - validate_start
                self.logger.debug(f"model_validate() succeeded in {validate_duration:.3f}s")
                return response
            except ValidationError as ve:
                self.logger.error(
                    "❌ model_validate() failed, trying **response_dict fallback",
                    extra={
                        "error": str(ve),
                        "error_count": len(ve.errors()) if hasattr(ve, "errors") else None,
                        "correlation_id": correlation_id,
                    },
                    exc_info=True,
                )
                try:
                    fallback_start = time.time()
                    response = ValuationResponse(**response_dict)
                    fallback_duration = time.time() - fallback_start
                    self.logger.warning(
                        f"**response_dict fallback succeeded in {fallback_duration:.3f}s",
                        extra={"correlation_id": correlation_id},
                    )
                    return response
                except Exception as ve2:
                    self.logger.error(
                        "❌ Both model_validate() and **response_dict failed",
                        extra={
                            "first_error": str(ve),
                            "second_error": str(ve2),
                            "correlation_id": correlation_id,
                            "response_dict_keys": (
                                list(response_dict.keys())
                                if isinstance(response_dict, dict)
                                else None
                            ),
                        },
                        exc_info=True,
                    )
                    raise

        executor_start_time = time.time()

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(create_response), timeout=VALIDATION_TIMEOUT_SECONDS
            )

            # Validate response for NaN/Infinity values
            nan_fields = self.validator.validate_valuation_response(response)
            if nan_fields:
                self.logger.error(
                    "❌ CRITICAL: ValuationResponse contains NaN/Infinity values",
                    extra={
                        "nan_fields": nan_fields,
                        "correlation_id": correlation_id,
                        "valuation_id": valuation_id,
                    },
                )
                response = self.validation_builder.sanitize_valuation_response(response, nan_fields)

            return response

        except asyncio.TimeoutError:
            executor_duration = time.time() - executor_start_time
            validation_duration = time.time() - validation_start_time
            error_msg = f"ValuationResponse validation timed out after {VALIDATION_TIMEOUT_SECONDS}s (executor: {executor_duration:.2f}s, total: {validation_duration:.2f}s)"
            self.logger.error(
                "❌ ValuationResponse validation timeout",
                extra={
                    "timeout_seconds": VALIDATION_TIMEOUT_SECONDS,
                    "executor_duration": executor_duration,
                    "actual_duration": validation_duration,
                    "problematic_fields": problematic_fields,
                    "correlation_id": correlation_id,
                    "response_dict_keys": list(response_dict.keys()),
                    "response_dict_size": len(str(response_dict)),
                },
            )

            try:
                direct_timeout = 3.0
                direct_start = time.time()
                response = await asyncio.wait_for(
                    asyncio.to_thread(lambda: ValuationResponse.model_validate(response_dict)),
                    timeout=direct_timeout,
                )
                direct_duration = time.time() - direct_start
                self.logger.warning(
                    "Direct validation fallback succeeded after executor timeout",
                    extra={"direct_duration": direct_duration, "correlation_id": correlation_id},
                )
                return response
            except (ValidationError, DataValidationError, Exception) as direct_error:
                self.logger.error(
                    "❌ Direct validation fallback failed after timeout",
                    extra={
                        "error": str(direct_error),
                        "error_type": type(direct_error).__name__,
                        "correlation_id": correlation_id,
                    },
                    exc_info=True,
                )
                try:
                    fallback_dict = response_dict.copy()
                    if problematic_fields:
                        for field_name in [
                            "transparency",
                            "financial_metrics",
                            "multiples_valuation",
                            "dcf_valuation",
                        ]:
                            if any(field_name in pf for pf in problematic_fields):
                                fallback_dict[field_name] = None

                    fallback_start = time.time()
                    response = await asyncio.wait_for(
                        asyncio.to_thread(lambda: ValuationResponse.model_validate(fallback_dict)),
                        timeout=3.0,
                    )
                    fallback_duration = time.time() - fallback_start
                    self.logger.warning(
                        "Created fallback response without problematic fields",
                        extra={
                            "removed_fields": [
                                f
                                for f in [
                                    "transparency",
                                    "financial_metrics",
                                    "multiples_valuation",
                                    "dcf_valuation",
                                ]
                                if f not in fallback_dict or fallback_dict[f] is None
                            ],
                            "correlation_id": correlation_id,
                        },
                    )
                    return response
                except (ValidationError, Exception) as fallback_error:
                    self.logger.error(
                        "All fallback mechanisms failed",
                        extra={
                            "fallback_error": str(fallback_error),
                            "fallback_error_type": type(fallback_error).__name__,
                            "correlation_id": correlation_id,
                        },
                        exc_info=True,
                    )
                    raise TimeoutError(error_msg) from fallback_error

        except (
            ValidationError,
            DataValidationError,
            ValueError,
            TypeError,
            Exception,
        ) as validation_error:
            executor_duration = (
                time.time() - executor_start_time if "executor_start_time" in locals() else None
            )
            validation_duration = time.time() - validation_start_time
            error_msg = str(validation_error)
            error_type = type(validation_error).__name__
            self.logger.error(
                "❌ ValuationResponse validation error",
                extra={
                    "error": error_msg,
                    "error_type": error_type,
                    "executor_duration": executor_duration,
                    "validation_duration": validation_duration,
                    "problematic_fields": problematic_fields,
                    "correlation_id": correlation_id,
                    "response_dict_size": (
                        response_dict_size if "response_dict_size" in locals() else None
                    ),
                },
                exc_info=True,
            )
            raise
