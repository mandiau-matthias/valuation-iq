"""Multiple-channel headline policy for stateless valuations."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping

from src.api.schemas.stateless_api import BusinessTypeCalibration, CalculateRequest, TriageFlag
from src.domain.multiples.advisor_controls import (
    build_multiple_type_blend,
    build_sotp_segments,
    infer_sector_multiple_type_weights,
)
from src.domain.financial_arithmetic import FinancialNumber, decimal_number
from src.utils.decimal_helpers import safe_decimal_or_zero, safe_float

# BET-526: when segments are supplied but earnings/multiple are incomplete, the
# headline reverts to a single blended estimate — widen the band (brand oath:
# no false precision on an estimate). ~15% wider each side than the model band.
BLEND_FALLBACK_BAND_WIDENING_LOW = Decimal("0.85")
BLEND_FALLBACK_BAND_WIDENING_HIGH = Decimal("1.15")


@dataclass(frozen=True)
class StatelessMultiplesHeadlineInputs:
    ebitda_basis: Decimal
    segment_valuation: dict[str, object] | None
    true_sotp_enabled: bool
    multiple_type_blend_block: dict[str, object] | None
    blend_drives_headline: bool
    pre_adjustment_enterprise_value: Decimal
    base_enterprise_value: float
    implied_mid_multiple: Decimal
    low_band_ratio: Decimal
    high_band_ratio: Decimal
    triage_flags: list[TriageFlag]


def build_stateless_multiples_headline_inputs(
    *,
    request: CalculateRequest,
    calibration: BusinessTypeCalibration,
    benchmark_contract: Mapping[str, object] | None,
    benchmark_contract_resolved: bool,
    revenue: FinancialNumber,
    ebitda: FinancialNumber,
    ev_ebitda_multiple: object,
    p25_multiple: object,
    p75_multiple: object,
) -> StatelessMultiplesHeadlineInputs:
    """Resolve the multiples headline source and band policy without recomputing later math."""
    ebitda_basis = decimal_number(ebitda, "normalized EBITDA")
    revenue = decimal_number(revenue, "revenue")
    segment_valuation = _build_segment_valuation(request)
    true_sotp_enabled = _is_true_sotp_enabled(segment_valuation)
    multiple_type_blend_block = _build_multiple_type_blend_block(
        request=request,
        calibration=calibration,
        benchmark_contract=benchmark_contract,
        benchmark_contract_resolved=benchmark_contract_resolved,
        revenue=revenue,
        ebitda_basis=ebitda_basis,
        ev_ebitda_multiple=ev_ebitda_multiple,
    )
    blend_drives_headline = _blend_drives_headline(
        request=request,
        true_sotp_enabled=true_sotp_enabled,
        multiple_type_blend_block=multiple_type_blend_block,
    )
    pre_adjustment_enterprise_value = _pre_adjustment_enterprise_value(
        segment_valuation=segment_valuation,
        true_sotp_enabled=true_sotp_enabled,
        multiple_type_blend_block=multiple_type_blend_block,
        blend_drives_headline=blend_drives_headline,
        ebitda_basis=ebitda_basis,
        ev_ebitda_multiple=ev_ebitda_multiple,
    )
    implied_mid_multiple = (
        pre_adjustment_enterprise_value / ebitda_basis
        if (true_sotp_enabled or blend_drives_headline) and ebitda_basis > 0
        else safe_decimal_or_zero(ev_ebitda_multiple)
    )
    low_band_ratio, high_band_ratio, triage_flags = _band_ratios_and_flags(
        segment_valuation=segment_valuation,
        p25_multiple=p25_multiple,
        ev_ebitda_multiple=ev_ebitda_multiple,
        p75_multiple=p75_multiple,
    )

    return StatelessMultiplesHeadlineInputs(
        ebitda_basis=ebitda_basis,
        segment_valuation=segment_valuation,
        true_sotp_enabled=true_sotp_enabled,
        multiple_type_blend_block=multiple_type_blend_block,
        blend_drives_headline=blend_drives_headline,
        pre_adjustment_enterprise_value=pre_adjustment_enterprise_value,
        base_enterprise_value=safe_float(pre_adjustment_enterprise_value),
        implied_mid_multiple=implied_mid_multiple,
        low_band_ratio=low_band_ratio,
        high_band_ratio=high_band_ratio,
        triage_flags=triage_flags,
    )


def _build_segment_valuation(request: CalculateRequest) -> dict[str, object] | None:
    segment_valuation = build_sotp_segments(getattr(request, "business_type_segments", None))
    return segment_valuation if isinstance(segment_valuation, dict) else None


def _is_true_sotp_enabled(segment_valuation: dict[str, object] | None) -> bool:
    return bool(
        segment_valuation
        and segment_valuation.get("mode") == "true_sotp"
        and segment_valuation.get("enterprise_value") is not None
    )


def _build_multiple_type_blend_block(
    *,
    request: CalculateRequest,
    calibration: BusinessTypeCalibration,
    benchmark_contract: Mapping[str, object] | None,
    benchmark_contract_resolved: bool,
    revenue: FinancialNumber,
    ebitda_basis: Decimal,
    ev_ebitda_multiple: object,
) -> dict[str, object] | None:
    # BET-535: build the multiple-type blend ONCE. When the advisor supplies
    # multiple_type_weights, the weighted blend (EV/EBITDA + EV/Revenue [+ P/E])
    # drives the pre-adjustment EV; otherwise the default remains pure EV/EBITDA.
    revenue_decimal = decimal_number(revenue, "revenue")
    ev_ebitda_candidate = ebitda_basis * safe_decimal_or_zero(ev_ebitda_multiple)
    blend_default_weights, _ = infer_sector_multiple_type_weights(
        revenue=revenue,
        ebitda=ebitda_basis,
        benchmark_contract=benchmark_contract if benchmark_contract_resolved else None,
    )
    blend_candidate_values: dict[str, object] = {"ev_ebitda": ev_ebitda_candidate}
    ev_revenue_median = calibration.ev_revenue_median
    if ev_revenue_median and revenue_decimal > 0:
        blend_candidate_values["ev_revenue"] = safe_decimal_or_zero(revenue) * safe_decimal_or_zero(
            ev_revenue_median
        )

    if len(blend_candidate_values) <= 1:
        return None

    return build_multiple_type_blend(
        blend_candidate_values,
        raw_weights=getattr(request, "multiple_type_weights", None),
        default_weights=blend_default_weights,
    )


def _blend_drives_headline(
    *,
    request: CalculateRequest,
    true_sotp_enabled: bool,
    multiple_type_blend_block: dict[str, object] | None,
) -> bool:
    return bool(
        getattr(request, "multiple_type_weights", None)
        and not true_sotp_enabled
        and multiple_type_blend_block is not None
    )


def _pre_adjustment_enterprise_value(
    *,
    segment_valuation: dict[str, object] | None,
    true_sotp_enabled: bool,
    multiple_type_blend_block: dict[str, object] | None,
    blend_drives_headline: bool,
    ebitda_basis: Decimal,
    ev_ebitda_multiple: object,
) -> Decimal:
    if true_sotp_enabled and segment_valuation is not None:
        return safe_decimal_or_zero(segment_valuation.get("enterprise_value"))
    if blend_drives_headline and multiple_type_blend_block is not None:
        return safe_decimal_or_zero(multiple_type_blend_block.get("weighted_enterprise_value"))
    return ebitda_basis * safe_decimal_or_zero(ev_ebitda_multiple)


def _band_ratios_and_flags(
    *,
    segment_valuation: dict[str, object] | None,
    p25_multiple: object,
    ev_ebitda_multiple: object,
    p75_multiple: object,
) -> tuple[Decimal, Decimal, list[TriageFlag]]:
    denominator = safe_decimal_or_zero(ev_ebitda_multiple)
    if denominator > 0:
        low_band_ratio = safe_decimal_or_zero(p25_multiple) / denominator
        high_band_ratio = safe_decimal_or_zero(p75_multiple) / denominator
    else:
        low_band_ratio = Decimal("0.8")
        high_band_ratio = Decimal("1.2")

    if not (segment_valuation and segment_valuation.get("mode") == "weighted_blend_fallback"):
        return low_band_ratio, high_band_ratio, []

    segment_valuation["band_widened"] = True
    return (
        low_band_ratio * BLEND_FALLBACK_BAND_WIDENING_LOW,
        high_band_ratio * BLEND_FALLBACK_BAND_WIDENING_HIGH,
        [
            TriageFlag(
                field="business_type_segments",
                issue="segment_blend_estimate_band_widened",
                severity="info",
                value=True,
            )
        ],
    )
