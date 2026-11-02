
"""
Valuation Synthesizer.

Combines multiple valuation methodologies (DCF, Market Multiples, etc.)
into a single comprehensive valuation with range and recommendations.

This synthesizer implements best practices from Big 4 advisory firms
and institutional investors for creating robust valuation opinions.
"""

from datetime import date
from decimal import Decimal
from typing import Any, List, Optional, Tuple

import numpy as np

from src.domain.dcf_engine import DCFValuationEngine
from src.domain.financial_metrics import FinancialMetricsCalculator
from src.domain.models import (
    ComparableCompany,
    ConfidenceLevel,
    DCFResult,
    FinancialData,
    FinancialMetrics,
    IndustryBenchmarks,
    MarketContext,
    MultiplesResult,
    SynthesizedValuation,
    ValidationWarning,
)
from src.domain.multiples_engine import MarketMultiplesEngine
from src.domain.synthesis.risk_factor_analyzer import RiskFactorAnalyzer
from src.domain.synthesis.value_driver_analyzer import ValueDriverAnalyzer
from src.domain.synthesis.coordinators import (
    AskingPriceCalculationCoordinator,
    ConfidenceCalculationCoordinator,
    OwnerDependencyCoordinator,
    RangeCalculationCoordinator,
    SummaryGenerationCoordinator,
    ValidationCoordinator,
)
from src.domain.synthesis.synthesis_executors import (
    DCFValuationExecutor,
    MultiplesValuationExecutor,
)
from src.domain.synthesis.owner_concentration_processor import OwnerConcentrationProcessor
from src.domain.synthesis.owner_dependency_processor import OwnerDependencyProcessor
from src.domain.synthesis.dcf_result_converter import DCFResultConverter
from src.domain.owner_risk_ledger import build_owner_risk_ledger
from src.utils.exceptions import (
    CalculationError,
    DataQualityError,
    DCFCalculationError,
    MarketDataError,
    MultiplesCalculationError,
    SynthesisError,
    ValidationError,
)
from src.errors.error_types import DomainError
from src.domain.interfaces.transparency_protocol import TransparencyTrackerProtocol
from src.utils.decimal_helpers import bank_round, from_decimal, to_decimal
from src.utils.logging import get_logger, log_calculation_step, log_validation_step
from src.utils.logging_context import get_current_context

# Transparency tracking imports
# TransparencyTracker imported locally to avoid circular imports

logger = get_logger(__name__)


