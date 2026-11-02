"""
Result Aggregation Coordinator

Orchestrates result aggregation and final calculations for the DCF engine.
Handles present value calculations, equity value conversion, confidence assessment, and transparency data.

RESPONSIBILITIES:
- Discount cash flows to present value
- Calculate equity value from enterprise value
- Assess confidence in valuation
- Create transparency data
- Generate valuation summary

ARCHITECTURE:
This coordinator acts as a thin orchestration layer that:
1. Performs present value calculations
2. Converts enterprise value to equity value
3. Assesses confidence
4. Creates transparency data

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive error handling
- Detailed logging
- No code duplication
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Tuple

from src.domain.dcf.dcf_confidence_assessment import assess_dcf_confidence
from src.domain.dcf_types import DCFConfiguration
from src.domain.models import FinancialData
from src.errors.error_types import CalculationError, MultiplesCalculationError
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.exceptions import CalculationError as UtilsCalculationError
from src.utils.logging import get_logger, log_calculation_step

logger = get_logger(__name__)


class ResultAggregationCoordinator:
    """
    Coordinates result aggregation for the DCF engine.

    This coordinator handles:
    1. Present value calculations
    2. Equity value conversion
    3. Confidence assessment
    4. Transparency data creation
    """

    def __init__(
        self,
        financial_data: FinancialData,
        config: DCFConfiguration,
    ) -> None:
        """
        Initialize result aggregation coordinator.

        Args:
            financial_data: Company financial data
            config: DCF configuration
        """
        self.financial_data = financial_data
        self.config = config
        self.logger = logger

    def discount_cash_flows(self, fcf_values: List[Decimal], wacc: Decimal) -> List[Decimal]:
        """
        Discount cash flows to present value using WACC.

        Args:
            fcf_values: List of projected free cash flows
            wacc: Weighted Average Cost of Capital (discount rate)

        Returns:
            List of present values for each projected cash flow
        """
        try:
            wacc_decimal = to_decimal(wacc)
            # Validate WACC
            if wacc_decimal <= 0:
                raise CalculationError(
                    f"WACC must be positive, got {wacc_decimal}",
                    context={"wacc": from_decimal(wacc_decimal)},
                )

            pv_values = []
            period_offset = Decimal("0.5") if self.config.mid_year_discounting else Decimal("1")
            for i, fcf in enumerate(fcf_values):
                year = Decimal(str(i)) + period_offset
                fcf_decimal = to_decimal(fcf)
                # Decimal supports fractional powers. Keep the discounting
                # path decimal through both mid-year and year-end conventions.
                discount_factor = (Decimal("1") + wacc_decimal) ** year
                pv = fcf_decimal / discount_factor
                pv_values.append(pv)

            return pv_values

        except (ValueError, TypeError, ZeroDivisionError) as e:
            self.logger.error(
                f"Cash flow discounting failed: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise CalculationError(
                f"Failed to discount cash flows: {e}",
                context={"fcf_count": len(fcf_values), "wacc": from_decimal(wacc)},
            ) from e

    def calculate_equity_value(self, enterprise_value: Decimal) -> Decimal:
        """
        Calculate equity value from enterprise value.

        Equity Value = Enterprise Value - Net Debt
        Net Debt = Total Debt - Cash

        Args:
            enterprise_value: Enterprise value from DCF calculation

        Returns:
            Equity value (value attributable to shareholders)
        """
        try:
            # Get debt and cash from current year
            current_year = self.financial_data.current_year
            total_debt = to_decimal(current_year.total_debt or 0)
            cash = to_decimal(current_year.cash or 0)

            # Equity Value = Enterprise Value - Net Debt + Cash
            # Net Debt = Total Debt - Cash
            enterprise_value_decimal = to_decimal(enterprise_value)
            net_debt = total_debt - cash
            equity_value = enterprise_value_decimal - net_debt

            # Ensure equity value is positive
            equity_value = max(equity_value, Decimal("0"))

            return equity_value

        except (ValueError, TypeError) as e:
            self.logger.error(
                f"Equity value calculation failed: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise CalculationError(
                f"Failed to calculate equity value: {e}",
                context={"enterprise_value": from_decimal(enterprise_value)},
            ) from e

    def assess_confidence(
        self, historical_fcf: Any, fcf_projections: List[Any], wacc_components: Any
    ) -> Tuple[str, Decimal, List[str]]:
        """
        Assess confidence in the DCF valuation.

        Args:
            historical_fcf: Historical free cash flow analysis
            fcf_projections: Future cash flow projections
            wacc_components: WACC calculation components

        Returns:
            Tuple of (confidence_level, confidence_score, confidence_factors)
        """
        try:
            assessment = assess_dcf_confidence(historical_fcf, fcf_projections, wacc_components)
            return assessment.level, assessment.score, assessment.factors

        except (ValueError, TypeError, AttributeError) as e:
            self.logger.error(
                f"Confidence assessment failed: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            # Return low confidence rather than raising, as this is a non-critical assessment
            return "low", Decimal("0.5"), [f"Confidence assessment failed: {str(e)}"]
        except CalculationError as e:
            self.logger.error(
                f"Unexpected error in confidence assessment: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            return "low", Decimal("0.5"), ["Unexpected error in confidence assessment"]

    def create_transparency_data(self) -> Dict[str, Any]:
        """
        Create transparency data for the valuation.

        Returns:
            Dictionary containing transparency and audit trail data
        """
        try:
            return {
                "calculation_timestamp": datetime.now(timezone.utc).isoformat(),
                "methodology": "dcf_refactored",
                "components_used": [
                    "cash_flow_projector",
                    "discount_rate_calculator",
                    "terminal_value_calculator",
                ],
                "configuration": {
                    "projection_years": self.config.projection_years,
                    "terminal_growth_method": self.config.terminal_growth_method.value,
                    "sensitivity_analysis": self.config.sensitivity_analysis,
                },
                "data_sources": ["financial_statements", "market_data", "industry_benchmarks"],
            }

        except (ValueError, TypeError, AttributeError) as e:
            self.logger.error(
                f"Transparency data creation failed: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            # Return empty dict rather than raising, as transparency is non-critical
            return {}
        except MultiplesCalculationError as e:
            self.logger.error(
                f"Unexpected error in transparency data creation: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            return {}

    def get_valuation_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the valuation configuration and status.

        Returns:
            Dictionary containing valuation configuration and status summary
        """
        return {
            "company": self.financial_data.company_name,
            "configuration": {
                "projection_years": self.config.projection_years,
                "terminal_growth_method": self.config.terminal_growth_method.value,
                "sensitivity_analysis": self.config.sensitivity_analysis,
                "confidence_threshold": self.config.confidence_threshold,
            },
            "components": {
                "cash_flow_projector": "active",
                "discount_rate_calculator": "active",
                "terminal_value_calculator": "active",
            },
            "data_quality": {
                "financial_data": "available",
                "market_context": "available",
                "industry_benchmarks": "available",
            },
        }
