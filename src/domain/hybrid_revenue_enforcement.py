"""Revenue-tier guardrails for hybrid DCF/multiples weights."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from src.domain.historical_years import oldest_historical_year
from src.domain.hybrid_types import (
    DCF_WEIGHT_CAP_LARGE,
    DCF_WEIGHT_CAP_MICRO,
    DCF_WEIGHT_CAP_MID,
    DCF_WEIGHT_CAP_SMALL,
    REVENUE_THRESHOLD_MICRO,
    REVENUE_THRESHOLD_MID,
    REVENUE_THRESHOLD_SMALL,
)
from src.domain.interfaces.request_protocol import ValuationRequestProtocol
from src.utils.decimal_helpers import to_decimal


@dataclass(frozen=True)
class RevenueEnforcementDecision:
    dcf_weight: Decimal
    multiples_weight: Decimal
    reason: Optional[str]
    log_message: Optional[str] = None
    is_high_growth: bool = False


def is_high_growth_revenue_profile(request: ValuationRequestProtocol) -> bool:
    historical = [
        year
        for year in (getattr(request, "historical_years_data", []) or [])
        if not getattr(year, "is_forecast", False)
    ]
    if not historical:
        return False

    oldest_year = oldest_historical_year(historical)
    oldest_revenue = to_decimal(getattr(oldest_year, "revenue", 0) or 0)
    current_revenue = to_decimal(request.current_year_data.revenue or 0)
    if oldest_revenue <= 0 or current_revenue <= 0:
        return False

    years = len(historical) + 1
    cagr = float(current_revenue / oldest_revenue) ** (1.0 / years) - 1.0
    return cagr > 0.20


def build_revenue_enforcement_decision(
    revenue: Decimal,
    dcf_weight: Decimal,
    multiples_weight: Decimal,
    is_high_growth: bool,
) -> RevenueEnforcementDecision:
    revenue_threshold_micro = to_decimal(REVENUE_THRESHOLD_MICRO)
    revenue_threshold_small = to_decimal(REVENUE_THRESHOLD_SMALL)
    revenue_threshold_mid = to_decimal(REVENUE_THRESHOLD_MID)

    if revenue < revenue_threshold_micro:
        return _micro_revenue_decision(dcf_weight, multiples_weight, is_high_growth)
    if revenue < revenue_threshold_small:
        return _small_revenue_decision(dcf_weight, multiples_weight, is_high_growth)
    if revenue < revenue_threshold_mid:
        return _cap_decision(
            dcf_weight=dcf_weight,
            multiples_weight=multiples_weight,
            cap=to_decimal(DCF_WEIGHT_CAP_MID),
            reason="white_paper_guardrail_€5-10M_dcf_capped_at_40%",
            log_message="✅ White Paper Guardrail: Revenue €5-10M → DCF capped at 40%",
        )
    return _cap_decision(
        dcf_weight=dcf_weight,
        multiples_weight=multiples_weight,
        cap=to_decimal(DCF_WEIGHT_CAP_LARGE),
        reason="white_paper_guardrail_>€10M_dcf_soft_cap_at_60%",
        log_message="✅ White Paper Guardrail: Revenue >€10M → DCF soft capped at 60%",
    )


def _micro_revenue_decision(
    dcf_weight: Decimal, multiples_weight: Decimal, is_high_growth: bool
) -> RevenueEnforcementDecision:
    if is_high_growth:
        return _cap_decision(
            dcf_weight=dcf_weight,
            multiples_weight=multiples_weight,
            cap=to_decimal(DCF_WEIGHT_CAP_SMALL),
            reason="white_paper_guardrail_<€2.5M_high_growth_dcf_capped_at_10%",
            log_message=(
                "✅ White Paper Guardrail (growth-relaxed): Revenue <€2.5M + high growth "
                "→ DCF capped at 10%"
            ),
            is_high_growth=True,
        )

    return _forced_decision(
        cap=to_decimal(DCF_WEIGHT_CAP_MICRO),
        reason="white_paper_guardrail_<€2.5M_dcf_forced_to_0%",
        log_message="✅ White Paper Guardrail: Revenue <€2.5M → DCF forced to 0%",
    )


def _small_revenue_decision(
    dcf_weight: Decimal, multiples_weight: Decimal, is_high_growth: bool
) -> RevenueEnforcementDecision:
    if is_high_growth:
        return _cap_decision(
            dcf_weight=dcf_weight,
            multiples_weight=multiples_weight,
            cap=to_decimal(DCF_WEIGHT_CAP_MID),
            reason="white_paper_guardrail_€2.5-5M_high_growth_dcf_capped_at_40%",
            log_message=(
                "✅ White Paper Guardrail (growth-relaxed): Revenue €2.5-5M + high growth "
                "→ DCF capped at 40%"
            ),
            is_high_growth=True,
        )

    return _cap_decision(
        dcf_weight=dcf_weight,
        multiples_weight=multiples_weight,
        cap=to_decimal(DCF_WEIGHT_CAP_SMALL),
        reason="white_paper_guardrail_€2.5-5M_dcf_capped_at_10%",
        log_message="✅ White Paper Guardrail: Revenue €2.5-5M → DCF capped at 10%",
    )


def _forced_decision(
    cap: Decimal,
    reason: str,
    log_message: str,
) -> RevenueEnforcementDecision:
    return RevenueEnforcementDecision(
        dcf_weight=cap,
        multiples_weight=Decimal("1.0") - cap,
        reason=reason,
        log_message=log_message,
    )


def _cap_decision(
    *,
    dcf_weight: Decimal,
    multiples_weight: Decimal,
    cap: Decimal,
    reason: str,
    log_message: str,
    is_high_growth: bool = False,
) -> RevenueEnforcementDecision:
    if dcf_weight <= cap:
        return RevenueEnforcementDecision(
            dcf_weight=dcf_weight,
            multiples_weight=multiples_weight,
            reason=None,
            is_high_growth=is_high_growth,
        )

    return RevenueEnforcementDecision(
        dcf_weight=cap,
        multiples_weight=Decimal("1.0") - cap,
        reason=reason,
        log_message=log_message,
        is_high_growth=is_high_growth,
    )
