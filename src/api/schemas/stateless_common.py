"""Common DTOs shared by the stateless ValuationIQ API schemas."""

import hashlib
import json
import math
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Dict, List, Literal, Optional, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.config.economic_snapshots import (
    ECONOMIC_SNAPSHOT_SCHEMA_VERSION,
    verify_economic_snapshot_hash,
)
from src.domain.financial_observations import validate_financial_observation_values

from .real_estate_yield_evidence import PropertyYieldEvidenceSource as PropertyYieldEvidenceSource
from .real_estate_yield_evidence import (
    RealEstateYieldEvidenceContract as RealEstateYieldEvidenceContract,
)

JsonObject = Dict[str, object]


class BenchmarkGeographyV1(BaseModel):
    country_code: Optional[str] = Field(None, min_length=2, max_length=2)
    region_key: Optional[str] = Field(None, min_length=1, max_length=64)


class BenchmarkContractV1(BaseModel):
    """Typed transport for the country-aware Upswitch benchmark release contract.

    Weak or continuity benchmarks are valid contracts, but their
    ``standalone_conclusion_eligible`` flag is false. Titan owns advisor
    approval; ValuationIQ preserves this full contract in the immutable run so
    the approval gate can independently inspect the sealed evidence.
    """

    model_config = ConfigDict(extra="allow")

    schema_version: Literal["benchmark_contract.v1"]
    status: Literal["resolved", "no_defendable_benchmark", "resolver_unavailable", "not_requested"]
    source: Literal["delphi_resolver", "country_baseline"]
    business_type_id: str = Field(..., min_length=1, max_length=255)
    primary_nace_code: Optional[str] = Field(None, max_length=32)
    geography: BenchmarkGeographyV1
    company_size_band: Optional[str] = Field(None, max_length=64)
    release_policy: Literal[
        "direct",
        "hierarchical_blend",
        "broader_peers_required",
        "country_baseline",
        "unavailable",
    ]
    standalone_conclusion_eligible: bool
    release_blockers: List[
        Literal[
            "country_baseline_not_standalone",
            "sample_size_below_five",
            "direct_sample_size_below_ten",
            "published_benchmark_stale",
            "distribution_not_ordered",
        ]
    ] = Field(default_factory=list)


class _FiniteDecimalMixin:
    """Rejects NaN and Inf values in Decimal and float fields at validation time."""

    @model_validator(mode="after")
    def _reject_nan_inf_decimals(self) -> Self:
        for name, value in self.__dict__.items():
            if isinstance(value, Decimal) and (value.is_nan() or value.is_infinite()):
                raise ValueError(
                    f"Field '{name}' must be a finite number, got {'NaN' if value.is_nan() else 'Infinity'}"
                )
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError(
                    f"Field '{name}' must be a finite number, got {'NaN' if math.isnan(value) else 'Infinity'}"
                )
        return self


