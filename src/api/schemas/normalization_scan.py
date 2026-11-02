from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class SDEFlagScanLedgerEntry(BaseModel):
    account_code: str
    description: str = ""
    balance: Decimal


class SDEFlagScanYear(BaseModel):
    year: int = Field(..., ge=2000, le=2100)
    revenue: Decimal = Field(..., ge=0)
    entries: list[SDEFlagScanLedgerEntry] = Field(default_factory=list)


class SDEFlagScanRequest(BaseModel):
    industry: str = "other"
    sector_benchmarks: dict[str, dict[str, Any]] | None = None
    years: list[SDEFlagScanYear] = Field(default_factory=list)


class SDEFlagItem(BaseModel):
    ledger_code: str
    ledger_name: str
    amount: float
    deviation_pct: float
    benchmark_median_pct: float
    benchmark_std_pct: float | None = None
    actual_pct_of_revenue: float | None = None
    z_score: float | None = None
    confidence: float | None = None
    year: int | None = None
    potential_sde_addback: bool
    suggested_question: str
    rationale: str | None = None
    category: str | None = None


class SDEFlagScanResponse(BaseModel):
    total_flags: int
    years: dict[str, list[SDEFlagItem]]


# ---------------------------------------------------------------------------
# Related-party scan schemas (BET-226)
# ---------------------------------------------------------------------------


class RelatedPartyLedgerEntry(BaseModel):
    account_code: str
    description: str = ""
    balance: Decimal


class RelatedPartyScanYear(BaseModel):
    year: int = Field(..., ge=2000, le=2100)
    revenue: Decimal = Field(..., ge=0)
    entries: list[RelatedPartyLedgerEntry] = Field(default_factory=list)


class RelatedPartyScanRequest(BaseModel):
    industry: str = "other"
    known_owner_entities: list[str] = Field(default_factory=list)
    years: list[RelatedPartyScanYear] = Field(default_factory=list)


class RelatedPartyFindingItem(BaseModel):
    ledger_code: str
    ledger_name: str
    amount: float
    category: str
    confidence: float
    rationale: str
    proposed_ebitda_adjustment: float
    adjustment_type: str
    benchmark_market_rate: float | None = None
    year: int | None = None
    suggested_question: str
    audit_sources: list[str] = Field(default_factory=list)


class RelatedPartyYearResult(BaseModel):
    year: int | None
    findings: list[RelatedPartyFindingItem]
    total_proposed_ebitda_adjustment: float
    high_confidence_count: int
    revenue: float
    explanation: str


class RelatedPartyScanResponse(BaseModel):
    total_findings: int
    total_proposed_ebitda_adjustment: float
    years: dict[str, RelatedPartyYearResult]


# ---------------------------------------------------------------------------
# Lease / IFRS 16 scan schemas (BET-227)
# ---------------------------------------------------------------------------


class LeaseScanLedgerEntry(BaseModel):
    account_code: str
    description: str = ""
    balance: Decimal


class LeaseScanYear(BaseModel):
    year: int = Field(..., ge=2000, le=2100)
    revenue: Decimal = Field(..., ge=0)
    reported_ebitda: Decimal | None = None
    entries: list[LeaseScanLedgerEntry] = Field(default_factory=list)


class LeaseScanRequest(BaseModel):
    industry: str = "other"
    country: str = "BE"
    years: list[LeaseScanYear] = Field(default_factory=list)


class LeaseLineItem(BaseModel):
    ledger_code: str
    ledger_name: str
    annual_amount: float
    ifrs16_ebitda_addback: float
    lease_type_hint: str
    gaap_regime: str
    already_capitalized: bool
    confidence: float
    rationale: str
    year: int | None = None


class LeaseYearResult(BaseModel):
    year: int | None
    lease_lines: list[LeaseLineItem]
    total_operating_lease_expense: float
    total_ifrs16_ebitda_addback: float
    reported_ebitda: float | None = None
    ifrs16_adjusted_ebitda: float | None = None
    lease_as_pct_of_revenue: float | None = None
    sector_benchmark_pct: float | None = None
    is_lease_intensive: bool
    gaap_regime: str
    gaap_regime_note: str
    explanation: str
    materiality_flag: bool
    materiality_note: str


class LeaseScanResponse(BaseModel):
    total_lease_expense: float
    total_ifrs16_ebitda_addback: float
    years: dict[str, LeaseYearResult]


# ---------------------------------------------------------------------------
# Owner benefit / pension scan schemas (BET-230)
# ---------------------------------------------------------------------------


class OwnerBenefitLedgerEntry(BaseModel):
    account_code: str
    description: str = ""
    balance: Decimal


class OwnerBenefitScanYear(BaseModel):
    year: int = Field(..., ge=2000, le=2100)
    entries: list[OwnerBenefitLedgerEntry] = Field(default_factory=list)


class OwnerBenefitScanRequest(BaseModel):
    owner_count: int = Field(default=1, ge=1)
    country: str = "BE"
    years: list[OwnerBenefitScanYear] = Field(default_factory=list)


class OwnerBenefitFindingItem(BaseModel):
    ledger_code: str
    ledger_name: str
    amount: float
    category: str
    category_label: str
    confidence: float
    rationale: str
    proposed_ebitda_adjustment: float
    personal_use_fraction: float
    year: int | None = None
    suggested_question: str
    audit_sources: list[str] = Field(default_factory=list)


class OwnerBenefitYearResult(BaseModel):
    year: int | None
    findings: list[OwnerBenefitFindingItem]
    total_proposed_ebitda_adjustment: float
    high_confidence_count: int
    vapz_cap_breach: bool
    explanation: str


class OwnerBenefitScanResponse(BaseModel):
    total_findings: int
    total_proposed_ebitda_adjustment: float
    vapz_cap_breach: bool
    years: dict[str, OwnerBenefitYearResult]
