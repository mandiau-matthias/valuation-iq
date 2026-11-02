"""Equity, beta, and WACC validation helpers for discount-rate calculations."""

from __future__ import annotations

from decimal import Decimal
from typing import Callable, Optional

from src.errors.error_types import MarketDataError
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.exceptions import CalculationError, DCFCalculationError

from .dcf_types import (
    CAPMComponents,
    CostOfEquityModel,
    DCFConfiguration,
    FamaFrenchComponents,
    WACCComponents,
)
from .market_defaults import get_default_equity_risk_premium
from .models import FinancialData, IndustryBenchmarks, MarketContext

EstimateBeta = Callable[[IndustryBenchmarks, Optional[FinancialData]], Decimal]
EstimateFactorBeta = Callable[[IndustryBenchmarks], Decimal]
AdjustBetaForLeverage = Callable[[Decimal, Decimal, Decimal], Decimal]
CalculateFamaFrench = Callable[[MarketContext, IndustryBenchmarks], FamaFrenchComponents]

_RATE_PRECISION = 6


def _rate(value: Decimal) -> Decimal:
    """Commit a rate/beta without applying the currency rounding default."""

    return from_decimal(value, precision=_RATE_PRECISION)


def calculate_cost_of_equity(
    *,
    config: DCFConfiguration,
    market_context: MarketContext,
    industry_benchmarks: IndustryBenchmarks,
    financial_data: Optional[FinancialData],
    estimate_beta: EstimateBeta,
    calculate_fama_french_cost_of_equity: CalculateFamaFrench,
    logger: object,
) -> CAPMComponents:
    """Calculate cost of equity using the configured CAPM or Fama-French model."""
    try:
        if (
            hasattr(config, "cost_of_equity_model")
            and config.cost_of_equity_model == CostOfEquityModel.FAMA_FRENCH_3
        ):
            ff_components = calculate_fama_french_cost_of_equity(
                market_context, industry_benchmarks
            )
            return CAPMComponents(
                risk_free_rate=ff_components.risk_free_rate,
                beta=ff_components.market_beta,
                market_risk_premium=ff_components.market_risk_premium,
                cost_of_equity=ff_components.cost_of_equity,
                beta_source=f"fama_french_3_{ff_components.beta_source}",
                confidence=ff_components.confidence,
            )

        from .market_defaults import get_risk_free_rate as _get_rf

        country = getattr(market_context, "country_code", None)
        rf_live, _rf_source = _get_rf(country)
        risk_free_attr = getattr(market_context, "risk_free_rate", None)
        if risk_free_attr is None:
            risk_free_attr = market_context.government_bond_yield
        if risk_free_attr is None:
            risk_free_attr = rf_live
        risk_free_rate = to_decimal(risk_free_attr)

        market_risk_attr = getattr(market_context, "market_risk_premium", None)
        if market_risk_attr is None:
            market_risk_attr = market_context.equity_risk_premium
        market_risk_premium = to_decimal(market_risk_attr)

        beta_decimal = to_decimal(estimate_beta(industry_benchmarks, financial_data))
        cost_of_equity = risk_free_rate + beta_decimal * market_risk_premium
        cost_of_equity = max(Decimal("0.05"), min(cost_of_equity, Decimal("0.30")))

        return CAPMComponents(
            risk_free_rate=_rate(risk_free_rate),
            beta=_rate(beta_decimal),
            market_risk_premium=_rate(market_risk_premium),
            cost_of_equity=_rate(cost_of_equity),
            beta_source="industry_benchmark",
            confidence=Decimal("0.8"),
        )

    except (CalculationError, MarketDataError):
        raise
    except (ValueError, TypeError, AttributeError) as e:
        logger.error(
            f"Cost of equity calculation failed: {e}",
            extra={"error_type": type(e).__name__, "error": str(e)},
        )
        raise CalculationError(
            f"Failed to calculate cost of equity: {e}",
            calculation_type="CAPM Cost of Equity",
        ) from e
    except DCFCalculationError as e:
        logger.error(
            f"Unexpected error in cost of equity calculation: {e}",
            extra={"error_type": type(e).__name__, "error": str(e)},
        )
        raise DCFCalculationError(
            f"Unexpected error in cost of equity calculation: {e}",
            step="cost_of_equity_calculation",
            calculation_type="CAPM Cost of Equity",
            context={"error_type": type(e).__name__},
        ) from e


