"""Monte Carlo and valuation-range helpers for DCF calculation."""

from decimal import Decimal
from typing import Optional, Protocol

from src.api.schemas import ValuationRequest
from src.utils.exceptions import CalculationError, DataQualityError, DCFCalculationError
from src.utils.exceptions import ValuationRangeError as RangeCalculationError


class CalculatorLogger(Protocol):
    def info(self, message: str, *, extra: dict[str, object] | None = None) -> None: ...

    def error(
        self,
        message: str,
        *,
        extra: dict[str, object] | None = None,
        exc_info: bool = False,
    ) -> None: ...


async def run_monte_carlo_simulation(
    request: ValuationRequest,
    *,
    logger: CalculatorLogger,
    base_fcf_override: Optional[Decimal] = None,
    base_wacc_override: Optional[Decimal] = None,
    base_growth_override: Optional[Decimal] = None,
) -> dict[str, object]:
    try:
        logger.info("🎲 Initializing Monte Carlo engine")

        from src.domain.monte_carlo_engine import MonteCarloValuationEngine

        mc_engine = MonteCarloValuationEngine()
        assumptions = getattr(request, "assumptions", None) or {}
        base_fcf = (
            base_fcf_override
            if base_fcf_override is not None
            else request.current_year_data.revenue * Decimal("0.1")
        )
        _disc_rate = getattr(request.current_year_data, "discount_rate", None)
        base_wacc = (
            base_wacc_override
            if base_wacc_override is not None
            else (_disc_rate if _disc_rate is not None else Decimal("0.10"))
        )
        base_growth = (
            base_growth_override
            if base_growth_override is not None
            else (
                assumptions.get("terminal_growth_rate", Decimal("0.03"))
                if isinstance(assumptions, dict)
                else Decimal("0.03")
            )
        )

        logger.info(
            "🎲 Monte Carlo parameters",
            extra={
                "base_fcf": base_fcf,
                "base_wacc": base_wacc,
                "base_growth": base_growth,
                "iterations": 10000,
            },
        )

        monte_carlo_results = dict(
            mc_engine.simulate_dcf(
                base_fcf=base_fcf,
                base_wacc=base_wacc,
                base_growth=base_growth,
                iterations=10000,
            )
        )

        logger.info(
            "✅ Monte Carlo simulation complete",
            extra={
                "p10": monte_carlo_results["p10"],
                "p50": monte_carlo_results["p50"],
                "p90": monte_carlo_results["p90"],
            },
        )

        return monte_carlo_results
    except (CalculationError, DataQualityError):
        raise
    except Exception as e:
        logger.error(
            "❌ Monte Carlo simulation failed",
            extra={"error": str(e), "error_type": type(e).__name__},
            exc_info=True,
        )
        raise DCFCalculationError(
            f"Failed to run Monte Carlo simulation: {e}",
            step="monte_carlo_simulation",
            calculation_type="Monte Carlo Simulation",
            context={"error_type": type(e).__name__},
        ) from e


async def calculate_probabilistic_range(
    equity_value: Decimal,
    monte_carlo_results: dict[str, object],
    *,
    logger: CalculatorLogger,
) -> dict[str, Decimal]:
    try:
        logger.info("📊 Calculating probabilistic range from Monte Carlo")

        from src.domain.range_calculator import ValuationRangeCalculator

        range_calc = ValuationRangeCalculator()
        valuation_range = range_calc.calculate_probabilistic_range(
            equity_value=equity_value,
            monte_carlo_results=monte_carlo_results,
            confidence_level="medium",
        )

        logger.info(
            "✅ Probabilistic range calculated",
            extra={
                "low": valuation_range["equity_value_low"],
                "mid": valuation_range["equity_value_mid"],
                "high": valuation_range["equity_value_high"],
            },
        )

        return valuation_range
    except (CalculationError, DataQualityError):
        raise
    except Exception as e:
        logger.error(
            "❌ Probabilistic range calculation failed",
            extra={"error": str(e), "error_type": type(e).__name__},
            exc_info=True,
        )
        raise RangeCalculationError(
            f"Failed to calculate probabilistic range: {e}",
            step="probabilistic_range",
            calculation_type="Probabilistic Range Calculation",
            context={"error_type": type(e).__name__},
        ) from e


async def calculate_deterministic_range(
    equity_value: Decimal,
    *,
    logger: CalculatorLogger,
) -> dict[str, Decimal]:
    try:
        logger.info("📊 Calculating deterministic range")

        from src.domain.range_calculator import ValuationRangeCalculator

        range_calc = ValuationRangeCalculator()
        valuation_range = range_calc.calculate_range(
            equity_value=equity_value,
            confidence_level="medium",
        )

        logger.info(
            "✅ Deterministic range calculated",
            extra={
                "low": valuation_range["equity_value_low"],
                "mid": valuation_range["equity_value_mid"],
                "high": valuation_range["equity_value_high"],
            },
        )

        return valuation_range
    except (CalculationError, DataQualityError):
        raise
    except Exception as e:
        logger.error(
            "❌ Deterministic range calculation failed",
            extra={"error": str(e), "error_type": type(e).__name__},
            exc_info=True,
        )
        raise RangeCalculationError(
            f"Failed to calculate deterministic range: {e}",
            step="deterministic_range",
            calculation_type="Deterministic Range Calculation",
            context={"error_type": type(e).__name__},
        ) from e
