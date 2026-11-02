"""
Market Multiples Valuation Engine - Refactored (Coordinator Pattern)

Valuation based on comparable companies and transaction multiples.
Uses EV/EBITDA, EV/Revenue, and P/E ratios with appropriate adjustments.

Methodology:
1. Find comparable companies (via FMP adapter or manually provided)
2. Calculate median market multiples
3. Apply multiples to subject company metrics
4. Apply adjustments (size, liquidity, geography, growth)
5. Calculate weighted valuation range

Architecture (Coordinator Pattern):
- MarketMultiplesRetrievalCoordinator: Retrieves market multiples from comparables or benchmarks
- DiscountCalculationCoordinator: Calculates size, liquidity, country, and growth adjustments
- ValuationCalculationCoordinator: Calculates weighted EV and equity value
- ConfidenceAssessmentCoordinator: Assesses confidence and quality scoring

REFACTORING (December 2025):
- File size reduced from 1,033 → 212 lines (79% reduction)
- Extracted 4 coordinator classes following Coordinator Pattern
- Extracted MultiplesCalculationOrchestrator for workflow coordination
- Extracted MultiplesTransparencyTracker for transparency tracking
- Removed all private methods (now handled by coordinators)
- Improved maintainability, testability, and separation of concerns
- Single Responsibility Principle fully applied
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional, Mapping

from src.domain.models import (
    ComparableCompany,
    FinancialData,
    IndustryBenchmarks,
    MarketContext,
    MultiplesResult,
)

from src.errors.error_types import (
    CalculationError,
    DataQualityError,
    MarketDataError,
    MultiplesCalculationError,
    ValidationError,
)
from src.domain.interfaces.transparency_protocol import TransparencyTrackerProtocol
from src.domain.multiples.advisor_controls import DEFAULT_DISCOUNT_FLOOR_FACTOR
from src.utils.logging import get_logger, log_calculation_step
from src.utils.logging_context import get_current_context

# Import coordinators
from .multiples.coordinators.market_multiples_retrieval_coordinator import (
    MarketMultiplesRetrievalCoordinator,
)
from .multiples.coordinators.discount_calculation_coordinator import DiscountCalculationCoordinator
from .multiples.coordinators.valuation_calculation_coordinator import (
    ValuationCalculationCoordinator,
)
from .multiples.coordinators.confidence_assessment_coordinator import (
    ConfidenceAssessmentCoordinator,
)

# Import orchestrator and transparency tracker
from .multiples.orchestrators.multiples_calculation_orchestrator import (
    MultiplesCalculationOrchestrator,
)
from .multiples.transparency.multiples_transparency_tracker import MultiplesTransparencyTracker

logger = get_logger(__name__)


class MarketMultiplesEngine:
    """
    Market multiples valuation engine.

    Values companies based on how similar companies are valued in the market.
    """

    def __init__(
        self,
        financial_data: FinancialData,
        market_context: MarketContext,
        industry_benchmarks: IndustryBenchmarks,
        comparables: Optional[List[ComparableCompany]] = None,
        transparency_tracker: Optional["TransparencyTrackerProtocol"] = None,
        transparency_collector: Optional[Any] = None,  # NEW: Frontend transparency collector
        multiple_type_weights: Optional[Mapping[str, object]] = None,
        default_multiple_type_weights: Optional[Mapping[str, object]] = None,
        default_multiple_type_source: str = "sector_aware_default",
        advisor_discount_weights: Optional[Mapping[str, object]] = None,
        risk_analysis_enabled: bool = True,
        discount_floor_factor: object = DEFAULT_DISCOUNT_FLOOR_FACTOR,
        strength_factor_discount_adjustments: object = None,
    ) -> None:
        """
        Initialize market multiples engine.

        Args:
            financial_data: Company financial data
            market_context: Market and economic context
            industry_benchmarks: Industry benchmarks (including median multiples)
            comparables: Optional list of comparable companies
            transparency_tracker: Optional transparency tracker for data provenance (legacy)
            transparency_collector: Optional transparency collector for frontend (new)
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

        # Legacy transparency tracker (for existing system)
        # Use protocol to avoid service layer dependency
        if transparency_tracker is None:
            # Lazy import only when needed to avoid circular dependency
            try:
                from src.services.privacy.compliance.transparency_tracker import TransparencyTracker

                self.transparency: Optional[TransparencyTrackerProtocol] = TransparencyTracker()
            except ImportError:
                # Fallback if service not available
                self.transparency = None
        else:
            self.transparency = transparency_tracker

        # NEW: Transparency collector for frontend
        self.transparency_collector = transparency_collector

        # Initialize orchestrator (handles workflow coordination)
        self.orchestrator = MultiplesCalculationOrchestrator(
            financial_data=self.financial_data,
            market_context=self.market_context,
            industry_benchmarks=self.industry_benchmarks,
            comparables=self.comparables,
            transparency_tracker=self.transparency,
            transparency_collector=self.transparency_collector,
            multiple_type_weights=multiple_type_weights,
            default_multiple_type_weights=default_multiple_type_weights,
            default_multiple_type_source=default_multiple_type_source,
            advisor_discount_weights=advisor_discount_weights,
            risk_analysis_enabled=risk_analysis_enabled,
            discount_floor_factor=discount_floor_factor,
            strength_factor_discount_adjustments=strength_factor_discount_adjustments,
        )

        # Keep coordinators accessible for backward compatibility
        self.market_multiples_coordinator = self.orchestrator.market_multiples_coordinator
        self.discount_coordinator = self.orchestrator.discount_coordinator
        self.valuation_coordinator = self.orchestrator.valuation_coordinator
        self.confidence_coordinator = self.orchestrator.confidence_coordinator

    def calculate_multiples_valuation(self) -> MultiplesResult:
        """
        Calculate valuation using market multiples with enhanced logging.

        Delegates to orchestrator for workflow execution.

        Returns:
            MultiplesResult with detailed valuation breakdown
        """
        try:
            # Get current logging context
            logging_context = get_current_context()
            session_id = (
                getattr(logging_context, "current_session_id", None) if logging_context else None
            )

            # Log multiples calculation start
            log_calculation_step(
                "multiples_calculation_start",
                inputs={
                    "company_name": self.financial_data.company_name,
                    "comparables_count": len(self.comparables),
                    "financial_data": {
                        "revenue": self.financial_data.current_year.revenue,
                        "ebitda": self.financial_data.current_year.ebitda,
                        "net_income": self.financial_data.current_year.net_income,
                    },
                },
                outputs={"calculation_id": f"multiples_{datetime.now().strftime('%Y%m%d_%H%M%S')}"},
                formula="Multiples_Start = Initialize_Calculation + Setup_Logging + Start_Processing",
            )

            logger.calculation(
                "Starting market multiples valuation calculation",
                session_id=session_id,
                company=self.financial_data.company_name,
                comparables_count=len(self.comparables),
            )

            # Delegate to orchestrator for workflow execution
            result = self.orchestrator.execute_calculation_workflow()

            logger.info(
                "Market multiples valuation complete",
                base_value=(
                    f"\u20AC{result.base_value:,.0f}" if hasattr(result, "base_value") else "N/A"
                ),
                adjusted_equity_value=(
                    f"\u20AC{result.adjusted_equity_value:,.0f}"
                    if hasattr(result, "adjusted_equity_value")
                    else "N/A"
                ),
                confidence=result.confidence.value if hasattr(result, "confidence") else "N/A",
            )

            return result

        except (CalculationError, DataQualityError, MarketDataError, ValidationError) as exc:
            # Re-raise specific errors, but track them first
            self.orchestrator.transparency_tracker.track_error(
                exc, self.financial_data, self.industry_benchmarks, self.comparables
            )
            raise
        except (ValueError, TypeError, ZeroDivisionError, AttributeError, KeyError) as e:
            # Track error in transparency collector before raising
            self.orchestrator.transparency_tracker.track_error(
                e, self.financial_data, self.industry_benchmarks, self.comparables
            )
            logger.error(
                f"Multiples valuation failed: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
                exc_info=True,
            )
            raise CalculationError(
                f"Failed to calculate multiples valuation: {e}",
                calculation_type="Multiples Valuation",
                context={
                    "company": self.financial_data.company_name,
                    "comparables_count": len(self.comparables),
                },
            ) from e
        except MultiplesCalculationError as e:
            # Track error in transparency collector before raising
            self.orchestrator.transparency_tracker.track_error(
                e, self.financial_data, self.industry_benchmarks, self.comparables
            )
            logger.error(
                f"Unexpected error in multiples valuation: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
                exc_info=True,
            )
            raise
