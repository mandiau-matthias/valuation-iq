"""A verified company forecast, committed by the signed valuation case.

Wire monetary values remain decimal strings. An uploaded file or a forecast
entered in a form is not sufficient: the source and company must be verified.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from decimal import Decimal, localcontext
from typing import Annotated, Literal, Mapping

import rfc8785
from pydantic import BaseModel, ConfigDict, Field, model_validator

Money = Annotated[str, Field(pattern=r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$", max_length=48)]
Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class ForecastCashFlowPeriod(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    start_date: date
    end_date: date
    revenue: Money
    ebitda: Money
    depreciation: Money
    amortization: Money
    cash_taxes: Money
    capex: Money
    change_in_operating_nwc: Money
    free_cash_flow: Money
    source_document_hash: Hash

    @model_validator(mode="after")
    def reconcile_unlevered_cash_flow(self) -> "ForecastCashFlowPeriod":
        if self.start_date >= self.end_date:
            raise ValueError("forecast period must have positive duration")
        for field in ("revenue", "depreciation", "amortization", "capex"):
            if Decimal(getattr(self, field)) < 0:
                raise ValueError(f"forecast {field} must be non-negative")
        with localcontext() as context:
            context.prec = 60
            fcff = (
                Decimal(self.ebitda)
                - Decimal(self.cash_taxes)
                - Decimal(self.capex)
                - Decimal(self.change_in_operating_nwc)
            )
            if fcff != Decimal(self.free_cash_flow):
                raise ValueError(
                    "forecast FCFF does not reconcile to EBITDA, cash taxes, capex and operating NWC"
                )
        return self


class ForecastVerification(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    record_id: str = Field(min_length=1)
    verifier_id: str = Field(min_length=1)
    verified_at: str
    source_identity_verified: Literal[True]
    company_identity_verified: Literal[True]
    document_hashes_verified: Literal[True]
    schedule_reconciled: Literal[True]


class ForecastEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["forecast-evidence.v1"] = "forecast-evidence.v1"
    company_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    issuer: str = Field(min_length=1)
    issued_on: date
    currency: Literal[
        "EUR", "GBP", "USD", "CHF", "CAD", "AUD", "NZD", "SEK", "NOK", "DKK", "PLN", "CZK"
    ]
    source_kind: Literal["connected_company_forecast", "verified_company_document"]
    source_document_hashes: list[Hash] = Field(min_length=1)
    periods: list[ForecastCashFlowPeriod] = Field(min_length=1, max_length=15)
    verification: ForecastVerification
    financing_treatment: Literal["unlevered_fcff"]
    lease_treatment: Literal["operating_cash_cost_in_ebitda"]
    discount_timing: Literal["year_end", "mid_year"]
    terminal_assumptions: str = Field(min_length=20)
    content_hash: Hash

    @model_validator(mode="before")
    @classmethod
    def verify_wire_hash(cls, value: object) -> object:
        if isinstance(value, Mapping):
            material = {key: child for key, child in value.items() if key != "content_hash"}
            expected = hashlib.sha256(rfc8785.dumps(material)).hexdigest()
            if value.get("content_hash") != expected:
                raise ValueError("forecast evidence content hash mismatch")
        return value

    @model_validator(mode="after")
    def validate_commitment(self) -> "ForecastEvidence":
        verified_at = datetime.fromisoformat(self.verification.verified_at.replace("Z", "+00:00"))
        if verified_at.tzinfo is None:
            raise ValueError("forecast verification must include a timezone")
        if verified_at.date() < self.issued_on:
            raise ValueError("forecast cannot be verified before issue")
        hashes = set(self.source_document_hashes)
        if len(hashes) != len(self.source_document_hashes):
            raise ValueError("forecast source hashes must be unique")
        prior: date | None = None
        for period in self.periods:
            if period.source_document_hash not in hashes:
                raise ValueError("forecast period source is not committed")
            if prior is not None and (period.start_date - prior).days != 1:
                raise ValueError("forecast periods must be ordered, contiguous and non-overlapping")
            prior = period.end_date
        return self