def calculate_fama_french_cost_of_equity(
    *,
    config: DCFConfiguration,
    market_context: MarketContext,
    industry_benchmarks: IndustryBenchmarks,
    estimate_beta: EstimateBeta,
    estimate_smb_beta: EstimateFactorBeta,
    estimate_hml_beta: EstimateFactorBeta,
    logger: object,
) -> FamaFrenchComponents:
    """Calculate cost of equity with the Fama-French 3-factor model."""
    try:
        risk_free_rate = to_decimal(
            getattr(market_context, "risk_free_rate", None) or market_context.government_bond_yield
        )
        market_risk_premium = to_decimal(
            getattr(market_context, "market_risk_premium", None)
            or market_context.equity_risk_premium
        )
        market_beta = to_decimal(estimate_beta(industry_benchmarks, None))
        smb_premium = to_decimal(getattr(config, "smb_premium", Decimal("0.03")))
        hml_premium = to_decimal(getattr(config, "hml_premium", Decimal("0.04")))
        smb_beta = estimate_smb_beta(industry_benchmarks)
        hml_beta = estimate_hml_beta(industry_benchmarks)

        cost_of_equity = (
            risk_free_rate
            + market_beta * market_risk_premium
            + smb_beta * smb_premium
            + hml_beta * hml_premium
        )
        cost_of_equity = max(Decimal("0.08"), min(cost_of_equity, Decimal("0.35")))

        logger.info(
            "Fama-French 3-factor cost of equity calculated",
            risk_free_rate=f"{risk_free_rate:.2%}",
            market_beta=f"{market_beta:.2f}",
            smb_beta=f"{smb_beta:.2f}",
            hml_beta=f"{hml_beta:.2f}",
            cost_of_equity=f"{cost_of_equity:.2%}",
        )

        return FamaFrenchComponents(
            risk_free_rate=_rate(risk_free_rate),
            market_beta=_rate(market_beta),
            market_risk_premium=_rate(market_risk_premium),
            smb_premium=_rate(smb_premium),
            smb_beta=_rate(smb_beta),
            hml_premium=_rate(hml_premium),
            hml_beta=_rate(hml_beta),
            cost_of_equity=_rate(cost_of_equity),
            model_type="fama_french_3",
            beta_source="sme_adjusted",
            confidence=Decimal("0.85"),
        )

    except (ValueError, TypeError, AttributeError) as e:
        logger.error(
            f"Fama-French cost of equity calculation failed: {e}",
            extra={"error_type": type(e).__name__, "error": str(e)},
        )
        raise CalculationError(
            f"Failed to calculate Fama-French cost of equity: {e}",
            calculation_type="Fama-French 3-Factor",
        ) from e


def estimate_smb_beta(industry_benchmarks: IndustryBenchmarks) -> Decimal:
    """Estimate SMB beta for SME-sized companies."""
    _ = industry_benchmarks
    base_smb_beta = Decimal("1.2")
    industry_adjustment = Decimal("0.0")
    return max(Decimal("0.5"), min(base_smb_beta + industry_adjustment, Decimal("1.8")))


def estimate_hml_beta(industry_benchmarks: IndustryBenchmarks) -> Decimal:
    """Estimate HML beta for SME-sized companies."""
    _ = industry_benchmarks
    base_hml_beta = Decimal("0.7")
    industry_adjustment = Decimal("0.0")
    return max(Decimal("-0.5"), min(base_hml_beta + industry_adjustment, Decimal("1.5")))


def estimate_beta(
    *,
    config: DCFConfiguration,
    industry_benchmarks: IndustryBenchmarks,
    financial_data: Optional[FinancialData],
    adjust_beta_for_leverage: AdjustBetaForLeverage,
    logger: object,
) -> Decimal:
    """Estimate industry beta and optionally lever it from balance-sheet debt."""
    try:
        industry_beta = to_decimal(industry_benchmarks.average_beta)
        beta = industry_beta

        if financial_data is not None:
            current_year = financial_data.current_year
            total_debt = to_decimal(current_year.total_debt or 0)
            total_equity = to_decimal(current_year.total_equity or 0)
            tax_rate = to_decimal(industry_benchmarks.avg_tax_rate)
            debt_to_equity = total_debt / total_equity if total_equity > 0 else Decimal("0")
            beta = adjust_beta_for_leverage(industry_beta, debt_to_equity, tax_rate)

        min_beta = to_decimal(config.beta_range[0])
        max_beta = to_decimal(config.beta_range[1])
        return max(min_beta, min(beta, max_beta))

    except (ValueError, TypeError, AttributeError) as e:
        logger.error(
            f"Beta estimation failed: {e}",
            extra={"error_type": type(e).__name__, "error": str(e)},
        )
        return Decimal("1.0")
    except CalculationError as e:
        logger.error(
            f"Unexpected error in beta estimation: {e}",
            extra={"error_type": type(e).__name__, "error": str(e)},
        )
        return Decimal("1.0")


def adjust_beta_for_leverage(
    *,
    unlevered_beta: Decimal,
    debt_to_equity: Decimal,
    tax_rate: Decimal,
    logger: object,
) -> Decimal:
    """Adjust beta for leverage using the Hamada equation."""
    try:
        unlevered_beta_decimal = to_decimal(unlevered_beta)
        debt_to_equity_decimal = to_decimal(debt_to_equity)
        tax_rate_decimal = to_decimal(tax_rate)
        return unlevered_beta_decimal * (
            Decimal("1") + (Decimal("1") - tax_rate_decimal) * debt_to_equity_decimal
        )

    except (ValueError, TypeError, ZeroDivisionError) as e:
        logger.error(
            f"Beta leverage adjustment failed: {e}",
            extra={"error_type": type(e).__name__, "error": str(e)},
        )
        return unlevered_beta
    except CalculationError as e:
        logger.error(
            f"Unexpected error in beta leverage adjustment: {e}",
            extra={"error_type": type(e).__name__, "error": str(e)},
        )
        return unlevered_beta


