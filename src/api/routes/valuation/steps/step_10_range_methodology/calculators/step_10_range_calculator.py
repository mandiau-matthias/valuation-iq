"""
Step 10 Range Calculator

Calculates growth rates and determines methodology selection.
"""

from decimal import Decimal
from typing import Optional

from src.api.routes.valuation.shared.historical_years import oldest_and_newest_historical_years
from src.utils.decimal_helpers import money_multiply, safe_money_divide, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class Step10RangeCalculator:
    """Calculates growth rates and range methodology for Step 10."""

    def calculate_growth_rate(self, request: any) -> Optional[Decimal]:
        """
        Calculate revenue growth rate (CAGR) from historical data.

        Args:
            request: Valuation request with historical_years_data

        Returns:
            Growth rate as decimal (e.g., Decimal('0.30') for 30%), or None if insufficient data
        """
        if not hasattr(request, "historical_years_data") or not request.historical_years_data:
            return None

        historical = request.historical_years_data
        if len(historical) < 2:
            return None

        oldest_year, newest_year = oldest_and_newest_historical_years(historical)
        oldest_revenue = oldest_year.revenue if hasattr(oldest_year, "revenue") else None
        newest_revenue = newest_year.revenue if hasattr(newest_year, "revenue") else None

        if oldest_revenue is None or newest_revenue is None or oldest_revenue <= 0:
            return None

        oldest_year_value = getattr(oldest_year, "year", None)
        newest_year_value = getattr(newest_year, "year", None)
        try:
            year_span = int(newest_year_value) - int(oldest_year_value)
        except (TypeError, ValueError):
            year_span = 0
        years = year_span if year_span > 0 else len(historical) - 1

        try:
            import math

            if oldest_revenue <= 0 or newest_revenue <= 0 or years <= 0:
                logger.warning(
                    "⚠️ Invalid inputs for CAGR calculation",
                    extra={
                        "step_number": 10,
                        "oldest_revenue": oldest_revenue,
                        "newest_revenue": newest_revenue,
                        "years": years,
                    },
                )
                return None

            cagr = (newest_revenue / oldest_revenue) ** (Decimal("1.0") / years) - Decimal("1.0")

            if not math.isfinite(float(cagr)):
                logger.warning(
                    "⚠️ CAGR calculation produced invalid result (NaN/Infinity)",
                    extra={
                        "step_number": 10,
                        "oldest_revenue": oldest_revenue,
                        "newest_revenue": newest_revenue,
                        "years": years,
                    },
                )
                return None

            return to_decimal(cagr)
        except (ValueError, ZeroDivisionError, OverflowError) as e:
            logger.warning("⚠️ CAGR calculation failed", extra={"step_number": 10, "error": str(e)})
            return None

    def determine_growth_validated(self, request: any) -> bool:
        """
        Determine if growth is validated (has historical data).

        Args:
            request: Valuation request

        Returns:
            True if growth is validated, False otherwise
        """
        if hasattr(request, "historical_years_data") and request.historical_years_data:
            historical_count = (
                len(request.historical_years_data)
                if isinstance(request.historical_years_data, list)
                else 0
            )
            return historical_count >= 2
        return False

    def should_use_dispersion(
        self,
        sufficient_comparables: bool,
        comparables_found: int,
        primary_method: str,
        ev_revenue_p25: Optional[Decimal],
        ev_revenue_p75: Optional[Decimal],
        ev_ebitda_p25: Optional[Decimal],
        ev_ebitda_p75: Optional[Decimal],
    ) -> bool:
        """
        Determine if multiple dispersion should be used.

        Args:
            sufficient_comparables: Whether comparables are sufficient
            comparables_found: Number of comparables found
            primary_method: Primary method ('EV/Revenue' or 'EV/EBITDA')
            ev_revenue_p25: Revenue P25 percentile
            ev_revenue_p75: Revenue P75 percentile
            ev_ebitda_p25: EBITDA P25 percentile
            ev_ebitda_p75: EBITDA P75 percentile

        Returns:
            True if dispersion should be used, False otherwise
        """
        return (
            sufficient_comparables
            and comparables_found >= 5
            and (
                (
                    primary_method == "EV/Revenue"
                    and ev_revenue_p25 is not None
                    and ev_revenue_p75 is not None
                )
                or (
                    primary_method == "EV/EBITDA"
                    and ev_ebitda_p25 is not None
                    and ev_ebitda_p75 is not None
                )
            )
        )

    def calculate_dispersion_range(
        self,
        equity_mid: Decimal,
        primary_method: str,
        ev_revenue_p25: Optional[Decimal],
        ev_revenue_p50: Optional[Decimal],
        ev_revenue_p75: Optional[Decimal],
        ev_ebitda_p25: Optional[Decimal],
        ev_ebitda_p50: Optional[Decimal],
        ev_ebitda_p75: Optional[Decimal],
    ) -> tuple[Optional[Decimal], Optional[Decimal], bool]:
        """
        Calculate range using multiple dispersion.

        Args:
            equity_mid: Equity mid value
            primary_method: Primary method ('EV/Revenue' or 'EV/EBITDA')
            ev_revenue_p25: Revenue P25 percentile
            ev_revenue_p50: Revenue P50 percentile
            ev_revenue_p75: Revenue P75 percentile
            ev_ebitda_p25: EBITDA P25 percentile
            ev_ebitda_p50: EBITDA P50 percentile
            ev_ebitda_p75: EBITDA P75 percentile

        Returns:
            Tuple of (equity_low, equity_high, success)
        """
        if (
            primary_method == "EV/Revenue"
            and ev_revenue_p25 is not None
            and ev_revenue_p50 is not None
            and ev_revenue_p75 is not None
        ):
            p50_decimal = to_decimal(ev_revenue_p50)
            if p50_decimal > 0:
                p25_ratio = safe_money_divide(
                    to_decimal(ev_revenue_p25), p50_decimal, Decimal("0.8")
                )
                p75_ratio = safe_money_divide(
                    to_decimal(ev_revenue_p75), p50_decimal, Decimal("1.2")
                )
                equity_low = money_multiply(equity_mid, p25_ratio)
                equity_high = money_multiply(equity_mid, p75_ratio)
                return equity_low, equity_high, True
        elif (
            primary_method == "EV/EBITDA"
            and ev_ebitda_p25 is not None
            and ev_ebitda_p50 is not None
            and ev_ebitda_p75 is not None
        ):
            p50_decimal = to_decimal(ev_ebitda_p50)
            if p50_decimal > 0:
                p25_ratio = safe_money_divide(
                    to_decimal(ev_ebitda_p25), p50_decimal, Decimal("0.8")
                )
                p75_ratio = safe_money_divide(
                    to_decimal(ev_ebitda_p75), p50_decimal, Decimal("1.2")
                )
                equity_low = money_multiply(equity_mid, p25_ratio)
                equity_high = money_multiply(equity_mid, p75_ratio)
                return equity_low, equity_high, True

        return None, None, False

    def adjust_spread_for_declining_revenue(
        self, growth_rate: Optional[Decimal], total_spread: Decimal
    ) -> tuple[Decimal, bool]:
        """
        Adjust spread for declining revenue scenarios.

        Args:
            growth_rate: Growth rate as decimal
            total_spread: Current total spread

        Returns:
            Tuple of (adjusted_spread, is_declining)
        """
        if growth_rate is not None and growth_rate < -0.20:  # CAGR < -20%
            adjusted_spread = to_decimal("0.333")  # ±33.3%
            logger.info(
                "⚠️ Declining revenue detected: Applying ±33.3% range per academic valuation standards (Koller, Goedhart & Wessels 2020, Chapter 10)",
                extra={
                    "step_number": 10,
                    "growth_rate": growth_rate,
                    "growth_rate_pct": growth_rate * 100,
                    "original_total_spread": to_decimal(total_spread),
                    "adjusted_total_spread": to_decimal(adjusted_spread),
                },
            )
            return adjusted_spread, True
        return total_spread, False
