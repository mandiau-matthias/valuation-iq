from src.utils.exceptions import MultiplesCalculationError

"""
Step 2: Industry Benchmarking & Multiple Selection

This is the CRITICAL FIRST DECISION POINT in the calculation triage system.

This step:
1. Determines Methodology Eligibility (DCF vs Multiples vs Hybrid)
2. Selects Appropriate Multiples (resolved benchmark contract first)
3. Benchmarks Against Comparables (real market data)
4. Provides Market Insights (industry trends, economic context)

Concrete business-type valuations fail closed unless Step 2 receives a resolved
benchmark contract. External/cache/default fallbacks are only allowed
when the caller explicitly accepts disclosed untrusted fallback data.
"""

from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from src.utils.decimal_helpers import from_decimal, to_decimal

if TYPE_CHECKING:
    from src.adapters.fmp_adapter import FMPAdapter
    from src.services.market.market_cache_service import MarketDataCacheService

from src.api.routes.valuation.steps.base_step import (
    CalculationStep,
    StepInput,
    StepOutput,
    StepStatus,
)
from src.api.routes.valuation.steps.step_2_benchmarking.calculators import (
    MultiplesCalculator,
    RangeCalculator,
)

# Import new modular collectors and calculators
from src.api.routes.valuation.steps.step_2_benchmarking.collectors import (
    BUSINESS_TYPE_DEFAULTS,
    INDUSTRY_DEFAULTS,
    ComparableCompaniesCollector,
    IndustryBenchmarkCollector,
    MarketDataCollector,
)
from src.api.routes.valuation.steps.step_2_benchmarking.generators import Step2InsightsGenerator
from src.api.routes.valuation.steps.step_2_benchmarking.handlers import Step2ErrorHandler

# Import new orchestrator, handlers, validators, and generators
from src.api.routes.valuation.steps.step_2_benchmarking.orchestrators import Step2Orchestrator
from src.api.routes.valuation.steps.step_2_benchmarking.utils.benchmark_helpers import (
    calibrate_multiple_for_sme,
    ensure_float,
    map_industry_to_sector,
)
from src.api.routes.valuation.steps.step_2_benchmarking.validators import Step2Validator
from src.api.routes.valuation.triage.business_type_triage import (
    BusinessTypeCategory,
    BusinessTypeTriageEngine,
)
from src.api.routes.valuation.triage.step_registry import register_step
from src.domain.data_quality_assessor import DataQualityAssessor
from src.domain.methodology_eligibility_decider import MethodologyEligibilityDecider
from src.utils.data_flow_tracer import get_tracer
from src.utils.valuation_logger import ValuationLogger

logger = ValuationLogger(__name__)

# Phase 3: Market Data Integration - Optional imports
try:
    from src.adapters.fmp_adapter import FMPAdapter
    from src.services.market.market_cache_service import CacheDataType, MarketDataCacheService

    MARKET_DATA_AVAILABLE = True
except ImportError:
    MARKET_DATA_AVAILABLE = False
    logger.warning("Market data services not available - using fallback defaults")


