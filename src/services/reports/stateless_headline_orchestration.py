"""Headline valuation phase for the stateless calculation route."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from src.api.schemas.stateless_api import CalculateRequest, TriageFlag
from src.config.valuation_constants import get_asking_price_markup
from src.domain.financial_arithmetic import FinancialNumber, decimal_number
from src.domain.multiples.strength_factor_discount_evidence import (
    strength_factor_discount_adjustments_from_business_context,
)
from src.services.reports.benchmark_range_disclosure import benchmark_range_disclosure
from src.services.reports.stateless_asset_primary import build_asset_primary_headline_state
from src.services.reports.stateless_benchmark_policy import resolve_multiples_source_policy
from src.services.reports.stateless_calculation_helpers import (
    calculate_confidence_score,
    calculate_country_adjustment,
    calculate_size_discount,
    identify_risk_factors,
    identify_value_drivers,
    score_to_level,
)
from src.services.reports.stateless_completion_accounts import completion_account_bridge
from src.services.reports.stateless_discount_stack import build_stateless_discount_stack
from src.services.reports.stateless_equity_adjustments import apply_stateless_equity_adjustments
from src.services.reports.stateless_input_context import StatelessInputContext
from src.services.reports.stateless_multiple_build_up import build_stateless_multiple_build_up_state
from src.services.reports.stateless_multiples_headline import (
    build_stateless_multiples_headline_inputs,
)
from src.services.reports.stateless_override_governance import resolve_effective_multiple_override
from src.utils.decimal_helpers import float_or_none, safe_decimal_or_zero, safe_float


class LoggerLike(Protocol):
    def info(self, msg: str, *args: object, **kwargs: object) -> object: ...

    def warning(self, msg: str, *args: object, **kwargs: object) -> object: ...


@dataclass(frozen=True)
class StatelessHeadlineComputation:
    equity_value_low: Decimal
    equity_value_mid: Decimal
    equity_value_high: Decimal
    enterprise_value_low: Decimal | None
    enterprise_value_mid: Decimal | None
    enterprise_value_high: Decimal | None
    confidence_score: int
    confidence_level: str
    recommended_asking: Decimal
    value_drivers: object
    risk_factors: object
    data_quality: dict[str, object]
    size_discount: float
    liquidity_discount: float
    owner_adjustment: float
    country_adjustment: float
    total_adjustment: Decimal
    base_enterprise_value: float
    adjusted_ev: float
    recommended_multiple: Decimal | None
    multiples_results: dict[str, object] | None
    multiple_build_up_obj: object | None
    earnings_basis_value: str | None
    earnings_basis_rationale_value: str | None
    ownership_percentage: Decimal
    ownership_multiplier: Decimal
    nwc_normalization_data: dict[str, object] | None
    bridge_adjustment_data: dict[str, object]


def build_stateless_headline_computation(
    *,
    request: CalculateRequest,
    input_context: StatelessInputContext,
    asset_primary_payload: dict[str, object] | None,
    real_estate_surplus: Decimal,
    benchmark_contract_resolved: bool,
    benchmark_provenance: dict[str, object],
    ev_ebitda_multiple: float,
    p25_multiple: float,
    p75_multiple: float,
    multiple_calibration_audit: dict[str, object] | None,
    business_type_multiple_override_audit: dict[str, object] | None,
    benchmark_contract: dict[str, object] | None,
    total_debt: float,
    cash: float,
    logger: LoggerLike,
) -> StatelessHeadlineComputation:
    if asset_primary_payload and asset_primary_payload["available"]:
        return _asset_primary_headline_computation(
            request=request,
            input_context=input_context,
            asset_primary_payload=asset_primary_payload,
            real_estate_surplus=real_estate_surplus,
            benchmark_contract=benchmark_contract,
            benchmark_contract_resolved=benchmark_contract_resolved,
            benchmark_provenance=benchmark_provenance,
        )

    return _multiples_headline_computation(
        request=request,
        input_context=input_context,
        real_estate_surplus=real_estate_surplus,
        benchmark_contract=benchmark_contract,
        benchmark_contract_resolved=benchmark_contract_resolved,
        benchmark_provenance=benchmark_provenance,
        ev_ebitda_multiple=ev_ebitda_multiple,
        p25_multiple=p25_multiple,
        p75_multiple=p75_multiple,
        multiple_calibration_audit=multiple_calibration_audit,
        business_type_multiple_override_audit=business_type_multiple_override_audit,
        total_debt=total_debt,
        cash=cash,
        logger=logger,
    )


def _asset_primary_headline_computation(
    *,
    request: CalculateRequest,
    input_context: StatelessInputContext,
    asset_primary_payload: dict[str, object],
    real_estate_surplus: Decimal,
    benchmark_contract: dict[str, object] | None,
    benchmark_contract_resolved: bool,
    benchmark_provenance: dict[str, object],
) -> StatelessHeadlineComputation:
    asset_headline = build_asset_primary_headline_state(
        request=request,
        asset_primary_payload=asset_primary_payload,
        real_estate_surplus=real_estate_surplus,
        calibration=input_context.calibration,
        primary_business_type_id=input_context.primary_business_type_id,
        business_type_mix=input_context.business_type_mix,
        business_type_weights=input_context.business_type_weights,
        business_type_mix_policy=input_context.business_type_mix_policy,
        benchmark_contract=benchmark_contract,
        benchmark_contract_resolved=benchmark_contract_resolved,
        benchmark_provenance=benchmark_provenance,
    )
    input_context.triage_flags.extend(asset_headline.bridge_adjustment_flags)
    return StatelessHeadlineComputation(
        equity_value_low=asset_headline.equity_value_low,
        equity_value_mid=asset_headline.equity_value_mid,
        equity_value_high=asset_headline.equity_value_high,
        # Adjusted NAV is a direct equity-premise method. The NAV engine's
        # ``enterprise_value`` compatibility field is the corrected net asset
        # value, not an independently reconciled EV. Publishing only that
        # midpoint created a malformed EV band and could imply a fictitious
        # debt/cash bridge. Preserve explicit non-applicability instead.
        enterprise_value_low=None,
        enterprise_value_mid=None,
        enterprise_value_high=None,
        confidence_score=asset_headline.confidence_score,
        confidence_level=asset_headline.confidence_level,
        recommended_asking=asset_headline.recommended_asking,
        value_drivers=asset_headline.value_drivers,
        risk_factors=asset_headline.risk_factors,
        data_quality=asset_headline.data_quality,
        size_discount=0.0,
        liquidity_discount=0.0,
        owner_adjustment=0.0,
        country_adjustment=0.0,
        total_adjustment=Decimal("0"),
        base_enterprise_value=0.0,
        adjusted_ev=0.0,
        recommended_multiple=None,
        multiples_results=None,
        multiple_build_up_obj=None,
        earnings_basis_value=None,
        earnings_basis_rationale_value=None,
        ownership_percentage=input_context.ownership_percentage,
        ownership_multiplier=input_context.ownership_multiplier,
        nwc_normalization_data=None,
        bridge_adjustment_data=asset_headline.bridge_adjustment_data,
    )


def _multiples_headline_computation(
    *,
    request: CalculateRequest,
    input_context: StatelessInputContext,
    real_estate_surplus: Decimal,
    benchmark_contract: dict[str, object] | None,
    benchmark_contract_resolved: bool,
    benchmark_provenance: dict[str, object],
    ev_ebitda_multiple: float,
    p25_multiple: float,
    p75_multiple: float,
    multiple_calibration_audit: dict[str, object] | None,
    business_type_multiple_override_audit: dict[str, object] | None,
    total_debt: float,
    cash: float,
    logger: LoggerLike,
) -> StatelessHeadlineComputation:
    calibration = input_context.calibration
    size_discount = calculate_size_discount(input_context.revenue, calibration)
    liquidity_discount = (
        float(calibration.sme_liquidity_discount)
        if calibration.sme_liquidity_discount is not None
        else 0.15
    )
    owner_adjustment = 0.0
    country_adjustment = calculate_country_adjustment(request.country_code)
    discount_build_up = _discount_build_up(
        request=request,
        revenue=input_context.revenue,
        team_size=getattr(request, "number_of_employees", None),
        size_discount=size_discount,
        liquidity_discount=liquidity_discount,
        country_adjustment=country_adjustment,
        triage_flags=input_context.triage_flags,
    )
    adjustment_factor = safe_decimal_or_zero(discount_build_up.get("total_adjustment_factor"))
    total_adjustment = Decimal("1") - adjustment_factor

    headline_inputs = build_stateless_multiples_headline_inputs(
        request=request,
        calibration=calibration,
        benchmark_contract=benchmark_contract,
        benchmark_contract_resolved=benchmark_contract_resolved,
        revenue=request.current_year.revenue,
        ebitda=decimal_number(input_context.earnings_basis["normalized_ebitda"]),
        ev_ebitda_multiple=ev_ebitda_multiple,
        p25_multiple=p25_multiple,
        p75_multiple=p75_multiple,
    )
    input_context.triage_flags.extend(headline_inputs.triage_flags)
    effective_override_state = _effective_override_state(
        request=request,
        ebitda_basis=headline_inputs.ebitda_basis,
        implied_mid_multiple=headline_inputs.implied_mid_multiple,
        low_band_ratio=headline_inputs.low_band_ratio,
        high_band_ratio=headline_inputs.high_band_ratio,
        adjustment_factor=adjustment_factor,
    )
    adjusted_ev_decimal, adjusted_low_ev_decimal, adjusted_high_ev_decimal = (
        _adjusted_enterprise_values(
            headline_inputs=headline_inputs,
            adjustment_factor=adjustment_factor,
            effective_override_state=effective_override_state,
        )
    )
    _stamp_segment_valuation(
        headline_inputs.segment_valuation,
        true_sotp_enabled=headline_inputs.true_sotp_enabled,
        adjustment_factor=adjustment_factor,
        adjusted_ev_decimal=adjusted_ev_decimal,
    )

    adjusted_ev = safe_float(adjusted_ev_decimal)
    enterprise_value_mid = adjusted_ev_decimal if adjusted_ev_decimal >= 0 else None
    enterprise_value_low = safe_decimal_or_zero(
        min(adjusted_low_ev_decimal, adjusted_high_ev_decimal)
    )
    enterprise_value_high = safe_decimal_or_zero(
        max(adjusted_low_ev_decimal, adjusted_high_ev_decimal)
    )
    exact_completion_bridge = completion_account_bridge(request)
    equity_value_low, equity_value_mid, equity_value_high = _equity_value_range(
        adjusted_ev=adjusted_ev_decimal,
        adjusted_low_ev_decimal=adjusted_low_ev_decimal,
        adjusted_high_ev_decimal=adjusted_high_ev_decimal,
        total_debt=exact_completion_bridge.bridge_total_debt,
        cash=exact_completion_bridge.bridge_cash,
    )
    equity_adjustments = apply_stateless_equity_adjustments(
        request=request,
        historical_data=input_context.historical_data,
        current_year_data=input_context.current_year_data,
        equity_value_low=equity_value_low,
        equity_value_mid=equity_value_mid,
        equity_value_high=equity_value_high,
        real_estate_surplus=real_estate_surplus,
        logger=logger,
    )
    input_context.triage_flags.extend(equity_adjustments.bridge_adjustment_flags)
    confidence_score = calculate_confidence_score(
        historical_data=input_context.historical_data,
        calibration=calibration,
        data_quality=len(input_context.historical_data) >= 3,
    )
    confidence_level = score_to_level(confidence_score)
    recommended_asking = _recommended_asking(
        request=request,
        equity_value_mid=equity_adjustments.equity_value_mid,
        confidence_level=confidence_level,
    )
    recommended_multiple = Decimal(str(ev_ebitda_multiple)) if ev_ebitda_multiple > 0 else None
    multiples_results = _multiples_results_payload(
        input_context=input_context,
        benchmark_contract=benchmark_contract,
        benchmark_contract_resolved=benchmark_contract_resolved,
        benchmark_provenance=benchmark_provenance,
        base_enterprise_value=headline_inputs.base_enterprise_value,
        ev_ebitda_multiple=ev_ebitda_multiple,
        p25_multiple=p25_multiple,
        p75_multiple=p75_multiple,
        size_discount=size_discount,
        liquidity_discount=liquidity_discount,
        country_adjustment=country_adjustment,
        total_adjustment=total_adjustment,
        discount_build_up=discount_build_up,
        adjusted_equity_value=equity_adjustments.equity_value_mid,
        segment_valuation=headline_inputs.segment_valuation,
        multiple_calibration_audit=multiple_calibration_audit,
        effective_multiple_override_audit=effective_override_state.audit,
        real_estate_surplus=real_estate_surplus,
        request=request,
    )
    data_quality = _data_quality_payload(
        input_context=input_context,
        benchmark_contract=benchmark_contract,
        benchmark_contract_resolved=benchmark_contract_resolved,
        benchmark_provenance=benchmark_provenance,
    )
    multiples_results.update(_multiples_source_payload(data_quality))
    build_up_state = build_stateless_multiple_build_up_state(
        request=request,
        multiples_results=multiples_results,
        ebitda_basis=headline_inputs.ebitda_basis,
        segment_valuation=headline_inputs.segment_valuation,
        multiple_type_blend_block=headline_inputs.multiple_type_blend_block,
        enterprise_value_mid=enterprise_value_mid,
        total_debt=total_debt,
        cash=cash,
        nwc_normalization_data=equity_adjustments.nwc_normalization_data,
        real_estate_surplus=real_estate_surplus,
        equity_value_mid_full=equity_adjustments.equity_value_mid_full,
        effective_multiple_override_audit=effective_override_state.audit,
        business_type_multiple_override_audit=business_type_multiple_override_audit,
        multiple_calibration_audit=multiple_calibration_audit,
        calibration=calibration,
        activity_code=input_context.activity_code,
        benchmark_provenance=benchmark_provenance,
        ev_ebitda_multiple=ev_ebitda_multiple,
        p25_multiple=p25_multiple,
        p75_multiple=p75_multiple,
        discount_build_up=discount_build_up,
        effective_mid_multiple=effective_override_state.effective_mid_multiple,
        enterprise_value_low=enterprise_value_low,
        enterprise_value_high=enterprise_value_high,
        earnings_basis_ledger=input_context.earnings_basis,
        bridge_adjustment_data=equity_adjustments.bridge_adjustment_data,
    )
    return StatelessHeadlineComputation(
        equity_value_low=equity_adjustments.equity_value_low,
        equity_value_mid=equity_adjustments.equity_value_mid,
        equity_value_high=equity_adjustments.equity_value_high,
        enterprise_value_low=enterprise_value_low,
        enterprise_value_mid=enterprise_value_mid,
        enterprise_value_high=enterprise_value_high,
        confidence_score=confidence_score,
        confidence_level=confidence_level,
        recommended_asking=recommended_asking,
        value_drivers=identify_value_drivers(
            ebitda_margin=input_context.ebitda_margin,
            revenue_growth=float(input_context.revenue_growth),
            calibration=calibration,
        ),
        risk_factors=identify_risk_factors(
            owner_dependency=request.owner_dependency,
            revenue=input_context.revenue,
            ebitda=input_context.ebitda,
            historical_years=len(input_context.historical_data),
        ),
        data_quality=data_quality,
        size_discount=size_discount,
        liquidity_discount=liquidity_discount,
        owner_adjustment=owner_adjustment,
        country_adjustment=country_adjustment,
        total_adjustment=total_adjustment,
        base_enterprise_value=headline_inputs.base_enterprise_value,
        adjusted_ev=adjusted_ev,
        recommended_multiple=recommended_multiple,
        multiples_results=build_up_state.multiples_results,
        multiple_build_up_obj=build_up_state.multiple_build_up,
        earnings_basis_value=build_up_state.earnings_basis,
        earnings_basis_rationale_value=build_up_state.earnings_basis_rationale,
        ownership_percentage=equity_adjustments.ownership_percentage,
        ownership_multiplier=equity_adjustments.ownership_multiplier,
        nwc_normalization_data=equity_adjustments.nwc_normalization_data,
        bridge_adjustment_data=equity_adjustments.bridge_adjustment_data,
    )


def _discount_build_up(
    *,
    request: CalculateRequest,
    revenue: float,
    team_size: object,
    size_discount: float,
    liquidity_discount: float,
    country_adjustment: float,
    triage_flags: list[TriageFlag],
) -> dict[str, object]:
    discount_build_up = build_stateless_discount_stack(
        size_discount=size_discount,
        liquidity_discount=liquidity_discount,
        country_adjustment=country_adjustment,
        advisor_discount_weights=getattr(request, "advisor_discount_weights", None),
        risk_analysis_enabled=getattr(request, "risk_analysis_enabled", True),
        discount_floor_factor=getattr(request, "discount_floor_factor", None),
        strength_factor_discount_adjustments=(
            strength_factor_discount_adjustments_from_business_context(
                getattr(request, "business_context", None),
                revenue=revenue,
                team_size=team_size,
            )
        ),
    )
    if not bool(getattr(request, "risk_analysis_enabled", True)):
        triage_flags.append(
            TriageFlag(
                field="risk_analysis_enabled",
                issue="risk_analysis_disabled_reference_value",
                severity="warning",
                value=False,
            )
        )
    return discount_build_up


def _effective_override_state(
    *,
    request: CalculateRequest,
    ebitda_basis: Decimal,
    implied_mid_multiple: Decimal,
    low_band_ratio: Decimal,
    high_band_ratio: Decimal,
    adjustment_factor: Decimal,
):
    adj_factor = adjustment_factor
    model_effective_mid_multiple = safe_decimal_or_zero(
        implied_mid_multiple
    ) * safe_decimal_or_zero(adj_factor)
    model_effective_low_multiple = (
        safe_decimal_or_zero(implied_mid_multiple)
        * low_band_ratio
        * safe_decimal_or_zero(adj_factor)
    )
    model_effective_high_multiple = (
        safe_decimal_or_zero(implied_mid_multiple)
        * high_band_ratio
        * safe_decimal_or_zero(adj_factor)
    )
    return resolve_effective_multiple_override(
        request=request,
        ebitda_basis=ebitda_basis,
        model_effective_mid_multiple=model_effective_mid_multiple,
        model_effective_low_multiple=model_effective_low_multiple,
        model_effective_high_multiple=model_effective_high_multiple,
    )


def _adjusted_enterprise_values(
    *,
    headline_inputs,
    adjustment_factor: Decimal,
    effective_override_state,
) -> tuple[Decimal, Decimal, Decimal]:
    if headline_inputs.true_sotp_enabled and not effective_override_state.raw_override_present:
        return (
            headline_inputs.pre_adjustment_enterprise_value * adjustment_factor,
            headline_inputs.pre_adjustment_enterprise_value
            * headline_inputs.low_band_ratio
            * adjustment_factor,
            headline_inputs.pre_adjustment_enterprise_value
            * headline_inputs.high_band_ratio
            * adjustment_factor,
        )
    return (
        headline_inputs.ebitda_basis * effective_override_state.effective_mid_multiple,
        headline_inputs.ebitda_basis * effective_override_state.effective_low_multiple,
        headline_inputs.ebitda_basis * effective_override_state.effective_high_multiple,
    )


def _stamp_segment_valuation(
    segment_valuation: object,
    *,
    true_sotp_enabled: bool,
    adjustment_factor: Decimal,
    adjusted_ev_decimal: Decimal,
) -> None:
    if not isinstance(segment_valuation, dict):
        return
    segment_valuation["value_source"] = (
        "true_sotp" if true_sotp_enabled else "weighted_blend_fallback_not_applied"
    )
    segment_valuation["adjustment_factor"] = adjustment_factor
    segment_valuation["adjusted_enterprise_value"] = (
        adjusted_ev_decimal if true_sotp_enabled else None
    )


def _equity_value_range(
    *,
    adjusted_ev: FinancialNumber,
    adjusted_low_ev_decimal: Decimal,
    adjusted_high_ev_decimal: Decimal,
    total_debt: FinancialNumber,
    cash: FinancialNumber,
) -> tuple[Decimal, Decimal, Decimal]:
    bridge = -decimal_number(total_debt, "total debt") + decimal_number(cash, "cash")
    eq_mid = decimal_number(adjusted_ev, "enterprise midpoint") + bridge
    eq_low = decimal_number(adjusted_low_ev_decimal, "enterprise lower bound") + bridge
    eq_high = decimal_number(adjusted_high_ev_decimal, "enterprise upper bound") + bridge
    return min(eq_low, eq_high), eq_mid, max(eq_low, eq_high)


def _recommended_asking(
    *,
    request: CalculateRequest,
    equity_value_mid: Decimal,
    confidence_level: str,
) -> Decimal:
    asking_markup = get_asking_price_markup(
        confidence_level.lower(),
        advisor_override_pct=getattr(request, "asking_price_buffer_pct", None),
    )
    return (equity_value_mid * asking_markup).quantize(Decimal("0.01"))


def _multiples_results_payload(
    *,
    input_context: StatelessInputContext,
    benchmark_contract: dict[str, object] | None,
    benchmark_contract_resolved: bool,
    benchmark_provenance: dict[str, object],
    base_enterprise_value: float,
    ev_ebitda_multiple: float,
    p25_multiple: float,
    p75_multiple: float,
    size_discount: float,
    liquidity_discount: float,
    country_adjustment: float,
    total_adjustment: Decimal,
    discount_build_up: dict[str, object],
    adjusted_equity_value: Decimal,
    segment_valuation: object,
    multiple_calibration_audit: dict[str, object] | None,
    effective_multiple_override_audit: dict[str, object] | None,
    real_estate_surplus: Decimal,
    request: CalculateRequest,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "ev_ebitda_valuation": base_enterprise_value,
        "ebitda_multiple": ev_ebitda_multiple,
        **benchmark_range_disclosure(
            resolved=benchmark_contract_resolved,
            contract=benchmark_contract,
            supplied_low=input_context.calibration.ev_ebitda_p25,
            supplied_high=input_context.calibration.ev_ebitda_p75,
            applied_low=p25_multiple,
            applied_high=p75_multiple,
            governed_external=request.external_market_reference_contract is not None,
            disclosed_external=request.disclosed_external_market_reference is not None,
            composite_price=bool(segment_valuation or request.multiple_type_weights),
        ),
        "benchmark_contract_resolved": benchmark_contract_resolved,
        "size_discount": float(size_discount),
        "liquidity_discount": liquidity_discount,
        "country_adjustment": country_adjustment,
        "total_adjustment": float(total_adjustment),
        "discount_build_up": discount_build_up,
        "base_value": base_enterprise_value,
        "adjusted_equity_value": float(adjusted_equity_value),
        "business_type_id": input_context.calibration.business_type_id,
        "primary_business_type_id": input_context.primary_business_type_id,
        "business_type_mix": input_context.business_type_mix,
        "business_type_weights": input_context.business_type_weights,
        "business_type_mix_policy": input_context.business_type_mix_policy,
        "benchmark_contract": benchmark_contract if benchmark_contract_resolved else None,
        "benchmark_provenance": benchmark_provenance,
        "earnings_basis_ledger": input_context.earnings_basis,
    }
    _apply_optional_multiples_payloads(
        payload,
        segment_valuation=segment_valuation,
        multiple_calibration_audit=multiple_calibration_audit,
        effective_multiple_override_audit=effective_multiple_override_audit,
        real_estate_surplus=real_estate_surplus,
        request=request,
    )
    return payload


def _apply_optional_multiples_payloads(
    payload: dict[str, object],
    *,
    segment_valuation: object,
    multiple_calibration_audit: dict[str, object] | None,
    effective_multiple_override_audit: dict[str, object] | None,
    real_estate_surplus: Decimal,
    request: CalculateRequest,
) -> None:
    if segment_valuation:
        payload["segment_valuation"] = segment_valuation
    if multiple_calibration_audit:
        payload["multiple_calibration"] = multiple_calibration_audit
    if effective_multiple_override_audit:
        payload["effective_multiple_override"] = effective_multiple_override_audit
    if real_estate_surplus != Decimal("0"):
        payload["real_estate_inclusion"] = {
            "market_value": float_or_none(request.real_estate_market_value),
            "book_value": float_or_none(request.real_estate_book_value),
            "property_bridge_value": float(real_estate_surplus),
            "surplus_value": float(real_estate_surplus),
            "treatment": "owned_included",
            "book_value_used_in_bridge": False,
        }


def _data_quality_payload(
    *,
    input_context: StatelessInputContext,
    benchmark_contract: dict[str, object] | None,
    benchmark_contract_resolved: bool,
    benchmark_provenance: dict[str, object],
) -> dict[str, object]:
    multiples_source, is_delphi_benchmark_sourced, fallback_used, fallback_reason = (
        resolve_multiples_source_policy(
            benchmark_contract_resolved=benchmark_contract_resolved,
            benchmark_contract=benchmark_contract,
            allow_untrusted_multiples_fallback=input_context.allow_untrusted_multiples_fallback,
            governed_external_market_reference=(
                input_context.request.external_market_reference_contract is not None
            ),
        )
    )
    calibration = input_context.calibration
    return {
        "multiples_source": multiples_source,
        "is_delphi_benchmark_sourced": is_delphi_benchmark_sourced,
        "enrichment_complete": True,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "business_type_id": calibration.business_type_id,
        "primary_business_type_id": input_context.primary_business_type_id,
        "business_type_mix": input_context.business_type_mix,
        "business_type_weights": input_context.business_type_weights,
        "business_type_mix_policy": input_context.business_type_mix_policy,
        "category_id": calibration.category_id,
        "data_quality_score": (
            safe_float(calibration.calibration_quality_score)
            if calibration.calibration_quality_score is not None
            else None
        ),
        "benchmark_contract": benchmark_contract if benchmark_contract_resolved else None,
        "benchmark_provenance": benchmark_provenance,
    }


def _multiples_source_payload(data_quality: dict[str, object]) -> dict[str, object]:
    return {
        "multiples_source": data_quality["multiples_source"],
        "is_delphi_benchmark_sourced": data_quality["is_delphi_benchmark_sourced"],
        "fallback_used": data_quality["fallback_used"],
        "fallback_reason": data_quality["fallback_reason"],
    }
