"""Canonical, Decimal-only shareholder-equity bridge adjustments.

The stateless request historically carried both ``tax_latencies`` and
``balance_sheet_adjustments`` while the calculation path ignored them.  This
module turns those accepted inputs into one itemized ledger and de-duplicates
tax rows that were serialized through both legacy fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from src.api.schemas.stateless_api import CalculateRequest, TriageFlag
from src.utils.decimal_helpers import safe_decimal_or_zero

_BRIDGE_DECISION_CATEGORIES = {
    "balance_sheet_adjustment",
    "enterprise_to_equity",
    "equity_bridge",
    "tax_latency",
}


def _status(value: object) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _authoritative_bridge_decisions(request: CalculateRequest) -> list[object]:
    valuation_case = request.valuation_case
    if valuation_case is None:
        return []
    return [
        decision
        for decision in valuation_case.authoritative_input_decisions
        if _status(getattr(decision, "state", None)) in {"accepted", "edited"}
        and _status(getattr(decision, "category", None)) in _BRIDGE_DECISION_CATEGORIES
    ]


def _same_decimal(left: object, right: object) -> bool:
    return safe_decimal_or_zero(left) == safe_decimal_or_zero(right)


def _payload_mapping(decision: object) -> dict[str, object] | None:
    value = getattr(decision, "value_payload", None)
    if not isinstance(value, dict):
        return None
    nested = value.get("bridge_row")
    return nested if isinstance(nested, dict) else value


def _decision_scope_matches(
    decision: object,
    row: object,
    *,
    valuation_currency: str | None,
) -> bool:
    row_id = str(getattr(row, "id", None) or "").strip()
    evidence_id = str(getattr(row, "evidence_id", None) or "").strip()
    row_currency = str(getattr(row, "currency", None) or "").strip().upper()
    decision_currency = str(getattr(decision, "currency", None) or "").strip().upper()
    if not row_id or not evidence_id or not valuation_currency:
        return False
    if row_currency != valuation_currency or decision_currency != valuation_currency:
        return False
    if str(getattr(decision, "evidence_id", None) or "").strip() != evidence_id:
        return False
    if getattr(decision, "fiscal_year", None) != getattr(row, "fiscal_year", None):
        return False
    return True


def _tax_decision_matches(
    decision: object,
    latency: object,
    *,
    valuation_currency: str | None,
) -> bool:
    if not _decision_scope_matches(
        decision,
        latency,
        valuation_currency=valuation_currency,
    ):
        return False
    row_id = str(getattr(latency, "id", None) or "").strip()
    field_key = str(getattr(decision, "field_key", None) or "").strip()
    if field_key not in {f"tax_latencies.{row_id}", f"tax_latencies.{row_id}.bridge_row"}:
        return False
    payload = _payload_mapping(decision)
    if payload is None:
        return False
    if not {"type", "temporary_difference", "tax_rate", "effective_date"}.issubset(payload):
        return False
    return bool(
        _status(payload.get("type")) == _status(getattr(latency, "type", None))
        and _same_decimal(
            payload.get("temporary_difference"),
            getattr(latency, "temporary_difference", None),
        )
        and _same_decimal(payload.get("tax_rate"), getattr(latency, "tax_rate", None))
        and str(payload.get("effective_date") or "").strip()
        == str(getattr(latency, "effective_date", None) or "").strip()
    )


def _balance_sheet_decision_matches(
    decision: object,
    adjustment: object,
    *,
    valuation_currency: str | None,
) -> bool:
    if not _decision_scope_matches(
        decision,
        adjustment,
        valuation_currency=valuation_currency,
    ):
        return False
    row_id = str(getattr(adjustment, "id", None) or "").strip()
    field_key = str(getattr(decision, "field_key", None) or "").strip()
    signed_amount = (
        safe_decimal_or_zero(getattr(adjustment, "amount", None))
        if getattr(adjustment, "type", None) == "add"
        else -safe_decimal_or_zero(getattr(adjustment, "amount", None))
    )
    if field_key == f"balance_sheet_adjustments.{row_id}.signed_amount":
        return (
            getattr(decision, "value_payload", None) is None
            and getattr(decision, "signed_amount", None) is not None
            and _same_decimal(getattr(decision, "signed_amount", None), signed_amount)
        )
    if field_key not in {
        f"balance_sheet_adjustments.{row_id}",
        f"balance_sheet_adjustments.{row_id}.bridge_row",
    }:
        return False
    payload = _payload_mapping(decision)
    if payload is None:
        return False
    if not {"type", "category", "amount", "effective_date"}.issubset(payload):
        return False
    if not (
        _status(payload.get("type")) == _status(getattr(adjustment, "type", None))
        and _status(payload.get("category")) == _status(getattr(adjustment, "category", None))
        and _same_decimal(payload.get("amount"), getattr(adjustment, "amount", None))
        and str(payload.get("effective_date") or "").strip()
        == str(getattr(adjustment, "effective_date", None) or "").strip()
    ):
        return False
    if getattr(adjustment, "category", None) != "tax_latency":
        return True
    if not {"temporary_difference", "tax_rate", "tax_latency_type"}.issubset(payload):
        return False
    return bool(
        _same_decimal(
            payload.get("temporary_difference"),
            getattr(adjustment, "temporary_difference", None),
        )
        and _same_decimal(payload.get("tax_rate"), getattr(adjustment, "tax_rate", None))
        and _status(payload.get("tax_latency_type"))
        == _status(getattr(adjustment, "tax_latency_type", None))
    )


def _matching_decision(
    decisions: list[object],
    row: object,
    *,
    valuation_currency: str | None,
    row_kind: str,
) -> object | None:
    matcher = (
        _tax_decision_matches if row_kind == "tax_latency" else _balance_sheet_decision_matches
    )
    matches = [
        decision
        for decision in decisions
        if matcher(decision, row, valuation_currency=valuation_currency)
    ]
    # Ambiguous authority is a hard exclusion, never a choose-first policy.
    return matches[0] if len(matches) == 1 else None


def _unpriced_status(row: object, *, valuation_currency: str | None) -> str:
    currency = str(getattr(row, "currency", None) or "").strip().upper()
    if not currency or not valuation_currency:
        return "unpriced_currency_unresolved"
    if currency != valuation_currency:
        return "unpriced_currency_mismatch"
    if _status(getattr(row, "status", None)) in {
        "accepted",
        "approved",
        "applied",
        "confirmed",
        "verified",
    }:
        return "scenario_only_unmatched_authoritative_decision"
    return _status(getattr(row, "status", None)) or "proposed"


@dataclass(frozen=True)
class StatelessBridgeAdjustmentLedger:
    rows: list[dict[str, object]]
    total: Decimal
    tax_latency_total: Decimal
    balance_sheet_adjustment_total: Decimal
    triage_flags: list[TriageFlag]

    def to_payload(self) -> dict[str, object]:
        return {
            "version": "stateless_equity_bridge_adjustments_v1",
            "value_basis": "equity_value",
            "currency_treatment": "request_currency",
            "rows": self.rows,
            "tax_latency_net_impact": self.tax_latency_total,
            "balance_sheet_adjustment_net_impact": self.balance_sheet_adjustment_total,
            "total_net_impact": self.total,
        }


def resolve_stateless_bridge_adjustments(
    request: CalculateRequest,
) -> StatelessBridgeAdjustmentLedger:
    """Resolve explicit bridge inputs once, preserving formulas and provenance."""
    rows: list[dict[str, object]] = []
    flags: list[TriageFlag] = []
    seen_tax_keys: set[tuple[str, ...]] = set()
    tax_total = Decimal("0")
    balance_sheet_total = Decimal("0")
    valuation_currency = request.currency
    authoritative_decisions = _authoritative_bridge_decisions(request)

    for index, adjustment in enumerate(request.balance_sheet_adjustments or []):
        amount = abs(safe_decimal_or_zero(adjustment.amount))
        signed_amount = amount if adjustment.type == "add" else -amount
        decision = _matching_decision(
            authoritative_decisions,
            adjustment,
            valuation_currency=valuation_currency,
            row_kind="balance_sheet_adjustment",
        )
        applied = decision is not None
        row = {
            "key": adjustment.id or f"balance_sheet_adjustment_{index + 1}",
            "label": adjustment.label,
            "category": adjustment.category,
            "operator": "+" if signed_amount >= 0 else "-",
            "amount": amount,
            "signed_amount": signed_amount,
            "description": adjustment.description,
            "account_code": adjustment.account_code,
            "source_contract": "balance_sheet_adjustments",
            "status": (
                _status(getattr(decision, "state", None))
                if applied
                else _unpriced_status(adjustment, valuation_currency=valuation_currency)
            ),
            "evidence_id": adjustment.evidence_id,
            "reviewed_at": adjustment.reviewed_at,
            "rule_version": adjustment.rule_version,
            "approved_by": adjustment.approved_by,
            "currency": adjustment.currency,
            "fiscal_year": adjustment.fiscal_year,
            "effective_date": adjustment.effective_date,
            "decision_id": getattr(decision, "decision_id", None),
            "decision_content_hash": getattr(decision, "content_hash", None),
            "policy_version": getattr(decision, "policy_version", None),
            "applied": applied,
        }
        if adjustment.category == "tax_latency":
            tax_key = _tax_adjustment_key(adjustment)
            if applied:
                seen_tax_keys.add(tax_key)
            row.update(
                {
                    "temporary_difference": adjustment.temporary_difference,
                    "tax_rate": adjustment.tax_rate,
                    "tax_latency_type": adjustment.tax_latency_type
                    or ("active" if adjustment.type == "add" else "passive"),
                }
            )
            if applied:
                tax_total += signed_amount
        else:
            if applied:
                balance_sheet_total += signed_amount
        rows.append(row)

    for index, latency in enumerate(request.tax_latencies or []):
        tax_key = _tax_latency_key(latency)
        if tax_key in seen_tax_keys:
            flags.append(
                TriageFlag(
                    field="tax_latencies",
                    issue="duplicate_tax_latency_applied_once",
                    severity="info",
                    value={
                        "account_code": latency.account_code,
                        "description": latency.description,
                    },
                )
            )
            continue

        amount = (
            safe_decimal_or_zero(latency.temporary_difference)
            * safe_decimal_or_zero(latency.tax_rate)
            / Decimal("100")
        )
        signed_amount = amount if latency.type == "active" else -amount
        decision = _matching_decision(
            authoritative_decisions,
            latency,
            valuation_currency=valuation_currency,
            row_kind="tax_latency",
        )
        applied = decision is not None
        rows.append(
            {
                "key": latency.id or f"tax_latency_{index + 1}",
                "label": latency.description or "Deferred tax adjustment",
                "category": "tax_latency",
                "operator": "+" if signed_amount >= 0 else "-",
                "amount": abs(amount),
                "signed_amount": signed_amount,
                "description": latency.description,
                "account_code": latency.account_code,
                "temporary_difference": latency.temporary_difference,
                "tax_rate": latency.tax_rate,
                "tax_latency_type": latency.type,
                "source_contract": "tax_latencies",
                "status": (
                    _status(getattr(decision, "state", None))
                    if applied
                    else _unpriced_status(latency, valuation_currency=valuation_currency)
                ),
                "evidence_id": latency.evidence_id,
                "reviewed_at": latency.reviewed_at,
                "rule_version": latency.rule_version,
                "approved_by": latency.approved_by,
                "currency": latency.currency,
                "fiscal_year": latency.fiscal_year,
                "effective_date": latency.effective_date,
                "decision_id": getattr(decision, "decision_id", None),
                "decision_content_hash": getattr(decision, "content_hash", None),
                "policy_version": getattr(decision, "policy_version", None),
                "applied": applied,
            }
        )
        if applied:
            tax_total += signed_amount
            seen_tax_keys.add(tax_key)

    unpriced_rows = [row for row in rows if row.get("applied") is not True]
    if unpriced_rows:
        flags.append(
            TriageFlag(
                field="equity_bridge_adjustments",
                issue="unverified_bridge_adjustments_excluded_from_priced_equity",
                severity="warning",
                value={
                    "count": len(unpriced_rows),
                    "keys": [row.get("key") for row in unpriced_rows],
                },
            )
        )

    return StatelessBridgeAdjustmentLedger(
        rows=rows,
        total=tax_total + balance_sheet_total,
        tax_latency_total=tax_total,
        balance_sheet_adjustment_total=balance_sheet_total,
        triage_flags=flags,
    )


def _normalized_text(value: object) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _tax_key(
    *,
    account_code: object,
    description: object,
    latency_type: object,
    temporary_difference: object,
    tax_rate: object,
) -> tuple[str, ...]:
    identifier = _normalized_text(account_code) or _normalized_text(description)
    return (
        identifier,
        _normalized_text(latency_type),
        str(safe_decimal_or_zero(temporary_difference).normalize()),
        str(safe_decimal_or_zero(tax_rate).normalize()),
    )


def _tax_adjustment_key(adjustment: object) -> tuple[str, ...]:
    latency_type = getattr(adjustment, "tax_latency_type", None) or (
        "active" if getattr(adjustment, "type", None) == "add" else "passive"
    )
    temporary_difference = getattr(adjustment, "temporary_difference", None)
    tax_rate = getattr(adjustment, "tax_rate", None)
    # A legacy balance-sheet row can carry only the already-calculated amount.
    # Use that amount as a 100%-rate base so an identical direct row is only
    # considered a duplicate when the full tax formula is also present.
    if temporary_difference is None or tax_rate is None:
        temporary_difference = getattr(adjustment, "amount", 0)
        tax_rate = Decimal("100")
    return _tax_key(
        account_code=getattr(adjustment, "account_code", None),
        description=getattr(adjustment, "description", None) or getattr(adjustment, "label", None),
        latency_type=latency_type,
        temporary_difference=temporary_difference,
        tax_rate=tax_rate,
    )


def _tax_latency_key(latency: object) -> tuple[str, ...]:
    return _tax_key(
        account_code=getattr(latency, "account_code", None),
        description=getattr(latency, "description", None),
        latency_type=getattr(latency, "type", None),
        temporary_difference=getattr(latency, "temporary_difference", None),
        tax_rate=getattr(latency, "tax_rate", None),
    )
