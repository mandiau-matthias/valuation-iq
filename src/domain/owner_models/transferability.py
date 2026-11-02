"""Transferability v2 facade.

The v2 owner-transferability model is intentionally split into focused,
pure-domain modules. This facade preserves the historical import surface for
engines, processors, renderers, and tests that import from
``src.domain.owner_models.transferability``.
"""

from __future__ import annotations

from src.domain.owner_models.transferability_buyer_gap import (
    _BUYER_PROFILE_BANDS,
    _SEVERITY_TIERS,
    _buyer_rationale,
    _raw_discount_for_severity,
    _severity_for_gap,
    BuyerArchetype,
    BuyerProfile,
    GapSeverity,
    TransferabilityGap,
    compute_transferability_gap,
    derive_buyer_profile,
)
from src.domain.owner_models.transferability_citations import (
    EU_SME_SEGMENT_LABELS,
    METHODOLOGY_CITATIONS,
    MethodologyCitation,
)
from src.domain.owner_models.transferability_decomposition import (
    SUB_FACTOR_GROUPS,
    SUB_FACTOR_LABELS_EN,
    _band_for_score,
    SubFactorScore,
    TransferabilityDecomposition,
    decompose_factors,
)
from src.domain.owner_models.transferability_incidence import (
    METHOD_INCIDENCE,
    _METHOD_LABELS_EN,
    _METHOD_RATIONALE_EN,
    _format_pct,
    CascadeLineData,
    MethodIncidence,
    blended_incidence,
    build_cascade_data,
    build_narrative_cascade,
    method_incidence_table,
)
from src.domain.owner_models.transferability_profile import (
    ConfidenceAssessment,
    ConfidenceTier,
    TransferabilityProfile,
    build_transferability_profile,
    derive_confidence_tier,
)

__all__ = [
    "BuyerArchetype",
    "BuyerProfile",
    "CascadeLineData",
    "ConfidenceAssessment",
    "ConfidenceTier",
    "EU_SME_SEGMENT_LABELS",
    "GapSeverity",
    "METHOD_INCIDENCE",
    "METHODOLOGY_CITATIONS",
    "MethodIncidence",
    "MethodologyCitation",
    "SUB_FACTOR_GROUPS",
    "SUB_FACTOR_LABELS_EN",
    "SubFactorScore",
    "TransferabilityDecomposition",
    "TransferabilityGap",
    "TransferabilityProfile",
    "_BUYER_PROFILE_BANDS",
    "_METHOD_LABELS_EN",
    "_METHOD_RATIONALE_EN",
    "_SEVERITY_TIERS",
    "_band_for_score",
    "_buyer_rationale",
    "_format_pct",
    "_raw_discount_for_severity",
    "_severity_for_gap",
    "blended_incidence",
    "build_cascade_data",
    "build_narrative_cascade",
    "build_transferability_profile",
    "compute_transferability_gap",
    "decompose_factors",
    "derive_buyer_profile",
    "derive_confidence_tier",
    "method_incidence_table",
]