@register_step
class Step2Benchmarking(CalculationStep):
    """
    Industry Benchmarking and Methodology Decision Step.

    This is the CRITICAL FIRST DECISION POINT in the calculation triage system.

    Responsibilities:
    1. Determine Methodology Eligibility (DCF vs Multiples vs Hybrid)
    2. Select Appropriate Multiples (business-type-aware, market-driven)
    3. Benchmark Against Comparables (real market data)
    4. Provide Market Insights (industry trends, economic context)

    Sources (in priority order):
    1. FMP API (real-time market data)
    2. Redis Cache (cached market data)
    3. Database Business Types (DB-driven multiples)
    4. Business type hardcoded defaults (last resort)
    5. Industry multiples from business rules
    6. Generic industry defaults
    """

    # Note: BUSINESS_TYPE_DEFAULTS and INDUSTRY_DEFAULTS are now defined in
    # IndustryBenchmarkCollector and imported from the collectors module.
    # They are kept as class-level imports for backward compatibility if needed.

    def __init__(
        self,
        multiples_adapter=None,
        business_rules: Optional[Dict[str, Any]] = None,
        fmp_adapter: Optional[Any] = None,
        cache_service: Optional[Any] = None,
    ):
        # Lazy initialization - if adapter not provided, create it
        # This ensures DB integration works even when CalculationTriage instantiates
        # steps without arguments via step_class()
        if multiples_adapter is None:
            try:
                from src.services.business_intelligence.business_type_multiples_adapter import (
                    get_business_type_multiples_adapter,
                )

                self.multiples_adapter = get_business_type_multiples_adapter()
                logger.debug("✅ MultiplesAdapter auto-initialized for DB integration")
            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize MultiplesAdapter: {e}", exc_info=True)
                self.multiples_adapter = None
        else:
            self.multiples_adapter = multiples_adapter
            logger.debug("✅ MultiplesAdapter provided via dependency injection")

        self.business_rules = business_rules or {}
        # Phase 1: Business Type Integration - Reuse BusinessTypeTriageEngine
        self.business_type_triage = BusinessTypeTriageEngine()
        # Phase 2: DCF Eligibility - Integrate MethodologyEligibilityDecider
        self.methodology_decider = MethodologyEligibilityDecider()
        # Phase 3: Market Data Integration - Optional FMP adapter and cache service
        self.fmp_adapter = fmp_adapter
        self.cache_service = cache_service
        # Market data is available if module is available AND services are injected
        self.market_data_available = MARKET_DATA_AVAILABLE and (
            fmp_adapter is not None or cache_service is not None
        )

        # Initialize modular collectors and calculators
        # MarketDataCollector for FMP API and cache operations
        self.market_data_collector = MarketDataCollector(
            fmp_adapter=fmp_adapter, cache_service=cache_service
        )

        # IndustryBenchmarkCollector for priority cascade multiples selection
        self.industry_benchmark_collector = IndustryBenchmarkCollector(
            multiples_adapter=self.multiples_adapter,
            fmp_adapter=fmp_adapter,
            cache_service=cache_service,
            market_data_collector=self.market_data_collector,
            business_rules=self.business_rules,
        )

        # ComparableCompaniesCollector for finding comparables and calculating percentiles
        self.comparable_companies_collector = ComparableCompaniesCollector(fmp_adapter=fmp_adapter)

        # MultiplesCalculator for primary method determination
        self.multiples_calculator = MultiplesCalculator(
            business_type_triage=self.business_type_triage
        )

        # RangeCalculator for range calculations (wraps ValuationRangeCalculator)
        self.range_calculator = RangeCalculator()

        # Initialize new orchestrator, handlers, validators, and generators
        self.insights_generator = Step2InsightsGenerator(logger)
        self.validator = Step2Validator(logger)
        self.error_handler = Step2ErrorHandler(
            industry_benchmark_collector=self.industry_benchmark_collector,
            business_type_triage=self.business_type_triage,
            step_name=self.step_name,
            logger=logger,
        )
        self.orchestrator = Step2Orchestrator(
            industry_benchmark_collector=self.industry_benchmark_collector,
            comparable_companies_collector=self.comparable_companies_collector,
            market_data_collector=self.market_data_collector,
            multiples_calculator=self.multiples_calculator,
            business_type_triage=self.business_type_triage,
            methodology_decider=self.methodology_decider,
            insights_generator=self.insights_generator,
            validator=self.validator,
            step_name=self.step_name,
            logger=logger,
        )

        # DEBUG: fires twice at startup (wrapper + comprehensive orchestrator
        # both construct Step 2). Init detail, not request-time signal.
        logger.debug(
            "✅ Step 2: Modular collectors, calculators, orchestrator, handlers, validators, and generators initialized"
        )

    @property
    def step_number(self) -> int:
        return 2

    @property
    def step_name(self) -> str:
        return "Industry Benchmarking & Multiple Selection"

    @property
    def dependencies(self) -> List[int]:
        return [0, 1]  # Depends on data quality (Step 0) and input validation (Step 1)

    def should_execute(self, input_data: StepInput) -> bool:
        return True  # Always execute benchmarking

    async def execute(self, input_data: StepInput) -> StepOutput:
        """
        Execute Step 2: Industry Benchmarking & Methodology Decision.

        This is the CRITICAL FIRST DECISION POINT in the calculation triage system.

        Responsibilities:
        1. Determine Methodology Eligibility (DCF vs Multiples vs Hybrid)
        2. Select Appropriate Multiples (business-type-aware, market-driven)
        3. Benchmark Against Comparables (real market data)
        4. Provide Market Insights (industry trends, economic context)
        """
        request = input_data.request
        context = input_data.context or {}
        correlation_id = context.get("correlation_id")

        logger.info(
            "🔍 Starting Step 2: Industry Benchmarking & Multiple Selection",
            extra={
                "step_number": 2,
                "step_name": self.step_name,
                "company_name": getattr(request, "company_name", "N/A"),
                "dependencies": self.dependencies,
                "available_previous_steps": list(input_data.previous_results.keys()),
                "market_data_available": self.market_data_available,
                "correlation_id": correlation_id,
            },
        )

        # Track result dict and metadata for exception handling
        result_dict = None
        metadata_dict = None
        multiples_data_backup = None

        # Initialize variables before try block to ensure they're always defined
        result_dict: Optional[Dict[str, Any]] = None
        metadata_dict: Optional[Dict[str, Any]] = None
        multiples_data_backup: Optional[Dict[str, Any]] = None

        try:
            # Get Step 1 result for early validation
            step1_result = self.get_previous_step_result(1, input_data.previous_results)

            # Handle early fallback if Step 1 data is missing or invalid
            early_fallback = self.error_handler.handle_step_1_missing(
                step1_result, request, correlation_id
            )
            if early_fallback:
                return early_fallback

            # Validate Step 0 and Step 1 data
            step0_result, step_0_failed = self.validator.validate_step_0_data(
                self.get_previous_step_result(0, input_data.previous_results),
                input_data.previous_results,
            )

            is_valid, validated_step1_result = self.validator.validate_step_1_data(
                step1_result, request
            )
            if not is_valid:
                return self.error_handler.handle_invalid_revenue(
                    request, step1_result.get("revenue", 0) if step1_result else 0, correlation_id
                )

            # Orchestrate main execution
            logger.debug(
                "Step 2: About to call orchestrate_execution",
                extra={
                    "step_number": 2,
                    "correlation_id": correlation_id,
                    "has_orchestrator": self.orchestrator is not None,
                    "orchestrator_type": (
                        type(self.orchestrator).__name__ if self.orchestrator else None
                    ),
                    "has_input_data": input_data is not None,
                    "has_step0_result": step0_result is not None,
                    "has_step1_result": validated_step1_result is not None,
                },
            )

            # Initialize variables before try block to ensure they're available in exception handler
            result_dict = None
            metadata_dict = None
            multiples_data_backup = None

            try:
                result_dict, metadata_dict, multiples_data_backup = (
                    await self.orchestrator.orchestrate_execution(
                        input_data=input_data,
                        step0_result=step0_result,
                        step1_result=validated_step1_result,
                        correlation_id=correlation_id,
                    )
                )

                logger.debug(
                    "Step 2: orchestrate_execution completed",
                    extra={
                        "step_number": 2,
                        "correlation_id": correlation_id,
                        "result_dict_size": len(result_dict) if result_dict else 0,
                        "result_dict_keys": list(result_dict.keys()) if result_dict else [],
                        "has_metadata": metadata_dict is not None,
                        "has_multiples_backup": multiples_data_backup is not None,
                        "multiples_backup_keys": (
                            list(multiples_data_backup.keys()) if multiples_data_backup else []
                        ),
                    },
                )
            except Exception as orchestration_error:
                if multiples_data_backup is None:
                    multiples_data_backup = {}

                logger.error(
                    "Step 2: orchestrate_execution raised exception",
                    extra={
                        "step_number": 2,
                        "correlation_id": correlation_id,
                        "error_type": type(orchestration_error).__name__,
                        "error_message": str(orchestration_error),
                        "error_stack": (
                            str(orchestration_error.__traceback__)
                            if hasattr(orchestration_error, "__traceback__")
                            else None
                        ),
                        "has_multiples_backup": multiples_data_backup is not None,
                        "multiples_backup_keys": (
                            list(multiples_data_backup.keys()) if multiples_data_backup else []
                        ),
                    },
                    exc_info=True,
                )
                # Re-raise MultiplesCalculationError to be caught by outer handler
                if isinstance(orchestration_error, MultiplesCalculationError):
                    raise
                # Wrap other exceptions
                raise MultiplesCalculationError(
                    f"Step 2 orchestration failed: {str(orchestration_error)}",
                    context={
                        "step": "step_2_orchestration",
                        "error_type": type(orchestration_error).__name__,
                        "correlation_id": correlation_id,
                    },
                ) from orchestration_error

            # Final validation before return
            if not result_dict or len(result_dict) == 0:
                logger.error(
                    "Step 2: result_dict is empty after orchestration",
                    extra={
                        "step_number": 2,
                        "correlation_id": correlation_id,
                        "result_dict": result_dict,
                        "metadata_dict": metadata_dict,
                        "multiples_data_backup": multiples_data_backup,
                        "multiples_backup_keys": (
                            list(multiples_data_backup.keys()) if multiples_data_backup else []
                        ),
                        "multiples_backup_size": (
                            len(multiples_data_backup) if multiples_data_backup else 0
                        ),
                        "has_ev_ebitda_in_backup": (
                            "ev_ebitda" in multiples_data_backup if multiples_data_backup else False
                        ),
                        "has_ev_revenue_in_backup": (
                            "ev_revenue" in multiples_data_backup
                            if multiples_data_backup
                            else False
                        ),
                    },
                )
                # If we have multiples_data_backup with valid data, mark as COMPLETED
                if multiples_data_backup and len(multiples_data_backup) > 0:
                    has_backup_multiples = bool(
                        multiples_data_backup.get("ev_ebitda")
                        or multiples_data_backup.get("ev_revenue")
                    )
                    if has_backup_multiples:
                        logger.info(
                            "✅ Step 2: Empty result_dict but valid multiples_data_backup available, using error handler recovery",
                            extra={
                                "step_number": 2,
                                "correlation_id": correlation_id,
                                "backup_data_source": multiples_data_backup.get("data_source"),
                                "backup_ev_ebitda": (
                                    str(multiples_data_backup.get("ev_ebitda"))
                                    if multiples_data_backup.get("ev_ebitda")
                                    else None
                                ),
                                "backup_ev_revenue": (
                                    str(multiples_data_backup.get("ev_revenue"))
                                    if multiples_data_backup.get("ev_revenue")
                                    else None
                                ),
                            },
                        )
                error_handler_output = self.error_handler.handle_execution_exception(
                    Exception("Result dict is empty"),
                    request,
                    result_dict,
                    multiples_data_backup,
                    correlation_id,
                )
                logger.info(
                    "Step 2: Error handler returned StepOutput",
                    extra={
                        "step_number": 2,
                        "correlation_id": correlation_id,
                        "error_handler_status": (
                            error_handler_output.status.value
                            if hasattr(error_handler_output, "status")
                            else "unknown"
                        ),
                        "error_handler_result_keys": (
                            list(error_handler_output.result.keys())
                            if hasattr(error_handler_output, "result")
                            and error_handler_output.result
                            else []
                        ),
                        "error_handler_result_size": (
                            len(error_handler_output.result)
                            if hasattr(error_handler_output, "result")
                            and error_handler_output.result
                            else 0
                        ),
                    },
                )
                return error_handler_output

            # Check if result was recovered (has recovery_applied flag or warning about recovery)
            was_recovered = (
                result_dict.get("recovery_applied", False)
                or "recovered" in result_dict.get("warning", "").lower()
                or "recovery" in result_dict.get("data_source", "").lower()
            )

            # Check if we have valid multiples data (even if recovered)
            has_valid_multiples = bool(
                result_dict.get("ev_ebitda_multiple") or result_dict.get("ev_revenue_multiple")
            )

            # If we have valid data (even if recovered), mark as COMPLETED
            # This ensures that successful database lookups are always marked as completed
            if has_valid_multiples:
                logger.debug(
                    "✅ Step 2: Has valid multiples data, marking as COMPLETED",
                    extra={
                        "step_number": 2,
                        "correlation_id": correlation_id,
                        "data_source": result_dict.get("data_source"),
                        "ev_ebitda_multiple": (
                            str(result_dict.get("ev_ebitda_multiple"))
                            if result_dict.get("ev_ebitda_multiple")
                            else None
                        ),
                        "ev_revenue_multiple": (
                            str(result_dict.get("ev_revenue_multiple"))
                            if result_dict.get("ev_revenue_multiple")
                            else None
                        ),
                        "was_recovered": was_recovered,
                        "recovery_applied": result_dict.get("recovery_applied", False),
                    },
                )
                # Create StepOutput - always mark as COMPLETED if we have valid data
                step_output = StepOutput(
                    step_number=2,
                    step_name=self.step_name,
                    status=StepStatus.COMPLETED,
                    result=result_dict,
                    metadata={
                        **(metadata_dict or {}),
                        "was_recovered": was_recovered,
                    },
                )

                if was_recovered:
                    logger.warning(
                        "⚠️ Step 2: Result was recovered from backup but marked as COMPLETED",
                        extra={
                            "step_number": 2,
                            "correlation_id": correlation_id,
                            "data_source": result_dict.get("data_source"),
                            "has_valid_multiples": has_valid_multiples,
                        },
                    )

                return step_output
            else:
                # No valid multiples - this is a real failure
                logger.error(
                    "❌ Step 2: No valid multiples data found, marking as FAILED",
                    extra={
                        "step_number": 2,
                        "correlation_id": correlation_id,
                        "result_dict_keys": list(result_dict.keys()) if result_dict else [],
                        "result_dict_size": len(result_dict) if result_dict else 0,
                    },
                )
                return self.error_handler.handle_execution_exception(
                    Exception("No valid multiples data in result_dict"),
                    request,
                    result_dict,
                    multiples_data_backup,
                    correlation_id,
                )

        except MultiplesCalculationError as e:
            if multiples_data_backup is None:
                multiples_data_backup = {}
            logger.error(
                "Step 2: MultiplesCalculationError caught",
                extra={
                    "step_number": 2,
                    "correlation_id": correlation_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "result_dict_exists": result_dict is not None,
                    "result_dict_size": len(result_dict) if result_dict else 0,
                    "multiples_backup_exists": multiples_data_backup is not None,
                    "multiples_backup_keys": (
                        list(multiples_data_backup.keys()) if multiples_data_backup else []
                    ),
                },
                exc_info=True,
            )
            return self.error_handler.handle_execution_exception(
                e, request, result_dict, multiples_data_backup, correlation_id
            )
        except Exception as e:
            if multiples_data_backup is None:
                multiples_data_backup = {}
            logger.error(
                "Step 2: Unexpected exception caught",
                extra={
                    "step_number": 2,
                    "correlation_id": correlation_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "result_dict_exists": result_dict is not None,
                    "result_dict_size": len(result_dict) if result_dict else 0,
                    "multiples_backup_exists": multiples_data_backup is not None,
                    "multiples_backup_keys": (
                        list(multiples_data_backup.keys()) if multiples_data_backup else []
                    ),
                },
                exc_info=True,
            )
            # Convert to MultiplesCalculationError for consistent handling
            return self.error_handler.handle_execution_exception(
                MultiplesCalculationError(
                    f"Unexpected error in Step 2: {str(e)}",
                    context={
                        "step": "step_2_execution",
                        "error_type": type(e).__name__,
                        "correlation_id": correlation_id,
                    },
                ),
                request,
                result_dict,
                multiples_data_backup,
                correlation_id,
            )

    # These methods delegate to the new modular calculators/collectors
    def _determine_primary_method(
        self,
        ebitda: Optional[Decimal],
        ebitda_margin: Decimal,
        revenue: Optional[Decimal] = None,
        business_type_id: Optional[str] = None,
        business_category: Optional[BusinessTypeCategory] = None,
        growth_rate: Optional[Decimal] = None,
    ) -> str:
        """
        Backward compatibility wrapper for determine_primary_method.

        Delegates to MultiplesCalculator.determine_primary_method().
        This method is kept for test compatibility.
        """
        return self.multiples_calculator.determine_primary_method(
            ebitda=ebitda,
            ebitda_margin=ebitda_margin,
            revenue=revenue,
            business_type_id=business_type_id,
            business_category=business_category,
            growth_rate=growth_rate,
        )
