"""Versioned partial financial contract: absent earnings and bridges remain absent."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

from src.api.schemas.stateless_common import _FiniteDecimalMixin
from src.api.schemas.stateless_response_schemas import MethodResult


class PartialDecimalModel(_FiniteDecimalMixin, BaseModel):
    """Preserve the v1 reader's finite decimals; new calculations enforce arithmetic limits."""

    @field_validator("source_reference", check_fields=False)
    @classmethod
    def nonblank_source(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Source reference must not be blank")
        return value


class PartialFinancialInputs(PartialDecimalModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    fiscal_year: int | None = Field(None, ge=2000, le=2100)
    currency: str | None = Field(None, pattern=r"^[A-Z]{3}$")
    amount_unit: Literal["currency_units"] = "currency_units"
    period_kind: Literal["annual_actual", "annual_forecast"] = "annual_actual"
    revenue: Decimal | None = Field(None, ge=0)
    ebitda: Decimal | None = None
    cash: Decimal | None = Field(None, ge=0)
    financial_debt: Decimal | None = Field(None, ge=0)
    nwc_adjustment: Decimal | None = None
    source_reference: str | None = None


class PartialMultipleReference(PartialDecimalModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    metric: Literal["revenue", "ebitda"]
    country_code: str = Field(pattern=r"^[A-Z]{2}$")
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    period_kind: Literal["annual_actual", "annual_forecast"] = "annual_actual"
    median: Decimal = Field(gt=0)
    low: Decimal | None = Field(None, ge=0)
    high: Decimal | None = Field(None, ge=0)
    evidence_status: Literal["supplied_market_reference", "disclosed_assumption"]
    source_reference: str = Field(min_length=1, max_length=1000)
    observed_on: date

    @model_validator(mode="after")
    def ordered_bounds(self) -> "PartialMultipleReference":
        from src.domain.financial_arithmetic import multiple_bounds

        multiple_bounds(self.median, self.low, self.high)
        return self


class ExplicitFcffYear(PartialDecimalModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    year_index: int = Field(ge=1, le=15)
    ebit: Decimal
    cash_taxes: Decimal = Field(ge=0)
    depreciation_amortization: Decimal = Field(ge=0)
    capex: Decimal = Field(ge=0)
    change_in_nwc: Decimal


class ExplicitFcffForecast(PartialDecimalModel):
    """Explicit standalone unlevered forecast; financing is excluded from FCFF."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    years: list[ExplicitFcffYear] = Field(min_length=1, max_length=15)
    discount_rate: Decimal = Field(gt=0, lt=1)
    discount_timing: Literal["end_of_year"] = "end_of_year"
    terminal_growth: Decimal | None = Field(None, gt=-1, lt=1)
    source_reference: str = Field(min_length=1, max_length=1000)
    evidence_status: Literal["supplied_forecast", "disclosed_assumption"]

    @field_validator("years")
    @classmethod
    def canonical_year_order(cls, years: list[ExplicitFcffYear]) -> list[ExplicitFcffYear]:
        return sorted(years, key=lambda row: row.year_index)

    @model_validator(mode="after")
    def valid_forecast(self) -> "ExplicitFcffForecast":
        years = sorted(row.year_index for row in self.years)
        if years != list(range(1, len(years) + 1)):
            raise ValueError("FCFF forecast requires distinct consecutive annual periods")
        if self.terminal_growth is not None and self.terminal_growth >= self.discount_rate:
            raise ValueError("Terminal growth must be below the discount rate")
        return self


class FairValueAssets(PartialDecimalModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    valuation_date: date
    fair_value_assets: Decimal = Field(ge=0)
    all_liabilities: Decimal = Field(ge=0)
    disposal_costs: Decimal = Field(ge=0)
    tax_latencies: Decimal = Field(ge=0)
    source_reference: str = Field(min_length=1, max_length=1000)
    evidence_status: Literal["supplied_appraisal", "disclosed_assumption"]


class PartialValuationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company_name: str = Field(min_length=1, max_length=200)
    country_code: str | None = Field(None, pattern=r"^[A-Z]{2}$")
    valuation_date: date
    evidence_revision_id: str = Field(min_length=1, max_length=100)
    financials: PartialFinancialInputs
    references: list[PartialMultipleReference] = Field(default_factory=list, max_length=2)
    fcff_forecast: ExplicitFcffForecast | None = None
    fair_value_assets: FairValueAssets | None = None

    @model_validator(mode="after")
    def validate_reference_identities(self) -> "PartialValuationRequest":
        metrics = [reference.metric for reference in self.references]
        if len(metrics) != len(set(metrics)):
            raise ValueError("Duplicate metric references")
        if any(reference.observed_on > self.valuation_date for reference in self.references):
            raise ValueError("Market evidence cannot post-date the valuation date")
        return self


class PartialValuationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[
        "partial_valuation.v1", "partial_valuation.v2", "partial_valuation.v3"
    ] = "partial_valuation.v1"
    assessment_id: str
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_revision_id: str
    conclusion: Literal[
        "numerical_methods_available", "numerical_results_only", "no_numerical_basis"
    ]
    valuation_basis: Literal["standalone_100_percent_control"] = "standalone_100_percent_control"
    inputs: PartialValuationRequest
    methods: dict[str, MethodResult]
    assumptions: list[str]
    advisor_acceptance_required: Literal[False] = False
    private_save_allowed: Literal[True] = True
    source_policy_version: Literal["source-evidence-required.v1"] | None = None
    diagnostics: dict[str, MethodResult] | None = None

    @model_serializer(mode="wrap")
    def preserve_historical_commitment(
        self, handler: SerializerFunctionWrapHandler
    ) -> dict[str, object]:
        payload: dict[str, object] = handler(self)
        if self.schema_version != "partial_valuation.v3":
            # Existing v1/v2 records are immutable. Reader defaults must not
            # change their original content commitments.
            for key in ("source_policy_version", "diagnostics"):
                if getattr(self, key) is None:
                    payload.pop(key, None)
        return payload

    @model_validator(mode="after")
    def verify_hash(self) -> "PartialValuationResponse":
        from src.services.reports.stateless_valuation_run import canonical_hash

        if self.schema_version == "partial_valuation.v3":
            if (
                self.source_policy_version != "source-evidence-required.v1"
                or self.diagnostics is None
            ):
                raise ValueError("Source-governed assessments require the server evidence policy")
            if self.conclusion != "no_numerical_basis":
                raise ValueError("Unverified partial inputs cannot support a priced conclusion")
            if any(method.available for method in self.diagnostics.values()):
                raise ValueError("Diagnostic scenarios cannot be eligible valuation methods")
            for method in self.methods.values():
                if method.available or any(
                    getattr(method, field) is not None
                    for field in (
                        "value",
                        "value_low",
                        "value_high",
                        "enterprise_value",
                        "enterprise_value_low",
                        "enterprise_value_high",
                        "equity_value",
                        "equity_value_low",
                        "equity_value_high",
                        "multiple_used",
                        "wacc",
                    )
                ):
                    raise ValueError("Unverified partial inputs must remain outside priced methods")
        elif self.source_policy_version is not None or self.diagnostics is not None:
            raise ValueError("Source policy fields require partial_valuation.v3")

        if self.schema_version == "partial_valuation.v1" and (
            self.inputs.country_code is None
            or self.inputs.financials.currency is None
            or self.inputs.financials.fiscal_year is None
        ):
            raise ValueError(
                "Saved v1 assessments require a known country, currency and fiscal year"
            )
        digest = canonical_hash(
            self.model_dump(mode="json", exclude={"assessment_id", "content_sha256"})
        )
        if digest != self.content_sha256 or self.assessment_id != f"partial_{digest}":
            raise ValueError("Partial valuation content commitment changed")
        from src.domain.method_keys import CANONICAL_RUNTIME_METHOD_KEYS, normalize_method_key

        if set(self.methods) != set(CANONICAL_RUNTIME_METHOD_KEYS):
            raise ValueError(
                "Partial valuation must account for every canonical method exactly once"
            )
        if self.evidence_revision_id != self.inputs.evidence_revision_id:
            raise ValueError("Partial valuation evidence revision disagrees with inputs")
        for key, method in self.methods.items():
            if normalize_method_key(method.method_key) != key:
                raise ValueError("Method identity disagrees with registry key")
            if self.inputs.country_code is None or self.inputs.financials.currency is None:
                if method.available or any(
                    getattr(method, field) is not None
                    for field in (
                        "value",
                        "value_low",
                        "value_high",
                        "enterprise_value",
                        "enterprise_value_low",
                        "enterprise_value_high",
                        "equity_value",
                        "equity_value_low",
                        "equity_value_high",
                        "multiple_used",
                        "wacc",
                    )
                ):
                    raise ValueError("Unknown country or currency cannot support numerical results")
            basis = getattr(method, method.value_basis)
            if method.value is not None and basis != method.value:
                raise ValueError("Method value disagrees with its declared value basis")
            if method.available and (method.value is None or method.value <= 0):
                raise ValueError("Eligible method requires an observed positive numerical result")
            if method.value_basis == "enterprise_value" and any(
                value is not None
                for value in (
                    method.equity_value,
                    method.equity_value_low,
                    method.equity_value_high,
                )
            ):
                raise ValueError("Enterprise-only result cannot imply a completed equity bridge")
            for mid, low, high in (
                (method.value, method.value_low, method.value_high),
                (
                    method.enterprise_value,
                    method.enterprise_value_low,
                    method.enterprise_value_high,
                ),
                (
                    method.equity_value,
                    method.equity_value_low,
                    method.equity_value_high,
                ),
            ):
                if (low is None) != (high is None):
                    raise ValueError("Method range must contain both endpoints or neither")
                if (
                    low is not None
                    and high is not None
                    and (low > high or mid is None or not low <= mid <= high)
                ):
                    raise ValueError("Method range must be ordered around its own point value")
        available = any(method.available for method in self.methods.values())
        if available != (self.conclusion == "numerical_methods_available"):
            raise ValueError("Partial valuation conclusion disagrees with method eligibility")
        if self.conclusion == "numerical_results_only" and not any(
            method.value is not None or method.enterprise_value is not None
            for method in self.methods.values()
        ):
            raise ValueError("Numerical results conclusion requires a computed value")
        # Older immutable v1 deficit assessments used no_numerical_basis when
        # positive-value eligibility failed. Keep their original hash readable;
        # new calculations distinguish a deficit from absent financial evidence.
        return self
