"""Liquidation Analysis subpackage.

Self-contained module for the orderly + forced liquidation valuation
method, with Phase 1 academic depth (premise of value, distress
probability, 12-class realisation schedule).

Public surface
--------------
Core scenarios (round-1 MVP, still stable):
- ``compute_liquidation_scenarios(...)`` — pure function returning a
  ``LiquidationScenarios`` payload.
- ``LiquidationScenarios`` / ``LiquidationScenario`` — typed result.
- ``LIQUIDATION_LABEL`` — Dutch label constant.
- ``LiquidationUnavailableReason`` — enum of unavailable codes.
- ``ORDERLY_FACTORS`` / ``FORCED_FACTORS`` — 8-class flat factors.

Phase 1 (Big-4 academic depth):
- ``AssetClass`` / ``AssetLine`` / ``AssetSchedule`` — 12-class
  realisation schedule with per-class adjusted FMV, recovery factor,
  disposal-month hint, and reconciliation against balance-sheet total.
- ``ORDERLY_CLASS_FACTORS`` / ``FORCED_CLASS_FACTORS`` — extended
  12-class factor tables.
- ``DistressAssessment`` / ``DistressZone`` / ``assess_distress_probability``
  — Altman Z'' (2000) private-firm score + zone + bounded P(distress).
- ``PremiseOfValue`` / ``PremiseDecision`` / ``select_premise`` /
  ``expected_value`` — IVS 104 §60–80 premise selector with the
  probability-weighted expected-value reconciliation.

What lives where
----------------
- 8-class flat factors: ``factors.py``
- 12-class extended factors + disposal-month: ``asset_schedule.py``
- Scenario math + insolvency recovery + premise/distress wire-up:
  ``scenarios.py``
- Result payloads: ``payloads.py``
- Distress probability (Altman Z''): ``distress_probability.py``
- Premise of value selector (IVS 104): ``premise.py``

Out of scope (deferred to later phases)
---------------------------------------
- Insolvency priority waterfall (BE/NL): Phase 2.
- Tax leakage on liquidation (BE 30% liquidatiebonus etc.): Phase 2.
- Wind-down cost build-up (bottom-up): Phase 2.
- PV-discounted disposal timeline + sensitivity: Phase 3.
- NACE-mapped recovery factors via Delphi: Phase 4.
"""

from .asset_schedule import (
    FORCED_CLASS_FACTORS,
    FORCED_DISPOSAL_MONTH,
    ORDERLY_CLASS_FACTORS,
    ORDERLY_DISPOSAL_MONTH,
    AssetClass,
    AssetLine,
    AssetSchedule,
    build_asset_schedule,
)
from .audit_trail import (
    AUDIT_TRAIL_SOURCES,
    ENGINE_VERSION,
    ENGINE_VERSION_NOTES,
    AuditTrail,
    build_audit_trail,
)
from .creditor_letters import (
    CREDITOR_LETTER_SOURCES,
    CreditorLetter,
    CreditorLetterPack,
    LetterUrgency,
    build_creditor_letter_pack,
)
from .disclosure import (
    DISCLOSURE_SOURCES,
    DisclosureBlock,
    FairValueHierarchyEntry,
    FairValueLevel,
    build_disclosure_block,
)
from .disposal_schedule_pv import (
    PV_SOURCES,
    DisposalLinePV,
    DisposalSchedulePV,
    compute_disposal_schedule_pv,
)
from .distress_probability import (
    DISTRESS_SOURCES,
    DistressAssessment,
    DistressRatios,
    DistressUnavailableReason,
    DistressZone,
    assess_distress_probability,
)
from .factors import FORCED_FACTORS, LIQUIDATION_SOURCES, ORDERLY_FACTORS
from .nace_factors import (
    NACE_FACTOR_SOURCES,
    CohortConfidence,
    CohortFactor,
    CohortStore,
    LocalCohortStore,
    lookup_recovery_factor,
)
from .payloads import (
    LIQUIDATION_LABEL,
    LiquidationScenario,
    LiquidationScenarios,
    LiquidationUnavailableReason,
)
from .premise import (
    PREMISE_SOURCES,
    PremiseDecision,
    PremiseOfValue,
    PremiseSelectionTrigger,
    expected_value,
    select_premise,
)
from .premise_reconciliation import (
    RECONCILIATION_SOURCES,
    PremiseRecommendation,
    PremiseReconciliation,
    reconcile_premises,
)
from .priority_cascade import (
    CASCADE_SOURCES_BE,
    CASCADE_SOURCES_NL,
    CascadeJurisdiction,
    CascadeTier,
    CascadeTierCode,
    PriorityCascade,
    compute_priority_cascade,
)
from .replacement_cost import (
    REPLACEMENT_COST_SOURCES,
    ReplacementCostEstimate,
    ReplacementCostLine,
    compute_replacement_cost,
)
from .scenarios import compute_liquidation_scenarios
from .sensitivity import (
    SENSITIVITY_SOURCES,
    SensitivityDriver,
    SensitivityResult,
    TornadoBar,
    build_default_drivers,
    compute_sensitivity,
)
from .statement_of_affairs import (
    STATEMENT_OF_AFFAIRS_SOURCES,
    MAndABand,
    StatementOfAffairs,
    WaterfallStep,
    WaterfallStepKind,
    build_statement_of_affairs,
)
from .strategic_buyer_scenarios import (
    STRATEGIC_BUYER_SOURCES,
    BuyerProfile,
    BuyerScenario,
    StrategicBuyerScenarios,
    build_strategic_buyer_scenarios,
)
from .sufficiency_memo import (
    SUFFICIENCY_MEMO_SOURCES,
    CoverageVerdict,
    SufficiencyMemo,
    TierVerdict,
    build_sufficiency_memo,
)
from .tax_leakage import (
    BE_LIQUIDATION_BONUS_RATE,
    TAX_LEAKAGE_SOURCES_BE,
    TAX_LEAKAGE_SOURCES_NL,
    TaxLeakageBridge,
    TaxLeakageJurisdiction,
    TaxLeakageLine,
    compute_be_tax_leakage,
    compute_nl_tax_leakage,
    compute_tax_leakage,
)
from .wind_down_costs import (
    WIND_DOWN_SOURCES,
    WindDownComponent,
    WindDownCostEstimate,
    WindDownLine,
    compute_wind_down_costs,
)

