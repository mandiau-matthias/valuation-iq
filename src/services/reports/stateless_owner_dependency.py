"""Apply the canonical 12-factor transferability adjustment exactly once."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from src.api.schemas.stateless_api import CalculateRequest
from src.domain.synthesis.owner_dependency_processor import OwnerDependencyProcessor
from src.utils.decimal_helpers import safe_decimal_or_zero

_PRICED_DECISION_STATES = {"accepted", "edited"}
_OWNER_FACTOR_CATEGORIES = {
    "owner_dependency",
    "owner_dependency_factor",
    "owner_transferability",
}
_OWNER_FACTOR_FIELD = "owner_dependency_factors"


@dataclass(frozen=True)
class StatelessOwnerDependencyState:
    result: dict[str, object] | None
    adjustment: Decimal
    equity_value_low: Decimal
    equity_value_mid: Decimal
    equity_value_high: Decimal
    recommended_asking_price: Decimal
    risk_factors: list[str]


def apply_stateless_owner_dependency(
    *,
    request: CalculateRequest,
    equity_value_low: Decimal,
    equity_value_mid: Decimal,
    equity_value_high: Decimal,
    recommended_asking_price: Decimal,
    risk_factors: object,
    valuation_results: Mapping[str, object],
) -> StatelessOwnerDependencyState:
    """Apply a single disclosed equity-side owner-dependency adjustment."""
    factors = request.owner_dependency_factors
    existing_risks = [str(item) for item in (risk_factors or [])]
    if factors is None:
        return StatelessOwnerDependencyState(
            result=None,
            adjustment=Decimal("0"),
            equity_value_low=equity_value_low,
            equity_value_mid=equity_value_mid,
            equity_value_high=equity_value_high,
            recommended_asking_price=recommended_asking_price,
            risk_factors=existing_risks,
        )

    governance_reason = _owner_factor_governance_failure(request)
    if governance_reason is not None:
        return StatelessOwnerDependencyState(
            result={
                "status": "scenario_only_unverified",
                "priced": False,
                "reason": governance_reason,
                "required_proof": (
                    "An accepted or edited, evidence-linked owner-dependency decision "
                    "bound to the exact reviewed factor payload, reviewer, timestamp and "
                    "rule version"
                ),
            },
            adjustment=Decimal("0"),
            equity_value_low=equity_value_low,
            equity_value_mid=equity_value_mid,
            equity_value_high=equity_value_high,
            recommended_asking_price=recommended_asking_price,
            risk_factors=[
                *existing_risks,
                "Owner-dependency factors are scenario-only until evidence is reviewed.",
            ],
        )

    eligible_methods = [
        str(method_key)
        for method_key, method in valuation_results.items()
        if bool(getattr(method, "available", False))
    ]
    business_context = request.business_context if isinstance(request.business_context, Mapping) else {}
    owner_hours = business_context.get("owner_hours_per_week")
    try:
        owner_hours_value = int(owner_hours) if owner_hours is not None else None
    except (TypeError, ValueError):
        owner_hours_value = None
    owner_count = factors.number_of_owners or 1
    if request.ownership_summary is not None and request.ownership_summary.working_owner_count > 0:
        owner_count = request.ownership_summary.working_owner_count

    processor = OwnerDependencyProcessor(financial_data=None, transparency_collector=None)
    (
        result,
        adjustment,
        adjusted_low,
        adjusted_mid,
        adjusted_high,
        adjusted_asking,
        updated_risks,
    ) = processor.process_owner_dependency(
        owner_dependency_factors=factors,
        equity_value_low=equity_value_low,
        equity_value_mid=equity_value_mid,
        equity_value_high=equity_value_high,
        recommended_asking_price=recommended_asking_price,
        risk_factors=existing_risks,
        owner_hours_per_week=owner_hours_value,
        eligible_methods=eligible_methods,
        owner_count=owner_count,
    )
    result_payload = result.model_dump(mode="json") if result is not None else None
    return StatelessOwnerDependencyState(
        result=result_payload,
        adjustment=safe_decimal_or_zero(adjustment),
        equity_value_low=max(Decimal("0"), safe_decimal_or_zero(adjusted_low)).quantize(
            Decimal("0.01")
        ),
        equity_value_mid=max(Decimal("0"), safe_decimal_or_zero(adjusted_mid)).quantize(
            Decimal("0.01")
        ),
        equity_value_high=max(Decimal("0"), safe_decimal_or_zero(adjusted_high)).quantize(
            Decimal("0.01")
        ),
        recommended_asking_price=max(
            Decimal("0"), safe_decimal_or_zero(adjusted_asking)
        ).quantize(Decimal("0.01")),
        risk_factors=list(updated_risks),
    )


def _owner_factor_governance_failure(request: CalculateRequest) -> str | None:
    """Require Titan's immutable decision envelope before factors affect price."""
    valuation_case = request.valuation_case
    if valuation_case is None or not valuation_case.evidence_revision_id:
        return "missing versioned ValuationCase evidence revision"

    expected_payload = request.owner_dependency_factors.model_dump(
        mode="json",
        exclude_none=True,
    )
    governed = []
    for decision in valuation_case.authoritative_input_decisions:
        field_key = str(decision.field_key).strip().lower()
        category = str(decision.category).strip().lower()
        if decision.state not in _PRICED_DECISION_STATES:
            continue
        if field_key != _OWNER_FACTOR_FIELD or category not in _OWNER_FACTOR_CATEGORIES:
            continue
        if not (
            str(decision.evidence_id).strip()
            and str(decision.rule_version or "").strip()
            and str(decision.decided_by or "").strip()
            and decision.decided_at is not None
        ):
            continue
        if decision.value_payload != expected_payload:
            continue
        governed.append(decision)

    if not governed:
        return "missing accepted evidence-linked owner-dependency decision"
    return None
