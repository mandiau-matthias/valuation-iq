"""
Discount Rate Calculation Coordinator

Orchestrates WACC calculation for the DCF engine.
Handles discount rate calculation and transparency tracking.

RESPONSIBILITIES:
- Coordinate WACC calculation
- Log WACC components
- Track transparency data

ARCHITECTURE:
This coordinator acts as a thin orchestration layer that:
1. Delegates to DiscountRateCalculator for WACC calculation
2. Logs calculation steps
3. Handles transparency tracking

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive error handling
- Detailed logging
- No code duplication
"""

from decimal import Decimal
from typing import Any, Optional

from src.domain.discount_rate_calculator import DiscountRateCalculator
from src.domain.models import FinancialData, IndustryBenchmarks, MarketContext
from src.utils.logging import get_logger, log_calculation_step

logger = get_logger(__name__)


class DiscountRateCalculationCoordinator:
    """
    Coordinates discount rate calculation for the DCF engine.
    
    This coordinator handles:
    1. WACC calculation
    2. WACC component logging
    """
    
    def __init__(
        self,
        discount_rate_calculator: DiscountRateCalculator,
        financial_data: FinancialData,
        market_context: MarketContext,
        industry_benchmarks: IndustryBenchmarks,
        transparency_collector: Optional[Any] = None,
        size_premium: Optional[Decimal] = None,
        customer_concentration: Optional[Decimal] = None,
        industry: Optional[str] = None,
        has_audit: Optional[bool] = None,
        owner_dependency_score: Optional[Decimal] = None,
    ) -> None:
        """
        Initialize discount rate calculation coordinator.
        
        Args:
            discount_rate_calculator: Discount rate calculator instance
            financial_data: Company financial data
            market_context: Market context
            industry_benchmarks: Industry benchmarks
            transparency_collector: Frontend transparency collector
            size_premium: SME size premium from Titan DB (Duff & Phelps 2024)
            customer_concentration: Top-customer concentration (0-1)
            industry: Industry / NACE category
            has_audit: Whether financials are audited
            owner_dependency_score: Owner dependency risk score (0-1)
        """
        self.discount_rate_calculator = discount_rate_calculator
        self.financial_data = financial_data
        self.market_context = market_context
        self.industry_benchmarks = industry_benchmarks
        self.transparency_collector = transparency_collector
        self.size_premium = size_premium
        self.customer_concentration = customer_concentration
        self.industry = industry
        self.has_audit = has_audit
        self.owner_dependency_score = owner_dependency_score
        self.logger = logger
    
    def calculate_wacc(self) -> Any:
        """
        Calculate Weighted Average Cost of Capital (WACC).
        
        Returns:
            WACC components result
        """
        log_calculation_step(
            "wacc_calculation",
            inputs={
                "financial_data": {
                    "total_equity": self.financial_data.current_year.total_equity if self.financial_data.current_year.total_equity else None,
                    "total_debt": self.financial_data.current_year.total_debt if self.financial_data.current_year.total_debt else None,
                },
                "market_context": {
                    "risk_free_rate": self.market_context.government_bond_yield,
                    "market_premium": self.market_context.equity_risk_premium,
                },
            },
            outputs={},
            formula="WACC = (E/V × Re) + (D/V × Rd × (1-T))",
        )
        
        wacc_components = self.discount_rate_calculator.calculate_wacc(
            self.financial_data, self.market_context, self.industry_benchmarks,
            size_premium=self.size_premium,
            customer_concentration=self.customer_concentration,
            industry=self.industry,
            has_audit=self.has_audit,
            owner_dependency_score=self.owner_dependency_score,
        )
        
        log_calculation_step(
            "wacc_results",
            inputs={"wacc_components": wacc_components},
            outputs={
                "wacc": wacc_components.wacc,
                "cost_of_equity": wacc_components.cost_of_equity,
                "cost_of_debt": wacc_components.cost_of_debt,
            },
            formula="WACC_Results = Calculate_WACC + Extract_Components",
        )
        
        # Add to transparency collector for frontend
        if self.transparency_collector:
            self.transparency_collector.add_calculation_step(
                description="Weighted Average Cost of Capital (WACC)",
                formula=f"WACC = (E/V × Re) + (D/V × Rd × (1-T)) = "
                f"({wacc_components.equity_weight:.2f} × {wacc_components.cost_of_equity:.4f}) + "
                f"({wacc_components.debt_weight:.2f} × {wacc_components.cost_of_debt:.4f} × (1-{wacc_components.tax_rate:.2f}))",
                inputs={
                    "cost_of_equity": round(wacc_components.cost_of_equity, 4),
                    "cost_of_debt": round(wacc_components.cost_of_debt, 4),
                    "equity_weight": round(wacc_components.equity_weight, 4),
                    "debt_weight": round(wacc_components.debt_weight, 4),
                    "tax_rate": round(wacc_components.tax_rate, 4),
                    "company_specific_risk": round(wacc_components.company_specific_risk, 4),
                },
                outputs={"wacc": round(wacc_components.wacc, 4)},
                explanation="Calculated weighted average cost of capital using CAPM for cost of equity. "
                "WACC represents the discount rate for future cash flows.",
            )
        
        return wacc_components

