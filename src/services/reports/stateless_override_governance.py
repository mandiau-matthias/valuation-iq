"""Advisor override governance helpers for the stateless calculation path."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status

from src.domain.multiples.governance import BoundsVerdict, check_effective_multiple, check_multiple
from src.utils.decimal_helpers import safe_decimal_or_zero, safe_float


@dataclass(frozen=True)
class MultipleCalibrationState:
    ev_ebitda_multiple: float
    p25_multiple: float
    p75_multiple: float
    business_type_multiple_override_audit: dict[str, object] | None
    multiple_calibration_audit: dict[str, object] | None


@dataclass(frozen=True)
class EffectiveMultipleOverrideState:
    effective_mid_multiple: Decimal
    effective_low_multiple: Decimal
    effective_high_multiple: Decimal
    audit: dict[str, object] | None
    raw_override_present: bool


def utc_now_iso() -> str:
    """Return a high-resolution canonical UTC ISO-8601 timestamp.

    Valuation runs are immutable observations. Truncating to whole seconds made
    two otherwise identical recalculations collide in Titan's append-only graph.
    Keep microseconds so the recording instant remains part of run identity.
    """
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def enforce_override_governance(verdict: BoundsVerdict, *, lever: str, confirmed: bool) -> bool:
    """Enforce centralized override bounds and return whether the value is out-of-band."""
    if not verdict.within_absolute:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "OVERRIDE_OUT_OF_BOUNDS",
                "lever": lever,
                "message": verdict.reason or "Override is outside the sane range.",
                "lower_bound": float(verdict.lower),
                "upper_bound": float(verdict.upper),
            },
        )
    if verdict.out_of_band and not confirmed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "OVERRIDE_OUT_OF_BAND_UNCONFIRMED",
                "lever": lever,
                "message": (
                    (verdict.reason or "Override is far from the model.")
                    + " Set override_out_of_band_confirmed=true to proceed."
                ),
            },
        )
    return verdict.out_of_band


def resolve_multiple_calibration(
    *,
    request,
    calibration,
    primary_business_type_id: str | None,
) -> MultipleCalibrationState:
    """Resolve model multiples plus advisor calibration/primary type overrides."""
    ev_ebitda_multiple = safe_float(calibration.ev_ebitda_median)
    disclosed_reference = getattr(request, "disclosed_external_market_reference", None)
    governed_reference = getattr(request, "external_market_reference_contract", None)
    external_reference = governed_reference or disclosed_reference
    if external_reference is not None:
        # These variables feed the valuation band only. They are *not* P25/P75
        # observations: the schema and report layer preserve the source's
        # advisor-defined external-reference status.
        p25_multiple = safe_float(external_reference.range_low_multiple)
        p75_multiple = safe_float(external_reference.range_high_multiple)
    else:
        p25_multiple = (
            safe_float(calibration.ev_ebitda_p25)
            if calibration.ev_ebitda_p25 is not None
            else (ev_ebitda_multiple * 0.8 if ev_ebitda_multiple > 0 else 0.0)
        )
        p75_multiple = (
            safe_float(calibration.ev_ebitda_p75)
            if calibration.ev_ebitda_p75 is not None
            else (ev_ebitda_multiple * 1.2 if ev_ebitda_multiple > 0 else 0.0)
        )

    business_type_multiple_override_audit = None
    primary_override_value = None
    primary_override_key = None
    business_type_overrides = getattr(request, "business_type_multiple_overrides", None) or {}
    for override_key in (primary_business_type_id, calibration.business_type_id):
        if override_key and override_key in business_type_overrides:
            primary_override_value = business_type_overrides[override_key]
            primary_override_key = override_key
            break

    if primary_override_value is not None and ev_ebitda_multiple > 0:
        override_multiple = safe_float(primary_override_value)
        model_base_multiple = ev_ebitda_multiple
        verdict = check_multiple(override_multiple, basis="EBITDA", model_value=model_base_multiple)
        out_of_band = enforce_override_governance(
            verdict,
            lever="business_type_multiple",
            confirmed=bool(getattr(request, "override_out_of_band_confirmed", False)),
        )
        low_ratio = (p25_multiple / model_base_multiple) if model_base_multiple > 0 else 0.8
        high_ratio = (p75_multiple / model_base_multiple) if model_base_multiple > 0 else 1.2
        ev_ebitda_multiple = override_multiple
        p25_multiple = override_multiple * low_ratio
        p75_multiple = override_multiple * high_ratio
        business_type_multiple_override_audit = {
            "kind": "per_type_multiple",
            "business_type_id": primary_override_key,
            "model_multiple": model_base_multiple,
            "advisor_multiple": override_multiple,
            "delta_multiple": override_multiple - model_base_multiple,
            "out_of_band": out_of_band,
            "index_protected": True,
            "advisor_id": getattr(request, "advisor_id", None),
            "timestamp": utc_now_iso(),
            "note": getattr(request, "business_type_multiple_override_note", None),
        }

    multiple_calibration_audit = None
    manual_multiple_adjustment = safe_float(request.multiple_calibration_adjustment)
    if manual_multiple_adjustment:
        sector_average_multiple = ev_ebitda_multiple
        ev_ebitda_multiple += manual_multiple_adjustment
        p25_multiple += manual_multiple_adjustment
        p75_multiple += manual_multiple_adjustment
        if ev_ebitda_multiple <= 0 or p25_multiple <= 0 or p75_multiple <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "INVALID_MULTIPLE_CALIBRATION",
                    "message": "Advisor multiple calibration produces a non-positive multiple.",
                    "sector_average_multiple": sector_average_multiple,
                    "specific_risk_quality_premium": manual_multiple_adjustment,
                },
            )
        multiple_calibration_audit = {
            "sector_average_multiple": sector_average_multiple,
            "specific_risk_quality_premium": manual_multiple_adjustment,
            "calibrated_multiple": ev_ebitda_multiple,
            "note": request.multiple_calibration_note,
        }

    return MultipleCalibrationState(
        ev_ebitda_multiple=ev_ebitda_multiple,
        p25_multiple=p25_multiple,
        p75_multiple=p75_multiple,
        business_type_multiple_override_audit=business_type_multiple_override_audit,
        multiple_calibration_audit=multiple_calibration_audit,
    )


def resolve_effective_multiple_override(
    *,
    request,
    ebitda_basis: Decimal,
    model_effective_mid_multiple: Decimal,
    model_effective_low_multiple: Decimal,
    model_effective_high_multiple: Decimal,
) -> EffectiveMultipleOverrideState:
    """Resolve advisor effective-multiple override and preserve the model baseline audit."""
    effective_mid_multiple = model_effective_mid_multiple
    effective_low_multiple = model_effective_low_multiple
    effective_high_multiple = model_effective_high_multiple
    raw_effective_multiple_override = getattr(request, "effective_multiple_override", None)
    if raw_effective_multiple_override is None:
        return EffectiveMultipleOverrideState(
            effective_mid_multiple=effective_mid_multiple,
            effective_low_multiple=effective_low_multiple,
            effective_high_multiple=effective_high_multiple,
            audit=None,
            raw_override_present=False,
        )

    advisor_effective_multiple = safe_decimal_or_zero(raw_effective_multiple_override)
    if ebitda_basis <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "INVALID_EFFECTIVE_MULTIPLE_OVERRIDE",
                "message": "effective_multiple_override requires positive EBITDA.",
            },
        )
    if advisor_effective_multiple <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "INVALID_EFFECTIVE_MULTIPLE_OVERRIDE",
                "message": "effective_multiple_override must be positive.",
            },
        )

    verdict = check_effective_multiple(
        advisor_effective_multiple, model_value=model_effective_mid_multiple
    )
    out_of_band = enforce_override_governance(
        verdict,
        lever="effective_multiple",
        confirmed=bool(getattr(request, "override_out_of_band_confirmed", False)),
    )

    override_delta = advisor_effective_multiple - model_effective_mid_multiple
    effective_mid_multiple = advisor_effective_multiple
    effective_low_multiple = max(Decimal("0"), model_effective_low_multiple + override_delta)
    effective_high_multiple = max(Decimal("0"), model_effective_high_multiple + override_delta)
    audit = {
        "source": "advisor_override",
        "out_of_band": out_of_band,
        "index_protected": True,
        "advisor_id": getattr(request, "advisor_id", None),
        "timestamp": utc_now_iso(),
        "model_effective_multiple": safe_float(model_effective_mid_multiple),
        "advisor_effective_multiple": safe_float(advisor_effective_multiple),
        "delta_multiple": safe_float(override_delta),
        "model_enterprise_value": safe_float(ebitda_basis * model_effective_mid_multiple),
        "advisor_enterprise_value": safe_float(ebitda_basis * advisor_effective_multiple),
        "note": getattr(request, "effective_multiple_override_note", None),
    }
    return EffectiveMultipleOverrideState(
        effective_mid_multiple=effective_mid_multiple,
        effective_low_multiple=effective_low_multiple,
        effective_high_multiple=effective_high_multiple,
        audit=audit,
        raw_override_present=True,
    )
