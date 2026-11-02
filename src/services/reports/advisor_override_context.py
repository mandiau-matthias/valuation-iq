"""Advisor override context builders for valuation reports."""

from collections.abc import Mapping
from decimal import Decimal
from typing import cast

from src.services.reports.protocol_adapter import _attr
from src.services.reports.report_benchmark_contracts import as_plain_mapping
from src.services.reports.report_metadata_access import (
    get_metadata_bool,
    get_metadata_float,
    get_metadata_str,
)
from src.utils.decimal_helpers import optional_decimal, safe_decimal_or_zero, safe_float


def _first_nonzero_decimal(*values: object) -> Decimal | None:
    for value in values:
        parsed = optional_decimal(value)
        if parsed is not None and parsed != Decimal("0"):
            return cast(Decimal, parsed)
    return None


def _first_present(*values: object) -> object | None:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def _optional_safe_float(value: object) -> float | None:
    parsed = optional_decimal(value)
    return safe_float(parsed) if parsed is not None else None


def _multiple_calibration_payload(
    request_metadata: Mapping[str, object],
) -> Mapping[str, object]:
    raw_multiple_calibration = request_metadata.get("multiple_calibration") or request_metadata.get(
        "advisor_multiple_calibration"
    )
    return as_plain_mapping(raw_multiple_calibration) or {}


def _effective_override_audit_payload(
    *,
    request_metadata: Mapping[str, object],
    multiple_calibration: Mapping[str, object],
    explicit_audit: Mapping[str, object] | None,
) -> Mapping[str, object]:
    return (
        explicit_audit
        or as_plain_mapping(request_metadata.get("effective_multiple_override_audit"))
        or as_plain_mapping(multiple_calibration.get("effective_multiple_override_audit"))
        or {}
    )


def _manual_calibration_adjustment(
    *,
    request: object | None,
    request_metadata: Mapping[str, object],
    multiple_calibration: Mapping[str, object],
) -> Decimal | None:
    adjustment = (
        optional_decimal(_attr(request, "multiple_calibration_adjustment", None))
        if request
        else None
    )
    if adjustment is not None:
        return adjustment
    return _first_nonzero_decimal(
        multiple_calibration.get("specific_risk_quality_premium"),
        request_metadata.get("multiple_calibration_adjustment"),
    )


def _effective_multiple_override(
    *,
    request: object | None,
    request_metadata: Mapping[str, object],
    multiple_calibration: Mapping[str, object],
    effective_override_audit: Mapping[str, object],
) -> Decimal | None:
    override = (
        optional_decimal(_attr(request, "effective_multiple_override", None)) if request else None
    )
    if override is not None:
        return override
    return optional_decimal(
        _first_present(
            request_metadata.get("effective_multiple_override"),
            multiple_calibration.get("effective_multiple_override"),
            multiple_calibration.get("advisor_effective_multiple"),
            effective_override_audit.get("advisor_effective_multiple"),
            effective_override_audit.get("effective_multiple_override"),
        )
    )


def _manual_calibration_context(
    *,
    request: object | None,
    request_metadata: Mapping[str, object],
    multiple_calibration: Mapping[str, object],
    applied_multiple: Decimal,
    manual_adjustment: Decimal | None,
) -> dict[str, object]:
    if manual_adjustment is None or manual_adjustment == Decimal("0"):
        return {}

    calibrated_multiple = _first_nonzero_decimal(
        multiple_calibration.get("calibrated_multiple"),
        request_metadata.get("calibrated_multiple"),
    )
    if calibrated_multiple is None:
        calibrated_multiple = cast(Decimal, safe_decimal_or_zero(applied_multiple))

    sector_average_multiple = _first_nonzero_decimal(
        multiple_calibration.get("sector_average_multiple"),
        request_metadata.get("sector_average_multiple"),
    )
    if sector_average_multiple is None:
        sector_average_multiple = calibrated_multiple - cast(Decimal, manual_adjustment)

    return {
        "sector_average_multiple": safe_float(sector_average_multiple),
        "specific_risk_quality_premium": safe_float(manual_adjustment),
        "calibrated_multiple": safe_float(calibrated_multiple),
        "note": (_attr(request, "multiple_calibration_note", None) if request else None)
        or request_metadata.get("multiple_calibration_note")
        or multiple_calibration.get("note"),
    }