def calculate_unlevered_beta(
    *,
    levered_beta: Decimal,
    debt_to_equity: Decimal,
    tax_rate: Decimal,
    logger: object,
) -> Decimal:
    """Calculate unlevered beta from levered beta."""
    try:
        levered_beta_decimal = to_decimal(levered_beta)
        debt_to_equity_decimal = to_decimal(debt_to_equity)
        tax_rate_decimal = to_decimal(tax_rate)
        return levered_beta_decimal / (
            Decimal("1") + (Decimal("1") - tax_rate_decimal) * debt_to_equity_decimal
        )

    except (ValueError, TypeError, ZeroDivisionError) as e:
        logger.error(
            f"Unlevered beta calculation failed: {e}",
            extra={"error_type": type(e).__name__, "error": str(e)},
        )
        return levered_beta
    except CalculationError as e:
        logger.error(
            f"Unexpected error in unlevered beta calculation: {e}",
            extra={"error_type": type(e).__name__, "error": str(e)},
        )
        return levered_beta


def estimate_risk_free_rate(
    *,
    market_context: MarketContext,
    maturity: str,
    logger: object,
) -> Decimal:
    """Estimate risk-free rate for different maturities."""
    try:
        base_rate = to_decimal(
            getattr(market_context, "risk_free_rate", None) or market_context.government_bond_yield
        )

        if maturity == "short_term":
            return base_rate - Decimal("0.005")
        if maturity == "long_term":
            return base_rate + Decimal("0.005")
        return base_rate

    except (ValueError, TypeError, AttributeError) as e:
        logger.error(
            f"Risk-free rate estimation failed: {e}",
            extra={"error_type": type(e).__name__, "error": str(e)},
        )
        return Decimal("0.03")
    except CalculationError as e:
        logger.error(
            f"Unexpected error in risk-free rate estimation: {e}",
            extra={"error_type": type(e).__name__, "error": str(e)},
        )
        return Decimal("0.03")


def calculate_market_risk_premium(
    *,
    market_context: MarketContext,
    historical_period: str,
    logger: object,
) -> Decimal:
    """Calculate market risk premium with period adjustment."""
    try:
        base_premium = to_decimal(
            getattr(market_context, "market_risk_premium", None)
            or market_context.equity_risk_premium
        )

        if historical_period == "short_term":
            return base_premium * Decimal("0.8")
        if historical_period == "long_term":
            return base_premium * Decimal("1.2")
        return base_premium

    except (ValueError, TypeError, AttributeError) as e:
        logger.error(
            f"Market risk premium calculation failed: {e}",
            extra={"error_type": type(e).__name__, "error": str(e)},
        )
        return get_default_equity_risk_premium(getattr(market_context, "country_code", None))
    except DCFCalculationError as e:
        logger.error(
            f"Unexpected error in market risk premium calculation: {e}",
            extra={"error_type": type(e).__name__, "error": str(e)},
        )
        return get_default_equity_risk_premium(getattr(market_context, "country_code", None))


def validate_wacc_components(
    *,
    config: DCFConfiguration,
    wacc_components: WACCComponents,
    logger: object,
) -> bool:
    """Validate WACC components for reasonableness."""
    try:
        if not (config.wacc_range[0] <= wacc_components.wacc <= config.wacc_range[1]):
            logger.warning(f"WACC outside expected range: {wacc_components.wacc:.2%}")
            return False

        weight_sum = wacc_components.equity_weight + wacc_components.debt_weight
        if abs(weight_sum - Decimal("1.0")) > 0.01:
            logger.warning(f"Weights don't sum to 1: {weight_sum:.3f}")
            return False

        if not (Decimal("0.05") <= wacc_components.cost_of_equity <= Decimal("0.30")):
            logger.warning(
                f"Cost of equity outside expected range: {wacc_components.cost_of_equity:.2%}"
            )
            return False

        if not (Decimal("0.02") <= wacc_components.cost_of_debt <= Decimal("0.20")):
            logger.warning(
                f"Cost of debt outside expected range: {wacc_components.cost_of_debt:.2%}"
            )
            return False

        return True

    except (ValueError, TypeError, AttributeError) as e:
        logger.error(
            f"WACC validation failed: {e}",
            extra={"error_type": type(e).__name__, "error": str(e)},
        )
        return False
    except DCFCalculationError as e:
        logger.error(
            f"Unexpected error in WACC validation: {e}",
            extra={"error_type": type(e).__name__, "error": str(e)},
        )
        return False
