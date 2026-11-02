"""
Comprehensive Valuation Orchestrator

Orchestrates the entire comprehensive valuation flow:
- Methodology determination
- Execution (via executors)
- Response building (via builders)
- Transparency generation (via builders)
- Error handling (via handlers)
- Performance monitoring (via handlers)

This class extracts the logic from ValuationOrchestrator.process_comprehensive_valuation()
to keep the main orchestrator thin (~200 lines).
"""

import uuid
from typing import Any, Dict, Optional

from src.api.schemas import ValuationRequest, ValuationResponse
from src.services.holding_consolidation_pipeline import apply_holdings_consolidation_to_request
from src.utils.exceptions import DCFCalculationError
from src.utils.valuation_logger import ValuationLogger

from .comprehensive.omni_enrichment import (
    _OmniExecutionContext,
    _apply_startup_valuation_override,
    _canonical_net_multiples_equity,
    _enrich_with_omni_calc,
    _normalize_methodology_token_for_omni,
    _omni_primary_basis_from_executed_methodology,
    _resolve_omni_execution_context,
    reconcile_synthesis_multiples_legs,
)
from .comprehensive.stage_logging import comp_stage_log as _comp_stage_log

# Academic provenance tracking
try:
    from src.services.academic.calculation_provenance_tracker import (
        create_tracker,
        set_current_tracker,
    )

    ACADEMIC_TRACKING_AVAILABLE = True
except ImportError:
    ACADEMIC_TRACKING_AVAILABLE = False

# Import comprehensive modules
from .comprehensive import (
    AlternativeValuationExecutor,
    ConfidenceQualityCalculator,
    HTMLReportGenerator,
    InitializationHandler,
    MethodologyDeterminer,
    PayloadReducer,
    PerformanceMonitor,
    PostProcessingHandler,
)
from .comprehensive import ResponseBuilder as ComprehensiveResponseBuilder
from .comprehensive import ResponseOrchestrator, ResponseValidator
from .comprehensive import TransparencyBuilder as ComprehensiveTransparencyBuilder
from .comprehensive import ValuationExecutor, ValueExtractor, WeightedMetricsCalculator