def _effective_override_context(
    *,
    request: object | None,
    request_metadata: Mapping[str, object],
    multiple_calibration: Mapping[str, object],
    effective_override_audit: Mapping[str, object],
    effective_multiple_override: Decimal | None,
) -> dict[str, object]:
    if effective_multiple_override is None or effective_multiple_override == Decimal("0"):
        return {}

    return {
        "effective_multiple_override": safe_float(effective_multiple_override),
        "effective_multiple_override_note": (
            _attr(request, "effective_multiple_override_note", None) if request else None
        )
        or request_metadata.get("effective_multiple_override_note")
        or multiple_calibration.get("effective_multiple_override_note")
        or effective_override_audit.get("note"),
        "model_effective_multiple": _optional_safe_float(
            effective_override_audit.get("model_effective_multiple")
        ),
        "advisor_effective_multiple": _optional_safe_float(
            effective_override_audit.get("advisor_effective_multiple")
        )
        or safe_float(effective_multiple_override),
        "delta_multiple": _optional_safe_float(effective_override_audit.get("delta_multiple")),
    }


def build_advisor_multiple_calibration(
    *,
    request: object | None,
    request_metadata: Mapping[str, object],
    applied_multiple: Decimal,
    effective_multiple_override_audit: Mapping[str, object] | None = None,
) -> dict[str, object] | None:
    """Build context for advisor-entered multiple calibration overrides."""
    multiple_calibration = _multiple_calibration_payload(request_metadata)
    effective_override_audit = _effective_override_audit_payload(
        request_metadata=request_metadata,
        multiple_calibration=multiple_calibration,
        explicit_audit=effective_multiple_override_audit,
    )
    manual_adjustment = _manual_calibration_adjustment(
        request=request,
        request_metadata=request_metadata,
        multiple_calibration=multiple_calibration,
    )
    effective_override = _effective_multiple_override(
        request=request,
        request_metadata=request_metadata,
        multiple_calibration=multiple_calibration,
        effective_override_audit=effective_override_audit,
    )

    if (manual_adjustment is None or manual_adjustment == Decimal("0")) and (
        effective_override is None or effective_override == Decimal("0")
    ):
        return None

    context = _manual_calibration_context(
        request=request,
        request_metadata=request_metadata,
        multiple_calibration=multiple_calibration,
        applied_multiple=applied_multiple,
        manual_adjustment=manual_adjustment,
    )
    context.update(
        _effective_override_context(
            request=request,
            request_metadata=request_metadata,
            multiple_calibration=multiple_calibration,
            effective_override_audit=effective_override_audit,
            effective_multiple_override=effective_override,
        )
    )
    return context


def build_advisor_real_estate_treatment(
    *,
    request: object | None,
    request_metadata: Mapping[str, object],
) -> dict[str, object] | None:
    """Build context for advisor-entered real-estate transaction treatment."""
    if request is None:
        return None

    raw_report_treatment = request_metadata.get("real_estate_treatment")
    real_estate_metadata = _advisor_real_estate_metadata(
        request_metadata=request_metadata,
        raw_report_treatment=raw_report_treatment,
    )
    treatment = _advisor_real_estate_treatment(
        request=request,
        raw_report_treatment=raw_report_treatment,
        real_estate_metadata=real_estate_metadata,
    )
    if treatment is None:
        return None

    market_value = _advisor_real_estate_decimal(
        request=request,
        request_metadata=request_metadata,
        real_estate_metadata=real_estate_metadata,
        request_key="real_estate_market_value",
        metadata_key="real_estate_market_value",
        nested_keys=("real_estate_market_value", "market_value"),
    )
    book_value = _advisor_real_estate_decimal(
        request=request,
        request_metadata=request_metadata,
        real_estate_metadata=real_estate_metadata,
        request_key="real_estate_book_value",
        metadata_key="real_estate_book_value",
        nested_keys=("real_estate_book_value", "book_value"),
    )
    market_rent = _advisor_real_estate_decimal(
        request=request,
        request_metadata=request_metadata,
        real_estate_metadata=real_estate_metadata,
        request_key="estimated_market_rent",
        metadata_key="estimated_market_rent",
        nested_keys=("estimated_market_rent", "market_rent"),
    )

    return {
        "treatment": treatment,
        "market_value": safe_float(market_value) if market_value is not None else None,
        "book_value": safe_float(book_value) if book_value is not None else None,
        "estimated_market_rent": safe_float(market_rent) if market_rent is not None else None,
        "property_bridge_value": _advisor_real_estate_bridge_value(
            treatment,
            market_value,
        ),
        # Disclosure of the advisor's own inputs, not a bridge line item: the
        # audit trail labels this "meerwaarde"/"surplus", so it must stay
        # market value minus book value.
        "surplus_value": _advisor_real_estate_surplus_value(market_value, book_value),
    }


