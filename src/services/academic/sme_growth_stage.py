"""
SME growth-stage classification.

Keeps startup/growth/mature decisions isolated from the multiple selector so
calibration orchestration can stay focused on selecting and adjusting multiples.
"""

from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from src.utils.logging import get_logger

logger = get_logger(__name__)


def has_multi_year_profitable_history(
    historical_data: Optional[List[Dict[str, object]]],
) -> bool:
    """Return true when historical data shows at least two positive EBITDA years."""
    if not historical_data or len(historical_data) < 2:
        return False

    positive_years = 0
    for entry in historical_data:
        try:
            if not isinstance(entry, dict):
                continue

            ebitda_raw = entry.get("ebitda")
            if ebitda_raw is None:
                ebitda_raw = entry.get("normalized_ebitda")
            if ebitda_raw is None:
                continue

            if Decimal(str(ebitda_raw)) > Decimal("0"):
                positive_years += 1
        except (TypeError, ValueError, ArithmeticError):
            continue

    return positive_years >= 2


def determine_growth_stage(
    founded_year: Optional[int] = None,
    current_year: Optional[int] = None,
    historical_data: Optional[List[Dict[str, object]]] = None,
    revenue: Optional[Decimal] = None,
) -> Tuple[str, Decimal]:
    """
    Determine growth stage (startup/growth/mature) from age and financial history.

    Returns ``(growth_stage, adjustment_factor)`` where startup-stage companies
    receive a risk discount and growth/mature companies do not.
    """
    from src.utils.fiscal_year import get_current_filing_year

    if current_year is None:
        current_year = get_current_filing_year()

    if founded_year is None:
        logger.debug("No founded_year provided, assuming mature stage")
        return "mature", Decimal("1.0")

    company_age = current_year - founded_year

    if company_age < 3:
        if has_multi_year_profitable_history(historical_data):
            logger.debug(
                "Determined growth stage: growth (overrode age-based startup tag)",
                company_age=company_age,
                historical_data_years=len(historical_data) if historical_data else 0,
                note=(
                    "founded_year suggests <3 years old but historical data shows "
                    "at least two profitable EBITDA years; treating as growth-stage "
                    "SME, not a startup."
                ),
            )
            return "growth", Decimal("1.0")

        risk_factor = Decimal("1.0") - (
            Decimal(str(3 - company_age)) / Decimal("3.0") * Decimal("0.05")
        )
        adjustment_factor = max(Decimal("0.90"), min(Decimal("0.95"), risk_factor))
        logger.debug(
            "Determined growth stage: startup",
            company_age=company_age,
            adjustment_factor=float(adjustment_factor),
        )
        return "startup", adjustment_factor

    if company_age <= 10:
        if historical_data and len(historical_data) >= 2 and revenue:
            historical_revenues = sorted(
                [
                    Decimal(str(h.get("revenue", 0)))
                    for h in historical_data
                    if h.get("revenue")
                ],
                reverse=True,
            )

            if len(historical_revenues) >= 2:
                growth_rates = []
                for index in range(len(historical_revenues) - 1):
                    previous_revenue = historical_revenues[index + 1]
                    if previous_revenue > Decimal("0"):
                        growth_rate = (
                            historical_revenues[index] - previous_revenue
                        ) / previous_revenue
                        growth_rates.append(growth_rate)

                if growth_rates:
                    avg_growth = sum(growth_rates) / Decimal(str(len(growth_rates)))
                    variance = sum((growth - avg_growth) ** 2 for growth in growth_rates) / Decimal(
                        str(len(growth_rates))
                    )

                    import math

                    volatility = Decimal(str(math.sqrt(float(variance))))

                    if volatility > Decimal("0.5"):
                        adjustment_factor = Decimal("0.92")
                        logger.debug(
                            "Determined growth stage: startup (high volatility)",
                            company_age=company_age,
                            volatility=float(volatility),
                            adjustment_factor=float(adjustment_factor),
                        )
                        return "startup", adjustment_factor

        logger.debug("Determined growth stage: growth", company_age=company_age)
        return "growth", Decimal("1.0")

    logger.info("Determined growth stage: mature", company_age=company_age)
    return "mature", Decimal("1.0")
