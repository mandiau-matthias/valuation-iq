"""
Business Scenario Detection

Identifies business scenario to customize report content and methodology approach.
"""

from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Optional, Union

from src.domain.historical_years import oldest_historical_year

if TYPE_CHECKING:
    from src.api.schemas import ValuationRequest

from src.services.interfaces.request_response_protocol import ValuationRequestProtocol
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class BusinessScenario(Enum):
    """Business scenario classification for appropriate valuation treatment."""

    PROFITABLE_MATURE = "profitable_mature"  # 3+ years, positive EBITDA, stable
    GROWTH_STAGE = "growth_stage"  # Negative EBITDA <10%, growing revenue
    PRE_REVENUE = "pre_revenue"  # No/minimal revenue (<€100K)
    DISTRESSED = "distressed"  # Negative EBITDA >10%, declining
    LIMITED_HISTORY = "limited_history"  # <3 years data, otherwise healthy


class NegativeEbitdaStrategy(Enum):
    """Strategy for handling negative EBITDA scenarios."""

    NONE = "none"  # Positive EBITDA - no special handling
    REVENUE_MULTIPLES = "revenue_multiples"  # Marginally negative, use revenue
    HIGH_RISK_VALUATION = "high_risk"  # Significant negative, wide ranges
    NOT_DETERMINABLE = "not_determinable"  # Structurally unprofitable


def detect_scenario(request: ValuationRequestProtocol) -> BusinessScenario:
    """
    Detect business scenario to customize report content.

    Args:
        request: ValuationRequest containing financial data

    Returns:
        BusinessScenario enum value
    """

    # Calculate years of data
    years_of_data = len(request.historical_years_data) if request.historical_years_data else 0
    if request.current_year_data:
        years_of_data += 1

    # Get current year metrics
    current_data = request.current_year_data
    if not current_data:
        logger.warning("No current year data available for scenario detection")
        return BusinessScenario.LIMITED_HISTORY

    revenue_decimal = to_decimal(current_data.revenue or 0)
    ebitda_decimal = to_decimal(current_data.ebitda or 0)

    if revenue_decimal > Decimal("0"):
        ebitda_margin_decimal = ebitda_decimal / revenue_decimal
        ebitda_margin = from_decimal(ebitda_margin_decimal)
    else:
        ebitda_margin = -Decimal("1.0")

    revenue = from_decimal(revenue_decimal)
    ebitda = from_decimal(ebitda_decimal)

    # Calculate revenue growth if possible
    revenue_growth = None
    if request.historical_years_data and len(request.historical_years_data) > 0:
        oldest_year = oldest_historical_year(request.historical_years_data)
        oldest_revenue_decimal = to_decimal(getattr(oldest_year, "revenue", 0) or 0)
        if oldest_revenue_decimal > Decimal("0"):
            years_span = years_of_data - 1
            if years_span > 0:
                # Decimal does not support fractional exponents; use float for
                # exponentiation, then convert back to Decimal for comparisons.
                revenue_ratio = float(revenue_decimal / oldest_revenue_decimal)
                growth_calc = revenue_ratio ** (1 / years_span) - 1
                revenue_growth = Decimal(str(growth_calc))

    # Scenario detection logic

    # Pre-revenue: Minimal revenue
    if revenue < 100_000:  # €100K threshold
        logger.info(f"Scenario detected: PRE_REVENUE (revenue: \u20AC{revenue:,.0f})")
        return BusinessScenario.PRE_REVENUE

    # Limited history: <3 years
    if years_of_data < 3:
        logger.info(f"Scenario detected: LIMITED_HISTORY ({years_of_data} years)")
        return BusinessScenario.LIMITED_HISTORY

    # Distressed: Significant losses AND declining revenue
    if ebitda_margin < Decimal("-0.10"):
        if revenue_growth is not None and revenue_growth < Decimal("-0.05"):  # Declining >5%
            logger.info(
                f"Scenario detected: DISTRESSED (EBITDA margin: {ebitda_margin:.1%}, growth: {revenue_growth:.1%})"
            )
            return BusinessScenario.DISTRESSED
        else:
            # Losses but not declining - growth stage
            logger.info(f"Scenario detected: GROWTH_STAGE (EBITDA margin: {ebitda_margin:.1%})")
            return BusinessScenario.GROWTH_STAGE

    # Growth stage: Marginally negative but growing
    if ebitda_margin < Decimal("0"):
        logger.info(f"Scenario detected: GROWTH_STAGE (EBITDA margin: {ebitda_margin:.1%})")
        return BusinessScenario.GROWTH_STAGE

    # Profitable mature: Default for 3+ years with positive EBITDA
    logger.info(f"Scenario detected: PROFITABLE_MATURE (EBITDA margin: {ebitda_margin:.1%})")
    return BusinessScenario.PROFITABLE_MATURE