def _advisor_real_estate_metadata(
    *,
    request_metadata: Mapping[str, object],
    raw_report_treatment: object,
) -> Mapping[str, object]:
    raw_real_estate_metadata = request_metadata.get("advisor_real_estate_treatment")
    if raw_real_estate_metadata is None and isinstance(raw_report_treatment, Mapping):
        raw_real_estate_metadata = raw_report_treatment
    raw_real_estate_metadata = raw_real_estate_metadata or request_metadata.get(
        "real_estate_treatment_details"
    )
    return as_plain_mapping(raw_real_estate_metadata) or {}


def _advisor_real_estate_treatment(
    *,
    request: object,
    raw_report_treatment: object,
    real_estate_metadata: Mapping[str, object],
) -> str | None:
    treatment = (
        str(
            _first_present(
                _attr(request, "real_estate_treatment", None),
                raw_report_treatment if not isinstance(raw_report_treatment, Mapping) else None,
                real_estate_metadata.get("real_estate_treatment"),
                real_estate_metadata.get("treatment"),
            )
            or ""
        )
        .strip()
        .lower()
    )
    if not treatment and bool(_attr(request, "exclude_real_estate", False)):
        treatment = "carve_out"
    return (
        treatment
        if treatment
        in {
            "carve_out",
            "included",
            "owned_included",
            "owned_excluded",
            "leased",
            "unresolved",
        }
        else None
    )


def _advisor_real_estate_decimal(
    *,
    request: object,
    request_metadata: Mapping[str, object],
    real_estate_metadata: Mapping[str, object],
    request_key: str,
    metadata_key: str,
    nested_keys: tuple[str, ...],
) -> Decimal | None:
    return optional_decimal(
        _first_present(
            _attr(request, request_key, None),
            request_metadata.get(metadata_key),
            *(real_estate_metadata.get(key) for key in nested_keys),
        )
    )


def _advisor_real_estate_bridge_value(
    treatment: str,
    market_value: Decimal | None,
) -> float | None:
    if treatment not in {"included", "owned_included"}:
        return 0.0
    return safe_float(market_value) if market_value is not None else None


def _advisor_real_estate_surplus_value(
    market_value: Decimal | None,
    book_value: Decimal | None,
) -> float | None:
    if market_value is None or book_value is None:
        return None
    return safe_float(market_value - book_value)


def build_method_override_context(request: object | None) -> dict[str, object]:
    """Build initial context for accountant manual method-selection overrides."""
    return {
        "method_override_visibility_locked": get_metadata_bool(
            request,
            "method_override_visibility_locked",
            False,
        ),
        "show_method_override": get_metadata_bool(request, "show_method_override", False),
        "method_override_selected_method": get_metadata_str(
            request,
            "method_override_selected_method",
        ),
        "method_override_label": get_metadata_str(request, "method_override_label"),
        "method_override_value": get_metadata_float(request, "method_override_value"),
        "method_override_reason": get_metadata_str(request, "method_override_reason"),
        "method_override_note": get_metadata_str(request, "method_override_note"),
        "method_override_date": get_metadata_str(request, "method_override_date"),
    }
