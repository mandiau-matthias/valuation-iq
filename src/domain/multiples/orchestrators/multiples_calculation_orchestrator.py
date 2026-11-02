"""
Multiples Calculation Orchestrator

Extracted from MarketMultiplesEngine to follow Single Responsibility Principle.
Orchestrates the multiples calculation workflow.

Author: Upswitch CTO Team
Date: December 2025
Status: Production Ready
"""

from decimal import Decimal
from typing import Dict, Any, Optional, Tuple, List, Mapping

from src.domain.models import (
    FinancialData,
    IndustryBenchmarks,
    MarketContext,
    MultiplesResult,
    ComparableCompany,
    ConfidenceLevel,
)
from src.domain.multiples.coordinators.market_multiples_retrieval_coordinator import (
    MarketMultiplesRetrievalCoordinator,
)
from src.domain.multiples.coordinators.discount_calculation_coordinator import (
    DiscountCalculationCoordinator,
)
from src.domain.multiples.coordinators.valuation_calculation_coordinator import (
    ValuationCalculationCoordinator,
)
from src.domain.multiples.coordinators.confidence_assessment_coordinator import (
    ConfidenceAssessmentCoordinator,
)
from src.domain.multiples.advisor_controls import (
    DEFAULT_DISCOUNT_FLOOR_FACTOR,
    build_adjusted_ebitda_build_up,
    build_pipeline_multiple_build_up,
    normalize_earnings_basis,
)
from src.domain.multiples.transparency.multiples_transparency_tracker import (
    MultiplesTransparencyTracker,
)
from src.utils.logging import get_logger, log_calculation_step
from src.utils.logging_context import get_current_context
from src.utils.decimal_helpers import to_decimal

logger = get_logger(__name__)


