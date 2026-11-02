"""
Multiples Calculator Module (REFACTORED)

Market multiples-based valuation calculator using the modular step pipeline.

REFACTORING COMPLETE:
- Now uses CalculationTriage orchestrator with 11 modular steps
- Maintains 100% backward compatibility with existing API
- Each calculation step is independently testable
- Conditional execution based on data availability
- Full transparency reporting

Original monolithic version backed up as: multiples_calculator_old.py
"""

import asyncio
from decimal import Decimal
from threading import Lock as ThreadingLock
from typing import Optional, TypeAlias

from src.api.schemas import ValuationRequest
from src.domain.models import ConfidenceLevel
from src.utils.data_flow_tracer import get_tracer
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.exceptions import CalculationError, DataQualityError, ValidationError
from src.utils.valuation_logger import ValuationLogger

from ..steps import StepOutput, StepStatus

# Import the new modular system
from ..triage import CalculationTriage
from .legacy_response_helpers import (
    build_owner_concentration_dict,
    get_industry_default_multiple,
    get_primary_method_reason,
    map_confidence_level,
)
from .legacy_response_transformer import LegacyResponseTransformer

# Import focused SRP classes
from .multiples.step2_result_extractor import Step2ResultExtractor
from .multiples.step2_result_updater import Step2ResultUpdater
from .multiples.step2_result_validator import Step2ResultValidator

# Import helper modules for extraction and recovery
from .step2_recovery_handler import Step2RecoveryHandler
from .valuation_extractor import ValuationExtractor

logger = ValuationLogger(__name__)

JsonMap: TypeAlias = dict[str, object]
StepOutputMap: TypeAlias = dict[int, StepOutput]


