"""Liquidation analysis method-detail schemas and builder."""

from typing import Any, Dict, List, Optional, TypedDict


class LiquidationScenarioDetails(TypedDict, total=False):
    """One scenario block (orderly OR forced) within liquidation details."""

    method: str  # "orderly_liquidation" | "forced_liquidation"
    equity_value: float
    total_assets_book: float
    total_assets_adjusted: float
    total_liabilities_book: float
    total_liabilities_adjusted: float
    net_asset_value_unclamped: float
    value_low: float
    value_high: float
    asset_adjustments: List[Dict[str, Any]]
    would_be_insolvent: bool
    warnings: List[str]
    rationale: str


class DistressRatiosDetails(TypedDict, total=False):
    """Altman Z'' input ratios (Phase 1)."""

    x1_working_capital_ratio: float
    x2_retained_earnings_ratio: float
    x3_ebit_ratio: float
    x4_equity_to_liabilities: float


class DistressDetails(TypedDict, total=False):
    """Altman Z'' assessment surfaced inside liquidation details (Phase 1)."""

    model_version: str
    assessment_status: str
    probability_status: str
    z_double_prime: Optional[float]
    zone: str  # "safe" | "grey" | "distress" | "undetermined"
    probability_of_distress: Optional[float]
    ratios: Optional[DistressRatiosDetails]
    rationale: str
    sources: List[str]
    available: bool
    unavailable_code: Optional[str]
    warnings: List[str]


class PremiseDetails(TypedDict, total=False):
    """Advisory scenario comparison; no calibrated probability weights."""

    assessment_status: str
    primary: str  # "going_concern" | "orderly_liquidation" | "forced_liquidation"
    secondary: str
    probability_of_distress: Optional[float]
    going_concern_weight: Optional[float]
    liquidation_weight: Optional[float]
    trigger: str
    rationale: str
    sources: List[str]


class AssetLineDetails(TypedDict, total=False):
    """One row of the 12-class realisation schedule (Phase 1)."""

    asset_class: str
    label: str
    source_account_code: Optional[str]
    book_value: float
    adjusted_value: float
    orderly_recovery_factor: float
    forced_recovery_factor: float
    orderly_realisable_value: float
    forced_realisable_value: float
    orderly_disposal_month: int
    forced_disposal_month: int
    rationale: str


class AssetScheduleDetails(TypedDict, total=False):
    """12-class realisation schedule contract (Phase 1)."""

    lines: List[AssetLineDetails]
    total_book: float
    total_adjusted: float
    total_orderly_realisable: float
    total_forced_realisable: float
    unallocated_book: float
    warnings: List[str]
    sources: List[str]


class CascadeTierDetails(TypedDict, total=False):
    """One row in the priority waterfall (Phase 2)."""

    code: str
    label: str
    claim_amount: float
    recovery_amount: float
    recovery_rate: float
    shortfall: float
    statutory_anchor: str
    rationale: str


class PriorityCascadeDetails(TypedDict, total=False):
    """BE Boek XX WER / NL Faillissementswet cascade (Phase 2)."""

    jurisdiction: str  # "BE" | "NL"
    gross_proceeds: float
    tiers: List[CascadeTierDetails]
    equity_to_shareholders: float
    total_claims: float
    total_recovered: float
    total_shortfall: float
    sources: List[str]
    warnings: List[str]
    input_liability_buckets: Dict[str, float]


class TaxLeakageLineDetails(TypedDict, total=False):
    label: str
    gross: float
    rate: float
    tax_amount: float
    statutory_anchor: str
    rationale: str


class TaxLeakageDetails(TypedDict, total=False):
    """BE liquidatiebonus + NL box-2 + DTL bridge (Phase 2)."""

    jurisdiction: str
    gross_distribution: float
    paid_up_capital: float
    taxable_base: float
    lines: List[TaxLeakageLineDetails]
    total_tax_leakage: float
    net_to_shareholders: float
    sources: List[str]
    warnings: List[str]


class WindDownLineDetails(TypedDict, total=False):
    component: str
    label: str
    amount: float
    statutory_anchor: str
    rationale: str


class WindDownDetails(TypedDict, total=False):
    """Bottom-up wind-down cost build-up (Phase 2)."""

    scenario: str
    runway_months: int
    headcount: int
    lines: List[WindDownLineDetails]
    total: float
    sources: List[str]
    warnings: List[str]


