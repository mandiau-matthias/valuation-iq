"""BET-293 holdings consolidation service facade.

Titan owns the holding-tree metadata; ValuationIQ owns deterministic financial
roll-up. This module bridges the two: it accepts parent/subsidiary entity
payloads shaped like Titan API responses, normalizes aliases, aggregates manual
intercompany transaction flags, and delegates the arithmetic to the pure
``multi_entity_consolidation`` core.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import cast

from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.multi_entity_consolidation import consolidate_holdings, validate_holding_structure

DEFAULT_HOLDING_ENGINE_LINES: tuple[str, ...] = (
    "revenue",
    "ebitda",
    "equity",
    "net_income",
    "total_assets",
    "net_debt",
)

_LINE_CONTAINER_KEYS = ("lines", "financial_lines", "financials")
_OWNERSHIP_KEYS = ("ownership_pct", "ownership_pct_in_parent", "parent_ownership_pct")
_INTERCOMPANY_FLAG_KEYS = ("is_intercompany", "intercompany", "related_party")
_TRANSACTION_ID_KEYS = ("id", "transaction_id", "source_id", "external_id")


class HoldingConsolidationInputError(ValueError):
    """Raised when a holdings structure cannot be safely consolidated."""

    def __init__(self, validation: Mapping[str, object]):
        self.validation = dict(validation)
        super().__init__("Invalid holding structure")


def _as_mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be a mapping")
    return value


def _entity_name(entity: Mapping[str, object], fallback: str) -> str:
    for key in ("name", "title", "legal_name", "id"):
        value = entity.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return fallback


def _entity_lines(
    entity: Mapping[str, object],
    lines: Sequence[str],
) -> dict[str, object]:
    for key in _LINE_CONTAINER_KEYS:
        nested = entity.get(key)
        if isinstance(nested, Mapping):
            return {line: nested.get(line) for line in lines}
    return {line: entity.get(line) for line in lines}


def _ownership_pct(entity: Mapping[str, object]) -> object:
    for key in _OWNERSHIP_KEYS:
        if key in entity:
            return entity.get(key)
    return None


def _decimal_or_none(value: object) -> Decimal | None:
    try:
        return cast(Decimal, to_decimal(value))
    except (TypeError, ValueError):
        return None


def normalize_holding_entities(
    parent: Mapping[str, object],
    subsidiaries: Sequence[Mapping[str, object]],
    *,
    lines: Sequence[str] = DEFAULT_HOLDING_ENGINE_LINES,
) -> dict[str, object]:
    """Normalize Titan-style holdings rows into consolidation-core payloads."""
    parent_entity = _as_mapping(parent, "parent")

    normalized_subsidiaries: list[dict[str, object]] = []
    for index, raw_subsidiary in enumerate(subsidiaries, start=1):
        subsidiary = _as_mapping(raw_subsidiary, f"subsidiary #{index}")
        normalized_subsidiaries.append(
            {
                "name": _entity_name(subsidiary, f"Subsidiary {index}"),
                "source_id": subsidiary.get("id"),
                "ownership_pct": _ownership_pct(subsidiary),
                "lines": _entity_lines(subsidiary, lines),
            }
        )

    return {
        "parent": {
            "name": _entity_name(parent_entity, "Parent"),
            "source_id": parent_entity.get("id"),
            "lines": _entity_lines(parent_entity, lines),
        },
        "subsidiaries": normalized_subsidiaries,
    }


def build_intercompany_eliminations(
    transactions: Sequence[Mapping[str, object]] | None,
) -> dict[str, Decimal]:
    """Sum manually flagged intercompany amounts without replaying stable rows.

    Imports and retries can repeat the same transaction. When a stable identifier
    is available, count that transaction once so a replay cannot silently reduce
    the consolidated financial line twice. Rows without an identifier remain
    additive because ValuationIQ cannot safely infer whether equal amounts are
    duplicates or distinct transactions.
    """
    totals: dict[str, Decimal] = {}
    seen_transaction_lines: set[tuple[str, str]] = set()
    for raw_transaction in transactions or ():
        if not any(bool(raw_transaction.get(key)) for key in _INTERCOMPANY_FLAG_KEYS):
            continue

        transaction_id = next(
            (
                str(raw_transaction.get(key)).strip()
                for key in _TRANSACTION_ID_KEYS
                if raw_transaction.get(key) is not None and str(raw_transaction.get(key)).strip()
            ),
            None,
        )
        line = str(
            raw_transaction.get("line")
            or raw_transaction.get("financial_line")
            or raw_transaction.get("metric")
            or "revenue"
        ).strip()
        if not line:
            continue
        transaction_line = (transaction_id, line) if transaction_id is not None else None
        if transaction_line is not None and transaction_line in seen_transaction_lines:
            continue

        amount = _decimal_or_none(raw_transaction.get("amount"))
        if amount is None or amount == 0:
            continue
        if transaction_line is not None:
            seen_transaction_lines.add(transaction_line)
        totals[line] = totals.get(line, Decimal("0")) + abs(amount)

    return {line: from_decimal(amount) for line, amount in totals.items() if amount != 0}


def _normalized_eliminations(
    elimination_map: Mapping[str, object] | None,
) -> dict[str, Decimal]:
    normalized: dict[str, Decimal] = {}
    for raw_line, raw_amount in (elimination_map or {}).items():
        line = str(raw_line).strip()
        amount = _decimal_or_none(raw_amount)
        if not line or amount is None or amount == 0:
            continue
        # Elimination inputs represent an amount to remove. Treat a signed
        # accounting export as magnitude; a negative input must never turn an
        # elimination into an unproven increase in group value.
        normalized[line] = abs(amount)
    return normalized


def _resolve_eliminations(
    explicit: Mapping[str, object] | None,
    transactions: Mapping[str, object] | None,
) -> tuple[dict[str, Decimal], dict[str, dict[str, object]]]:
    """Resolve one authoritative elimination amount per financial line.

    Explicit line totals are the advisor-controlled source of truth. Flagged
    transaction totals fill only lines that have no explicit amount. Adding the
    two sources together would commonly count the same intercompany flow twice.
    The returned provenance records that precedence for audit consumers.
    """
    explicit_lines = _normalized_eliminations(explicit)
    transaction_lines = _normalized_eliminations(transactions)
    resolved: dict[str, Decimal] = {}
    provenance: dict[str, dict[str, object]] = {}

    for line in sorted(set(explicit_lines) | set(transaction_lines)):
        explicit_amount = explicit_lines.get(line)
        transaction_amount = transaction_lines.get(line)
        if explicit_amount is not None:
            resolved[line] = explicit_amount
            provenance[line] = {
                "source": "explicit",
                "amount": from_decimal(explicit_amount),
                "transaction_total_suppressed": (
                    from_decimal(transaction_amount) if transaction_amount is not None else None
                ),
            }
            continue

        if transaction_amount is not None:
            resolved[line] = transaction_amount
            provenance[line] = {
                "source": "intercompany_transactions",
                "amount": from_decimal(transaction_amount),
                "transaction_total_suppressed": None,
            }

    return (
        {line: from_decimal(amount) for line, amount in resolved.items()},
        provenance,
    )


def consolidate_holding_entities(
    parent: Mapping[str, object],
    subsidiaries: Sequence[Mapping[str, object]],
    *,
    eliminations: Mapping[str, object] | None = None,
    intercompany_transactions: Sequence[Mapping[str, object]] | None = None,
    mode: str = "pro_rata",
    lines: Sequence[str] = DEFAULT_HOLDING_ENGINE_LINES,
    require_valid: bool = True,
) -> dict[str, object]:
    """Consolidate a parent entity with subsidiaries into engine-ready lines."""
    normalized = normalize_holding_entities(parent, subsidiaries, lines=lines)
    normalized_parent = cast(Mapping[str, object], normalized["parent"])
    normalized_subsidiaries = cast(Sequence[Mapping[str, object]], normalized["subsidiaries"])
    validation = validate_holding_structure(normalized_subsidiaries)
    if require_valid and not validation["ok"]:
        raise HoldingConsolidationInputError(validation)

    transaction_eliminations = build_intercompany_eliminations(intercompany_transactions)
    effective_eliminations, elimination_provenance = _resolve_eliminations(
        eliminations,
        transaction_eliminations,
    )
    result = consolidate_holdings(
        cast(Mapping[str, object], normalized_parent["lines"]),
        normalized_subsidiaries,
        eliminations=effective_eliminations,
        mode=mode,
        lines=lines,
    )
    subsidiary_count = int(result.get("subsidiary_count", len(normalized_subsidiaries)))

    return {
        **result,
        "entity_count": subsidiary_count + 1,
        "parent": normalized_parent,
        "structure_validation": validation,
        "elimination_provenance": elimination_provenance,
    }
