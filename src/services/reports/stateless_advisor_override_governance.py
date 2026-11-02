"""Evidence-bind manual advisor controls before they can change priced economics."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from src.api.schemas.stateless_api import CalculateRequest, TriageFlag

_PRICED_STATES = {"accepted", "edited"}


@dataclass(frozen=True)
class _Override:
    field: str
    expected: object
    justification: str | None
    categories: frozenset[str]
    updates: Mapping[str, object]


def apply_advisor_override_governance(
    request: CalculateRequest,
) -> tuple[CalculateRequest, list[TriageFlag]]:
    """Demote unverified manual controls to disclosed, non-priced scenarios."""
    overrides = _active_overrides(request)
    if not overrides:
        return request, []

    updates: dict[str, object] = {}
    flags: list[TriageFlag] = []
    for override in overrides:
        if _has_exact_decision(request, override):
            continue
        updates.update(override.updates)
        flags.append(
            TriageFlag(
                field=override.field,
                issue="advisor_override_scenario_only_unverified",
                severity="warning",
                value={
                    "submitted_value": _json_safe(override.expected),
                    "submitted_justification": override.justification,
                    "required_proof": (
                        "accepted evidence-linked decision bound to the exact value, "
                        "rule version, reviewer and decision timestamp"
                    ),
                },
            )
        )
    if not updates:
        return request, flags
    if any(
        field in updates
        for field in (
            "multiple_calibration_adjustment",
            "business_type_multiple_overrides",
            "effective_multiple_override",
        )
    ):
        updates["override_out_of_band_confirmed"] = False
    return request.model_copy(update=updates), flags


def _active_overrides(request: CalculateRequest) -> list[_Override]:
    overrides: list[_Override] = []
    metadata = request.metadata if isinstance(request.metadata, Mapping) else {}
    public_resolution = (
        metadata.get("public_adaptive_resolution")
        if isinstance(metadata.get("public_adaptive_resolution"), Mapping)
        else {}
    )
    machine_public_policy = (
        (
            (
                metadata.get("public_adaptive_profile_v2") is True
                and public_resolution.get("schema_version") == "public_adaptive_profile.v2"
            )
            or (
                metadata.get("public_adaptive_profile_v1") is True
                and public_resolution.get("schema_version") == "public_adaptive_profile.v1"
            )
        )
        and public_resolution.get("producer_contract_hash")
        == (
            metadata.get("public_adaptive_producer_contract", {}).get("contract_hash")
            if isinstance(metadata.get("public_adaptive_producer_contract"), Mapping)
            else None
        )
    )
    if request.business_type_segments:
        primary_business_type = request.business_type_calibration.business_type_id
        overrides.append(
            _Override(
                field="business_type_segments",
                expected=request.business_type_segments,
                justification=None,
                categories=frozenset(
                    {
                        "advisor_override",
                        "segment_sotp",
                        "transaction_perimeter",
                        "valuation_synthesis",
                    }
                ),
                updates={
                    "business_type_segments": None,
                    # CalculateRequest normalizes segment identities into the
                    # benchmark mix before this pricing boundary. Remove that
                    # derived influence too when the underlying SOTP schedule
                    # is not governed, otherwise an unpriced scenario could
                    # still select a different benchmark blend.
                    "business_type_mix": [
                        {"business_type_id": primary_business_type, "weight": 100}
                    ],
                    "business_type_weights": {primary_business_type: 100},
                },
            )
        )
    if request.asking_price_buffer_pct is not None:
        overrides.append(
            _Override(
                field="asking_price_buffer_pct",
                expected=request.asking_price_buffer_pct,
                justification=None,
                categories=frozenset(
                    {"advisor_override", "asking_price_policy", "transaction_pricing"}
                ),
                updates={"asking_price_buffer_pct": None},
            )
        )
    if request.multiple_calibration_adjustment not in (None, Decimal("0")):
        overrides.append(
            _Override(
                field="multiple_calibration_adjustment",
                expected=request.multiple_calibration_adjustment,
                justification=_text(request.multiple_calibration_note),
                categories=frozenset({"advisor_override", "multiple_override"}),
                updates={
                    "multiple_calibration_adjustment": None,
                    "multiple_calibration_note": None,
                },
            )
        )
    if request.business_type_multiple_overrides:
        overrides.append(
            _Override(
                field="business_type_multiple_overrides",
                expected=request.business_type_multiple_overrides,
                justification=_text(request.business_type_multiple_override_note),
                categories=frozenset({"advisor_override", "multiple_override"}),
                updates={
                    "business_type_multiple_overrides": None,
                    "business_type_multiple_override_note": None,
                },
            )
        )
    if request.effective_multiple_override is not None:
        overrides.append(
            _Override(
                field="effective_multiple_override",
                expected=request.effective_multiple_override,
                justification=_text(request.effective_multiple_override_note),
                categories=frozenset({"advisor_override", "multiple_override"}),
                updates={
                    "effective_multiple_override": None,
                    "effective_multiple_override_note": None,
                },
            )
        )
    if request.multiple_type_weights:
        overrides.append(
            _Override(
                field="multiple_type_weights",
                expected=request.multiple_type_weights,
                justification=None,
                categories=frozenset({"advisor_override", "methodology_weighting"}),
                updates={"multiple_type_weights": None},
            )
        )
    if request.risk_analysis_enabled is False and not machine_public_policy:
        overrides.append(
            _Override(
                field="risk_analysis_enabled",
                expected=False,
                justification=None,
                categories=frozenset({"advisor_override", "discount_policy"}),
                updates={"risk_analysis_enabled": True},
            )
        )
    if request.advisor_discount_weights:
        overrides.append(
            _Override(
                field="advisor_discount_weights",
                expected=request.advisor_discount_weights,
                justification=None,
                categories=frozenset({"advisor_override", "discount_policy"}),
                updates={"advisor_discount_weights": None},
            )
        )
    if request.discount_floor_factor is not None:
        overrides.append(
            _Override(
                field="discount_floor_factor",
                expected=request.discount_floor_factor,
                justification=None,
                categories=frozenset({"advisor_override", "discount_policy"}),
                updates={"discount_floor_factor": None},
            )
        )
    if (
        request.historical_ebitda_weighting_mode in {"weighted", "current_year"}
        and not machine_public_policy
    ):
        overrides.append(
            _Override(
                field="historical_ebitda_weighting",
                expected={
                    "mode": request.historical_ebitda_weighting_mode,
                    "weights": request.historical_ebitda_weights or {},
                },
                justification=None,
                categories=frozenset({"advisor_override", "historical_weighting"}),
                updates={
                    "historical_ebitda_weighting_mode": "standard",
                    "historical_ebitda_weights": None,
                },
            )
        )
    return overrides


def _has_exact_decision(request: CalculateRequest, override: _Override) -> bool:
    case = request.valuation_case
    if case is None or not _text(case.evidence_revision_id):
        return False
    for decision in case.authoritative_input_decisions:
        if decision.state not in _PRICED_STATES:
            continue
        if str(decision.field_key).strip() != override.field:
            continue
        if str(decision.category).strip().lower() not in override.categories:
            continue
        if not (
            _text(decision.evidence_id)
            and _text(decision.rule_version)
            and _text(decision.decided_by)
            and decision.decided_at is not None
        ):
            continue
        payload = decision.value_payload
        if not isinstance(payload, Mapping) or "value" not in payload:
            continue
        if not _exact_value(override.expected, payload.get("value")):
            continue
        if (
            override.justification is not None
            and str(payload.get("justification") or "").strip() != override.justification
        ):
            continue
        return True
    return False


def _exact_value(expected: object, actual: object) -> bool:
    if isinstance(expected, Mapping):
        if not isinstance(actual, Mapping):
            return False
        expected_by_key = {str(key): value for key, value in expected.items()}
        actual_by_key = {str(key): value for key, value in actual.items()}
        if set(expected_by_key) != set(actual_by_key):
            return False
        return all(
            _exact_value(value, actual_by_key[key]) for key, value in expected_by_key.items()
        )
    if isinstance(expected, Sequence) and not isinstance(expected, (str, bytes, bytearray)):
        if not isinstance(actual, Sequence) or isinstance(actual, (str, bytes, bytearray)):
            return False
        return len(expected) == len(actual) and all(
            _exact_value(expected_item, actual_item)
            for expected_item, actual_item in zip(expected, actual)
        )
    if isinstance(expected, bool):
        return isinstance(actual, bool) and actual is expected
    if isinstance(expected, (Decimal, int, float)) and not isinstance(expected, bool):
        try:
            actual_decimal = Decimal(str(actual))
            expected_decimal = Decimal(str(expected))
        except (InvalidOperation, TypeError, ValueError):
            return False
        return actual_decimal.is_finite() and actual_decimal == expected_decimal
    return actual == expected


def _json_safe(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, Decimal):
        return str(value)
    return value


def _text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None
