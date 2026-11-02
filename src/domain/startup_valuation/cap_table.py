"""Cap-table simulator math — deterministic, Decimal-precise.

The consortium blueprint requires every founder report to surface a
"if you raise €X at this valuation, you dilute Y%" line directly under
the football-field chart.  Historically that math lived in the report
context layer and used ``float`` arithmetic, which is fine for display
but unsafe to reuse from a JSON API contract that other services
(Mercury preview, Venus live-preview hook) must round-trip.

This module is the **single source of truth** for that math.  All
inputs and outputs are :class:`Decimal`; quantization is delegated to
:mod:`.money` so cents and percentages round identically everywhere.

Public surface
--------------
* :func:`simulate_round` — given a pre-money + investment ask + optional
  option pool and outstanding SAFEs, return a :class:`CapTableSimulation`
  with post-money, founder dilution and option-pool dilution.
* :class:`CapTableSimulation` — frozen dataclass safe to pass around
  freely; ``to_payload()`` serializes for the report context.

Determinism
-----------
Pure function, no I/O, no module-level mutable state, no hidden defaults.
Identical inputs ⇒ identical outputs across processes and OS locales.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Optional

from .money import (
    ONE_HUNDRED,
    Q_PCT,
    ZERO,
    clamp,
    q_eur,
    q_pct,
    q_rate,
    safe_decimal,
    safe_float,
    sum_decimals,
)
from .schemas import CapTableSummary, RoundScenario

#: Source attribution shown in the report copy when the simulation
#: derived its round size from the *historical* last round (because the
#: founder didn't supply ``investment_amount_sought`` on the wizard).
SOURCE_INVESTOR_ASK: str = "investor_ask"
SOURCE_ROUND_SCENARIO: str = "round_scenario"
SOURCE_LAST_ROUND_PROXY: str = "last_round_proxy"


@dataclass(frozen=True)
class CapTableSimulation:
    """Result of a cap-table simulation for one round scenario."""

    investment_amount: Decimal
    pre_money: Decimal
    post_money: Decimal
    investor_dilution_pct: Decimal
    option_pool_pct: Decimal
    safe_dilution_pct: Decimal
    founder_dilution_pct: Decimal
    safe_total: Decimal
    source: str
    """Provenance label — see :data:`SOURCE_INVESTOR_ASK` /
    :data:`SOURCE_LAST_ROUND_PROXY`."""

    def to_payload(self) -> Dict[str, Any]:
        """Serialize for the report-context JSON payload (floats at the edge)."""
        return {
            "investment_amount": safe_float(self.investment_amount),
            "pre_money": safe_float(self.pre_money),
            "post_money": safe_float(self.post_money),
            "dilution_pct": safe_float(self.investor_dilution_pct),
            "investor_dilution_pct": safe_float(self.investor_dilution_pct),
            "option_pool_pct": safe_float(self.option_pool_pct),
            "safe_dilution_pct": safe_float(self.safe_dilution_pct),
            "founder_dilution_pct": safe_float(self.founder_dilution_pct),
            "safe_total": safe_float(self.safe_total),
            "source": self.source,
        }


def _safe_total(cap_table: Optional[CapTableSummary]) -> Decimal:
    """Sum the principal of every outstanding SAFE / convertible note.

    SAFEs without an explicit amount default to zero — the conservative
    choice (we never invent dilution the founder didn't enter)."""
    if cap_table is None:
        return ZERO
    notes = getattr(cap_table, "safe_notes", None) or []
    amounts = []
    for note in notes:
        # ``CapTableSummary`` is the typed contract, but defensively
        # handle dicts so the helper can be called from the report
        # context where the cap table arrives as an arbitrary mapping.
        amount = getattr(note, "amount", None)
        if amount is None and isinstance(note, dict):
            amount = note.get("amount")
        amounts.append(safe_decimal(amount))
    return sum_decimals(amounts)


def _resolve_investment_amount(
    investment_amount_sought: Optional[Decimal],
    cap_table: Optional[CapTableSummary],
    round_scenario: Optional[RoundScenario] = None,
) -> tuple[Decimal, str]:
    """Pick the round size + remember which source we used.

    Priority (consortium spec):
      1. ``investment_amount_sought`` from Screen 3 — the most reliable
         signal because it's the explicit ask in the wizard.
      2. ``round_scenario.amount_raised`` / ``target_amount`` — a typed
         scenario from the round console or Mercury startup dashboard.
      3. ``cap_table.last_round_amount`` — historical fallback so the
         simulator still draws a defensible line when the founder
         skipped the explicit ask (common on the orphaned dashboard
         flow where Mercury seeds last round but not the next one).
      4. Zero — the simulator gracefully omits itself from the report.
    """
    primary = safe_decimal(investment_amount_sought)
    if primary > ZERO:
        return primary, SOURCE_INVESTOR_ASK

    if round_scenario is not None:
        scenario_amount = safe_decimal(round_scenario.amount_raised)
        if scenario_amount <= ZERO:
            scenario_amount = safe_decimal(round_scenario.target_amount)
        if scenario_amount > ZERO:
            return scenario_amount, SOURCE_ROUND_SCENARIO

    if cap_table is not None:
        secondary = safe_decimal(getattr(cap_table, "last_round_amount", None))
        if secondary > ZERO:
            return secondary, SOURCE_LAST_ROUND_PROXY

    return ZERO, SOURCE_INVESTOR_ASK


def simulate_round(
    *,
    pre_money: Decimal,
    investment_amount_sought: Optional[Decimal] = None,
    cap_table: Optional[CapTableSummary] = None,
    round_scenario: Optional[RoundScenario] = None,
) -> Optional[CapTableSimulation]:
    """Simulate dilution for a fundraising round.

    Returns ``None`` when neither a positive ``pre_money`` nor a positive
    investment amount is available — *not* a zero-everything object,
    because the report should *omit* the simulator card entirely in
    that case rather than render an unhelpful "you raised €0".

    Parameters
    ----------
    pre_money:
        Blended pre-money valuation produced by the synthesis blender
        (or any other defensible reference).  Must be > 0 for the
        simulation to render.
    investment_amount_sought:
        Founder's explicit ask from the wizard (Screen 3).  When
        omitted we fall back to ``cap_table.last_round_amount`` per
        the consortium spec.
    cap_table:
        Optional :class:`.schemas.CapTableSummary`.  Drives the
        option-pool dilution column and the SAFE-conversion drag.
    round_scenario:
        Optional first-class fundraising scenario.  Supplies the round
        amount when the legacy ``investment_amount_sought`` field is absent.
    """
    pre_money_q = q_eur(safe_decimal(pre_money))
    if pre_money_q <= ZERO:
        return None

    investment_raw, source = _resolve_investment_amount(
        investment_amount_sought, cap_table, round_scenario
    )
    if investment_raw <= ZERO:
        return None
    # Quantize to cents BEFORE we use the value anywhere downstream so
    # `pre_money + investment_amount == post_money` holds at the cent
    # level the report templates display. Without this, a fractional-cent
    # ask (e.g. €123,456.789) would round-trip as 3-decimal in
    # `investment_amount` while `pre_money` and `post_money` would round
    # to 2-decimal — making the three columns of the simulator card
    # disagree by sub-cent amounts.
    investment_q = q_eur(investment_raw)

    safe_total = _safe_total(cap_table)
    option_pool_pct = (
        safe_decimal(getattr(cap_table, "option_pool_pct", None)) if cap_table else ZERO
    )
    # Defensive clamp — schema enforces 0..50 but the engine should
    # behave even if a mis-configured upstream payload leaks a wider
    # range (we never want to render founder_dilution_pct > 100).
    option_pool_pct = clamp(option_pool_pct, low=ZERO, high=ONE_HUNDRED)

    post_money_q = q_eur(pre_money_q + investment_q)

    # Investor dilution = round size / post-money.  Clamped to [0, 100]
    # so an extreme upstream pre-money never produces a > 100 % display
    # (which reads as a UI bug to a founder).
    if post_money_q > ZERO:
        raw_investor_dilution = (investment_q / post_money_q) * ONE_HUNDRED
    else:
        raw_investor_dilution = ZERO
    investor_dilution_pct = clamp(q_pct(raw_investor_dilution), low=ZERO, high=ONE_HUNDRED)

    # SAFE conversion drag — outstanding SAFE principal converts at
    # the new round and slices founder ownership proportional to the
    # post-money snapshot.  We approximate the conversion at the
    # blended pre-money (same lens as Bessemer's "fully-diluted post"
    # convention).
    if post_money_q > ZERO and safe_total > ZERO:
        raw_safe_dilution = (safe_total / post_money_q) * ONE_HUNDRED
    else:
        raw_safe_dilution = ZERO
    safe_dilution_pct = clamp(q_pct(raw_safe_dilution), low=ZERO, high=ONE_HUNDRED)

    # Founder dilution = investor + safe + option pool, capped at 100 %
    # so the report never claims a founder is "diluted 137%".
    raw_founder = investor_dilution_pct + safe_dilution_pct + option_pool_pct
    founder_dilution_pct = clamp(raw_founder.quantize(Q_PCT), low=ZERO, high=ONE_HUNDRED)

    return CapTableSimulation(
        investment_amount=investment_q,
        pre_money=pre_money_q,
        post_money=post_money_q,
        investor_dilution_pct=investor_dilution_pct,
        option_pool_pct=q_pct(option_pool_pct),
        safe_dilution_pct=safe_dilution_pct,
        founder_dilution_pct=founder_dilution_pct,
        safe_total=q_eur(safe_total),
        source=source,
    )


def build_round_context_payload(
    *,
    objective_pre_money: Decimal,
    round_scenario: Optional[RoundScenario] = None,
    investment_amount_sought: Optional[Decimal] = None,
    cap_table: Optional[CapTableSummary] = None,
) -> Optional[dict[str, object]]:
    """Return the market-implied round layer for graph/report consumers."""
    pre_money = _first_positive(
        getattr(round_scenario, "pre_money", None),
        getattr(cap_table, "pre_money_target", None),
    )
    amount = _first_positive(
        getattr(round_scenario, "amount_raised", None),
        getattr(round_scenario, "target_amount", None),
        investment_amount_sought,
        getattr(cap_table, "last_round_amount", None),
    )
    post_money = _first_positive(getattr(round_scenario, "post_money", None))
    if post_money <= ZERO and pre_money > ZERO and amount > ZERO:
        post_money = q_eur(pre_money + amount)

    valuation_cap = _first_positive(
        getattr(round_scenario, "valuation_cap", None),
        _lowest_safe_valuation_cap(cap_table),
    )
    market_implied_pre_money = pre_money
    if market_implied_pre_money <= ZERO and post_money > amount > ZERO:
        market_implied_pre_money = q_eur(post_money - amount)
    if market_implied_pre_money <= ZERO:
        market_implied_pre_money = valuation_cap

    if market_implied_pre_money <= ZERO and post_money <= ZERO and amount <= ZERO:
        return None

    objective = q_eur(safe_decimal(objective_pre_money))
    comparison = _round_comparison_payload(objective, market_implied_pre_money)
    scenario_payload = _scenario_payload(round_scenario)
    provenance_payload = _round_provenance_payload(
        scenario_payload,
        round_scenario=round_scenario,
        investment_amount_sought=investment_amount_sought,
        cap_table=cap_table,
    )

    return {
        "layer": "market_implied_round_context",
        "overwrites_objective_dot": False,
        "value_relationship": scenario_payload["value_relationship"],
        "status": scenario_payload["status"],
        "instrument_type": scenario_payload["instrument_type"],
        "label": scenario_payload["label"],
        "market_implied": {
            "pre_money": safe_float(market_implied_pre_money),
            "post_money": safe_float(post_money),
            "valuation_cap": safe_float(valuation_cap),
            "target_amount": safe_float(getattr(round_scenario, "target_amount", None)),
            "amount_raised": safe_float(getattr(round_scenario, "amount_raised", None)),
            "comparison_amount": safe_float(amount),
            "discount_pct": safe_float(getattr(round_scenario, "discount_pct", None)),
            "target_close_date": getattr(round_scenario, "target_close_date", None),
        },
        "comparison_to_objective": comparison,
        "provenance": provenance_payload,
    }


def _first_positive(*values: object) -> Decimal:
    for value in values:
        candidate = q_eur(safe_decimal(value))
        if candidate > ZERO:
            return candidate
    return ZERO


def _lowest_safe_valuation_cap(cap_table: Optional[CapTableSummary]) -> Decimal:
    if cap_table is None:
        return ZERO
    caps = [
        safe_decimal(getattr(note, "valuation_cap", None))
        for note in (getattr(cap_table, "safe_notes", None) or [])
        if safe_decimal(getattr(note, "valuation_cap", None)) > ZERO
    ]
    return q_eur(min(caps)) if caps else ZERO


def _round_comparison_payload(
    objective_pre_money: Decimal, market_implied_pre_money: Decimal
) -> dict[str, object]:
    delta = ZERO
    ratio: Optional[Decimal] = None
    if objective_pre_money > ZERO and market_implied_pre_money > ZERO:
        delta = q_eur(market_implied_pre_money - objective_pre_money)
        ratio = q_rate(market_implied_pre_money / objective_pre_money)
    return {
        "objective_pre_money_mid": safe_float(objective_pre_money),
        "market_implied_pre_money": safe_float(market_implied_pre_money),
        "delta_to_objective": safe_float(delta),
        "ratio_to_objective": safe_float(ratio),
    }


def _scenario_payload(round_scenario: Optional[RoundScenario]) -> dict[str, object]:
    if round_scenario is None:
        return {
            "label": None,
            "instrument_type": "priced_equity",
            "status": "draft_scenario",
            "evidence_source": "founder_entered",
            "evidence_quality": "founder_asserted",
            "value_relationship": "market_implied_valuation",
            "assumptions": {},
        }
    return {
        "label": round_scenario.label,
        "instrument_type": round_scenario.instrument_type,
        "status": round_scenario.status,
        "evidence_source": round_scenario.evidence_source,
        "evidence_quality": round_scenario.evidence_quality,
        "value_relationship": round_scenario.value_relationship,
        "assumptions": dict(round_scenario.assumptions),
    }


def _round_provenance_payload(
    scenario_payload: dict[str, object],
    *,
    round_scenario: Optional[RoundScenario],
    investment_amount_sought: Optional[Decimal],
    cap_table: Optional[CapTableSummary],
) -> dict[str, object]:
    if round_scenario is not None:
        return {
            "source": scenario_payload["evidence_source"],
            "quality": scenario_payload["evidence_quality"],
            "source_detail": scenario_payload["evidence_source"],
            "assumptions": scenario_payload["assumptions"],
        }

    source_detail = _fallback_round_source_detail(
        investment_amount_sought=investment_amount_sought,
        cap_table=cap_table,
    )
    return {
        "source": "founder_entered",
        "quality": "unverified",
        "source_detail": source_detail,
        "assumptions": {"derived_from": source_detail},
    }


def _fallback_round_source_detail(
    *,
    investment_amount_sought: Optional[Decimal],
    cap_table: Optional[CapTableSummary],
) -> str:
    if _first_positive(getattr(cap_table, "pre_money_target", None)) > ZERO:
        return "legacy_cap_table_pre_money_target"
    if _lowest_safe_valuation_cap(cap_table) > ZERO:
        return "legacy_safe_valuation_cap"
    if _first_positive(getattr(cap_table, "last_round_amount", None)) > ZERO:
        return "legacy_last_round_amount"
    if _first_positive(investment_amount_sought) > ZERO:
        return "founder_investment_amount_sought"
    return "generated_round_context"
