"""Project the engine's admitted annual ledger without re-reading client claims."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Literal

from src.utils.decimal_helpers import optional_decimal

PROJECTION_VERSION: Literal["earnings_basis_build_up.v2"] = "earnings_basis_build_up.v2"


def _money(value: object) -> Decimal:
    parsed: Decimal | None = optional_decimal(value)
    if parsed is None:
        raise ValueError("canonical earnings ledger requires finite monetary values")
    return parsed


def _rows(value: object) -> list[Mapping[str, object]]:
    if not isinstance(value, list) or any(not isinstance(row, Mapping) for row in value):
        raise ValueError("canonical earnings ledger requires structured annual/decision rows")
    return value


def _evidence_key(row: Mapping[str, object]) -> tuple[str, Decimal, str] | None:
    evidence = row.get("evidence_id")
    if not evidence:
        return None
    return (
        str(evidence),
        _money(row["signed_amount"]),
        str(row.get("currency") or ""),
    )


def project_earnings_basis_ledger(ledger: Mapping[str, object]) -> dict[str, object]:
    """Keep annual decision amounts and their contribution to weighted earnings.

    Admission, duplicate detection and pricing belong to the earnings resolver.
    This projection only applies its recorded year weights for disclosure; it
    never admits a proposal, selects a different year or changes the conclusion.
    """
    if ledger.get("version") != "stateless_earnings_basis_v1":
        raise ValueError("unsupported canonical earnings ledger")
    for field in ("reported_ebitda", "normalized_ebitda", "total_adjustments"):
        _money(ledger.get(field))
    adjustments: list[dict[str, object]] = []
    rows = _rows(ledger.get("rows"))
    weights: list[str] = []
    for row in rows:
        weight = _money(row["weight"])
        if not 0 <= weight <= 1:
            raise ValueError("canonical earnings ledger requires normalized year weights")
        year = row["fiscal_year"]
        percent = f"{weight * 100:f}"
        if "." in percent:
            percent = percent.rstrip("0").rstrip(".")
        weights.append(f"{year}: {percent}%")
        applied_rows = _rows(row.get("applied_adjustments"))
        applied_evidence = {
            _evidence_key(raw)
            for raw in applied_rows
            if raw.get("applied") is True and _evidence_key(raw)
        }
        for key in ("applied_adjustments", "pending_adjustments"):
            candidates = _rows(row.get(key))
            for raw in candidates:
                # The resolver retains duplicate transport mirrors as unpriced
                # audit rows. Show the admitted decision once in this summary;
                # the full annual ledger still retains the duplicate evidence.
                if (
                    key == "pending_adjustments"
                    and not str(raw.get("source") or "").startswith("valuation_input_decision.")
                    and raw.get("status")
                    in {"duplicate_transport_ambiguous", "scenario_only_unverified"}
                    and _evidence_key(raw) in applied_evidence
                ):
                    continue
                annual_amount = _money(raw["signed_amount"])
                contribution = annual_amount * weight
                applied = key == "applied_adjustments" and raw.get("applied") is True
                selected = applied and weight != 0
                label = str(raw.get("label") or raw.get("category") or "Adjustment")
                if label.startswith("normalizations."):
                    label = label.removeprefix("normalizations.").replace("_", " ").capitalize()
                adjustments.append(
                    {
                        "label": f"{year} · {percent}% · {label}",
                        "category": raw.get("category") or "other",
                        "amount": abs(contribution),
                        "signed_amount": contribution,
                        "type": "subtract" if contribution < 0 else "add",
                        "annual_signed_amount": annual_amount,
                        "fiscal_year": year,
                        "weight": weight,
                        "applied": selected,
                        "status": (
                            "excluded_zero_weight"
                            if applied and not selected
                            else raw.get("status")
                        ),
                        "rationale": raw.get("decision_reason") or raw.get("rationale"),
                        "source": raw.get("source"),
                        "decision_id": raw.get("id"),
                        "evidence_id": raw.get("evidence_id"),
                        "rule_version": raw.get("rule_version"),
                        "currency": raw.get("currency"),
                        "decided_by": raw.get("decided_by") or raw.get("approved_by"),
                        "decided_at": raw.get("decided_at") or raw.get("reviewed_at"),
                    }
                )
    # Stable display order does not change the resolver's admission or totals.
    adjustments.sort(
        key=lambda row: (
            str(row["fiscal_year"]),
            str(row.get("decision_id") or ""),
            str(row.get("evidence_id") or ""),
            str(row["label"]),
            str(row["signed_amount"]),
        )
    )
    applied = any(row["applied"] for row in adjustments)
    if applied:
        rationale = (
            "Adjusted EBITDA basis: accepted normalization decisions applied once "
            "to their fiscal periods."
        )
    else:
        rationale = "Reported EBITDA basis: no normalization adjustments were applied."
    if len(rows) > 1 or ledger.get("mode") == "advisor_weighted":
        rationale += " Year weights (" + ", ".join(weights) + ")."
    if any(not row["applied"] for row in adjustments):
        rationale += " Unpriced or unselected adjustments are excluded from the earnings basis."
    return {
        "version": PROJECTION_VERSION,
        "reported_ebitda": ledger["reported_ebitda"],
        "adjusted_ebitda": ledger["normalized_ebitda"],
        "adjustments": adjustments,
        "source": str(ledger.get("version") or "stateless_earnings_basis_v1"),
        "rationale": rationale,
    }