class DisposalLinePVDetails(TypedDict, total=False):
    asset_class: str
    label: str
    nominal_value: float
    disposal_month: int
    discount_rate_annual: float
    discount_factor: float
    pv_value: float
    pv_haircut: float


class DisposalSchedulePVDetails(TypedDict, total=False):
    """PV-discounted disposal schedule (Phase 3)."""

    scenario: str
    discount_rate_annual: float
    lines: List[DisposalLinePVDetails]
    total_nominal: float
    total_pv: float
    total_pv_haircut: float
    sources: List[str]


class TornadoBarDetails(TypedDict, total=False):
    driver_name: str
    label: str
    impact_low: float
    impact_high: float
    impact_range: float


class SensitivityDriverDetails(TypedDict, total=False):
    name: str
    label: str
    central: float
    low: float
    high: float


class SensitivityDetails(TypedDict, total=False):
    """Tornado + P10/P50/P90 quantiles (Phase 3)."""

    central: float
    p10: float
    p50: float
    p90: float
    tornado: List[TornadoBarDetails]
    sample_count: int
    drivers: List[SensitivityDriverDetails]
    sources: List[str]


class PremiseReconciliationDetails(TypedDict, total=False):
    """LV vs Adj-NAV vs DCF reconciliation (Phase 3)."""

    liquidation_value: float
    adjusted_nav: Optional[float]
    dcf_value: Optional[float]
    multiples_value: Optional[float]
    going_concern_defensible: Optional[bool]
    recommendation: str
    rationale: str
    sources: List[str]


class FairValueHierarchyEntryDetails(TypedDict, total=False):
    item_label: str
    level: str  # "level_1" | "level_2" | "level_3"
    rationale: str


class DisclosureDetails(TypedDict, total=False):
    """IVS 104 §10 / USPAP STANDARD 9 / IFRS 13 (Phase 4)."""

    bases_of_value: List[str]
    premise_of_value: str
    approaches_used: List[str]
    methodology_compliance: str
    fair_value_hierarchy: List[FairValueHierarchyEntryDetails]
    limitations: List[str]
    out_of_scope: List[str]
    assumptions: List[str]
    sources: List[str]
    signatory: Dict[str, str]


class ReplacementCostLineDetails(TypedDict, total=False):
    """One row in the replacement-cost build-up (M&A ceiling)."""

    asset_class: str
    label: str
    book_value: float
    crn_multiplier: float
    crn_value: float
    remaining_life_factor: float
    depreciated_value: float


class ReplacementCostDetails(TypedDict, total=False):
    """M&A buyer ceiling per IVS 105 §60-90."""

    lines: List[ReplacementCostLineDetails]
    total_book: float
    tangible_replacement_value: float
    identifiable_intangibles_uplift_pct: float
    identifiable_intangibles_uplift: float
    total_replacement_cost: float
    sources: List[str]
    rationale: str


class WaterfallStepDetails(TypedDict, total=False):
    kind: str  # "gross" | "deduction" | "subtotal" | "net"
    label: str
    amount: float
    running_total: float
    rationale: str


class MAndABandDetails(TypedDict, total=False):
    floor: float
    floor_label: str
    reference: Optional[float]
    reference_label: Optional[str]
    ceiling: Optional[float]
    ceiling_label: Optional[str]
    rationale: str


class StatementOfAffairsDetails(TypedDict, total=False):
    """EY/KPMG-format M&A cover doc (Section 0)."""

    waterfall_orderly: List[WaterfallStepDetails]
    waterfall_forced: List[WaterfallStepDetails]
    headline_net_orderly: float
    headline_net_forced: float
    headline_book_equity: float
    band: MAndABandDetails
    sources: List[str]
    rationale: str


class AuditTrailDetails(TypedDict, total=False):
    """Tamper-evident metadata for a digitalised M&A artifact."""

    run_id: str
    effective_date: str
    computed_at: str
    engine_version: str
    engine_version_notes: str
    payload_hash: str
    payload_hash_algorithm: str
    sources: List[str]


class TierVerdictDetails(TypedDict, total=False):
    """One row in the Sufficiency Memo (Phase 5)."""

    code: str
    label: str
    statutory_anchor: str
    claim_amount: float
    recovery_amount: float
    shortfall: float
    coverage_pct: float
    verdict: str  # "paid_in_full" | "partial" | "uncovered"
    rationale: str


