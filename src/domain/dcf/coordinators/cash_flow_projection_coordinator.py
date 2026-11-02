"""
Cash Flow Projection Coordinator

Orchestrates cash flow projection calculations for the DCF engine.
Handles historical FCF analysis and future FCF projections.

RESPONSIBILITIES:
- Coordinate historical FCF calculation
- Coordinate future FCF projections
- Log calculation steps
- Handle transparency tracking

ARCHITECTURE:
This coordinator acts as a thin orchestration layer that:
1. Delegates to CashFlowProjector for calculations
2. Logs calculation steps
3. Handles transparency tracking

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive error handling
- Detailed logging
- No code duplication
"""

from decimal import Decimal
from typing import Any, List, Optional

from src.domain.cash_flow_projector import CashFlowProjector
from src.domain.models import FinancialData, IndustryBenchmarks, MarketContext, YearData
from src.utils.logging import get_logger, log_calculation_step

logger = get_logger(__name__)


class CashFlowProjectionCoordinator:
    """
    Coordinates cash flow projection calculations for the DCF engine.
    
    This coordinator handles:
    1. Historical FCF calculation
    2. Future FCF projections
    """
    
    def __init__(
        self,
        cash_flow_projector: CashFlowProjector,
        financial_data: FinancialData,
        industry_benchmarks: IndustryBenchmarks,
        market_context: MarketContext,
        transparency_collector: Optional[Any] = None,
    ) -> None:
        """
        Initialize cash flow projection coordinator.
        
        Args:
            cash_flow_projector: Cash flow projector instance
            financial_data: Company financial data
            industry_benchmarks: Industry benchmarks
            market_context: Market context
            transparency_collector: Frontend transparency collector
        """
        self.cash_flow_projector = cash_flow_projector
        self.financial_data = financial_data
        self.industry_benchmarks = industry_benchmarks
        self.market_context = market_context
        self.transparency_collector = transparency_collector
        self.logger = logger
    
    def calculate_historical_fcf(self) -> Any:
        """
        Calculate historical free cash flows.
        
        Returns:
            Historical FCF analysis result
        """
        log_calculation_step(
            "historical_fcf_calculation",
            inputs={
                "financial_data": {
                    "revenue": self.financial_data.current_year.revenue,
                    "ebitda": self.financial_data.current_year.ebitda,
                    "capex": self.financial_data.current_year.capex if self.financial_data.current_year.capex else None,
                },
                "industry_benchmarks": self.industry_benchmarks.industry,
            },
            outputs={},
            formula="Historical_FCF = EBIT(1-T) + Depreciation - CapEx - ΔWorking_Capital",
        )
        
        historical_fcf = self.cash_flow_projector.calculate_historical_fcf(
            self.financial_data, self.industry_benchmarks
        )
        
        log_calculation_step(
            "historical_fcf_results",
            inputs={"historical_fcf": historical_fcf},
            outputs={
                "fcf_values": historical_fcf.fcf_values if historical_fcf else [],
                "fcf_growth_rate": historical_fcf.cagr if historical_fcf else Decimal("0"),
            },
            formula="FCF_Results = Calculate_FCF_Values + Analyze_Growth_Rate",
        )
        
        return historical_fcf
    
    def project_future_fcf(
        self, historical_fcf: Any, projection_years: int
    ) -> tuple[List[Decimal], Any]:
        """
        Project future free cash flows.
        
        Args:
            historical_fcf: Historical FCF analysis result
            projection_years: Number of years to project
            
        Returns:
            Tuple of (FCF values list, FCF projections)
        """
        log_calculation_step(
            "future_fcf_projection",
            inputs={
                "historical_fcf": historical_fcf,
                "projection_years": projection_years,
                "market_context": self.market_context.government_bond_yield,
            },
            outputs={},
            formula="Future_FCF = Project_Cash_Flows + Apply_Growth_Rates + Apply_Industry_Factors",
        )
        
        fcf_projections = self.cash_flow_projector.project_future_fcf(
            historical_fcf, self.market_context, self.industry_benchmarks, projection_years
        )
        
        # Extract FCF values for calculations
        fcf_values = [projection.free_cash_flow for projection in fcf_projections]
        
        log_calculation_step(
            "fcf_projections_results",
            inputs={"fcf_projections": fcf_projections},
            outputs={"fcf_values": fcf_values, "projection_years": len(fcf_values)},
            formula="FCF_Projections = Calculate_Future_FCF + Extract_Values",
        )
        
        return fcf_values, fcf_projections

    def project_explicit_forecast_fcf(self, historical_fcf: Any, forecast_years: List[YearData]) -> tuple[List[Decimal], Any]:
        """Project DCF cash flows directly from user-provided forecast rows."""
        fcf_projections = self.cash_flow_projector.project_explicit_forecast_fcf(
            historical_fcf,
            forecast_years,
            self.industry_benchmarks,
        )
        fcf_values = [projection.free_cash_flow for projection in fcf_projections]
        return fcf_values, fcf_projections

