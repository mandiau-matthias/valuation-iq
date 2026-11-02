"""Recipient-safe, frozen acquisition research. No valuation calculation or owner inference."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from datetime import date
from urllib.parse import urlsplit


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Source(StrictModel):
    id: str | None = None
    title: str = Field(max_length=200)
    url: str = Field(max_length=2000)
    kind: Literal["registry", "filing", "company_website", "direct_confirmation", "third_party"]
    checkedOn: str
    asOf: str | None = None

    @field_validator("url")
    @classmethod
    def source_url(cls, value):
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Sources require HTTPS without credentials")
        return value


class Criterion(StrictModel):
    id: str
    label: str = Field(max_length=2500)
    essential: bool
    verdict: Literal["meets", "fails", "unknown"]
    explanation: str = Field(max_length=2500)
    sources: list[Source] = Field(max_length=5)


class FinancialPeriod(StrictModel):
    year: int | None
    periodEnd: str | None
    currency: str | None
    revenue: float | None
    revenueBasis: str | None
    ebitda: float | None
    ebitdaBasis: str | None
    operatingProfit: float | None
    source: str | None
    sourceUrl: str | None
    warnings: list[str]

    @field_validator("sourceUrl")
    @classmethod
    def source_url(cls, value):
        return Source.source_url(value) if value else None


class ValuationEvidence(StrictModel):
    low: float | None
    high: float | None
    currency: str | None
    computedAt: str | None
    method: str | None


class BusinessProfileFinding(StrictModel):
    topic: Literal['activity', 'customers', 'revenue_model', 'capabilities', 'geography']
    text: str = Field(min_length=1, max_length=2500)
    basis: Literal['company_evidence', 'taxonomy_context']
    sources: list[Source] = Field(min_length=1, max_length=5)


class ValuationObservation(StrictModel):
    periodEnd: str
    low: float = Field(ge=0)
    high: float = Field(ge=0)
    currency: str = Field(pattern=r'^[A-Z]{3}$')
    method: str = Field(min_length=1, max_length=200)
    computedAt: str
    valueBasis: Literal['equity_value', 'enterprise_value', 'net_asset_reference']
    sources: list[Source] = Field(min_length=1, max_length=5)

    @model_validator(mode='after')
    def historical_evidence(self):
        for value in (self.periodEnd, self.computedAt):
            if date.fromisoformat(value).isoformat() != value:
                raise ValueError('Use an exact calendar date')
        if self.low > self.high or self.periodEnd > self.computedAt:
            raise ValueError('Invalid historical valuation bounds or dates')
        if not any(s.asOf == self.periodEnd for s in self.sources):
            raise ValueError('Valuation observation needs a source for its accounting period')
        return self


class Candidate(StrictModel):
    key: str
    countryCode: str
    registryNumber: str
    name: str = Field(max_length=255)
    city: str | None
    activity: str | None
    status: str | None
    capturedAt: str
    summary: str = Field(min_length=1, max_length=2500)
    nextStep: str = Field(min_length=1, max_length=1500)
    website: str
    identitySources: list[Source] = Field(max_length=5)
    criteria: list[Criterion] = Field(max_length=25)
    financials: list[FinancialPeriod] = Field(max_length=5)
    valuation: ValuationEvidence
    businessProfile: list[BusinessProfileFinding] = Field(default_factory=list, max_length=5)
    valuationHistory: list[ValuationObservation] = Field(default_factory=list, max_length=10)

    @model_validator(mode='after')
    def unique_enrichment(self):
        if len({p.periodEnd for p in self.valuationHistory}) != len(self.valuationHistory):
            raise ValueError('Duplicate valuation periods')
        if len({(p.currency, p.valueBasis) for p in self.valuationHistory}) > 1:
            raise ValueError('Mixed valuation currencies or value bases')
        if len({f.topic for f in self.businessProfile}) != len(self.businessProfile):
            raise ValueError('Duplicate business-profile topics')
        return self


class AcquisitionShortlistSnapshot(StrictModel):
    schemaVersion: Literal[1, 2]
    briefId: str
    version: int = Field(ge=1, le=2)
    publishedAt: str
    locale: Literal["en", "nl", "fr"]
    organization: str = Field(max_length=255)
    geography: str = Field(max_length=2500)
    agreedBrief: str = Field(max_length=12000)
    coverageNote: str = Field(max_length=2500)
    candidates: list[Candidate] = Field(min_length=5, max_length=10)

    @model_validator(mode='after')
    def frozen_enrichment(self):
        cutoff = self.publishedAt[:10]
        if self.schemaVersion == 2:
            date.fromisoformat(cutoff)
            if len({c.key for c in self.candidates}) != len(self.candidates) or len({(c.countryCode.upper(), c.registryNumber) for c in self.candidates}) != len(self.candidates):
                raise ValueError('Duplicate acquisition candidate')
        for c in self.candidates:
            if self.schemaVersion == 2 and len({a.id for a in c.criteria}) != len(c.criteria):
                raise ValueError('Duplicate criterion finding')
            if self.schemaVersion == 1 and (c.businessProfile or c.valuationHistory):
                raise ValueError('Enrichment requires snapshot version 2')
            if any(p.computedAt > cutoff for p in c.valuationHistory):
                raise ValueError('Valuation was calculated after publication')
            for s in [s for f in c.businessProfile for s in f.sources] + [s for p in c.valuationHistory for s in p.sources]:
                if date.fromisoformat(s.checkedOn).isoformat() != s.checkedOn:
                    raise ValueError('Use an exact source review date')
                if s.asOf and date.fromisoformat(s.asOf).isoformat() != s.asOf:
                    raise ValueError('Use an exact evidence date')
                if s.checkedOn > cutoff or (s.asOf and s.asOf > s.checkedOn):
                    raise ValueError('Evidence dates exceed publication or review date')
        return self


class AcquisitionShortlistRenderRequest(StrictModel):
    snapshot: AcquisitionShortlistSnapshot
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
