"""Coordinate progressive valuation phases through focused collaborators."""

import asyncio
import logging
import time
from decimal import Decimal
from typing import Any, Dict, Optional

from src.api.routes.valuation.benchmark_contract_utils import (
    REQUIRED_BENCHMARK_PROVENANCE_FIELDS,
    as_mapping,
    extract_resolved_benchmark_contract,
)
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.exceptions import (
    DCFCalculationError,
    ExternalServiceError,
    MultiplesCalculationError,
    ValidationError,
    ValuationEngineError,
)

from .coordinators import (
    HTMLGenerationCoordinator,
    MockCalculationCoordinator,
    SummaryGenerationCoordinator,
)
from .phase2_intermediate import calculate_phase_2_intermediate_for_service
from .progressive_valuation_types import (
    ValuationAdvanced,
    ValuationComplete,
    ValuationInstant,
    ValuationIntermediate,
    ValuationPhase,
    ValuationPreview,
)

logger = logging.getLogger(__name__)


class ProgressiveValuationService:
    """Coordinate progressive valuation workflow through focused collaborators."""

    def __init__(
        self,
        valuation_orchestrator=None,
        valuation_processor=None,
        phase_determiner: Optional["PhaseDeterminer"] = None,
        phase_calculator: Optional["PhaseCalculator"] = None,
        academic_tracker_manager: Optional["AcademicTrackerManager"] = None,
        html_coordinator: Optional[HTMLGenerationCoordinator] = None,
        html_generator: Optional["ProgressiveHTMLGenerator"] = None,
        mock_coordinator: Optional["MockCalculationCoordinator"] = None,
        summary_coordinator: Optional["SummaryGenerationCoordinator"] = None,
        data_transformer: Optional["ProgressiveDataTransformer"] = None,
        fallback_generator: Optional["FallbackValuationGenerator"] = None,
    ):
        """Initialize with dependency-injected collaborators."""
        self._initialize_progressive_components(
            phase_determiner=phase_determiner,
            academic_tracker_manager=academic_tracker_manager,
            html_coordinator=html_coordinator,
            html_generator=html_generator,
            mock_coordinator=mock_coordinator,
            summary_coordinator=summary_coordinator,
        )
        self._initialize_phase_calculator(phase_calculator)
        self._initialize_calculation_services(
            valuation_orchestrator=valuation_orchestrator,
            valuation_processor=valuation_processor,
            data_transformer=data_transformer,
            fallback_generator=fallback_generator,
        )

    def _initialize_progressive_components(
        self,
        *,
        phase_determiner: Optional["PhaseDeterminer"],
        academic_tracker_manager: Optional["AcademicTrackerManager"],
        html_coordinator: Optional[HTMLGenerationCoordinator],
        html_generator: Optional["ProgressiveHTMLGenerator"],
        mock_coordinator: Optional["MockCalculationCoordinator"],
        summary_coordinator: Optional["SummaryGenerationCoordinator"],
    ) -> None:
        from .academic_tracker_manager import AcademicTrackerManager
        from .academic_validation_service import AcademicValidationService
        from .phase_determiner import PhaseDeterminer
        from .progressive_html_generator import ProgressiveHTMLGenerator

        self.phase_determiner = phase_determiner or PhaseDeterminer()
        self.academic_tracker_manager = academic_tracker_manager or AcademicTrackerManager()
        self.academic_validation_service = AcademicValidationService(
            academic_tracker_manager=self.academic_tracker_manager
        )
        self.html_coordinator = html_coordinator or HTMLGenerationCoordinator()
        self.html_generator = html_generator or ProgressiveHTMLGenerator()
        self.mock_coordinator = mock_coordinator or MockCalculationCoordinator()
        self.summary_coordinator = summary_coordinator or SummaryGenerationCoordinator()

    def _initialize_phase_calculator(
        self,
        phase_calculator: Optional["PhaseCalculator"],
    ) -> None:
        if phase_calculator is not None:
            self.phase_calculator = phase_calculator
            return

        from .phase_calculator import PhaseCalculator

        self.phase_calculator = PhaseCalculator(
            html_coordinator=self.html_coordinator,
            mock_coordinator=self.mock_coordinator,
            summary_coordinator=self.summary_coordinator,
        )

    def _initialize_calculation_services(
        self,
        *,
        valuation_orchestrator: object,
        valuation_processor: object,
        data_transformer: Optional["ProgressiveDataTransformer"],
        fallback_generator: Optional["FallbackValuationGenerator"],
    ) -> None:
        from .data_transformer import ProgressiveDataTransformer
        from .fallback_generator import FallbackValuationGenerator

        try:
            from src.api.routes.valuation.valuation_orchestrator import get_valuation_orchestrator
            from src.services.core.orchestration.valuation_processor import ValuationProcessor

            self.orchestrator = valuation_orchestrator or get_valuation_orchestrator()
            self.processor = valuation_processor or ValuationProcessor()
            self.data_transformer = data_transformer or ProgressiveDataTransformer()
            self.fallback_generator = fallback_generator or FallbackValuationGenerator()
            self.use_mock = False

            logger.info(
                "✅ [PROGRESSIVE-SERVICE] SRP-compliant service initialized with real calculation services",
                extra={
                    "has_orchestrator": True,
                    "has_processor": True,
                    "has_html_generator": True,
                    "has_academic_validation": True,
                    "use_mock": False,
                },
            )

        except ImportError as e:
            logger.error(f"[PROGRESSIVE-SERVICE] Failed to import real calculation services: {e}")
            self.orchestrator = None
            self.processor = None
            self.data_transformer = data_transformer or ProgressiveDataTransformer()
            self.fallback_generator = fallback_generator or FallbackValuationGenerator()
            self.use_mock = True

            logger.warning(
                "⚠️ [PROGRESSIVE-SERVICE] Falling back to mock calculations",
                extra={"use_mock": True},
            )

    def determine_valuation_phase(self, data: Dict[str, Any]) -> ValuationPhase:
        """
        Determine current phase based on data completeness

        Delegates to PhaseDeterminer for single responsibility.

        Args:
            data: Collected data dictionary

        Returns:
            ValuationPhase enum value
        """
        return self.phase_determiner.determine_phase(data)

    def _resolved_benchmark_contract(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Return the normalized benchmark contract embedded in progressive context."""
        return extract_resolved_benchmark_contract(data)

    def _allows_untrusted_multiples_fallback(self, data: Dict[str, Any]) -> bool:
        """Explicit fallback consent can only be boolean true on known containers."""
        if data.get("allow_untrusted_multiples_fallback") is True:
            return True
        for key in ("metadata", "business_context", "multiples_metadata"):
            container = as_mapping(data.get(key))
            if container.get("allow_untrusted_multiples_fallback") is True:
                return True
        return False

    def _blocked_multiples_data(
        self,
        *,
        reason: str = "Resolved benchmark contract required",
    ) -> Dict[str, Any]:
        return {
            "value_low": 0,
            "value_mid": 0,
            "value_high": 0,
            "revenue_multiple": None,
            "ebitda_multiple": None,
            "methodology": reason,
            "blocked": True,
            "requires_benchmark_contract": True,
            "publication_allowed": False,
            "benchmark_contract_required": True,
        }

    def _benchmark_contract_methodology_label(
        self,
        benchmark_contract: Optional[Dict[str, Any]],
    ) -> str:
        """Return a concise provider-aware label for resolved benchmark contracts."""
        if not benchmark_contract:
            return "Resolved benchmark contract"
        source = benchmark_contract.get("source")
        if not isinstance(source, str) or not source.strip():
            return "Resolved benchmark contract"
        normalized_source = source.replace("_", " ").replace("-", " ").strip().lower()
        provider = "Upswitch Index" if "delphi" in normalized_source else normalized_source.title()
        return f"Resolved {provider} benchmark contract"

    def _blocked_preview(self, data: Dict[str, Any], industry: str) -> ValuationPreview:
        return ValuationPreview(
            value_low=Decimal("0"),
            value_mid=Decimal("0"),
            value_high=Decimal("0"),
            confidence_score=Decimal("0"),
            confidence_level="blocked",
            methodology="Resolved benchmark contract required",
            multiple_low=Decimal("0"),
            multiple_high=Decimal("0"),
            industry=industry,
            data_completeness=Decimal("25.0"),
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
        )

    def _benchmark_metric_decimal(
        self,
        metric: Optional[Dict[str, Any]],
        field: str,
    ) -> Optional[Decimal]:
        if not isinstance(metric, dict):
            return None
        value = metric.get(field)
        if value is None:
            return None
        try:
            return to_decimal(value)
        except Exception:
            return None

    def _calculate_contract_multiples_data(
        self,
        *,
        benchmark_contract: Dict[str, Any],
        revenue: Decimal,
        ebitda: Decimal,
    ) -> Dict[str, Any]:
        metrics = as_mapping(benchmark_contract.get("metrics"))
        ev_revenue_metric = as_mapping(metrics.get("ev_revenue"))
        ev_ebitda_metric = as_mapping(metrics.get("ev_ebitda"))
        revenue_multiple = self._benchmark_metric_decimal(ev_revenue_metric, "median")
        ebitda_multiple = self._benchmark_metric_decimal(ev_ebitda_metric, "median")

        prefer_ebitda = ebitda > 0 and revenue > 0 and ebitda >= revenue * Decimal("0.05")
        metric_name = None
        metric = None
        financial_base = None
        if prefer_ebitda and ebitda_multiple is not None:
            metric_name = "ev_ebitda"
            metric = ev_ebitda_metric
            financial_base = ebitda
        elif revenue_multiple is not None:
            metric_name = "ev_revenue"
            metric = ev_revenue_metric
            financial_base = revenue
        elif ebitda_multiple is not None and ebitda > 0:
            metric_name = "ev_ebitda"
            metric = ev_ebitda_metric
            financial_base = ebitda

        median = self._benchmark_metric_decimal(metric, "median")
        if metric_name is None or metric is None or financial_base is None or median is None:
            return self._blocked_multiples_data(
                reason="Resolved benchmark contract missing usable EV/Revenue or EV/EBITDA metric"
            )

        p25 = self._benchmark_metric_decimal(metric, "p25") or median
        p75 = self._benchmark_metric_decimal(metric, "p75") or median
        provenance = {
            field: benchmark_contract.get(field) for field in REQUIRED_BENCHMARK_PROVENANCE_FIELDS
        }
        return {
            "value_low": from_decimal(financial_base * p25),
            "value_mid": from_decimal(financial_base * median),
            "value_high": from_decimal(financial_base * p75),
            "revenue_multiple": (
                from_decimal(revenue_multiple) if revenue_multiple is not None else None
            ),
            "ebitda_multiple": (
                from_decimal(ebitda_multiple) if ebitda_multiple is not None else None
            ),
            "metric_used": metric_name,
            "multiple_low": from_decimal(p25),
            "multiple_mid": from_decimal(median),
            "multiple_high": from_decimal(p75),
            "methodology": self._benchmark_contract_methodology_label(benchmark_contract),
            "blocked": False,
            "requires_benchmark_contract": False,
            "publication_allowed": True,
            "benchmark_contract_required": False,
            "benchmark_contract": benchmark_contract,
            "benchmark_provenance": provenance,
            **provenance,
        }

    async def calculate_phase_0_instant(self, data: Dict[str, Any]) -> ValuationInstant:
        """
        Phase 0: Instant preview from ANY data

        Delegates to PhaseCalculator for single responsibility.

        Args:
            data: Collected data dictionary

        Returns:
            ValuationInstant result
        """
        # Initialize academic tracker for this valuation
        self.academic_tracker_manager.ensure_tracker(data)

        return await self.phase_calculator.calculate_phase_0_instant(data)

    # SRP: HTML generation methods removed - delegated to ProgressiveHTMLGenerator
    # Old methods (_generate_welcome_html, _generate_progress_html, _generate_placeholder_range,
    # _generate_next_steps) have been extracted to progressive_html_generator.py

    # SRP: Academic validation methods removed - delegated to AcademicValidationService
    # Old method (_run_academic_validation) has been extracted to academic_validation_service.py

    async def calculate_phase_1_preview(self, data: Dict[str, Any]) -> ValuationPreview:
        """
        Phase 1: Revenue + Industry only
        Returns: Quick multiple-based estimate
        """
        """
        Phase 1: Revenue + Industry only
        Returns: Quick multiple-based estimate
        Confidence: Low (40-60%)
        """
        # Initialize academic tracker for this valuation
        self.academic_tracker_manager.ensure_tracker(data)
        start_time = time.time()
        company_name = data.get("company_name", "Unknown")
        revenue = data.get("revenue", 0)
        industry = data.get("industry", "unknown")
        benchmark_contract = self._resolved_benchmark_contract(data)
        allow_untrusted_multiples_fallback = self._allows_untrusted_multiples_fallback(data)

        logger.info(
            f"[VALUATION] Starting Phase 1 calculation | company={company_name} | revenue={revenue} | industry={industry}"
        )

        if self.use_mock:
            logger.warning(f"[VALUATION] Using MOCK calculations (real services unavailable)")

        try:
            revenue_decimal = to_decimal(revenue)

            if self.use_mock:
                if benchmark_contract:
                    multiples_data = self._calculate_contract_multiples_data(
                        benchmark_contract=benchmark_contract,
                        revenue=revenue_decimal,
                        ebitda=to_decimal(data.get("ebitda", 0)),
                    )
                    if multiples_data.get("blocked"):
                        return self._blocked_preview(data, industry)
                    value_low = multiples_data["value_low"]
                    value_mid = multiples_data["value_mid"]
                    value_high = multiples_data["value_high"]
                    multiple_low = to_decimal(multiples_data["multiple_low"])
                    multiple_high = to_decimal(multiples_data["multiple_high"])
                    confidence_score = Decimal("55.0")
                elif allow_untrusted_multiples_fallback:
                    # Explicit development fallback only; never publication-grade.
                    multiple_low, multiple_high = self.mock_coordinator.get_industry_multiples_mock(
                        industry
                    )
                    multiple_low_decimal = to_decimal(multiple_low)
                    multiple_high_decimal = to_decimal(multiple_high)
                    multiple_mid_decimal = (multiple_low_decimal + multiple_high_decimal) / Decimal(
                        "2"
                    )
                    value_mid_decimal = revenue_decimal * multiple_mid_decimal
                    value_low_decimal = revenue_decimal * multiple_low_decimal
                    value_high_decimal = revenue_decimal * multiple_high_decimal
                    value_mid = from_decimal(value_mid_decimal)
                    value_low = from_decimal(value_low_decimal)
                    value_high = from_decimal(value_high_decimal)
                    confidence_score = Decimal("25.0")
                else:
                    return self._blocked_preview(data, industry)
            else:
                if benchmark_contract is None and not allow_untrusted_multiples_fallback:
                    return self._blocked_preview(data, industry)

                # Real calculation using ValuationOrchestrator
                from typing import TYPE_CHECKING

                if TYPE_CHECKING:
                    from src.api.schemas import QuickValuationRequest

                # Before transformation
                logger.debug(
                    f"[VALUATION] Transforming context to QuickValuationRequest | fields={list(data.keys())}"
                )
                quick_request = self.data_transformer.conversation_to_quick_request(data)
                logger.debug(
                    f"[VALUATION] QuickValuationRequest created | business_name={quick_request.business_name} | revenue={quick_request.revenue}"
                )

                # Before orchestrator call
                logger.debug(f"[VALUATION] Calling ValuationOrchestrator.process_quick_valuation")
                result = await self.orchestrator.process_quick_valuation(quick_request)
                logger.debug(
                    f"[VALUATION] Orchestrator result | value_mid={result.valuation_range_mid} | confidence={result.confidence_score}"
                )

                # Extract values from result
                value_low = result.valuation_range_low
                value_mid = result.valuation_range_mid
                value_high = result.valuation_range_high
                confidence_score = result.confidence_score

                # Calculate multiples from result
                revenue_multiple = to_decimal(getattr(result, "revenue_multiple", Decimal("2.5")))
                multiple_low = revenue_multiple * Decimal("0.8")
                multiple_high = revenue_multiple * Decimal("1.2")

            calculation_time = (time.time() - start_time) * 1000
            logger.info(
                f"[VALUATION] Phase 1 complete | value_mid={value_mid} | confidence={confidence_score} | time={calculation_time:.2f}ms"
            )

            # SRP: Run academic validation via dedicated service
            self.academic_validation_service.validate_calculation()

            return ValuationPreview(
                value_low=value_low,
                value_mid=value_mid,
                value_high=value_high,
                confidence_score=confidence_score,
                confidence_level="low" if benchmark_contract else "fallback",
                methodology=(
                    self._benchmark_contract_methodology_label(benchmark_contract)
                    if benchmark_contract
                    else "Explicit disclosed multiples fallback"
                ),
                multiple_low=multiple_low,
                multiple_high=multiple_high,
                industry=industry,
                data_completeness=Decimal("25.0"),
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )

        except MultiplesCalculationError as e:
            logger.error(
                "Phase 1 quick valuation failed closed: resolved benchmark contract required",
                extra={
                    "company": data.get("company_name"),
                    "industry": data.get("industry"),
                    "error": str(e),
                },
            )
            return ValuationPreview(
                value_low=Decimal("0"),
                value_mid=Decimal("0"),
                value_high=Decimal("0"),
                confidence_score=Decimal("0"),
                confidence_level="blocked",
                methodology="Resolved benchmark contract required",
                multiple_low=Decimal("0"),
                multiple_high=Decimal("0"),
                industry=industry,
                data_completeness=Decimal("25.0"),
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )
        except Exception as e:
            logger.error(
                "Phase 1 quick valuation failed before publication-grade multiples could be applied",
                extra={
                    "company": data.get("company_name"),
                    "industry": data.get("industry"),
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            return ValuationPreview(
                value_low=Decimal("0"),
                value_mid=Decimal("0"),
                value_high=Decimal("0"),
                confidence_score=Decimal("0"),
                confidence_level="Error",
                methodology="Valuation unavailable",
                multiple_low=Decimal("0"),
                multiple_high=Decimal("0"),
                industry=industry,
                data_completeness=Decimal("25.0"),
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )

    async def calculate_phase_2_intermediate(self, data: Dict[str, Any]) -> ValuationIntermediate:
        """
        Phase 2: Revenue + EBITDA + Growth
        Returns: Simplified DCF + Multiples
        Confidence: Medium (60-75%)
        """
        return await calculate_phase_2_intermediate_for_service(
            self,
            data,
            ValuationIntermediate,
        )

    async def calculate_phase_3_advanced(self, data: Dict[str, Any]) -> ValuationAdvanced:
        """
        Phase 3: All financial data
        Returns: Full DCF + Multiples + Adjustments
        Confidence: High (75-85%)
        """
        # Initialize academic tracker for this valuation
        self.academic_tracker_manager.ensure_tracker(data)
        start_time = time.time()
        logger.info(f"Calculating Phase 3 advanced for {data.get('company_name', 'Unknown')}")

        try:
            # Get all financial data
            revenue_decimal = to_decimal(data.get("revenue", 0))
            ebitda_decimal = to_decimal(data.get("ebitda", 0))
            growth_rate_decimal = to_decimal(data.get("growth_rate", 0))
            total_assets_decimal = to_decimal(data.get("total_assets", 0))
            total_debt_decimal = to_decimal(data.get("total_debt", 0))
            cash_decimal = to_decimal(data.get("cash", 0))
            revenue = from_decimal(revenue_decimal)
            ebitda = from_decimal(ebitda_decimal)
            growth_rate = from_decimal(growth_rate_decimal)
            total_assets = from_decimal(total_assets_decimal)
            total_debt = from_decimal(total_debt_decimal)
            cash = from_decimal(cash_decimal)
            industry = data.get("industry", "unknown")

            if self.use_mock:
                # Mock full DCF calculation
                dcf_complete = self.mock_coordinator.calculate_mock_full_dcf(
                    revenue, ebitda, growth_rate, total_assets, total_debt, cash
                )
                adjustments = self.mock_coordinator.calculate_mock_adjustments(
                    revenue, ebitda, industry, total_assets, total_debt
                )
            else:
                # Real full calculations using ValuationOrchestrator
                from typing import TYPE_CHECKING

                if TYPE_CHECKING:
                    from src.api.schemas import ValuationRequest

                # Convert data to comprehensive ValuationRequest for Phase 3
                valuation_request = self.data_transformer.conversation_to_comprehensive_request(
                    data
                )

                # Calculate comprehensive valuation
                result = await self.orchestrator.process_comprehensive_valuation(valuation_request)

                # Extract DCF data from result
                dcf_complete = {
                    "value_low": getattr(result, "dcf_value_low", result.equity_value_low),
                    "value_mid": getattr(result, "dcf_value_mid", result.equity_value_mid),
                    "value_high": getattr(result, "dcf_value_high", result.equity_value_high),
                    "discount_rate": getattr(result, "discount_rate", Decimal("0.10")),
                    "terminal_growth_rate": getattr(
                        result, "terminal_growth_rate", Decimal("0.03")
                    ),
                    "projected_cash_flows": getattr(result, "projected_cash_flows", []),
                    "terminal_value": getattr(result, "terminal_value", 0),
                    "value_drivers": getattr(result, "key_value_drivers", []),
                }

                # Extract adjustments from result
                adjustments = {
                    "size_adjustment": getattr(result, "size_adjustment", 0),
                    "liquidity_adjustment": getattr(result, "liquidity_adjustment", 0),
                    "market_adjustment": getattr(result, "market_adjustment", 0),
                    "risk_factors": getattr(result, "risk_factors", []),
                    "sensitivity_analysis": getattr(result, "sensitivity_analysis", {}),
                }

            # Apply adjustments
            base_value = to_decimal(dcf_complete["value_mid"])
            size_adjustment = to_decimal(adjustments.get("size_adjustment", 0))
            liquidity_adjustment = to_decimal(adjustments.get("liquidity_adjustment", 0))

            final_value_mid = base_value * (1 + size_adjustment) * (1 + liquidity_adjustment)
            final_value_low = final_value_mid * Decimal("0.85")  # 15% range
            final_value_high = final_value_mid * Decimal("1.15")

            calculation_time = (time.time() - start_time) * 1000
            logger.info(f"Phase 3 advanced calculated in {calculation_time:.2f}ms")

            # SRP: Run academic validation via dedicated service
            self.academic_validation_service.validate_calculation()

            return ValuationAdvanced(
                dcf_complete=dcf_complete,
                adjustments=adjustments,
                final_value_low=final_value_low,
                final_value_mid=final_value_mid,
                final_value_high=final_value_high,
                confidence_score=Decimal("80.0"),
                risk_factors=adjustments.get("risk_factors", []),
                value_drivers=dcf_complete.get("value_drivers", []),
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )

        except DCFCalculationError as e:
            logger.error(f"Phase 3 calculation failed closed: {e}")
            return ValuationAdvanced(
                dcf_complete={"methodology": "Valuation unavailable", "error": str(e)},
                adjustments={"methodology": "No fallback adjustments applied"},
                final_value_low=Decimal("0"),
                final_value_mid=Decimal("0"),
                final_value_high=Decimal("0"),
                confidence_score=Decimal("0"),
                risk_factors=["Valuation unavailable without defensible inputs"],
                value_drivers=[],
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error(
                "Phase 3 calculation failed before valuation-grade inputs could be applied",
                extra={"error": str(e), "error_type": type(e).__name__},
            )
            return ValuationAdvanced(
                dcf_complete={"methodology": "Valuation unavailable", "error": str(e)},
                adjustments={"methodology": "No fallback adjustments applied"},
                final_value_low=Decimal("0"),
                final_value_mid=Decimal("0"),
                final_value_high=Decimal("0"),
                confidence_score=Decimal("0"),
                risk_factors=["Valuation unavailable without defensible inputs"],
                value_drivers=[],
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )

    async def calculate_phase_4_complete(self, data: Dict[str, Any]) -> ValuationComplete:
        """
        Phase 4: Financial + Owner profiling
        Returns: Complete valuation with owner factor
        Confidence: Very High (85-95%)
        """
        # Initialize academic tracker for this valuation
        self.academic_tracker_manager.ensure_tracker(data)
        start_time = time.time()
        logger.info(f"Calculating Phase 4 complete for {data.get('company_name', 'Unknown')}")

        try:
            # Get owner profile data
            owner_profile = data.get("owner_profile", {})

            if self.use_mock:
                # Mock owner analysis
                owner_analysis = self.mock_coordinator.calculate_mock_owner_analysis(owner_profile)
                final_valuation = self.mock_coordinator.calculate_mock_final_valuation(
                    data, owner_analysis
                )
            else:
                # Real owner analysis using ValuationOrchestrator
                from typing import TYPE_CHECKING

                if TYPE_CHECKING:
                    from src.api.schemas import ValuationRequest

                # Convert data to comprehensive ValuationRequest for Phase 4
                valuation_request = self.data_transformer.conversation_to_comprehensive_request(
                    data
                )

                # Calculate comprehensive valuation with owner profiling
                result = await self.orchestrator.process_comprehensive_valuation(valuation_request)

                # Extract owner analysis from result
                owner_analysis = {
                    "dependency_score": getattr(result, "owner_dependency_score", Decimal("0.7")),
                    "risk_level": getattr(result, "owner_risk_level", "medium"),
                    "adjustment_factor": getattr(result, "owner_adjustment_factor", Decimal("0.9")),
                    "recommendations": getattr(result, "owner_recommendations", []),
                    "time_commitment": getattr(result, "owner_time_commitment", "full_time"),
                    "skill_criticality": getattr(result, "owner_skill_criticality", "high"),
                }

                # Extract final valuation from result
                final_valuation = {
                    "value_low": result.equity_value_low,
                    "value_mid": result.equity_value_mid,
                    "value_high": result.equity_value_high,
                    "confidence_score": result.confidence_score,
                    "methodology_breakdown": getattr(result, "methodology_breakdown", {}),
                    "sensitivity_analysis": getattr(result, "sensitivity_analysis", {}),
                    "executive_summary": getattr(result, "valuation_summary", ""),
                    "recommendations": getattr(result, "recommendations", []),
                }

            # Generate executive summary and recommendations
            executive_summary = final_valuation.get(
                "executive_summary"
            ) or self.summary_coordinator.generate_executive_summary(data, final_valuation)
            recommendations = self.summary_coordinator.generate_phase_recommendations(
                data,
                owner_analysis,
                final_valuation.get("recommendations"),
            )

            calculation_time = (time.time() - start_time) * 1000
            logger.info(f"Phase 4 complete calculated in {calculation_time:.2f}ms")

            # SRP: Run academic validation via dedicated service
            self.academic_validation_service.validate_calculation()

            return ValuationComplete(
                owner_analysis=owner_analysis,
                final_valuation=final_valuation,
                valuation_id=f"val_{int(time.time())}",
                executive_summary=executive_summary,
                recommendations=recommendations,
                confidence_score=Decimal("90.0"),
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )

        except MultiplesCalculationError as e:
            logger.error(f"Phase 4 calculation failed closed: {e}")
            return ValuationComplete(
                owner_analysis={"methodology": "Owner analysis unavailable"},
                final_valuation={
                    "value_low": Decimal("0"),
                    "value_mid": Decimal("0"),
                    "value_high": Decimal("0"),
                    "confidence_score": Decimal("0"),
                    "publication_allowed": False,
                    "error": str(e),
                },
                valuation_id=f"val_fallback_{int(time.time())}",
                executive_summary="Valuation unavailable without a resolved benchmark contract or defensible inputs.",
                recommendations=[
                    "Resolve and approve a benchmark contract before publishing multiples-based valuation output."
                ],
                confidence_score=Decimal("0"),
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )

        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error(
                "Phase 4 calculation failed before valuation-grade inputs could be applied",
                extra={"error": str(e), "error_type": type(e).__name__},
            )
            return ValuationComplete(
                owner_analysis={"methodology": "Owner analysis unavailable"},
                final_valuation={
                    "value_low": Decimal("0"),
                    "value_mid": Decimal("0"),
                    "value_high": Decimal("0"),
                    "confidence_score": Decimal("0"),
                    "publication_allowed": False,
                    "error": str(e),
                },
                valuation_id=f"val_fallback_{int(time.time())}",
                executive_summary="Valuation unavailable without defensible inputs.",
                recommendations=[
                    "Provide valid financial data and a resolved benchmark contract before publishing valuation output."
                ],
                confidence_score=Decimal("0"),
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )
