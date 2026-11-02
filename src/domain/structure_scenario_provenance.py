"""Provenance gate for structure-linked forward valuation scenarios.

Structure work is not itself a source of monetary uplift. A scenario may use a
structure action only when ValuationIQ has recalculated company-specific inputs
from an eligible, auditable Belgian evidence revision.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from src.domain.forward_method_registry import (
    AssumptionEvidence,
    AssumptionSourceKind,
    AssumptionUseKind,
    ForwardEvidenceConfidence,
)

_STRUCTURE_ACTION_IDS = frozenset({"simplify_legal_structure", "structure_cleanup"})
_REQUIRED_PROVENANCE = frozenset(
    {
        "valuation_iq:company_specific_structure_scenario_v1",
        "source:valuation_iq_holdings_consolidation",
        "structure_evidence_contract:be_structure_evidence_v1",
        "structure_evidence_gate:eligible",
        "calculation_basis:company_specific_financial_inputs",
    }
)
_REQUIRED_PROVENANCE_PREFIXES = (
    "company_id:",
    "valuation_run_id:",
    "evidence_revision:",
    "playbook_version:",
    "evidence_reference:",
)


class _ScenarioDelta(Protocol):
    value_up_action_id: str | None
    evidence: AssumptionEvidence
    method_keys: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class StructureScenarioProvenanceGate:
    """Whether a scenario is supported by auditable structure evidence."""

    allowed: bool
    reasons: tuple[str, ...]


def _has_populated_prefix(provenance: set[str], prefix: str) -> bool:
    return any(token.startswith(prefix) and token != prefix for token in provenance)


def _evidence_is_grounded(delta: _ScenarioDelta) -> bool:
    evidence = delta.evidence
    return (
        evidence.use_kind == AssumptionUseKind.SCENARIO_DELTA
        and evidence.source_kind == AssumptionSourceKind.INTEGRATION_OBSERVED
        and evidence.confidence == ForwardEvidenceConfidence.HIGH
        and evidence.source == "valuation_iq_holdings_consolidation"
        and evidence.responsible_surface == "valuation_iq_forward_projection_engine"
        and bool(evidence.transformation and evidence.transformation.strip())
        and not evidence.fallback
        and bool(delta.method_keys)
        and not any(
            "heuristic" in warning.lower() or "fallback" in warning.lower()
            for warning in (*evidence.warnings, *delta.warnings)
        )
    )


def evaluate_structure_scenario_provenance(
    deltas: Sequence[_ScenarioDelta],
    provenance: Sequence[str],
) -> StructureScenarioProvenanceGate:
    """Block unsupported drivers and ungrounded structure monetary scenarios."""

    reasons = [
        "unsupported_scenario_driver_group"
        for delta in deltas
        if "unsupported_scenario_driver_group" in delta.warnings
    ]
    structure_deltas = [
        delta for delta in deltas if delta.value_up_action_id in _STRUCTURE_ACTION_IDS
    ]
    if not structure_deltas:
        unique_reasons = tuple(dict.fromkeys(reasons))
        return StructureScenarioProvenanceGate(not unique_reasons, unique_reasons)

    tokens = {str(token).strip() for token in provenance if str(token).strip()}
    if any("heuristic" in token.lower() for token in tokens):
        reasons.append("structure_scenario_heuristic_blocked")
    if not _REQUIRED_PROVENANCE.issubset(tokens) or any(
        not _has_populated_prefix(tokens, prefix) for prefix in _REQUIRED_PROVENANCE_PREFIXES
    ):
        reasons.append("structure_scenario_provenance_incomplete")
    if any(not _evidence_is_grounded(delta) for delta in structure_deltas):
        reasons.append("structure_scenario_evidence_incomplete")

    unique_reasons = tuple(dict.fromkeys(reasons))
    return StructureScenarioProvenanceGate(not unique_reasons, unique_reasons)


__all__ = ["StructureScenarioProvenanceGate", "evaluate_structure_scenario_provenance"]