class SufficiencyMemoDetails(TypedDict, total=False):
    """Per-scenario Sufficiency Memo — lawyer's first question."""

    scenario: str
    jurisdiction: str
    verdicts: List[TierVerdictDetails]
    deepest_tier_paid_in_full: Optional[str]
    deepest_tier_label: Optional[str]
    headline_coverage_ratio: float
    estate_exhausted_at_tier: Optional[str]
    rationale: str
    sources: List[str]


class CreditorLetterDetails(TypedDict, total=False):
    """One auto-drafted creditor notification letter (Phase 5)."""

    tier_code: str
    tier_label: str
    statutory_anchor: str
    urgency: str  # "urgent" | "standard" | "hardship"
    subject_line: str
    salutation_placeholder: str
    body_paragraphs: List[str]
    closing: str
    signatory_placeholder: str
    expected_dividend_pct: float
    expected_dividend_amount: float
    claim_amount: float
    rationale: str


class CreditorLetterPackDetails(TypedDict, total=False):
    """Per-scenario auto-drafted creditor letter pack."""

    scenario: str
    jurisdiction: str
    letters: List[CreditorLetterDetails]
    cover_note: str
    sources: List[str]


class BuyerScenarioDetails(TypedDict, total=False):
    """One canonical M&A buyer scenario (Phase 5)."""

    profile: str  # "financial" | "strategic" | "mbo"
    label_nl: str
    label_en: str
    bid_floor: float
    bid_anchor: float
    bid_ceiling: float
    floor_multiplier_of_lv: float
    ceiling_multiplier_of_lv: float
    rationale_nl: str
    rationale_en: str


class StrategicBuyerScenariosDetails(TypedDict, total=False):
    """Three-buyer pack — financial / strategic / MBO bid bands."""

    scenarios: List[BuyerScenarioDetails]
    base_lv_net: float
    base_going_concern: Optional[float]
    base_replacement_cost: Optional[float]
    rationale: str
    sources: List[str]


class LiquidationAnalysisDetails(TypedDict, total=False):
    orderly: LiquidationScenarioDetails
    forced: LiquidationScenarioDetails
    book_equity: float
    ownership_multiplier: float
    sources: List[str]
    scope_note: str
    # Phase 1 — Big-4 academic depth
    premise: PremiseDetails
    distress: DistressDetails
    asset_schedule: AssetScheduleDetails
    expected_value_status: str
    going_concern_comparison_status: str
    expected_equity_value: Optional[float]
    going_concern_proxy_equity: float
    # Phase 2 — EY-grade insolvency cascade + tax + wind-down
    priority_cascade_orderly: PriorityCascadeDetails
    priority_cascade_forced: PriorityCascadeDetails
    tax_leakage_orderly: TaxLeakageDetails
    tax_leakage_forced: TaxLeakageDetails
    wind_down_orderly: WindDownDetails
    wind_down_forced: WindDownDetails
    # Phase 3 — PV + sensitivity + premise reconciliation
    disposal_schedule_pv_orderly: DisposalSchedulePVDetails
    disposal_schedule_pv_forced: DisposalSchedulePVDetails
    sensitivity: SensitivityDetails
    premise_reconciliation: PremiseReconciliationDetails
    # Phase 4 — IVS / USPAP / IFRS 13 disclosure
    disclosure: DisclosureDetails
    # Net-to-shareholder headlines (post cascade + tax + wind-down)
    net_equity_to_shareholders_orderly: float
    net_equity_to_shareholders_forced: float
    # Phase 4+ — M&A buyer ceiling, EY-format Section 0, audit trail
    replacement_cost: ReplacementCostDetails
    statement_of_affairs: StatementOfAffairsDetails
    audit_trail: AuditTrailDetails
    # Phase 5 — Lawyer / accountant grade reductions
    sufficiency_memo_orderly: SufficiencyMemoDetails
    sufficiency_memo_forced: SufficiencyMemoDetails
    creditor_letters_orderly: CreditorLetterPackDetails
    creditor_letters_forced: CreditorLetterPackDetails
    strategic_buyer_scenarios: StrategicBuyerScenariosDetails


def build_liquidation_analysis_details(*, scenarios: Any) -> LiquidationAnalysisDetails:
    """Build the typed details payload from a ``LiquidationScenarios`` object.

    ``scenarios`` is typed ``Any`` here to keep this schema module free
    of a downstream import on ``src.domain.liquidation`` (which would
    create a layering cycle: domain → schemas → domain). The dataclass
    has a ``to_details_dict()`` that produces a structurally identical
    dict, so we just delegate.
    """
    return scenarios.to_details_dict()
