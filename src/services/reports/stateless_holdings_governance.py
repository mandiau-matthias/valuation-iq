"""Evidence governance for raw assumptions used by holding valuations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from src.api.schemas.stateless_api import CalculateRequest

_PRICED_DECISION_STATES = {"accepted", "edited"}
_SOTP_DECISION_CATEGORIES = {
    "holding_sotp",
    "holding_sotp_assumption",
    "holding_entity_valuation",
    "holding_valuation",
    "holding_structure",
    "intercompany_elimination",
    "ownership",
    "ownership_assumption",
    "participation_book_value",
}
_CONSOLIDATED_ELIMINATION_FIELDS = {
    "revenue",
    "ebitda",
    "equity",
    "net_income",
    "total_assets",
    "net_debt",
}


@dataclass(frozen=True)
class AssumptionGovernanceVerdict:
    """Result of binding a submitted assumption to accepted governance."""

    priced: bool
    source: str | None = None
    reason: str | None = None


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _first_decimal(*values: object) -> Decimal | None:
    for value in values:
        if value is not None and value != "":
            try:
                parsed = value if isinstance(value, Decimal) else Decimal(str(value))
            except (InvalidOperation, TypeError, ValueError):
                continue
            if parsed.is_finite():
                return parsed
    return None


def _first_decimal_field(
    row: Mapping[str, object],
    *field_names: str,
) -> tuple[str | None, Decimal | None]:
    for field_name in field_names:
        if field_name not in row:
            continue
        parsed = _first_decimal(row.get(field_name))
        if parsed is not None:
            return field_name, parsed
    return None, None


def _record_value(record: object, field_name: str) -> object:
    if isinstance(record, Mapping):
        return record.get(field_name)
    return getattr(record, field_name, None)


def _governance_bound_amount(record: object, *, field_name: str) -> Decimal | None:
    for key in ("signed_amount", "amount", "value"):
        parsed = _first_decimal(_record_value(record, key))
        if parsed is not None:
            return parsed
    payload = _record_value(record, "value_payload")
    if isinstance(payload, Mapping):
        for key in (field_name, "signed_amount", "amount", "value"):
            parsed = _first_decimal(payload.get(key))
            if parsed is not None:
                return parsed
    return None


def assumption_governance(
    request: CalculateRequest,
    *,
    field_name: str,
    field_path: str,
    value: Decimal,
    monetary: bool,
    parent_currency: str | None,
    decision_path_aliases: tuple[str, ...] = (),
) -> AssumptionGovernanceVerdict:
    """Bind one priced raw assumption to its exact accepted value.

    A status, revision string or evidence reference inside the open holdings
    payload is not a trust anchor. Only the canonical ``ValuationCase``
    decision envelope can approve a submitted raw amount; code-owned policies
    are applied explicitly at their derivation sites. The governed amount must
    equal the value used by the SOTP arithmetic, so stale approval metadata
    cannot bless a new value.
    """

    candidate_reasons: set[str] = set()
    accepted_paths = {
        field_path.strip().casefold(),
        *(path.strip().casefold() for path in decision_path_aliases),
    }
    valuation_case = request.valuation_case
    if valuation_case is not None:
        for decision in valuation_case.authoritative_input_decisions:
            if str(decision.field_key).strip().casefold() not in accepted_paths:
                continue
            if (
                decision.state not in _PRICED_DECISION_STATES
                or str(decision.category).strip().casefold() not in _SOTP_DECISION_CATEGORIES
                or not valuation_case.evidence_revision_id
                or not str(decision.decision_id).strip()
                or not str(decision.evidence_id).strip()
                or not str(decision.rule_version or "").strip()
                or not str(decision.decided_by or "").strip()
                or decision.decided_at is None
            ):
                candidate_reasons.add("governance_incomplete")
                continue
            currency = str(decision.currency or "").strip().upper()
            if monetary and (not parent_currency or not currency or currency != parent_currency):
                candidate_reasons.add("governance_currency_mismatch")
                continue
            if not monetary and currency and parent_currency and currency != parent_currency:
                candidate_reasons.add("governance_currency_mismatch")
                continue
            bound_amount = _governance_bound_amount(
                decision,
                field_name=field_name,
            )
            if bound_amount is None:
                candidate_reasons.add("governance_value_unbound")
                continue
            if bound_amount != value:
                candidate_reasons.add("governance_value_mismatch")
                continue
            return AssumptionGovernanceVerdict(
                priced=True,
                source=f"valuation_case:{decision.decision_id}",
            )

    reason_priority = (
        "governance_value_mismatch",
        "governance_currency_mismatch",
        "governance_value_unbound",
        "governance_incomplete",
    )
    reason = next(
        (candidate for candidate in reason_priority if candidate in candidate_reasons),
        "accepted_decision_or_versioned_policy_required",
    )
    return AssumptionGovernanceVerdict(priced=False, reason=reason)


def unpriced_assumption(
    *,
    field_path: str,
    value: object,
    verdict: AssumptionGovernanceVerdict,
) -> dict[str, object]:
    """Build the visible scenario-only record for an excluded assumption."""

    return {
        "field": field_path,
        "status": "scenario_only_unverified",
        "reason": verdict.reason or "accepted_decision_or_versioned_policy_required",
        "submitted_value": value,
        "required_proof": (
            "accepted evidence-linked decision or versioned policy bound to the exact "
            "assumption value"
        ),
    }


def consolidation_governance_issues(
    request: CalculateRequest,
    *,
    payload: object,
    parent_currency: str | None,
) -> list[dict[str, object]]:
    """Find ungoverned raw assumptions that would alter operating inputs."""

    issues: list[dict[str, object]] = []
    subsidiaries = list(getattr(payload, "subsidiaries", None) or [])
    for index, raw in enumerate(subsidiaries):
        subsidiary = _mapping(raw)
        ownership_field, ownership = _first_decimal_field(
            subsidiary,
            "ownership_pct",
            "ownership_pct_in_parent",
            "parent_ownership_pct",
        )
        if ownership_field is None or ownership is None:
            continue
        field_path = f"holdings_consolidation.subsidiaries[{index}].{ownership_field}"
        verdict = assumption_governance(
            request,
            field_name=ownership_field,
            field_path=field_path,
            value=ownership,
            monetary=False,
            parent_currency=parent_currency,
        )
        if not verdict.priced:
            issues.append(
                unpriced_assumption(
                    field_path=field_path,
                    value=ownership,
                    verdict=verdict,
                )
            )

    eliminations = _mapping(getattr(payload, "eliminations", None))
    for field_name in sorted(_CONSOLIDATED_ELIMINATION_FIELDS):
        amount = _first_decimal(eliminations.get(field_name))
        if amount is None or amount == 0:
            continue
        effective_amount = abs(amount)
        field_path = f"holdings_consolidation.eliminations.{field_name}"
        verdict = assumption_governance(
            request,
            field_name=field_name,
            field_path=field_path,
            value=effective_amount,
            monetary=True,
            parent_currency=parent_currency,
        )
        if not verdict.priced:
            issues.append(
                unpriced_assumption(
                    field_path=field_path,
                    value=effective_amount,
                    verdict=verdict,
                )
            )

    transactions = list(getattr(payload, "intercompany_transactions", None) or [])
    for index, raw in enumerate(transactions):
        transaction = _mapping(raw)
        if not any(
            bool(transaction.get(key))
            for key in ("is_intercompany", "intercompany", "related_party")
        ):
            continue
        amount = _first_decimal(transaction.get("amount"))
        if amount is None or amount == 0:
            continue
        line = str(
            transaction.get("line")
            or transaction.get("financial_line")
            or transaction.get("metric")
            or "revenue"
        ).strip()
        if line not in _CONSOLIDATED_ELIMINATION_FIELDS:
            continue
        effective_amount = abs(amount)
        field_path = f"holdings_consolidation.intercompany_transactions[{index}].{line}.amount"
        verdict = assumption_governance(
            request,
            field_name="amount",
            field_path=field_path,
            value=effective_amount,
            monetary=True,
            parent_currency=parent_currency,
        )
        if not verdict.priced:
            issues.append(
                unpriced_assumption(
                    field_path=field_path,
                    value=effective_amount,
                    verdict=verdict,
                )
            )
    return issues