class YearDataStateless(_FiniteDecimalMixin, BaseModel):
    """Financial data for a single year - stateless version."""

    year: int = Field(..., ge=2000, le=2100, description="Fiscal year")
    financial_observations: Dict[
        str, Literal["observed", "derived", "missing", "placeholder", "unknown"]
    ] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_observation_values(self) -> Self:
        validate_financial_observation_values(self.financial_observations, self.__dict__)
        return self

    period_start: Optional[date] = Field(
        None, description="Inclusive start date of the filed accounting period"
    )
    period_end: Optional[date] = Field(
        None, description="Inclusive end date of the filed accounting period"
    )
    revenue: Decimal = Field(
        ...,
        ge=0,
        description=(
            "Annual revenue in the request currency (0 allowed for holdings and "
            "asset-based cases)"
        ),
    )
    revenue_source: Optional[str] = Field(
        None,
        description=(
            "Filed source classification for revenue. Gross-margin classifications "
            "are never eligible as turnover."
        ),
    )
    gross_margin: Optional[Decimal] = Field(
        None,
        description="Filed gross margin, retained separately and never treated as revenue",
    )
    ebitda: Decimal = Field(..., description="EBITDA (can be negative)")
    ebitda_basis: Optional[str] = Field(
        None,
        description="Evidence basis such as reported, derived_from_ebit_da, or unavailable",
    )
    reported_ebitda: Optional[Decimal] = Field(
        None,
        description=(
            "EBITDA exactly as reported by the source. This is never overwritten "
            "by normalization decisions."
        ),
    )
    normalized_ebitda: Optional[Decimal] = Field(
        None,
        description=(
            "Evidence-backed EBITDA after accepted/verified adjustments. Proposed "
            "normalizations must not be written here."
        ),
    )

    ebitda_normalized: bool = Field(False, description="Whether EBITDA has been normalized")
    ebitda_normalization_metadata: Optional[JsonObject] = Field(
        None, description="Normalization adjustments applied"
    )

    cogs: Optional[Decimal] = Field(None, ge=0, description="Cost of Goods Sold")
    operating_revenue: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Operating top line after excluding financial/extraordinary income.",
    )
    gross_profit: Optional[Decimal] = None
    financial_income: Optional[Decimal] = None
    extraordinary_income: Optional[Decimal] = None
    extraordinary_items: Optional[Decimal] = None
    accounting_basis_policy: Optional[str] = Field(None, min_length=1, max_length=120)
    # Signed source costs and reversals; these fields never approve normalizations.
    operating_impairments: Optional[Decimal] = Field(None, allow_inf_nan=False)
    operating_provisions: Optional[Decimal] = Field(None, allow_inf_nan=False)
    non_recurring_operating_expenses: Optional[Decimal] = Field(None, allow_inf_nan=False)
    non_recurring_financial_expenses: Optional[Decimal] = Field(None, allow_inf_nan=False)
    unclassified_pnl_expenses: Optional[Decimal] = Field(None, allow_inf_nan=False)
    total_operating_income: Optional[Decimal] = Field(None, allow_inf_nan=False)
    non_recurring_operating_income: Optional[Decimal] = Field(None, allow_inf_nan=False)
    non_recurring_financial_income: Optional[Decimal] = Field(None, allow_inf_nan=False)
    unclassified_pnl_income: Optional[Decimal] = Field(None, allow_inf_nan=False)
    operating_expenses: Optional[Decimal] = Field(None, ge=0)
    ebit: Optional[Decimal] = None
    operating_profit: Optional[Decimal] = Field(
        None, description="Disclosed operating profit; eligible for EBIT, not EBITDA"
    )
    depreciation: Optional[Decimal] = Field(None, ge=0)
    depreciation_amortization: Optional[Decimal] = Field(None, ge=0)
    amortization: Optional[Decimal] = Field(None, ge=0)
    interest_expense: Optional[Decimal] = Field(None, ge=0)
    tax_expense: Optional[Decimal] = Field(None, ge=0)
    rent_expense: Optional[Decimal] = Field(None, ge=0)
    owner_director_compensation: Optional[Decimal] = Field(None, ge=0)
    personnel_costs: Optional[Decimal] = Field(None, ge=0)
    filed_employee_fte: Optional[Decimal] = Field(
        None,
        ge=0,
        description=(
            "Average employee headcount in full-time equivalents from the filed "
            "social balance (BE rubric 9087). Disclosure-only: excludes the "
            "owner/director and self-employed staff, so it must never be used "
            "as total operating capacity."
        ),
    )
    net_income: Optional[Decimal] = None

    total_assets: Optional[Decimal] = Field(None, ge=0)
    current_assets: Optional[Decimal] = Field(None, ge=0)
    cash: Optional[Decimal] = Field(None, ge=0)
    accounts_receivable: Optional[Decimal] = Field(None, ge=0)
    accounts_payable: Optional[Decimal] = Field(None, ge=0)
    inventory: Optional[Decimal] = Field(None, ge=0)
    total_liabilities: Optional[Decimal] = Field(None, ge=0)
    current_liabilities: Optional[Decimal] = Field(None, ge=0)
    short_term_debt: Optional[Decimal] = Field(None, ge=0)
    total_debt: Optional[Decimal] = Field(None, ge=0)
    lease_liabilities: Optional[Decimal] = Field(None, ge=0)
    total_equity: Optional[Decimal] = None
    # Signed: consolidated minorities can carry a loss share.
    minority_interest_result_share: Optional[Decimal] = None
    fixed_assets: Optional[Decimal] = Field(None, ge=0)
    paid_up_capital: Optional[Decimal] = Field(None, ge=0)
    capital_subsidies: Optional[Decimal] = Field(None, ge=0)
    deferred_tax_liabilities: Optional[Decimal] = Field(None, ge=0)
    buildings: Optional[Decimal] = Field(None, ge=0)
    machinery_equipment: Optional[Decimal] = Field(None, ge=0)
    other_provisions: Optional[Decimal] = Field(None, ge=0)

    capex: Optional[Decimal] = Field(None, ge=0, description="Capital Expenditures")
    nwc_change: Optional[Decimal] = Field(None, description="Change in Net Working Capital")
    operating_cash_flow: Optional[Decimal] = None
    investing_cash_flow: Optional[Decimal] = None
    financing_cash_flow: Optional[Decimal] = None
    free_cash_flow: Optional[Decimal] = Field(
        None,
        description="Explicit free cash flow to the firm (FCFF), including negative forecasts.",
    )

    is_forecast: bool = Field(
        False, description="True if this year is a user-provided forecast/prognosis"
    )
    source_identifier: Optional[str] = Field(
        None, description="Immutable filing/deposit identifier"
    )
    source_record_id: Optional[str] = Field(None, description="Immutable normalized-row identifier")
    source_parser_version: Optional[str] = Field(None, description="Parser/model version")
    source_currency: Optional[str] = Field(None, pattern=r"^[A-Z]{3}$")
    currency_basis: Optional[str] = Field(
        None, description="Original or converted currency basis for this filing row"
    )

    @model_validator(mode="after")
    def require_reported_basis_for_pre_normalized_ebitda(self) -> "YearDataStateless":
        """A normalized amount may never erase its reported starting point.

        Legacy clients sometimes carry the reported amount only inside the
        normalization metadata. Preserve that explicit number, but reject a
        pre-normalized row when no reported basis exists at all.
        """

        if not self.ebitda_normalized or self.reported_ebitda is not None:
            return self
        metadata = self.ebitda_normalization_metadata
        candidate = metadata.get("reported_ebitda") if isinstance(metadata, dict) else None
        if candidate is None:
            raise ValueError(
                "ebitda_normalized=true requires reported_ebitda; "
                "reported and adjusted earnings must remain separate"
            )
        try:
            reported = Decimal(str(candidate))
        except Exception as exc:
            raise ValueError("normalization metadata reported_ebitda must be a Decimal") from exc
        if not reported.is_finite():
            raise ValueError("normalization metadata reported_ebitda must be finite")
        self.reported_ebitda = reported
        return self


