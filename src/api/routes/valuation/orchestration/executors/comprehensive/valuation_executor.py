"""
Valuation Executor for Comprehensive Valuation Orchestrator

Handles execution of valuation methodologies.
"""

from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from src.api.schemas import ValuationRequest
from src.domain.report_integrity import build_method_substitution_warning
from src.domain.methods.startup import calculate_startup_result
from src.utils.decimal_helpers import to_decimal
from src.utils.exceptions import MethodologyError
from src.utils.valuation_logger import ValuationLogger

from .alternative_valuation_executor import (
    AssetBasedUnavailableError,
    RealEstateYieldUnavailableError,
)
from .performance_monitor import PerformanceMonitor


class ValuationExecutor:
    """Executes valuation methodologies."""

    def __init__(
        self,
        dcf_executor,
        multiples_executor,
        hybrid_executor,
        alternative_valuation_executor,
        performance_monitor: PerformanceMonitor,
        logger: ValuationLogger,
    ):
        """
        Initialize the valuation executor.

        Args:
            dcf_executor: DCF executor instance
            multiples_executor: Multiples executor instance
            hybrid_executor: Hybrid executor instance
            alternative_valuation_executor: Alternative valuation executor instance
            performance_monitor: Performance monitor instance
            logger: Logger instance
        """
        self.dcf_executor = dcf_executor
        self.multiples_executor = multiples_executor
        self.hybrid_executor = hybrid_executor
        self.alternative_valuation_executor = alternative_valuation_executor
        self.performance_monitor = performance_monitor
        self.logger = logger

    async def execute_valuation(
        self,
        request: ValuationRequest,
        methodology: str,
        context: Dict[str, Any],
        should_calculate_dcf_precheck: bool,
        dcf_exclusion_reason_precheck: Optional[str],
        correlation_id: str,
        valuation_calc_start: Decimal,
        stage_timings: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], str, Optional[str]]:
        """
        Execute valuation based on methodology.

        Args:
            request: The valuation request
            methodology: The methodology to execute
            context: Processing context
            should_calculate_dcf_precheck: Whether DCF should be calculated
            dcf_exclusion_reason_precheck: DCF exclusion reason if applicable
            correlation_id: Correlation ID for logging
            valuation_calc_start: Start time for valuation calculation
            stage_timings: Dictionary to track stage timings

        Returns:
            Tuple of detailed results, executed methodology, and optional downgrade reason
        """
        self.logger.debug(
            "🔍 DIAGNOSTIC: About to execute valuation methodology",
            extra={
                "methodology": methodology,
                "will_execute_hybrid": methodology == "HYBRID",
                "will_execute_dcf_only": methodology == "DCF",
                "will_execute_multiples_only": methodology == "MULTIPLES",
            },
        )

        # Execute based on methodology
        try:
            executed_methodology = methodology
            execution_downgrade_reason: Optional[str] = None

            if methodology == "DCF":
                self.logger.debug(
                    "⚠️ DIAGNOSTIC: Executing DCF-only path (weight calculation will NOT run)"
                )
                detailed_results = await self.dcf_executor.execute(request, context)
            elif methodology == "MULTIPLES":
                detailed_results = await self.multiples_executor.execute(request, context)
            elif methodology == "ASSET_BASED":
                try:
                    detailed_results = (
                        await self.alternative_valuation_executor.execute_asset_based_valuation(
                            request, context
                        )
                    )
                except AssetBasedUnavailableError as asset_error:
                    executed_methodology = "MULTIPLES"
                    fallback_metadata = asset_error.to_metadata()
                    execution_downgrade_reason = (
                        "Asset-Based methodology was selected, but balance-sheet data was "
                        "insufficient or adjusted NAV could not be produced. Falling back "
                        "to Market Multiples methodology."
                    )
                    self.logger.warning(
                        "Asset-based valuation unavailable; falling back to multiples",
                        extra={
                            "requested_methodology": methodology,
                            "executed_methodology": executed_methodology,
                            "reason": fallback_metadata.get("reason"),
                            "reason_code": fallback_metadata.get("code"),
                            "missing_fields": fallback_metadata.get("missing_fields"),
                            "correlation_id": correlation_id,
                        },
                    )
                    detailed_results = await self.multiples_executor.execute(request, context)
                    substitution_payload = {
                        "requested_methodology": methodology,
                        "executed_methodology": executed_methodology,
                        "reason": fallback_metadata.get("reason"),
                        "reason_code": fallback_metadata.get("code"),
                        "missing_fields": list(fallback_metadata.get("missing_fields") or []),
                        "remediation": fallback_metadata.get("remediation"),
                        "details": dict(fallback_metadata.get("details") or {}),
                    }
                    detailed_results["asset_based_fallback_reason"] = fallback_metadata.get(
                        "reason"
                    )
                    detailed_results["methodology_substitution"] = substitution_payload
                    # Surface the substitution as a must-disclose integrity
                    # warning so the PDF Page-1 callout shows it even when
                    # other data is clean. Aggregation (response_builder) will
                    # collect this from detailed_results into the canonical
                    # response.data_quality_warnings list.
                    integrity_warning = build_method_substitution_warning(
                        requested_method="ASSET_BASED",
                        executed_method="MULTIPLES",
                        reason=fallback_metadata.get("reason"),
                        extra_details={
                            "reason_code": fallback_metadata.get("code"),
                            "missing_fields": list(fallback_metadata.get("missing_fields") or []),
                            "remediation": fallback_metadata.get("remediation"),
                            "substitution": substitution_payload,
                        },
                    )
                    existing_warnings = detailed_results.get("data_quality_warnings")
                    if isinstance(existing_warnings, list):
                        existing_warnings.append(integrity_warning)
                    else:
                        detailed_results["data_quality_warnings"] = [integrity_warning]
            elif methodology == "REAL_ESTATE_YIELD":
                try:
                    detailed_results = await self.alternative_valuation_executor.execute_real_estate_yield_valuation(
                        request, context
                    )
                except RealEstateYieldUnavailableError as yield_error:
                    yield_metadata = yield_error.to_metadata()
                    execution_downgrade_reason = (
                        "Real-Estate Yield methodology was selected, but income-capitalisation "
                        "data was insufficient. Falling back to Asset-Based methodology."
                    )
                    # Propco with no usable net rent → fall back to the NAV floor
                    # (Asset-Based), then to Multiples only if NAV is also
                    # unavailable. Mirrors the asset→multiples disclosure chain.
                    self.logger.warning(
                        "Real-estate yield unavailable; falling back to Asset-Based (NAV)",
                        extra={
                            "requested_methodology": methodology,
                            "reason": yield_error.reason,
                            "correlation_id": correlation_id,
                        },
                    )
                    try:
                        executed_methodology = "ASSET_BASED"
                        detailed_results = (
                            await self.alternative_valuation_executor.execute_asset_based_valuation(
                                request, context
                            )
                        )
                        substitution_payload = {
                            "requested_methodology": methodology,
                            "executed_methodology": executed_methodology,
                            "reason": yield_metadata.get("reason"),
                            "reason_code": yield_metadata.get("code"),
                            "missing_fields": list(yield_metadata.get("missing_fields") or []),
                            "remediation": yield_metadata.get("remediation"),
                            "details": dict(yield_metadata.get("details") or {}),
                        }
                        detailed_results["real_estate_yield_fallback_reason"] = yield_metadata.get(
                            "reason"
                        )
                        detailed_results["methodology_substitution"] = substitution_payload
                        integrity_warning = build_method_substitution_warning(
                            requested_method="REAL_ESTATE_YIELD",
                            executed_method="ASSET_BASED",
                            reason=yield_metadata.get("reason"),
                            extra_details={
                                "reason_code": yield_metadata.get("code"),
                                "missing_fields": list(yield_metadata.get("missing_fields") or []),
                                "remediation": yield_metadata.get("remediation"),
                                "substitution": substitution_payload,
                            },
                        )
                        existing_warnings = detailed_results.get("data_quality_warnings")
                        if isinstance(existing_warnings, list):
                            existing_warnings.append(integrity_warning)
                        else:
                            detailed_results["data_quality_warnings"] = [integrity_warning]
                    except AssetBasedUnavailableError as asset_error:
                        executed_methodology = "MULTIPLES"
                        fallback_metadata = asset_error.to_metadata()
                        execution_downgrade_reason = (
                            "Real-Estate Yield methodology was selected, but income-capitalisation "
                            "data was insufficient and adjusted NAV could not be produced. "
                            "Falling back to Market Multiples methodology."
                        )
                        detailed_results = await self.multiples_executor.execute(request, context)
                        combined_reason = (
                            f"{yield_metadata.get('reason')}; adjusted NAV fallback unavailable: "
                            f"{fallback_metadata.get('reason')}"
                        )
                        substitution_payload = {
                            "requested_methodology": methodology,
                            "executed_methodology": executed_methodology,
                            "reason": combined_reason,
                            "reason_code": "YIELD_AND_NAV_UNAVAILABLE",
                            "missing_fields": list(fallback_metadata.get("missing_fields") or []),
                            "remediation": fallback_metadata.get("remediation"),
                            "details": {
                                "yield_unavailable": yield_metadata,
                                "asset_based_unavailable": fallback_metadata,
                            },
                        }
                        detailed_results["real_estate_yield_fallback_reason"] = yield_metadata.get(
                            "reason"
                        )
                        detailed_results["asset_based_fallback_reason"] = fallback_metadata.get(
                            "reason"
                        )
                        detailed_results["methodology_substitution"] = substitution_payload
                        integrity_warning = build_method_substitution_warning(
                            requested_method="REAL_ESTATE_YIELD",
                            executed_method="MULTIPLES",
                            reason=combined_reason,
                            extra_details={
                                "reason_code": "YIELD_AND_NAV_UNAVAILABLE",
                                "missing_fields": list(
                                    fallback_metadata.get("missing_fields") or []
                                ),
                                "remediation": fallback_metadata.get("remediation"),
                                "substitution": substitution_payload,
                            },
                        )
                        existing_warnings = detailed_results.get("data_quality_warnings")
                        if isinstance(existing_warnings, list):
                            existing_warnings.append(integrity_warning)
                        else:
                            detailed_results["data_quality_warnings"] = [integrity_warning]
            elif methodology == "MARKET":
                detailed_results = (
                    await self.alternative_valuation_executor.execute_market_valuation(
                        request, context
                    )
                )
            elif methodology == "STARTUP":
                detailed_results = self._execute_startup_valuation(request)
            elif methodology == "INCOME":
                detailed_results = (
                    await self.alternative_valuation_executor.execute_income_valuation(
                        request, context
                    )
                )
            elif methodology == "COST":
                detailed_results = await self.alternative_valuation_executor.execute_cost_valuation(
                    request, context
                )
            elif methodology == "HYBRID":
                self.logger.debug(
                    "✅ DIAGNOSTIC: Executing HYBRID path (weight calculation WILL run)",
                    extra={
                        "methodology": "HYBRID",
                        "use_dcf": getattr(request, "use_dcf", True),
                        "use_multiples": getattr(request, "use_multiples", True),
                        "should_calculate_dcf": should_calculate_dcf_precheck,
                        "dcf_exclusion_reason": dcf_exclusion_reason_precheck,
                        "revenue": (
                            request.current_year_data.revenue if request.current_year_data else None
                        ),
                    },
                )
                detailed_results = await self.hybrid_executor.execute(request, context)

                # Log DCF execution status in HYBRID methodology
                dcf_created = detailed_results.get("dcf_valuation") is not None
                self.logger.info(
                    "📊 HYBRID Methodology Execution Summary",
                    extra={
                        "dcf_executed": dcf_created,
                        "dcf_equity_value": (
                            detailed_results.get("dcf_valuation", {}).get("equity_value")
                            if dcf_created
                            else None
                        ),
                        "multiples_executed": detailed_results.get("multiples_valuation")
                        is not None,
                        "multiples_equity_value": (
                            detailed_results.get("multiples_valuation", {}).get("equity_value")
                            if detailed_results.get("multiples_valuation")
                            else None
                        ),
                        "dcf_weight": detailed_results.get("dcf_weight", Decimal("0.0")),
                        "multiples_weight": detailed_results.get(
                            "multiples_weight", Decimal("0.0")
                        ),
                        "final_equity_value_mid": detailed_results.get("equity_value_mid"),
                        "dcf_exclusion_reason": (
                            dcf_exclusion_reason_precheck if not dcf_created else None
                        ),
                    },
                )
            else:
                raise ValueError(f"Unsupported methodology: {methodology}")

            # Performance monitoring: Valuation calculation complete
            valuation_calc_duration = self.performance_monitor.record_stage_timing(
                stage_timings, "valuation_calculation", valuation_calc_start
            )
            self.performance_monitor.log_slow_operation(
                "valuation_calculation",
                valuation_calc_duration,
                threshold=Decimal("5.0"),
                context={"methodology": executed_methodology, "correlation_id": correlation_id},
            )

            # DEBUG: layer-internal completion. metrics_logging_coordinator
            # logs the canonical "Valuation calculation completed
            # successfully" with full telemetry at INFO.
            self.logger.debug(
                "✅ Valuation calculated",
                extra={
                    "methodology": executed_methodology,
                    "requested_methodology": methodology,
                    "enterprise_value": detailed_results.get("enterprise_value"),
                    "equity_value": detailed_results.get("equity_value"),
                },
            )

            return detailed_results, executed_methodology, execution_downgrade_reason

        except MethodologyError as methodology_error:
            # Log error and re-raise for error handler in orchestrator
            self.logger.error(
                f"❌ Error executing {methodology} valuation",
                extra={
                    "error": str(methodology_error),
                    "error_type": type(methodology_error).__name__,
                    "methodology": methodology,
                    "correlation_id": correlation_id,
                },
                exc_info=True,
            )
            raise

    def _execute_startup_valuation(self, request: ValuationRequest) -> Dict[str, Any]:
        """Execute the standalone startup engine without touching SME multiples."""
        startup_inputs = getattr(request, "startup_inputs", None)
        if startup_inputs is None:
            raise MethodologyError(
                "Startup valuation requires startup_inputs; request validation "
                "should reject startup_valuation requests before execution when "
                "qualitative startup inputs are missing."
            )

        startup_method = calculate_startup_result(startup_inputs=startup_inputs)
        if not startup_method.available or startup_method.value is None:
            reason = startup_method.unavailable_reason or "Startup valuation unavailable"
            raise MethodologyError(reason)

        startup_mid = to_decimal(startup_method.value)
        startup_low, startup_high = self._startup_range(startup_method, startup_mid)
        startup_payload = startup_method.model_dump()

        self.logger.info(
            "📊 STARTUP Methodology Execution Summary",
            extra={
                "startup_equity_value": startup_mid,
                "selected_method": getattr(request, "selected_method", None),
                "use_dcf": getattr(request, "use_dcf", None),
                "use_multiples": getattr(request, "use_multiples", None),
            },
        )

        return {
            "methodology": "STARTUP",
            "methodology_label": "Startup Valuation",
            "enterprise_value": startup_mid,
            "equity_value": startup_mid,
            "equity_value_low": startup_low,
            "equity_value_mid": startup_mid,
            "equity_value_high": startup_high,
            "step_11_asking_price": startup_mid,
            "dcf_weight": Decimal("0.0"),
            "multiples_weight": Decimal("0.0"),
            "startup_valuation": startup_payload,
            "valuation_results": {"startup_valuation": startup_payload},
            "startup_valuation_native": True,
            "per_share_value": None,
            "_value_sources": {
                "equity_value_low_source": "Startup Valuation",
                "equity_value_mid_source": "Startup Valuation",
                "equity_value_high_source": "Startup Valuation",
            },
        }

    @staticmethod
    def _startup_range(startup_method: object, startup_mid: Decimal) -> Tuple[Decimal, Decimal]:
        details = getattr(startup_method, "details", None) or {}
        canonical = details.get("canonical") if isinstance(details, dict) else None
        canonical = canonical if isinstance(canonical, dict) else {}
        low_raw = (
            canonical.get("pre_money_low")
            or getattr(startup_method, "value_low", None)
            or details.get("equity_value_low")
        )
        high_raw = (
            canonical.get("pre_money_high")
            or getattr(startup_method, "value_high", None)
            or details.get("equity_value_high")
        )
        startup_low = to_decimal(low_raw) if low_raw is not None else startup_mid
        startup_high = to_decimal(high_raw) if high_raw is not None else startup_mid
        if startup_low <= 0 or startup_high < startup_low:
            return startup_mid, startup_mid
        return startup_low, startup_high
