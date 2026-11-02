"""Fail-closed governance for monetary inputs on the operational v1 path."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping

from src.utils.decimal_helpers import from_decimal, to_decimal

def _value(row: object, key: str) -> object:
    if isinstance(row, Mapping):
        return row.get(key)
    return getattr(row, key, None)


def _text(value: object) -> str:
    return str(value or "").strip()


def _status(value: object) -> str:
    return _text(value).lower().replace("-", "_").replace(" ", "_")


# Submitted row states that carry no request to price the row: an engine or
# Titan auto-proposal nobody accepted (the schema default), or one the advisor
# declined. Any other state (accepted, edited, verified, applied, or a value
# this module does not know) is treated as an advisor decision.
_STATES_NOT_REQUESTING_PRICING = frozenset({"", "proposed", "pending", "rejected"})


def _submitted_status(row: object) -> str:
    return _status(_value(row, "status"))


def is_governed_v1_value_input(
    row: object,
    *,
    valuation_currency: str | None,
) -> bool:
    """Legacy v1 rows are audit/scenario inputs, never monetary authority.

    Reviewer-looking strings in the v1 request are client-controlled and are
    therefore forgeable. Canonical pricing authority exists only in Titan's
    signed v2 case envelope. The compatibility engine stays reported-facts
    only and permanently uncertified; it cannot mint an accepted decision.
    """

    del row, valuation_currency
    return False


def governance_qualification(row: object, *, valuation_currency: str | None) -> str:
    row_currency = _text(_value(row, "currency")).upper()
    if not row_currency or not valuation_currency:
        return "unpriced_currency_unresolved"
    if row_currency != valuation_currency.upper():
        return "unpriced_currency_mismatch"
    return "scenario_only_unverified"


def governed_real_estate_perimeter_decision(
    request: object,
    *,
    treatment: str,
) -> Mapping[str, object] | None:
    """Resolve the typed-in-metadata v1 perimeter decision envelope."""
    metadata = getattr(request, "metadata", None)
    if not isinstance(metadata, Mapping):
        return None
    decision = metadata.get("real_estate_perimeter_decision")
    if not isinstance(decision, Mapping):
        return None
    if _status(decision.get("treatment")) != _status(treatment):
        return None
    if not is_governed_v1_value_input(
        decision,
        valuation_currency=getattr(request, "currency", None),
    ):
        return None
    return decision


@dataclass(frozen=True)
class LegacyBridgeLedger:
    priced_tax_rows: list[dict[str, object]]
    priced_balance_sheet_rows: list[dict[str, object]]
    all_rows: list[dict[str, object]]
    tax_total: Decimal
    balance_sheet_total: Decimal

    @property
    def total(self) -> Decimal:
        return self.tax_total + self.balance_sheet_total

    @property
    def unpriced_rows(self) -> list[dict[str, object]]:
        return [
            row
            for row in self.all_rows
            if row.get("applied") is not True
            and row.get("status") != "duplicate_governed_row_applied_once"
        ]

    @property
    def unpriced_requested_rows(self) -> list[dict[str, object]]:
        """Unpriced rows the caller submitted as a decision to price them.

        These make the reported equity differ from what the advisor accepted.
        Unpriced rows outside this list are proposals nobody accepted (or the
        advisor declined), so the value is exactly what everyone expects.
        """
        return [
            row
            for row in self.unpriced_rows
            if str(row.get("submitted_status") or "") not in _STATES_NOT_REQUESTING_PRICING
        ]


def resolve_legacy_bridge_ledger(request: object) -> LegacyBridgeLedger:
    """Resolve v1 bridge rows once; retain rejected rows as scenario evidence."""
    currency = getattr(request, "currency", None)
    priced_tax_rows: list[dict[str, object]] = []
    priced_bs_rows: list[dict[str, object]] = []
    all_rows: list[dict[str, object]] = []
    tax_total = Decimal("0")
    bs_total = Decimal("0")
    seen_tax_keys: set[tuple[str, ...]] = set()

    for index, adjustment in enumerate(getattr(request, "balance_sheet_adjustments", None) or []):
        amount = abs(to_decimal(_value(adjustment, "amount")))
        signed = -amount if _value(adjustment, "type") == "subtract" else amount
        applied = is_governed_v1_value_input(adjustment, valuation_currency=currency)
        category = _text(_value(adjustment, "category")) or "other"
        row = {
            "id": _text(_value(adjustment, "id")) or f"balance_sheet_adjustment_{index + 1}",
            "label": _value(adjustment, "label"),
            "amount": from_decimal(amount, 2),
            "signed_amount": from_decimal(signed, 2),
            "type": _value(adjustment, "type"),
            "category": category,
            "description": _value(adjustment, "description"),
            "account_code": _value(adjustment, "account_code"),
            "temporary_difference": _value(adjustment, "temporary_difference"),
            "tax_rate": _value(adjustment, "tax_rate"),
            "tax_latency_type": _value(adjustment, "tax_latency_type"),
            "status": (
                _status(_value(adjustment, "status"))
                if applied
                else governance_qualification(adjustment, valuation_currency=currency)
            ),
            "submitted_status": _submitted_status(adjustment),
            "evidence_id": _value(adjustment, "evidence_id"),
            "approved_by": _value(adjustment, "approved_by"),
            "reviewed_at": _value(adjustment, "reviewed_at"),
            "rule_version": _value(adjustment, "rule_version"),
            "currency": _value(adjustment, "currency"),
            "applied": applied,
            "source_contract": "balance_sheet_adjustments",
        }
        all_rows.append(row)
        if not applied:
            continue
        if category == "tax_latency":
            seen_tax_keys.add(_tax_adjustment_key(adjustment))
            tax_total += signed
            priced_tax_rows.append(_tax_row_from_adjustment(row, adjustment, signed))
        else:
            bs_total += signed
            priced_bs_rows.append(row)

    for index, latency in enumerate(getattr(request, "tax_latencies", None) or []):
        difference = to_decimal(_value(latency, "temporary_difference"))
        rate = to_decimal(_value(latency, "tax_rate"))
        amount = difference * rate / Decimal("100")
        signed = amount if _value(latency, "type") == "active" else -amount
        applied = is_governed_v1_value_input(latency, valuation_currency=currency)
        key = _tax_latency_key(latency)
        duplicate = applied and key in seen_tax_keys
        row = {
            "id": _text(_value(latency, "id")) or f"tax_latency_{index + 1}",
            "type": _value(latency, "type"),
            "description": _value(latency, "description"),
            "temporary_difference": from_decimal(difference, 2),
            "tax_rate": from_decimal(rate, 2),
            "amount": from_decimal(signed, 2),
            "account_code": _value(latency, "account_code"),
            "status": (
                "duplicate_governed_row_applied_once"
                if duplicate
                else (
                    _status(_value(latency, "status"))
                    if applied
                    else governance_qualification(latency, valuation_currency=currency)
                )
            ),
            "submitted_status": _submitted_status(latency),
            "evidence_id": _value(latency, "evidence_id"),
            "approved_by": _value(latency, "approved_by"),
            "reviewed_at": _value(latency, "reviewed_at"),
            "rule_version": _value(latency, "rule_version"),
            "currency": _value(latency, "currency"),
            "applied": applied and not duplicate,
            "source_contract": "tax_latencies",
        }
        all_rows.append(row)
        if applied and not duplicate:
            tax_total += signed
            priced_tax_rows.append(row)
            seen_tax_keys.add(key)

    return LegacyBridgeLedger(
        priced_tax_rows=priced_tax_rows,
        priced_balance_sheet_rows=priced_bs_rows,
        all_rows=all_rows,
        tax_total=tax_total,
        balance_sheet_total=bs_total,
    )


def _normalized(value: object) -> str:
    return " ".join(_text(value).lower().split())


def _tax_key(
    *, account: object, description: object, kind: object, difference: object, rate: object
) -> tuple[str, ...]:
    return (
        _normalized(account) or _normalized(description),
        _normalized(kind),
        str(to_decimal(difference).normalize()),
        str(to_decimal(rate).normalize()),
    )


def _tax_latency_key(row: object) -> tuple[str, ...]:
    return _tax_key(
        account=_value(row, "account_code"),
        description=_value(row, "description"),
        kind=_value(row, "type"),
        difference=_value(row, "temporary_difference"),
        rate=_value(row, "tax_rate"),
    )


def _tax_adjustment_key(row: object) -> tuple[str, ...]:
    kind = _value(row, "tax_latency_type") or (
        "active" if _value(row, "type") == "add" else "passive"
    )
    difference = _value(row, "temporary_difference")
    rate = _value(row, "tax_rate")
    if difference is None or rate is None:
        difference, rate = _value(row, "amount"), Decimal("100")
    return _tax_key(
        account=_value(row, "account_code"),
        description=_value(row, "description") or _value(row, "label"),
        kind=kind,
        difference=difference,
        rate=rate,
    )


def _tax_row_from_adjustment(
    ledger_row: dict[str, object], adjustment: object, signed: Decimal
) -> dict[str, object]:
    kind = _value(adjustment, "tax_latency_type") or (
        "active" if _value(adjustment, "type") == "add" else "passive"
    )
    difference = _value(adjustment, "temporary_difference")
    rate = _value(adjustment, "tax_rate")
    return {
        **ledger_row,
        "type": kind,
        "temporary_difference": from_decimal(
            to_decimal(difference) if difference is not None else abs(signed), 2
        ),
        "tax_rate": from_decimal(to_decimal(rate) if rate is not None else Decimal("100"), 2),
        "amount": from_decimal(signed, 2),
    }