class NormalizationAdjustment(_FiniteDecimalMixin, BaseModel):
    """A normalization decision transported by Titan and priced by ValuationIQ."""

    field: str = Field(..., description="Field being adjusted (e.g., 'ebitda', 'owner_salary')")
    category: Optional[str] = Field(
        None,
        description="Economic adjustment category, kept distinct from the adjusted field",
    )
    label: str = Field(..., description="Human-readable label")
    original_value: Decimal = Field(..., description="Original value before adjustment")
    adjusted_value: Decimal = Field(..., description="Value after adjustment")
    adjustment_amount: Decimal = Field(..., description="Amount of adjustment")
    reason: str = Field(..., description="Reason for adjustment")
    source: str = Field(
        ..., description="Source of adjustment: 'user_input', 'ai_suggested', 'import'"
    )
    approved_by: Optional[str] = Field(None, description="Who approved the adjustment")
    id: Optional[str] = Field(None, description="Stable normalization decision identifier")
    fiscal_year: Optional[int] = Field(
        None,
        ge=1900,
        le=2100,
        description="Fiscal year affected; legacy missing values apply to current_year only.",
    )
    status: str = Field(
        "proposed",
        description="accepted/verified/applied enter priced totals; proposed/rejected do not.",
    )
    evidence_id: Optional[str] = Field(None, description="Hermes fact/evidence identifier")
    reviewed_at: Optional[str] = Field(
        None,
        max_length=64,
        description="ISO-8601 timestamp of the explicit reviewer decision, when available",
    )
    rule_version: Optional[str] = Field(None, description="Economic normalization policy version")
    currency: Optional[str] = Field(None, pattern=r"^[A-Z]{3}$")
    owner_role: Optional[str] = Field(None, pattern=r"^(working|passive)$")
    actual_owner_compensation: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Gross owner compensation actually paid in the fiscal year",
    )
    replacement_owner_compensation: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Market replacement compensation; zero for a passive owner",
    )

    @model_validator(mode="after")
    def reconcile_reported_adjusted_and_signed_amount(self) -> "NormalizationAdjustment":
        expected = self.adjusted_value - self.original_value
        if expected.quantize(Decimal("0.01")) != self.adjustment_amount.quantize(Decimal("0.01")):
            raise ValueError("adjustment_amount must equal adjusted_value - original_value")
        compensation_values = (
            self.actual_owner_compensation,
            self.replacement_owner_compensation,
            self.owner_role,
        )
        if any(value is not None for value in compensation_values):
            if any(value is None for value in compensation_values):
                raise ValueError(
                    "owner compensation terms require owner_role, "
                    "actual_owner_compensation and replacement_owner_compensation"
                )
            identifier = str(self.category or self.field).strip().lower()
            if identifier not in {
                "salary",
                "owner_salary",
                "owner_comp",
                "owner_compensation_adjustment",
            }:
                raise ValueError("owner compensation terms require an owner-compensation category")
            assert self.actual_owner_compensation is not None
            assert self.replacement_owner_compensation is not None
            expected_delta = self.actual_owner_compensation - self.replacement_owner_compensation
            if expected_delta.quantize(Decimal("0.01")) != self.adjustment_amount.quantize(
                Decimal("0.01")
            ):
                raise ValueError(
                    "owner compensation adjustment must equal actual compensation "
                    "minus replacement compensation"
                )
            if self.owner_role == "passive" and self.replacement_owner_compensation != 0:
                raise ValueError("passive-owner replacement compensation must be zero")
        return self