__all__ = [
    # Core MVP surface (kept stable)
    "FORCED_FACTORS",
    "LIQUIDATION_LABEL",
    "LIQUIDATION_SOURCES",
    "LiquidationScenario",
    "LiquidationScenarios",
    "LiquidationUnavailableReason",
    "ORDERLY_FACTORS",
    "compute_liquidation_scenarios",
    # Phase 1 — Asset schedule
    "AssetClass",
    "AssetLine",
    "AssetSchedule",
    "FORCED_CLASS_FACTORS",
    "FORCED_DISPOSAL_MONTH",
    "ORDERLY_CLASS_FACTORS",
    "ORDERLY_DISPOSAL_MONTH",
    "build_asset_schedule",
    # Phase 1 — Distress probability
    "DISTRESS_SOURCES",
    "DistressAssessment",
    "DistressRatios",
    "DistressUnavailableReason",
    "DistressZone",
    "assess_distress_probability",
    # Phase 1 — Premise of value
    "PREMISE_SOURCES",
    "PremiseDecision",
    "PremiseOfValue",
    "PremiseSelectionTrigger",
    "expected_value",
    "select_premise",
    # Phase 2 — Insolvency cascade (BE + NL)
    "CASCADE_SOURCES_BE",
    "CASCADE_SOURCES_NL",
    "CascadeJurisdiction",
    "CascadeTier",
    "CascadeTierCode",
    "PriorityCascade",
    "compute_priority_cascade",
    # Phase 2 — Tax leakage
    "BE_LIQUIDATION_BONUS_RATE",
    "TAX_LEAKAGE_SOURCES_BE",
    "TAX_LEAKAGE_SOURCES_NL",
    "TaxLeakageBridge",
    "TaxLeakageJurisdiction",
    "TaxLeakageLine",
    "compute_be_tax_leakage",
    "compute_nl_tax_leakage",
    "compute_tax_leakage",
    # Phase 2 — Wind-down cost build-up
    "WIND_DOWN_SOURCES",
    "WindDownComponent",
    "WindDownCostEstimate",
    "WindDownLine",
    "compute_wind_down_costs",
    # Phase 3 — PV-discounted disposal
    "PV_SOURCES",
    "DisposalLinePV",
    "DisposalSchedulePV",
    "compute_disposal_schedule_pv",
    # Phase 3 — Sensitivity engine
    "SENSITIVITY_SOURCES",
    "SensitivityDriver",
    "SensitivityResult",
    "TornadoBar",
    "build_default_drivers",
    "compute_sensitivity",
    # Phase 3 — Premise reconciliation
    "RECONCILIATION_SOURCES",
    "PremiseReconciliation",
    "PremiseRecommendation",
    "reconcile_premises",
    # Phase 4 — Delphi NACE recovery factors
    "CohortConfidence",
    "CohortFactor",
    "CohortStore",
    "LocalCohortStore",
    "NACE_FACTOR_SOURCES",
    "lookup_recovery_factor",
    # Phase 4 — IVS 104 / USPAP / IFRS 13 disclosure
    "DISCLOSURE_SOURCES",
    "DisclosureBlock",
    "FairValueHierarchyEntry",
    "FairValueLevel",
    "build_disclosure_block",
    # Phase 4+ — Replacement cost (M&A buyer ceiling)
    "REPLACEMENT_COST_SOURCES",
    "ReplacementCostEstimate",
    "ReplacementCostLine",
    "compute_replacement_cost",
    # Phase 4+ — Statement of Affairs (Section 0)
    "STATEMENT_OF_AFFAIRS_SOURCES",
    "MAndABand",
    "StatementOfAffairs",
    "WaterfallStep",
    "WaterfallStepKind",
    "build_statement_of_affairs",
    # Phase 4+ — Audit trail (digitalised M&A reproducibility)
    "AUDIT_TRAIL_SOURCES",
    "ENGINE_VERSION",
    "ENGINE_VERSION_NOTES",
    "AuditTrail",
    "build_audit_trail",
    # Phase 5 — Lawyer/accountant-grade reductions ("M&A magic")
    "SUFFICIENCY_MEMO_SOURCES",
    "CoverageVerdict",
    "SufficiencyMemo",
    "TierVerdict",
    "build_sufficiency_memo",
    "CREDITOR_LETTER_SOURCES",
    "CreditorLetter",
    "CreditorLetterPack",
    "LetterUrgency",
    "build_creditor_letter_pack",
    "STRATEGIC_BUYER_SOURCES",
    "BuyerProfile",
    "BuyerScenario",
    "StrategicBuyerScenarios",
    "build_strategic_buyer_scenarios",
]
