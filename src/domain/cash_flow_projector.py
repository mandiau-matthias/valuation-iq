"""
Cash Flow Projector

This module handles all cash flow calculations and projections for DCF valuation,
including historical FCF calculation, future projections, and growth modeling.
"""

from decimal import Decimal
from typing import Any, List, Optional

import numpy as np

from src.errors.error_types import ValidationError
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.exceptions import CalculationError, DataQualityError, DCFCalculationError
from src.utils.logging import get_logger

from .dcf_types import (
    DEFAULT_DCF_CONFIG,
    CashFlowProjection,
    DCFConfiguration,
    GrowthModel,
    GrowthProjection,
    HistoricalFCF,
)
from .cash_flow_components import (
    FCFBreakdown,
    fcf_breakdown_from_components,
    resolve_capex,
    resolve_d_and_a_and_ebit,
    resolve_nwc_change,
    resolve_taxes,
    resolve_unlevered_tax,
    zero_fcf_breakdown,
)
from .models import FinancialData, IndustryBenchmarks, MarketContext, YearData

logger = get_logger(__name__)


class CashFlowProjector:
    """
    Cash flow projection service for DCF valuation

    Handles:
    - Historical FCF calculation (EBITDA - Taxes - CapEx - NWC Change)
    - Future FCF projections with growth decay
    - CAGR calculation and trend analysis
    - Economic cycle adjustments
    - Revenue and expense modeling
    """

    def __init__(
        self,
        config: Optional[DCFConfiguration] = None,
        transparency_collector: Optional[Any] = None,
    ):
        """
        Initialize the cash flow projector

        Args:
            config: DCF configuration settings
            transparency_collector: Optional transparency collector for tracking
        """
        self.logger = logger
        self.config = config or DEFAULT_DCF_CONFIG
        self.transparency_collector = transparency_collector

        self.logger.info("CashFlowProjector initialized with transparency tracking")

    def calculate_historical_fcf(
        self, financial_data: FinancialData, industry_benchmarks: IndustryBenchmarks
    ) -> HistoricalFCF:
        """
        Calculate historical Free Cash Flow.

        FCF = EBITDA - Taxes - CapEx - Change in NWC

        Args:
            financial_data: Company financial statements
            industry_benchmarks: Industry-specific benchmarks

        Returns:
            HistoricalFCF with complete historical analysis
        """
        try:
            self.logger.info("Calculating historical FCF")

            all_years = sorted(
                financial_data.historical_years + [financial_data.current_year],
                key=lambda item: item.year,
            )
            fcf_values = []
            revenue = []
            ebitda = []
            taxes = []
            capex = []
            nwc_change = []
            years = []
            actual_tax_years = 0
            actual_capex_years = 0
            actual_nwc_years = 0

            prev_rev: Optional[Decimal] = None
            for year_data in all_years:
                breakdown = self._calculate_fcf_for_year(
                    year_data,
                    industry_benchmarks,
                    previous_revenue=prev_rev,
                )
                fcf_values.append(breakdown.fcf)
                revenue.append(year_data.revenue)
                ebitda.append(year_data.ebitda)
                prev_rev = (
                    to_decimal(year_data.revenue) if year_data.revenue is not None else prev_rev
                )
                taxes.append(year_data.tax_expense or 0)
                capex.append(year_data.capex or 0)
                nwc_change.append(year_data.nwc_change or 0)
                years.append(year_data.year)
                if year_data.tax_expense is not None:
                    actual_tax_years += 1
                if year_data.capex is not None:
                    actual_capex_years += 1
                if year_data.nwc_change is not None:
                    actual_nwc_years += 1

            # Calculate CAGR and volatility
            cagr = self._calculate_cagr(fcf_values, years)
            volatility = self._calculate_volatility(fcf_values)
            trend = self._analyze_trend(fcf_values)

            historical_fcf = HistoricalFCF(
                years=years,
                fcf_values=fcf_values,
                revenue=revenue,
                ebitda=ebitda,
                taxes=taxes,
                capex=capex,
                nwc_change=nwc_change,
                actual_tax_years=actual_tax_years,
                actual_capex_years=actual_capex_years,
                actual_nwc_years=actual_nwc_years,
                cagr=cagr,
                volatility=volatility,
                trend=trend,
            )

            self.logger.info(
                "Historical FCF calculated",
                cagr=f"{cagr:.2%}",
                volatility=f"{volatility:.2%}",
                trend=trend,
            )

            return historical_fcf

        except (CalculationError, DataQualityError, ValidationError):
            raise  # Re-raise specific errors
        except (ValueError, TypeError, ZeroDivisionError, AttributeError) as e:
            self.logger.error(
                f"Historical FCF calculation failed: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise CalculationError(
                f"Failed to calculate historical FCF: {e}",
                calculation_type="Historical FCF Calculation",
            ) from e
        except DCFCalculationError as e:
            self.logger.error(
                f"Unexpected error in historical FCF calculation: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise DCFCalculationError(
                f"Unexpected error in historical FCF calculation: {e}",
                step="historical_fcf_calculation",
                calculation_type="Historical FCF Calculation",
                context={"error_type": type(e).__name__},
            ) from e

    def project_future_fcf(
        self,
        historical_fcf: HistoricalFCF,
        market_context: MarketContext,
        industry_benchmarks: IndustryBenchmarks,
        projection_years: Optional[int] = None,
    ) -> List[CashFlowProjection]:
        """
        Project future free cash flows with growth modeling.

        Args:
            historical_fcf: Historical FCF data
            market_context: Market and economic context
            industry_benchmarks: Industry benchmarks
            projection_years: Number of years to project

        Returns:
            List of future cash flow projections
        """
        try:
            projection_years = projection_years or self.config.projection_years

            self.logger.info(
                "Projecting future FCF",
                projection_years=projection_years,
                historical_cagr=f"{historical_fcf.cagr:.2%}",
            )

            # Calculate growth parameters
            growth_projection = self._calculate_growth_parameters(
                historical_fcf, market_context, industry_benchmarks
            )

            # Track FCF projection assumptions in transparency
            if self.transparency_collector:
                base_revenue = historical_fcf.revenue[-1] if historical_fcf.revenue else 0
                base_ebitda = historical_fcf.ebitda[-1] if historical_fcf.ebitda else 0
                base_margin = base_ebitda / base_revenue if base_revenue > 0 else 0

                assumptions = {
                    "base_revenue": base_revenue,
                    "base_ebitda": base_ebitda,
                    "base_margin": base_margin,
                    "initial_growth_rate": growth_projection.historical_growth,  # Use historical_growth as initial
                    "terminal_growth_rate": growth_projection.terminal_growth,  # Use terminal_growth attribute
                    "projection_years": projection_years,
                    "historical_cagr": historical_fcf.cagr,
                }

                self.transparency_collector.add_calculation_step(
                    description="FCF Projection Assumptions",
                    formula="FCF = EBIT(1-T) + Depreciation - CapEx - ΔWC",
                    inputs=assumptions,
                    outputs={"projection_years": projection_years},
                    explanation=f"Projecting {projection_years} years of FCF using:\n"
                    f"• Initial growth rate: {growth_projection.historical_growth:.1%} (based on historical {historical_fcf.cagr:.1%} CAGR)\n"
                    f"• Terminal growth rate: {growth_projection.terminal_growth:.1%} (long-term GDP growth)\n"
                    f"• Base EBITDA margin: {base_margin:.1%} (assumed stable)\n"
                    f"• Growth decay model: Gradual convergence to terminal rate\n"
                    f"• Historical volatility: {historical_fcf.volatility:.1%}",
                )

            # Project cash flows
            projections = []
            current_fcf = to_decimal(
                historical_fcf.fcf_values[-1] if historical_fcf.fcf_values else 0
            )
            cumulative_growth = Decimal("0")

            base_revenue = to_decimal(historical_fcf.revenue[-1] if historical_fcf.revenue else 0)
            base_ebitda = to_decimal(historical_fcf.ebitda[-1] if historical_fcf.ebitda else 0)
            _bench_margin = getattr(industry_benchmarks, "avg_ebitda_margin", None)
            ebitda_margin = (
                base_ebitda / base_revenue
                if base_revenue > 0
                else to_decimal(_bench_margin if _bench_margin is not None else Decimal("0.10"))
            )
            capex_ratio = to_decimal(industry_benchmarks.avg_capex_to_revenue)
            da_ratio = to_decimal(
                industry_benchmarks.avg_da_to_revenue
                if getattr(industry_benchmarks, "avg_da_to_revenue", None) is not None
                else Decimal("0")
            )
            _nwc = getattr(industry_benchmarks, "avg_nwc_to_revenue", None)
            nwc_ratio = to_decimal(_nwc if _nwc is not None else Decimal("0"))
            tax_rate = to_decimal(industry_benchmarks.avg_tax_rate)
            projected_revenue = base_revenue
            previous_nwc_level = base_revenue * nwc_ratio

            for year in range(1, projection_years + 1):
                # Calculate growth rate for this year
                year_growth = self._calculate_year_growth_rate(
                    year, projection_years, growth_projection
                )

                # Apply economic cycle adjustment
                cycle_adjustment = self._get_economic_cycle_adjustment(year, market_context)
                year_growth_decimal = to_decimal(year_growth)
                cycle_adjustment_decimal = to_decimal(cycle_adjustment)
                adjusted_growth = year_growth_decimal * cycle_adjustment_decimal
                cumulative_growth += adjusted_growth

                # Project line items from base year, then derive FCFF via
                # the standard NOPAT + D&A - CapEx - ΔNWC bridge so every
                # row in the report table reconciles with the displayed FCFF.
                projected_revenue = projected_revenue * (Decimal("1") + adjusted_growth)
                projected_ebitda = projected_revenue * ebitda_margin
                projected_da = projected_revenue * da_ratio
                projected_ebit = projected_ebitda - projected_da
                projected_taxes = max(Decimal("0"), projected_ebit) * tax_rate
                projected_capex = projected_revenue * capex_ratio
                nwc_level = projected_revenue * nwc_ratio
                delta_nwc = nwc_level - previous_nwc_level
                nopat = projected_ebit - projected_taxes
                current_fcf = nopat + projected_da - projected_capex - delta_nwc

                # Create projection
                confidence_score = self._calculate_confidence_score(
                    year, projection_years, growth_projection
                )
                projection = CashFlowProjection(
                    year=year,
                    revenue=from_decimal(projected_revenue),
                    ebitda=from_decimal(projected_ebitda),
                    ebit=from_decimal(projected_ebit),
                    taxes=from_decimal(projected_taxes),
                    capex=from_decimal(projected_capex),
                    nwc_change=from_decimal(delta_nwc),
                    free_cash_flow=from_decimal(current_fcf),
                    growth_rate=from_decimal(adjusted_growth),
                    cumulative_growth=from_decimal(cumulative_growth),
                    confidence_score=from_decimal(confidence_score),
                )

                previous_nwc_level = nwc_level

                projections.append(projection)

                # Track each year's calculation in transparency
                if (
                    self.transparency_collector and year <= 5
                ):  # Only track first 5 years for display
                    self.transparency_collector.add_calculation_step(
                        description=f"FCF Year {year} Projection",
                        formula=f"FCF Year {year} = FCF Year {year-1} × (1 + Growth Rate {adjusted_growth:.2%})",
                        inputs={
                            "year": year,
                            "previous_fcf": from_decimal(
                                current_fcf / (Decimal("1") + adjusted_growth)
                                if adjusted_growth != Decimal("-1")
                                else Decimal("0")
                            ),
                            "growth_rate": from_decimal(adjusted_growth),
                            "cycle_adjustment": from_decimal(cycle_adjustment_decimal),
                            "base_growth": from_decimal(year_growth_decimal),
                        },
                        outputs={
                            "fcf": from_decimal(current_fcf),
                            "cumulative_growth": from_decimal(cumulative_growth),
                        },
                        explanation=f"Year {year}: FCF €{from_decimal(current_fcf):,.0f} (growth: {from_decimal(adjusted_growth):.1%}). "
                        f"Growth rate decays from {growth_projection.historical_growth:.1%} to {growth_projection.terminal_growth:.1%} over {projection_years} years.",
                    )

            self.logger.info(
                "Future FCF projections completed",
                final_fcf=current_fcf,
                avg_growth=(
                    f"{cumulative_growth/projection_years:.2%}" if projection_years > 0 else "N/A"
                ),
            )

            return projections

        except (CalculationError, DataQualityError, ValidationError):
            raise  # Re-raise specific errors
        except (ValueError, TypeError, ZeroDivisionError, AttributeError) as e:
            self.logger.error(
                f"Future FCF projection failed: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise CalculationError(
                f"Failed to project future FCF: {e}", calculation_type="FCF Projection"
            ) from e
        except DCFCalculationError as e:
            self.logger.error(
                f"Unexpected error in future FCF projection: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise DCFCalculationError(
                f"Unexpected error in future FCF projection: {e}",
                step="future_fcf_projection",
                calculation_type="FCF Projection",
                context={"error_type": type(e).__name__},
            ) from e

    def project_explicit_forecast_fcf(
        self,
        historical_fcf: HistoricalFCF,
        forecast_years: List[YearData],
        industry_benchmarks: IndustryBenchmarks,
    ) -> List[CashFlowProjection]:
        """Convert user-provided forecast rows into explicit DCF cash-flow projections."""
        projections: List[CashFlowProjection] = []
        sorted_forecasts = sorted(forecast_years, key=lambda year_data: year_data.year)
        _hist_rev = getattr(historical_fcf, "revenue", None)
        previous_revenue = (
            to_decimal(_hist_rev[-1])
            if _hist_rev and isinstance(_hist_rev, (list, tuple)) and len(_hist_rev) > 0
            else Decimal("0")
        )
        cumulative_growth = Decimal("0")

        for index, year_data in enumerate(sorted_forecasts, start=1):
            explicit_fcff = year_data.is_forecast and year_data.free_cash_flow is not None
            if explicit_fcff:
                free_cash_flow = to_decimal(year_data.free_cash_flow)
                display_ebitda = Decimal("0")
                display_ebit = Decimal("0")
                display_taxes = Decimal("0")
                display_capex = Decimal("0")
                display_nwc = Decimal("0")
            else:
                breakdown = self._calculate_fcf_for_year(
                    year_data,
                    industry_benchmarks,
                    previous_revenue=previous_revenue,
                )
                free_cash_flow = breakdown.fcf
                display_ebitda = to_decimal(year_data.ebitda)
                display_ebit = breakdown.ebit
                display_taxes = breakdown.taxes
                display_capex = breakdown.capex
                display_nwc = breakdown.nwc_change

            current_revenue = to_decimal(year_data.revenue)
            if previous_revenue > 0:
                growth_rate = (current_revenue - previous_revenue) / previous_revenue
            else:
                growth_rate = Decimal("0")
            cumulative_growth += growth_rate

            projection = CashFlowProjection(
                year=index,
                revenue=to_decimal(year_data.revenue),
                ebitda=display_ebitda,
                ebit=display_ebit,
                taxes=display_taxes,
                capex=display_capex,
                nwc_change=display_nwc,
                free_cash_flow=free_cash_flow,
                growth_rate=growth_rate,
                cumulative_growth=cumulative_growth,
                confidence_score=max(
                    Decimal("0.4"), Decimal("1.0") - (Decimal(index - 1) * Decimal("0.1"))
                ),
            )
            projections.append(projection)
            previous_revenue = current_revenue

        return projections

    def _calculate_fcf_for_year(
        self,
        year_data: YearData,
        industry_benchmarks: IndustryBenchmarks,
        previous_revenue: Optional[Decimal] = None,
    ) -> FCFBreakdown:
        """
        Calculate FCF for a single year using McKinsey standard formula.

        CORRECT FORMULA (McKinsey Standard):
        FCF = EBIT(1-T) + Depreciation + Amortization - CapEx - ΔWorking Capital

        Or equivalently:
        FCF = EBITDA(1-T) + (Depreciation + Amortization) × T - CapEx - ΔNWC

        This accounts for the tax shield on depreciation/amortization.

        Returns an ``FCFBreakdown`` so callers can populate display fields
        (EBIT, taxes, CapEx, NWC) that reconcile with the computed FCFF.
        """
        try:
            d_and_a, ebit = resolve_d_and_a_and_ebit(year_data, industry_benchmarks)
            taxes = resolve_taxes(
                ebit=ebit,
                tax_rate=to_decimal(industry_benchmarks.avg_tax_rate),
                unlevered_tax=resolve_unlevered_tax(year_data, ebit),
            )
            capex = resolve_capex(year_data, industry_benchmarks)
            nwc_change = resolve_nwc_change(
                year_data,
                industry_benchmarks,
                previous_revenue,
            )

            return fcf_breakdown_from_components(
                ebit=ebit,
                d_and_a=d_and_a,
                taxes=taxes,
                capex=capex,
                nwc_change=nwc_change,
            )

        except (ValueError, TypeError, ZeroDivisionError, AttributeError) as e:
            self.logger.error(
                f"FCF calculation for year {year_data.year} failed: {e}",
                extra={"error_type": type(e).__name__, "error": str(e), "year": year_data.year},
            )
            return zero_fcf_breakdown()
        except DCFCalculationError as e:
            self.logger.error(
                f"Unexpected error in FCF calculation for year {year_data.year}: {e}",
                extra={"error_type": type(e).__name__, "error": str(e), "year": year_data.year},
            )
            return zero_fcf_breakdown()

    def _calculate_cagr(self, values: List[Decimal], years: Optional[List[int]] = None) -> Decimal:
        """Calculate Compound Annual Growth Rate"""
        if len(values) < 2:
            return Decimal("0")

        beginning = to_decimal(values[0])
        ending = to_decimal(values[-1])
        n_years = years[-1] - years[0] if years is not None else len(values) - 1
        if n_years <= 0:
            return Decimal("0")

        if beginning <= 0 or ending <= 0:
            # Handle negative values with simple average growth
            growths = []
            for i in range(1, len(values)):
                prev_val = to_decimal(values[i - 1])
                if prev_val > 0:
                    curr_val = to_decimal(values[i])
                    growth = (curr_val - prev_val) / abs(prev_val)
                    growths.append(growth)  # Keep as Decimal
            # Convert to float only for numpy mean, then back to Decimal
            if growths:
                growths_float = [float(g) for g in growths]
                return to_decimal(np.mean(growths_float))
            return Decimal("0")

        # Use float for exponentiation (Decimal doesn't support ** with float exponent)
        # But convert operands to Decimal for precision
        beginning_float = to_decimal(beginning)
        ending_float = to_decimal(ending)
        if beginning_float <= 0:
            return Decimal("0")
        cagr_float = (ending_float / beginning_float) ** (Decimal("1.0") / n_years) - Decimal("1.0")
        return to_decimal(cagr_float)

    def _calculate_volatility(self, values: List[Decimal]) -> Decimal:
        """Calculate volatility of FCF values"""
        if len(values) < 2:
            return Decimal("0")

        # Calculate standard deviation of growth rates
        growth_rates = []
        for i in range(1, len(values)):
            prev_val = to_decimal(values[i - 1])
            if prev_val != 0:
                curr_val = to_decimal(values[i])
                growth = (curr_val - prev_val) / abs(prev_val)
                growth_rates.append(growth)  # Keep as Decimal

        if not growth_rates:
            return Decimal("0")

        # Convert to float only for numpy std, then back to Decimal
        growth_rates_float = [float(g) for g in growth_rates]
        return to_decimal(np.std(growth_rates_float))

    def _analyze_trend(self, values: List[Decimal]) -> str:
        """Analyze trend in FCF values"""
        if len(values) < 3:
            return "insufficient_data"

        # Calculate trend using linear regression
        x = np.arange(len(values))
        # Convert Decimal values to float for numpy operations, then back to Decimal
        y = np.array([float(to_decimal(v)) for v in values])

        # Simple linear trend
        slope = np.polyfit(x, y, 1)[0]
        slope_decimal = to_decimal(slope)

        mean_val = float(np.mean(y))
        mean_val_decimal = to_decimal(mean_val)
        if slope_decimal > Decimal("0.1") * mean_val_decimal:
            return "increasing"
        elif slope_decimal < -Decimal("0.1") * mean_val_decimal:
            return "decreasing"
        else:
            return "stable"

    def _calculate_growth_parameters(
        self,
        historical_fcf: HistoricalFCF,
        market_context: MarketContext,
        industry_benchmarks: IndustryBenchmarks,
    ) -> GrowthProjection:
        """Calculate growth projection parameters.

        The historical FCF CAGR is a *candidate* input, not a forward assumption.
        Two guards keep the projection defensible for SMEs (Damodaran, Investment
        Valuation — high-growth fade; never extrapolate unsustainable or
        statistically unreliable growth):

        1. Sustainability cap — historical growth is capped toward a sustainable
           ceiling (2x industry growth, floor 20%). A 100%+ CAGR computed off a
           small or recovering base is not a five-year forward growth rate.
        2. Volatility guard — when the historical FCF series is too volatile to
           yield a reliable CAGR (stdev of YoY growth > 100%), the historical leg
           is dropped and the blend falls back to industry/economic growth only.

        Without these guards a young, fast-growing micro company (e.g. FCF rising
        off a near-zero base) produces an absurd terminal value that dominates the
        hybrid headline even at a low DCF weight.
        """

        # Industry and economic growth (always-trusted legs)
        industry_growth = industry_benchmarks.expected_growth_rate
        economic_growth = market_context.long_term_gdp_growth
        industry_growth_decimal = to_decimal(industry_growth)
        economic_growth_decimal = to_decimal(economic_growth)

        min_growth = to_decimal(self.config.growth_range[0])
        max_growth = to_decimal(self.config.growth_range[1])

        # Guard 1 — cap unsustainable historical growth toward a defensible ceiling.
        raw_historical_growth = to_decimal(historical_fcf.cagr)
        growth_ceiling = max(industry_growth_decimal * Decimal("2"), Decimal("0.20"))
        capped_historical_growth = max(min_growth, min(raw_historical_growth, growth_ceiling))

        # Guard 2 — drop the historical leg when the FCF series is too volatile
        # for its CAGR to mean anything (common for young/recovering SMEs).
        fcf_volatility = to_decimal(getattr(historical_fcf, "volatility", Decimal("0")) or 0)
        historical_volatility_ceiling = Decimal("1.0")  # 100% stdev of YoY FCF growth
        historical_weight = (
            Decimal("0") if fcf_volatility > historical_volatility_ceiling else Decimal("0.4")
        )

        # Reallocate any dropped historical weight across industry/economic,
        # preserving their original 2:1 split (0.4 industry : 0.2 economic).
        remaining_weight = Decimal("1") - historical_weight
        industry_weight = remaining_weight * Decimal("2") / Decimal("3")
        economic_weight = remaining_weight * Decimal("1") / Decimal("3")
        blended_growth = (
            historical_weight * capped_historical_growth
            + industry_weight * industry_growth_decimal
            + economic_weight * economic_growth_decimal
        )

        # Final safety clamp to configured bounds.
        blended_growth = max(min_growth, min(blended_growth, max_growth))

        # Terminal growth (typically GDP growth)
        terminal_growth = market_context.long_term_gdp_growth

        # Report the capped historical growth so downstream transparency does not
        # echo an unsustainable headline CAGR as if it were a forward assumption.
        return GrowthProjection(
            historical_growth=capped_historical_growth,
            industry_growth=industry_growth,
            economic_growth=economic_growth,
            blended_growth=blended_growth,
            decay_factor=Decimal("0.5"),  # 50% decay toward terminal rate
            terminal_growth=terminal_growth,
            projection_years=self.config.projection_years,
            model=self.config.growth_model,
        )

    def _calculate_year_growth_rate(
        self, year: int, projection_years: int, growth_projection: GrowthProjection
    ) -> Decimal:
        """Calculate growth rate for a specific year"""

        blended_growth_decimal = to_decimal(growth_projection.blended_growth)
        terminal_growth_decimal = to_decimal(growth_projection.terminal_growth)
        decay_factor_decimal = to_decimal(growth_projection.decay_factor)

        safe_projection_years = max(1, projection_years)

        if self.config.growth_model == GrowthModel.DECAY:
            decay_factor = min(
                Decimal(str(year)) / Decimal(str(safe_projection_years)), Decimal("1")
            )
            year_growth = (
                blended_growth_decimal * (Decimal("1") - decay_factor * decay_factor_decimal)
                + terminal_growth_decimal * decay_factor * decay_factor_decimal
            )
        elif self.config.growth_model == GrowthModel.LINEAR:
            year_ratio = Decimal(str(year)) / Decimal(str(safe_projection_years))
            year_growth = blended_growth_decimal - (
                (blended_growth_decimal - terminal_growth_decimal) * year_ratio
            )
        else:
            # Default to blended growth
            year_growth = blended_growth_decimal

        return year_growth

    def _get_economic_cycle_adjustment(self, year: int, market_context: MarketContext) -> Decimal:
        """Get economic cycle adjustment factor"""
        # Simplified economic cycle adjustment
        # In production, this would use sophisticated macroeconomic models

        # Check if market_conditions attribute exists (optional)
        market_conditions = getattr(market_context, "market_conditions", None)
        if market_conditions == "bull":
            return Decimal("1.1")  # 10% boost in bull markets
        elif market_conditions == "bear":
            return Decimal("0.9")  # 10% reduction in bear markets
        else:
            return Decimal("1.0")  # Neutral adjustment

    def _calculate_confidence_score(
        self, year: int, projection_years: int, growth_projection: GrowthProjection
    ) -> Decimal:
        """Calculate confidence score for a projection year"""
        safe_projection_years = max(1, projection_years)
        year_ratio = Decimal(str(year)) / Decimal(str(safe_projection_years))
        distance_factor = Decimal("1.0") - year_ratio * Decimal("0.3")

        # Confidence based on growth stability
        blended_growth_decimal = to_decimal(growth_projection.blended_growth)
        terminal_growth_decimal = to_decimal(growth_projection.terminal_growth)
        growth_stability = Decimal("1.0") - abs(blended_growth_decimal - terminal_growth_decimal)

        # Overall confidence
        confidence = distance_factor * growth_stability

        return max(Decimal("0.1"), min(Decimal("1.0"), confidence))
