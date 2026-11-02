
from src.utils.exceptions import CalculationError, DCFCalculationError

"""
Real Options Valuation Engine

Implements Real Options Valuation (ROV) for strategic optionality.
Based on Valuation_Trends_2026.md research requirements.

Features:
- Black-Scholes Option Pricing
- Strategic options for tech/biotech companies
- Expansion, abandonment, and timing options
- Decision tree analysis

Author: Senior CTO
Version: 1.0.0
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy.stats import norm

from src.utils.decimal_helpers import bank_round, from_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class OptionParameters:
    """Parameters for real option valuation."""

    current_value: Decimal  # S0 - Current asset value
    strike_price: Decimal  # K - Exercise price
    time_to_expiration: Decimal  # T - Time to expiration (years)
    risk_free_rate: Decimal  # r - Risk-free rate
    volatility: Decimal  # σ - Volatility
    dividend_yield: Decimal = None  # q - Dividend yield (default 0 for growth companies)

    def __post_init__(self):
        if self.dividend_yield is None:
            self.dividend_yield = Decimal("0.0")


class RealOptionsValuationEngine:
    """
    Real Options Valuation for strategic optionality.

    Use Cases:
    - Tech companies with platform optionality
    - Biotech with drug pipeline options
    - Companies with expansion options
    - Patent/IP monetization options

    Methods:
    - Black-Scholes Option Pricing
    - Binomial Tree Models
    - Decision Tree Analysis
    """

    def __init__(self):
        """Initialize Real Options Valuation Engine."""
        self.logger = get_logger(__name__)

    def calculate_option_value(
        self,
        base_npv: Decimal,
        volatility: Decimal,
        time_to_expiration: Decimal,
        strike_price: Decimal,
        risk_free_rate: Decimal,
        option_type: str = "call",
    ) -> Dict[str, Decimal]:
        """
        Calculate real option value using Black-Scholes.

        Args:
            base_npv: Base NPV of the project/asset
            volatility: Volatility of the underlying asset
            time_to_expiration: Time to expiration in years
            strike_price: Exercise price
            risk_free_rate: Risk-free interest rate
            option_type: "call" or "put"

        Returns:
        {
            "option_value": Decimal,
            "expanded_npv": base_npv + option_value,
            "option_type": "expansion|abandonment|timing",
            "exercise_probability": Decimal,
            "delta": Decimal,
            "gamma": Decimal,
            "theta": Decimal,
            "vega": Decimal
        }
        """
        try:
            # Create option parameters
            base_npv_decimal = to_decimal(base_npv)
            strike_price_decimal = to_decimal(strike_price)
            time_to_expiration_decimal = to_decimal(time_to_expiration)
            risk_free_rate_decimal = to_decimal(risk_free_rate)
            volatility_decimal = to_decimal(volatility)

            params = OptionParameters(
                current_value=base_npv_decimal,
                strike_price=strike_price_decimal,
                time_to_expiration=time_to_expiration_decimal,
                risk_free_rate=risk_free_rate_decimal,
                volatility=volatility_decimal,
            )

            if option_type == "call":
                option_value, greeks = self._black_scholes_call(params)
            else:  # put
                option_value, greeks = self._black_scholes_put(params)

            # Calculate exercise probability
            exercise_prob = self._calculate_exercise_probability(params)

            # Determine option type based on context
            if base_npv_decimal > strike_price_decimal:
                option_category = "expansion"
            elif base_npv_decimal < strike_price_decimal * Decimal("0.5"):
                option_category = "abandonment"
            else:
                option_category = "timing"

            result = {
                "option_value": option_value,
                "expanded_npv": base_npv_decimal + option_value,
                "option_type": option_category,
                "exercise_probability": exercise_prob,
                "delta": greeks["delta"],
                "gamma": greeks["gamma"],
                "theta": greeks["theta"],
                "vega": greeks["vega"],
            }

            self.logger.info(
                f"Real option calculated",
                option_value=option_value,
                option_type=option_category,
                exercise_probability=exercise_prob,
            )

            return result

        except (ValueError, TypeError, ZeroDivisionError) as e:
            self.logger.error(
                f"Error calculating real option value: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise CalculationError(
                f"Failed to calculate real option value: {e}",
                calculation_type="Real Options Valuation",
                context={"base_npv": base_npv, "strike_price": strike_price},
            ) from e
        except CalculationError as e:
            self.logger.error(
                f"Unexpected error calculating real option value: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise CalculationError(
                f"Unexpected error in real option calculation: {e}",
                calculation_type="Real Options Valuation",
                context={
                    "base_npv": from_decimal(base_npv) if "base_npv" in locals() else None,
                    "strike_price": (
                        from_decimal(strike_price) if "strike_price" in locals() else None
                    ),
                    "error_type": type(e).__name__,
                },
            ) from e

    def _black_scholes_call(self, params: OptionParameters) -> Tuple[Decimal, Dict[str, Decimal]]:
        """Calculate Black-Scholes call option value and Greeks."""
        try:
            # Convert to float for numpy/scipy operations
            S0 = to_decimal(params.current_value)
            K = to_decimal(params.strike_price)
            T = to_decimal(params.time_to_expiration)
            r = to_decimal(params.risk_free_rate)
            sigma = to_decimal(params.volatility)
            q = to_decimal(params.dividend_yield)

            # Calculate d1 and d2
            d1 = (np.log(S0 / K) + (r - q + Decimal("0.5") * sigma**2) * T) / (sigma * np.sqrt(T))
            d2 = d1 - sigma * np.sqrt(T)

            # Calculate option value
            option_value_float = S0 * np.exp(-q * T) * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(
                d2
            )

            # Calculate Greeks
            delta_float = np.exp(-q * T) * norm.cdf(d1)
            gamma_float = (np.exp(-q * T) * norm.pdf(d1)) / (S0 * sigma * np.sqrt(T))
            theta_float = (
                -(S0 * np.exp(-q * T) * norm.pdf(d1) * sigma) / (2 * np.sqrt(T))
                - r * K * np.exp(-r * T) * norm.cdf(d2)
                + q * S0 * np.exp(-q * T) * norm.cdf(d1)
            )
            vega_float = S0 * np.exp(-q * T) * norm.pdf(d1) * np.sqrt(T)

            # Convert back to Decimal
            greeks = {
                "delta": to_decimal(delta_float),
                "gamma": to_decimal(gamma_float),
                "theta": to_decimal(theta_float),
                "vega": to_decimal(vega_float),
            }

            return to_decimal(option_value_float), greeks

        except (ValueError, TypeError, ZeroDivisionError) as e:
            self.logger.error(
                f"Error in Black-Scholes call calculation: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise CalculationError(
                f"Failed to calculate Black-Scholes call option: {e}",
                calculation_type="Real Options Valuation",
                context={
                    "current_value": params.current_value,
                    "strike_price": params.strike_price,
                },
            ) from e
        except CalculationError as e:
            self.logger.error(
                f"Unexpected error in Black-Scholes call calculation: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise CalculationError(
                f"Unexpected error in Black-Scholes call calculation: {e}",
                calculation_type="Real Options Valuation",
                context={
                    "current_value": (
                        from_decimal(params.current_value) if "params" in locals() else None
                    ),
                    "strike_price": (
                        from_decimal(params.strike_price) if "params" in locals() else None
                    ),
                    "error_type": type(e).__name__,
                },
            ) from e

    def _black_scholes_put(self, params: OptionParameters) -> Tuple[Decimal, Dict[str, Decimal]]:
        """Calculate Black-Scholes put option value and Greeks."""
        try:
            # Convert to float for numpy/scipy operations
            S0 = to_decimal(params.current_value)
            K = to_decimal(params.strike_price)
            T = to_decimal(params.time_to_expiration)
            r = to_decimal(params.risk_free_rate)
            sigma = to_decimal(params.volatility)
            q = to_decimal(params.dividend_yield)

            # Calculate d1 and d2
            d1 = (np.log(S0 / K) + (r - q + Decimal("0.5") * sigma**2) * T) / (sigma * np.sqrt(T))
            d2 = d1 - sigma * np.sqrt(T)

            # Calculate option value
            option_value_float = K * np.exp(-r * T) * norm.cdf(-d2) - S0 * np.exp(
                -q * T
            ) * norm.cdf(-d1)

            # Calculate Greeks
            delta_float = -np.exp(-q * T) * norm.cdf(-d1)
            gamma_float = (np.exp(-q * T) * norm.pdf(d1)) / (S0 * sigma * np.sqrt(T))
            theta_float = (
                -(S0 * np.exp(-q * T) * norm.pdf(d1) * sigma) / (2 * np.sqrt(T))
                + r * K * np.exp(-r * T) * norm.cdf(-d2)
                - q * S0 * np.exp(-q * T) * norm.cdf(-d1)
            )
            vega_float = S0 * np.exp(-q * T) * norm.pdf(d1) * np.sqrt(T)

            # Convert back to Decimal
            greeks = {
                "delta": to_decimal(delta_float),
                "gamma": to_decimal(gamma_float),
                "theta": to_decimal(theta_float),
                "vega": to_decimal(vega_float),
            }

            return to_decimal(option_value_float), greeks

        except (ValueError, TypeError, ZeroDivisionError) as e:
            self.logger.error(
                f"Error in Black-Scholes put calculation: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise CalculationError(
                f"Failed to calculate Black-Scholes put option: {e}",
                calculation_type="Real Options Valuation",
                context={
                    "current_value": params.current_value,
                    "strike_price": params.strike_price,
                },
            ) from e
        except CalculationError as e:
            self.logger.error(
                f"Unexpected error in Black-Scholes put calculation: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise CalculationError(
                f"Unexpected error in Black-Scholes put calculation: {e}",
                calculation_type="Real Options Valuation",
                context={
                    "current_value": (
                        from_decimal(params.current_value) if "params" in locals() else None
                    ),
                    "strike_price": (
                        from_decimal(params.strike_price) if "params" in locals() else None
                    ),
                    "error_type": type(e).__name__,
                },
            ) from e

    def _calculate_exercise_probability(self, params: OptionParameters) -> Decimal:
        """Calculate probability of option exercise."""
        try:
            # Convert to float for numpy/scipy operations
            S0 = to_decimal(params.current_value)
            K = to_decimal(params.strike_price)
            T = to_decimal(params.time_to_expiration)
            r = to_decimal(params.risk_free_rate)
            sigma = to_decimal(params.volatility)
            q = to_decimal(params.dividend_yield)

            # Calculate d2 (same as in Black-Scholes)
            d2 = (np.log(S0 / K) + (r - q - Decimal("0.5") * sigma**2) * T) / (sigma * np.sqrt(T))

            # Probability of exercise = N(d2)
            exercise_prob_float = norm.cdf(d2)

            return to_decimal(exercise_prob_float)

        except (ValueError, TypeError, ZeroDivisionError) as e:
            self.logger.error(
                f"Error calculating exercise probability: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise CalculationError(
                f"Failed to calculate exercise probability: {e}",
                calculation_type="Real Options Valuation",
            ) from e
        except CalculationError as e:
            self.logger.error(
                f"Unexpected error calculating exercise probability: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise CalculationError(
                f"Unexpected error in exercise probability calculation: {e}",
                calculation_type="Real Options Valuation",
                context={"error_type": type(e).__name__},
            ) from e

    def calculate_strategic_options(
        self, company_profile: Dict[str, Any], base_npv: Decimal
    ) -> Dict[str, Any]:
        """
        Calculate strategic options for a company.

        Args:
            company_profile: Company characteristics
            base_npv: Base NPV of the company

        Returns:
            Dict with strategic options analysis
        """
        try:
            industry = company_profile.get("industry", "").lower()
            company_size = company_profile.get("company_size", "").lower()
            growth_rate = to_decimal(company_profile.get("growth_rate", Decimal("0.0")))

            base_npv_decimal = to_decimal(base_npv)
            strategic_options = []
            total_option_value = Decimal("0.0")

            # Technology/SaaS companies - Platform expansion options
            if industry in ["technology", "saas", "software"]:
                expansion_option = self._calculate_platform_expansion_option(
                    base_npv_decimal, growth_rate
                )
                strategic_options.append(expansion_option)
                total_option_value += to_decimal(expansion_option["option_value"])

            # Biotech/Pharma companies - Pipeline options
            if industry in ["biotech", "pharma"]:
                pipeline_option = self._calculate_pipeline_option(base_npv_decimal, company_size)
                strategic_options.append(pipeline_option)
                total_option_value += to_decimal(pipeline_option["option_value"])

            # High-growth companies - Market expansion options
            if growth_rate and growth_rate > Decimal("0.3"):
                market_option = self._calculate_market_expansion_option(
                    base_npv_decimal, growth_rate
                )
                strategic_options.append(market_option)
                total_option_value += to_decimal(market_option["option_value"])

            # All companies - Abandonment options (put options)
            abandonment_option = self._calculate_abandonment_option(base_npv_decimal, company_size)
            strategic_options.append(abandonment_option)
            total_option_value += to_decimal(abandonment_option["option_value"])

            return {
                "strategic_options": strategic_options,
                "total_option_value": total_option_value,
                "expanded_npv": base_npv_decimal + total_option_value,
                "option_premium_pct": (
                    from_decimal((total_option_value / base_npv_decimal * Decimal("100")))
                    if base_npv_decimal > 0
                    else 0.0
                ),
            }

        except (KeyError, ValueError, TypeError) as e:
            self.logger.error(
                f"Error calculating strategic options: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise CalculationError(
                f"Failed to calculate strategic options: {e}",
                calculation_type="Real Options Valuation",
                context={"base_npv": base_npv},
            ) from e
        except CalculationError as e:
            self.logger.error(
                f"Unexpected error calculating strategic options: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise CalculationError(
                f"Unexpected error in strategic options calculation: {e}",
                calculation_type="Real Options Valuation",
                context={
                    "base_npv": from_decimal(base_npv) if "base_npv" in locals() else None,
                    "error_type": type(e).__name__,
                },
            ) from e

    def _calculate_platform_expansion_option(
        self, base_npv: Decimal, growth_rate: Decimal
    ) -> Dict[str, Any]:
        """Calculate platform expansion option for tech companies."""
        try:
            base_npv_decimal = to_decimal(base_npv)
            # Platform expansion parameters
            strike_price = base_npv_decimal * Decimal("0.5")  # 50% of current value to expand
            volatility = Decimal("0.4")  # High volatility for tech
            time_to_expiration = Decimal("3.0")  # 3 years to expand
            risk_free_rate = Decimal("0.03")  # 3% risk-free rate

            option_result = self.calculate_option_value(
                base_npv=base_npv_decimal,
                volatility=volatility,
                time_to_expiration=time_to_expiration,
                strike_price=strike_price,
                risk_free_rate=risk_free_rate,
                option_type="call",
            )

            return {
                "option_name": "Platform Expansion",
                "option_description": "Option to expand platform to new markets/features",
                "option_value": option_result["option_value"],
                "exercise_probability": option_result["exercise_probability"],
                "option_type": "expansion",
            }

        except CalculationError:
            raise  # Re-raise CalculationError from calculate_option_value
        except CalculationError as e:
            self.logger.error(
                f"Unexpected error calculating platform expansion option: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise CalculationError(
                f"Unexpected error in platform expansion option: {e}",
                calculation_type="Real Options Valuation",
                context={"error_type": type(e).__name__, "option_type": "expansion"},
            ) from e

    def _calculate_pipeline_option(self, base_npv: Decimal, company_size: str) -> Dict[str, Any]:
        """Calculate drug pipeline option for biotech/pharma companies."""
        try:
            base_npv_decimal = to_decimal(base_npv)
            # Pipeline option parameters
            if company_size == "startup":
                strike_price = base_npv_decimal * Decimal("0.3")  # Lower threshold for startups
                volatility = Decimal("0.6")  # Very high volatility
                time_to_expiration = Decimal("5.0")  # Longer time for drug development
            else:
                strike_price = base_npv_decimal * Decimal("0.4")
                volatility = Decimal("0.5")
                time_to_expiration = Decimal("4.0")

            risk_free_rate = Decimal("0.03")

            option_result = self.calculate_option_value(
                base_npv=base_npv_decimal,
                volatility=volatility,
                time_to_expiration=time_to_expiration,
                strike_price=strike_price,
                risk_free_rate=risk_free_rate,
                option_type="call",
            )

            return {
                "option_name": "Drug Pipeline",
                "option_description": "Option to develop and commercialize drug pipeline",
                "option_value": option_result["option_value"],
                "exercise_probability": option_result["exercise_probability"],
                "option_type": "expansion",
            }

        except CalculationError:
            raise  # Re-raise CalculationError from calculate_option_value
        except CalculationError as e:
            self.logger.error(
                f"Unexpected error calculating pipeline option: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise CalculationError(
                f"Unexpected error in pipeline option: {e}",
                calculation_type="Real Options Valuation",
                context={"error_type": type(e).__name__, "option_type": "expansion"},
            ) from e

    def _calculate_market_expansion_option(
        self, base_npv: Decimal, growth_rate: Decimal
    ) -> Dict[str, Any]:
        """Calculate market expansion option for high-growth companies."""
        try:
            base_npv_decimal = to_decimal(base_npv)
            growth_rate_decimal = to_decimal(growth_rate)
            # Market expansion parameters
            strike_price = base_npv_decimal * Decimal("0.6")  # 60% of current value to expand
            volatility = min(Decimal("0.5"), growth_rate_decimal)  # Volatility related to growth
            time_to_expiration = Decimal("2.0")  # 2 years to expand
            risk_free_rate = Decimal("0.03")

            option_result = self.calculate_option_value(
                base_npv=base_npv_decimal,
                volatility=volatility,
                time_to_expiration=time_to_expiration,
                strike_price=strike_price,
                risk_free_rate=risk_free_rate,
                option_type="call",
            )

            return {
                "option_name": "Market Expansion",
                "option_description": "Option to expand into new markets/geographies",
                "option_value": option_result["option_value"],
                "exercise_probability": option_result["exercise_probability"],
                "option_type": "expansion",
            }

        except CalculationError:
            raise  # Re-raise CalculationError from calculate_option_value
        except CalculationError as e:
            self.logger.error(
                f"Unexpected error calculating market expansion option: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise CalculationError(
                f"Unexpected error in market expansion option: {e}",
                calculation_type="Real Options Valuation",
                context={"error_type": type(e).__name__, "option_type": "expansion"},
            ) from e

    def _calculate_abandonment_option(self, base_npv: Decimal, company_size: str) -> Dict[str, Any]:
        """Calculate abandonment option (put option) for all companies."""
        try:
            base_npv_decimal = to_decimal(base_npv)
            # Abandonment option parameters
            if company_size == "startup":
                strike_price = base_npv_decimal * Decimal("0.3")  # Can abandon for 30% of value
                volatility = Decimal("0.5")
                time_to_expiration = Decimal("2.0")
            else:
                strike_price = base_npv_decimal * Decimal("0.4")  # Can abandon for 40% of value
                volatility = Decimal("0.3")
                time_to_expiration = Decimal("3.0")

            risk_free_rate = Decimal("0.03")

            option_result = self.calculate_option_value(
                base_npv=base_npv_decimal,
                volatility=volatility,
                time_to_expiration=time_to_expiration,
                strike_price=strike_price,
                risk_free_rate=risk_free_rate,
                option_type="put",
            )

            return {
                "option_name": "Abandonment Option",
                "option_description": "Option to abandon project and recover salvage value",
                "option_value": option_result["option_value"],
                "exercise_probability": option_result["exercise_probability"],
                "option_type": "abandonment",
            }

        except CalculationError:
            raise  # Re-raise CalculationError from calculate_option_value
        except CalculationError as e:
            self.logger.error(
                f"Unexpected error calculating abandonment option: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise CalculationError(
                f"Unexpected error in abandonment option: {e}",
                calculation_type="Real Options Valuation",
                context={"error_type": type(e).__name__, "option_type": "abandonment"},
            ) from e

    def calculate_compound_options(
        self, base_npv: Decimal, option_chain: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate compound options (options on options).

        Args:
            base_npv: Base NPV
            option_chain: List of sequential options

        Returns:
            Compound option analysis
        """
        try:
            base_npv_decimal = to_decimal(base_npv)
            # This is a simplified compound option calculation
            # In practice, this would require more sophisticated modeling

            total_compound_value = Decimal("0.0")
            compound_options = []

            for i, option in enumerate(option_chain):
                # Each subsequent option depends on the previous
                if i == 0:
                    option_value = to_decimal(option["option_value"])
                else:
                    # Reduce value based on probability of previous option exercise
                    exercise_prob = to_decimal(
                        option_chain[i - 1].get("exercise_probability", Decimal("0.5"))
                    )
                    option_value = to_decimal(option["option_value"]) * exercise_prob

                compound_options.append(
                    {
                        "option_name": option["option_name"],
                        "option_value": option_value,
                        "stage": i + 1,
                    }
                )

                total_compound_value += option_value

            return {
                "compound_options": compound_options,
                "total_compound_value": total_compound_value,
                "compound_premium_pct": (
                    from_decimal((total_compound_value / base_npv_decimal * Decimal("100")))
                    if base_npv_decimal > 0
                    else 0.0
                ),
            }

        except (ValueError, TypeError, ZeroDivisionError, KeyError) as e:
            self.logger.error(
                f"Error calculating compound options: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise CalculationError(
                f"Failed to calculate compound options: {e}",
                calculation_type="Real Options Valuation",
                context={"base_npv": base_npv},
            ) from e
        except CalculationError as e:
            self.logger.error(
                f"Unexpected error calculating compound options: {e}",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            raise CalculationError(
                f"Unexpected error in compound options calculation: {e}",
                calculation_type="Real Options Valuation",
                context={
                    "base_npv": from_decimal(base_npv) if "base_npv" in locals() else None,
                    "error_type": type(e).__name__,
                },
            ) from e
