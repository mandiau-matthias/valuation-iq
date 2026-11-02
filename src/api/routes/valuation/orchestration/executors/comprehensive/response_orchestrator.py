"""
Response Orchestrator for Comprehensive Valuation Orchestrator

Handles the complete response building flow including response dict construction,
transparency building, validation, and error handling.
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from src.api.schemas import ValuationRequest, ValuationResponse
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.valuation_logger import ValuationLogger

from .performance_monitor import PerformanceMonitor
from .response_builder import ResponseBuilder as ComprehensiveResponseBuilder
from .response_validator import ResponseValidator
from .transparency_builder import TransparencyBuilder as ComprehensiveTransparencyBuilder


class ResponseOrchestrator:
    """Orchestrates the complete response building flow."""

    def __init__(
        self,
        comprehensive_response_builder: ComprehensiveResponseBuilder,
        comprehensive_transparency_builder: ComprehensiveTransparencyBuilder,
        response_validator: ResponseValidator,
        performance_monitor: PerformanceMonitor,
        logger: ValuationLogger,
    ):
        """
        Initialize the response orchestrator.

        Args:
            comprehensive_response_builder: Comprehensive response builder instance
            comprehensive_transparency_builder: Comprehensive transparency builder instance
            response_validator: Response validator instance
            performance_monitor: Performance monitor instance
            logger: Logger instance
        """
        self.comprehensive_response_builder = comprehensive_response_builder
        self.comprehensive_transparency_builder = comprehensive_transparency_builder
        self.response_validator = response_validator
        self.performance_monitor = performance_monitor
        self.logger = logger

    async def build_and_validate_response(
        self,
        request: ValuationRequest,
        detailed_results: Dict[str, Any],
        valuation_id: str,
        methodology: str,
        equity_value_low: Decimal,
        equity_value_mid: Decimal,
        equity_value_high: Decimal,
        confidence_score: Decimal,
        financial_metrics: Dict[str, Any],
        methodology_downgrade_reason: Optional[str],
        dcf_exclusion_reason_precheck: Optional[str],
        correlation_id: str,
        stage_timings: Dict[str, Any],
    ) -> ValuationResponse:
        """
        Build and validate the complete valuation response.

        Args:
            request: The valuation request
            detailed_results: The detailed valuation results
            valuation_id: Valuation ID
            methodology: Valuation methodology
            equity_value_low: Low equity value
            equity_value_mid: Mid equity value
            equity_value_high: High equity value
            confidence_score: Confidence score
            financial_metrics: Financial metrics dictionary
            methodology_downgrade_reason: Methodology downgrade reason if applicable
            dcf_exclusion_reason_precheck: DCF exclusion reason if applicable
            correlation_id: Correlation ID for logging
            stage_timings: Dictionary to track stage timings

        Returns:
            Complete ValuationResponse object

        Raises:
            Exception: If response building or validation fails
        """
        from src.config import get_settings

        # Log response building start
        if get_settings().debug:
            print(f"[ERROR-LOGGING] About to build ValuationResponse")
        self.logger.debug(
            "🔍 Building ValuationResponse",
            extra={
                "valuation_id": valuation_id,
                "equity_value_mid": equity_value_mid,
                "confidence_score": confidence_score,
            },
        )

        # Performance monitoring: Start response building timing
        response_build_start = self.performance_monitor.start_timing()

        try:
            # Build response dictionary using ComprehensiveResponseBuilder
            response_dict = self.comprehensive_response_builder.build_response_dict(
                request=request,
                detailed_results=detailed_results,
                valuation_id=valuation_id,
                methodology=methodology,
                equity_value_low=equity_value_low,
                equity_value_mid=equity_value_mid,
                equity_value_high=equity_value_high,
                confidence_score=confidence_score,
                financial_metrics=financial_metrics,
                methodology_downgrade_reason=methodology_downgrade_reason,
                dcf_exclusion_reason_precheck=dcf_exclusion_reason_precheck,
                correlation_id=correlation_id,
            )

            if response_dict.get("dcf_valuation") is None:
                response_dict["dcf_exclusion_reason"] = dcf_exclusion_reason_precheck

            # Build transparency using ComprehensiveTransparencyBuilder
            self._build_transparency(
                request, detailed_results, confidence_score, correlation_id, response_dict
            )

            # Build structured defensibility report (0-10 academic + ICP scores,
            # typed warnings, submit-gate). Defensive: any failure here is
            # logged and the field is left absent — never blocks the response.
            self._build_defensibility_report(
                request, response_dict, correlation_id
            )

            # Validate critical fields using ResponseValidator
            self.response_validator.validate_critical_fields(response_dict)

            # Validate nested models using ResponseValidator
            problematic_fields = self.response_validator.validate_nested_models(
                response_dict, correlation_id
            )

            # Create ValuationResponse using ResponseValidator
            response = await self.response_validator.create_valuation_response(
                response_dict=response_dict,
                correlation_id=correlation_id,
                valuation_id=valuation_id,
            )

            # Performance monitoring: Response building complete
            response_build_duration = self.performance_monitor.record_stage_timing(
                stage_timings, "response_building", response_build_start
            )
            self.performance_monitor.log_slow_operation(
                "response_building",
                response_build_duration,
                threshold=Decimal("5.0"),
                context={"correlation_id": correlation_id},
            )

            return response

        except Exception as response_error:
            self._handle_response_error(response_error, valuation_id, request, correlation_id)
            raise

    def _build_transparency(
        self,
        request: ValuationRequest,
        detailed_results: Dict[str, Any],
        confidence_score: Decimal,
        correlation_id: str,
        response_dict: Dict[str, Any],
    ) -> None:
        """
        Build transparency data and add to response dict.

        Args:
            request: The valuation request
            detailed_results: The detailed valuation results
            confidence_score: Confidence score
            correlation_id: Correlation ID for logging
            response_dict: Response dictionary to update
        """
        try:
            transparency_data = self.comprehensive_transparency_builder.build_transparency_data(
                request=request,
                detailed_results=detailed_results,
                confidence_score=confidence_score,
                correlation_id=correlation_id,
            )
            response_dict["transparency"] = transparency_data
        except Exception as transparency_error:
            # ComprehensiveTransparencyBuilder handles errors internally
            # Fallback is already set in the builder
            self.logger.error(
                "❌ Transparency building failed",
                extra={
                    "error": str(transparency_error),
                    "error_type": type(transparency_error).__name__,
                },
                exc_info=True,
            )
            # Set None as last resort (schema allows Optional)
            if "transparency" not in response_dict or response_dict["transparency"] is None:
                response_dict["transparency"] = None

    def _build_defensibility_report(
        self,
        request: Any,
        response_dict: Dict[str, Any],
        correlation_id: str,
    ) -> None:
        """Compose the structured defensibility report and stash it on the
        response. The shape is documented in
        ``src.services.defensibility.report.DefensibilityReport.to_serializable``.

        Defensive: never raises. The submit-gate and cover chip are
        rendered from this field but the engine *cannot* refuse to return
        a valuation because of a defensibility-layer bug — the existing
        ``DefensibilityVerdict`` (auto_watermark) remains the failsafe.
        """
        try:
            from src.services.defensibility import build_defensibility_report

            # Build a flat dict the scorer can read. The scorer is tolerant
            # of missing keys; we pass the response_dict directly so it
            # sees transparency_report, detailed_results, owner_dependency,
            # and the canonical financial fields.
            locale = getattr(request, "report_locale", None) or getattr(request, "locale", None) or "nl"
            # The response schema omits request identity/provenance. Preserve
            # validated inputs for scoring, with calculated values taking precedence.
            request_data = request.model_dump() if hasattr(request, "model_dump") else vars(request)
            scoring_input = {**request_data, **response_dict}
            scoring_input["metadata"] = {
                **(request_data.get("metadata") or {}),
                **(response_dict.get("metadata") or {}),
            }
            report = build_defensibility_report(scoring_input, locale=str(locale))
            response_dict["defensibility_report"] = report.to_serializable()
            self.logger.debug(
                "✅ Defensibility report attached",
                extra={
                    "correlation_id": correlation_id,
                    "academic_score": report.academic.score,
                    "icp_score": report.icp.score,
                    "submit_recommendation": report.submit_gate.recommendation.value,
                    "warnings_count": len(report.warnings),
                },
            )
        except Exception as e:
            # Never block the response on a defensibility-layer bug.
            self.logger.warning(
                "⚠️ Defensibility report build failed — field omitted",
                extra={
                    "correlation_id": correlation_id,
                    "error": str(e)[:200],
                    "error_type": type(e).__name__,
                },
            )

    def _handle_response_error(
        self,
        response_error: Exception,
        valuation_id: str,
        request: ValuationRequest,
        correlation_id: str,
    ) -> None:
        """
        Handle response building errors.

        Args:
            response_error: The exception that occurred
            valuation_id: Valuation ID
            request: The valuation request
            correlation_id: Correlation ID for logging
        """
        import traceback

        from src.config import get_settings

        error_msg = str(response_error) if response_error else "Unknown response building error"
        error_type = type(response_error).__name__ if response_error else "UnknownType"

        if get_settings().debug:
            print(
                f"[ERROR-LOGGING] ValuationResponse construction FAILED | error={error_msg} | type={error_type}"
            )

        self.logger.error(
            "❌ Error building ValuationResponse",
            extra={
                "error": error_msg,
                "error_type": error_type,
                "error_repr": repr(response_error) if response_error else None,
                "valuation_id": valuation_id,
                "company_name": request.company_name,
            },
            exc_info=True,
        )

        traceback_str = traceback.format_exc()
        if get_settings().debug:
            print(f"[ERROR-LOGGING] ValuationResponse TRACEBACK:\n{traceback_str}")
