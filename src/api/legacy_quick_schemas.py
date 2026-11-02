"""Legacy quick-valuation and utility response schemas."""

from decimal import Decimal
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from src.api.business_type_mix import normalize_business_type_mix_fields
from src.api.legacy_schema_validation import validate_industry_field
from src.domain.models import ConfidenceLevel

JsonObject = Dict[str, object]


class QuickValuationRequest(BaseModel):
    """Simplified request for quick valuation estimate."""

    revenue: Decimal = Field(
        ..., ge=0, description="Annual revenue in EUR (0 allowed for pre-revenue startups)"
    )
    ebitda: Decimal = Field(..., description="Annual EBITDA in EUR")
    industry: str = Field(
        ..., min_length=1, max_length=100, description="Industry classification (flexible string)"
    )
    country_code: str = Field(..., pattern="^[A-Z]{2}$", description="2-letter ISO country code")
    registration_number: Optional[str] = Field(
        None, max_length=50, description="Generic company registration number (KBO/KVK)"
    )
    kbo_number: Optional[str] = Field(None, max_length=50, description="Belgian KBO/BCE number")
    kvk_number: Optional[str] = Field(None, max_length=50, description="Dutch KVK number")
    vat_number: Optional[str] = Field(None, max_length=50, description="VAT number")
    legal_form: Optional[str] = Field(None, max_length=100, description="Legal form")
    postal_code: Optional[str] = Field(None, max_length=20, description="Postal code")
    city: Optional[str] = Field(None, max_length=100, description="City location")

    business_type_id: Optional[str] = Field(
        None, max_length=100, description="Business type ID for enhanced intelligence"
    )
    business_type_mix: Optional[List[JsonObject]] = Field(
        None,
        min_length=1,
        max_length=20,
        description="Titan-normalized weighted business type mix.",
    )
    business_type_weights: Optional[JsonObject] = Field(
        None,
        description="Optional compact caller weights keyed by business_type_id.",
    )
    benchmark_contract: Optional[JsonObject] = Field(
        None,
        description="Resolved Upswitch Index benchmark contract required for valuation-grade multiples.",
    )
    multiples_metadata: Optional[JsonObject] = Field(
        None,
        description="Multiples provenance block; may contain benchmark_contract.",
    )
    allow_untrusted_multiples_fallback: bool = Field(
        False,
        description=(
            "Explicit opt-in to disclosed fallback multiples when no resolved "
            "Upswitch Index benchmark contract is available."
        ),
    )

    company_name: Optional[str] = Field(None, max_length=200)
    founding_year: Optional[int] = Field(None, ge=1900, le=2100)
    total_debt: Optional[Decimal] = Field(Decimal("0.0"), ge=0, description="Total debt in EUR")
    cash: Optional[Decimal] = Field(Decimal("0.0"), ge=0, description="Cash in EUR")

    @field_validator("industry")
    @classmethod
    def validate_industry(cls, v: str) -> str:
        """Validate and sanitize industry field."""
        return validate_industry_field(v)

    @model_validator(mode="after")
    def normalize_business_type_mix_contract(self) -> "QuickValuationRequest":
        primary, mix, weights = normalize_business_type_mix_fields(
            business_type_id=self.business_type_id,
            business_type_mix=self.business_type_mix,
            business_type_weights=self.business_type_weights,
        )
        if primary:
            self.business_type_id = primary
        if mix is not None:
            self.business_type_mix = mix
        if weights is not None:
            self.business_type_weights = weights
        return self


class QuickValuationResponse(BaseModel):
    """Simplified valuation response for quick estimates."""

    valuation_range_low: Decimal
    valuation_range_mid: Decimal
    valuation_range_high: Decimal
    recommended_asking_price: Decimal
    confidence: ConfidenceLevel
    confidence_score: int = Field(..., ge=0, le=100)
    methodology_used: str
    key_factors: List[str] = Field(default_factory=list, description="Key valuation factors")
    recommendations: List[str] = Field(
        default_factory=list, description="Valuation recommendations"
    )
    note: str = Field(
        default="This is a quick estimate. For a comprehensive valuation, please provide complete financial data."
    )
    benchmark_contract: Optional[JsonObject] = Field(
        None, description="Resolved Upswitch Index benchmark contract used for the quick valuation."
    )
    benchmark_provenance: Optional[JsonObject] = Field(
        None, description="Alias of benchmark_contract for report/source consumers."
    )
    benchmark_id: Optional[str] = None
    dataset_version_id: Optional[str] = None
    benchmark_country_code: Optional[str] = None
    benchmark_region_key: Optional[str] = None
    benchmark_tier: Optional[str] = None
    benchmark_walk_step: Optional[str] = None
    benchmark_sample_size: Optional[int] = None
    benchmark_confidence_band: Optional[str] = None
    benchmark_source_mix: Optional[JsonObject] = None
    benchmark_evidence_summary: Optional[object] = None
    benchmark_published_at: Optional[str] = None
    benchmark_methodology_version: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response schema."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    timestamp: str = Field(..., description="Current timestamp")
    uptime_seconds: Optional[Decimal] = None
    adapters_status: Optional[Dict[str, str]] = None
