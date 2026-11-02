"""Stateless-specific assembly of the canonical multiple build-up object."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from src.api.schemas.multiple_build_up import MultipleBuildUp
from src.domain.multiples.advisor_controls import (
    build_adjusted_ebitda_build_up,
    normalize_earnings_basis,
)
from src.services.reports.multiple_build_up_assembler import (
    assemble_multiple_build_up,
    build_equity_bridge,
)
from src.services.reports.earnings_basis_projection import project_earnings_basis_ledger
from src.utils.decimal_helpers import safe_decimal_or_zero


@dataclass(frozen=True)
class StatelessMultipleBuildUpState:
    earnings_basis: str
    earnings_basis_rationale: str
    multiple_build_up: MultipleBuildUp
    multiples_results: dict[str, object]


def _business_type_title(
    *,
    calibration,
    benchmark_provenance: dict[str, object] | None,
) -> object:
    if benchmark_provenance and benchmark_provenance.get("source_business_type_title"):
        return benchmark_provenance.get("source_business_type_title")

    contract = getattr(calibration, "benchmark_contract", None)
    if isinstance(contract, dict) and contract.get("source_business_type_title"):
        return contract.get("source_business_type_title")

    return getattr(calibration, "industry", None)


def build_stateless_multiple_build_up_state(
    *,
    request,
    multiples_results: dict[str, object],
    ebitda_basis: Decimal,
    segment_valuation: dict[str, object] | None,
    multiple_type_blend_block: dict[str, object] | None,
    enterprise_value_mid: Decimal | None,
    total_debt: object,
    cash: object,
    nwc_normalization_data: dict[str, object] | None,
    real_estate_surplus: Decimal,
    equity_value_mid_full: Decimal,
    effective_multiple_override_audit: dict[str, object] | None,
    business_type_multiple_override_audit: dict[str, object] | None,
    multiple_calibration_audit: dict[str, object] | None,
    calibration,
    activity_code: object,
    benchmark_provenance: dict[str, object] | None,
    ev_ebitda_multiple: object,
    p25_multiple: object,
    p75_multiple: object,
    discount_build_up: dict[str, object],
    effective_mid_multiple: object,
    enterprise_value_low: Decimal,
    enterprise_value_high: Decimal,
    earnings_basis_ledger: dict[str, object] | None = None,
    bridge_adjustment_data: dict[str, object] | None = None,
) -> StatelessMultipleBuildUpState:
    """Build the typed SSOT for multiples without recomputing valuation math."""
    adjusted_ebitda_build_up = (
        project_earnings_basis_ledger(earnings_basis_ledger)
        if earnings_basis_ledger is not None
        else build_adjusted_ebitda_build_up(request.current_year)
    )
    reported_earnings_value = safe_decimal_or_zero(
        (earnings_basis_ledger or {}).get("reported_ebitda")
        if earnings_basis_ledger
        else (
            adjusted_ebitda_build_up.get("reported_ebitda")
            if adjusted_ebitda_build_up
            else ebitda_basis
        )
    )
    adjusted_earnings_value = ebitda_basis
    earnings_basis = normalize_earnings_basis("EBITDA")
    has_normalizations = bool(getattr(request, "normalizations", None))
    if earnings_basis_ledger is not None:
        earnings_basis_rationale = str(adjusted_ebitda_build_up["rationale"])
    elif getattr(request.current_year, "ebitda_normalized", False) or has_normalizations:
        earnings_basis_rationale = (
            "Adjusted EBITDA basis: approved normalizations × market EV/EBITDA multiple."
        )
    else:
        earnings_basis_rationale = (
            "Reported EBITDA basis: no normalization adjustments were applied."
        )

    updated_multiples_results = dict(multiples_results)
    disclosed_reference = getattr(request, "disclosed_external_market_reference", None)
    if disclosed_reference is not None:
        updated_multiples_results["disclosed_external_market_reference"] = (
            disclosed_reference.model_dump(mode="json")
        )
    governed_reference = getattr(request, "external_market_reference_contract", None)
    if governed_reference is not None:
        updated_multiples_results["external_market_reference_contract"] = (
            governed_reference.model_dump(mode="json")
        )
        # A governed external-market reference is an advisor-selected observation,
        # not an empirical benchmark distribution.  Keep the applied value visible
        # without silently relabelling it as a sample median in the canonical
        # build-up consumed by reports and downstream APIs.
        updated_multiples_results["applied_reference_multiple"] = str(
            safe_decimal_or_zero(ev_ebitda_multiple)
        )
    if multiple_type_blend_block:
        updated_multiples_results["multiple_type_blend"] = multiple_type_blend_block
    if earnings_basis_ledger:
        updated_multiples_results["earnings_basis_ledger"] = earnings_basis_ledger

    equity_bridge = build_equity_bridge(
        enterprise_value=enterprise_value_mid,
        total_debt=safe_decimal_or_zero(total_debt),
        cash=safe_decimal_or_zero(cash),
        nwc_normalization=nwc_normalization_data,
        real_estate_surplus=real_estate_surplus,
        bridge_adjustments=bridge_adjustment_data,
        equity_value=equity_value_mid_full,
        show_bridge=bool(getattr(request, "show_enterprise_to_equity_bridge", True)),
    )

    if effective_multiple_override_audit:
        advisor_override_payload: dict[str, object] | None = {
            **effective_multiple_override_audit,
            "kind": "effective_multiple",
        }
    elif business_type_multiple_override_audit:
        advisor_override_payload = {
            **business_type_multiple_override_audit,
            "model_effective_multiple": business_type_multiple_override_audit.get("model_multiple"),
            "advisor_effective_multiple": business_type_multiple_override_audit.get(
                "advisor_multiple"
            ),
        }
    elif multiple_calibration_audit:
        advisor_override_payload = {
            "kind": "multiple_calibration",
            "model_effective_multiple": multiple_calibration_audit.get("sector_average_multiple"),
            "advisor_effective_multiple": multiple_calibration_audit.get("calibrated_multiple"),
            "note": multiple_calibration_audit.get("note"),
        }
    else:
        advisor_override_payload = None

    if business_type_multiple_override_audit:
        updated_multiples_results["business_type_multiple_override"] = (
            business_type_multiple_override_audit
        )

    multiple_build_up = assemble_multiple_build_up(
        basis=earnings_basis,
        basis_rationale=earnings_basis_rationale,
        reported_earnings=reported_earnings_value,
        adjusted_earnings=adjusted_earnings_value,
        add_back_ledger=adjusted_ebitda_build_up,
        segment_valuation=segment_valuation,
        primary_basis=earnings_basis,
        primary_meta={
            "business_type_id": calibration.business_type_id,
            "business_type_title": _business_type_title(
                calibration=calibration,
                benchmark_provenance=benchmark_provenance,
            ),
            "nace_code": activity_code or None,
        },
        benchmark_provenance=benchmark_provenance,
        primary_multiple=safe_decimal_or_zero(ev_ebitda_multiple),
        primary_p25=(
            safe_decimal_or_zero(p25_multiple) if benchmark_provenance is not None else None
        ),
        primary_median=(
            None if governed_reference is not None else safe_decimal_or_zero(ev_ebitda_multiple)
        ),
        primary_p75=(
            safe_decimal_or_zero(p75_multiple) if benchmark_provenance is not None else None
        ),
        discount_build_up=discount_build_up,
        multiple_type_blend=multiple_type_blend_block,
        advisor_override=advisor_override_payload,
        risk_analysis_enabled=bool(getattr(request, "risk_analysis_enabled", True)),
        equity_bridge=equity_bridge,
        effective_multiple=safe_decimal_or_zero(effective_mid_multiple),
        enterprise_value=enterprise_value_mid,
        equity_value=equity_value_mid_full,
        band_low=enterprise_value_low,
        band_high=enterprise_value_high,
        primary_is_override=(
            effective_multiple_override_audit is not None
            or business_type_multiple_override_audit is not None
        ),
    )
    updated_multiples_results["multiple_build_up"] = multiple_build_up.model_dump(mode="json")
    updated_multiples_results.update(
        {
            "enterprise_value": str(enterprise_value_mid),
            "enterprise_value_low": str(enterprise_value_low),
            "enterprise_value_high": str(enterprise_value_high),
            "equity_value": str(equity_value_mid_full),
        }
    )

    return StatelessMultipleBuildUpState(
        earnings_basis=earnings_basis,
        earnings_basis_rationale=earnings_basis_rationale,
        multiple_build_up=multiple_build_up,
        multiples_results=updated_multiples_results,
    )
