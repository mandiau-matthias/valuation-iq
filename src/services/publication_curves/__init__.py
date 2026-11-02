"""Deterministic, offline-only public valuation curves for Workstream D v9.

The package deliberately has no database, HTTP, Athena, Delphi, or Railway
dependency.  A campaign binds frozen multiple contracts before any company is
calculated and emits immutable results that a separate importer may persist.
"""

from .batch import execute_campaign_page
from .campaign_io import (
    PublicCurveCampaignIOError,
    build_campaign,
    execute_campaign_to_directory,
    load_frozen_multiple_artifact,
)
from .company_knowledge_curve_v1 import (
    COMPANY_KNOWLEDGE_CURVE_RULESET_VERSION,
    CompanyKnowledgeCurveV1,
    KnowledgeCurveLevel,
    KnowledgeCurveStage,
    MaterialFactBindingV1,
    MaterialFactCategory,
    PeriodMaterialFactCoverageV1,
)
from .contracts import (
    BenchmarkContractV2,
    BroadMedianPriorContractV1,
    CampaignJobV1,
    ClosedDealObservationV1,
    ConfidenceLevel,
    CurveCompanyInputV1,
    FrozenMultipleSnapshotV1,
    GovernedModelCellV1,
    MappingStatus,
    ModelPriorContractV1,
    MultipleMetric,
    OfficialFinancialPeriodV1,
    PublicCurveCampaignPlanV1,
    RevenueSourceKind,
    StatementScope,
    ValueBasis,
    ValuationGrade,
)
from .runner import (
    CURRENT_MODEL_HISTORICAL_LABEL,
    PUBLICATION_GRADE_PERIOD_FLOORS,
    run_public_curve,
    to_public_seal_v9,
)

__all__ = [
    "BenchmarkContractV2",
    "BroadMedianPriorContractV1",
    "CURRENT_MODEL_HISTORICAL_LABEL",
    "CampaignJobV1",
    "ClosedDealObservationV1",
    "ConfidenceLevel",
    "COMPANY_KNOWLEDGE_CURVE_RULESET_VERSION",
    "CompanyKnowledgeCurveV1",
    "CurveCompanyInputV1",
    "FrozenMultipleSnapshotV1",
    "GovernedModelCellV1",
    "MappingStatus",
    "KnowledgeCurveStage",
    "KnowledgeCurveLevel",
    "MaterialFactBindingV1",
    "MaterialFactCategory",
    "ModelPriorContractV1",
    "MultipleMetric",
    "OfficialFinancialPeriodV1",
    "PeriodMaterialFactCoverageV1",
    "PUBLICATION_GRADE_PERIOD_FLOORS",
    "PublicCurveCampaignPlanV1",
    "PublicCurveCampaignIOError",
    "RevenueSourceKind",
    "StatementScope",
    "ValueBasis",
    "ValuationGrade",
    "execute_campaign_page",
    "build_campaign",
    "execute_campaign_to_directory",
    "load_frozen_multiple_artifact",
    "run_public_curve",
    "to_public_seal_v9",
]
