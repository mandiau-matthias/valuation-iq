"""
Valuation Orchestrator (Refactored)

Lightweight orchestrator delegating to specialized modules.

REFACTORING SUMMARY:
- Original: 1,272 lines monolithic class
- Refactored: ~400 lines coordinator + 10 specialized modules
- Benefits: Better maintainability, testability, separation of concerns

ARCHITECTURE:
- calculators/: Quick, DCF, Multiples calculators
- adjustments/: Business type adjuster
- quality/: Confidence scorer, quality assessor, validator
- reporting/: Summary generator
- utils/: Metrics builder, config loader

BACKWARD COMPATIBILITY: 100% maintained
"""

import re
from decimal import Decimal
from threading import Lock
from typing import Any, Dict, List, Optional

from src.api.schemas import (
    DCFValuationResponse,
    MultiplesValuationResponse,
    QuickValuationRequest,
    QuickValuationResponse,
    ValuationRequest,
    ValuationResponse,
)

# Business Type Intelligence Integration
from src.database.business_types_repository import get_business_types_repository
from src.domain.transparency import CalculationStep
from src.services.business_intelligence.business_type_multiples_adapter import (
    get_business_type_multiples_adapter,
)
from src.services.business_intelligence.integration.business_type_database_service import (
    get_business_type_database_service,
)
from src.services.infrastructure.html_report_service import get_html_report_service
from src.utils.exceptions import (
    CalculationError,
    DCFCalculationError,
    MultiplesCalculationError,
    SynthesisError,
)
from src.utils.valuation_logger import ValuationLogger

from .adjustments import BusinessTypeAdjuster
from .benchmark_contract_utils import (
    REQUIRED_BENCHMARK_PROVENANCE_FIELDS,
    diagnose_request_benchmark_contract,
    extract_request_resolved_benchmark_contract,
    request_allows_untrusted_multiples_fallback,
)

# Import refactored modules
from .calculators import (
    DCFCalculator,
    MultiplesCalculator,
    QuickValuationCalculator,
    WeightedEBITDACalculator,
)
from .hybrid import HybridMethodologyOrchestrator
from .orchestration.builders import ResponseBuilder, TransparencyBuilder, ValidationBuilder

# Import new orchestration modules (Phase 2 refactoring)
from .orchestration.executors import (
    ComprehensiveValuationOrchestrator,
    DCFExecutor,
    HybridExecutor,
    MultiplesExecutor,
)
from .orchestration.handlers import ErrorHandler, PerformanceHandler
from .orchestration.utils import AdjustmentHelpers, CacheManager, ContextManager
from .quality import ConfidenceScorer, QualityAssessor, ValuationValidator
from .quick_valuation_processor import (
    QuickValuationProcessor,
    determine_quick_valuation_methodology,
    quick_request_display_name,
)
from .reporting import SummaryGenerator
from .steps.base_step import StepOutput
from .utils import ConfigLoader, MetricsBuilder
from .valuation_types import BusinessType, ValuationMethod

logger = ValuationLogger(__name__)
_quick_request_display_name = quick_request_display_name

# UUID validation pattern (standard UUID v4 format)
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


def is_uuid(value: Optional[str]) -> bool:
    """Check if a string is a valid UUID format"""
    if not value:
        return False
    return bool(UUID_PATTERN.match(value))


def _request_would_route_asset_based(request: Any) -> bool:
    """Detect requests that the methodology determiner will route to
    ASSET_BASED, ahead of the full orchestrator running.

    Mirrors the NACE + industry-tag branches of
    `is_asset_heavy_holding_activity`. Does NOT replicate the balance-sheet
    heuristic (book_equity ≥ 5× EBITDA …) because that depends on
    cross-field math and shouldn't gate the preflight check — patrimonium
    requests that lack NACE/industry tags will still hit the gate, which
    is fine: those are the requests that genuinely need a contract or an
    explicit fallback override.

    Used by `_request_uses_multiples` to short-circuit the Delphi
    benchmark contract preflight for patrimony / financial-holding
    entities that the engine will value via NAV, not multiples.
    """
    from src.domain.asset_based_support import is_asset_heavy_holding_activity

    activity_code = (
        getattr(request, "canonical_nace_code", None)
        or getattr(request, "nace_code", None)
        or getattr(request, "activity_code", None)
    )
    industry = getattr(request, "industry", None)
    return is_asset_heavy_holding_activity(
        activity_code=str(activity_code) if activity_code else None,
        industry=str(industry) if industry else None,
    )


