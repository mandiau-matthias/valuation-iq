"""
DCF eligibility rule helpers for Step 0.

The public determiner owns orchestration and logging context; this module owns
the pure policy decisions so threshold branches do not become another god
method.
"""

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Optional

from src.api.routes.valuation.shared.historical_years import oldest_historical_year
from src.utils.logging import get_logger
from src.utils.sole_trader_detector import SoleTraderDetector

logger = get_logger(__name__)


@dataclass(frozen=True)
class RevenueThresholdDecision:
    """Resolved DCF revenue threshold and audit metadata."""

    threshold: int = 5_000_000
    source: str = "standard"
    metadata: dict[str, object] = field(default_factory=dict)


def current_revenue(request: object) -> object:
    """Return the current-year revenue used by DCF eligibility checks."""
    if hasattr(request, "current_year_data") and request.current_year_data:
        return getattr(request.current_year_data, "revenue", 0) or 0
    return 0


def historical_actual_years(request: object) -> list[object]:
    """Return historical years, excluding forecasts."""
    return [
        year
        for year in (getattr(request, "historical_years_data", []) or [])
        if getattr(year, "is_forecast", False) is not True
    ]


def is_sole_trader_request(request: object) -> bool:
    """Detect whether DCF should be excluded because the business is a sole trader."""
    return SoleTraderDetector.detect(
        business_structure=getattr(request, "business_type", None),
        business_type=getattr(request, "business_type", None),
        number_of_owners=getattr(request, "number_of_owners", None),
        number_of_employees=getattr(request, "number_of_employees", None),
        is_sole_trader=getattr(request, "is_sole_trader", None),
        business_context=getattr(request, "business_context", None),
    )


def quality_threshold_failure_reason(quality_score: int) -> Optional[str]:
    """Return a DCF quality failure reason, if the score is too low."""
    if quality_score >= 60:
        return None
    return f"Data quality score {quality_score}% below 60% threshold"


def historical_data_failure_reason(*, historical_count: int, quality_score: int) -> Optional[str]:
    """Return a historical-data failure reason, if DCF history rules fail."""
    if historical_count < 2:
        return f"Historical data {historical_count} years below 2 years minimum"
    if historical_count == 2 and quality_score < 70:
        return f"With only 2 years of data, quality score {quality_score}% below 70% threshold"
    return None


def revenue_failure_reason(revenue: object, revenue_threshold: int) -> str:
    """Return the standard revenue-threshold exclusion reason."""
    return (
        f"Revenue €{revenue:,.0f} below €{revenue_threshold/1_000_000:.0f}M threshold "
        "(DCF not reliable for small companies, Multiples more accurate per academic "
        "valuation standards - Koller, Goedhart & Wessels 2020, Trugman 2017)"
    )


def resolve_revenue_threshold(
    *,
    request: object,
    business_category_value: str,
    revenue: object,
    historical_years: list[object],
    sub_calculations: Optional[dict[str, dict[str, object]]],
    step_number: int,
) -> RevenueThresholdDecision:
    """Resolve the DCF revenue threshold for the current business context."""
    if business_category_value == "saas_software":
        return _resolve_saas_revenue_threshold(
            revenue=revenue,
            historical_years=historical_years,
            sub_calculations=sub_calculations,
            step_number=step_number,
        )

    if revenue < 5_000_000:
        return _resolve_small_company_revenue_threshold(
            request=request,
            revenue=revenue,
            historical_years=historical_years,
            business_category_value=business_category_value,
            step_number=step_number,
        )

    return RevenueThresholdDecision()


def eligibility_criteria_summary(
    *,
    quality_score: int,
    revenue: object,
    revenue_threshold: int,
    dcf_revenue_bypass: bool,
    historical_count: int,
) -> dict[str, object]:
    """Build the final positive eligibility criteria summary."""
    return {
        "not_sole_trader": True,
        "quality_score_met": quality_score >= 60,
        "revenue_threshold_met": revenue >= revenue_threshold or dcf_revenue_bypass,
        "historical_data_met": historical_count >= 2,
        "enhanced_quality_met": historical_count >= 3
        or (historical_count == 2 and quality_score >= 70),
    }


def _resolve_saas_revenue_threshold(
    *,
    revenue: object,
    historical_years: list[object],
    sub_calculations: Optional[dict[str, dict[str, object]]],
    step_number: int,
) -> RevenueThresholdDecision:
    saas_analysis = (
        sub_calculations.get("saas_analysis") if isinstance(sub_calculations, dict) else None
    )
    saas_dcf_context = (
        saas_analysis.get("dcf_context")
        if isinstance(saas_analysis, dict) and isinstance(saas_analysis.get("dcf_context"), dict)
        else {}
    )
    threshold_from_subcalc = saas_dcf_context.get("revenue_threshold")
    if threshold_from_subcalc is not None:
        threshold = int(threshold_from_subcalc)
        logger.info(
            "✅ SaaS Step 0 sub-calculation supplied DCF revenue threshold",
            extra={
                "step_number": step_number,
                "threshold": threshold,
                "revenue": revenue,
                "signals": (
                    saas_analysis.get("signals") if isinstance(saas_analysis, dict) else None
                ),
            },
        )
        return RevenueThresholdDecision(
            threshold=threshold,
            source="saas_subcalculation",
            metadata={
                "signals": saas_analysis.get("signals") if isinstance(saas_analysis, dict) else None
            },
        )

    if len(historical_years) < 2:
        return RevenueThresholdDecision()

    return _resolve_saas_growth_threshold(
        revenue=revenue,
        historical_years=historical_years,
        step_number=step_number,
    )


