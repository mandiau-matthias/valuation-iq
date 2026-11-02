"""
Ownership Calculator

Handles business structure and ownership percentage adjustments for valuations.
Integrates main platform logic with advanced valuation engine.
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.utils.decimal_helpers import bank_round, from_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class OwnershipCalculator:
    """
    Calculator for ownership-adjusted valuations.

    Handles:
    - Business structure (sole trader vs company)
    - Shares for sale percentage
    - Growth rate calculations from historical data
    - Growth premium/discount application
    """

    def __init__(self):
        pass

    def calculate_cagr(self, start_value: Decimal, end_value: Decimal, periods: int) -> Decimal:
        """
        Calculate Compound Annual Growth Rate (CAGR).

        Formula: CAGR = (End Value / Start Value) ^ (1 / periods) - 1
        """
        start_decimal = to_decimal(start_value)
        end_decimal = to_decimal(end_value)

        if start_decimal <= 0 or end_decimal <= 0:
            return Decimal("0.0")

        try:
            # Use Decimal arithmetic, convert to float only for exponentiation
            # Decimal doesn't support fractional exponents, so convert for exponentiation
            ratio_decimal = end_decimal / start_decimal
            exponent = Decimal("1") / Decimal(str(periods))
            # Convert to float only for exponentiation, then back to Decimal immediately
            ratio_float = float(ratio_decimal)
            exponent_float = float(exponent)
            cagr_float = (ratio_float ** exponent_float) - 1.0
            cagr_decimal = to_decimal(cagr_float) * Decimal("100")  # Return as percentage
            return bank_round(cagr_decimal, 2)
        except (ValueError, ZeroDivisionError):
            return Decimal("0.0")

    def calculate_growth_rates(self, historical_data: List[Dict[str, Any]]) -> Dict[str, Decimal]:
        """
        Calculate revenue and EBITDA growth rates from historical data.

        Args:
            historical_data: List of yearly financial data (must be sorted by year)

        Returns:
            Dict with revenue_cagr and ebitda_cagr
        """
        if not historical_data or len(historical_data) < 2:
            logger.warning("Insufficient historical data for growth calculation")
            return {"revenue_cagr": Decimal("0.0"), "ebitda_cagr": Decimal("0.0"), "periods": 0}

        # Sort by year to ensure correct order
        sorted_data = sorted(historical_data, key=lambda x: x.get("year", 0))

        first_year = sorted_data[0]
        last_year = sorted_data[-1]
        periods = len(sorted_data) - 1

        revenue_cagr = self.calculate_cagr(
            to_decimal(first_year.get("revenue", 0)),
            to_decimal(last_year.get("revenue", 0)),
            periods,
        )

        ebitda_cagr = self.calculate_cagr(
            to_decimal(first_year.get("ebitda", 0)), to_decimal(last_year.get("ebitda", 0)), periods
        )

        logger.info(
            "Growth rates calculated",
            revenue_cagr=from_decimal(revenue_cagr),
            ebitda_cagr=from_decimal(ebitda_cagr),
            periods=periods,
        )

        return {"revenue_cagr": revenue_cagr, "ebitda_cagr": ebitda_cagr, "periods": periods}

    def calculate_growth_multiplier(self, revenue_cagr: Decimal, ebitda_cagr: Decimal) -> Decimal:
        """
        Calculate growth-based valuation multiplier.

        High growth = premium
        Negative growth = discount

        Args:
            revenue_cagr: Revenue CAGR (%)
            ebitda_cagr: EBITDA CAGR (%)

        Returns:
            Growth multiplier (Decimal('1.0') = no adjustment)
        """
        revenue_cagr_decimal = to_decimal(revenue_cagr)
        ebitda_cagr_decimal = to_decimal(ebitda_cagr)
        # Average growth rate
        avg_growth = (revenue_cagr_decimal + ebitda_cagr_decimal) / Decimal("2")

        if avg_growth >= Decimal("30"):
            multiplier = Decimal("1.40")  # +40% premium for exceptional growth
            reason = "Exceptional growth (30%+ CAGR)"
        elif avg_growth >= Decimal("20"):
            multiplier = Decimal("1.25")  # +25% premium for high growth
            reason = "High growth (20-30% CAGR)"
        elif avg_growth >= Decimal("10"):
            multiplier = Decimal("1.10")  # +10% premium for good growth
            reason = "Good growth (10-20% CAGR)"
        elif avg_growth >= Decimal("5"):
            multiplier = Decimal("1.00")  # No adjustment for moderate growth
            reason = "Moderate growth (5-10% CAGR)"
        elif avg_growth >= Decimal("0"):
            multiplier = Decimal("0.95")  # -5% discount for slow growth
            reason = "Slow growth (0-5% CAGR)"
        else:
            multiplier = Decimal("0.80")  # -20% discount for negative growth
            reason = "Negative growth (declining)"

        logger.info(
            "Growth multiplier calculated",
            avg_growth=from_decimal(avg_growth),
            multiplier=from_decimal(multiplier),
            reason=reason,
        )

        return multiplier

    def apply_ownership_adjustment(
        self,
        base_valuation: Dict[str, Decimal],
        business_type: str,
        shares_for_sale: Optional[Decimal] = None,
        growth_rates: Optional[Dict[str, Decimal]] = None,
    ) -> Dict[str, Any]:
        """
        Apply ownership percentage and growth adjustments to valuation.

        Main Platform Logic:
        1. Calculate base valuation (DCF + Multiples)
        2. Apply growth premium/discount
        3. Apply ownership percentage (if company with partial sale)

        Args:
            base_valuation: Dict with equity_value_low, _mid, _high
            business_type: 'sole-trader' or 'company'
            shares_for_sale: Percentage of shares for sale (1-100)
            growth_rates: Dict with revenue_cagr and ebitda_cagr

        Returns:
            Adjusted valuation with ownership details
        """
        # 1. Apply growth multiplier if historical data available
        if growth_rates and growth_rates.get("periods", 0) > 0:
            growth_multiplier = self.calculate_growth_multiplier(
                growth_rates["revenue_cagr"], growth_rates["ebitda_cagr"]
            )
        else:
            growth_multiplier = Decimal("1.0")

        # Apply growth adjustment to base valuation
        equity_low = to_decimal(base_valuation["equity_value_low"])
        equity_mid = to_decimal(base_valuation["equity_value_mid"])
        equity_high = to_decimal(base_valuation["equity_value_high"])

        adjusted_low = equity_low * growth_multiplier
        adjusted_mid = equity_mid * growth_multiplier
        adjusted_high = equity_high * growth_multiplier

        # 2. Determine ownership percentage
        if business_type == "sole-trader":
            ownership_percentage = Decimal("100.0")
            ownership_explanation = "100% ownership (sole trader)"
        elif business_type == "company":
            ownership_percentage = (
                to_decimal(shares_for_sale) if shares_for_sale else Decimal("100.0")
            )
            if ownership_percentage == Decimal("100.0"):
                ownership_explanation = "100% of company shares"
            else:
                ownership_explanation = f"{from_decimal(ownership_percentage)}% of company shares"
        else:
            # Default to 100%
            ownership_percentage = Decimal("100.0")
            ownership_explanation = "100% ownership (assumed)"

        # 3. Apply ownership percentage
        ownership_multiplier = ownership_percentage / Decimal("100.0")

        final_low = adjusted_low * ownership_multiplier
        final_mid = adjusted_mid * ownership_multiplier
        final_high = adjusted_high * ownership_multiplier

        logger.info(
            "Ownership adjustment applied",
            business_type=business_type,
            ownership_percentage=from_decimal(ownership_percentage),
            growth_multiplier=from_decimal(growth_multiplier),
            base_mid=from_decimal(equity_mid),
            adjusted_mid=from_decimal(adjusted_mid),
            final_mid=from_decimal(final_mid),
        )

        return {
            # Final ownership-adjusted values
            "equity_value_low": bank_round(final_low, 2),
            "equity_value_mid": bank_round(final_mid, 2),
            "equity_value_high": bank_round(final_high, 2),
            # Detailed breakdown
            "ownership_adjustment": {
                "business_type": business_type,
                "shares_for_sale": from_decimal(ownership_percentage),
                "ownership_multiplier": from_decimal(ownership_multiplier),
                "ownership_explanation": ownership_explanation,
                # Enterprise value (before ownership adjustment)
                "enterprise_value_low": bank_round(adjusted_low, 2),
                "enterprise_value_mid": bank_round(adjusted_mid, 2),
                "enterprise_value_high": bank_round(adjusted_high, 2),
                # Growth adjustment details
                "growth_adjustment": {
                    "revenue_cagr": (
                        from_decimal(growth_rates.get("revenue_cagr", Decimal("0")))
                        if growth_rates
                        else 0
                    ),
                    "ebitda_cagr": (
                        from_decimal(growth_rates.get("ebitda_cagr", Decimal("0")))
                        if growth_rates
                        else 0
                    ),
                    "growth_multiplier": from_decimal(growth_multiplier),
                    "growth_premium_pct": from_decimal(
                        bank_round((growth_multiplier - Decimal("1.0")) * Decimal("100"), 2)
                    ),
                },
            },
        }
