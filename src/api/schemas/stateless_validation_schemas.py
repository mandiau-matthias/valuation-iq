"""Validation endpoint schemas for stateless ValuationIQ requests."""

from decimal import Decimal
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from src.api.business_type_mix import normalize_business_type_mix_fields
from src.api.schemas.stateless_common import (
    BusinessTypeCalibration,
    ExternalMarketReferenceContract,
    JsonObject,
    YearDataStateless,
)
from src.config.countries import normalize_country_code
from src.config.country_packs import country_pack
from src.utils.fiscal_year import get_max_confirmable_year


class ValidateRequest(BaseModel):
    """
    Validation request for triage/dry-run checking.

    Used before final calculation to check data completeness and quality.
    """

    # === Financial Data ===
    current_year: YearDataStateless
    historical_years: List[YearDataStateless] = Field(default=[])

    # === Context ===
    industry: str
    country_code: str = Field(..., pattern=r"^[A-Z]{2}$")
    business_type_id: Optional[str] = None
    business_type_mix: Optional[List[Dict[str, object]]] = Field(
        default=None, min_length=1, max_length=20
    )
    business_type_weights: Optional[JsonObject] = Field(default=None)
    business_type_segments: Optional[List[JsonObject]] = Field(default=None)

    # Optional: when ASSET_BASED, zero turnover is valid without EV/Revenue multiples.
    methodology: Optional[Literal["HYBRID", "DCF", "MULTIPLES", "ASSET_BASED"]] = Field(
        default=None,
        description="If ASSET_BASED, validation allows €0 turnover (holdings / balance-sheet-led cases).",
    )

    # === Business Type Calibration (for benchmarking) ===
    business_type_calibration: Optional[BusinessTypeCalibration] = None
    allow_untrusted_multiples_fallback: bool = Field(
        False,
        description=(
            "Advisor-only consent to use a prominently disclosed external market "
            "fallback when no resolved Upswitch Index contract is available."
        ),
    )
    untrusted_multiples_fallback_reason: Optional[str] = Field(
        None,
        max_length=2000,
        description="Required written advisor rationale when fallback consent is enabled.",
    )
    external_market_reference_contract: Optional[ExternalMarketReferenceContract] = None

    @field_validator("current_year")
    @classmethod
    def validate_current_year_not_in_future(cls, value: YearDataStateless) -> YearDataStateless:
        max_confirmable_year = get_max_confirmable_year()
        if value.year > max_confirmable_year:
            raise ValueError(
                f"current_year.year ({value.year}) cannot be later than the previous calendar year ({max_confirmable_year})"
            )
        return value

    @field_validator("country_code", mode="before")
    @classmethod
    def validate_supported_country_code(cls, value: object) -> str:
        code = normalize_country_code(value)
        if country_pack(code) is None:
            raise ValueError(f"no CountryPack configured for {code!r}")
        return code

    @model_validator(mode="after")
    def normalize_business_type_mix_contract(self) -> "ValidateRequest":
        primary, mix, weights = normalize_business_type_mix_fields(
            business_type_id=self.business_type_id,
            business_type_mix=self.business_type_mix,
            business_type_segments=self.business_type_segments,
            business_type_weights=self.business_type_weights,
        )
        if primary:
            self.business_type_id = primary
        if mix is not None:
            self.business_type_mix = mix
        if weights is not None:
            self.business_type_weights = weights
        if (
            self.allow_untrusted_multiples_fallback
            and not (self.untrusted_multiples_fallback_reason or "").strip()
        ):
            raise ValueError(
                "untrusted_multiples_fallback_reason is required when "
                "allow_untrusted_multiples_fallback=true"
            )
        if self.external_market_reference_contract is not None:
            if self.allow_untrusted_multiples_fallback:
                raise ValueError(
                    "external_market_reference_contract cannot be combined with "
                    "allow_untrusted_multiples_fallback=true"
                )
            if self.business_type_calibration is None:
                raise ValueError(
                    "external_market_reference_contract requires business_type_calibration"
                )
            contract = self.external_market_reference_contract
            if contract.country_code != self.country_code:
                raise ValueError("external market reference country_code must match request")
            if contract.business_type_id != self.business_type_calibration.business_type_id:
                raise ValueError(
                    "external market reference business_type_id must match calibration"
                )
            if self.business_type_calibration.calibration_source != (
                "GOVERNED_EXTERNAL_MARKET_REFERENCE"
            ):
                raise ValueError(
                    "external_market_reference_contract requires "
                    "GOVERNED_EXTERNAL_MARKET_REFERENCE calibration"
                )
        return self


class ValidationWarning(BaseModel):
    """A single validation warning."""

    field: str = Field(..., description="Field with the issue")
    code: str = Field(..., description="Warning code for programmatic handling")
    message: str = Field(..., description="Human-readable message")
    severity: str = Field(..., description="Severity: 'info', 'warning', 'error'")
    suggestion: Optional[str] = Field(None, description="Suggested fix")


class ValidateResponse(BaseModel):
    """
    Validation result from triage/dry-run.

    Tells Titan what's missing or problematic without performing full calculation.
    """

    # === Overall Status ===
    status: str = Field(..., description="VALID, WARNINGS, INVALID")
    ready_for_calculation: bool = Field(..., description="Whether calculation can proceed")

    # === Warnings ===
    warnings: List[ValidationWarning] = Field(default=[])

    # === Quick Estimate (if calculable) ===
    estimated_valuation_range: Optional[Dict[str, Decimal]] = Field(
        None, description="Quick estimate: {low, mid, high}"
    )
    estimated_multiple: Optional[Decimal] = None

    # === Benchmark Comparison ===
    benchmark_comparisons: Optional[JsonObject] = Field(
        None, description="How company compares to industry benchmarks"
    )

    # === Missing Fields ===
    missing_required_fields: List[str] = Field(default=[])
    missing_optional_fields: List[str] = Field(default=[])

    # === Data Quality Score ===
    data_quality_score: int = Field(..., ge=0, le=100)
