"""
Terminal Value Calculation Coordinator

Orchestrates terminal value calculation for the DCF engine.
Handles Gordon Growth Model and exit multiples approach.

RESPONSIBILITIES:
- Coordinate terminal value calculation
- Handle Gordon Growth Model
- Log terminal value steps
- Handle transparency tracking

ARCHITECTURE:
This coordinator acts as a thin orchestration layer that:
1. Delegates to TerminalValueCalculator for calculations
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

from src.domain.dcf_types import DCFConfiguration, DCFMethodology
from src.domain.models import IndustryBenchmarks, MarketContext
from src.domain.terminal_value_calculator import TerminalValueCalculator
from src.utils.logging import get_logger, log_calculation_step

logger = get_logger(__name__)


class TerminalValueCalculationCoordinator:
    """
    Coordinates terminal value calculation for the DCF engine.
    
    This coordinator handles:
    1. Terminal value calculation
    2. Terminal value discounting
    """
    
    def __init__(
        self,
        terminal_value_calculator: TerminalValueCalculator,
        market_context: MarketContext,
        industry_benchmarks: IndustryBenchmarks,
        config: DCFConfiguration,
        transparency_collector: Optional[Any] = None,
    ) -> None:
        """
        Initialize terminal value calculation coordinator.
        
        Args:
            terminal_value_calculator: Terminal value calculator instance
            market_context: Market context
            industry_benchmarks: Industry benchmarks
            config: DCF configuration
            transparency_collector: Frontend transparency collector
        """
        self.terminal_value_calculator = terminal_value_calculator
        self.market_context = market_context
        self.industry_benchmarks = industry_benchmarks
        self.config = config
        self.transparency_collector = transparency_collector
        self.logger = logger
    
    def calculate_terminal_value(
        self, final_fcf: Decimal, wacc: Decimal
    ) -> Any:
        """
        Calculate terminal value using Gordon Growth Model.
        
        Args:
            final_fcf: Final projected free cash flow
            wacc: Weighted Average Cost of Capital
            
        Returns:
            Terminal value parameters
        """
        log_calculation_step(
            "terminal_value_calculation",
            inputs={
                "final_fcf": final_fcf,
                "wacc": wacc,
                "terminal_growth_method": self.config.terminal_growth_method,
            },
            outputs={},
            formula="Terminal_Value = Final_FCF × (1 + g) / (WACC - g)",
        )
        
        terminal_value_params = self.terminal_value_calculator.calculate_terminal_value(
            final_fcf,
            wacc,
            self.market_context,
            self.industry_benchmarks,
            self.config.terminal_growth_method,
        )
        
        log_calculation_step(
            "terminal_value_results",
            inputs={"terminal_value_params": terminal_value_params},
            outputs={
                "terminal_value": terminal_value_params.terminal_value,
                "terminal_growth_rate": terminal_value_params.terminal_growth_rate,
            },
            formula="Terminal_Value_Results = Calculate_Terminal_Value + Extract_Growth_Rate",
        )
        
        # Add terminal value to transparency collector
        if self.transparency_collector:
            methodology = terminal_value_params.methodology
            if methodology == DCFMethodology.EXIT_MULTIPLE:
                description = "Terminal Value (Exit Multiple)"
                formula = (
                    f"TV = EBITDA_exit × Exit_Multiple = "
                    f"{terminal_value_params.exit_year_ebitda:,.0f} × "
                    f"{terminal_value_params.exit_multiple:.2f}"
                )
                explanation = (
                    "Exit multiple approach values the business at a multiple of terminal year EBITDA. "
                    "Terminal value typically represents 60-80% of enterprise value (Damodaran, 2012)"
                )
            elif methodology == DCFMethodology.HYBRID:
                description = "Terminal Value (Hybrid: GGM + Exit Multiple)"
                formula = (
                    f"TV = avg(GGM, Exit_Multiple) where "
                    f"GGM = {final_fcf:,.0f} × (1 + {terminal_value_params.terminal_growth_rate:.4f}) / "
                    f"({wacc:.4f} - {terminal_value_params.terminal_growth_rate:.4f}), "
                    f"Exit = {terminal_value_params.exit_year_ebitda:,.0f} × "
                    f"{terminal_value_params.exit_multiple:.2f}"
                )
                explanation = (
                    "Hybrid approach averages Gordon Growth Model and exit multiple for robustness. "
                    "Terminal value typically represents 60-80% of enterprise value (Damodaran, 2012)"
                )
            else:
                description = "Terminal Value (Gordon Growth Model)"
                formula = (
                    f"TV = FCF_final × (1 + g) / (WACC - g) = "
                    f"{final_fcf:,.0f} × (1 + {terminal_value_params.terminal_growth_rate:.4f}) / "
                    f"({wacc:.4f} - {terminal_value_params.terminal_growth_rate:.4f})"
                )
                explanation = (
                    "Gordon Growth Model assumes perpetual growth at terminal rate. "
                    "Terminal value typically represents 60-80% of enterprise value (Damodaran, 2012)"
                )

            self.transparency_collector.add_calculation_step(
                description=description,
                formula=formula,
                inputs={
                    "final_fcf": round(final_fcf, 2),
                    "terminal_growth_rate": round(
                        terminal_value_params.terminal_growth_rate, 4
                    ),
                    "wacc": round(wacc, 4),
                },
                outputs={
                    "terminal_value": round(terminal_value_params.terminal_value, 2),
                    "pv_terminal_value": round(terminal_value_params.pv_terminal_value, 2),
                },
                explanation=explanation,
            )
        
        return terminal_value_params
    
    def discount_terminal_value(
        self, terminal_value: Decimal, wacc: Decimal, projection_years: int
    ) -> Decimal:
        """
        Discount terminal value to present value.
        
        Args:
            terminal_value: Terminal value
            wacc: Weighted Average Cost of Capital
            projection_years: Number of projection years
            
        Returns:
            Present value of terminal value
        """
        return self.terminal_value_calculator.discount_terminal_value(
            terminal_value, wacc, projection_years
        )

