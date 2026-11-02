"""Versioned contracts for negative-EBITDA recovery valuations.

The input is deliberately explicit: callers provide operating drivers and
reinvestment assumptions, while ValuationIQ derives EBITDA, EBIT, cash taxes
and FCFF.  Authenticated verification remains a Titan responsibility and is
accepted only when the same receipt and schedules are committed by a signed
``valuation_case.v2``.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, Field, model_validator


class CustomerAcvDriver(BaseModel):
    model_type: Literal["customer_acv"] = "customer_acv"
    customers: Decimal = Field(..., ge=0)
    annual_contract_value: Decimal = Field(..., ge=0)

    @property
    def derived_revenue(self) -> Decimal:
        return self.customers * self.annual_contract_value


class ConsultantCapacityDriver(BaseModel):
    model_type: Literal["consultant_capacity"] = "consultant_capacity"
    consultants: Decimal = Field(..., ge=0)
    annual_capacity_per_consultant: Decimal = Field(..., ge=0)
    utilization: Decimal = Field(..., ge=0, le=1)
    rate: Decimal = Field(..., ge=0)

    @property
    def derived_revenue(self) -> Decimal:
        return self.consultants * self.annual_capacity_per_consultant * self.utilization * self.rate


class ArrRetentionExpansionDriver(BaseModel):
    model_type: Literal["arr_retention_expansion"] = "arr_retention_expansion"
    opening_arr: Decimal = Field(..., ge=0)
    gross_retention_rate: Decimal = Field(..., ge=0, le=1)
    expansion_arr: Decimal = Field(Decimal("0"), ge=0)
    new_arr: Decimal = Field(Decimal("0"), ge=0)

    @property
    def derived_revenue(self) -> Decimal:
        return self.opening_arr * self.gross_retention_rate + self.expansion_arr + self.new_arr


class UnitsPriceDriver(BaseModel):
    model_type: Literal["units_price"] = "units_price"
    units: Decimal = Field(..., ge=0)
    price_per_unit: Decimal = Field(..., ge=0)

    @property
    def derived_revenue(self) -> Decimal:
        return self.units * self.price_per_unit


class AdvisorCustomDriver(BaseModel):
    model_type: Literal["advisor_reviewed_custom"] = "advisor_reviewed_custom"
    model_name: str = Field(..., min_length=3, max_length=120)
    derived_revenue: Decimal = Field(..., ge=0)
    evidence_references: List[str] = Field(..., min_length=1, max_length=20)


class AttestedCustomDriver(BaseModel):
    """Evidence-backed custom model attested by an authenticated case owner.

    Advisor review remains an optional confidence uplift.  It is not an
    availability dependency: Titan authenticates the actor and commits the
    receipt and schedule in the signed valuation case.
    """

    model_type: Literal["attested_custom"] = "attested_custom"
    model_name: str = Field(..., min_length=3, max_length=120)
    derived_revenue: Decimal = Field(..., ge=0)
    evidence_references: List[str] = Field(..., min_length=1, max_length=20)


RecoveryOperatingDriver = Annotated[
    Union[
        CustomerAcvDriver,
        ConsultantCapacityDriver,
        ArrRetentionExpansionDriver,
        UnitsPriceDriver,
        AttestedCustomDriver,
        AdvisorCustomDriver,
    ],
    Field(discriminator="model_type"),
]


class RecoveryForecastYear(BaseModel):
    year: int = Field(..., ge=2000, le=2100)
    revenue: Decimal = Field(..., ge=0)
    operating_expenses_excluding_da: Decimal = Field(..., ge=0)
    depreciation_and_amortization: Decimal = Field(..., ge=0)
    tax_rate: Decimal = Field(..., ge=0, le=1)
    nol_opening: Decimal = Field(Decimal("0"), ge=0)
    capex: Decimal = Field(..., ge=0)
    delta_nwc: Decimal
    operating_driver: RecoveryOperatingDriver
    evidence_references: List[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def reconcile_driver_revenue(self) -> "RecoveryForecastYear":
        derived = self.operating_driver.derived_revenue
        tolerance = max(Decimal("1"), abs(self.revenue) * Decimal("0.005"))
        if abs(derived - self.revenue) > tolerance:
            raise ValueError(
                "operating driver revenue must reconcile to forecast revenue within 0.5%"
            )
        return self


class RecoveryScenario(BaseModel):
    key: Literal["downside", "base", "upside"]
    probability_percent: Decimal = Field(..., gt=0, le=100)
    forecast_years: List[RecoveryForecastYear] = Field(..., min_length=3, max_length=10)
    wacc_override: Optional[Decimal] = Field(None, gt=0, lt=1)
    terminal_growth_override: Optional[Decimal] = Field(None, ge=-0.1, lt=0.15)
    override_evidence_references: List[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_schedule_and_overrides(self) -> "RecoveryScenario":
        years = [row.year for row in self.forecast_years]
        if years != sorted(years) or len(years) != len(set(years)):
            raise ValueError("forecast years must be unique and strictly increasing")
        if years != list(range(years[0], years[0] + len(years))):
            raise ValueError("forecast years must be consecutive")
        if (
            self.wacc_override is not None or self.terminal_growth_override is not None
        ) and not self.override_evidence_references:
            raise ValueError("scenario-specific terminal overrides require evidence")
        return self


class FundingCommitment(BaseModel):
    amount: Decimal = Field(..., gt=0)
    available_year: int = Field(..., ge=2000, le=2100)
    source: Literal[
        "shareholder",
        "bank",
        "investor",
        "grant",
        "operating_facility",
        "other",
    ]
    evidence_references: List[str] = Field(..., min_length=1, max_length=20)


class RecoveryFundingPlan(BaseModel):
    opening_cash: Decimal = Field(..., ge=0)
    minimum_cash: Decimal = Field(..., ge=0)
    commitments: List[FundingCommitment] = Field(default_factory=list, max_length=20)
    # Optional only for legacy v1 deserialization. Titan refuses to mint new
    # automated Recovery DCF authority when this provenance is absent.
    evidence_references: List[str] = Field(default_factory=list, max_length=20)


class RecoveryVerificationIntent(BaseModel):
    intent: Literal["automated_guardrails", "owner_attestation", "advisor_review"]
    accepted: bool


class RecoveryVerificationReceipt(BaseModel):
    receipt_id: str = Field(..., min_length=8, max_length=160)
    actor_id: str = Field(..., min_length=1, max_length=200)
    actor_role: Literal["owner", "advisor"]
    verified_at: datetime
    revision_id: str = Field(..., min_length=1, max_length=200)
    evidence_references: List[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def require_timezone(self) -> "RecoveryVerificationReceipt":
        if self.verified_at.tzinfo is None or self.verified_at.utcoffset() is None:
            raise ValueError("verified_at must include a timezone")
        return self


class GovernedRecoveryAssumptions(BaseModel):
    wacc: Decimal = Field(..., gt=0, lt=1)
    terminal_growth_rate: Decimal = Field(..., ge=-0.1, lt=0.15)
    evidence_references: List[str] = Field(..., min_length=1, max_length=30)

    @model_validator(mode="after")
    def require_growth_below_wacc(self) -> "GovernedRecoveryAssumptions":
        if self.terminal_growth_rate >= self.wacc:
            raise ValueError("terminal growth must be lower than WACC")
        return self


class RecoveryInputs(BaseModel):
    schema_version: Literal["recovery_inputs.v1"] = "recovery_inputs.v1"
    scenarios: List[RecoveryScenario] = Field(..., min_length=3, max_length=3)
    funding_plan: RecoveryFundingPlan
    governed_assumptions: GovernedRecoveryAssumptions
    verification_intent: RecoveryVerificationIntent
    verification_receipt: Optional[RecoveryVerificationReceipt] = None

    @model_validator(mode="after")
    def validate_complete_scenario_set(self) -> "RecoveryInputs":
        keys = [scenario.key for scenario in self.scenarios]
        if sorted(keys) != ["base", "downside", "upside"] or len(set(keys)) != 3:
            raise ValueError("exactly one downside, base and upside scenario is required")
        total = sum((scenario.probability_percent for scenario in self.scenarios), Decimal("0"))
        if total != Decimal("100"):
            raise ValueError("scenario probabilities must sum exactly to 100%")
        starts = {scenario.forecast_years[0].year for scenario in self.scenarios}
        if len(starts) != 1:
            raise ValueError("all recovery scenarios must start in the same forecast year")
        return self


class OperatingTrajectory(BaseModel):
    direction: Literal["improving", "stable", "deteriorating", "mixed", "unknown"]
    ebitda_direction: Literal["improving", "stable", "deteriorating", "unknown"]
    confidence: Literal["low", "medium", "high"]
    comparable_periods: int = Field(..., ge=0)
    latest_revenue_growth: Optional[Decimal] = None
    latest_gross_margin_change: Optional[Decimal] = None
    latest_ebitda_margin_change: Optional[Decimal] = None
    latest_cash_burn_change: Optional[Decimal] = None
    latest_working_capital_change: Optional[Decimal] = None
    warnings: List[str] = Field(default_factory=list)
    conflicts: List[str] = Field(default_factory=list)


class RecoveryScenarioResult(BaseModel):
    key: Literal["downside", "base", "upside"]
    probability_percent: Decimal
    status: Literal["eligible", "floor_substituted", "blocked"]
    enterprise_value_low: Optional[Decimal] = Field(None, ge=0)
    enterprise_value_mid: Optional[Decimal] = Field(None, ge=0)
    enterprise_value_high: Optional[Decimal] = Field(None, ge=0)
    equity_value_low: Optional[Decimal] = None
    equity_value_mid: Optional[Decimal] = None
    equity_value_high: Optional[Decimal] = None
    break_even_year: Optional[int] = None
    funding_gap: Decimal = Field(Decimal("0"), ge=0)
    terminal_value_share: Optional[Decimal] = Field(None, ge=0, le=1)
    blockers: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    derived_schedule: List[dict[str, object]] = Field(default_factory=list)


class NegativeEbitdaResolution(BaseModel):
    status: Literal[
        "normalized_positive",
        "recovery_eligible",
        "revenue_benchmark_eligible",
        "asset_floor_only",
        "no_going_concern_range",
    ]
    reported_ebitda: Decimal
    normalized_ebitda: Optional[Decimal] = None
    operating_trajectory: OperatingTrajectory
    primary_method: Optional[
        Literal[
            "normalized_ebitda",
            "sde",
            "recovery_dcf",
            "arr_multiple",
            "revenue_multiple",
            "adjusted_nav",
            "orderly_liquidation",
        ]
    ] = None
    method_family: Literal[
        "normalized_earnings",
        "recovery_dcf",
        "revenue_or_arr",
        "asset_floor",
        "distress_or_liquidation",
        "insufficient_recovery_evidence",
    ] = "insufficient_recovery_evidence"
    primary_cause: Literal[
        "temporary_investment",
        "owner_compensation_distortion",
        "product_development_investment",
        "recent_customer_loss",
        "underutilization",
        "one_off_restructuring",
        "structurally_unprofitable_model",
        "insufficient_evidence",
    ] = "insufficient_evidence"
    cross_check_methods: List[str] = Field(default_factory=list)
    break_even_year: Optional[int] = None
    funding_gap: Optional[Decimal] = Field(None, ge=0)
    terminal_value_share: Optional[Decimal] = Field(None, ge=0, le=1)
    headline_equity_value_low: Optional[Decimal] = None
    headline_equity_value_mid: Optional[Decimal] = None
    headline_equity_value_high: Optional[Decimal] = None
    headline_enterprise_value_low: Optional[Decimal] = Field(None, ge=0)
    headline_enterprise_value_mid: Optional[Decimal] = Field(None, ge=0)
    headline_enterprise_value_high: Optional[Decimal] = Field(None, ge=0)
    confidence: Literal["low", "medium", "high"]
    cause_codes: List[str] = Field(default_factory=list)
    normalization_bridge: dict[str, object] = Field(default_factory=dict)
    break_even_bridge: Optional[dict[str, object]] = None
    equity_bridge: Optional[dict[str, object]] = None
    blockers: List[str] = Field(default_factory=list)
    required_evidence: List[str] = Field(default_factory=list)
    value_building_actions: List[str] = Field(default_factory=list)
    scenario_results: List[RecoveryScenarioResult] = Field(default_factory=list)
    candidate_method_audit: dict[str, dict[str, object]] = Field(default_factory=dict)
    audit_trail_version: Literal["negative_ebitda_resolution.v1"] = "negative_ebitda_resolution.v1"
    model_version: Literal["negative_ebitda_recovery.v1"] = "negative_ebitda_recovery.v1"
    evaluated_at: datetime
    input_snapshot_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    resolution_snapshot_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")


class PublicNegativeEbitdaRecoveryProjection(BaseModel):
    schema_version: Literal["public_negative_ebitda_recovery.v1"] = (
        "public_negative_ebitda_recovery.v1"
    )
    status: str
    entity_key: Optional[str] = None
    latest_fiscal_year: Optional[int] = None
    input_fingerprint: Optional[str] = Field(None, pattern=r"^[0-9a-f]{64}$")
    result_fingerprint: Optional[str] = Field(None, pattern=r"^[0-9a-f]{64}$")
    operating_trajectory: OperatingTrajectory
    primary_method: Optional[str] = None
    eligible_floor_methods: List[str] = Field(default_factory=list)
    blockers: List[str] = Field(default_factory=list)
    required_evidence: List[str] = Field(default_factory=list)
    audit_trail_version: Literal["negative_ebitda_resolution.v1"] = "negative_ebitda_resolution.v1"
    model_version: Literal["negative_ebitda_recovery.v1"] = "negative_ebitda_recovery.v1"
    evaluated_at: datetime
