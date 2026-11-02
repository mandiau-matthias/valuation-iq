"""Govern advisor method weights before they can change a priced valuation."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

from src.api.schemas.stateless_api import CalculateRequest, TriageFlag
from src.services.reports.public_adaptive_profile import (
    public_adaptive_weights_are_authorized,
)

_PRICED_STATES = {"accepted", "edited"}
_FIELDS = {"user_weights", "methodology_weights"}
_CATEGORIES = {"methodology_weighting", "method_weights", "valuation_synthesis"}


def apply_method_weight_governance(
    request: CalculateRequest,
) -> tuple[CalculateRequest, list[TriageFlag]]:
    """Keep unreviewed advisor weights as a scenario, never a priced blend."""
    if not request.user_weights:
        return request, []
    if public_adaptive_weights_are_authorized(request):
        return request, []
    if _matching_weight_decision(request):
        return request, []
    return (
        request.model_copy(
            update={"user_weights": None, "user_weight_justification": None}
        ),
        [
            TriageFlag(
                field="user_weights",
                issue="advisor_method_weights_scenario_only_unverified",
                severity="warning",
                value={
                    "submitted_weights": dict(request.user_weights),
                    "required_proof": (
                        "accepted evidence-linked methodology-weighting decision "
                        "bound to the exact weights and justification"
                    ),
                },
            )
        ],
    )


def _matching_weight_decision(request: CalculateRequest) -> bool:
    case = request.valuation_case
    if case is None or not case.evidence_revision_id:
        return False
    expected = _normalized_weights(request.user_weights)
    justification = str(request.user_weight_justification or "").strip()
    if expected is None or not justification:
        return False
    for decision in case.authoritative_input_decisions:
        if decision.state not in _PRICED_STATES:
            continue
        if str(decision.field_key).strip().lower() not in _FIELDS:
            continue
        if str(decision.category).strip().lower() not in _CATEGORIES:
            continue
        if not (
            str(decision.evidence_id).strip()
            and str(decision.rule_version or "").strip()
            and str(decision.decided_by or "").strip()
            and decision.decided_at is not None
        ):
            continue
        payload = decision.value_payload
        if not isinstance(payload, Mapping):
            continue
        if _normalized_weights(payload.get("weights")) != expected:
            continue
        if str(payload.get("justification") or "").strip() != justification:
            continue
        return True
    return False


def _normalized_weights(value: object) -> dict[str, Decimal] | None:
    if not isinstance(value, Mapping):
        return None
    normalized: dict[str, Decimal] = {}
    for key, raw in value.items():
        try:
            weight = raw if isinstance(raw, Decimal) else Decimal(str(raw))
        except (InvalidOperation, TypeError, ValueError):
            return None
        if not weight.is_finite():
            return None
        normalized[str(key)] = weight.normalize()
    return normalized
