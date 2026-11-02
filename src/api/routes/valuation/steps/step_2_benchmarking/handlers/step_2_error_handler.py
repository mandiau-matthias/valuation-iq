"""
Step 2 Error Handler

Handles error scenarios and fallback logic for Step 2.
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from src.api.routes.valuation.benchmark_contract_utils import as_mapping as _as_mapping
from src.api.routes.valuation.benchmark_contract_utils import (
    extract_resolved_benchmark_contract as _resolved_benchmark_contract,
)
from src.api.routes.valuation.benchmark_contract_utils import (
    request_allows_untrusted_multiples_fallback as _request_allows_untrusted_multiples_fallback,
)
from src.api.routes.valuation.triage.business_type_triage import (
    BusinessTypeCategory,
    BusinessTypeTriageEngine,
)
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.valuation_logger import ValuationLogger

from ...base_step import StepOutput, StepStatus
from ..services import Step2RecoveryService


def _request_business_type_id(request: Any) -> Optional[str]:
    business_type_id = getattr(request, "business_type_id", None)
    if isinstance(business_type_id, str) and business_type_id.strip():
        return business_type_id.strip()
    return None


def _fallback_recovery_context(request: Any, correlation_id: Optional[str]) -> Dict[str, Any]:
    business_type_id = _request_business_type_id(request)
    return {
        "correlation_id": correlation_id,
        "business_type_id": business_type_id,
        "business_category": getattr(request, "business_category", None),
        "industry": getattr(request, "industry", None),
        "allow_untrusted_multiples_fallback": _request_allows_untrusted_multiples_fallback(request),
        "requires_trusted_benchmark": (
            business_type_id is not None
            and not _request_allows_untrusted_multiples_fallback(request)
        ),
    }


class Step2ErrorHandler:
    """Handles error scenarios and fallback logic."""

    def __init__(
        self,
        industry_benchmark_collector,
        business_type_triage: BusinessTypeTriageEngine,
        step_name: str,
        logger: ValuationLogger,
    ):
        """
        Initialize the error handler.

        Args:
            industry_benchmark_collector: Industry benchmark collector instance
            business_type_triage: Business type triage engine instance
            step_name: Step name for StepOutput
            logger: Logger instance
        """
        self.industry_benchmark_collector = industry_benchmark_collector
        self.business_type_triage = business_type_triage
        self.step_name = step_name
        self.logger = logger

        # Initialize recovery service
        self.recovery_service = Step2RecoveryService(logger)

    def _fail_closed_output(
        self,
        reason: str,
        request: Any,
        correlation_id: Optional[str] = None,
        exception: Optional[Exception] = None,
    ) -> StepOutput:
        """Return a failed Step 2 output instead of publishing silent fallback multiples."""
        self.logger.error(
            "Step 2 fallback refused: no resolved benchmark contract or explicit fallback consent",
            extra={
                "step_number": 2,
                "reason": reason,
                "correlation_id": correlation_id,
                "business_type_id": _request_business_type_id(request),
                "allow_untrusted_multiples_fallback": _request_allows_untrusted_multiples_fallback(
                    request
                ),
                "exception_type": type(exception).__name__ if exception else None,
                "exception_message": str(exception) if exception else None,
            },
        )
        return StepOutput(
            step_number=2,
            step_name=self.step_name,
            status=StepStatus.FAILED,
            result={},
            metadata={
                "fallback_applied": False,
                "fail_closed": True,
                "reason": reason,
                "requires_benchmark_contract": True,
                "allow_untrusted_multiples_fallback": False,
            },
            error=(
                "Resolved benchmark contract required for Step 2 multiples. "
                "Set allow_untrusted_multiples_fallback=true only for a disclosed fallback."
            ),
        )

    def handle_step_1_missing(
        self,
        step1_result: Optional[Dict[str, Any]],
        request: Any,
        correlation_id: Optional[str] = None,
    ) -> Optional[StepOutput]:
        """
        Handle missing or invalid Step 1 data.

        Args:
            step1_result: Step 1 result dictionary (may be None)
            request: The valuation request
            correlation_id: Correlation ID for logging

        Returns:
            StepOutput with fallback multiples if Step 1 is missing/invalid, None otherwise
        """
        if step1_result and step1_result.get("revenue") and step1_result.get("revenue", 0) > 0:
            return None  # Step 1 data is valid, no fallback needed

        self.logger.warning(
            "⚠️ Step 2: Step 1 data missing or invalid, calculating early fallback multiples",
            extra={
                "step_number": 2,
                "step_1_available": step1_result is not None,
                "step_1_has_revenue": (
                    step1_result.get("revenue") is not None if step1_result else False
                ),
                "step_1_revenue": step1_result.get("revenue") if step1_result else None,
                "correlation_id": correlation_id,
                "fallback_reason": "Step 1 data missing or invalid revenue",
            },
        )

        if not _request_allows_untrusted_multiples_fallback(request):
            return self._fail_closed_output(
                "step_1_missing_or_invalid",
                request,
                correlation_id,
            )

        # Calculate fallback multiples
        fallback_multiples = self.calculate_fallback_multiples(request)
        if not fallback_multiples:
            return None

        fallback_result = self._build_fallback_result(
            fallback_multiples, "Step 1 data missing or invalid"
        )

        return StepOutput(
            step_number=2,
            step_name=self.step_name,
            status=StepStatus.COMPLETED,
            result=fallback_result,
            metadata={
                "fallback_applied": True,
                "fallback_reason": "Step 1 data missing or invalid revenue",
                "recovery_method": "early_fallback_from_request",
                "business_category": fallback_multiples.get("business_category"),
                "industry": fallback_multiples.get("industry"),
                "business_type_id": fallback_multiples.get("business_type_id"),
            },
            error="Step 1 data missing or invalid, using calculated fallback multiples",
        )

    def handle_step_1_not_available(
        self, request: Any, correlation_id: Optional[str] = None
    ) -> StepOutput:
        """
        Handle Step 1 results not being available.

        Args:
            request: The valuation request
            correlation_id: Correlation ID for logging

        Returns:
            StepOutput with fallback multiples
        """
        self.logger.warning(
            "⚠️ Step 2: Step 1 results not available, calculating proper fallback multiples",
            extra={
                "step_number": 2,
                "correlation_id": correlation_id,
                "fallback_reason": "Step 1 results not available, calculating proper multiples from request data",
            },
        )

        if not _request_allows_untrusted_multiples_fallback(request):
            return self._fail_closed_output(
                "step_1_results_not_available",
                request,
                correlation_id,
            )

        fallback_multiples = self.calculate_fallback_multiples(request)
        if not fallback_multiples:
            fallback_multiples = self._get_generic_defaults()

        fallback_result = self._build_fallback_result(
            fallback_multiples, "Step 1 results not available"
        )

        return StepOutput(
            step_number=2,
            step_name=self.step_name,
            status=StepStatus.COMPLETED,
            result=fallback_result,
            metadata={
                "fallback_applied": True,
                "fallback_reason": "Step 1 results not available",
                "recovery_method": "calculated_fallback_from_request",
                "business_category": fallback_multiples.get("business_category"),
                "industry": fallback_multiples.get("industry"),
                "business_type_id": fallback_multiples.get("business_type_id"),
            },
            error="Step 1 results not available, using calculated fallback multiples",
        )

    def handle_invalid_revenue(
        self, request: Any, original_revenue: Decimal, correlation_id: Optional[str] = None
    ) -> StepOutput:
        """
        Handle invalid revenue from Step 1.

        Args:
            request: The valuation request
            original_revenue: The invalid revenue value
            correlation_id: Correlation ID for logging

        Returns:
            StepOutput with fallback multiples
        """
        self.logger.warning(
            "⚠️ Step 2: Invalid revenue from Step 1, calculating proper fallback multiples",
            extra={
                "step_number": 2,
                "revenue": original_revenue,
                "validation": "Revenue must be positive",
                "fallback_reason": "Invalid revenue, calculating proper multiples from request data",
                "correlation_id": correlation_id,
            },
        )

        if not _request_allows_untrusted_multiples_fallback(request):
            return self._fail_closed_output(
                "invalid_step_1_revenue",
                request,
                correlation_id,
            )

        fallback_multiples = self.calculate_fallback_multiples(request)
        if not fallback_multiples:
            fallback_multiples = self._get_generic_defaults()

        fallback_result = self._build_fallback_result(
            fallback_multiples,
            "Invalid revenue from Step 1",
            default_revenue=Decimal("1000000.0"),  # Default to €1M for fallback
        )

        return StepOutput(
            step_number=2,
            step_name=self.step_name,
            status=StepStatus.COMPLETED,
            result=fallback_result,
            metadata={
                "fallback_applied": True,
                "fallback_reason": "Invalid revenue from Step 1",
                "recovery_method": "calculated_fallback_from_request",
                "original_revenue": original_revenue,
                "business_category": fallback_multiples.get("business_category"),
                "industry": fallback_multiples.get("industry"),
                "business_type_id": fallback_multiples.get("business_type_id"),
            },
            error="Invalid revenue from Step 1, using calculated fallback multiples",
        )

    def handle_execution_exception(
        self,
        exception: Exception,
        request: Any,
        result_dict: Optional[Dict[str, Any]] = None,
        multiples_data_backup: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ) -> StepOutput:
        """
        Handle exceptions during execution.

        Args:
            exception: The exception that occurred
            request: The valuation request
            result_dict: Result dictionary if available
            multiples_data_backup: Backup multiples data if available
            correlation_id: Correlation ID for logging

        Returns:
            StepOutput with recovered or fallback data
        """
        # If we have a valid result dict, return it
        if result_dict and len(result_dict) > 0:
            # Verify result_dict has Step 2's keys, not Step 1's
            expected_step_2_keys = [
                "ev_revenue_multiple",
                "ev_ebitda_multiple",
                "primary_method",
                "data_source",
            ]
            step_1_keys = [
                "revenue",
                "ebitda",
                "ebitda_margin",
                "company_info",
                "using_weighted_metrics",
                "weighting_method",
            ]
            actual_keys = list(result_dict.keys())
            has_step_1_keys = any(key in actual_keys for key in step_1_keys)
            has_step_2_keys = any(key in actual_keys for key in expected_step_2_keys)

            if has_step_1_keys and not has_step_2_keys:
                self.logger.error(
                    "❌ CRITICAL: Step 2 exception handler result_dict has Step 1's keys! Not returning it.",
                    extra={
                        "step_number": 2,
                        "correlation_id": correlation_id,
                        "actual_keys": actual_keys,
                        "expected_keys": expected_step_2_keys,
                        "error_type": type(exception).__name__,
                    },
                )
            elif _request_allows_untrusted_multiples_fallback(
                request
            ) or _resolved_benchmark_contract(result_dict):
                # Result dict has correct keys, return it
                return StepOutput(
                    step_number=2,
                    step_name=self.step_name,
                    status=StepStatus.COMPLETED,
                    result=result_dict,
                    metadata={
                        "exception_occurred": True,
                        "exception_type": type(exception).__name__,
                        "exception_message": str(exception),
                    },
                    error=f"Exception during execution but result preserved: {str(exception)}",
                )
            else:
                return self._fail_closed_output(
                    "result_dict_missing_resolved_benchmark_contract",
                    request,
                    correlation_id,
                    exception,
                )

        # Log what we received
        self.logger.info(
            "🔍 Step 2: Error handler called - checking multiples_data_backup",
            extra={
                "step_number": 2,
                "multiples_backup_is_none": multiples_data_backup is None,
                "multiples_backup_type": (
                    type(multiples_data_backup).__name__ if multiples_data_backup else None
                ),
                "multiples_backup_is_dict": (
                    isinstance(multiples_data_backup, dict) if multiples_data_backup else False
                ),
                "multiples_backup_len": (
                    len(multiples_data_backup) if isinstance(multiples_data_backup, dict) else 0
                ),
                "multiples_backup_keys": (
                    list(multiples_data_backup.keys())
                    if isinstance(multiples_data_backup, dict)
                    else []
                ),
                "has_ev_ebitda": (
                    "ev_ebitda" in multiples_data_backup
                    if isinstance(multiples_data_backup, dict)
                    else False
                ),
                "has_ev_revenue": (
                    "ev_revenue" in multiples_data_backup
                    if isinstance(multiples_data_backup, dict)
                    else False
                ),
                "ev_ebitda_value": (
                    str(multiples_data_backup.get("ev_ebitda"))
                    if isinstance(multiples_data_backup, dict)
                    else None
                ),
                "ev_revenue_value": (
                    str(multiples_data_backup.get("ev_revenue"))
                    if isinstance(multiples_data_backup, dict)
                    else None
                ),
                "data_source": (
                    multiples_data_backup.get("data_source")
                    if isinstance(multiples_data_backup, dict)
                    else None
                ),
                "error_type": type(exception).__name__,
            },
        )

        # Try to recover from multiples_data_backup using recovery service
        if multiples_data_backup and self.recovery_service._is_valid_backup(multiples_data_backup):
            if not _request_allows_untrusted_multiples_fallback(
                request
            ) and not _resolved_benchmark_contract(multiples_data_backup):
                return self._fail_closed_output(
                    "backup_missing_resolved_benchmark_contract",
                    request,
                    correlation_id,
                    exception,
                )
            self.logger.warning(
                "Step 2: No result_dict but multiples_data_backup available, using recovery service",
                extra={
                    "step_number": 2,
                    "multiples_backup_keys": list(multiples_data_backup.keys()),
                    "multiples_backup_data_source": multiples_data_backup.get("data_source"),
                    # BANK-GRADE: Use explicit None checks to handle Decimal("0") correctly
                    # Decimal("0") is falsy but valid - must check for None explicitly, not truthiness
                    "backup_ev_ebitda": (
                        str(multiples_data_backup.get("ev_ebitda"))
                        if multiples_data_backup.get("ev_ebitda") is not None
                        else None
                    ),
                    "backup_ev_revenue": (
                        str(multiples_data_backup.get("ev_revenue"))
                        if multiples_data_backup.get("ev_revenue") is not None
                        else None
                    ),
                    "error_type": type(exception).__name__,
                },
            )

            # Use recovery service
            minimal_result = self.recovery_service.recover_result_dict(
                backup=multiples_data_backup,
                error=exception,
                context=_fallback_recovery_context(request, correlation_id),
            )

            self.logger.info(
                "Step 2: Error handler returning COMPLETED status with recovered multiples",
                extra={
                    "step_number": 2,
                    "status": "COMPLETED",
                    "data_source": minimal_result.get("data_source"),
                    "ev_ebitda_multiple": str(minimal_result.get("ev_ebitda_multiple")),
                    "ev_revenue_multiple": str(minimal_result.get("ev_revenue_multiple")),
                    "recovery_applied": minimal_result.get("recovery_applied", False),
                },
            )

            return StepOutput(
                step_number=2,
                step_name=self.step_name,
                status=StepStatus.COMPLETED,  # CRITICAL: Always COMPLETED when we have valid multiples
                result=minimal_result,
                metadata={
                    "multiples_backup": multiples_data_backup.copy(),
                    "result_backup": minimal_result.copy(),
                    "exception_occurred": True,
                    "exception_type": type(exception).__name__,
                    "exception_message": str(exception),
                    "recovery_method": "multiples_data_backup",
                    "recovery_applied": True,
                    "has_valid_multiples": True,
                },
                error=f"Exception during execution but multiples recovered: {str(exception)}",
            )

        # Last resort: use recovery service with defaults
        self.logger.warning(
            "Step 2: No result_dict or multiples_data_backup available, using recovery service defaults",
            extra={
                "step_number": 2,
                "error_type": type(exception).__name__,
                "error_message": str(exception),
                "fallback_reason": "No backup data available, using recovery service defaults",
            },
        )

        if not _request_allows_untrusted_multiples_fallback(request):
            return self._fail_closed_output(
                "no_step_2_backup_available",
                request,
                correlation_id,
                exception,
            )

        # Use recovery service with None backup to get defaults
        fallback_result = self.recovery_service.recover_result_dict(
            backup=None,
            error=exception,
            context=_fallback_recovery_context(request, correlation_id),
        )

        return StepOutput(
            step_number=2,
            step_name=self.step_name,
            status=StepStatus.COMPLETED,
            result=fallback_result,
            metadata={
                "exception_type": type(exception).__name__,
                "exception_message": str(exception),
                "recovery_method": "calculated_fallback_from_request",
                "fallback_applied": True,
                "business_category": fallback_result.get("business_category"),
                "industry": fallback_result.get("industry"),
                "business_type_id": fallback_result.get("business_type_id"),
            },
            error=f"Exception occurred but using calculated fallback multiples: {str(exception)}",
        )

    def calculate_fallback_multiples(self, request: Any) -> Optional[Dict[str, Any]]:
        """
        Calculate fallback multiples based on request data.

        Args:
            request: The valuation request

        Returns:
            Dictionary with fallback multiples or None if calculation fails
        """
        try:
            business_type_id = getattr(request, "business_type_id", None)
            industry = getattr(request, "industry", None)
            business_model = getattr(request, "business_model", None)
            business_category = (
                self.business_type_triage.get_business_type_category(
                    business_type_id=business_type_id,
                    business_model=business_model,
                    industry=industry,
                )
                if business_type_id
                else None
            )

            # Get proper multiples based on business_category/industry
            fallback_multiples = self.industry_benchmark_collector.get_fallback_multiples(
                business_category, industry, business_type_id
            )

            # Add metadata for logging
            fallback_multiples["business_category"] = (
                (
                    business_category.value
                    if hasattr(business_category, "value")
                    else str(business_category)
                )
                if business_category
                else None
            )
            fallback_multiples["industry"] = industry
            fallback_multiples["business_type_id"] = business_type_id

            return fallback_multiples
        except Exception as e:
            self.logger.error(
                "❌ Failed to calculate fallback multiples, using generic defaults",
                extra={"fallback_error": str(e)},
                exc_info=True,
            )
            return None

    def _build_fallback_result(
        self,
        fallback_multiples: Dict[str, Any],
        warning_message: str,
        default_revenue: Optional[Decimal] = None,
    ) -> Dict[str, Any]:
        """
        Build fallback result dictionary from fallback multiples.

        Args:
            fallback_multiples: Fallback multiples dictionary
            warning_message: Warning message to include
            default_revenue: Default revenue value if needed

        Returns:
            Fallback result dictionary
        """
        ev_ebitda_p25 = fallback_multiples["ev_ebitda"] * Decimal("0.8")
        ev_ebitda_p75 = fallback_multiples["ev_ebitda"] * Decimal("1.2")
        ev_revenue_p25 = fallback_multiples["ev_revenue"] * Decimal("0.8")
        ev_revenue_p75 = fallback_multiples["ev_revenue"] * Decimal("1.2")

        return {
            "primary_method": "EV/EBITDA",
            "ev_ebitda_multiple": fallback_multiples["ev_ebitda"],
            "ev_revenue_multiple": fallback_multiples["ev_revenue"],
            "pe_ratio": fallback_multiples["pe"],
            "data_source": fallback_multiples["data_source"],
            "ev_revenue_p25": ev_revenue_p25,
            "ev_revenue_p50": fallback_multiples["ev_revenue"],
            "ev_revenue_p75": ev_revenue_p75,
            "ev_ebitda_p25": ev_ebitda_p25,
            "ev_ebitda_p50": fallback_multiples["ev_ebitda"],
            "ev_ebitda_p75": ev_ebitda_p75,
            "multiples_p25": ev_ebitda_p25,
            "multiples_p50": fallback_multiples["ev_ebitda"],
            "multiples_p75": ev_ebitda_p75,
            "warning": f'{warning_message}, using calculated fallback multiples ({fallback_multiples["data_source"]}). Calculation will proceed with proper multiples.',
        }

    def _get_generic_defaults(self) -> Dict[str, Any]:
        """
        Get generic default multiples as last resort.

        5.0x EV/EBITDA reflects the cross-industry SME median from Pepperdine
        Private Capital Markets Report (2024) and BizBuySell transaction data.

        Returns:
            Dictionary with generic default multiples
        """
        return {
            "ev_ebitda": Decimal("5.0"),
            "ev_revenue": Decimal("1.0"),
            "pe": Decimal("13.0"),
            "data_source": "fallback_generic_defaults",
            "business_category": None,
            "industry": None,
            "business_type_id": None,
        }