def _request_uses_multiples(request: Any) -> bool:
    if getattr(request, "use_multiples", True) is False:
        return False
    methodology = str(getattr(request, "methodology", "") or "").upper()
    selected_method = str(getattr(request, "selected_method", "") or "").lower()
    if methodology in {"DCF", "ASSET_BASED"} and not selected_method.endswith("_multiple"):
        return False
    # Patrimonium / financial-holding entities route to ASSET_BASED in the
    # methodology determiner — they don't compute multiples at all. Skip
    # the Delphi benchmark-contract preflight for them unless the caller
    # explicitly asked for a multiples method by name (override wins).
    # Closes BET-258 for asset-heavy routes — keeps the preflight strict
    # for actual multiples cases while letting NAV-routed patrimony
    # requests through without `allow_untrusted_multiples_fallback=true`.
    if _request_would_route_asset_based(request) and not selected_method.endswith("_multiple"):
        return False
    return True


class ValuationOrchestrator:
    """
    Lightweight orchestrator coordinating specialized valuation modules

    DESIGN PATTERN: Facade + Delegation
    - Provides unified interface to clients
    - Delegates complex logic to specialized modules
    - Maintains backward compatibility with original API
    """

    def __init__(self):
        """Initialize orchestrator and all specialized modules"""
        self.logger = logger
        # DEBUG: detailed-build start; "🎉 Refactored orchestrator ready" at
        # the end is the canonical boot banner.
        self.logger.debug("🎬 Initializing refactored valuation orchestrator")

        # Load configuration
        config_loader = ConfigLoader()
        self.valuation_services = config_loader.load_valuation_services()
        self.business_rules = config_loader.load_business_rules()
        self.quality_standards = config_loader.load_quality_standards()

        self.logger.debug(
            "✅ Configuration loaded",
            extra={
                "services": len(self.valuation_services),
                "business_rules": len(self.business_rules),
            },
        )

        # Initialize Business Type Intelligence
        try:
            self.business_types_repo = get_business_types_repository()
            self.multiples_adapter = get_business_type_multiples_adapter()
            self.business_type_db_service = get_business_type_database_service()
            self.logger.debug("✅ Business Type Intelligence initialized")
        except Exception as e:
            self.logger.warning(f"⚠️ Business Type Intelligence initialization failed: {e}")
            self.business_types_repo = None
            self.multiples_adapter = None
            self.business_type_db_service = None

        # Initialize Market Data Services (Phase 3 - Optional)
        # Note: Cache service requires async Redis initialization, so it's initialized lazily
        self.fmp_adapter = None
        self.cache_service = None
        self._cache_service_initialized = False

        try:
            from src.adapters.fmp_adapter import FMPAdapter

            # Initialize FMP adapter (synchronous)
            self.fmp_adapter = FMPAdapter()
            self.logger.debug("✅ FMP Adapter initialized")
        except ImportError as e:
            self.logger.warning(f"⚠️ FMP Adapter not available: {e}")
        except Exception as e:
            self.logger.warning(f"⚠️ FMP Adapter initialization failed: {e}")

        # Cache service will be initialized lazily (requires async Redis connection)

        # Initialize HTML Report Service
        try:
            self.html_report_service = get_html_report_service()
            # CRITICAL: Verify service is properly initialized and has required methods
            if self.html_report_service is None:
                raise ValueError("get_html_report_service() returned None")
            if not hasattr(self.html_report_service, "generate_both_reports"):
                raise AttributeError("HTMLReportService missing generate_both_reports method")

            self.logger.debug(
                "✅ HTML Report Service initialized",
                extra={
                    "html_report_service_type": type(self.html_report_service).__name__,
                    "html_report_service_is_none": self.html_report_service is None,
                    "has_generate_both_reports": hasattr(
                        self.html_report_service, "generate_both_reports"
                    ),
                    "has_template_service": hasattr(self.html_report_service, "template_service"),
                    "template_service_is_none": getattr(
                        self.html_report_service, "template_service", None
                    )
                    is None,
                },
            )
        except Exception as e:
            self.logger.error(
                f"❌ HTML Report Service initialization failed: {e}",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "html_report_service_is_none": True,
                    "impact": "html_report will not be generated - frontend will show report unavailable",
                },
                exc_info=True,
            )
            self.html_report_service = None

        # DEBUG: boot-time service diagnostic.
        self.logger.debug(
            "🔍 [HTML-SERVICE-INIT] HTML Report Service initialization check",
            extra={
                "html_report_service_is_none": self.html_report_service is None,
                "html_report_service_type": (
                    type(self.html_report_service).__name__ if self.html_report_service else "None"
                ),
                "will_be_passed_to_comprehensive": True,
            },
        )

        # Initialize specialized modules
        self.quick_calculator = QuickValuationCalculator(
            self.business_rules, self.multiples_adapter, self.business_types_repo
        )
        self.dcf_calculator = DCFCalculator()
        self.multiples_calculator = MultiplesCalculator(
            multiples_adapter=self.multiples_adapter,
            business_rules=self.business_rules,
            business_types_repo=self.business_types_repo,  # Pass repo for industry-specific calibration
            fmp_adapter=self.fmp_adapter,  # Phase 3: Market Data Integration
            cache_service=self.cache_service,  # Phase 3: Market Data Integration
        )
        self.weighted_calculator = WeightedEBITDACalculator()
        self.business_adjuster = BusinessTypeAdjuster(self.business_rules)
        self.quick_valuation_processor = QuickValuationProcessor(
            quick_calculator=self.quick_calculator,
            business_adjuster=self.business_adjuster,
            logger=self.logger,
        )
        self.confidence_scorer = ConfidenceScorer()
        self.quality_assessor = QualityAssessor()
        self.validator = ValuationValidator()
        self.summary_generator = SummaryGenerator()
        self.metrics_builder = MetricsBuilder()

        # Initialize Hybrid Methodology Orchestrator (Phase 2 refactoring)
        self.hybrid_orchestrator = HybridMethodologyOrchestrator(
            dcf_calculator=self.dcf_calculator,
            multiples_calculator=self.multiples_calculator,
            confidence_scorer=self.confidence_scorer,
            business_types_repo=self.business_types_repo,
            multiples_adapter=self.multiples_adapter,
            fmp_adapter=self.fmp_adapter,
        )
        self.logger.debug("✅ Hybrid Methodology Orchestrator initialized")

        # Initialize new orchestration modules (Phase 2 refactoring)
        # Executors
        self.dcf_executor = DCFExecutor(self.dcf_calculator, self.logger)
        self.multiples_executor = MultiplesExecutor(self.multiples_calculator, self.logger)
        self.hybrid_executor = HybridExecutor(self.hybrid_orchestrator, self.logger)

        # Builders
        self.response_builder = ResponseBuilder(
            self.summary_generator, self.confidence_scorer, self.logger
        )
        self.transparency_builder = TransparencyBuilder(self.logger)
        self.validation_builder = ValidationBuilder(self.logger)

        # Handlers
        self.error_handler = ErrorHandler(self.logger)
        self.performance_handler = PerformanceHandler(self.logger)

        # Utils
        self.cache_manager = CacheManager(self.logger)
        self.context_manager = ContextManager(self.logger)
        self.adjustment_helpers = AdjustmentHelpers(self.logger)

        # Initialize Comprehensive Valuation Orchestrator (Phase 7 refactoring)
        self.comprehensive_orchestrator = ComprehensiveValuationOrchestrator(
            dcf_executor=self.dcf_executor,
            multiples_executor=self.multiples_executor,
            hybrid_executor=self.hybrid_executor,
            response_builder=self.response_builder,
            transparency_builder=self.transparency_builder,
            validation_builder=self.validation_builder,
            error_handler=self.error_handler,
            performance_handler=self.performance_handler,
            cache_manager=self.cache_manager,
            context_manager=self.context_manager,
            adjustment_helpers=self.adjustment_helpers,
            dcf_calculator=self.dcf_calculator,
            multiples_calculator=self.multiples_calculator,
            weighted_calculator=self.weighted_calculator,
            confidence_scorer=self.confidence_scorer,
            quality_assessor=self.quality_assessor,
            validator=self.validator,
            summary_generator=self.summary_generator,
            metrics_builder=self.metrics_builder,
            cache_service=self.cache_service,
            html_report_service=self.html_report_service,
            logger=self.logger,
        )

        # Single startup banner: ComprehensiveValuationOrchestrator logs its
        # own init line. Three confirmation lines here add no signal.
        self.logger.info("🎉 Refactored orchestrator ready")

    async def process_quick_valuation(
        self, request: QuickValuationRequest, context: Optional[Dict[str, Any]] = None
    ) -> QuickValuationResponse:
        """Process quick valuation request through the dedicated processor."""
        return await self.quick_valuation_processor.process(
            request,
            context,
            methodology_selector=self._determine_quick_valuation_methodology,
        )

    async def _ensure_cache_service_initialized(self):
        """
        Lazy initialization of cache service (requires async Redis connection).

        Delegates to CacheManager for consistency.
        """
        self.cache_service = await self.cache_manager.ensure_cache_service_initialized(
            self.cache_service, self.multiples_calculator
        )
        self._cache_service_initialized = self.cache_manager._cache_service_initialized

    async def process_comprehensive_valuation(
        self, request: ValuationRequest, context: Optional[Dict[str, Any]] = None
    ) -> ValuationResponse:
        """
        Process comprehensive valuation request (REFACTORED)

        This method delegates to the comprehensive valuation orchestrator
        which handles the entire valuation flow.

        Args:
            request: Comprehensive valuation request
            context: Optional processing context

        Returns:
            Comprehensive valuation response
        """
        if (
            _request_uses_multiples(request)
            and not request_allows_untrusted_multiples_fallback(request)
            and extract_request_resolved_benchmark_contract(request) is None
        ):
            raise MultiplesCalculationError(
                "Resolved benchmark contract required for multiples valuation. "
                "ValuationIQ will not publish generic, FMP, or hardcoded fallback "
                "multiples unless allow_untrusted_multiples_fallback=true is explicit.",
                step="comprehensive_valuation_preflight",
                calculation_type="Multiples",
                context={
                    "code": "BENCHMARK_CONTRACT_REQUIRED",
                    "country_code": getattr(request, "country_code", None),
                    "business_type_id": getattr(request, "business_type_id", None),
                    "methodology": getattr(request, "methodology", None),
                    "required_contract_fields": list(REQUIRED_BENCHMARK_PROVENANCE_FIELDS),
                    # Self-diagnosing: names the exact provenance field(s) the
                    # resolved contract is missing (e.g. source_mix / evidence_summary).
                    **diagnose_request_benchmark_contract(request),
                },
            )
        result = await self.comprehensive_orchestrator.process(request, context)
        return result

    def _extract_current_year_data(
        self, request: ValuationRequest, detailed_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Backward compatibility wrapper for current year data extraction.

        Delegates to ResponseBuilder.extract_current_year_data().
        """
        return self.response_builder.extract_current_year_data(request, detailed_results)

    def _safe_create_dcf_valuation(
        self, dcf_data: Optional[Dict[str, Any]]
    ) -> Optional[DCFValuationResponse]:
        """
        Backward compatibility wrapper for DCF valuation creation.

        Delegates to ResponseBuilder.safe_create_dcf_valuation().
        """
        return self.response_builder.safe_create_dcf_valuation(dcf_data)

    def _safe_create_multiples_valuation(
        self, multiples_data: Optional[Dict[str, Any]]
    ) -> Optional[MultiplesValuationResponse]:
        """
        Backward compatibility wrapper for Multiples valuation creation.

        Delegates to ResponseBuilder.safe_create_multiples_valuation().
        """
        return self.response_builder.safe_create_multiples_valuation(multiples_data)

    # Helper methods (preserved from original for backward compatibility)

    async def _determine_quick_valuation_methodology(
        self, business_type: BusinessType, industry: str
    ) -> ValuationMethod:
        """Determine appropriate quick valuation methodology."""
        return await determine_quick_valuation_methodology(business_type, industry)

    async def _execute_asset_based_valuation(
        self, request: ValuationRequest, context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Execute asset-based valuation (placeholder)"""
        self.logger.info("📊 Executing asset-based valuation")
        # Simplified implementation
        from src.domain.range_calculator import ValuationRangeCalculator

        total_assets = getattr(request.current_year_data, "total_assets", 0) or Decimal("0.0")
        total_debt = getattr(request.current_year_data, "total_debt", 0) or Decimal("0.0")
        equity_value = max(total_assets - total_debt, Decimal("0.0"))

        range_calc = ValuationRangeCalculator()
        valuation_range = range_calc.calculate_range(equity_value, "low")

        return {
            "methodology": "Asset-Based",
            "enterprise_value": equity_value,
            "equity_value": equity_value,
            **valuation_range,
            "per_share_value": None,
        }

    async def _execute_market_valuation(
        self, request: ValuationRequest, context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Execute market valuation (placeholder)"""
        self.logger.info("📊 Executing market valuation")
        from src.domain.range_calculator import ValuationRangeCalculator

        equity_value = request.current_year_data.revenue * Decimal("1.8")
        range_calc = ValuationRangeCalculator()
        valuation_range = range_calc.calculate_range(equity_value, "medium")

        return {
            "methodology": "Market",
            "enterprise_value": equity_value * Decimal("1.1"),
            "equity_value": equity_value,
            **valuation_range,
            "per_share_value": None,
        }

    async def _execute_income_valuation(
        self, request: ValuationRequest, context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Execute income valuation (placeholder)"""
        self.logger.info("📊 Executing income valuation")
        from src.domain.range_calculator import ValuationRangeCalculator

        net_income = getattr(request.current_year_data, "net_income", None)
        if net_income is None:
            net_income = request.current_year_data.ebitda * Decimal("0.6")
        equity_value = net_income * Decimal("8.0")

        range_calc = ValuationRangeCalculator()
        valuation_range = range_calc.calculate_range(equity_value, "medium")

        return {
            "methodology": "Income",
            "enterprise_value": equity_value * Decimal("1.1"),
            "equity_value": equity_value,
            **valuation_range,
            "per_share_value": None,
        }

    async def _execute_cost_valuation(
        self, request: ValuationRequest, context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Execute cost valuation (placeholder)"""
        self.logger.info("📊 Executing cost valuation")
        from src.domain.range_calculator import ValuationRangeCalculator

        total_assets = getattr(request.current_year_data, "total_assets", None)
        if total_assets is None:
            total_assets = request.current_year_data.revenue * Decimal("1.5")
        equity_value = total_assets * Decimal("0.9")

        range_calc = ValuationRangeCalculator()
        valuation_range = range_calc.calculate_range(equity_value, "low")

        return {
            "methodology": "Cost",
            "enterprise_value": equity_value,
            "equity_value": equity_value,
            **valuation_range,
            "per_share_value": None,
        }

    def _should_calculate_dcf(self, request: ValuationRequest) -> tuple[bool, Optional[str]]:
        """
        Backward compatibility wrapper for DCF eligibility.

        Delegates to DCFExecutor.should_calculate_dcf().
        """
        return self.dcf_executor.should_calculate_dcf(request)

    def _generate_methodology_rationale(
        self,
        request: ValuationRequest,
        dcf_included: bool,
        dcf_exclusion_reason: Optional[str],
        dcf_weight: Decimal,
        multiples_weight: Decimal,
        requested_methodology: Optional[str] = None,
    ) -> str:
        """
        Backward compatibility wrapper for methodology rationale generation.

        Delegates to AdjustmentHelpers.generate_methodology_rationale().
        """
        return self.adjustment_helpers.generate_methodology_rationale(
            request,
            dcf_included,
            dcf_exclusion_reason,
            dcf_weight,
            multiples_weight,
            requested_methodology,
        )

    def _get_size_discount_reason(self, revenue: Decimal) -> str:
        """
        Backward compatibility wrapper for size discount reason.

        Delegates to AdjustmentHelpers.get_size_discount_reason().
        """
        return self.adjustment_helpers.get_size_discount_reason(revenue)

    def _get_growth_premium_reason(self, request: ValuationRequest) -> str:
        """
        Backward compatibility wrapper for growth premium reason.

        Delegates to AdjustmentHelpers.get_growth_premium_reason().
        """
        return self.adjustment_helpers.get_growth_premium_reason(request)

    def _build_small_firm_adjustments(
        self, multiples_results: Optional[Dict[str, Any]], request: ValuationRequest
    ) -> Optional[Dict[str, Any]]:
        """
        Backward compatibility wrapper for small firm adjustments.

        Delegates to AdjustmentHelpers.build_small_firm_adjustments().
        """
        return self.adjustment_helpers.build_small_firm_adjustments(multiples_results, request)

    def _convert_step_output_to_calculation_step(
        self, step_output: StepOutput, step_number: int
    ) -> CalculationStep:
        """
        Backward compatibility wrapper for step output conversion.

        Delegates to TransparencyBuilder.convert_step_output_to_calculation_step().
        """
        return self.transparency_builder.convert_step_output_to_calculation_step(
            step_output, step_number
        )

    def _sanitize_for_json_serialization(self, obj: Any, field_path: str = "root") -> Any:
        """
        Backward compatibility wrapper for JSON sanitization.

        Delegates to ValidationBuilder.sanitize_for_json_serialization().
        """
        return self.validation_builder.sanitize_for_json_serialization(obj, field_path)

    async def _execute_hybrid_valuation(
        self, request: ValuationRequest, context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Execute hybrid valuation with dynamic weighting.

        REFACTORED (Phase 2): Now uses modular HybridMethodologyOrchestrator.
        - Original: 1076 lines monolithic method
        - Refactored: 15 lines thin wrapper
        - Improvement: 98.6% code reduction, full modularity

        Components:
        - MethodologyEligibilityDecider: Growth-aware DCF eligibility
        - HybridWeightCalculator: Priority cascade weight calculation
        - ValuationAggregator: Result aggregation
        - HybridMethodologyOrchestrator: Main coordinator

        The old method is backed up in:
        - Git history (commit before this refactoring)
        - valuation_orchestrator_backup_before_phase2.py
        """
        try:
            self.logger.info("📊 Executing hybrid valuation (Phase 2: Modular)")

            # Delegate to hybrid orchestrator (replaces 1076 lines of monolithic code)
            result = await self.hybrid_orchestrator.execute_hybrid(request, context)

            self.logger.info("✅ Hybrid valuation completed via modular orchestrator")
            return result

        except (
            SynthesisError,
            DCFCalculationError,
            MultiplesCalculationError,
            CalculationError,
        ):
            raise
        except Exception as e:
            self.logger.error(
                f"❌ Error in hybrid valuation: {e}",
                exc_info=True,
                extra={
                    "error_type": type(e).__name__,
                    "company": request.company_name if "request" in locals() else None,
                },
            )
            raise SynthesisError(
                f"Unexpected error in hybrid valuation: {e}",
                step="hybrid_valuation_orchestration",
                calculation_type="Hybrid Valuation",
                context={
                    "company": request.company_name if "request" in locals() else None,
                    "error_type": type(e).__name__,
                },
            ) from e

    async def _generate_valuation_report(
        self,
        valuation_id: str,
        request: ValuationRequest,
        detailed_results: Dict[str, Any],
        context: Optional[Dict[str, Any]],
    ) -> Optional[str]:
        """Generate valuation report URL (placeholder)"""
        self.logger.debug("📄 Generating valuation report")
        # Placeholder - return None for now
        return None

    async def _generate_transparency_data(
        self, request: ValuationRequest, detailed_results: Dict[str, Any]
    ) -> Optional[Any]:
        """Generate transparency data (placeholder)"""
        try:
            from src.services.transparency.transparency_service import TransparencyService

            self.logger.debug("🔍 Generating transparency data")
            transparency_service = TransparencyService()

            # Mock valuation result
            mock_result = type(
                "ValuationResponse",
                (),
                {
                    "valuation_id": "temp_id",
                    "equity_value_mid": detailed_results.get("equity_value_mid", 0),
                    "dcf_weight": detailed_results.get("dcf_weight", 0),
                    "multiples_weight": detailed_results.get("multiples_weight", 0),
                },
            )()

            transparency_data = await transparency_service.generate_transparency_data(
                request=request,
                valuation_result=mock_result,
                market_data=detailed_results.get("market_data", {}),
                calculation_details=detailed_results.get("calculation_details", {}),
            )

            self.logger.info("✅ Transparency data generated")
            return transparency_data

        except Exception as e:
            self.logger.warning(f"⚠️ Transparency generation failed: {e}")
            return None

    def _sanitize_valuation_response(
        self, response: ValuationResponse, nan_fields: List[str]
    ) -> ValuationResponse:
        """
        Backward compatibility wrapper for response sanitization.

        Delegates to ValidationBuilder.sanitize_valuation_response().
        """
        return self.validation_builder.sanitize_valuation_response(response, nan_fields)


_valuation_orchestrator_instance: Optional[ValuationOrchestrator] = None
_valuation_orchestrator_lock = Lock()


def get_valuation_orchestrator() -> ValuationOrchestrator:
    """Return the process-wide valuation orchestrator with a warm service stack."""
    global _valuation_orchestrator_instance
    if _valuation_orchestrator_instance is None:
        with _valuation_orchestrator_lock:
            if _valuation_orchestrator_instance is None:
                _valuation_orchestrator_instance = ValuationOrchestrator()
    return _valuation_orchestrator_instance