class BusinessTypeCalibration(_FiniteDecimalMixin, BaseModel):
    """Business type calibration data from Titan's resolved benchmark contract."""

    business_type_id: str = Field(..., description="Business type ID (e.g., 'bakery')")
    category_id: str = Field(..., description="Category ID (e.g., 'food-services')")
    industry: str = Field(..., description="Industry classification")
    sector: Optional[str] = Field(None, description="Sector classification")

    ev_ebitda_median: Decimal = Field(..., description="Median EV/EBITDA multiple")
    ev_ebitda_p10: Optional[Decimal] = Field(None, description="10th percentile")
    ev_ebitda_p25: Optional[Decimal] = Field(None, description="25th percentile")
    ev_ebitda_p75: Optional[Decimal] = Field(None, description="75th percentile")
    ev_ebitda_p90: Optional[Decimal] = Field(None, description="90th percentile")

    ev_revenue_median: Optional[Decimal] = Field(None, description="Median EV/Revenue multiple")
    ev_revenue_p10: Optional[Decimal] = None
    ev_revenue_p25: Optional[Decimal] = None
    ev_revenue_p75: Optional[Decimal] = None
    ev_revenue_p90: Optional[Decimal] = None

    # Optional governed public-method consumers. Their absence is deliberate:
    # ValuationIQ must fall through instead of manufacturing defaults.
    ev_ebit_median: Optional[Decimal] = Field(None, description="Median governed EV/EBIT multiple")
    ev_ebit_p10: Optional[Decimal] = None
    ev_ebit_p25: Optional[Decimal] = None
    ev_ebit_p75: Optional[Decimal] = None
    ev_ebit_p90: Optional[Decimal] = None

    pe_ratio_median: Optional[Decimal] = Field(None, description="Median governed P/E multiple")
    pe_ratio_p10: Optional[Decimal] = None
    pe_ratio_p25: Optional[Decimal] = None
    pe_ratio_p75: Optional[Decimal] = None
    pe_ratio_p90: Optional[Decimal] = None

    typical_ebitda_margin: Optional[Decimal] = Field(
        None, description="Typical EBITDA margin for this business type"
    )
    typical_revenue: Optional[Decimal] = None
    typical_employee_count: Optional[int] = None

    dcf_preference: Optional[Decimal] = Field(
        None, ge=Decimal("0"), le=Decimal("1"), description="DCF weight preference"
    )
    multiples_preference: Optional[Decimal] = Field(
        None, ge=Decimal("0"), le=Decimal("1"), description="Multiples weight preference"
    )
    owner_dependency_impact: Optional[Decimal] = Field(
        None,
        description=(
            "v1 SHADOW-ONLY (do not consume for adjustment math). "
            "Per-business-type / per-user dependency hint from Titan; "
            "preserved for telemetry and back-compat. The live owner-"
            "dependency adjustment runs through `OwnerDependencyProcessor` "
            "from the v2 `owner_dependency_factors` payload. The legacy "
            "consumer `stateless_router._calculate_owner_adjustment` is "
            "shimmed to 0.0; do not re-introduce it into any "
            "`total_adjustment` sum (SPIKE-1 §3.4)."
        ),
    )

    sme_size_discount_micro: Optional[Decimal] = None
    sme_size_discount_small: Optional[Decimal] = None
    sme_size_discount_medium: Optional[Decimal] = None
    sme_liquidity_discount: Optional[Decimal] = None

    calibration_source: str = Field(default="database", description="Source of calibration data")
    calibration_quality_score: Optional[Decimal] = Field(None, ge=0, le=1)
    sample_size: Optional[int] = None
    last_updated: Optional[str] = None
    benchmark_contract: Optional[JsonObject] = Field(
        None,
        description=(
            "Resolved Upswitch Index benchmark contract that authorized these multiples. "
            "Required for concrete business-type multiple valuations unless the "
            "request explicitly opts into a disclosed fallback."
        ),
    )