class MultiplesCalculator:
    """
    Market multiples valuation calculator (REFACTORED)

    Now uses the modular step pipeline with intelligent triage.

    Features:
    - Modular step-based architecture (Steps 0-10)
    - Intelligent triage routing
    - Conditional execution (e.g., owner concentration only if data available)
    - Full transparency and traceability
    - Backward compatible API

    Concurrency:
        One ``MultiplesCalculator`` instance reuses the same registered step objects.
        A per-instance async lock serializes that short critical section so overlapping
        API requests cannot race through shared step instances.

    Steps:
    0. Data Quality Assessment
    1. Input Validation & Normalization
    2. Industry Benchmarking & Multiple Selection
    3. Base Enterprise Value Calculation
    4. Owner Concentration Adjustment (conditional)
    5. Size Discount Application
    6. Liquidity Discount Application
    7. EV to Equity Conversion
    8. Confidence Score Analysis
    9. Range Methodology Selection
    10. Final Valuation Synthesis
    """

    def __init__(
        self,
        multiples_adapter=None,
        business_rules: Optional[JsonMap] = None,
        transparency_collector=None,
        business_types_repo=None,
        fmp_adapter=None,
        cache_service=None,
    ):
        """
        Initialize multiples calculator with modular system

        Args:
            multiples_adapter: Optional business type multiples adapter
            business_rules: Optional business rules configuration
            transparency_collector: Optional transparency reporting collector
            business_types_repo: Optional business types repository
            fmp_adapter: Optional FMP adapter for market data (Phase 3)
            cache_service: Optional cache service for market data (Phase 3)
        """
        self.logger = logger
        self.multiples_adapter = multiples_adapter
        self.business_rules = business_rules or {}
        self.transparency_collector = transparency_collector
        self.business_types_repo = business_types_repo
        self.fmp_adapter = fmp_adapter
        self.cache_service = cache_service

        # Initialize the new modular triage system
        self.triage = CalculationTriage()
        self._triage_execution_sync_lock = ThreadingLock()
        self._triage_execution_lock: Optional[asyncio.Lock] = None

        # Initialize helper modules for extraction and recovery
        self.step2_recovery = Step2RecoveryHandler()
        self.valuation_extractor = ValuationExtractor(
            get_industry_default_fn=get_industry_default_multiple, logger_instance=self.logger
        )
        self.legacy_transformer = LegacyResponseTransformer(self.valuation_extractor)

        # Initialize focused SRP classes
        self.step2_extractor = Step2ResultExtractor(self.step2_recovery)
        self.step2_validator = Step2ResultValidator()
        self.step2_updater = Step2ResultUpdater()

        # Pass dependencies to steps that need them
        self._inject_dependencies_into_steps()

        self.logger.debug(
            "🎯 MultiplesCalculator initialized (MODULAR SYSTEM)",
            extra={
                "architecture": "modular-step-pipeline",
                "triage_enabled": True,
                "registered_steps": len(self.triage.steps),
            },
        )

    @property
    def _triage_lock(self) -> asyncio.Lock:
        if self._triage_execution_lock is None:
            with self._triage_execution_sync_lock:
                if self._triage_execution_lock is None:
                    self._triage_execution_lock = asyncio.Lock()
        return self._triage_execution_lock

    async def _execute_triage_safely(
        self, request: ValuationRequest, context: JsonMap
    ) -> StepOutputMap:
        """Execute the shared triage pipeline without overlapping step usage."""
        async with self._triage_lock:
            return await self.triage.execute_full_calculation(request=request, context=context)

    def _inject_dependencies_into_steps(self):
        """Inject dependencies into steps that need them."""
        # Step 2 needs multiples adapter, business rules, FMP adapter, and cache service
        step_2 = self.triage.steps.get(2)
        if step_2:
            step_2.multiples_adapter = self.multiples_adapter
            step_2.business_rules = self.business_rules
            # Phase 3: Market Data Integration - Inject FMP adapter and cache service
            step_2.fmp_adapter = self.fmp_adapter
            step_2.cache_service = self.cache_service
            # Update market_data_available flag (recalculate based on injected services)
            # Step 2 checks MARKET_DATA_AVAILABLE module-level flag and injected services
            if hasattr(step_2, "market_data_available"):
                # Recalculate: market data is available if services are injected
                # Step 2's MARKET_DATA_AVAILABLE module flag is already set at import time
                step_2.market_data_available = (
                    self.fmp_adapter is not None or self.cache_service is not None
                )

    def _to_display_float(self, value: object) -> Decimal:
        """
        Convert Decimal to float for JSON serialization/display ONLY.
        Internal calculations must use Decimal.

        Args:
            value: Value to convert (Decimal, float, int, or None)

        Returns: Decimal value for display, or Decimal('0.0') if None
        """
        if value is None:
            return Decimal("0.0")
        if isinstance(value, Decimal):
            return from_decimal(value, precision=2)
        try:
            return to_decimal(value)
        except (TypeError, ValueError):
            return Decimal("0.0")

    async def calculate(
        self, request: ValuationRequest, context: Optional[JsonMap] = None
    ) -> JsonMap:
        """
        Calculate multiples-based valuation using modular system

        Args:
            request: Valuation request with financial data
            context: Optional calculation context

        Returns:
            Dictionary with multiples valuation results (backward compatible format)
        """
        try:
            # DEBUG: layer-internal start; the canonical INFO entry for the
            # calc is "🚀 Starting full 11-step calculation" emitted by
            # execution_orchestrator.
            self.logger.debug(
                "📊 Starting modular multiples valuation",
                extra={
                    "company": request.company_name,
                    "system": "modular-12-step",
                    "revenue": (
                        request.current_year_data.revenue if request.current_year_data else None
                    ),
                    "business_model": request.business_model,
                    "industry": request.industry,
                },
            )

            # Ensure weighted_metrics in context when multi-year data exists (for Step 1 Option B)
            ctx: JsonMap = context or {}
            if not ctx.get("weighted_metrics") and getattr(request, "historical_years_data", None):
                try:
                    from src.api.routes.valuation.calculators.weighted_ebitda_calculator import (
                        WeightedEBITDACalculator,
                    )

                    wc = WeightedEBITDACalculator()
                    ctx["weighted_metrics"] = wc.calculate_all_weighted_metrics(request)
                except Exception as e:
                    self.logger.debug(
                        "Could not precompute weighted_metrics for triage",
                        extra={"error": str(e)},
                    )

            # Execute the full 12-step calculation using triage orchestrator
            self.logger.debug(
                "🚀 Executing calculation triage orchestrator",
                extra={
                    "total_steps": 12,
                    "context_keys": list(ctx.keys()),
                    "has_weighted_metrics": bool(ctx.get("weighted_metrics")),
                },
            )

            step_results: StepOutputMap = await self._execute_triage_safely(
                request=request, context=ctx
            )

            self.logger.debug(
                "✅ Calculation triage execution complete",
                extra={
                    "total_steps_executed": len(step_results),
                    "steps_completed": sum(
                        1 for r in step_results.values() if r.status == StepStatus.COMPLETED
                    ),
                    "steps_skipped": sum(
                        1 for r in step_results.values() if r.status == StepStatus.SKIPPED
                    ),
                    "steps_failed": sum(
                        1 for r in step_results.values() if r.status == StepStatus.FAILED
                    ),
                    "total_execution_time_ms": sum(
                        (
                            Decimal(str(r.execution_time_ms))
                            for r in step_results.values()
                            if hasattr(r, "execution_time_ms") and r.execution_time_ms is not None
                        ),
                        Decimal("0"),
                    ),
                },
            )

            # Check if calculation succeeded
            final_step = step_results.get(11)  # Step 11 is Final Synthesis
            if not final_step or final_step.status != StepStatus.COMPLETED:
                step_number = 11
                step_name = "Final Synthesis" if final_step else "Final Synthesis (not executed)"
                self.logger.error(
                    "Final synthesis step (Step 11) did not complete successfully",
                    extra={
                        "final_step_number": step_number,
                        "final_step_name": step_name,
                        "final_step_status": final_step.status.value if final_step else "not_found",
                        "final_step_error": (
                            final_step.error
                            if final_step and hasattr(final_step, "error")
                            else "Step 11 was not executed or failed"
                        ),
                        "available_steps": list(step_results.keys()),
                        "step10_status": (
                            step_results.get(10).status.value
                            if step_results.get(10)
                            else "not_found"
                        ),
                        "step10_error": (
                            step_results.get(10).error
                            if step_results.get(10) and hasattr(step_results.get(10), "error")
                            else None
                        ),
                    },
                )
                raise ValueError(
                    f"Step {step_number} ({step_name}) did not complete successfully. Status: {final_step.status.value if final_step else 'not_found'}. Error: {final_step.error if final_step and hasattr(final_step, 'error') else 'Step 11 was not executed'}"
                )

            step11_result = final_step.result or {}
            step11_methodology = step11_result.get("methodology", "")
            _FALLBACK_METHODOLOGIES = {
                "fallback_minimum",
                "fallback_absolute_minimum",
                "fallback_exception_handler",
                "fallback_fatal_error",
                "fallback_fatal_error_invalid",
                "fallback_fatal_error_exception",
            }
            if step11_methodology in _FALLBACK_METHODOLOGIES:
                self.logger.error(
                    "Step 11 completed via fallback — valuation results are "
                    "placeholder values and must not be presented to clients",
                    extra={
                        "methodology": step11_methodology,
                        "valuation_mid": step11_result.get("valuation_mid"),
                        "confidence_score": step11_result.get("confidence_score"),
                    },
                )
                raise ValueError(
                    f"Step 11 completed via fallback ({step11_methodology}) — the pipeline "
                    "could not compute a real valuation. Placeholder values must not reach clients."
                )

            # STEP 2: Log step_results before passing to _transform_to_legacy_format
            # CRITICAL FIX: Enhanced validation and logging for Step 2
            if 2 in step_results:
                step_2_output = step_results[2]
                logger.debug(
                    "🔍 MultiplesCalculator.calculate() - step_results[2] before _transform_to_legacy_format",
                    extra={
                        "step_2_exists": True,
                        "step_2_type": type(step_2_output).__name__,
                        "step_2_id": id(step_2_output),
                        "step_2_has_result": hasattr(step_2_output, "result"),
                        "result_type": (
                            type(step_2_output.result).__name__
                            if hasattr(step_2_output, "result")
                            else None
                        ),
                        "result_is_dict": (
                            isinstance(step_2_output.result, dict)
                            if hasattr(step_2_output, "result")
                            else False
                        ),
                        "result_keys": (
                            list(step_2_output.result.keys())
                            if (
                                hasattr(step_2_output, "result")
                                and isinstance(step_2_output.result, dict)
                            )
                            else []
                        ),
                        "result_size": (
                            len(step_2_output.result)
                            if (
                                hasattr(step_2_output, "result")
                                and isinstance(step_2_output.result, dict)
                            )
                            else 0
                        ),
                        "ev_ebitda_multiple_in_result": (
                            step_2_output.result.get("ev_ebitda_multiple")
                            if (
                                hasattr(step_2_output, "result")
                                and isinstance(step_2_output.result, dict)
                            )
                            else None
                        ),
                        "ev_revenue_multiple_in_result": (
                            step_2_output.result.get("ev_revenue_multiple")
                            if (
                                hasattr(step_2_output, "result")
                                and isinstance(step_2_output.result, dict)
                            )
                            else None
                        ),
                        "full_result_dict": (
                            step_2_output.result
                            if (
                                hasattr(step_2_output, "result")
                                and isinstance(step_2_output.result, dict)
                            )
                            else None
                        ),
                        "status": (
                            step_2_output.status.value if hasattr(step_2_output, "status") else None
                        ),
                        "all_step_numbers": list(step_results.keys()),
                    },
                )

                # Pre-transformation check: Step 2 result may be empty here.
                # The extractor may recover trusted backups, but concrete
                # business-type valuations still fail closed unless the
                # recovered payload carries the resolved Delphi contract.
                if (
                    not hasattr(step_2_output, "result")
                    or not isinstance(step_2_output.result, dict)
                    or len(step_2_output.result) == 0
                ):
                    logger.warning(
                        "⚠️ Step 2 result missing or empty before transformation — recovery will be attempted",
                        extra={
                            "step_2_status": (
                                step_2_output.status.value
                                if hasattr(step_2_output, "status")
                                else None
                            ),
                            "has_result": hasattr(step_2_output, "result"),
                            "has_metadata": hasattr(step_2_output, "metadata"),
                        },
                    )
            else:
                logger.warning(
                    "⚠️ step_results[2] not found — non-concrete or explicitly opted-in requests may reconstruct from disclosed fallbacks",
                    extra={
                        "step_2_exists": False,
                        "all_step_numbers": list(step_results.keys()),
                    },
                )

            # Transform modular results to legacy API format
            self.logger.debug(
                "🔄 Transforming modular results to legacy API format",
                extra={"note": "Ensuring 100% backward compatibility with existing API consumers"},
            )

            result = self._transform_to_legacy_format(step_results, request, context)

            # DEBUG: dup of "Multiples valuation completed" emitted by multiples_executor.
            self.logger.debug(
                "✅ Modular multiples valuation complete",
                extra={
                    "total_steps_executed": len(step_results),
                    "steps_completed": sum(
                        1 for r in step_results.values() if r.status == StepStatus.COMPLETED
                    ),
                    "steps_skipped": sum(
                        1 for r in step_results.values() if r.status == StepStatus.SKIPPED
                    ),
                    "equity_value_mid": result.get("equity_value"),
                    "equity_value_low": result.get("equity_value_low"),
                    "equity_value_high": result.get("equity_value_high"),
                    "methodology": result.get("methodology"),
                    "confidence_score": result.get("confidence_score"),
                    "primary_method": result.get("primary_method"),
                },
            )

            return result

        except (CalculationError, DataQualityError, ValidationError):
            raise
        except Exception as e:
            self.logger.error(
                "❌ Modular multiples valuation failed",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "company": request.company_name,
                    "revenue": (
                        request.current_year_data.revenue if request.current_year_data else None
                    ),
                },
                exc_info=True,
            )
            raise CalculationError(
                f"Failed to calculate multiples valuation: {e}",
                context={
                    "company": request.company_name,
                    "calculation_type": "Multiples Valuation",
                },
            ) from e

    def _validate_step_2_result(self, step_2: JsonMap) -> bool:
        """
        Validate that step_2 result has required fields.

        Delegates to Step2ResultValidator for single responsibility.

        Args:
            step_2: Step 2 result dictionary

        Returns:
            True if all required fields are present
        """
        return self.step2_validator.validate_step_2_result(step_2)

    def _extract_step_2_result(
        self,
        step_results: StepOutputMap,
        request: ValuationRequest,
        context: Optional[JsonMap],
    ) -> JsonMap:
        """
        Extract step_2 result with comprehensive recovery logic.

        Delegates to Step2ResultExtractor for single responsibility.

        Args:
            step_results: Dictionary mapping step numbers to StepOutput objects
            request: Valuation request
            context: Optional calculation context

        Returns:
            Step 2 result dictionary. Concrete business-type requests fail
            closed unless recovery preserves the resolved Delphi contract.
        """
        return self.step2_extractor.extract_step_2_result(step_results, request, context)

    def _update_step_2_result_if_needed(
        self,
        step_results: StepOutputMap,
        step_2: JsonMap,
        revenue_multiple_raw: object,
        ebitda_multiple_raw: object,
        context: Optional[JsonMap],
    ) -> None:
        """
        Update Step 2's result in step_results if fallback recovery was used.

        Delegates to Step2ResultUpdater for single responsibility.

        Args:
            step_results: Dictionary mapping step numbers to StepOutput objects
            step_2: Extracted/recovered step_2 dictionary
            revenue_multiple_raw: Revenue multiple value
            ebitda_multiple_raw: EBITDA multiple value
            context: Optional calculation context
        """
        self.step2_updater.update_step_2_result_if_needed(
            step_results, step_2, revenue_multiple_raw, ebitda_multiple_raw, context
        )

    def _transform_to_legacy_format(
        self,
        step_results: StepOutputMap,
        request: ValuationRequest,
        context: Optional[JsonMap] = None,
    ) -> JsonMap:
        """
        Transform modular step results to legacy API format.

        This ensures 100% backward compatibility with existing API consumers.

        Args:
            step_results: Results from all 11 steps (0-10)
            request: Original valuation request
            context: Optional calculation context (for correlation ID extraction)

        Returns:
            Dictionary in legacy MultiplesCalculator format
        """
        # Extract all step results
        extracted_results = self.legacy_transformer.extract_step_results(step_results)

        # Extract step_2 with comprehensive recovery logic
        step_2 = self._extract_step_2_result(step_results, request, context)

        # Extract and validate valuation values
        valuation_values = self.valuation_extractor.extract_valuation_values(
            step_results, extracted_results, request
        )

        # Extract multiples with fallbacks
        multiples = self.valuation_extractor.extract_multiples_with_fallbacks(step_2, request)

        # Add data flow tracer checkpoint
        self.legacy_transformer.add_tracer_checkpoint(step_2, multiples)

        # Update Step 2 result if recovery was used
        self._update_step_2_result_if_needed(
            step_results,
            step_2,
            multiples["revenue_multiple_raw"],
            multiples["ebitda_multiple_raw"],
            context,
        )

        # Build legacy response
        result = self.legacy_transformer.build_legacy_response(
            step_results, extracted_results, step_2, valuation_values, multiples, request
        )

        # Log comprehensive final valuation summary
        self.legacy_transformer.log_transformation_summary(
            request, step_2, valuation_values, multiples, extracted_results, result
        )

        return result
