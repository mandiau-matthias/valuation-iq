"""Authoritative, additive company knowledge-curve publication contract.

``C0`` through ``C8`` are maturity *levels*, not processing stages.  The level
is a deterministic projection of the private T0--T5 graph and, for a public
projection, its T2/T3 valuation grade.  Financial fact categories are a
separate taxonomy used only to prove curve quality.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SHA256_PATTERN = r"^[0-9a-f]{64}$"
COUNTRY_PATTERN = r"^[A-Z]{2}$"
COMPANY_KNOWLEDGE_CURVE_RULESET_VERSION = "company-knowledge-curve/v1"


class _FrozenContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CompanyGraphTier(StrEnum):
    T0 = "T0"
    T1 = "T1"
    T2 = "T2"
    T3 = "T3"
    T4 = "T4"
    T5 = "T5"


class PublicProjectionTier(StrEnum):
    T2 = "T2"
    T3 = "T3"


class PublicValuationGrade(StrEnum):
    T2_E = "T2-E"
    T2_B = "T2-B"
    T2_M = "T2-M"
    T3_M = "T3-M"
    T3_O = "T3-O"


class KnowledgeCurveLevel(StrEnum):
    C0 = "C0"  # T0/T1: exclusion/quarantine or resolved identity graph
    C1 = "C1"  # T2-E: public source-bound evidence graph
    C2 = "C2"  # T2-B/T2-M: governed indicative value checkpoints
    C3 = "C3"  # T3-M: reproducible longitudinal modeled curve
    C4 = "C4"  # T3-O: governed observed-market curve
    C5 = "C5"  # T4-A: activated private workspace
    C6 = "C6"  # T4-Q: quantitatively normalized private workspace
    C7 = "C7"  # T4-C: contextualized living private dossier
    C8 = "C8"  # T5: transaction-ready private company


KNOWLEDGE_CURVE_LEVEL_ORDER = tuple(KnowledgeCurveLevel)
# Import compatibility for callers that imported the pre-correction symbol.
# Its semantics are now levels; new code must use KnowledgeCurveLevel.
KnowledgeCurveStage = KnowledgeCurveLevel
KNOWLEDGE_CURVE_STAGE_ORDER = KNOWLEDGE_CURVE_LEVEL_ORDER


class KnowledgeStageOutcome(StrEnum):
    PASSED = "passed"
    NOT_APPLICABLE = "not_applicable"
    BLOCKED = "blocked"


class MaterialFactCategory(StrEnum):
    PRIMARY_METHOD_DRIVER = "primary_method_driver"
    SECONDARY_INCOME_STATEMENT = "secondary_income_statement"
    NET_OR_OPERATING_RESULT = "net_or_operating_result"
    EQUITY = "equity"
    ASSETS_OR_LIABILITIES = "assets_or_liabilities"
    LIQUIDITY_LEVERAGE_OR_WORKING_CAPITAL = "liquidity_leverage_or_working_capital"


T3_M_REQUIRED_MATERIAL_FACT_CATEGORIES = frozenset(MaterialFactCategory)

_MATERIAL_CATEGORY_FACT_NAMES: dict[MaterialFactCategory, frozenset[str]] = {
    MaterialFactCategory.PRIMARY_METHOD_DRIVER: frozenset(
        {
            "ebitda",
            "reported_ebitda",
            "ebit",
            "operating_profit",
            "depreciation_amortization",
            "net_income",
            "revenue",
        }
    ),
    MaterialFactCategory.SECONDARY_INCOME_STATEMENT: frozenset(
        {
            "revenue",
            "gross_margin",
            "cost_of_sales",
            "operating_expenses",
            "depreciation_amortization",
        }
    ),
    MaterialFactCategory.NET_OR_OPERATING_RESULT: frozenset(
        {"ebit", "operating_profit", "net_income", "profit_before_tax"}
    ),
    MaterialFactCategory.EQUITY: frozenset({"book_equity", "equity", "net_assets"}),
    MaterialFactCategory.ASSETS_OR_LIABILITIES: frozenset(
        {
            "total_assets",
            "total_liabilities",
            "fixed_assets",
            "current_assets",
            "current_liabilities",
        }
    ),
    MaterialFactCategory.LIQUIDITY_LEVERAGE_OR_WORKING_CAPITAL: frozenset(
        {
            "cash",
            "interest_bearing_debt",
            "lease_liabilities",
            "leases",
            "working_capital",
            "receivables",
            "inventories",
        }
    ),
}


class ValuationMethod(StrEnum):
    EV_EBITDA = "EV_EBITDA"
    EV_EBIT = "EV_EBIT"
    PE = "PE"
    EV_REVENUE = "EV_REVENUE"


class RevenueSource(StrEnum):
    TURNOVER = "TURNOVER"
    GROSS_MARGIN = "GROSS_MARGIN"
    UNKNOWN = "UNKNOWN"


class MultipleSourceKind(StrEnum):
    NONE = "NONE"
    MODELED_BROAD_PRIOR = "MODELED_BROAD_PRIOR"
    MODELED_PRIOR = "MODELED_PRIOR"
    OBSERVED_CLOSED_DEALS = "OBSERVED_CLOSED_DEALS"


class MappingStatus(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    UNAVAILABLE = "unavailable"
    REVIEWED = "reviewed"


class CurveStatus(StrEnum):
    ABSENT = "absent"
    AVAILABLE = "available"


class IndexDecision(StrEnum):
    EXCLUDE = "exclude"
    INDEX = "index"


class RolloutState(StrEnum):
    EXCLUDED = "excluded"
    SEALED_DARK = "sealed_dark"
    ACTIVE = "active"


class Visibility(StrEnum):
    PRIVATE = "private"
    PUBLIC = "public"


class Searchability(StrEnum):
    NOT_SEARCHABLE = "not_searchable"
    PLATFORM_SEARCHABLE = "platform_searchable"


class CurveTemporality(StrEnum):
    NONE = "NONE"
    CURRENT_MODEL_APPLIED_TO_HISTORICAL_OFFICIAL_FINANCIALS = (
        "CURRENT_MODEL_APPLIED_TO_HISTORICAL_OFFICIAL_FINANCIALS"
    )


class OutputBasis(StrEnum):
    NONE = "none"
    ENTERPRISE_VALUE = "enterprise_value"
    EQUITY_VALUE = "equity_value"


class ConfidenceLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class UncertaintyBandSemantics(StrEnum):
    NONE = "none"
    P10_P90 = "p10_p90"
    CONTRACT_DISTRIBUTION = "contract_distribution"


class CohortPolicy(StrEnum):
    PRESERVED_5M = "preserved_5m"
    FUTURE_CURVE_FIRST = "future_curve_first"


class PublicLocaleRouteV1(_FrozenContract):
    locale: Literal["en", "nl", "fr"]
    route: str = Field(pattern=r"^/(?:en|nl|fr)/companies/[a-z]{2}/[a-z0-9-]+$")

    @model_validator(mode="after")
    def validate_route_locale(self) -> "PublicLocaleRouteV1":
        if not self.route.startswith(f"/{self.locale}/"):
            raise ValueError("public route locale prefix disagrees with locale")
        return self


class MethodSegmentV1(_FrozenContract):
    segment_id: str = Field(pattern=r"^segment-[1-9][0-9]*$")
    period_keys: tuple[str, ...] = Field(min_length=2, max_length=20)
    methods: tuple[ValuationMethod, ...] = Field(min_length=1, max_length=4)
    output_basis: OutputBasis

    @field_validator("period_keys")
    @classmethod
    def validate_period_keys(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)) or any(not value for value in values):
            raise ValueError("method-segment period keys must be non-empty and unique")
        return values

    @field_validator("methods")
    @classmethod
    def validate_methods(cls, values: tuple[ValuationMethod, ...]) -> tuple[ValuationMethod, ...]:
        if tuple(sorted(set(values))) != values:
            raise ValueError("method-segment methods must be sorted and unique")
        return values

    @model_validator(mode="after")
    def validate_basis(self) -> "MethodSegmentV1":
        if self.output_basis == OutputBasis.NONE:
            raise ValueError("a method segment requires a monetary value basis")
        return self


class KnowledgeLevelEvidenceV1(_FrozenContract):
    level: KnowledgeCurveLevel
    outcome: KnowledgeStageOutcome
    evidence_sha256s: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()

    @field_validator("evidence_sha256s")
    @classmethod
    def validate_evidence_hashes(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("level evidence hashes must be unique")
        if any(
            len(value) != 64 or any(c not in "0123456789abcdef" for c in value) for value in values
        ):
            raise ValueError("level evidence hashes must be lowercase SHA-256 values")
        return values

    @field_validator("reason_codes")
    @classmethod
    def validate_reasons(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)) or any(not value.strip() for value in values):
            raise ValueError("level reason codes must be non-empty and unique")
        return values

    @model_validator(mode="after")
    def validate_outcome(self) -> "KnowledgeLevelEvidenceV1":
        if self.outcome == KnowledgeStageOutcome.PASSED and not self.evidence_sha256s:
            raise ValueError("a passed knowledge level requires sealed evidence")
        if self.outcome != KnowledgeStageOutcome.PASSED and not self.reason_codes:
            raise ValueError("a non-passing knowledge level requires a reason code")
        return self


# Compatibility alias. Serialized material uses ``level`` and
# ``level_evidence`` only, so the old pipeline-stage shape cannot be emitted.
KnowledgeStageEvidenceV1 = KnowledgeLevelEvidenceV1


class MaterialFactBindingV1(_FrozenContract):
    category: MaterialFactCategory
    fact_names: tuple[str, ...] = Field(min_length=1, max_length=16)
    fact_sha256s: tuple[str, ...] = Field(min_length=1, max_length=16)
    applies_to_methods: tuple[ValuationMethod, ...] = Field(min_length=1, max_length=4)
    revenue_source: RevenueSource | None = None

    @field_validator("fact_names")
    @classmethod
    def validate_fact_names(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if tuple(sorted(set(values))) != values:
            raise ValueError("fact_names must be sorted and unique")
        if any(not value or value.lower() != value for value in values):
            raise ValueError("fact_names must be non-empty lowercase tokens")
        return values

    @field_validator("fact_sha256s")
    @classmethod
    def validate_fact_hashes(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("fact hashes must be unique within a category")
        if any(
            len(value) != 64 or any(c not in "0123456789abcdef" for c in value) for value in values
        ):
            raise ValueError("fact hashes must be lowercase SHA-256 values")
        return values

    @field_validator("applies_to_methods")
    @classmethod
    def validate_methods(cls, values: tuple[ValuationMethod, ...]) -> tuple[ValuationMethod, ...]:
        if tuple(sorted(set(values))) != values:
            raise ValueError("applies_to_methods must be sorted and unique")
        return values

    @model_validator(mode="after")
    def validate_binding(self) -> "MaterialFactBindingV1":
        if len(self.fact_names) != len(self.fact_sha256s):
            raise ValueError("every bound fact name requires one fact hash")
        if not set(self.fact_names) <= _MATERIAL_CATEGORY_FACT_NAMES[self.category]:
            raise ValueError("fact name is incompatible with its material fact category")
        return self


_PRIMARY_DRIVER_FACTS: dict[ValuationMethod, tuple[frozenset[str], ...]] = {
    ValuationMethod.EV_EBITDA: (
        frozenset({"ebitda"}),
        frozenset({"reported_ebitda"}),
        frozenset({"depreciation_amortization", "ebit"}),
    ),
    ValuationMethod.EV_EBIT: (
        frozenset({"ebit"}),
        frozenset({"operating_profit"}),
    ),
    ValuationMethod.PE: (frozenset({"net_income"}),),
    ValuationMethod.EV_REVENUE: (frozenset({"revenue"}),),
}


class PeriodMaterialFactCoverageV1(_FrozenContract):
    period_key: str = Field(min_length=1, max_length=512)
    official_period_sha256: str = Field(pattern=SHA256_PATTERN)
    source_document_sha256: str = Field(pattern=SHA256_PATTERN)
    segment_id: str = Field(pattern=r"^segment-[1-9][0-9]*$")
    methods: tuple[ValuationMethod, ...] = Field(min_length=1, max_length=4)
    bindings: tuple[MaterialFactBindingV1, ...] = Field(min_length=1, max_length=6)

    @field_validator("methods")
    @classmethod
    def validate_methods(cls, values: tuple[ValuationMethod, ...]) -> tuple[ValuationMethod, ...]:
        if tuple(sorted(set(values))) != values:
            raise ValueError("period methods must be sorted and unique")
        return values

    @model_validator(mode="after")
    def validate_coverage(self) -> "PeriodMaterialFactCoverageV1":
        categories = [binding.category for binding in self.bindings]
        if len(categories) != len(set(categories)):
            raise ValueError("a material category can count only once per period")
        used_hashes: set[str] = set()
        for binding in self.bindings:
            if not set(binding.applies_to_methods) <= set(self.methods):
                raise ValueError("binding methods must be a subset of the resolved method set")
            if used_hashes.intersection(binding.fact_sha256s):
                raise ValueError("one official fact cannot count in two material categories")
            used_hashes.update(binding.fact_sha256s)

        primary = next(
            (
                binding
                for binding in self.bindings
                if binding.category == MaterialFactCategory.PRIMARY_METHOD_DRIVER
            ),
            None,
        )
        if primary is None or set(primary.applies_to_methods) != set(self.methods):
            raise ValueError("the primary method driver must support every resolved method")
        names = frozenset(primary.fact_names)
        for method in self.methods:
            if not any(required <= names for required in _PRIMARY_DRIVER_FACTS[method]):
                raise ValueError(f"primary method evidence does not support {method.value}")
            if (
                method == ValuationMethod.EV_REVENUE
                and primary.revenue_source != RevenueSource.TURNOVER
            ):
                raise ValueError("EV_REVENUE requires genuine turnover, never gross margin")
        return self

    @property
    def material_fact_categories(self) -> frozenset[MaterialFactCategory]:
        return frozenset(binding.category for binding in self.bindings)


class CompanyKnowledgeCurveV1(_FrozenContract):
    schema_version: Literal["CompanyKnowledgeCurveV1"] = "CompanyKnowledgeCurveV1"
    ruleset_version: Literal["company-knowledge-curve/v1"] = COMPANY_KNOWLEDGE_CURVE_RULESET_VERSION
    company_key: str = Field(min_length=1, max_length=240)
    country_code: str = Field(pattern=COUNTRY_PATTERN)
    cohort_policy: CohortPolicy | None = None
    visibility: Visibility
    searchability: Searchability
    business_type_id: str | None = Field(default=None, min_length=1, max_length=160)
    nace_code: str | None = Field(default=None, min_length=1, max_length=32)
    graph_tier: CompanyGraphTier
    public_projection_tier: PublicProjectionTier | None = None
    valuation_grade: PublicValuationGrade | None = None
    knowledge_curve_level: KnowledgeCurveLevel
    level_evidence: KnowledgeLevelEvidenceV1
    curve_status: CurveStatus
    curve_temporality: CurveTemporality
    monetary_graph_allowed: bool
    mapping_status: MappingStatus
    mapping_version: str | None = Field(default=None, min_length=1, max_length=160)
    multiple_source_kind: MultipleSourceKind
    multiple_scope: str | None = Field(default=None, min_length=1, max_length=240)
    multiple_manifest_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    prior_weight: Decimal = Field(ge=0, le=1)
    uncertainty_band_semantics: UncertaintyBandSemantics
    output_basis: OutputBasis
    method_set: tuple[ValuationMethod, ...] = Field(default=(), max_length=4)
    method_segments: tuple[MethodSegmentV1, ...] = Field(default=(), max_length=10)
    method_change_segmented_and_disclosed: bool
    official_period_count: int = Field(ge=0, le=20)
    resolved_checkpoint_count: int = Field(ge=0, le=20)
    period_material_fact_coverage: tuple[PeriodMaterialFactCoverageV1, ...] = Field(
        default=(), max_length=20
    )
    observed_sample_size: int | None = Field(default=None, ge=10)
    observed_population_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    observed_metric: ValuationMethod | None = None
    observed_country_code: str | None = Field(default=None, pattern=COUNTRY_PATTERN)
    observed_business_type_id: str | None = Field(default=None, min_length=1, max_length=160)
    observed_benchmark_contract_sha256: str | None = Field(
        default=None, pattern=SHA256_PATTERN
    )
    observed_deal_sha256s: tuple[str, ...] = Field(default=(), max_length=10_000)
    observed_licence_id: str | None = Field(default=None, min_length=1, max_length=200)
    observed_licence_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    observed_licence_permits_public_derived_outputs: bool | None = None
    observed_window_start: date | None = None
    observed_window_end: date | None = None
    latest_filing_fresh: bool
    input_confidence: ConfidenceLevel
    model_confidence: ConfidenceLevel
    blocking_contradiction: bool
    rendered_source_bound_fact_count: int = Field(ge=0)
    material_official_module_count: int = Field(ge=0)
    material_official_record_count: int = Field(ge=0)
    material_official_public_url_count: int = Field(ge=0)
    unique_long_form_content: bool
    evidence_manifest_sha256: str = Field(pattern=SHA256_PATTERN)
    source_lineage_sha256: str = Field(pattern=SHA256_PATTERN)
    final_material_sha256: str = Field(pattern=SHA256_PATTERN)
    grade_artifact_sha256: str = Field(pattern=SHA256_PATTERN)
    reason_codes: tuple[str, ...] = Field(min_length=1, max_length=32)
    public_routes: tuple[PublicLocaleRouteV1, ...] = Field(default=(), max_length=3)
    index_decision: IndexDecision
    rollout_state: RolloutState

    @field_validator("business_type_id", "observed_business_type_id")
    @classmethod
    def validate_business_type_id(cls, value: str | None) -> str | None:
        if value is not None and value.strip() != value:
            raise ValueError("business type identifiers must be trimmed")
        return value

    @field_validator("method_set")
    @classmethod
    def validate_root_methods(cls, values: tuple[ValuationMethod, ...]) -> tuple[ValuationMethod, ...]:
        if tuple(sorted(set(values))) != values:
            raise ValueError("root method_set must be sorted and unique")
        return values

    @field_validator("reason_codes")
    @classmethod
    def validate_reason_codes(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if tuple(sorted(set(values))) != values or any(not value.strip() for value in values):
            raise ValueError("reason codes must be sorted, unique and non-empty")
        return values

    @field_validator("public_routes")
    @classmethod
    def validate_public_routes(cls, values: tuple[PublicLocaleRouteV1, ...]) -> tuple[PublicLocaleRouteV1, ...]:
        locales = tuple(item.locale for item in values)
        routes = tuple(item.route for item in values)
        if len(locales) != len(set(locales)) or len(routes) != len(set(routes)):
            raise ValueError("public locale routes must be unique")
        return values

    @field_validator("observed_deal_sha256s")
    @classmethod
    def validate_observed_deal_hashes(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if tuple(sorted(set(values))) != values or any(
            len(value) != 64 or any(c not in "0123456789abcdef" for c in value)
            for value in values
        ):
            raise ValueError("observed deal hashes must be sorted unique SHA-256 values")
        return values

    @model_validator(mode="after")
    def validate_contract(self) -> "CompanyKnowledgeCurveV1":
        if self.level_evidence.level != self.knowledge_curve_level:
            raise ValueError("level evidence must bind the current knowledge-curve level")

        if self.mapping_status == MappingStatus.REVIEWED:
            if self.business_type_id is None or self.mapping_version is None or self.nace_code is None:
                raise ValueError(
                    "reviewed mapping requires NACE, business type and mapping version"
                )
        elif any((self.business_type_id, self.mapping_version)):
            raise ValueError("unreviewed mapping cannot name a business type or mapping version")

        if self.multiple_source_kind == MultipleSourceKind.NONE:
            if self.multiple_scope is not None or self.multiple_manifest_sha256 is not None:
                raise ValueError("NONE multiple source cannot carry a multiple contract")
        elif self.multiple_scope is None or self.multiple_manifest_sha256 is None:
            raise ValueError("a monetary multiple requires scope and a frozen manifest")

        if self.resolved_checkpoint_count > self.official_period_count:
            raise ValueError("resolved checkpoints cannot exceed official periods")
        if self.valuation_grade == PublicValuationGrade.T3_M and (
            self.official_period_count < 3 or self.resolved_checkpoint_count < 3
        ):
            raise ValueError("T3-M requires at least three official checkpoints")
        if self.valuation_grade in {
            PublicValuationGrade.T2_B,
            PublicValuationGrade.T2_M,
        } and (self.official_period_count < 2 or self.resolved_checkpoint_count < 2):
            raise ValueError("curve-backed grades require at least two official checkpoints")
        if len(self.period_material_fact_coverage) != self.resolved_checkpoint_count:
            raise ValueError("every resolved checkpoint requires one period coverage record")
        period_keys = [value.period_key for value in self.period_material_fact_coverage]
        if len(period_keys) != len(set(period_keys)):
            raise ValueError("period coverage keys must be unique")
        period_hashes = [
            value.official_period_sha256 for value in self.period_material_fact_coverage
        ]
        if len(period_hashes) != len(set(period_hashes)):
            raise ValueError("resolved checkpoints must bind distinct official periods")
        coverage_methods = tuple(
            sorted({method for coverage in self.period_material_fact_coverage for method in coverage.methods})
        )
        if len(coverage_methods) > 1 and len(self.method_segments) < 2:
            raise ValueError("method segment disclosure is required when methods change")
        if coverage_methods != self.method_set:
            raise ValueError("root method_set must equal the methods resolved by every checkpoint")

        segment_keys = [key for segment in self.method_segments for key in segment.period_keys]
        coverage_keys = [coverage.period_key for coverage in self.period_material_fact_coverage]
        if sorted(segment_keys) != sorted(coverage_keys) or len(segment_keys) != len(set(segment_keys)):
            raise ValueError("method segments must cover every resolved checkpoint exactly once")
        segment_by_id = {segment.segment_id: segment for segment in self.method_segments}
        if len(segment_by_id) != len(self.method_segments):
            raise ValueError("method segment IDs must be unique")
        for coverage in self.period_material_fact_coverage:
            segment = segment_by_id.get(coverage.segment_id)
            if (
                segment is None
                or coverage.period_key not in segment.period_keys
                or coverage.methods != segment.methods
                or segment.output_basis != self.output_basis
            ):
                raise ValueError("checkpoint coverage disagrees with its method segment")
        if len(self.method_segments) > 1:
            if not self.method_change_segmented_and_disclosed:
                raise ValueError("method changes must be explicitly segmented and disclosed")
        elif self.method_change_segmented_and_disclosed:
            raise ValueError("a single method segment cannot claim a disclosed method change")

        expected_level_by_grade = {
            PublicValuationGrade.T2_E: KnowledgeCurveLevel.C1,
            PublicValuationGrade.T2_B: KnowledgeCurveLevel.C2,
            PublicValuationGrade.T2_M: KnowledgeCurveLevel.C2,
            PublicValuationGrade.T3_M: KnowledgeCurveLevel.C3,
            PublicValuationGrade.T3_O: KnowledgeCurveLevel.C4,
        }
        if self.graph_tier in {CompanyGraphTier.T0, CompanyGraphTier.T1}:
            if self.knowledge_curve_level != KnowledgeCurveLevel.C0:
                raise ValueError("T0/T1 must use knowledge-curve level C0")
        elif self.graph_tier == CompanyGraphTier.T4:
            if self.knowledge_curve_level not in {
                KnowledgeCurveLevel.C5,
                KnowledgeCurveLevel.C6,
                KnowledgeCurveLevel.C7,
            }:
                raise ValueError("T4 must use C5, C6, or C7")
        elif self.graph_tier == CompanyGraphTier.T5:
            if self.knowledge_curve_level != KnowledgeCurveLevel.C8:
                raise ValueError("T5 must use knowledge-curve level C8")

        if self.valuation_grade is None:
            if self.cohort_policy is not None or self.public_routes:
                raise ValueError("private graph material cannot carry publication policy or routes")
            if self.public_projection_tier is not None:
                raise ValueError("a non-public graph cannot have a public projection tier")
            if self.curve_status != CurveStatus.ABSENT or self.monetary_graph_allowed:
                raise ValueError("a non-public projection cannot expose monetary curve material")
            if (
                self.index_decision != IndexDecision.EXCLUDE
                or self.rollout_state != RolloutState.EXCLUDED
            ):
                raise ValueError("only public T2/T3 projections can enter rollout")
            if self.graph_tier in {CompanyGraphTier.T2, CompanyGraphTier.T3}:
                raise ValueError("T2/T3 graph tiers require a public valuation grade")
            if self.visibility != Visibility.PRIVATE or self.index_decision != IndexDecision.EXCLUDE:
                raise ValueError("T0/T1/T4/T5 graph material is private and excluded")
            expected_searchability = (
                Searchability.NOT_SEARCHABLE
                if self.graph_tier == CompanyGraphTier.T0
                else Searchability.PLATFORM_SEARCHABLE
            )
            if self.searchability != expected_searchability:
                raise ValueError("private graph searchability disagrees with its tier")
            if self.graph_tier != CompanyGraphTier.T0 and (
                self.level_evidence.outcome != KnowledgeStageOutcome.PASSED
            ):
                raise ValueError("resolved private maturity requires passing level evidence")
            return self

        if self.level_evidence.outcome != KnowledgeStageOutcome.PASSED:
            raise ValueError("a public projection requires passing current-level evidence")
        if self.cohort_policy is None:
            raise ValueError("a public projection requires an explicit acquisition policy")
        if self.visibility != Visibility.PUBLIC or self.searchability != Searchability.PLATFORM_SEARCHABLE:
            raise ValueError("public T2/T3 projections must be public and platform-searchable")
        if self.index_decision != IndexDecision.INDEX:
            raise ValueError("every retained T2/T3 projection is indexable")
        if self.rollout_state not in {RolloutState.SEALED_DARK, RolloutState.ACTIVE}:
            raise ValueError("a public projection must be sealed dark or active")
        if self.mapping_status == MappingStatus.NOT_APPLICABLE:
            raise ValueError("a public projection must resolve mapping as reviewed or unavailable")
        if {route.locale for route in self.public_routes} != {"en", "nl", "fr"}:
            raise ValueError("every public v10 company requires exact EN/NL/FR routes")
        if self.blocking_contradiction:
            raise ValueError("a public projection cannot contain a blocking contradiction")
        if (
            self.rendered_source_bound_fact_count < 6
            or self.material_official_module_count < 2
            or self.material_official_record_count < 2
            or self.material_official_public_url_count < 2
            or not self.unique_long_form_content
        ):
            raise ValueError("a public projection fails the T2-E long-form evidence floor")
        if (
            self.cohort_policy == CohortPolicy.FUTURE_CURVE_FIRST
            and self.valuation_grade == PublicValuationGrade.T2_E
        ):
            raise ValueError("future curve-first cohorts cannot retain a failed curve as T2-E")

        is_t3 = self.valuation_grade in {PublicValuationGrade.T3_M, PublicValuationGrade.T3_O}
        expected_projection = PublicProjectionTier.T3 if is_t3 else PublicProjectionTier.T2
        if self.public_projection_tier != expected_projection:
            raise ValueError("public projection tier and valuation grade disagree")
        allowed_graph_tiers = (
            {CompanyGraphTier.T3, CompanyGraphTier.T4, CompanyGraphTier.T5}
            if is_t3
            else {CompanyGraphTier.T2, CompanyGraphTier.T4, CompanyGraphTier.T5}
        )
        if self.graph_tier not in allowed_graph_tiers:
            raise ValueError("private graph tier cannot support the requested public projection")
        if self.graph_tier in {CompanyGraphTier.T2, CompanyGraphTier.T3} and (
            self.knowledge_curve_level != expected_level_by_grade[self.valuation_grade]
        ):
            raise ValueError("public graph tier, grade and knowledge-curve level disagree")

        if self.valuation_grade == PublicValuationGrade.T2_E:
            if self.curve_status != CurveStatus.ABSENT or self.monetary_graph_allowed:
                raise ValueError("T2-E cannot expose a monetary graph")
            if self.resolved_checkpoint_count != 0 or self.period_material_fact_coverage:
                raise ValueError("T2-E cannot carry resolved monetary checkpoints")
            if self.multiple_source_kind != MultipleSourceKind.NONE or self.prior_weight != 0:
                raise ValueError("T2-E cannot carry a multiple or prior")
            if any(
                (
                    self.curve_temporality != CurveTemporality.NONE,
                    self.output_basis != OutputBasis.NONE,
                    self.uncertainty_band_semantics != UncertaintyBandSemantics.NONE,
                    bool(self.method_set),
                    bool(self.method_segments),
                    self.method_change_segmented_and_disclosed,
                )
            ):
                raise ValueError("T2-E cannot carry monetary method, basis or band material")
        else:
            if self.curve_status != CurveStatus.AVAILABLE or not self.monetary_graph_allowed:
                raise ValueError("curve-backed T2/T3 grades require an available monetary graph")
            if self.official_period_count < 2 or self.resolved_checkpoint_count < 2:
                raise ValueError(
                    "curve-backed T2/T3 grades require at least two official checkpoints"
                )
            if (
                self.curve_temporality
                != CurveTemporality.CURRENT_MODEL_APPLIED_TO_HISTORICAL_OFFICIAL_FINANCIALS
                or self.output_basis == OutputBasis.NONE
                or not self.method_set
                or not self.method_segments
            ):
                raise ValueError("curve-backed grades require temporality, basis and method proof")

        if self.valuation_grade == PublicValuationGrade.T2_B:
            if self.mapping_status != MappingStatus.UNAVAILABLE:
                raise ValueError("T2-B requires the governed unmapped fallback")
            if (
                self.multiple_source_kind != MultipleSourceKind.MODELED_BROAD_PRIOR
                or self.prior_weight <= 0
            ):
                raise ValueError("T2-B requires a positive-weight broad modeled prior")
            if self.uncertainty_band_semantics != UncertaintyBandSemantics.P10_P90:
                raise ValueError("T2-B public low/high must be governed broad p10-p90")
        elif self.valuation_grade in {PublicValuationGrade.T2_M, PublicValuationGrade.T3_M}:
            if self.mapping_status != MappingStatus.REVIEWED:
                raise ValueError("T2-M/T3-M require reviewed NACE/business-type mapping")
            if (
                self.multiple_source_kind != MultipleSourceKind.MODELED_PRIOR
                or self.prior_weight <= 0
            ):
                raise ValueError("T2-M/T3-M require a positive-weight modeled prior")
            if self.uncertainty_band_semantics != UncertaintyBandSemantics.CONTRACT_DISTRIBUTION:
                raise ValueError("mapped modeled grades require contract-bound band semantics")

        if self.valuation_grade == PublicValuationGrade.T3_M:
            if self.official_period_count < 3 or self.resolved_checkpoint_count < 3:
                raise ValueError("T3-M requires at least three official resolved checkpoints")
            for coverage in self.period_material_fact_coverage:
                if coverage.material_fact_categories != T3_M_REQUIRED_MATERIAL_FACT_CATEGORIES:
                    raise ValueError(
                        "T3-M requires all six method-relative material categories per period"
                    )
            if (
                not self.latest_filing_fresh
                or self.input_confidence != ConfidenceLevel.HIGH
                or self.model_confidence != ConfidenceLevel.HIGH
            ):
                raise ValueError(
                    "T3-M requires a fresh filing and high input/model confidence"
                )

        if self.valuation_grade == PublicValuationGrade.T3_O:
            if self.mapping_status != MappingStatus.REVIEWED:
                raise ValueError("T3-O requires reviewed exact business-type mapping")
            if self.multiple_source_kind != MultipleSourceKind.OBSERVED_CLOSED_DEALS:
                raise ValueError("T3-O requires observed closed-deal evidence")
            if self.prior_weight != 0:
                raise ValueError("T3-O requires prior_weight=0")
            if self.uncertainty_band_semantics != UncertaintyBandSemantics.CONTRACT_DISTRIBUTION:
                raise ValueError("T3-O requires observed-contract band semantics")
            if (
                self.observed_sample_size is None
                or self.observed_sample_size < 10
                or self.observed_population_sha256 is None
                or self.observed_metric is None
                or self.observed_country_code != self.country_code
                or self.observed_business_type_id != self.business_type_id
                or self.observed_benchmark_contract_sha256 is None
                or len(self.observed_deal_sha256s) != self.observed_sample_size
                or self.observed_licence_id is None
                or self.observed_licence_sha256 is None
                or self.observed_licence_permits_public_derived_outputs is not True
                or self.observed_window_start is None
                or self.observed_window_end is None
                or self.observed_window_start > self.observed_window_end
                or any(
                    set(coverage.methods) != {self.observed_metric}
                    for coverage in self.period_material_fact_coverage
                )
            ):
                raise ValueError(
                    "T3-O requires an exact-country, exact-business-type, metric-specific "
                    "observed population of at least ten deals"
                )
        elif any(
            (
                self.observed_sample_size is not None,
                self.observed_population_sha256 is not None,
                self.observed_metric is not None,
                self.observed_country_code is not None,
                self.observed_business_type_id is not None,
                self.observed_benchmark_contract_sha256 is not None,
                bool(self.observed_deal_sha256s),
                self.observed_licence_id is not None,
                self.observed_licence_sha256 is not None,
                self.observed_licence_permits_public_derived_outputs is not None,
                self.observed_window_start is not None,
                self.observed_window_end is not None,
            )
        ):
            raise ValueError("observed benchmark proof belongs only to T3-O")

        return self