class MultiplesCalculationOrchestrator:
    """
    Orchestrates multiples calculation workflow.

    Single Responsibility: Workflow orchestration only.
    Delegates actual calculations to coordinators.
    """

    def __init__(
        self,
        financial_data: FinancialData,
        market_context: MarketContext,
        industry_benchmarks: IndustryBenchmarks,
        comparables: Optional[List[ComparableCompany]] = None,
        transparency_tracker: Optional[Any] = None,
        transparency_collector: Optional[Any] = None,
        multiple_type_weights: Optional[Mapping[str, object]] = None,
        default_multiple_type_weights: Optional[Mapping[str, object]] = None,
        default_multiple_type_source: str = "sector_aware_default",
        advisor_discount_weights: Optional[Mapping[str, object]] = None,
        risk_analysis_enabled: bool = True,
        discount_floor_factor: object = DEFAULT_DISCOUNT_FLOOR_FACTOR,
        strength_factor_discount_adjustments: object = None,
    ):
        """
        Initialize orchestrator with coordinators.

        Args:
            financial_data: Company financial data
            market_context: Market and economic context
            industry_benchmarks: Industry benchmarks
            comparables: Optional list of comparable companies
            transparency_tracker: Optional transparency tracker (legacy)
            transparency_collector: Optional transparency collector (new)
            multiple_type_weights: Optional advisor-provided method blend
            default_multiple_type_weights: Optional model/default method blend
            default_multiple_type_source: Source label for the model/default blend
            advisor_discount_weights: Optional advisor discount influence multipliers
            risk_analysis_enabled: Master toggle for the risk/discount layer
            discount_floor_factor: Lower bound for the multiplicative discount stack
            strength_factor_discount_adjustments: Explicit business-type strength-factor
                evidence that adjusts whitelisted multiple discount rows.
        """
        self.financial_data = financial_data
        self.market_context = market_context
        self.industry_benchmarks = industry_benchmarks
        self.comparables = comparables or []
        self.multiple_type_weights = multiple_type_weights
        self.default_multiple_type_weights = default_multiple_type_weights
        self.default_multiple_type_source = default_multiple_type_source
        self.advisor_discount_weights = advisor_discount_weights
        self.risk_analysis_enabled = risk_analysis_enabled
        self.discount_floor_factor = discount_floor_factor
        self.strength_factor_discount_adjustments = strength_factor_discount_adjustments

        # Initialize coordinators
        self.market_multiples_coordinator = MarketMultiplesRetrievalCoordinator(
            financial_data=self.financial_data,
            industry_benchmarks=self.industry_benchmarks,
            comparables=self.comparables,
            transparency=transparency_tracker,
            transparency_collector=transparency_collector,
        )
        self.discount_coordinator = DiscountCalculationCoordinator(
            financial_data=self.financial_data,
            market_context=self.market_context,
        )
        self.valuation_coordinator = ValuationCalculationCoordinator(
            financial_data=self.financial_data,
        )
        self.confidence_coordinator = ConfidenceAssessmentCoordinator(
            financial_data=self.financial_data,
            industry_benchmarks=self.industry_benchmarks,
            comparables=self.comparables,
        )

        # Initialize transparency tracker
        self.transparency_tracker = MultiplesTransparencyTracker(transparency_collector)
        self.adjusted_ebitda_build_up: Dict[str, Any] = {}

    def calculate_enterprise_values(
        self,
        ebitda_multiple: Optional[Decimal],
        revenue_multiple: Optional[Decimal],
        pe_multiple: Optional[Decimal],
    ) -> Tuple[Optional[Decimal], Optional[Decimal], Optional[Decimal]]:
        """
        Calculate enterprise values using different multiples.

        Returns:
            Tuple of (ev_ebitda_valuation, ev_revenue_valuation, pe_valuation)
        """
        self.adjusted_ebitda_build_up = build_adjusted_ebitda_build_up(
            self.financial_data.current_year
        )
        adjusted_ebitda = self.adjusted_ebitda_build_up.get("adjusted_ebitda")
        current_ebitda = to_decimal(
            adjusted_ebitda if adjusted_ebitda is not None else self.financial_data.current_year.ebitda
        )
        ev_ebitda_valuation = None
        if ebitda_multiple and current_ebitda > 0:
            ev_ebitda_valuation = current_ebitda * ebitda_multiple

        ev_revenue_valuation = None
        if revenue_multiple:
            ev_revenue_valuation = self.financial_data.current_year.revenue * revenue_multiple

        pe_valuation = None
        if pe_multiple and self.financial_data.current_year.net_income:
            if self.financial_data.current_year.net_income > 0:
                pe_valuation = self.financial_data.current_year.net_income * pe_multiple

        return ev_ebitda_valuation, ev_revenue_valuation, pe_valuation

    def execute_calculation_workflow(self) -> MultiplesResult:
        """
        Execute the complete multiples calculation workflow.

        Returns:
            MultiplesResult with detailed valuation breakdown
        """
        # Step 1: Get market multiples
        ebitda_multiple, revenue_multiple, pe_multiple = (
            self.market_multiples_coordinator.get_market_multiples()
        )

        # Track market multiples
        self.transparency_tracker.track_market_multiples(
            ebitda_multiple,
            revenue_multiple,
            pe_multiple,
            self.comparables,
            self.industry_benchmarks,
            self.financial_data,
        )
        self.transparency_tracker.track_data_sources(
            ebitda_multiple, revenue_multiple, self.comparables
        )
        self.transparency_tracker.track_comparable_companies(self.comparables)

        # Track industry benchmarks
        self.market_multiples_coordinator.track_industry_benchmarks()

        # Step 2: Calculate enterprise values
        ev_ebitda_valuation, ev_revenue_valuation, pe_valuation = self.calculate_enterprise_values(
            ebitda_multiple, revenue_multiple, pe_multiple
        )
        adjusted_ebitda_build_up = self.adjusted_ebitda_build_up

        # Track enterprise value calculation
        self.transparency_tracker.track_enterprise_value_calculation(
            ev_ebitda_valuation,
            ev_revenue_valuation,
            ebitda_multiple,
            revenue_multiple,
            self.financial_data,
        )

        # Step 3: Calculate adjustments
        adjustments = self.discount_coordinator.calculate_all_adjustments(
            advisor_discount_weights=self.advisor_discount_weights,
            risk_analysis_enabled=self.risk_analysis_enabled,
            discount_floor_factor=self.discount_floor_factor,
            strength_factor_discount_adjustments=self.strength_factor_discount_adjustments,
        )
        size_discount = adjustments["size_discount"]
        liquidity_discount = adjustments["liquidity_discount"]
        country_adjustment = adjustments["country_adjustment"]
        growth_premium = adjustments["growth_premium"]
        total_adjustment = to_decimal(adjustments["total_adjustment"])
        discount_stack = adjustments.get("discount_stack", {})

        # Track adjustments
        self.transparency_tracker.track_adjustments(
            size_discount, liquidity_discount, country_adjustment, growth_premium, total_adjustment
        )

        # Step 4: Calculate weighted enterprise value
        weighted_ev = self.valuation_coordinator.calculate_weighted_valuation(
            ev_ebitda_valuation,
            ev_revenue_valuation,
            pe_valuation,
            multiple_type_weights=self.multiple_type_weights,
            default_multiple_type_weights=self.default_multiple_type_weights,
            default_multiple_type_source=self.default_multiple_type_source,
        )
        multiple_type_blend = self.valuation_coordinator.last_multiple_type_blend

        adjusted_ev = weighted_ev * total_adjustment

        # Step 6: Calculate equity value
        balance_sheet_adjustments = list(
            getattr(self.financial_data, "balance_sheet_adjustments", []) or []
        )
        equity_value = self.valuation_coordinator.calculate_equity_value(
            adjusted_ev,
            balance_sheet_adjustments=balance_sheet_adjustments,
        )
        ev_equity_bridge = self.valuation_coordinator.last_ev_equity_bridge

        # Step 7: Assess confidence
        confidence_level, confidence_score = self.confidence_coordinator.assess_confidence()
        comparables_quality = self.confidence_coordinator.assess_comparables_quality()

        # Step 8: Calculate valuation range (simple ±20% range)
        range_factor = Decimal("0.20")
        valuation_range = {
            "low": equity_value * (Decimal("1.0") - range_factor),
            "high": equity_value * (Decimal("1.0") + range_factor),
        }

        # Build result (matching MultiplesResult structure)
        return MultiplesResult(
            ev_ebitda_valuation=ev_ebitda_valuation,
            ev_revenue_valuation=ev_revenue_valuation,
            pe_valuation=pe_valuation,
            ebitda_multiple=ebitda_multiple,
            revenue_multiple=revenue_multiple,
            pe_multiple=pe_multiple,
            comparables_count=len(self.comparables),
            comparables_quality=comparables_quality,
            base_value=weighted_ev,
            size_discount=size_discount,
            liquidity_discount=liquidity_discount,
            country_adjustment=country_adjustment,
            growth_premium=growth_premium,
            total_adjustment=total_adjustment - Decimal("1.0"),  # Convert to adjustment %
            adjusted_equity_value=equity_value,
            confidence=confidence_level,
            confidence_score=confidence_score,
            earnings_basis=normalize_earnings_basis("EBITDA" if ev_ebitda_valuation else "Revenue"),
            adjusted_ebitda_build_up=adjusted_ebitda_build_up,
            reported_ebitda=(
                to_decimal(adjusted_ebitda_build_up.get("reported_ebitda"))
                if adjusted_ebitda_build_up.get("reported_ebitda") is not None
                else None
            ),
            adjusted_ebitda=(
                to_decimal(adjusted_ebitda_build_up.get("adjusted_ebitda"))
                if adjusted_ebitda_build_up.get("adjusted_ebitda") is not None
                else None
            ),
            multiple_type_blend=multiple_type_blend,
            discount_build_up=discount_stack if isinstance(discount_stack, dict) else {},
            ev_equity_bridge=ev_equity_bridge,
            nwc_normalization=(
                ev_equity_bridge.get("nwc_normalization", {})
                if isinstance(ev_equity_bridge, dict)
                else {}
            ),
            nwc_surplus_deficit=to_decimal(
                ev_equity_bridge.get("nwc_surplus_deficit", 0)
                if isinstance(ev_equity_bridge, dict)
                else 0
            ),
            balance_sheet_adjustments=(
                ev_equity_bridge.get("balance_sheet_adjustments", [])
                if isinstance(ev_equity_bridge, dict)
                else []
            ),
            multiple_build_up=build_pipeline_multiple_build_up(
                {
                    "metric_type": "EBITDA" if ev_ebitda_valuation else "Revenue",
                    "metric_value": (
                        adjusted_ebitda_build_up.get("adjusted_ebitda")
                        or self.financial_data.current_year.ebitda
                        if ev_ebitda_valuation
                        else self.financial_data.current_year.revenue
                    ),
                    "reported_ebitda": adjusted_ebitda_build_up.get("reported_ebitda"),
                    "adjusted_ebitda": adjusted_ebitda_build_up.get("adjusted_ebitda"),
                    "adjusted_ebitda_build_up": adjusted_ebitda_build_up,
                    "initial_multiple_mid": ebitda_multiple or revenue_multiple or pe_multiple,
                    "final_multiple_mid": ebitda_multiple or revenue_multiple or pe_multiple,
                    "total_reduction_percentage": (total_adjustment - Decimal("1.0"))
                    * Decimal("100"),
                    "discount_waterfall": (
                        discount_stack.get("rows", []) if isinstance(discount_stack, dict) else []
                    ),
                    "stages": [],
                }
            )
            or {},
            advisor_override_governance={
                "label": "Upswitch model",
                "index_protected": True,
                "requires_rationale": True,
                "source": "system_default",
            },
        )
