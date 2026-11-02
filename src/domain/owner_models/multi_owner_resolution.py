"""
Multi-owner transferability resolution (BET-218).

Feature-flag-gated decision for which transferability index the valuation
engine treats as authoritative:

  - single-owner roster, OR the flag off  -> the single-owner index
    (today's behaviour, byte-identical -> zero regression)
  - multi-owner roster AND the flag on    -> the composite index that
    Titan's owner-team aggregator computes over the per-owner roster

This module is the SEAM for the Phase 1 engine swap. It deliberately
does NOT touch the owner-dependency engine's 12-factor maths — it only
decides which index value is authoritative, so the swap lands as a
small, auditable change carrying an explicit zero-regression guarantee.

The transferability index convention here matches Titan: 0-100, where a
HIGHER value means MORE key-person risk (less transferable).

Academic / design basis:
- BET-218 multi-owner profiling; Phase 0 team-aggregator design.
- A single irreplaceable founder must cap the venture even when diluted;
  a silent co-owner must not average a venture's risk down. Those
  invariants live in the aggregator — this module only routes its output.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# Public flag name (telemetry / logs) and the env var that toggles it.
MULTI_OWNER_PROFILE_V1_FLAG = "multi_owner_profile_v1"
_FLAG_ENV_VAR = "MULTI_OWNER_PROFILE_V1"

_TRUTHY = frozenset({"1", "true", "yes", "on"})

_INDEX_MIN = 0.0
_INDEX_MAX = 100.0

# Resolution sources — surfaced on the result for audit / provenance.
SOURCE_SINGLE_OWNER = "single_owner"
SOURCE_MULTI_OWNER_COMPOSITE = "multi_owner_composite"


def is_multi_owner_v1_enabled() -> bool:
    """True when the `multi_owner_profile_v1` flag is switched on via env."""
    return os.environ.get(_FLAG_ENV_VAR, "").strip().lower() in _TRUTHY


@dataclass(frozen=True)
class ResolvedTransferability:
    """The transferability index the engine should consume, plus provenance."""

    transferability_index: float
    source: str
    owner_count: int
    flag_enabled: bool
    rationale: str


def _clamp_index(value: float | int | None) -> float | None:
    """Clamp a transferability index into [0, 100]; pass through None."""
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric != numeric:  # NaN
        return None
    return max(_INDEX_MIN, min(_INDEX_MAX, numeric))


def resolve_transferability_index(
    *,
    single_owner_index: float | int | None,
    composite_index: float | int | None,
    owner_count: int,
    flag_enabled: bool,
) -> ResolvedTransferability:
    """
    Decide which transferability index is authoritative for this valuation.

    The multi-owner composite is used only when ALL of the following hold:
      1. the `multi_owner_profile_v1` flag is enabled,
      2. a composite index was supplied (Titan ran the team aggregator),
      3. the roster genuinely has more than one owner.

    In every other case the single-owner index is returned unchanged —
    this is the zero-regression guarantee: a solo client, or a deployment
    with the flag off, behaves exactly as it does today.

    Args:
        single_owner_index: today's single-owner transferability index.
        composite_index: aggregator output over the per-owner roster.
        owner_count: number of owners on the roster (clamped to >= 1).
        flag_enabled: whether `multi_owner_profile_v1` is on.

    Returns:
        ResolvedTransferability with the chosen value, its source and a
        human-readable rationale for the audit trail.
    """
    safe_owner_count = max(1, int(owner_count) if owner_count else 1)
    single_clamped = _clamp_index(single_owner_index)
    composite_clamped = _clamp_index(composite_index)

    use_composite = (
        flag_enabled and composite_clamped is not None and safe_owner_count > 1
    )

    if use_composite:
        return ResolvedTransferability(
            transferability_index=composite_clamped,  # type: ignore[arg-type]
            source=SOURCE_MULTI_OWNER_COMPOSITE,
            owner_count=safe_owner_count,
            flag_enabled=flag_enabled,
            rationale=(
                f"Multi-owner composite index applied across "
                f"{safe_owner_count} owners (multi_owner_profile_v1 on)."
            ),
        )

    # ----- single-owner path (zero-regression) -----
    resolved_value = single_clamped if single_clamped is not None else _INDEX_MIN

    if not flag_enabled:
        rationale = "multi_owner_profile_v1 disabled — single-owner index used."
    elif safe_owner_count <= 1:
        rationale = "Single-owner roster — single-owner index used (zero-regression)."
    elif composite_clamped is None:
        rationale = (
            "No composite index supplied — single-owner index used "
            "(aggregator did not run)."
        )
    else:  # pragma: no cover - defensive; covered logically by the branches above
        rationale = "Single-owner index used."

    return ResolvedTransferability(
        transferability_index=resolved_value,
        source=SOURCE_SINGLE_OWNER,
        owner_count=safe_owner_count,
        flag_enabled=flag_enabled,
        rationale=rationale,
    )
