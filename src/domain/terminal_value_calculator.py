from src.utils.exceptions import (
    CalculationError,
    DataQualityError,
    DCFCalculationError,
    MultiplesCalculationError,
    ValuationRangeError,
)

"""
Terminal Value Calculator

This module handles terminal value calculation and sensitivity analysis
for DCF valuation, including Gordon Growth Model and exit multiple methods.
"""

from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import numpy as np

from src.utils.decimal_helpers import bank_round, from_decimal, to_decimal
from src.utils.logging import get_logger

from .dcf_types import (
    DEFAULT_DCF_CONFIG,
    SENSITIVITY_RANGES,
    DCFConfiguration,
    DCFMethodology,
    SensitivityRange,
    SensitivityResult,
    SensitivityType,
    TerminalValueParams,
)
from .models import IndustryBenchmarks, MarketContext

logger = get_logger(__name__)


class TerminalValueCalculator:
    """
    Terminal value calculation service for DCF valuation

    Handles:
    - Terminal value calculation (Gordon Growth Model)
    - Terminal growth rate estimation
    - Exit multiple method (alternative)
    - Sensitivity analysis for WACC
    - Sensitivity analysis for growth rates
    - Terminal value adjustments
    """

    def __init__(self, config: Optional[DCFConfiguration] = None):
        """Initialize the terminal value calculator"""
        self.logger = logger
        self.config = config or DEFAULT_DCF_CONFIG

        self.logger.info("TerminalValueCalculator initialized")

    def calculate_terminal_value(
        self,
        final_fcf: Decimal,
        wacc: Decimal,
        market_context: MarketContext,
        industry_benchmarks: IndustryBenchmarks,
        methodology: DCFMethodology = DCFMethodology.GORDON_GROWTH,
    ) -> TerminalValueParams:
        """
        Calculate terminal value using specified methodology.

        Args:
            final_fcf: Final projected FCF
            wacc: Weighted Average Cost of Capital
            market_context: Market context
            industry_benchmarks: Industry benchmarks
            methodology: Terminal value methodology

        Returns:
            TerminalValueParams with calculation details
        """
        try:
            self.logger.info(
                "Calculating terminal value",
                final_fcf=from_decimal(final_fcf),
                wacc=f"{from_decimal(wacc):.2%}",
                methodology=methodology.value,
            )

            if methodology == DCFMethodology.GORDON_GROWTH:
                terminal_value_params = self._calculate_gordon_growth_terminal_value(
                    final_fcf, wacc, market_context, industry_benchmarks
                )
            elif methodology == DCFMethodology.EXIT_MULTIPLE:
                terminal_value_params = self._calculate_exit_multiple_terminal_value(
                    final_fcf, market_context, industry_benchmarks
                )
            elif methodology == DCFMethodology.HYBRID:
                # Use both methods and average
                gordon_params = self._calculate_gordon_growth_terminal_value(
                    final_fcf, wacc, market_context, industry_benchmarks
                )
                exit_params = self._calculate_exit_multiple_terminal_value(
                    final_fcf, market_context, industry_benchmarks
                )

                # Average the results
                terminal_value_params = TerminalValueParams(
                    final_fcf=from_decimal(final_fcf),
                    terminal_growth_rate=gordon_params.terminal_growth_rate,
                    wacc=from_decimal(wacc),
                    terminal_value=from_decimal(
                        (
                            to_decimal(gordon_params.terminal_value)
                            + to_decimal(exit_params.terminal_value)
                        )
                        / Decimal("2")
                    ),
                    pv_terminal_value=from_decimal(
                        (
                            to_decimal(gordon_params.pv_terminal_value)
                            + to_decimal(exit_params.pv_terminal_value)
                        )
                        / Decimal("2")
                    ),
                    methodology=methodology,
                    exit_multiple=exit_params.exit_multiple,
                    exit_year_ebitda=exit_params.exit_year_ebitda,
                    terminal_growth_evidence=gordon_params.terminal_growth_evidence,
                )
            else:
                raise ValueError(f"Unknown terminal value methodology: {methodology}")

            self.logger.info(
                "Terminal value calculated",
                terminal_value=terminal_value_params.terminal_value,
                pv_terminal_value=terminal_value_params.pv_terminal_value,
                terminal_growth_rate=f"{terminal_value_params.terminal_growth_rate:.2%}",
            )

            return terminal_value_params

        except (CalculationError, DataQualityError):
            raise  # Re-raise specific errors
        except (ValueError, TypeError, ZeroDivisionError, AttributeError) as e:
            self.logger.error(
                f"Terminal value calculation failed: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise CalculationError(
                f"Failed to calculate terminal value: {e}",
                context={"calculation_type": "Terminal Value Calculation"},
            ) from e
        except DCFCalculationError as e:
            self.logger.error(
                f"Unexpected error in terminal value calculation: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise DCFCalculationError(
                f"Unexpected error in terminal value calculation: {e}",
                context={
                    "step": "terminal_value_calculation",
                    "calculation_type": "Terminal Value Calculation",
                    "error_type": type(e).__name__,
                },
            ) from e

    def _calculate_gordon_growth_terminal_value(
        self,
        final_fcf: Decimal,
        wacc: Decimal,
        market_context: MarketContext,
        industry_benchmarks: IndustryBenchmarks,
    ) -> TerminalValueParams:
        """Calculate terminal value using Gordon Growth Model"""
        try:
            # Estimate terminal growth rate
            terminal_growth_rate = self._estimate_terminal_growth_rate(
                market_context, industry_benchmarks
            )

            if final_fcf <= Decimal("0"):
                self.logger.warning(
                    "Final projected FCF is non-positive (%.2f) — Gordon Growth Model "
                    "requires positive FCF. Terminal value set to zero.",
                    from_decimal(final_fcf),
                )
                return TerminalValueParams(
                    final_fcf=from_decimal(final_fcf),
                    terminal_growth_rate=terminal_growth_rate,
                    wacc=from_decimal(wacc),
                    terminal_value=Decimal("0"),
                    pv_terminal_value=Decimal("0"),
                    methodology=DCFMethodology.GORDON_GROWTH,
                    exit_multiple=None,
                    terminal_growth_evidence={
                        "source": "market_context_and_industry_benchmark",
                        "confidence": "medium",
                        "uncapped_terminal_growth_rate": terminal_growth_rate,
                        "applied_terminal_growth_rate": terminal_growth_rate,
                        "wacc": wacc,
                        "warnings": ("non_positive_final_fcf_terminal_value_zero",),
                    },
                )

            # Gordon Growth Model: TV = FCF * (1 + g) / (WACC - g)
            # McKinsey Standard: Terminal growth should not exceed WACC or long-term GDP growth
            gdp_growth_decimal = to_decimal(market_context.long_term_gdp_growth)
            max_terminal_growth = min(
                wacc * Decimal("0.95"), gdp_growth_decimal * Decimal("1.2")
            )  # Cap at 120% of GDP growth
            terminal_growth_rate_decimal = to_decimal(terminal_growth_rate)
            uncapped_terminal_growth_rate = terminal_growth_rate_decimal
            terminal_growth_warnings: list[str] = []

            if terminal_growth_rate_decimal >= wacc:
                # Growth rate cannot exceed WACC (critical constraint)
                terminal_growth_rate_decimal = wacc * Decimal("0.95")  # 95% of WACC
                terminal_growth_warnings.append("terminal_growth_capped_below_wacc")
                self.logger.warning(
                    f"Terminal growth rate adjusted to {from_decimal(terminal_growth_rate_decimal):.2%} "
                    f"(cannot exceed WACC of {from_decimal(wacc):.2%})"
                )
            elif terminal_growth_rate_decimal > max_terminal_growth:
                # Terminal growth should be sustainable (typically ≤ GDP growth)
                terminal_growth_rate_decimal = max_terminal_growth
                terminal_growth_warnings.append("terminal_growth_capped_to_sustainable_long_run")
                self.logger.warning(
                    f"Terminal growth rate capped at {from_decimal(terminal_growth_rate_decimal):.2%} "
                    f"(sustainable long-term growth limit, GDP growth: {market_context.long_term_gdp_growth:.2%})"
                )

            terminal_value = (
                final_fcf
                * (Decimal("1") + terminal_growth_rate_decimal)
                / (wacc - terminal_growth_rate_decimal)
            )

            return TerminalValueParams(
                final_fcf=to_decimal(final_fcf),
                terminal_growth_rate=terminal_growth_rate_decimal,
                wacc=to_decimal(wacc),
                terminal_value=terminal_value,
                # Present-value discounting is performed in dcf_engine.py using the
                # actual explicit projection horizon for this valuation run.
                pv_terminal_value=Decimal("0"),
                methodology=DCFMethodology.GORDON_GROWTH,
                terminal_growth_evidence={
                    "source": "market_context_and_industry_benchmark",
                    "confidence": "medium",
                    "uncapped_terminal_growth_rate": uncapped_terminal_growth_rate,
                    "applied_terminal_growth_rate": terminal_growth_rate_decimal,
                    "wacc": to_decimal(wacc),
                    "long_term_gdp_growth": gdp_growth_decimal,
                    "cap": max_terminal_growth,
                    "guardrail": "terminal_growth_must_remain_below_wacc_and_sustainable_growth",
                    "warnings": tuple(terminal_growth_warnings),
                },
            )

        except (CalculationError, DataQualityError):
            raise  # Re-raise specific errors
        except (ValueError, TypeError, ZeroDivisionError, AttributeError) as e:
            self.logger.error(
                f"Gordon growth terminal value calculation failed: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise CalculationError(
                f"Failed to calculate Gordon growth terminal value: {e}",
                context={"calculation_type": "Gordon Growth Terminal Value"},
            ) from e
        except DCFCalculationError as e:
            self.logger.error(
                f"Unexpected error in Gordon growth terminal value calculation: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise DCFCalculationError(
                f"Unexpected error in Gordon growth terminal value calculation: {e}",
                context={
                    "step": "gordon_growth_terminal_value",
                    "calculation_type": "Gordon Growth Terminal Value",
                    "error_type": type(e).__name__,
                },
            ) from e

    def _calculate_exit_multiple_terminal_value(
        self,
        final_fcf: Decimal,
        market_context: MarketContext,
        industry_benchmarks: IndustryBenchmarks,
    ) -> TerminalValueParams:
        """Calculate terminal value using exit multiple method"""
        try:
            if final_fcf <= Decimal("0"):
                self.logger.warning(
                    "Final projected FCF is non-positive (%.2f) — Exit Multiple method "
                    "requires positive cash flows. Terminal value set to zero.",
                    from_decimal(final_fcf),
                )
                return TerminalValueParams(
                    final_fcf=from_decimal(final_fcf),
                    terminal_growth_rate=Decimal("0.0"),
                    wacc=Decimal("0.10"),
                    terminal_value=Decimal("0"),
                    pv_terminal_value=Decimal("0"),
                    methodology=DCFMethodology.EXIT_MULTIPLE,
                    exit_multiple=None,
                    terminal_growth_evidence={
                        "source": "not_applicable_exit_multiple",
                        "confidence": "high",
                        "warnings": ("non_positive_final_fcf_terminal_value_zero",),
                    },
                )

            exit_multiple_decimal = to_decimal(self._estimate_exit_multiple(industry_benchmarks))

            exit_year_ebitda = final_fcf * Decimal("1.2")
            terminal_value = exit_multiple_decimal * exit_year_ebitda

            wacc = to_decimal(
                getattr(market_context, "risk_free_rate", None)
                or market_context.government_bond_yield
            ) + Decimal(
                "0.05"
            )  # Simplified WACC

            return TerminalValueParams(
                final_fcf=from_decimal(final_fcf),
                terminal_growth_rate=Decimal("0.0"),  # Not used in exit multiple method
                wacc=from_decimal(wacc),
                terminal_value=from_decimal(terminal_value),
                # Present-value discounting is performed in dcf_engine.py using the
                # active projection horizon for the current DCF run.
                pv_terminal_value=Decimal("0"),
                methodology=DCFMethodology.EXIT_MULTIPLE,
                exit_multiple=from_decimal(exit_multiple_decimal),
                exit_year_ebitda=from_decimal(exit_year_ebitda),
                terminal_growth_evidence={
                    "source": "not_applicable_exit_multiple",
                    "confidence": "high",
                    "warnings": (),
                },
            )

        except (CalculationError, DataQualityError):
            raise  # Re-raise specific errors
        except (ValueError, TypeError, ZeroDivisionError, AttributeError) as e:
            self.logger.error(
                f"Exit multiple terminal value calculation failed: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise CalculationError(
                f"Failed to calculate exit multiple terminal value: {e}",
                context={"calculation_type": "Exit Multiple Terminal Value"},
            ) from e
        except DCFCalculationError as e:
            self.logger.error(
                f"Unexpected error in exit multiple terminal value calculation: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise DCFCalculationError(
                f"Unexpected error in exit multiple terminal value calculation: {e}",
                context={
                    "step": "exit_multiple_terminal_value",
                    "calculation_type": "Exit Multiple Terminal Value",
                    "error_type": type(e).__name__,
                },
            ) from e

    def _estimate_terminal_growth_rate(
        self, market_context: MarketContext, industry_benchmarks: IndustryBenchmarks
    ) -> Decimal:
        """Estimate terminal growth rate"""
        try:
            # Use long-term GDP growth as base
            gdp_growth = to_decimal(market_context.long_term_gdp_growth)

            # Adjust for industry characteristics
            industry_growth = to_decimal(industry_benchmarks.expected_growth_rate)

            # Terminal growth should be sustainable long-term
            # Typically between 1-3% (inflation + real growth)
            terminal_growth = min(gdp_growth, industry_growth)

            # Ensure within reasonable bounds
            min_growth = to_decimal(self.config.terminal_growth_range[0])
            max_growth = to_decimal(self.config.terminal_growth_range[1])
            terminal_growth = max(min_growth, min(terminal_growth, max_growth))

            return terminal_growth

        except (ValueError, TypeError, AttributeError) as e:
            self.logger.error(
                f"Terminal growth rate estimation failed: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            # Return default rather than raising, as this is a fallback calculation
            return Decimal("0.025")
        except MultiplesCalculationError as e:
            self.logger.error(
                f"Unexpected error in terminal growth rate estimation: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            return Decimal("0.025")  # Default 2.5%

    def _estimate_exit_multiple(self, industry_benchmarks: IndustryBenchmarks) -> Decimal:
        """Estimate exit multiple for the industry"""
        try:
            # Use industry average EV/EBITDA multiple
            # In practice, this would be more sophisticated
            base_multiple = to_decimal(industry_benchmarks.avg_ev_ebitda_multiple)

            # Adjust for market conditions (simplified)
            market_adjustment = Decimal("1.0")  # Would be based on market conditions

            exit_multiple = base_multiple * market_adjustment

            # Ensure reasonable bounds (typically 5-20x)
            exit_multiple = max(Decimal("5.0"), min(exit_multiple, Decimal("20.0")))

            return exit_multiple

        except (ValueError, TypeError, AttributeError) as e:
            self.logger.error(
                f"Exit multiple estimation failed: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            # Return default rather than raising, as this is a fallback calculation
            return Decimal("10.0")
        except DCFCalculationError as e:
            self.logger.error(
                f"Unexpected error in exit multiple estimation: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            return Decimal("10.0")  # Default 10x multiple

    def perform_sensitivity_analysis(
        self,
        base_terminal_value: Decimal,
        base_wacc: Decimal,
        base_growth_rate: Decimal,
        sensitivity_ranges: Optional[Dict[SensitivityType, SensitivityRange]] = None,
    ) -> Dict[SensitivityType, SensitivityResult]:
        """
        Perform sensitivity analysis on terminal value.

        Args:
            base_terminal_value: Base terminal value
            base_wacc: Base WACC
            base_growth_rate: Base terminal growth rate
            sensitivity_ranges: Custom sensitivity ranges

        Returns:
            Dictionary of sensitivity results
        """
        try:
            self.logger.info("Performing terminal value sensitivity analysis")

            if sensitivity_ranges is None:
                sensitivity_ranges = SENSITIVITY_RANGES

            results = {}

            # WACC sensitivity
            if SensitivityType.WACC in sensitivity_ranges:
                wacc_range = sensitivity_ranges[SensitivityType.WACC]
                wacc_scenarios = self._generate_sensitivity_scenarios(wacc_range)
                wacc_results = {}

                for wacc in wacc_scenarios:
                    # Recalculate terminal value with new WACC
                    terminal_value = self._recalculate_terminal_value_with_wacc(
                        base_terminal_value, base_wacc, wacc, base_growth_rate
                    )
                    wacc_results[wacc] = terminal_value

                wacc_results_float = {k: from_decimal(v) for k, v in wacc_results.items()}
                results[SensitivityType.WACC] = SensitivityResult(
                    parameter=SensitivityType.WACC,
                    base_value=from_decimal(base_wacc),
                    base_result=from_decimal(base_terminal_value),
                    scenarios=wacc_results_float,
                    impact_range=(
                        min(wacc_results_float.values()),
                        max(wacc_results_float.values()),
                    ),
                    volatility=self._calculate_volatility(list(wacc_results.values())),
                    key_drivers=[
                        "WACC sensitivity is high",
                        "Terminal value decreases with higher WACC",
                    ],
                )

            # Growth rate sensitivity
            if SensitivityType.TERMINAL_GROWTH in sensitivity_ranges:
                growth_range = sensitivity_ranges[SensitivityType.TERMINAL_GROWTH]
                growth_scenarios = self._generate_sensitivity_scenarios(growth_range)
                growth_results = {}

                for growth_rate in growth_scenarios:
                    # Recalculate terminal value with new growth rate
                    terminal_value = self._recalculate_terminal_value_with_growth(
                        base_terminal_value, base_wacc, base_growth_rate, growth_rate
                    )
                    growth_results[growth_rate] = terminal_value

                growth_results_float = {k: from_decimal(v) for k, v in growth_results.items()}
                results[SensitivityType.TERMINAL_GROWTH] = SensitivityResult(
                    parameter=SensitivityType.TERMINAL_GROWTH,
                    base_value=from_decimal(base_growth_rate),
                    base_result=from_decimal(base_terminal_value),
                    scenarios=growth_results_float,
                    impact_range=(
                        min(growth_results_float.values()),
                        max(growth_results_float.values()),
                    ),
                    volatility=self._calculate_volatility(list(growth_results.values())),
                    key_drivers=[
                        "Growth rate sensitivity is very high",
                        "Terminal value increases with higher growth",
                    ],
                )

            # Log completion with volatility metrics
            wacc_volatility = 0
            growth_volatility = 0
            if SensitivityType.WACC in results:
                wacc_volatility = from_decimal(results[SensitivityType.WACC].volatility)
            if SensitivityType.TERMINAL_GROWTH in results:
                growth_volatility = from_decimal(
                    results[SensitivityType.TERMINAL_GROWTH].volatility
                )

            self.logger.info(
                "Sensitivity analysis completed",
                parameters_analyzed=len(results),
                wacc_volatility=wacc_volatility,
                growth_volatility=growth_volatility,
            )

            return results

        except (ValueError, TypeError, ZeroDivisionError, AttributeError) as e:
            self.logger.error(
                f"Sensitivity analysis failed: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            # Return empty dict rather than raising, as sensitivity analysis is non-critical
            return {}
        except ValuationRangeError as e:
            self.logger.error(
                f"Unexpected error in sensitivity analysis: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            return {}

    def _generate_sensitivity_scenarios(self, sensitivity_range: SensitivityRange) -> List[Decimal]:
        """Generate sensitivity analysis scenarios"""
        scenarios = []
        current_value = to_decimal(sensitivity_range.min_value)
        max_value = to_decimal(sensitivity_range.max_value)
        step_size = to_decimal(sensitivity_range.step_size)

        while current_value <= max_value:
            scenarios.append(current_value)
            current_value += step_size

        return scenarios

    def _recalculate_terminal_value_with_wacc(
        self,
        base_terminal_value: Decimal,
        base_wacc: Decimal,
        new_wacc: Decimal,
        growth_rate: Decimal,
    ) -> Decimal:
        """Recalculate terminal value with new WACC"""
        if growth_rate >= new_wacc:
            growth_rate = new_wacc * Decimal("0.95")

        new_denom = new_wacc - growth_rate
        base_denom = base_wacc - growth_rate
        if new_denom <= 0 or base_denom <= 0:
            return base_terminal_value

        wacc_adjustment = (Decimal("1") + growth_rate) / new_denom
        base_wacc_adjustment = (Decimal("1") + growth_rate) / base_denom
        return base_terminal_value * (wacc_adjustment / base_wacc_adjustment)

    def _recalculate_terminal_value_with_growth(
        self,
        base_terminal_value: Decimal,
        wacc: Decimal,
        base_growth_rate: Decimal,
        new_growth_rate: Decimal,
    ) -> Decimal:
        """Recalculate terminal value with new growth rate"""
        if new_growth_rate >= wacc:
            new_growth_rate = wacc * Decimal("0.95")

        new_denom = wacc - new_growth_rate
        base_denom = wacc - base_growth_rate
        if new_denom <= 0 or base_denom <= 0:
            return base_terminal_value

        growth_adjustment = (Decimal("1") + new_growth_rate) / new_denom
        base_growth_adjustment = (Decimal("1") + base_growth_rate) / base_denom
        return base_terminal_value * (growth_adjustment / base_growth_adjustment)

    def _calculate_volatility(self, values: List[Decimal]) -> Decimal:
        """Calculate volatility of sensitivity results"""
        if len(values) < 2:
            return Decimal("0")

        values_float = [from_decimal(v) for v in values]
        mean_value = np.mean(values_float)
        variance = np.mean([(x - mean_value) ** 2 for x in values_float])
        result = np.sqrt(variance) / mean_value if mean_value != 0 else Decimal("0.0")
        return to_decimal(result)

    def discount_terminal_value(
        self, terminal_value: Decimal, wacc: Decimal, projection_years: int
    ) -> Decimal:
        """
        Discount terminal value to present value using the configured cash-flow
        timing convention. Mid-year DCF discounts terminal value at n - 0.5;
        year-end DCF discounts at n to match accountant spreadsheet templates.

        Args:
            terminal_value: Terminal value at end of projection period
            wacc: Weighted Average Cost of Capital
            projection_years: Number of projection years

        Returns:
            Present value of terminal value
        """
        try:
            wacc_float = to_decimal(wacc)
            projection_period = Decimal(str(projection_years))
            if self.config.mid_year_discounting:
                discount_period = max(Decimal("0.5"), projection_period - Decimal("0.5"))
            else:
                discount_period = max(Decimal("1"), projection_period)
            if wacc_float <= 0 or projection_years <= 0:
                raise ValueError("terminal discounting requires positive WACC and horizon")
            discount_factor = (Decimal("1") + wacc_float) ** discount_period
            pv_terminal_value = to_decimal(terminal_value) / discount_factor

            self.logger.debug(
                "Terminal value discounted",
                terminal_value=from_decimal(terminal_value),
                pv_terminal_value=from_decimal(pv_terminal_value),
                discount_factor=from_decimal(Decimal("1") / discount_factor),
            )

            return pv_terminal_value

        except (ValueError, TypeError, ZeroDivisionError) as e:
            self.logger.error(
                f"Terminal value discounting failed: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise DCFCalculationError(f"Terminal value discounting failed: {e}") from e
        except DCFCalculationError:
            raise

    def validate_terminal_value(self, terminal_value_params: TerminalValueParams) -> bool:
        """Validate terminal value calculation for reasonableness"""
        try:
            # Check terminal value is positive
            if terminal_value_params.terminal_value <= 0:
                self.logger.warning("Terminal value is not positive")
                return False

            # Check growth rate is reasonable
            if not (
                self.config.terminal_growth_range[0]
                <= terminal_value_params.terminal_growth_rate
                <= self.config.terminal_growth_range[1]
            ):
                self.logger.warning(
                    f"Terminal growth rate outside expected range: "
                    f"{terminal_value_params.terminal_growth_rate:.2%}"
                )
                return False

            # Check growth rate doesn't exceed WACC
            if terminal_value_params.terminal_growth_rate >= terminal_value_params.wacc:
                self.logger.warning(
                    f"Terminal growth rate ({terminal_value_params.terminal_growth_rate:.2%}) "
                    f"exceeds WACC ({terminal_value_params.wacc:.2%})"
                )
                return False

            return True

        except (ValueError, TypeError, AttributeError) as e:
            self.logger.error(
                f"Terminal value validation failed: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            # Return False rather than raising, as validation failure is expected
            return False
        except DCFCalculationError as e:
            self.logger.error(
                f"Unexpected error in terminal value validation: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            return False
