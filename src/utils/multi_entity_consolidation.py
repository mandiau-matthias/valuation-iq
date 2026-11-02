"""BET-293 Multi-entity holdings consolidation — pure pro-rata roll-up.

Belgian holding structures (a parent + N subsidiaries with fractional ownership
and intercompany flows) need a consolidated financial picture before valuation.
VARE markets "automatisch pro-rata, intercompany flows automatisch
geëlimineerd" and wins enterprise/PE deals on it; this is the deterministic
core of that.

PURE: dict-in / dict-out, bank-grade ``Decimal`` arithmetic (repo convention),
no DB and no valuation-pipeline coupling — so it is unit-tested directly and
later fed into the engine + surfaced in Mercury.

Two modes (``mode=``), the parent always consolidated at 100%:
* ``pro_rata`` (default) — each subsidiary contributes ``ownership_pct`` × its
  lines; no minority interest. Matches the holding-valuation use case.
* ``full`` — IFRS-10 control model: 100% of each subsidiary's lines, with the
  non-controlling share booked separately as ``minority_interest`` and
  ``net_income_attributable_to_parent`` reported.
Intercompany flows are eliminated from the group total in both modes (revenue
billed between group entities is not external group revenue).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation

from src.utils.decimal_helpers import from_decimal, to_decimal

#: Canonical financial lines consolidated by default. Extend as the engine grows.
CONSOLIDATED_LINES: tuple[str, ...] = (
    "revenue",
    "ebitda",
    "ebit",
    "net_income",
    "total_assets",
    "net_debt",
)


def _safe_decimal(value: object) -> Decimal | None:
    """Coerce to a finite Decimal, or None for null / non-numeric / NaN / inf."""
    if value is None:
        return None
    try:
        d = to_decimal(value)
    except (InvalidOperation, ValueError, TypeError):
        return None
    return d if d.is_finite() else None


def _ownership_fraction(raw: object) -> Decimal:
    """Ownership percentage (0–100) → clamped fraction (0–1). Invalid → 0."""
    d = _safe_decimal(raw)
    if d is None or d <= 0:
        return Decimal(0)
    if d >= Decimal(100):
        return Decimal(1)
    return d / Decimal(100)


def consolidate_holdings(
    parent_lines: Mapping[str, object],
    subsidiaries: Sequence[Mapping[str, object]],
    *,
    eliminations: Mapping[str, object] | None = None,
    mode: str = "pro_rata",
    lines: Sequence[str] = CONSOLIDATED_LINES,
) -> dict[str, object]:
    """Pro-rata consolidate a parent + subsidiaries, then eliminate intercompany
    flows.

    Args:
        parent_lines: the parent's own financial lines (consolidated at 100%).
        subsidiaries: each ``{"name", "ownership_pct" (0–100), "lines": {...}}``.
        eliminations: intercompany amounts to remove from the group total per line.
        lines: which line items to consolidate (defaults to ``CONSOLIDATED_LINES``).

    Returns a dict with:
        ``lines``            — consolidated group total per line (floats, 2dp);
        ``by_entity``        — per-subsidiary pro-rata contribution per line;
        ``eliminations``     — the intercompany amounts actually applied;
        ``subsidiary_count`` — number of subsidiaries rolled up.
    """
    elim = eliminations or {}
    consolidation_mode = "full" if str(mode).strip().lower() == "full" else "pro_rata"
    # Accumulate in Decimal to avoid float drift across the roll-up.
    totals: dict[str, Decimal] = {
        line: (_safe_decimal(parent_lines.get(line)) or Decimal(0)) for line in lines
    }

    minority_interest = Decimal(0)
    by_entity: list[dict[str, object]] = []
    for sub in subsidiaries:
        fraction = _ownership_fraction(sub.get("ownership_pct"))
        # Full consolidation absorbs 100% of a controlled subsidiary's lines and
        # books the non-controlling share separately as minority interest;
        # pro-rata absorbs only the owned fraction (no minority interest).
        line_weight = Decimal(1) if consolidation_mode == "full" else fraction
        sub_lines = sub.get("lines")
        sub_lines = sub_lines if isinstance(sub_lines, Mapping) else {}
        contribution: dict[str, float] = {}
        for line in lines:
            raw = _safe_decimal(sub_lines.get(line))
            contributed = (raw * line_weight) if raw is not None else Decimal(0)
            totals[line] += contributed
            contribution[line] = from_decimal(contributed)
        if consolidation_mode == "full":
            sub_ni = _safe_decimal(sub_lines.get("net_income"))
            if sub_ni is not None:
                minority_interest += (Decimal(1) - fraction) * sub_ni
        by_entity.append(
            {
                "name": str(sub.get("name")) if sub.get("name") is not None else None,
                "ownership_pct": from_decimal(fraction * Decimal(100)),
                "contribution": contribution,
            }
        )

    applied_eliminations: dict[str, float] = {}
    for line in lines:
        amount = _safe_decimal(elim.get(line)) or Decimal(0)
        if amount != 0:
            totals[line] -= amount
            applied_eliminations[line] = from_decimal(amount)

    # Net income attributable to the parent = group net income (post-elimination)
    # less the non-controlling interest. Identical to the pro-rata net income by
    # construction (minority_interest is 0 under pro-rata).
    net_income_attributable = (
        from_decimal(totals["net_income"] - minority_interest)
        if "net_income" in lines
        else None
    )

    return {
        "mode": consolidation_mode,
        "lines": {line: from_decimal(totals[line]) for line in lines},
        "by_entity": by_entity,
        "eliminations": applied_eliminations,
        "minority_interest": from_decimal(minority_interest),
        "net_income_attributable_to_parent": net_income_attributable,
        "subsidiary_count": len(list(subsidiaries)),
    }


def validate_holding_structure(
    subsidiaries: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Pre-flight validation of a holding structure before consolidation.

    ``consolidate_holdings`` clamps bad input silently so a roll-up never
    crashes; this surfaces the same problems for the holdings UI / advisor to
    fix (e.g. an entity with no ownership %, an out-of-range stake, a duplicate).
    Returns ``{ok, issues}`` where each issue is ``{entity, code[, value]}`` with
    code in: ``missing_name`` | ``duplicate_name`` | ``ownership_missing`` |
    ``ownership_out_of_range``.
    """
    issues: list[dict[str, object]] = []
    seen: set[str] = set()
    for index, sub in enumerate(subsidiaries):
        mapping = sub if isinstance(sub, Mapping) else {}
        raw_name = mapping.get("name")
        name = (
            str(raw_name).strip()
            if raw_name is not None and str(raw_name).strip()
            else None
        )
        label = name or f"#{index + 1}"

        if name is None:
            issues.append({"entity": label, "code": "missing_name"})
        elif name.lower() in seen:
            issues.append({"entity": label, "code": "duplicate_name"})
        else:
            seen.add(name.lower())

        pct = _safe_decimal(mapping.get("ownership_pct"))
        if pct is None:
            issues.append({"entity": label, "code": "ownership_missing"})
        elif pct < 0 or pct > 100:
            issues.append(
                {
                    "entity": label,
                    "code": "ownership_out_of_range",
                    "value": from_decimal(pct),
                }
            )

    return {"ok": not issues, "issues": issues}