class ComprehensiveValuationOrchestrator:
    """
    Orchestrates comprehensive valuation flow.

    Responsibilities:
    - Determine methodology
    - Execute valuation via executors
    - Build response via builders
    - Generate transparency via builders
    - Handle errors via handlers
    - Monitor performance via handlers
    """

    def __init__(
        self,
        dcf_executor,
        multiples_executor,
        hybrid_executor,
        response_builder,
        transparency_builder,
        validation_builder,
        error_handler,
        performance_handler,
        cache_manager,
        context_manager,
        adjustment_helpers,
        # Calculators and services
        dcf_calculator,
        multiples_calculator,
        weighted_calculator,
        confidence_scorer,
        quality_assessor,
        validator,
        summary_generator,
        metrics_builder,
        # Additional services
        cache_service=None,
        html_report_service=None,
        logger: Optional[ValuationLogger] = None,
    ):
        """
        Initialize comprehensive valuation orchestrator.

        Args:
            dcf_executor: DCFExecutor instance
            multiples_executor: MultiplesExecutor instance
            hybrid_executor: HybridExecutor instance
            response_builder: ResponseBuilder instance
            transparency_builder: TransparencyBuilder instance
            validation_builder: ValidationBuilder instance
            error_handler: ErrorHandler instance
            performance_handler: PerformanceHandler instance
            cache_manager: CacheManager instance
            context_manager: ContextManager instance
            adjustment_helpers: AdjustmentHelpers instance
            dcf_calculator: DCFCalculator instance
            multiples_calculator: MultiplesCalculator instance
            weighted_calculator: WeightedEBITDACalculator instance
            confidence_scorer: ConfidenceScorer instance
            quality_assessor: QualityAssessor instance
            validator: ValuationValidator instance
            summary_generator: SummaryGenerator instance
            metrics_builder: MetricsBuilder instance
            logger: Optional logger instance
        """
        self.dcf_executor = dcf_executor
        self.multiples_executor = multiples_executor
        self.hybrid_executor = hybrid_executor
        self.response_builder = response_builder
        self.transparency_builder = transparency_builder
        self.validation_builder = validation_builder
        self.error_handler = error_handler
        self.performance_handler = performance_handler
        self.cache_manager = cache_manager
        self.context_manager = context_manager
        self.adjustment_helpers = adjustment_helpers
        self.dcf_calculator = dcf_calculator
        self.multiples_calculator = multiples_calculator
        self.weighted_calculator = weighted_calculator
        self.confidence_scorer = confidence_scorer
        self.quality_assessor = quality_assessor
        self.validator = validator
        self.summary_generator = summary_generator
        self.metrics_builder = metrics_builder
        self.cache_service = cache_service
        self.html_report_service = html_report_service
        self.logger = logger or ValuationLogger(self.__class__.__name__)

        # Initialize comprehensive modules
        self.methodology_determiner = MethodologyDeterminer(
            dcf_executor=self.dcf_executor, logger=self.logger
        )
        self.value_extractor = ValueExtractor(logger=self.logger)
        self.comprehensive_response_builder = ComprehensiveResponseBuilder(
            response_builder=self.response_builder,
            summary_generator=self.summary_generator,
            confidence_scorer=self.confidence_scorer,
            logger=self.logger,
        )
        self.comprehensive_transparency_builder = ComprehensiveTransparencyBuilder(
            transparency_builder=self.transparency_builder, logger=self.logger
        )
        self.response_validator = ResponseValidator(
            validator=self.validator, validation_builder=self.validation_builder, logger=self.logger
        )
        self.html_report_generator = HTMLReportGenerator(
            html_report_service=self.html_report_service, logger=self.logger
        )
        self.payload_reducer = PayloadReducer(logger=self.logger)
        self.performance_monitor = PerformanceMonitor(
            performance_handler=self.performance_handler, logger=self.logger
        )

        # Initialize new comprehensive modules
        self.initialization_handler = InitializationHandler(
            cache_manager=self.cache_manager,
            cache_service=self.cache_service,
            multiples_calculator=self.multiples_calculator,
            context_manager=self.context_manager,
            performance_monitor=self.performance_monitor,
            logger=self.logger,
        )
        self.alternative_valuation_executor = AlternativeValuationExecutor(logger=self.logger)
        self.valuation_executor = ValuationExecutor(
            dcf_executor=self.dcf_executor,
            multiples_executor=self.multiples_executor,
            hybrid_executor=self.hybrid_executor,
            alternative_valuation_executor=self.alternative_valuation_executor,
            performance_monitor=self.performance_monitor,
            logger=self.logger,
        )
        self.weighted_metrics_calculator = WeightedMetricsCalculator(
            weighted_calculator=self.weighted_calculator,
            performance_monitor=self.performance_monitor,
            logger=self.logger,
        )
        self.confidence_quality_calculator = ConfidenceQualityCalculator(
            confidence_scorer=self.confidence_scorer,
            quality_assessor=self.quality_assessor,
            logger=self.logger,
        )
        self.response_orchestrator = ResponseOrchestrator(
            comprehensive_response_builder=self.comprehensive_response_builder,
            comprehensive_transparency_builder=self.comprehensive_transparency_builder,
            response_validator=self.response_validator,
            performance_monitor=self.performance_monitor,
            logger=self.logger,
        )
        self.post_processing_handler = PostProcessingHandler(
            performance_monitor=self.performance_monitor,
            html_report_generator=self.html_report_generator,
            payload_reducer=self.payload_reducer,
            logger=self.logger,
        )

        self.logger.debug("✅ ComprehensiveValuationOrchestrator initialized")

    async def process(
        self, request: ValuationRequest, context: Optional[Dict[str, Any]] = None
    ) -> ValuationResponse:
        """
        Process comprehensive valuation request.

        This method orchestrates the entire valuation flow:
        1. Initialize cache service
        2. Determine methodology
        3. Calculate weighted metrics
        4. Execute valuation methodology
        5. Validate results
        6. Calculate confidence and quality
        7. Build response
        8. Generate transparency data
        9. Sanitize response

        Args:
            request: Comprehensive valuation request
            context: Optional processing context

        Returns:
            Comprehensive valuation response
        """
        correlation_id_preview = getattr(request, "correlation_id", "not_set")
        company_name = getattr(request, "company_name", "missing")

        # DEBUG: "🎬 ORCHESTRATOR START" below is the canonical INFO entry.
        self.logger.debug(
            "Orchestrator process() entry point",
            extra={
                "company_name": company_name,
                "industry": getattr(request, "industry", "missing"),
                "business_model": getattr(request, "business_model", "missing"),
                "business_type_id": getattr(request, "business_type_id", None),
                "has_current_year_data": hasattr(request, "current_year_data")
                and request.current_year_data is not None,
                "has_historical_data": hasattr(request, "historical_years_data")
                and bool(getattr(request, "historical_years_data", None)),
                "correlation_id": correlation_id_preview,
                "request_type": type(request).__name__,
                "request_keys": (
                    list(request.__dict__.keys()) if hasattr(request, "__dict__") else "no_dict"
                ),
            },
        )

        # Initialize processing context and cache service
        overall_start_time = self.performance_monitor.start_timing()
        stage_timings, correlation_id, cache_init_duration = (
            await self.initialization_handler.initialize(request, context, overall_start_time)
        )

        # Initialize academic tracking for this valuation
        academic_tracker = None
        if ACADEMIC_TRACKING_AVAILABLE:
            try:
                valuation_id = str(uuid.uuid4())
                academic_tracker = create_tracker(valuation_id)
                set_current_tracker(academic_tracker)
                # DEBUG: per-request tracker init; the valuation_id appears
                # in downstream INFO lines (e.g. validation result, audit).
                self.logger.debug(
                    f"[ACADEMIC] Provenance tracking initialized | valuation_id={valuation_id}"
                )
            except (ImportError, AttributeError, TypeError) as e:
                # Handle initialization errors gracefully
                self.logger.warning(
                    f"[ACADEMIC] Failed to initialize tracking (initialization error): {e}"
                )
            except Exception as e:
                self.logger.warning(f"[ACADEMIC] Failed to initialize tracking (non-fatal): {e}")

        try:
            valuation_id = str(uuid.uuid4())

            # BET-293: for parent/subsidiary runs, ValuationIQ owns the
            # deterministic financial roll-up, then feeds the consolidated
            # current-year lines into the existing valuation engine.
            request, holdings_consolidation = apply_holdings_consolidation_to_request(
                request,
                logger=self.logger,
            )
            if holdings_consolidation:
                context = dict(context or {})
                context["holdings_consolidation"] = holdings_consolidation

            # Determine methodology using MethodologyDeterminer
            methodology, methodology_downgrade_reason = (
                self.methodology_determiner.determine_methodology(request, context)
            )

            # Get DCF exclusion reason for later use
            should_calculate_dcf_precheck, dcf_exclusion_reason_precheck = (
                self.dcf_executor.should_calculate_dcf(request)
            )

            # Performance monitoring: Methodology determination complete
            methodology_duration = self.performance_monitor.record_stage_timing(
                stage_timings, "methodology_determination", overall_start_time
            )

            # Calculate weighted metrics (early in pipeline, before methodology execution)
            if context is None:
                context = {}
            weighted_metrics = self.weighted_metrics_calculator.calculate_weighted_metrics(
                request, context, correlation_id, stage_timings
            )

            # Execute valuation based on methodology
            valuation_calc_start = self.performance_monitor.start_timing()
            try:
                (
                    detailed_results,
                    executed_methodology,
                    execution_downgrade_reason,
                ) = await self.valuation_executor.execute_valuation(
                    request=request,
                    methodology=methodology,
                    context=context,
                    should_calculate_dcf_precheck=should_calculate_dcf_precheck,
                    dcf_exclusion_reason_precheck=dcf_exclusion_reason_precheck,
                    correlation_id=correlation_id,
                    valuation_calc_start=valuation_calc_start,
                    stage_timings=stage_timings,
                )
            except DCFCalculationError as methodology_error:
                # Use error handler for consistent error handling
                self.error_handler.handle_methodology_execution_error(
                    methodology_error, methodology, request, context
                )
                raise

            methodology = executed_methodology
            if execution_downgrade_reason:
                methodology_downgrade_reason = execution_downgrade_reason
                if methodology == "MULTIPLES":
                    dcf_exclusion_reason_precheck = None
            if holdings_consolidation:
                detailed_results["holdings_consolidation"] = holdings_consolidation

            _comp_stage_log(
                self.logger,
                stage="methodology_execution",
                phase="after",
                correlation_id=correlation_id,
                company=getattr(request, "company_name", None),
                methodology=str(methodology),
            )

            # Validate results (delegated to ValuationValidator)
            _comp_stage_log(
                self.logger,
                stage="validator",
                phase="before_validate_results",
                correlation_id=correlation_id,
                company=getattr(request, "company_name", None),
            )
            await self.validator.validate_results(detailed_results, methodology)
            _comp_stage_log(
                self.logger,
                stage="validator",
                phase="after_validate_results",
                correlation_id=correlation_id,
                company=getattr(request, "company_name", None),
            )

            # Extract values using ValueExtractor
            _comp_stage_log(
                self.logger,
                stage="value_extractor",
                phase="before",
                correlation_id=correlation_id,
                company=getattr(request, "company_name", None),
            )
            (
                enterprise_value,
                equity_value,
                equity_value_low,
                equity_value_mid,
                equity_value_high,
            ) = self.value_extractor.extract_equity_values(detailed_results)
            _comp_stage_log(
                self.logger,
                stage="value_extractor",
                phase="after",
                correlation_id=correlation_id,
                company=getattr(request, "company_name", None),
            )

            # Equity NAV floor for the ambiguous head-office / holding class
            # (NACE 70.10 / bare 'holding' tag) valued on an EARNINGS methodology:
            # a share buyer will not pay less than book NAV. No-op for every other
            # entity and for NAV-based methodologies. See holding_nav_floor.py.
            from .comprehensive.holding_nav_floor import apply_ambiguous_holding_nav_floor

            (
                equity_value_low,
                equity_value_mid,
                equity_value_high,
                _nav_floor_meta,
            ) = apply_ambiguous_holding_nav_floor(
                request=request,
                methodology=methodology,
                equity_value_low=equity_value_low,
                equity_value_mid=equity_value_mid,
                equity_value_high=equity_value_high,
            )
            if _nav_floor_meta is not None:
                detailed_results["ambiguous_holding_nav_floor"] = _nav_floor_meta
                self.logger.info(
                    "📊 Equity floored at book NAV (ambiguous head-office / holding)",
                    extra={
                        "book_nav": _nav_floor_meta.get("book_nav"),
                        "methodology": methodology,
                        "company": getattr(request, "company_name", None),
                    },
                )

            # Calculate confidence and quality
            _comp_stage_log(
                self.logger,
                stage="confidence_quality",
                phase="before",
                correlation_id=correlation_id,
                company=getattr(request, "company_name", None),
            )
            confidence_score, quality_rating, confidence_level = (
                await self.confidence_quality_calculator.calculate_confidence_and_quality(
                    request, detailed_results
                )
            )
            _comp_stage_log(
                self.logger,
                stage="confidence_quality",
                phase="after",
                correlation_id=correlation_id,
                company=getattr(request, "company_name", None),
            )

            # Generate report (delegated to transparency service)
            _comp_stage_log(
                self.logger,
                stage="valuation_report",
                phase="before",
                correlation_id=correlation_id,
                company=getattr(request, "company_name", None),
            )
            report_url = await self.alternative_valuation_executor.generate_valuation_report(
                valuation_id, request, detailed_results, context
            )
            _comp_stage_log(
                self.logger,
                stage="valuation_report",
                phase="after",
                correlation_id=correlation_id,
                company=getattr(request, "company_name", None),
            )

            # CRITICAL FIX: Build financial_metrics and add to detailed_results BEFORE calling SummaryGenerator
            # This ensures SummaryGenerator can access financial_metrics for quantitative analysis
            _comp_stage_log(
                self.logger,
                stage="financial_metrics",
                phase="before_build",
                correlation_id=correlation_id,
                company=getattr(request, "company_name", None),
            )
            financial_metrics = self.metrics_builder.build_financial_metrics(
                request, detailed_results
            )
            detailed_results["financial_metrics"] = financial_metrics
            _comp_stage_log(
                self.logger,
                stage="financial_metrics",
                phase="after_build",
                correlation_id=correlation_id,
                company=getattr(request, "company_name", None),
            )

            # Build and validate response using ResponseOrchestrator
            _comp_stage_log(
                self.logger,
                stage="response_orchestrator",
                phase="before_build_and_validate",
                correlation_id=correlation_id,
                company=getattr(request, "company_name", None),
            )
            response = await self.response_orchestrator.build_and_validate_response(
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
                stage_timings=stage_timings,
            )
            _comp_stage_log(
                self.logger,
                stage="response_orchestrator",
                phase="after_build_and_validate",
                correlation_id=correlation_id,
                company=getattr(request, "company_name", None),
            )

            # Omni-Calc: compute all valuation methods so the edit modal works
            try:
                _enrich_with_omni_calc(
                    request=request,
                    response=response,
                    equity_value_low=equity_value_low,
                    equity_value_mid=equity_value_mid,
                    equity_value_high=equity_value_high,
                    dcf_exclusion_reason=dcf_exclusion_reason_precheck,
                    _logger=self.logger,
                    methodology=methodology,
                )
            except Exception as omni_err:
                self.logger.warning(
                    f"[OmniCalc] Failed to enrich response (non-fatal): {omni_err}",
                    exc_info=True,
                )

            # Finalize response with post-processing
            _comp_stage_log(
                self.logger,
                stage="post_processing",
                phase="before_finalize",
                correlation_id=correlation_id,
                company=getattr(request, "company_name", None),
            )
            response = await self.post_processing_handler.finalize_response(
                response=response,
                request=request,
                valuation_id=valuation_id,
                equity_value_mid=equity_value_mid,
                quality_rating_value=quality_rating.value,
                correlation_id=correlation_id,
                overall_start_time=overall_start_time,
                stage_timings=stage_timings,
            )
            _comp_stage_log(
                self.logger,
                stage="post_processing",
                phase="after_finalize",
                correlation_id=correlation_id,
                company=getattr(request, "company_name", None),
            )

            if ACADEMIC_TRACKING_AVAILABLE and academic_tracker:
                from src.services.academic.attach_validation_issues import (
                    attach_academic_validation_issues_to_response,
                )

                attach_academic_validation_issues_to_response(
                    response,
                    academic_tracker,
                    self.logger,
                    valuation_id=valuation_id,
                )

            return response
        except Exception as e:
            # Broad catch at the orchestrator boundary: all exception types
            # (APIError, ValuationEngineError, DCFCalculationError, ValueError, TypeError, etc.)
            # are logged at ERROR level with a full traceback before propagating.
            # Inner handlers have already run their specific handling; this is the final safety net.
            self.logger.error(
                f"[Orchestrator] Comprehensive valuation failed: {type(e).__name__}: {e}",
                exc_info=True,
            )
            raise
        finally:
            if ACADEMIC_TRACKING_AVAILABLE:
                set_current_tracker(None)
            try:
                from src.services.business_intelligence.database_driven_defaults import (
                    DatabaseDrivenDefaults,
                )

                DatabaseDrivenDefaults.reset()
            except Exception:
                pass