class DisclosedExternalMarketReference(_FiniteDecimalMixin, BaseModel):
    """Advisor-approved external reference for a fail-closed benchmark fallback.

    This transport object is deliberately separate from an Index benchmark
    contract and from percentile fields.  A published market study can inform
    an advisor-defined reference range without turning its bounds into claimed
    P25/P75 observations for a company/market cohort that does not exist.
    """

    source_title: str = Field(..., min_length=3, max_length=240)
    source_url: str = Field(..., min_length=8, max_length=2048)
    source_as_of: Optional[str] = Field(None, max_length=64)
    evidence_summary: str = Field(..., min_length=10, max_length=2000)
    applied_multiple: Decimal = Field(..., gt=0, le=50)
    range_low_multiple: Decimal = Field(..., gt=0, le=50)
    range_high_multiple: Decimal = Field(..., gt=0, le=50)
    range_type: Literal["advisor_defined_external_reference_range"] = (
        "advisor_defined_external_reference_range"
    )

    @model_validator(mode="after")
    def validate_ordered_reference_range(self) -> "DisclosedExternalMarketReference":
        if self.range_low_multiple > self.applied_multiple:
            raise ValueError("external reference low multiple cannot exceed applied multiple")
        if self.range_high_multiple < self.applied_multiple:
            raise ValueError("external reference high multiple cannot be below applied multiple")
        return self


class ExternalMarketReferenceSource(_FiniteDecimalMixin, BaseModel):
    """One immutable source record inside an advisor-reviewed market contract."""

    source_title: str = Field(..., min_length=3, max_length=240)
    source_url: str = Field(..., min_length=8, max_length=2048)
    published_on: Optional[date] = None
    retrieved_on: date
    content_sha256: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    geography: str = Field(..., min_length=2, max_length=120)
    sector_relevance: str = Field(..., min_length=10, max_length=1000)
    metric_definition: str = Field(..., min_length=10, max_length=1000)
    observed_value: Optional[Decimal] = Field(None, gt=0, le=50)
    sample_disclosure: Optional[str] = Field(None, max_length=1000)
    evidence_summary: str = Field(..., min_length=10, max_length=2000)


