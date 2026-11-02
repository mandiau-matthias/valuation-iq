"""
Multi-owner team aggregator (BET-218) — Python engine-path implementation.

Rolls a per-owner roster up into one `composite_transferability_index`.
This is the authoritative engine-path aggregator: it lives next to the
12-factor owner-dependency engine because per-owner transferability
scoring is a Python concern, and aggregation belongs with scoring. (The
Titan TypeScript `owner-team-aggregator.ts` is the client-side preview
twin — same maths, used for instant wizard feedback before the server
round-trip.)

The 12-factor Damodaran transferability score is fundamentally about
HUMAN dependency, and that question lands differently for a 3-co-founder
venture than for a sole owner-operator. Three signals blend:

  1. Operating-load-weighted TRI — `Σ TRI · loadShare`, where
     `loadShare = (hours · roleCriticality) / Σ`. **Operating load, not
     equity, is the dependency currency**: a silent co-owner contributes
     ~zero load and ~zero weight.

  2. Critical-path ceiling — `max(TRI)` across owners with real load
     (`loadShare ≥ floor`) OR a structurally indispensable role
     (`roleCriticality ≥ threshold`). The most key-person-risky operator
     cannot be averaged away — even a low-load irreplaceable founder.

  3. Concentration premium (HHI) — `Σ loadShare²` normalised against the
     even-split floor `1/N`; up to +5 TRI points for funnelled load.

Blend: `(1−α)·loadWeighted + α·criticalPath + concentrationPremium`.

ZERO-REGRESSION INVARIANT: a single-owner roster collapses to exactly
that owner's TRI — it falls out of the uniform formula, there is no
owner-count branch.

TRI convention (matches Titan + `multi_owner_resolution`): 0-100, where
a HIGHER value means MORE key-person risk (less transferable).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

# Blend / signal defaults — exposed as kwargs so calibration tuning lands
# here first, with the engine reading the same composite shape.
_DEFAULT_CRITICAL_PATH_WEIGHT = 0.6
_DEFAULT_CRITICAL_PATH_LOAD_FLOOR = 0.1
_DEFAULT_MAX_CONCENTRATION_PREMIUM = 5.0
_DEFAULT_CRITICAL_ROLE_THRESHOLD = 4

_INDEX_MIN = 0.0
_INDEX_MAX = 100.0


# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------


@dataclass
class OwnerSubScore:
    """One owner's contribution within the aggregated team result."""

    owner_id: Optional[str]
    label: Optional[str]
    transferability_index: float
    load_share: float
    is_critical_path: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "owner_id": self.owner_id,
            "label": self.label,
            "transferability_index": self.transferability_index,
            "load_share": self.load_share,
            "is_critical_path": self.is_critical_path,
        }


@dataclass
class OwnerTeamProvenance:
    """Audit trail for how the composite was derived."""

    load_weighted_index: float
    critical_path_index: float
    hhi: float
    concentration_norm: float
    concentration_premium: float
    blend_alpha: float
    critical_owner_index: Optional[int]
    load_fallback_equal_shares: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "load_weighted_index": self.load_weighted_index,
            "critical_path_index": self.critical_path_index,
            "hhi": self.hhi,
            "concentration_norm": self.concentration_norm,
            "concentration_premium": self.concentration_premium,
            "blend_alpha": self.blend_alpha,
            "critical_owner_index": self.critical_owner_index,
            "load_fallback_equal_shares": self.load_fallback_equal_shares,
        }


@dataclass
class OwnerTeamAggregateResult:
    """Aggregate result of a multi-owner roster scan."""

    composite_transferability_index: float
    owner_count: int
    per_owner: list[OwnerSubScore] = field(default_factory=list)
    provenance: Optional[OwnerTeamProvenance] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "composite_transferability_index": self.composite_transferability_index,
            "owner_count": self.owner_count,
            "per_owner": [o.to_dict() for o in self.per_owner],
            "provenance": self.provenance.to_dict() if self.provenance else None,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clamp(value: float, low: float, high: float) -> float:
    if value != value:  # NaN
        return low
    return max(low, min(value, high))


def _safe_tri(value: Any) -> float:
    """Sanitise a raw TRI: non-numeric / NaN -> 0, else clamp to [0, 100]."""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return _INDEX_MIN
    return _clamp(numeric, _INDEX_MIN, _INDEX_MAX)


def _round2(value: float) -> float:
    return round(value, 2)


