"""Executed-methodology context helpers for OmniCalc enrichment."""

from typing import Literal, NamedTuple, Optional


def _normalize_methodology_token_for_omni(methodology: Optional[object]) -> str:
    """Normalize methodology from the determiner, API, or Enum into one token."""
    if methodology is None:
        return ""
    if isinstance(methodology, str):
        s = methodology.strip()
        if not s:
            return ""
        s = s.replace("-", "_")
        return "_".join(s.upper().split())
    val = getattr(methodology, "value", None)
    if isinstance(val, str) and val.strip():
        s = val.strip().replace("-", "_")
        return "_".join(s.upper().split())
    name = getattr(methodology, "name", None)
    if isinstance(name, str) and name.strip():
        return name.strip().upper().replace("-", "_")
    s = str(methodology).strip().replace("-", "_")
    return "_".join(s.upper().split()) if s else ""


class _OmniExecutionContext(NamedTuple):
    executed_methodology_token: str
    primary_basis: Literal["hybrid", "asset_based"]


def _resolve_omni_execution_context(methodology: Optional[object]) -> _OmniExecutionContext:
    """Return the normalized executed methodology token plus omni primary basis."""
    token = _normalize_methodology_token_for_omni(methodology)
    primary_basis: Literal["hybrid", "asset_based"] = (
        "asset_based" if token == "ASSET_BASED" else "hybrid"
    )
    return _OmniExecutionContext(executed_methodology_token=token, primary_basis=primary_basis)


def _omni_primary_basis_from_executed_methodology(
    methodology: Optional[object],
) -> Literal["hybrid", "asset_based"]:
    """Backward-compatible accessor for callers/tests that only need the primary basis."""
    return _resolve_omni_execution_context(methodology).primary_basis