class ExternalMarketReferenceContract(_FiniteDecimalMixin, BaseModel):
    """Sealed dossier-only market evidence; never an Upswitch Index contract.

    The contract authorizes a reviewed, non-statistical market reference without
    converting study observations into fabricated percentiles or sample counts.
    Its hash is verified over the complete payload except ``content_sha256``.
    """

    contract_id: str = Field(..., pattern=r"^emrc_[A-Za-z0-9_-]{8,80}$")
    schema_version: Literal["external_market_reference.v1"] = "external_market_reference.v1"
    status: Literal["reviewed_sealed"] = "reviewed_sealed"
    methodology_version: str = Field(..., min_length=3, max_length=120)
    reviewer: str = Field(..., min_length=3, max_length=200)
    reviewed_at: str = Field(..., min_length=10, max_length=64)
    business_type_id: str = Field(..., min_length=2, max_length=100)
    country_code: str = Field(..., pattern=r"^[A-Z]{2}$")
    metric: Literal["EV_EBITDA"] = "EV_EBITDA"
    applied_multiple: Decimal = Field(..., gt=0, le=50)
    range_low_multiple: Decimal = Field(..., gt=0, le=50)
    range_high_multiple: Decimal = Field(..., gt=0, le=50)
    percentile_p25: None = None
    percentile_median: None = None
    percentile_p75: None = None
    sample_size: None = None
    sources: List[ExternalMarketReferenceSource] = Field(..., min_length=1, max_length=20)
    limitations: List[str] = Field(..., min_length=1, max_length=20)
    content_sha256: str = Field(..., pattern=r"^[0-9a-f]{64}$")

    @staticmethod
    def canonical_hash(payload: Dict[str, object]) -> str:
        canonical = dict(payload)
        canonical.pop("content_sha256", None)
        raw = json.dumps(
            canonical,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @model_validator(mode="after")
    def validate_sealed_contract(self) -> "ExternalMarketReferenceContract":
        if self.range_low_multiple > self.applied_multiple:
            raise ValueError(
                "external market reference low multiple cannot exceed applied multiple"
            )
        if self.range_high_multiple < self.applied_multiple:
            raise ValueError(
                "external market reference high multiple cannot be below applied multiple"
            )
        payload = self.model_dump(mode="json")
        if self.canonical_hash(payload) != self.content_sha256:
            raise ValueError("external market reference content_sha256 does not match payload")
        return self


class WaccEvidenceContract(_FiniteDecimalMixin, BaseModel):
    """Source-bound direct sector WACC supplied by Titan.

    A direct sector WACC is a complete discount-rate observation, not a CAPM
    component.  In particular, ``includes_size_premium`` is deliberately fixed
    to ``True`` so the DCF adapter can never add an engine or SME size premium
    on top of the published rate.
    """

    schema_version: Literal["wacc_evidence.v1"] = "wacc_evidence.v1"
    mode: Literal["direct_sector_wacc"] = "direct_sector_wacc"
    value_pct: Decimal = Field(..., gt=0, le=100)
    range_low_pct: Decimal = Field(..., gt=0, le=100)
    range_high_pct: Decimal = Field(..., gt=0, le=100)
    period: str = Field(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    source_type: str = Field(..., min_length=3, max_length=120)
    source_url: str = Field(..., pattern=r"^https://", max_length=2048)
    content_sha256: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    chart_locator: str = Field(..., min_length=3, max_length=500)
    methodology: str = Field(..., min_length=10, max_length=2000)
    reviewer: str = Field(..., min_length=3, max_length=200)
    reviewed_at: str = Field(..., min_length=20, max_length=64)
    includes_size_premium: Literal[True] = True

    @property
    def value_fraction(self) -> Decimal:
        return self.value_pct / Decimal("100")

    @property
    def range_low_fraction(self) -> Decimal:
        return self.range_low_pct / Decimal("100")

    @property
    def range_high_fraction(self) -> Decimal:
        return self.range_high_pct / Decimal("100")

    @model_validator(mode="after")
    def validate_direct_sector_evidence(self) -> "WaccEvidenceContract":
        if not self.range_low_pct <= self.value_pct <= self.range_high_pct:
            raise ValueError("direct sector WACC value must fall inside its source band")

        # Direct-sector evidence must never be a relabelled Damodaran total-beta
        # table. Total beta is a private-company beta input, not a WACC or size
        # premium observation.
        provenance = " ".join(
            (
                self.source_type,
                self.source_url,
                self.chart_locator,
                self.methodology,
            )
        ).casefold()
        if re.search(r"\btotal[\s_-]*beta\b", provenance):
            raise ValueError("Total Beta cannot be used as direct sector WACC evidence")

        try:
            reviewed_at = datetime.fromisoformat(self.reviewed_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("reviewed_at must be an ISO-8601 timestamp") from exc
        if reviewed_at.tzinfo is None or reviewed_at.utcoffset() is None:
            raise ValueError("reviewed_at must include a timezone")
        reviewed_at = reviewed_at.astimezone(timezone.utc)
        period_year, period_month = (int(part) for part in self.period.split("-"))
        age_months = (reviewed_at.year - period_year) * 12 + reviewed_at.month - period_month
        if age_months < 0:
            raise ValueError("direct sector WACC period cannot be after reviewed_at")
        if age_months > 18:
            raise ValueError("direct sector WACC source period is stale (older than 18 months)")
        return self


class EconomicContext(_FiniteDecimalMixin, BaseModel):
    """Economic context from Titan for DCF calculations."""

    risk_free_rate: Decimal = Field(
        ..., description="10-year government bond yield (e.g., 0.025 for 2.5%)"
    )
    risk_free_rate_source: Optional[str] = Field(
        None,
        description="Provenance for the supplied risk-free rate (e.g. ECB snapshot, static defaults)",
    )
    risk_free_rate_is_override: bool = Field(
        False,
        description="When true, treat risk_free_rate as an explicit override instead of a reference input",
    )
    gdp_growth_rate: Decimal = Field(..., description="Expected GDP growth rate")
    terminal_growth_rate: Decimal = Field(..., description="Terminal growth rate for DCF")
    inflation_rate: Optional[Decimal] = Field(None, description="Expected inflation")
    equity_risk_premium: Optional[Decimal] = Field(
        None,
        description="Explicit equity risk premium override for WACC build-up",
    )
    market_risk_premium: Optional[Decimal] = Field(
        None,
        description="Alias for equity_risk_premium used by upstream systems",
    )
    erp: Optional[Decimal] = Field(
        None,
        description="Short alias for equity risk premium used by market-data feeds",
    )
    country_code: str = Field(
        ..., pattern=r"^[A-Z]{2}$", description="Explicit country for the economic context"
    )
    source: str = Field(default="titan", description="Data source")
    schema_version: Optional[Literal["economic_snapshot.v1"]] = None
    snapshot_id: Optional[str] = Field(None, min_length=1, max_length=200)
    snapshot_hash: Optional[str] = Field(None, pattern=r"^[0-9a-f]{64}$")
    snapshot_issuer: Optional[str] = Field(None, min_length=1, max_length=200)
    risk_free_rate_observed_at: Optional[date] = None
    equity_risk_premium_observed_at: Optional[date] = None
    growth_rates_observed_at: Optional[date] = None
    source_references: List[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_snapshot_commitment(self) -> "EconomicContext":
        snapshot_fields = (
            "schema_version",
            "snapshot_id",
            "snapshot_hash",
            "snapshot_issuer",
            "risk_free_rate_observed_at",
            "equity_risk_premium_observed_at",
            "growth_rates_observed_at",
        )
        supplied = [getattr(self, field) is not None for field in snapshot_fields]
        if not any(supplied):
            if self.source_references:
                raise ValueError(
                    "economic_context.source_references require a complete economic snapshot"
                )
            return self
        erp_values = [
            value
            for value in (
                self.equity_risk_premium,
                self.market_risk_premium,
                self.erp,
            )
            if value is not None
        ]
        if erp_values and any(value != erp_values[0] for value in erp_values[1:]):
            raise ValueError(
                "sealed economic_context equity_risk_premium aliases must describe one value"
            )
        if not all(supplied) or not self.source_references:
            raise ValueError(
                "economic_context snapshot metadata, observation dates and source_references "
                "must be supplied together"
            )
        if self.schema_version != ECONOMIC_SNAPSHOT_SCHEMA_VERSION:
            raise ValueError("unsupported economic_context snapshot schema")
        if any(not reference.startswith("https://") for reference in self.source_references):
            raise ValueError("economic_context source_references must use HTTPS")
        verify_economic_snapshot_hash(self.model_dump(mode="python"))
        return self


class OwnerDependencyInput(_FiniteDecimalMixin, BaseModel):
    """Owner dependency assessment from Titan's chat flow."""

    customer_relationships: Optional[int] = Field(None, ge=0, le=100)
    key_supplier_relationships: Optional[int] = Field(None, ge=0, le=100)
    operational_knowledge: Optional[int] = Field(None, ge=0, le=100)
    strategic_decision_making: Optional[int] = Field(None, ge=0, le=100)
    revenue_generation: Optional[int] = Field(None, ge=0, le=100)
    employee_management: Optional[int] = Field(None, ge=0, le=100)
    financial_oversight: Optional[int] = Field(None, ge=0, le=100)
    industry_expertise: Optional[int] = Field(None, ge=0, le=100)
    brand_association: Optional[int] = Field(None, ge=0, le=100)
    technology_systems: Optional[int] = Field(None, ge=0, le=100)
    regulatory_compliance: Optional[int] = Field(None, ge=0, le=100)
    succession_planning: Optional[int] = Field(None, ge=0, le=100)

    overall_dependency_score: Optional[int] = Field(
        None, ge=0, le=100, description="Overall owner dependency score"
    )
    suggested_discount: Optional[Decimal] = Field(
        None, description="Suggested discount based on owner dependency"
    )