def determine_negative_ebitda_strategy(
    ebitda_margin: Decimal, revenue_growth_cagr: Optional[Decimal] = None, years_of_losses: int = 0
) -> NegativeEbitdaStrategy:
    """
    Determine strategy for handling negative EBITDA.

    Professional Guidance:
    - Marginally negative (<10%): Revenue multiples (Damodaran, 2017)
    - Significantly negative (10-20%): High risk with wide ranges
    - Severe losses (>20%) or sustained: Going concern uncertainty

    Args:
        ebitda_margin: Current EBITDA margin (negative if losses)
        revenue_growth_cagr: Revenue growth rate (optional)
        years_of_losses: Number of consecutive years with losses

    Returns:
        NegativeEbitdaStrategy enum value
    """

    # Positive EBITDA - no special handling
    if ebitda_margin >= 0:
        return NegativeEbitdaStrategy.NONE

    # Severe losses (>20% negative margin) - not determinable
    if ebitda_margin < -0.20:
        logger.warning(f"Severe negative EBITDA margin: {ebitda_margin:.1%} - NOT_DETERMINABLE")
        return NegativeEbitdaStrategy.NOT_DETERMINABLE

    # Sustained losses (3+ years) with declining revenue - not determinable
    if years_of_losses >= 3 and revenue_growth_cagr is not None and revenue_growth_cagr < -0.05:
        logger.warning(f"Sustained losses with declining revenue - NOT_DETERMINABLE")
        return NegativeEbitdaStrategy.NOT_DETERMINABLE

    # Significant losses (10-20% negative margin) - high risk
    if ebitda_margin < -0.10:
        logger.info(f"Significant negative EBITDA margin: {ebitda_margin:.1%} - HIGH_RISK")
        return NegativeEbitdaStrategy.HIGH_RISK_VALUATION

    # Marginally negative (0-10% negative margin) - use revenue multiples
    logger.info(f"Marginally negative EBITDA margin: {ebitda_margin:.1%} - REVENUE_MULTIPLES")
    return NegativeEbitdaStrategy.REVENUE_MULTIPLES


def calculate_years_of_losses(request: Union["ValuationRequest", ValuationRequestProtocol]) -> int:
    """
    Calculate number of consecutive years with negative EBITDA.

    Args:
        request: ValuationRequest containing financial data

    Returns:
        Number of consecutive years with losses (starting from most recent)
    """

    years_of_losses = 0

    # Check current year
    if request.current_year_data:
        ebitda = request.current_year_data.ebitda or 0
        if ebitda < 0:
            years_of_losses += 1
        else:
            return 0  # No consecutive losses if current year is profitable

    # Check historical years (most recent first)
    if request.historical_years_data:
        # Reverse to get most recent first
        for year_data in reversed(request.historical_years_data):
            ebitda = year_data.ebitda or 0
            if ebitda < 0:
                years_of_losses += 1
            else:
                break  # Stop at first profitable year

    return years_of_losses


def get_scenario_description(scenario: BusinessScenario) -> str:
    """
    Get human-readable description of business scenario.

    Args:
        scenario: BusinessScenario enum value

    Returns:
        Description string
    """

    descriptions = {
        BusinessScenario.PROFITABLE_MATURE: (
            "Profitable, mature company with 3+ years of operating history and positive EBITDA. "
            "Standard valuation methods apply with full confidence."
        ),
        BusinessScenario.GROWTH_STAGE: (
            "Growth-stage company with negative EBITDA margins while investing in scale. "
            "Revenue multiples are more appropriate than EBITDA multiples. This is typical "
            "for companies prioritizing growth over near-term profitability."
        ),
        BusinessScenario.PRE_REVENUE: (
            "Pre-revenue or early-stage company with minimal revenue. Valuation relies heavily "
            "on comparable transactions, intellectual property value, and management projections. "
            "High uncertainty and wide valuation ranges apply."
        ),
        BusinessScenario.DISTRESSED: (
            "Distressed company with significant operating losses and declining revenue. "
            "Going concern uncertainty exists. Traditional valuation methods may not be appropriate. "
            "Asset-based or liquidation value may be more relevant."
        ),
        BusinessScenario.LIMITED_HISTORY: (
            "Limited operating history (<3 years) constrains trend analysis and normalization. "
            "Valuation relies more heavily on industry benchmarks and comparable companies. "
            "Wider valuation ranges apply to reflect increased uncertainty."
        ),
    }

    return descriptions.get(scenario, "Business scenario not classified")
