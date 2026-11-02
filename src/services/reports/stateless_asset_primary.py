"""Asset-primary routing helpers for stateless valuation calculation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from src.config.valuation_constants import get_asking_price_markup
from src.domain.asset_based_support import (
    calculate_adjusted_nav_payload,
    has_sufficient_asset_inputs,
)
from src.services.reports.stateless_bridge_adjustments import resolve_stateless_bridge_adjustments
from src.services.reports.stateless_calculation_helpers import score_to_level
from src.utils.decimal_helpers import safe_decimal_or_zero, safe_float


@dataclass(frozen=True)
class AssetPrimaryMethodologyState:
    asset_primary_payload: dict[str, object] | None
    methodology_used: str
    methodology_selection_reason: str
    dcf_weight: Decimal
    multiples_weight: Decimal
    dcf_exclusion_reason: str | None
    dcf_results: object | None


@dataclass(frozen=True)
class AssetPrimaryHeadlineState:
    equity_value_low: Decimal
    equity_value_mid: Decimal
    equity_value_high: Decimal
    enterprise_value_mid: Decimal
    confidence_score: int
    confidence_level: str
    recommended_asking: Decimal
    value_drivers: list[str]
    risk_factors: object
    data_quality: dict[str, object]
    bridge_adjustment_data: dict[str, object]
    bridge_adjustment_flags: list[object]


def resolve_asset_primary_methodology(
    *,
    request,
    normalized_business_model: str,
    balance_sheet,
    ownership_multiplier: Decimal,
    revenue: Decimal,
    methodology_used: str,
    methodology_selection_reason: str,
    dcf_weight: Decimal,
    multiples_weight: Decimal,
    dcf_exclusion_reason: str | None,
    dcf_results,
) -> AssetPrimaryMethodologyState:
    """Resolve whether the stateless path should switch to adjusted NAV."""
    asset_primary_payload = None
    operating_ebitda = safe_decimal_or_zero(request.current_year.ebitda)
    should_use_asset_primary = methodology_used == "ASSET_BASED" or (
        revenue <= 0 and operating_ebitda <= 0 and has_sufficient_asset_inputs(balance_sheet)
    )
    if should_use_asset_primary:
        asset_primary_payload = calculate_adjusted_nav_payload(
            company_name=request.company_name,
            industry=request.industry,
            business_model=normalized_business_model,
            founding_year=request.founding_year,
            reporting_year=request.current_year.year,
            revenue=request.current_year.revenue,
            ebitda=request.current_year.ebitda,
            ownership_multiplier=ownership_multiplier,
            country_code=request.country_code,
            balance_sheet=balance_sheet,
            business_context=getattr(request, "business_context", None),
        )
        if asset_primary_payload["available"]:
            methodology_used = "ASSET_BASED"
            methodology_selection_reason = (
                "Using Asset-Based methodology because both turnover and operating earnings are "
                "non-positive, or an explicit asset-based valuation was requested, and sufficient "
                "balance-sheet data is available."
            )
            dcf_weight = Decimal("0")
            multiples_weight = Decimal("0")
            dcf_exclusion_reason = (
                "Asset-based fallback selected for a zero-revenue, balance-sheet-led entity."
            )
            dcf_results = None
        elif str(request.methodology).upper() == "ASSET_BASED" or methodology_used == "ASSET_BASED":
            methodology_used = "MULTIPLES"
            methodology_selection_reason = (
                "Asset-Based methodology was selected, but balance-sheet data was insufficient. "
                "Falling back to standard valuation routing."
            )
            dcf_weight = Decimal("0")
            multiples_weight = Decimal("1")
            dcf_exclusion_reason = None
            dcf_results = None

    return AssetPrimaryMethodologyState(
        asset_primary_payload=asset_primary_payload,
        methodology_used=methodology_used,
        methodology_selection_reason=methodology_selection_reason,
        dcf_weight=dcf_weight,
        multiples_weight=multiples_weight,
        dcf_exclusion_reason=dcf_exclusion_reason,
        dcf_results=dcf_results,
    )


def confidence_score_from_asset_payload(asset_payload: dict[str, object]) -> int:
    confidence_level = str(asset_payload.get("confidence_level") or "MEDIUM").upper()
    if confidence_level == "HIGH":
        return 90
    if confidence_level == "LOW":
        return 60
    return 75


def build_asset_primary_headline_state(
    *,
    request,
    asset_primary_payload: dict[str, object],
    real_estate_surplus: Decimal,
    calibration,
    primary_business_type_id: object,
    business_type_mix: object,
    business_type_weights: object,
    business_type_mix_policy: object,
    benchmark_contract: object,
    benchmark_contract_resolved: bool,
    benchmark_provenance: object,
) -> AssetPrimaryHeadlineState:
    """Assemble the asset-primary headline without leaking branch policy upstream."""
    equity_value_low = safe_decimal_or_zero(asset_primary_payload["equity_value_low"])
    equity_value_mid = safe_decimal_or_zero(asset_primary_payload["equity_value"])
    equity_value_high = safe_decimal_or_zero(asset_primary_payload["equity_value_high"])
    enterprise_value_mid = safe_decimal_or_zero(asset_primary_payload["enterprise_value"])
    ownership_percentage = (
        request.shares_for_sale
        if getattr(request, "shares_for_sale", None) is not None
        else Decimal("100")
    )
    ownership_multiplier = safe_decimal_or_zero(ownership_percentage) / Decimal("100")
    if real_estate_surplus != Decimal("0"):
        stake_surplus = real_estate_surplus * ownership_multiplier
        equity_value_low += stake_surplus
        equity_value_mid += stake_surplus
        equity_value_high += stake_surplus

    bridge_ledger = resolve_stateless_bridge_adjustments(request)
    stake_bridge_impact = bridge_ledger.total * ownership_multiplier
    equity_value_low = max(Decimal("0"), equity_value_low + stake_bridge_impact)
    equity_value_mid = max(Decimal("0"), equity_value_mid + stake_bridge_impact)
    equity_value_high = max(Decimal("0"), equity_value_high + stake_bridge_impact)
    bridge_adjustment_data = {
        **bridge_ledger.to_payload(),
        "ownership_percentage": ownership_percentage,
        "stake_net_impact": stake_bridge_impact,
    }

    confidence_score = confidence_score_from_asset_payload(asset_primary_payload)
    confidence_level = score_to_level(confidence_score)
    asking_markup = get_asking_price_markup(
        confidence_level.lower(),
        advisor_override_pct=getattr(request, "asking_price_buffer_pct", None),
    )

    return AssetPrimaryHeadlineState(
        equity_value_low=equity_value_low,
        equity_value_mid=equity_value_mid,
        equity_value_high=equity_value_high,
        enterprise_value_mid=enterprise_value_mid,
        confidence_score=confidence_score,
        confidence_level=confidence_level,
        recommended_asking=(equity_value_mid * asking_markup).quantize(Decimal("0.01")),
        value_drivers=[
            "Balance sheet is the primary value anchor",
            "Adjusted net asset value replaces revenue-based methods",
        ],
        risk_factors=asset_primary_payload.get("warnings")
        or ["Revenue-based multiples are not applicable for zero-turnover entities"],
        data_quality={
            "multiples_source": "not_applicable",
            "is_delphi_benchmark_sourced": False,
            "enrichment_complete": True,
            "fallback_used": False,
            "fallback_methodology": "ASSET_BASED",
            "business_type_id": calibration.business_type_id,
            "primary_business_type_id": primary_business_type_id,
            "business_type_mix": business_type_mix,
            "business_type_weights": business_type_weights,
            "business_type_mix_policy": business_type_mix_policy,
            "category_id": calibration.category_id,
            "data_quality_score": (
                safe_float(calibration.calibration_quality_score)
                if calibration.calibration_quality_score is not None
                else None
            ),
            "benchmark_contract": benchmark_contract if benchmark_contract_resolved else None,
            "benchmark_provenance": benchmark_provenance,
        },
        bridge_adjustment_data=bridge_adjustment_data,
        bridge_adjustment_flags=list(bridge_ledger.triage_flags),
    )
