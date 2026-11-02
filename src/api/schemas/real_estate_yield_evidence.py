"""Sealed property-yield evidence and source validation contracts."""

import hashlib
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Literal, Optional

import rfc8785
from pydantic import BaseModel, Field, model_validator


class PropertyYieldEvidenceSource(BaseModel):
    """One immutable source used by the canonical property-yield method."""

    source_id: str = Field(..., min_length=3, max_length=200)
    provider: str = Field(..., min_length=2, max_length=200)
    source_kind: Literal[
        "property_title",
        "property_noi",
        "property_occupancy",
        "property_yield_snapshot",
        "property_debt",
        "property_cash",
        "property_nwc",
        "property_nav_appraisal",
    ]
    document_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    locator: Optional[str] = Field(None, min_length=1, max_length=1000)
    url: Optional[str] = Field(None, pattern=r"^https://", max_length=2048)
    observed_on: date
    published_on: Optional[date] = None
    evidence_summary: str = Field(..., min_length=10, max_length=2000)

    @model_validator(mode="after")
    def require_resolvable_source(self) -> "PropertyYieldEvidenceSource":
        if self.locator is None and self.url is None:
            raise ValueError("property evidence source requires locator or HTTPS url")
        if self.published_on is not None and self.published_on < self.observed_on:
            raise ValueError("property source published_on cannot pre-date observed_on")
        return self