def _resolve_saas_growth_threshold(
    *, revenue: object, historical_years: list[object], step_number: int
) -> RevenueThresholdDecision:
    oldest_year = oldest_historical_year(historical_years)
    first_revenue = getattr(oldest_year, "revenue", None) if oldest_year is not None else None
    growth_rate = (
        ((revenue / first_revenue - 1) * 100) if first_revenue and first_revenue > 0 else 0
    )

    logger.debug(
        "🔍 Checking SaaS growth rate",
        extra={
            "step_number": step_number,
            "first_revenue": first_revenue,
            "current_revenue": revenue,
            "growth_rate_pct": growth_rate,
            "growth_threshold": 30,
        },
    )

    growth_multiplier = Decimal("1.3")
    if first_revenue and first_revenue > 0 and revenue > first_revenue * growth_multiplier:
        threshold = 1_000_000
        logger.info(
            "✅ High-growth SaaS detected: Lower DCF revenue threshold",
            extra={
                "step_number": step_number,
                "revenue": revenue,
                "threshold": threshold,
                "growth_rate_pct": growth_rate,
                "formula": (
                    f"Revenue {revenue} > First Revenue {first_revenue} × "
                    f"1.3 = {first_revenue * growth_multiplier}"
                ),
            },
        )
        return RevenueThresholdDecision(
            threshold=threshold,
            source="saas_high_growth",
            metadata={
                "first_revenue": first_revenue,
                "growth_rate_pct": growth_rate,
                "growth_multiplier": growth_multiplier,
            },
        )

    return RevenueThresholdDecision()


def _resolve_small_company_revenue_threshold(
    *,
    request: object,
    revenue: object,
    historical_years: list[object],
    business_category_value: str,
    step_number: int,
) -> RevenueThresholdDecision:
    is_high_growth = _is_high_growth_for_small_company(
        historical_years=historical_years,
        revenue=revenue,
    )
    recurring_fraction = _recurring_revenue_fraction(request)
    recurring_threshold = Decimal("0.70") if revenue < 1_000_000 else Decimal("0.50")
    is_recurring_model = recurring_fraction > recurring_threshold
    if revenue < 100_000 or not (is_high_growth or is_recurring_model):
        return RevenueThresholdDecision()

    threshold = 100_000 if revenue < 1_000_000 else 1_000_000
    logger.info(
        "✅ High-growth/recurring SME detected: Lower DCF revenue threshold",
        extra={
            "step_number": step_number,
            "revenue": revenue,
            "threshold": threshold,
            "business_category": business_category_value,
            "is_high_growth": is_high_growth,
            "recurring_revenue_fraction": recurring_fraction,
            "recurring_threshold": recurring_threshold,
        },
    )
    return RevenueThresholdDecision(
        threshold=threshold,
        source="sme_growth_or_recurring",
        metadata={
            "is_high_growth": is_high_growth,
            "recurring_revenue_fraction": recurring_fraction,
            "recurring_threshold": recurring_threshold,
        },
    )


def _is_high_growth_for_small_company(
    *,
    historical_years: list[object],
    revenue: object,
) -> bool:
    oldest_year = oldest_historical_year(historical_years)
    if oldest_year is None:
        return False
    oldest_revenue = getattr(oldest_year, "revenue", 0) or 0
    try:
        oldest_revenue_decimal = Decimal(str(oldest_revenue))
        revenue_decimal = Decimal(str(revenue))
    except (InvalidOperation, TypeError, ValueError):
        return False
    if oldest_revenue_decimal <= 0 or revenue_decimal <= 0:
        return False
    if revenue_decimal < Decimal("1000000"):
        return revenue_decimal > oldest_revenue_decimal * Decimal("1.5")
    years = len(historical_years) + 1
    ratio = float(revenue_decimal / oldest_revenue_decimal)
    cagr = ratio ** (1.0 / years) - 1.0
    return cagr > 0.20


def _recurring_revenue_fraction(request: object) -> Decimal:
    recurring = getattr(request, "recurring_revenue_percentage", None)
    if recurring is None:
        recurring = getattr(request, "rev_recurring_pct", None)
    if recurring is None:
        return Decimal("0")
    try:
        recurring_decimal = Decimal(str(recurring))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")
    if recurring_decimal > 1:
        recurring_decimal = recurring_decimal / Decimal("100")
    return recurring_decimal
