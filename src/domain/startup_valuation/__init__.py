"""Startup valuation engine — isolated, pre-revenue / venture-stage methods.

This package is intentionally separate from ``src.domain.methods`` because
the math here does not consume historical financial statements.  It runs
on qualitative milestones, forward-looking traction and cap-table data and
blends three venture-capital methodologies (Berkus, Scorecard, VC Method,
SaaS Forward) into a single equity range.

Public surface:

- :class:`StartupInputs` — Pydantic v2 input contract.
- :func:`calculate_berkus`, :func:`calculate_scorecard`, :func:`calculate_vc`,
  :func:`calculate_saas_forward` — pure helper functions for each
  sub-methodology.
- :func:`blend` / :func:`blend_founder_view` — synthesis blenders.
- :func:`blend_to_method_result` — adapter to the canonical
  :class:`~src.api.schemas.stateless_api.MethodResult` envelope.
- :func:`apply_outlier_policy` — Tukey-style outlier cap (April 2026
  hardening).  Surfaces capped legs verbatim for the report.
- :func:`calculate_defensibility` — composite 0–10 score the report
  renders on the cover badge.
- :func:`is_saas_forward_compatible` — sector-policy gate for the SaaS
  Forward leg (only recurring-revenue SaaS / Fintech / Deeptech-AI
  sectors qualify).
- :func:`simulate_round` / :class:`CapTableSimulation` — Decimal-precise
  cap-table math.
- :class:`LegResult` / :class:`Money` helpers — shared primitives every
  leg adapts itself into.
"""

from .berkus import BerkusOutput, calculate_berkus
from .cap_table import CapTableSimulation, simulate_round
from .defensibility import (
    DefensibilityFactor,
    DefensibilityScore,
    calculate_defensibility,
    defensibility_payload,
)
from .founder_pedigree import (
    EVIDENCE_REQUIRED_CLAIMS,
    FounderPedigreeOutput,
    PedigreeFactor,
    calculate_founder_pedigree,
    pedigree_payload,
)
from .inception_lens import (
    InceptionLens,
    InceptionLensCalibration,
    InceptionLensOutput,
    apply_inception_lens,
    get_lens_calibration,
    lens_payload,
)
from .lifecycle_triage import (
    STARTUP_ROUTING_STAGES,
    STARTUP_ROUTING_TAGS,
    coerce_lifecycle_stage_triage,
    complete_lifecycle_stage_triage,
    infer_lifecycle_stage_triage,
    requires_founder_clarification,
    resolve_lifecycle_stage_triage,
    should_route_to_startup_path,
)
from .methodology_gate import (
    STARTUP_ALLOWED_METHOD_KEYS,
    STARTUP_BLOCKED_METHOD_KEYS,
    STARTUP_METHOD_OVERRIDE_CONTEXT_KEYS,
    StartupMethodologyRecommendation,
    apply_startup_methodology_gate,
    build_startup_methodology_recommendation,
    resolve_startup_methodology_override_provenance,
)
from .money import Q_EUR, Q_PCT, Q_RATE, LegResult, make_leg_result, q_eur, q_pct, q_rate
from .outlier_policy import (
    MAX_LEG_VS_MEDIAN,
    MIN_CAP_VS_MEDIAN,
    MIN_LEGS_FOR_POLICY,
    TUKEY_K,
    CappedLeg,
    OutlierPolicyOutput,
    apply_outlier_policy,
    cap_records_payload,
    policy_payload,
)
from .regional_data import (
    RegionalReferenceData,
    SectorDefaults,
    get_regional_reference_data,
    get_sector_defaults,
    list_sector_defaults,
)
from .saas_forward import SaasForwardOutput, calculate_saas_forward
from .schemas import (
    CapTableSummary,
    FounderPedigreeInputs,
    LifecycleConfidenceLevel,
    LifecycleRevenueState,
    LifecycleSignalProvenance,
    LifecycleStageCandidate,
    LifecycleStageTriage,
    RoundEvidenceQuality,
    RoundEvidenceSource,
    RoundInstrument,
    RoundScenario,
    RoundStatus,
    RoundValueRelationship,
    SafeNote,
    StartupBenchmarkEvidenceQuality,
    StartupBenchmarkGeographyScope,
    StartupBenchmarkInput,
    StartupBenchmarkSourceType,
    StartupInputs,
    StartupSector,
    StartupStage,
)
from .scorecard import ScorecardOutput, calculate_scorecard
from .sector_policy import (
    SAAS_FORWARD_COMPATIBLE_SECTORS,
    is_saas_forward_compatible,
    saas_forward_skip_reason,
)
from .synthesis import StartupBlendOutput, blend, blend_founder_view, blend_to_method_result
from .vc_method import VcOutput, calculate_vc

