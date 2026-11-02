"""Frozen input contracts for deterministic public valuation curves.

The models are intentionally strict and immutable.  They turn the governance
requirements of Workstream D v9 into data that can be validated before the
calculation fleet starts.  Live Delphi/Athena data is read once upstream and
materialised as one of the three multiple contracts below; this package never
performs a per-company lookup.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SHA256_PATTERN = r"^[0-9a-f]{64}$"
COUNTRY_PATTERN = r"^[A-Z]{2}$"
CURRENCY_PATTERN = r"^[A-Z]{3}$"
MAX_CAMPAIGN_JOBS = 10_000
MAX_DURABLE_RESULTS_PER_PAGE = 250
MAX_PUBLIC_CURVE_PERIODS = 20


class _FrozenContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MultipleMetric(StrEnum):
    EV_EBITDA = "EV_EBITDA"
    EV_EBIT = "EV_EBIT"
    PE = "PE"
    EV_REVENUE = "EV_REVENUE"


class MultipleSourceKind(StrEnum):
    MODELED_PRIOR = "MODELED_PRIOR"
    MODELED_BROAD_PRIOR = "MODELED_BROAD_PRIOR"
    OBSERVED_MARKET = "OBSERVED_MARKET"


class ValueBasis(StrEnum):
    ENTERPRISE_VALUE = "ENTERPRISE_VALUE"
    EQUITY_VALUE = "EQUITY_VALUE"


class ValuationGrade(StrEnum):
    T2_B = "T2-B"
    T2_M = "T2-M"
    T3_M = "T3-M"
    T3_O = "T3-O"


class MappingStatus(StrEnum):
    REVIEWED = "REVIEWED"
    UNAVAILABLE = "UNAVAILABLE"


class ConfidenceLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class StatementScope(StrEnum):
    COMPANY = "COMPANY"
    CONSOLIDATED = "CONSOLIDATED"


class RevenueSourceKind(StrEnum):
    TURNOVER = "TURNOVER"
    GROSS_MARGIN = "GROSS_MARGIN"
    UNKNOWN = "UNKNOWN"


class GeographyScope(StrEnum):
    GLOBAL = "GLOBAL"
    REGIONAL = "REGIONAL"
    COUNTRY = "COUNTRY"


class MultipleBandV1(_FrozenContract):
    low: Decimal = Field(gt=0)
    median: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)

    @model_validator(mode="after")
    def validate_order(self) -> "MultipleBandV1":
        if not self.low <= self.median <= self.high:
            raise ValueError("multiple band must satisfy low <= median <= high")
        if self.low == self.high:
            raise ValueError("multiple band must have non-zero dispersion")
        return self


class GovernedModelCellV1(_FrozenContract):
    cell_id: str = Field(min_length=1, max_length=160)
    metric: MultipleMetric
    geography_scope: Literal[GeographyScope.GLOBAL, GeographyScope.REGIONAL]
    geography_code: str = Field(min_length=1, max_length=32)
    business_type_id: str = Field(min_length=1, max_length=160)
    active: Literal[True] = True
    median: Decimal = Field(gt=0)
    source_sha256: str = Field(pattern=SHA256_PATTERN)


class _MultipleContractBase(_FrozenContract):
    contract_id: str = Field(min_length=1, max_length=200)
    effective_date: date
    frozen_at: datetime
    metric: MultipleMetric
    multiple_manifest_sha256: str = Field(pattern=SHA256_PATTERN)
    methodology_version: str = Field(min_length=1, max_length=160)
    vintage: str = Field(min_length=1, max_length=160)
    source_hashes: tuple[str, ...] = Field(min_length=1)
    confidence: Decimal = Field(gt=0, le=1)

    @field_validator("frozen_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("frozen_at must be timezone-aware")
        return value

    @field_validator("source_hashes")
    @classmethod
    def validate_source_hashes(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("source_hashes must be unique")
        for value in values:
            if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
                raise ValueError("source_hashes must contain lowercase SHA-256 digests")
        return values


class ModelPriorContractV1(_MultipleContractBase):
    contract_version: Literal["ModelPriorContractV1"] = "ModelPriorContractV1"
    source_kind: Literal[MultipleSourceKind.MODELED_PRIOR] = MultipleSourceKind.MODELED_PRIOR
    geography_scope: Literal[GeographyScope.GLOBAL, GeographyScope.REGIONAL]
    geography_code: str = Field(min_length=1, max_length=32)
    business_type_id: str = Field(min_length=1, max_length=160)
    mapping_version: str = Field(min_length=1, max_length=160)
    band: MultipleBandV1
    prior_weight: Decimal = Field(default=Decimal("1"), ge=1, le=1)


class BroadMedianPriorContractV1(_MultipleContractBase):
    contract_version: Literal["BroadMedianPriorContractV1"] = "BroadMedianPriorContractV1"
    source_kind: Literal[MultipleSourceKind.MODELED_BROAD_PRIOR] = (
        MultipleSourceKind.MODELED_BROAD_PRIOR
    )
    geography_scope: Literal[GeographyScope.GLOBAL, GeographyScope.REGIONAL]
    geography_code: str = Field(min_length=1, max_length=32)
    cells: tuple[GovernedModelCellV1, ...] = Field(min_length=30)
    p10: Decimal = Field(gt=0)
    median: Decimal = Field(gt=0)
    p90: Decimal = Field(gt=0)
    prior_weight: Decimal = Field(default=Decimal("1"), ge=1, le=1)

    @model_validator(mode="after")
    def validate_broad_population(self) -> "BroadMedianPriorContractV1":
        if not self.p10 <= self.median <= self.p90 or self.p10 == self.p90:
            raise ValueError("broad prior must satisfy p10 <= median <= p90 with dispersion")
        cell_ids = [cell.cell_id for cell in self.cells]
        if len(cell_ids) != len(set(cell_ids)):
            raise ValueError("broad-prior cell IDs must be unique")
        for cell in self.cells:
            if cell.metric != self.metric:
                raise ValueError("every broad-prior cell must use the contract metric")
            if cell.geography_scope != self.geography_scope:
                raise ValueError("every broad-prior cell must use the disclosed geography scope")
            if cell.geography_code != self.geography_code:
                raise ValueError("every broad-prior cell must use the disclosed geography code")
        return self

    @property
    def band(self) -> MultipleBandV1:
        return MultipleBandV1(low=self.p10, median=self.median, high=self.p90)


class ClosedDealObservationV1(_FrozenContract):
    observation_id: str = Field(min_length=1, max_length=200)
    evidence_kind: Literal["CLOSED_DEAL"] = "CLOSED_DEAL"
    country_code: str = Field(pattern=COUNTRY_PATTERN)
    business_type_id: str = Field(min_length=1, max_length=160)
    metric: MultipleMetric
    value_basis: ValueBasis
    closed_at: date
    multiple: Decimal = Field(gt=0)
    observation_sha256: str = Field(pattern=SHA256_PATTERN)


class BenchmarkContractV2(_MultipleContractBase):
    contract_version: Literal["BenchmarkContractV2"] = "BenchmarkContractV2"
    source_kind: Literal[MultipleSourceKind.OBSERVED_MARKET] = MultipleSourceKind.OBSERVED_MARKET
    country_code: str = Field(pattern=COUNTRY_PATTERN)
    business_type_id: str = Field(min_length=1, max_length=160)
    mapping_version: str = Field(min_length=1, max_length=160)
    currency: str = Field(pattern=CURRENCY_PATTERN)
    value_basis: ValueBasis
    observation_window_start: date
    observation_window_end: date
    estimator: str = Field(min_length=1, max_length=200)
    outlier_policy: str = Field(min_length=1, max_length=500)
    licence_id: str = Field(min_length=1, max_length=200)
    licence_permits_public_derived_outputs: Literal[True]
    observations: tuple[ClosedDealObservationV1, ...] = Field(min_length=10)
    band: MultipleBandV1
    prior_weight: Decimal = Field(default=Decimal("0"), ge=0, le=0)

    @model_validator(mode="after")
    def validate_observed_population(self) -> "BenchmarkContractV2":
        if self.observation_window_start > self.observation_window_end:
            raise ValueError("observation window start must be on or before its end")
        observation_ids = [item.observation_id for item in self.observations]
        observation_hashes = [item.observation_sha256 for item in self.observations]
        if len(observation_ids) != len(set(observation_ids)):
            raise ValueError("closed-deal observation IDs must be unique")
        if len(observation_hashes) != len(set(observation_hashes)):
            raise ValueError("closed-deal observation hashes must be unique")
        expected_basis = (
            ValueBasis.EQUITY_VALUE
            if self.metric == MultipleMetric.PE
            else ValueBasis.ENTERPRISE_VALUE
        )
        if self.value_basis != expected_basis:
            raise ValueError("observed value basis is incompatible with the contract metric")
        for item in self.observations:
            if item.country_code != self.country_code:
                raise ValueError("cross-country borrowing is forbidden for BenchmarkContractV2")
            if item.business_type_id != self.business_type_id:
                raise ValueError("every observed deal must match the reviewed business type")
            if item.metric != self.metric or item.value_basis != self.value_basis:
                raise ValueError("every observed deal must match the metric and value basis")
            if not self.observation_window_start <= item.closed_at <= self.observation_window_end:
                raise ValueError("closed deal falls outside the disclosed observation window")
        return self


MultipleContractV9 = Annotated[
    Union[ModelPriorContractV1, BroadMedianPriorContractV1, BenchmarkContractV2],
    Field(discriminator="contract_version"),
]


class OfficialFinancialPeriodV1(_FrozenContract):
    """One immutable, source-bound official period consumed by ValuationIQ.

    Negative and zero earnings remain valid facts.  Method eligibility is a
    runner decision and never mutates or drops the source values.
    """

    period_start: date
    period_end: date
    filed_at: date
    statement_scope: StatementScope
    source_document_version: str = Field(min_length=1, max_length=200)
    source_record_id: str = Field(min_length=1, max_length=200)
    source_sha256: str = Field(pattern=SHA256_PATTERN)
    currency: str = Field(pattern=CURRENCY_PATTERN)
    revenue: Decimal | None = None
    revenue_source: RevenueSourceKind = RevenueSourceKind.UNKNOWN
    gross_margin: Decimal | None = None
    reported_ebitda: Decimal | None = None
    ebit: Decimal | None = None
    depreciation_amortization: Decimal | None = None
    net_income: Decimal | None = None
    book_equity: Decimal | None = None
    interest_bearing_debt: Decimal | None = None
    lease_liabilities: Decimal | None = None
    cash: Decimal | None = None
    is_official: Literal[True] = True
    is_forecast: Literal[False] = False

    @model_validator(mode="after")
    def validate_period(self) -> "OfficialFinancialPeriodV1":
        if self.period_start > self.period_end:
            raise ValueError("period_start must be on or before period_end")
        if self.revenue_source == RevenueSourceKind.GROSS_MARGIN and self.gross_margin is None:
            raise ValueError("gross-margin source requires a separately preserved gross_margin")
        for name in ("interest_bearing_debt", "lease_liabilities", "cash"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} cannot be negative")
        return self

    @property
    def fiscal_year(self) -> int:
        return self.period_end.year

    @property
    def material_fact_count(self) -> int:
        fields = (
            self.revenue if self.revenue_source == RevenueSourceKind.TURNOVER else None,
            self.gross_margin,
            self.reported_ebitda,
            self.ebit,
            self.depreciation_amortization,
            self.net_income,
            self.book_equity,
            self.interest_bearing_debt,
            self.lease_liabilities,
            self.cash,
        )
        return sum(value is not None for value in fields)


class CurveCompanyInputV1(_FrozenContract):
    company_key: str = Field(min_length=1, max_length=240)
    country_code: str = Field(pattern=COUNTRY_PATTERN)
    normalized_registry_number: str = Field(min_length=1, max_length=80)
    currency: str = Field(pattern=CURRENCY_PATTERN)
    mapping_status: MappingStatus
    mapping_version: str | None = Field(default=None, max_length=160)
    nace_code: str | None = Field(default=None, max_length=32)
    business_type_id: str | None = Field(default=None, max_length=160)
    revenue_multiple_reviewed: bool = False
    method_business_fit: dict[MultipleMetric, Decimal] = Field(default_factory=dict)
    input_confidence: ConfidenceLevel
    model_confidence: ConfidenceLevel
    freshness_cutoff: date
    blocking_value_contradictions: tuple[str, ...] = ()
    periods: tuple[OfficialFinancialPeriodV1, ...] = Field(
        min_length=1,
        max_length=MAX_PUBLIC_CURVE_PERIODS,
    )

    @model_validator(mode="after")
    def validate_company_input(self) -> "CurveCompanyInputV1":
        if self.mapping_status == MappingStatus.REVIEWED:
            if not self.mapping_version or not self.business_type_id or not self.nace_code:
                raise ValueError(
                    "reviewed mapping requires mapping_version, NACE and business type"
                )
        elif any((self.mapping_version, self.business_type_id, self.nace_code)):
            raise ValueError("unavailable mapping cannot carry mapped identifiers")
        if len({period.source_record_id for period in self.periods}) != len(self.periods):
            raise ValueError("official period source_record_id values must be unique")
        natural_periods = {
            (period.period_end, period.statement_scope, period.source_document_version)
            for period in self.periods
        }
        if len(natural_periods) != len(self.periods):
            raise ValueError("official period natural keys must be unique")
        for period in self.periods:
            if period.currency != self.currency:
                raise ValueError("period currency must equal the company calculation currency")
        for metric, score in self.method_business_fit.items():
            if score <= 0 or score > 1:
                raise ValueError(f"method fit for {metric} must be in (0, 1]")
        if any(not reason.strip() for reason in self.blocking_value_contradictions):
            raise ValueError("blocking value contradiction codes cannot be empty")
        if len(self.blocking_value_contradictions) != len(set(self.blocking_value_contradictions)):
            raise ValueError("blocking value contradiction codes must be unique")
        return self


class FrozenMultipleSnapshotV1(_FrozenContract):
    snapshot_id: str = Field(min_length=1, max_length=200)
    source_systems: Literal["DELPHI_ATHENA"] = "DELPHI_ATHENA"
    frozen_at: datetime
    multiple_manifest_sha256: str = Field(pattern=SHA256_PATTERN)
    contract_sha256_by_id: dict[str, str] = Field(min_length=1)

    @field_validator("frozen_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("snapshot frozen_at must be timezone-aware")
        return value

    @field_validator("contract_sha256_by_id")
    @classmethod
    def validate_contract_hashes(cls, values: dict[str, str]) -> dict[str, str]:
        if any(not key for key in values):
            raise ValueError("snapshot contract IDs cannot be empty")
        for value in values.values():
            if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
                raise ValueError("snapshot contract hashes must be lowercase SHA-256 digests")
        return values


class CampaignJobV1(_FrozenContract):
    company_key: str = Field(min_length=1, max_length=240)
    contract_ids: tuple[str, ...] = Field(min_length=1, max_length=4)

    @field_validator("contract_ids")
    @classmethod
    def validate_contract_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("a campaign job cannot repeat a contract ID")
        return values


class PublicCurveCampaignPlanV1(_FrozenContract):
    plan_version: Literal["PublicCurveCampaignPlanV1"] = "PublicCurveCampaignPlanV1"
    campaign_request_id: str = Field(min_length=1, max_length=200)
    model_version: Literal["valuationiq_public_curve_v9"] = "valuationiq_public_curve_v9"
    created_at: datetime
    snapshot: FrozenMultipleSnapshotV1
    engine_sha256: str = Field(pattern=SHA256_PATTERN)
    runtime_sha256: str = Field(pattern=SHA256_PATTERN)
    package_lock_sha256: str = Field(pattern=SHA256_PATTERN)
    jobs: tuple[CampaignJobV1, ...] = Field(min_length=1, max_length=MAX_CAMPAIGN_JOBS)
    durable_results_per_page: int = Field(
        default=MAX_DURABLE_RESULTS_PER_PAGE,
        ge=1,
        le=MAX_DURABLE_RESULTS_PER_PAGE,
    )

    @model_validator(mode="after")
    def validate_plan(self) -> "PublicCurveCampaignPlanV1":
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("plan created_at must be timezone-aware")
        company_keys = [job.company_key for job in self.jobs]
        if len(company_keys) != len(set(company_keys)):
            raise ValueError("campaign plan company keys must be unique")
        known_contracts = set(self.snapshot.contract_sha256_by_id)
        referenced = {contract_id for job in self.jobs for contract_id in job.contract_ids}
        unknown = referenced - known_contracts
        if unknown:
            raise ValueError(
                f"campaign jobs reference contracts outside the snapshot: {sorted(unknown)}"
            )
        return self


__all__ = [
    "BenchmarkContractV2",
    "BroadMedianPriorContractV1",
    "CampaignJobV1",
    "ClosedDealObservationV1",
    "ConfidenceLevel",
    "CurveCompanyInputV1",
    "FrozenMultipleSnapshotV1",
    "GeographyScope",
    "GovernedModelCellV1",
    "MAX_CAMPAIGN_JOBS",
    "MAX_DURABLE_RESULTS_PER_PAGE",
    "MAX_PUBLIC_CURVE_PERIODS",
    "MappingStatus",
    "ModelPriorContractV1",
    "MultipleBandV1",
    "MultipleContractV9",
    "MultipleMetric",
    "MultipleSourceKind",
    "OfficialFinancialPeriodV1",
    "PublicCurveCampaignPlanV1",
    "RevenueSourceKind",
    "StatementScope",
    "ValueBasis",
    "ValuationGrade",
]