class RealEstateYieldEvidenceContract(BaseModel):
    """Hash-sealed evidence contract for canonical income capitalisation.

    The contract is not standalone monetary authority.  It is priced only when
    Titan's Ed25519-signed ``ValuationCase v2`` commits to these exact bytes.
    """

    schema_version: Literal["real_estate_yield_evidence.v1"] = "real_estate_yield_evidence.v1"
    contract_id: str = Field(..., pattern=r"^reyc_[A-Za-z0-9_-]{8,80}$")
    status: Literal["reviewed_sealed"] = "reviewed_sealed"
    company_id: str = Field(..., min_length=1, max_length=200)
    evidence_revision_id: str = Field(..., min_length=1, max_length=200)
    country_code: str = Field(..., pattern=r"^(BE|FR|IE)$")
    currency: str = Field(..., pattern=r"^[A-Z]{3}$")
    valuation_date: date

    sustainable_noi: Decimal = Field(..., gt=Decimal("0"))
    noi_period_start: date
    noi_period_end: date
    noi_is_annualized: Literal[True] = True
    occupancy_rate: Decimal = Field(..., ge=Decimal("0"), le=Decimal("1"))
    property_debt: Decimal = Field(..., ge=Decimal("0"))
    unrestricted_cash: Decimal = Field(Decimal("0"), ge=Decimal("0"))
    normalized_nwc_adjustment: Decimal = Decimal("0")

    metric: Literal["property_yield"] = "property_yield"
    methodology: Literal["net_income_capitalisation"] = "net_income_capitalisation"
    methodology_version: str = Field(..., min_length=3, max_length=120)
    sample_size: int = Field(..., ge=1)
    cap_rate_low: Decimal = Field(..., gt=Decimal("0"), lt=Decimal("1"))
    cap_rate_mid: Decimal = Field(..., gt=Decimal("0"), lt=Decimal("1"))
    cap_rate_high: Decimal = Field(..., gt=Decimal("0"), lt=Decimal("1"))
    yield_observed_on: date
    yield_published_on: date

    governed_nav_equity_floor: Optional[Decimal] = Field(None, ge=Decimal("0"))
    nav_floor_basis: Optional[Literal["adjusted_equity_value"]] = None
    sources: List[PropertyYieldEvidenceSource] = Field(..., min_length=5, max_length=30)
    reviewer_id: str = Field(..., min_length=1, max_length=200)
    reviewer_organization: str = Field(..., min_length=1, max_length=200)
    reviewer_role: Literal["advisor", "senior_advisor", "real_estate_valuer", "compliance_reviewer"]
    reviewed_at: datetime
    limitations: List[str] = Field(default_factory=list, max_length=20)
    content_sha256: str = Field(..., pattern=r"^[0-9a-f]{64}$")

    @staticmethod
    def canonical_hash(payload: Dict[str, object]) -> str:
        canonical = dict(payload)
        canonical.pop("content_sha256", None)
        return hashlib.sha256(rfc8785.dumps(canonical)).hexdigest()

    @model_validator(mode="after")
    def validate_governed_property_contract(self) -> "RealEstateYieldEvidenceContract":
        monetary_values = (
            self.sustainable_noi,
            self.property_debt,
            self.unrestricted_cash,
            self.normalized_nwc_adjustment,
            self.cap_rate_low,
            self.cap_rate_mid,
            self.cap_rate_high,
            self.governed_nav_equity_floor,
        )
        if any(value is not None and not value.is_finite() for value in monetary_values):
            raise ValueError("property yield contract decimals must be finite")
        if not self.cap_rate_low <= self.cap_rate_mid <= self.cap_rate_high:
            raise ValueError("cap-rate range must satisfy low <= mid <= high")
        if self.noi_period_start > self.noi_period_end:
            raise ValueError("NOI period start cannot follow period end")
        if self.noi_period_end > self.valuation_date:
            raise ValueError("NOI period cannot extend beyond the valuation date")
        if (self.noi_period_end - self.noi_period_start).days < 270:
            raise ValueError("canonical sustainable NOI requires at least nine months of evidence")
        if self.yield_published_on < self.yield_observed_on:
            raise ValueError("yield published date cannot pre-date its observation date")
        if max(self.yield_observed_on, self.yield_published_on) > self.valuation_date:
            raise ValueError("yield evidence cannot post-date the valuation date")
        if self.reviewed_at.tzinfo is None or self.reviewed_at.utcoffset() is None:
            raise ValueError("property evidence reviewed_at must include timezone")
        if self.reviewed_at.date() < self.yield_observed_on:
            raise ValueError("property evidence review cannot pre-date the yield observation")

        kinds = {source.source_kind for source in self.sources}
        required = {
            "property_noi",
            "property_occupancy",
            "property_yield_snapshot",
            "property_debt",
        }
        missing = sorted(required - kinds)
        if missing:
            raise ValueError(f"property evidence sources missing: {', '.join(missing)}")
        if not {"property_title", "property_nav_appraisal"} & kinds:
            raise ValueError("property evidence requires dated title or appraisal evidence")
        source_ids = [source.source_id for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("property evidence source_id values must be unique")
        if self.unrestricted_cash != 0 and "property_cash" not in kinds:
            raise ValueError("non-zero property cash requires a source")
        if self.normalized_nwc_adjustment != 0 and "property_nwc" not in kinds:
            raise ValueError("non-zero property NWC adjustment requires a source")
        if (self.governed_nav_equity_floor is None) != (self.nav_floor_basis is None):
            raise ValueError("governed NAV floor and adjusted-equity basis are required together")
        if self.governed_nav_equity_floor is not None and "property_nav_appraisal" not in kinds:
            raise ValueError("governed NAV floor requires a dated property appraisal source")
        if any(
            source.observed_on > self.valuation_date
            or (source.published_on is not None and source.published_on > self.valuation_date)
            for source in self.sources
        ):
            raise ValueError("property sources cannot be observed or published after valuation")
        yield_sources = [
            source for source in self.sources if source.source_kind == "property_yield_snapshot"
        ]
        if not any(
            source.observed_on == self.yield_observed_on
            and (source.published_on or source.observed_on) == self.yield_published_on
            for source in yield_sources
        ):
            raise ValueError(
                "yield snapshot source dates must match the governed yield observation"
            )

        payload = self.model_dump(mode="json")
        if self.canonical_hash(payload) != self.content_sha256:
            raise ValueError("real-estate yield content_sha256 does not match RFC8785 payload")
        return self