class ValuationSynthesizer:
    """
    Synthesize multiple valuation methodologies into final valuation.

    This class orchestrates all valuation engines and produces a
    comprehensive valuation report with ranges, confidence scoring,
    and actionable recommendations.
    """

    def __init__(
        self,
        financial_data: FinancialData,
        market_context: MarketContext,
        industry_benchmarks: IndustryBenchmarks,
        comparables: Optional[List[ComparableCompany]] = None,
        transparency_tracker: Optional[TransparencyTrackerProtocol] = None,
    ) -> None:
        """
        Initialize valuation synthesizer.

        Args:
            financial_data: Company financial data
            market_context: Market and economic context
            industry_benchmarks: Industry benchmarks
            comparables: Optional comparable companies for multiples valuation
            transparency_tracker: Optional transparency tracker for data provenance
        """
        self.financial_data = financial_data
        self.market_context = market_context
        self.industry_benchmarks = industry_benchmarks
        self.comparables = comparables or []

        # Initialize legacy transparency tracker (for existing system)
        # Use protocol to avoid service layer dependency
        if transparency_tracker is None:
            # Lazy import only when needed to avoid circular dependency
            try:
                from src.services.privacy.compliance.transparency_tracker import TransparencyTracker
                self.transparency: TransparencyTrackerProtocol = TransparencyTracker()
            except ImportError:
                # Fallback if service not available
                self.transparency = None  # type: ignore
        else:
            self.transparency = transparency_tracker

        # NEW: Initialize transparency collector for frontend
        from src.utils.transparency_collector import TransparencyCollector

        self.transparency_collector = TransparencyCollector()

        # Initialize engines (pass both transparency systems to each)
        self.metrics_calculator = FinancialMetricsCalculator(financial_data)
        self.dcf_engine = DCFValuationEngine(
            financial_data,
            market_context,
            industry_benchmarks,
            config=None,  # Use default config
            transparency_tracker=self.transparency,
            transparency_collector=self.transparency_collector,  # NEW
        )
        self.multiples_engine = MarketMultiplesEngine(
            financial_data,
            market_context,
            industry_benchmarks,
            comparables,
            self.transparency,
            transparency_collector=self.transparency_collector,  # NEW
        )

        # Initialize synthesis helpers
        self.value_driver_analyzer = ValueDriverAnalyzer()
        self.risk_factor_analyzer = RiskFactorAnalyzer()
        
        # Initialize coordinators
        self.validation_coordinator = ValidationCoordinator()
        self.range_coordinator = RangeCalculationCoordinator(financial_data)
        self.confidence_coordinator = ConfidenceCalculationCoordinator()
        self.asking_price_coordinator = AskingPriceCalculationCoordinator()
        self.summary_coordinator = SummaryGenerationCoordinator(
            financial_data, market_context, industry_benchmarks
        )
        self.owner_dependency_coordinator = OwnerDependencyCoordinator()
        
        # Initialize synthesis processors
        self.dcf_executor = DCFValuationExecutor(
            self.dcf_engine, self.validation_coordinator, financial_data
        )
        self.multiples_executor = MultiplesValuationExecutor(self.multiples_engine, financial_data)
        self.owner_concentration_processor = OwnerConcentrationProcessor()
        self.owner_dependency_processor = OwnerDependencyProcessor(
            financial_data, self.transparency_collector
        )
        self.dcf_result_converter = DCFResultConverter()

    def synthesize_valuation(
        self,
        use_dcf: bool = True,
        use_multiples: bool = True,
        projection_years: int = 5,
        owner_dependency_factors: Optional[Any] = None,  # OwnerDependencyFactors
        *,
        owner_hours_per_week: Optional[int] = None,
        eligible_methods: Optional[List[Any]] = None,
        owner_profile_roster: Optional[List[Any]] = None,
    ) -> SynthesizedValuation:
        """
        Create comprehensive synthesized valuation with enhanced logging.

        Args:
            use_dcf: Whether to include DCF valuation
            use_multiples: Whether to include multiples valuation
            projection_years: Years to project for DCF
            owner_dependency_factors: Optional 12-factor owner dependency assessment
            owner_hours_per_week: Optional owner self-reported intensity (Q1
                of the wizard). Drives the v2 transferability gap calc; when
                omitted the gap defaults to a pessimistic 60 hrs/wk so the
                gap is never silently understated. Kwargs-only with default
                ``None`` so existing positional callers work unchanged.
            eligible_methods: Optional list of method ids the engine ran.
                Drives the blended-incidence figure on the v2 cascade.
            owner_profile_roster: Optional BET-218 multi-owner roster — a
                list of per-owner dicts, each carrying a 12-factor
                ``factors`` payload plus ``role_criticality`` and
                ``owner_hours_per_week``. When supplied it is aggregated to
                one composite transferability index fed to the owner-
                dependency engine; when omitted the engine scores a single
                owner exactly as today (zero-regression).

        Returns:
            SynthesizedValuation with complete valuation analysis
        """
        try:
            company_name = self.financial_data.company_name

            logger.info(
                "🎯 Synthesizer.synthesize_valuation called",
                extra={
                    "company_name": company_name,
                    "use_dcf": use_dcf,
                    "use_multiples": use_multiples,
                    "projection_years": projection_years,
                    "has_owner_dependency_factors": owner_dependency_factors is not None,
                },
            )

            # Get current logging context
            logging_context = get_current_context()
            session_id = (
                getattr(logging_context, "current_session_id", None) if logging_context else None
            )

            # Log synthesis start
            log_calculation_step(
                "synthesis_start",
                inputs={
                    "company_name": company_name,
                    "use_dcf": use_dcf,
                    "use_multiples": use_multiples,
                    "projection_years": projection_years,
                },
                outputs={"synthesis_id": f"synthesis_{date.today().strftime('%Y%m%d_%H%M%S')}"},
                formula="Synthesis_Start = Initialize_Synthesis + Setup_Logging + Start_Processing",
            )

            logger.calculation(
                "Starting valuation synthesis",
                session_id=session_id,
                company=self.financial_data.company_name,
                use_dcf=use_dcf,
                use_multiples=use_multiples,
            )

            # Calculate financial metrics
            financial_metrics = self.metrics_calculator.calculate_all_metrics()

            # Collect all validation warnings throughout the process
            from src.domain.models import ValidationWarning

            all_validation_warnings: List[ValidationWarning] = []

            # Run validation early (will be called again after DCF)
            validation_warnings = self.validation_coordinator.validate_calculation_results(None, financial_metrics)
            if validation_warnings:
                all_validation_warnings.extend(validation_warnings)
                for warning in validation_warnings:
                    logger.warning("Validation check", warning=warning)

            # Execute DCF valuation
            dcf_result, use_dcf, all_validation_warnings = self.dcf_executor.execute(
                use_dcf, projection_years, financial_metrics, all_validation_warnings
            )

            # Execute multiples valuation
            multiples_result, use_multiples = self.multiples_executor.execute(use_multiples)

            # Determine methodology weights
            dcf_weight, multiples_weight = self._calculate_methodology_weights(
                dcf_result, multiples_result, financial_metrics
            )

            logger.info(
                "Methodology weights",
                dcf_weight=f"{float(dcf_weight):.0%}",  # Convert to float for formatting only
                multiples_weight=f"{float(multiples_weight):.0%}",  # Convert to float for formatting only
            )

            # Calculate valuation range using RangeCalculationCoordinator
            equity_value_low, equity_value_mid, equity_value_high = self.range_coordinator.calculate_valuation_range(
                dcf_result, multiples_result, dcf_weight, multiples_weight
            )

            # Determine overall confidence
            overall_confidence, confidence_score = self.confidence_coordinator.calculate_overall_confidence(
                dcf_result, multiples_result, dcf_weight, multiples_weight, financial_metrics
            )

            # Generate valuation summary and analytical data
            valuation_summary = self.summary_coordinator.generate_valuation_summary(
                equity_value_low, equity_value_mid, equity_value_high, dcf_result, multiples_result
            )
            key_value_drivers = self.value_driver_analyzer.identify_value_drivers(
                financial_metrics, dcf_result, self.financial_data
            )
            risk_factors = self.risk_factor_analyzer.identify_risk_factors(
                financial_metrics, dcf_result, multiples_result, self.financial_data
            )

            # Process owner concentration risk factor
            risk_factors = self.owner_concentration_processor.process_owner_concentration_risk(
                multiples_result, risk_factors
            )

            methodology_notes = self.summary_coordinator.generate_methodology_notes(
                dcf_result, multiples_result, dcf_weight, multiples_weight
            )

            # Track methodology notes for transparency
            self.transparency.set_methodology_notes(methodology_notes)

            # Process owner dependency assessment and apply adjustments
            # NOTE: We now calculate asking price AFTER this to ensure it's based on final adjusted value
            #
            # BET-218 — multi-owner roster: collapse a per-owner roster into
            # one composite transferability index. `process_owner_dependency`
            # forwards it to the engine, whose `multi_owner_profile_v1`-gated
            # swap routes the composite. A None/empty roster yields (None, 1)
            # — the engine no-ops to single-owner scoring (zero-regression).
            # Lazy import mirrors `process_owner_dependency`'s own engine
            # import — keeps the owner-models subsystem cycle-free.
            from src.domain.owner_models.owner_team_aggregator import (
                resolve_team_composite,
            )

            composite_transferability_index, owner_count = resolve_team_composite(
                owner_profile_roster,
                financial_data=self.financial_data,
            )
            (
                owner_dependency_result,
                owner_dependency_adjustment,
                equity_value_low,
                equity_value_mid,
                equity_value_high,
                _, # We ignore the legacy asking price from here
                risk_factors,
            ) = self.owner_dependency_processor.process_owner_dependency(
                owner_dependency_factors,
                equity_value_low,
                equity_value_mid,
                equity_value_high,
                Decimal("0"), # Placeholder for legacy price
                risk_factors,
                owner_hours_per_week=owner_hours_per_week,
                eligible_methods=eligible_methods,
                composite_transferability_index=composite_transferability_index,
                owner_count=owner_count,
            )

            # Calculate recommended asking price and multiple
            # BANK-GRADE: Applying premium to multiple per user request for Info Tab simplification
            ebitda = to_decimal(self.financial_data.current_year.ebitda or 0)
            net_debt = to_decimal(self.financial_data.current_year.total_debt or 0) - to_decimal(self.financial_data.current_year.cash or 0)
            
            # Use final adjusted ebitda multiple from multiples_result if available
            current_multiple = multiples_result.ebitda_multiple if multiples_result else None
            
            recommended_asking_price, recommended_asking_multiple = self.asking_price_coordinator.calculate_asking_price(
                equity_value_mid, 
                confidence_score,
                ebitda=ebitda,
                net_debt=net_debt,
                current_multiple=current_multiple
            )

            logger.info(
                "Valuation synthesis complete",
                equity_value_mid=f"\u20AC{equity_value_mid:,.0f}",
                recommended_asking_price=f"\u20AC{recommended_asking_price:,.0f}",
                recommended_asking_multiple=f"{recommended_asking_multiple}x",
                overall_confidence=overall_confidence.value if hasattr(overall_confidence, 'value') else overall_confidence,
                owner_dependency_adjustment=(
                    f"{owner_dependency_adjustment:.1%}"
                    if owner_dependency_adjustment != 0
                    else "N/A"
                ),
            )


            # Convert DCFResult from dataclass to BaseModel if needed
            dcf_valuation_model = self.dcf_result_converter.convert(dcf_result)

            # MultiplesResult is already a BaseModel, so no conversion needed
            multiples_valuation_model = multiples_result

            # Build the M&A-grade Owner Risk Ledger — single auditable
            # reconciliation of structural (multiple-side) + behavioral
            # (equity-side) owner-risk discounts. Pure presentation: never
            # raises if upstream data is partial.
            owner_risk_ledger_model = self._build_owner_risk_ledger_safely(
                multiples_result=multiples_result,
                owner_dependency_result=owner_dependency_result,
                owner_dependency_adjustment=owner_dependency_adjustment,
                equity_value_mid_after=equity_value_mid,
            )

            result = SynthesizedValuation(
                company_id=self.financial_data.company_id,
                company_name=self.financial_data.company_name,
                valuation_date=date.today(),
                dcf_valuation=dcf_valuation_model,
                multiples_valuation=multiples_valuation_model,
                dcf_weight=dcf_weight,
                multiples_weight=multiples_weight,
                equity_value_low=equity_value_low,
                equity_value_mid=equity_value_mid,
                equity_value_high=equity_value_high,
                financial_metrics=financial_metrics,
                overall_confidence=overall_confidence,
                confidence_score=confidence_score,
                validation_warnings=all_validation_warnings,
                recommended_asking_price=recommended_asking_price if recommended_asking_price > 0 else equity_value_mid,
                recommended_asking_multiple=recommended_asking_multiple if recommended_asking_multiple and recommended_asking_multiple > 0 else None,
                valuation_summary=valuation_summary,
                key_value_drivers=key_value_drivers,
                risk_factors=risk_factors,
                methodology_notes=methodology_notes,
                owner_dependency_result=owner_dependency_result,
                owner_dependency_adjustment=owner_dependency_adjustment,
                owner_risk_ledger=owner_risk_ledger_model,
            )

            return result

        except (CalculationError, DataQualityError, MarketDataError, DomainError, ValidationError):
            # Re-raise specific errors
            raise
        except (ValueError, TypeError, ZeroDivisionError, AttributeError, KeyError) as e:
            error_msg = str(e) if e else "Unknown synthesizer error"
            error_type = type(e).__name__ if e else "UnknownType"
            error_repr = repr(e) if e else None

            company_name = (
                getattr(self.financial_data, "company_name", "Unknown")
                if hasattr(self, "financial_data")
                else "Unknown"
            )

            logger.error(
                "❌ Error in synthesize_valuation",
                extra={
                    "error": error_msg,
                    "error_type": error_type,
                    "error_repr": error_repr,
                    "company_name": company_name,
                    "use_dcf": use_dcf if "use_dcf" in locals() else None,
                    "use_multiples": use_multiples if "use_multiples" in locals() else None,
                },
                exc_info=True,
            )
            raise SynthesisError(
                f"Failed to synthesize valuation: {e}",
                context={
                    "company_name": company_name,
                    "step": "synthesis",
                    "calculation_type": "Valuation Synthesis",
                },
            ) from e
        except MultiplesCalculationError as e:
            error_msg = str(e) if e else "Unknown synthesizer error"
            error_type = type(e).__name__ if e else "UnknownType"
            error_repr = repr(e) if e else None

            company_name = (
                getattr(self.financial_data, "company_name", "Unknown")
                if hasattr(self, "financial_data")
                else "Unknown"
            )

            logger.error(
                "❌ Unexpected error in synthesize_valuation",
                extra={
                    "error": error_msg,
                    "error_type": error_type,
                    "error_repr": error_repr,
                    "company_name": company_name,
                    "use_dcf": use_dcf if "use_dcf" in locals() else None,
                    "use_multiples": use_multiples if "use_multiples" in locals() else None,
                },
                exc_info=True,
            )
            raise SynthesisError(
                f"Unexpected error in synthesize_valuation: {e}",
                context={
                    "company_name": company_name,
                    "error_type": error_type,
                    "step": "synthesis_unexpected_error",
                    "calculation_type": "Valuation Synthesis",
                    "use_dcf": use_dcf if "use_dcf" in locals() else None,
                    "use_multiples": use_multiples if "use_multiples" in locals() else None,
                },
            ) from e

    def _calculate_methodology_weights(
        self,
        dcf_result: Optional[DCFResult],
        multiples_result: Optional[MultiplesResult],
        financial_metrics: FinancialMetrics,
    ) -> Tuple[Decimal, Decimal]:
        """
        Calculate DCF/multiples weights based on confidence scores and company profile.

        Uses consistent Decimal arithmetic throughout (no float mixing).
        Replaces the deprecated MethodologyWeightCalculator.
        """
        if not dcf_result and not multiples_result:
            return Decimal("0"), Decimal("0")
        if not dcf_result:
            return Decimal("0"), Decimal("1")
        if not multiples_result:
            return Decimal("1"), Decimal("0")

        dcf_weight = Decimal("0.50")
        multiples_weight = Decimal("0.50")

        dcf_conf = Decimal(str(dcf_result.confidence_score))
        mult_conf = Decimal(str(getattr(multiples_result, "confidence_score", 50)))
        total_conf = dcf_conf + mult_conf
        if total_conf > 0:
            dcf_weight = dcf_conf / total_conf
            multiples_weight = mult_conf / total_conf

        if (
            financial_metrics.ebitda_margin > Decimal("0.15")
            and self.financial_data.operating_history_years >= 5
            and financial_metrics.revenue_growth < Decimal("0.30")
        ):
            dcf_weight += Decimal("0.10")
            multiples_weight -= Decimal("0.10")

        if financial_metrics.revenue_growth > Decimal("0.30") and self.financial_data.operating_history_years < 5:
            dcf_weight -= Decimal("0.10")
            multiples_weight += Decimal("0.10")

        if financial_metrics.ebitda_margin < Decimal("0"):
            dcf_weight -= Decimal("0.15")
            multiples_weight += Decimal("0.15")

        dcf_weight = max(Decimal("0"), min(Decimal("1"), dcf_weight))
        multiples_weight = max(Decimal("0"), min(Decimal("1"), multiples_weight))

        total = dcf_weight + multiples_weight
        if total > 0:
            dcf_weight /= total
            multiples_weight /= total
        else:
            dcf_weight = Decimal("0.50")
            multiples_weight = Decimal("0.50")

        return dcf_weight, multiples_weight

    def _build_owner_risk_ledger_safely(
        self,
        *,
        multiples_result: Optional[Any],
        owner_dependency_result: Optional[Any],
        owner_dependency_adjustment: Decimal,
        equity_value_mid_after: Decimal,
    ) -> Optional[Any]:
        """Adapt existing pipeline outputs to the ledger builder's input shape.

        The synthesizer doesn't see the Step-4 pipeline_stage dict directly
        (it sees the flattened MultiplesResult), so we project a minimal
        pipeline_stage view from `multiples_result.owner_concentration` —
        which already carries the post-Step-4 adjustment_percentage and EV
        delta. Anything missing is logged and the ledger degrades to a
        partial entry; we never let ledger construction raise.
        """
        try:
            pipeline_stage_4: Optional[dict] = None
            structural_ev_before: Optional[Decimal] = None
            structural_ev_after: Optional[Decimal] = None
            number_of_owners: Optional[int] = None

            owner_conc = (
                getattr(multiples_result, "owner_concentration", None)
                if multiples_result is not None
                else None
            )
            if isinstance(owner_conc, dict):
                # The Step-4 dict carries `adjustment_percentage` (signed
                # %) and an `ev_change` delta computed at Step-4 boundary.
                # Both are populated by Step4ResultBuilder.
                adjustment_percentage = owner_conc.get("adjustment_percentage")
                ev_change = owner_conc.get("ev_change")
                number_of_owners = owner_conc.get("number_of_owners")

                if adjustment_percentage is not None:
                    pipeline_stage_4 = {"discount_percentage": adjustment_percentage}
                    # Carry the corroboration verdict through, or the ledger
                    # defaults it to CORROBORATED and renders a registry-sourced
                    # headcount as confirmed fact.
                    for key in ("evidence_grade", "input_basis"):
                        if owner_conc.get(key) is not None:
                            pipeline_stage_4[key] = owner_conc[key]

                # Reconstruct ev_before/after from the delta + the post-
                # Step-4 EV (which the dict often carries as `ev_after`).
                ev_after = owner_conc.get("ev_after")
                if ev_after is None:
                    ev_after = owner_conc.get("enterprise_value_mid")
                if ev_after is not None and ev_change is not None:
                    structural_ev_after = Decimal(str(ev_after))
                    structural_ev_before = structural_ev_after - Decimal(str(ev_change))

            return build_owner_risk_ledger(
                pipeline_stage_4=pipeline_stage_4,
                structural_ev_before=structural_ev_before or Decimal("0"),
                structural_ev_after=structural_ev_after or Decimal("0"),
                owner_dependency_result=owner_dependency_result,
                owner_dependency_adjustment=owner_dependency_adjustment,
                equity_value_mid_after=equity_value_mid_after,
                number_of_owners=number_of_owners,
            )
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            logger.warning(
                "Owner risk ledger: build failed; report will render without it",
                extra={"error": str(e), "error_type": type(e).__name__},
            )
            return None

    def apply_owner_dependency_adjustment(
        self, valuation: SynthesizedValuation, dependency_score: Decimal, adjustment_factor: Decimal
    ) -> SynthesizedValuation:
        """
        Apply owner dependency adjustment to valuation.
        
        Delegates to OwnerDependencyCoordinator.
        
        Args:
            valuation: Original valuation result
            dependency_score: Owner dependency score
            adjustment_factor: Adjustment factor
            
        Returns:
            Adjusted valuation with owner dependency impact
        """
        return self.owner_dependency_coordinator.apply_owner_dependency_adjustment(
            valuation, dependency_score, adjustment_factor
        )