def _round4(value: float) -> float:
    return round(value, 4)


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------


def aggregate_owner_team(
    members: list[dict[str, Any]],
    *,
    critical_path_weight: float = _DEFAULT_CRITICAL_PATH_WEIGHT,
    critical_path_load_floor: float = _DEFAULT_CRITICAL_PATH_LOAD_FLOOR,
    max_concentration_premium: float = _DEFAULT_MAX_CONCENTRATION_PREMIUM,
    critical_role_threshold: int = _DEFAULT_CRITICAL_ROLE_THRESHOLD,
) -> Optional[OwnerTeamAggregateResult]:
    """
    Aggregate a per-owner roster into a composite transferability index.

    Args:
        members: per-owner dicts with keys `transferability_index`,
            `role_criticality`, optional `owner_hours_per_week`,
            `owner_id`, `label`.

    Returns:
        OwnerTeamAggregateResult, or None for an empty roster (the caller
        decides whether that means "fall back to single-owner scoring").
    """
    if not members:
        return None

    alpha = _clamp(critical_path_weight, 0.0, 1.0)
    load_floor = _clamp(critical_path_load_floor, 0.0, 1.0)
    max_premium = max(0.0, max_concentration_premium)

    n = len(members)
    tri = [_safe_tri(m.get("transferability_index")) for m in members]
    criticality = [
        int(_clamp(float(m.get("role_criticality") or 1), 1, 5)) for m in members
    ]

    # Operating load = hours x role intensity. A silent owner (0 hours)
    # contributes zero load and therefore zero weight.
    def _hours(m: dict[str, Any]) -> float:
        raw = m.get("owner_hours_per_week")
        try:
            value = float(raw) if raw is not None else 0.0
        except (TypeError, ValueError):
            value = 0.0
        return max(0.0, value)

    load_raw = [_hours(m) * criticality[i] for i, m in enumerate(members)]
    load_total = sum(load_raw)

    # If nobody logged hours we cannot infer load — fall back to an equal
    # split so the aggregator still produces a defensible composite.
    load_fallback_equal_shares = load_total <= 0
    if load_fallback_equal_shares:
        load_share = [1.0 / n] * n
    else:
        load_share = [v / load_total for v in load_raw]

    # Signal 1 — operating-load-weighted TRI.
    load_weighted_index = sum(tri[i] * load_share[i] for i in range(n))

    # Signal 2 — critical-path ceiling.
    critical_owner_index: Optional[int] = None
    critical_path_index = -1.0
    for i in range(n):
        eligible = (
            load_share[i] >= load_floor or criticality[i] >= critical_role_threshold
        )
        if eligible and tri[i] > critical_path_index:
            critical_path_index = tri[i]
            critical_owner_index = i
    # No owner cleared the floor or the role threshold — take the plain
    # max so the ceiling is never silently dropped.
    if critical_owner_index is None:
        for i in range(n):
            if tri[i] > critical_path_index:
                critical_path_index = tri[i]
                critical_owner_index = i

    # Signal 3 — HHI concentration premium.
    hhi = sum(s * s for s in load_share)
    even_floor = 1.0 / n
    # For N=1 the floor equals HHI (both 1) — the 0/0 limit is 0: a solo
    # owner has no concentration *relative to a team* because there is no
    # team. Degenerate-denominator guard, not an owner-count branch.
    if n <= 1 or (1.0 - even_floor) <= 0:
        concentration_norm = 0.0
    else:
        concentration_norm = _clamp(
            (hhi - even_floor) / (1.0 - even_floor), 0.0, 1.0
        )
    concentration_premium = concentration_norm * max_premium

    composite = _clamp(
        (1.0 - alpha) * load_weighted_index
        + alpha * critical_path_index
        + concentration_premium,
        _INDEX_MIN,
        _INDEX_MAX,
    )

    per_owner = [
        OwnerSubScore(
            owner_id=members[i].get("owner_id"),
            label=members[i].get("label"),
            transferability_index=tri[i],
            load_share=load_share[i],
            is_critical_path=(i == critical_owner_index),
        )
        for i in range(n)
    ]

    return OwnerTeamAggregateResult(
        composite_transferability_index=_round2(composite),
        owner_count=n,
        per_owner=per_owner,
        provenance=OwnerTeamProvenance(
            load_weighted_index=_round2(load_weighted_index),
            critical_path_index=_round2(critical_path_index),
            hhi=_round4(hhi),
            concentration_norm=_round4(concentration_norm),
            concentration_premium=_round2(concentration_premium),
            blend_alpha=alpha,
            critical_owner_index=critical_owner_index,
            load_fallback_equal_shares=load_fallback_equal_shares,
        ),
    )