__all__ = [
    "BerkusOutput",
    "CapTableSimulation",
    "CapTableSummary",
    "CappedLeg",
    "DefensibilityFactor",
    "DefensibilityScore",
    "EVIDENCE_REQUIRED_CLAIMS",
    "FounderPedigreeInputs",
    "FounderPedigreeOutput",
    "InceptionLens",
    "InceptionLensCalibration",
    "InceptionLensOutput",
    "LegResult",
    "LifecycleConfidenceLevel",
    "LifecycleRevenueState",
    "LifecycleSignalProvenance",
    "LifecycleStageCandidate",
    "LifecycleStageTriage",
    "MAX_LEG_VS_MEDIAN",
    "MIN_CAP_VS_MEDIAN",
    "MIN_LEGS_FOR_POLICY",
    "OutlierPolicyOutput",
    "PedigreeFactor",
    "Q_EUR",
    "Q_PCT",
    "Q_RATE",
    "RegionalReferenceData",
    "RoundEvidenceQuality",
    "RoundEvidenceSource",
    "RoundInstrument",
    "RoundScenario",
    "RoundStatus",
    "RoundValueRelationship",
    "SAAS_FORWARD_COMPATIBLE_SECTORS",
    "STARTUP_ALLOWED_METHOD_KEYS",
    "STARTUP_BLOCKED_METHOD_KEYS",
    "STARTUP_METHOD_OVERRIDE_CONTEXT_KEYS",
    "STARTUP_ROUTING_STAGES",
    "STARTUP_ROUTING_TAGS",
    "SaasForwardOutput",
    "SafeNote",
    "ScorecardOutput",
    "SectorDefaults",
    "StartupBlendOutput",
    "StartupInputs",
    "StartupMethodologyRecommendation",
    "StartupSector",
    "StartupStage",
    "TUKEY_K",
    "VcOutput",
    "apply_startup_methodology_gate",
    "apply_inception_lens",
    "apply_outlier_policy",
    "blend",
    "blend_founder_view",
    "blend_to_method_result",
    "build_startup_methodology_recommendation",
    "calculate_berkus",
    "calculate_defensibility",
    "calculate_founder_pedigree",
    "calculate_saas_forward",
    "calculate_scorecard",
    "calculate_vc",
    "cap_records_payload",
    "coerce_lifecycle_stage_triage",
    "complete_lifecycle_stage_triage",
    "defensibility_payload",
    "infer_lifecycle_stage_triage",
    "get_lens_calibration",
    "get_regional_reference_data",
    "get_sector_defaults",
    "is_saas_forward_compatible",
    "lens_payload",
    "list_sector_defaults",
    "make_leg_result",
    "pedigree_payload",
    "policy_payload",
    "q_eur",
    "q_pct",
    "q_rate",
    "resolve_startup_methodology_override_provenance",
    "resolve_lifecycle_stage_triage",
    "requires_founder_clarification",
    "saas_forward_skip_reason",
    "should_route_to_startup_path",
    "simulate_round",
]