# ---------------------------------------------------------------------------
# Orchestration — score a per-owner roster, then aggregate
# ---------------------------------------------------------------------------


def score_and_aggregate_owner_roster(
    roster: list[dict[str, Any]],
    *,
    financial_data: Any = None,
    critical_path_weight: float = _DEFAULT_CRITICAL_PATH_WEIGHT,
    critical_path_load_floor: float = _DEFAULT_CRITICAL_PATH_LOAD_FLOOR,
    max_concentration_premium: float = _DEFAULT_MAX_CONCENTRATION_PREMIUM,
    critical_role_threshold: int = _DEFAULT_CRITICAL_ROLE_THRESHOLD,
) -> Optional[OwnerTeamAggregateResult]:
    """
    Score every roster member through the 12-factor owner-dependency
    engine, then aggregate the per-owner transferability indices into the
    composite.

    This is the bridge between a per-owner roster of 12-factor
    assessments and the single `composite_transferability_index` that
    `OwnerDependencyEngine.calculate_dependency_score` consumes — it
    closes the multi-owner computation chain:

        roster ──► score each owner ──► aggregate ──► composite ──► engine

    Each roster entry is a dict:
        factors:              OwnerDependencyFactors  (required — entries
                              without it are skipped)
        role_criticality:     int 1-5 (default 3)
        owner_hours_per_week: optional float
        owner_id / label:     optional, carried through to provenance

    Returns None for an empty roster (or one with no scorable members) —
    the caller falls back to single-owner scoring.

    Pure: the per-member engine calls are deterministic computation, no
    I/O. The engine import is lazy, mirroring `OwnerDependencyProcessor`,
    so this `owner_models` sibling never risks an import cycle with the
    engine module.
    """
    if not roster:
        return None

    from src.domain.owner_dependency_engine import OwnerDependencyEngine

    engine = OwnerDependencyEngine(financial_data, None)
    scored_members: list[dict[str, Any]] = []
    for entry in roster:
        factors = entry.get("factors")
        if factors is None:
            continue
        # No equity baseline passed → the heavy v2 transferability
        # profile is skipped; only the headline `overall_score` is needed.
        member_result = engine.calculate_dependency_score(factors)
        # Engine score: "less dependency = higher". TRI: the inverse
        # ("more key-person risk = higher").
        member_tri = _INDEX_MAX - float(member_result.overall_score)
        scored_members.append(
            {
                "transferability_index": member_tri,
                "role_criticality": entry.get("role_criticality", 3),
                "owner_hours_per_week": entry.get("owner_hours_per_week"),
                "owner_id": entry.get("owner_id"),
                "label": entry.get("label"),
            }
        )

    if not scored_members:
        return None

    return aggregate_owner_team(
        scored_members,
        critical_path_weight=critical_path_weight,
        critical_path_load_floor=critical_path_load_floor,
        max_concentration_premium=max_concentration_premium,
        critical_role_threshold=critical_role_threshold,
    )


def resolve_team_composite(
    owner_profile_roster: Optional[list[dict[str, Any]]],
    *,
    financial_data: Any = None,
) -> tuple[Optional[float], int]:
    """
    Collapse a multi-owner roster into the `(composite_transferability_index,
    owner_count)` pair that `OwnerDependencyProcessor.process_owner_dependency`
    consumes (BET-218).

    The synthesizer-facing adapter over `score_and_aggregate_owner_roster`:
    it scores + aggregates the roster, then unpacks just the two values the
    engine call needs. Keeping it here — rather than inlined in the
    synthesizer — gives the request-path wiring a single pure, testable seam.

    Returns `(None, 1)` for a missing / empty roster, or one with no scorable
    members. The engine then no-ops to single-owner scoring, which is the
    zero-regression default: a request that carries no roster behaves
    exactly as it does today. A single-owner roster collapses to exactly
    that owner's transferability index (the aggregator's pinned invariant).
    """
    if not owner_profile_roster:
        return None, 1

    result = score_and_aggregate_owner_roster(
        owner_profile_roster, financial_data=financial_data
    )
    if result is None:
        return None, 1

    return result.composite_transferability_index, result.owner_count
