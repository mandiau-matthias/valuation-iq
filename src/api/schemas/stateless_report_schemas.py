"""Report-generation schemas for stateless ValuationIQ outputs."""

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from src.api.schemas.stateless_common import (
    JsonObject,
    YearDataStateless,
    _FiniteDecimalMixin,
)
from src.api.schemas.stateless_response_schemas import CalculateResponse
from src.api.schemas.valuation_assurance_security import ValuationAssuranceEnvelopeV2
from src.api.schemas.valuation_contracts import (
    BenchmarkSnapshotReference,
    ClassificationResolutionSnapshot,
    GovernedReportReviewDecision,
    NormalizationAdjustmentSnapshot,
    ReportAssuranceContract,
    ReportContentProvenanceSnapshot,
    ReportSourceCitation,
    Sha256Hex,
    SnapshotReference,
)
from src.domain.method_keys import normalize_selected_method_key
from src.utils.fiscal_year import get_max_confirmable_year

_RUN_METHODOLOGY_SELECTED_METHOD = {
    "HYBRID": "upswitch_adaptive",
    "MULTIPLES": "upswitch_adaptive",
    "ASSET_BASED": "adjusted_nav",
    "WEIGHTED_SYNTHESIS": "custom_weighted",
}


class ReportBranding(BaseModel):
    """Accountant/advisor branding for report."""

    firm_name: Optional[str] = None
    logo_url: Optional[str] = None
    logo_data_uri: Optional[str] = Field(None, max_length=700_000)
    logo_sha256: Optional[str] = Field(None, pattern=r"^[0-9a-f]{64}$")
    logo_mime_type: Optional[Literal["image/png", "image/jpeg", "image/webp"]] = None
    logo_width_px: Optional[int] = Field(None, ge=16, le=4096)
    logo_height_px: Optional[int] = Field(None, ge=16, le=4096)
    website: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    # Report customization (parity with Titan metadata)
    show_cover_price: Optional[bool] = True
    valuation_goal: Optional[str] = None
    custom_disclaimer: Optional[str] = None
    # Pass-5: advisor-configured asking-price buffer override.
    # Fraction in [0, 0.25] - e.g. 0.10 for 10%. When None, the engine uses
    # the confidence-aware default (5-10%).
    asking_price_buffer_pct: Optional[Decimal] = Field(
        None,
        ge=Decimal("0.0"),
        le=Decimal("0.25"),
        description=(
            "Firm-level asking-price buffer override as a fraction. "
            "Replaces the engine's confidence-aware default markup."
        ),
    )

    @model_validator(mode="after")
    def validate_immutable_logo_asset(self) -> "ReportBranding":
        from src.services.reports.report_branding_validation import (
            validate_immutable_logo_asset,
        )

        return validate_immutable_logo_asset(self)


class ReportEngagementScope(BaseModel):
    """Professional scope facts displayed verbatim in a valuation memorandum."""

    purpose: str = Field(..., min_length=3, max_length=300)
    intended_users: List[str] = Field(..., min_length=1, max_length=10)
    subject_interest: str = Field(..., min_length=3, max_length=300)
    ownership_percentage: Decimal = Field(..., gt=0, le=Decimal("100"))
    basis_of_value: str = Field(..., min_length=3, max_length=200)
    premise_of_value: str = Field(..., min_length=3, max_length=300)
    valuation_date: str = Field(..., min_length=10, max_length=10)
    evidence_date: str = Field(..., min_length=10, max_length=10)
    source_periods: List[str] = Field(..., min_length=1, max_length=12)
    excluded_periods: List[str] = Field(default_factory=list, max_length=12)
    scope_limitations: List[str] = Field(default_factory=list, max_length=20)
    information_reliance: str = Field(..., min_length=20, max_length=2000)
    conflict_disclosures: List[str] = Field(..., min_length=1, max_length=20)
    issue_date: Optional[str] = Field(None, min_length=10, max_length=10)
    legal_rights: Optional[str] = Field(None, min_length=3, max_length=1000)
    investigations_performed: List[str] = Field(default_factory=list, max_length=30)
    investigations_not_performed: List[str] = Field(default_factory=list, max_length=30)
    assumptions: List[str] = Field(default_factory=list, max_length=30)
    special_assumptions: List[str] = Field(default_factory=list, max_length=30)
    material_uncertainty: Optional[str] = Field(None, min_length=3, max_length=2000)
    material_esg_factors: List[str] = Field(default_factory=list, max_length=30)
    company_business_model: Optional[str] = Field(None, min_length=3, max_length=2000)
    products_services: List[str] = Field(default_factory=list, max_length=30)
    customer_concentration: Optional[str] = Field(None, min_length=3, max_length=2000)
    supplier_dependencies: List[str] = Field(default_factory=list, max_length=30)
    key_person_dependencies: List[str] = Field(default_factory=list, max_length=30)
    market_sector_overview: Optional[str] = Field(None, min_length=3, max_length=3000)
    competition_overview: Optional[str] = Field(None, min_length=3, max_length=2000)
    material_business_risks: List[str] = Field(default_factory=list, max_length=30)
    principal_value_drivers: List[str] = Field(default_factory=list, max_length=20)
    principal_caveats: List[str] = Field(default_factory=list, max_length=20)
    sustainable_earnings_commentary: Optional[str] = Field(None, min_length=3, max_length=2000)


class ReportRegistrySnapshot(BaseModel):
    """Exact non-economic registry snapshot pinned to the valuation run."""

    source: Literal["KBO"] = "KBO"
    data_version: str = Field(..., min_length=1, max_length=160)
    snapshot_date: str = Field(..., min_length=10, max_length=10)
    archive_sha256: str = Field(..., pattern=r"^[0-9a-f]{64}$")


class UnweightedValuationLens(_FiniteDecimalMixin, BaseModel):
    """A cross-check valuation lens shown at 0% weight. DISCLOSURE ONLY.

    Some methods answer a different question than the weighted synthesis — a
    revenue/barema rule of thumb, for instance, prices goodwill and lands on
    EQUITY, not enterprise value. Blending such a lens into the weighted total
    would add together incompatible value concepts, but hiding it denies the
    reader a sanity check they would otherwise do themselves.

    There is deliberately NO settable weight: no instance can carry a non-zero
    weight, so this row is structurally unable to reach a priced total. It is
    never merged into ``synthesis_contributions`` (the displayed low/high band
    is derived from those rows by min/max with no weight filter, so a
    disclosure placed there would silently move the client-visible band), and
    never enters the aggregation dict that feeds the legacy pricing path.
    """

    lens_id: str = Field(..., pattern=r"^[a-z][a-z0-9_]{2,63}$")
    lens_family: Optional[str] = Field(
        None,
        pattern=r"^[a-z][a-z0-9_]{2,63}$",
        description=(
            "Groups several CASES of one lens (e.g. two coefficients of the "
            "same rule of thumb) so counts describe lenses, not rows. "
            "Defaults to lens_id."
        ),
    )
    label: str = Field(..., min_length=3, max_length=140)
    value: Decimal = Field(..., ge=0, le=Decimal("1000000000"))
    value_basis: Literal["equity_value", "enterprise_value"]
    computation_note: str = Field(..., min_length=20, max_length=700)
    zero_weight_reason: str = Field(..., min_length=20, max_length=700)
    weight_pct: Literal[0] = 0


class GenerateReportRequest(BaseModel):
    """
    Report generation request - receives complete valuation result.

    Titan sends the calculation result and company info.
    ValuationIQ generates HTML and PDF.
    """

    # === Valuation Result (from CalculateResponse) ===
    valuation_result: CalculateResponse = Field(
        ..., description="Complete valuation result from /calculate"
    )

    # === Company Info for Report ===
    company_name: str
    industry: str
    country_code: str
    founding_year: int
    number_of_employees: Optional[int] = None
    registration_number: Optional[str] = Field(None, max_length=50)
    nace_code: Optional[str] = Field(None, max_length=20)
    legal_form: Optional[str] = Field(None, max_length=100)
    city: Optional[str] = Field(None, max_length=100)
    incorporated_on: Optional[str] = Field(None, max_length=20)
    business_type_label: Optional[str] = Field(None, max_length=100)
    report_id: Optional[str] = Field(None, max_length=100)
    valuation_assurance_envelope: Optional[ValuationAssuranceEnvelopeV2] = Field(
        None,
        description=(
            "Titan-signed, audience-specific assurance authority. A sealed calculation "
            "without this envelope remains canonical_uncertified."
        ),
    )
    valuation_assurance_envelope_id: Optional[str] = Field(None, min_length=1, max_length=100)
    assurance_audience: Optional[Literal["owner", "advisor", "buyer"]] = None
    assurance_observation_ids: List[str] = Field(default_factory=list)

    # === Calculation-bound financial history for the rendered dossier ===
    # `/calculate` intentionally returns compact financial metrics.  A full
    # client report may also need the source-reconciled actual-year schedule
    # that was supplied to the calculation.  Keep it explicit and typed here;
    # do not reconstruct prior-year figures from valuation-timeline values.
    current_year_data: Optional[YearDataStateless] = None
    historical_years_data: List[YearDataStateless] = Field(default_factory=list)

    # === Report Options ===
    include_pdf: bool = Field(True, description="Generate PDF report")
    include_html: bool = Field(True, description="Generate HTML report")
    include_report_data: bool = Field(True, description="Include structured JSON for React")
    publication_intent: Literal["draft", "final"] = Field(
        "draft",
        description=(
            "Drafts may render with review restrictions. Final generation fails closed "
            "unless the immutable report release contract is publishable."
        ),
    )
    report_scope: Literal[
        "standard", "client_indicative", "advisor_memorandum", "automated_indicative"
    ] = Field(
        "standard",
        description=(
            "Release policy. client_indicative authorizes a limited-scope client "
            "handoff while explicitly prohibiting customer persistence and T4 use."
        ),
    )
    engagement_scope: Optional[ReportEngagementScope] = None
    registry_snapshot: Optional[ReportRegistrySnapshot] = None
    report_assurance_level: Optional[Literal["indicative", "advisor_approved"]] = None

    # === Branding ===
    branding: Optional[ReportBranding] = Field(None, description="Accountant co-branding")

    # === Language ===
    language: str = Field(default="nl", description="Report language: 'nl', 'en', 'fr'")
    reporting_year: Optional[int] = Field(
        default=None,
        description="Closed fiscal year that the report refers to. When omitted, the current date is used.",
    )
    valuation_date: Optional[str] = Field(
        None,
        max_length=20,
        description="ISO valuation date; distinct from the financial reference date.",
    )
    financial_reference_date: Optional[str] = Field(None, max_length=20)

    # === Omni-Calc: Which method to render ===
    selected_method: Optional[str] = Field(
        default=None,
        description="Selected valuation method key (e.g. 'dcf', 'sde_multiple'). When set, report renders only this method's values.",
    )
    headline_value_basis: Literal["equity_value", "enterprise_value"] = Field(
        default="equity_value",
        description="Value basis used for the cover and executive conclusion.",
    )
    show_asking_price: bool = Field(
        default=True,
        description="Whether the report may present the engine's recommended asking price.",
    )
    equity_bridge_is_illustrative: bool = Field(
        default=False,
        description=(
            "Marks the EV-to-equity bridge as illustrative because one or more "
            "cash, debt-like, lease or completion-account inputs remain unverified."
        ),
    )
    include_ebitda_normalization_page: bool = True
    include_transaction_readiness_section: bool = True
    include_business_growth_maturity_section: bool = True
    include_growth_multiple_sensitivity: bool = True
    include_sde_cross_check: bool = True
    include_attestation_page: bool = True
    include_generic_next_steps: bool = True
    fallback_reasonableness_note: Optional[str] = Field(None, max_length=1000)
    additional_risk_factors: List[str] = Field(default_factory=list, max_length=10)
    source_references: List[JsonObject] = Field(default_factory=list, max_length=20)
    unweighted_valuation_lenses: List[UnweightedValuationLens] = Field(
        default_factory=list,
        max_length=6,
        description=(
            "DISCLOSURE-ONLY cross-check lenses rendered at 0% weight. Never "
            "read by pricing, never merged into synthesis_contributions, never "
            "used to derive a band, never in the aggregation dict."
        ),
    )
    client_presentation_method_label: Optional[str] = Field(
        None,
        max_length=160,
        description=(
            "Client-facing, non-economic method label. It may improve advisor branding "
            "but cannot change the selected method, values, source lineage or disclosures."
        ),
    )
    client_presentation_methodology_statement: Optional[str] = Field(
        None,
        max_length=2500,
        description=(
            "Client-facing, non-economic methodology explanation. The calculation and "
            "benchmark provenance remain immutable."
        ),
    )
    suppress_engine_product_name: bool = Field(
        False,
        description=(
            "Suppresses internal engine product naming in client-facing HTML/PDF. "
            "The immutable report manifest and internal audit logs retain engine provenance."
        ),
    )
    show_weighted_synthesis_range_on_cover: bool = Field(
        False,
        description=(
            "Show the weighted low/high conclusion on the cover even when method "
            "divergence is separately disclosed. The range must already be committed "
            "to the immutable calculation response."
        ),
    )

    @field_validator("reporting_year")
    @classmethod
    def clamp_reporting_year_to_filing_year(cls, value: Optional[int]) -> Optional[int]:
        if value is None:
            return value
        return min(value, get_max_confirmable_year())

    @model_validator(mode="before")
    @classmethod
    def reject_run_relabelling_before_field_normalization(cls, value: object) -> object:
        """Catch raw year overrides before the legacy filing-year clamp runs."""
        if not isinstance(value, Mapping):
            return value
        result = _contract_field(value, "valuation_result")
        run = _contract_field(result, "valuation_run")
        if run is None:
            return value
        metrics = _contract_field(result, "financial_metrics")
        enterprise_only = (
            _contract_field(run, "value_basis") == "enterprise_value"
            and _contract_field(metrics, "equity_status") == "unavailable_incomplete_bridge"
        )
        if enterprise_only:
            if value.get("headline_value_basis", "enterprise_value") != "enterprise_value":
                raise ValueError("equity headline is unavailable in the sealed enterprise-only run")
            value = dict(value)
            value.update(
                {
                    "headline_value_basis": "enterprise_value",
                    "show_asking_price": False,
                    "equity_bridge_is_illustrative": False,
                }
            )
        reporting_year, valuation_date, financial_reference_date, selected_method = (
            _canonical_run_report_binding(run)
        )
        _require_raw_match(value, "reporting_year", reporting_year)
        _require_raw_match(value, "valuation_date", valuation_date)
        _require_raw_match(
            value,
            "financial_reference_date",
            financial_reference_date,
        )
        raw_selected_method = value.get("selected_method")
        if (
            raw_selected_method is not None
            and normalize_selected_method_key(raw_selected_method) != selected_method
        ):
            raise ValueError("report selected_method does not match valuation_run")
        return value

    @model_validator(mode="after")
    def apply_client_indicative_render_policy(self) -> "GenerateReportRequest":
        if self.report_scope == "automated_indicative":
            self.show_asking_price = False
            self.include_attestation_page = False
            self.show_weighted_synthesis_range_on_cover = True
            return self
        if self.report_scope != "client_indicative":
            return self
        if self.publication_intent != "final":
            raise ValueError("client_indicative report scope requires publication_intent='final'")
        if not (self.client_presentation_method_label or "").strip():
            raise ValueError(
                "client_indicative report scope requires a client presentation method label"
            )
        # Scope policy, not caller preference: a paid indicative handoff shows a
        # range and its limitations, never an asking price, legal attestation,
        # or internal engine product name.
        self.include_pdf = True
        self.include_html = True
        self.include_report_data = True
        self.show_asking_price = False
        self.equity_bridge_is_illustrative = True
        self.include_attestation_page = False
        self.suppress_engine_product_name = True
        self.show_weighted_synthesis_range_on_cover = True
        return self

    @model_validator(mode="after")
    def bind_company_metadata_to_valuation_run(self) -> "GenerateReportRequest":
        """Prevent a valid run from being relabelled at report time."""
        run = self.valuation_result.valuation_run
        if run is None:
            return self
        if run.valuation_id is not None and run.valuation_id != self.valuation_result.valuation_id:
            raise ValueError("report valuation_id does not match valuation_run")
        if run.company_name is not None and _normalized_identity(
            run.company_name
        ) != _normalized_identity(self.company_name):
            raise ValueError("report company_name does not match valuation_run")
        if run.country_code is not None and run.country_code.upper() != self.country_code.upper():
            raise ValueError("report country_code does not match valuation_run")
        profile = run.company_profile_snapshot
        _require_profile_match("industry", self.industry, profile.industry)
        _require_profile_match("founding_year", self.founding_year, profile.founding_year)
        _require_profile_match(
            "number_of_employees",
            self.number_of_employees,
            profile.number_of_employees,
        )
        _require_profile_match(
            "registration_number",
            self.registration_number,
            profile.registration_number,
        )
        _require_profile_match("nace_code", self.nace_code, profile.nace_code)
        _require_profile_match("legal_form", self.legal_form, profile.legal_form)
        _require_profile_match("city", self.city, profile.city)
        _require_profile_match(
            "incorporated_on",
            self.incorporated_on,
            profile.incorporated_on,
        )
        _require_profile_match(
            "business_type_label",
            self.business_type_label,
            profile.business_type_label,
        )
        reporting_year, valuation_date, financial_reference_date, selected_method = (
            _canonical_run_report_binding(run)
        )
        if self.reporting_year is not None and self.reporting_year != reporting_year:
            raise ValueError("report reporting_year does not match valuation_run")
        if self.valuation_date is not None and self.valuation_date != valuation_date:
            raise ValueError("report valuation_date does not match valuation_run")
        if (
            self.financial_reference_date is not None
            and self.financial_reference_date != financial_reference_date
        ):
            raise ValueError("report financial_reference_date does not match valuation_run")
        if (
            self.selected_method is not None
            and normalize_selected_method_key(self.selected_method) != selected_method
        ):
            raise ValueError("report selected_method does not match valuation_run")
        self.reporting_year = reporting_year
        self.valuation_date = valuation_date
        self.financial_reference_date = financial_reference_date
        self.selected_method = selected_method
        self.industry = profile.industry
        self.founding_year = profile.founding_year
        self.number_of_employees = profile.number_of_employees
        self.registration_number = profile.registration_number
        self.nace_code = profile.nace_code
        self.legal_form = profile.legal_form
        self.city = profile.city
        self.incorporated_on = profile.incorporated_on
        self.business_type_label = profile.business_type_label
        if self.source_references:
            raise ValueError(
                "canonical report source_references must be committed in valuation_run; "
                "report-time source overlays are not permitted"
            )
        if self.additional_risk_factors:
            raise ValueError(
                "canonical report qualifications must be committed in valuation_run; "
                "report-time risk overlays are not permitted"
            )
        return self

    @model_validator(mode="after")
    def bind_rendered_financial_history_to_calculation(self) -> "GenerateReportRequest":
        from src.services.reports.sealed_financial_history_projection import (
            bind_report_financial_history,
        )

        return bind_report_financial_history(self)

    @model_validator(mode="after")
    def verify_titan_assurance_authority(self) -> "GenerateReportRequest":
        envelope = self.valuation_assurance_envelope
        if envelope is None:
            if (
                self.valuation_assurance_envelope_id is not None
                or self.assurance_audience is not None
                or self.assurance_observation_ids
            ):
                raise ValueError(
                    "assurance id/audience/observations require valuation_assurance_envelope"
                )
            return self

        from src.api.schemas.valuation_assurance_security import (
            bind_valuation_assurance_to_report,
            parse_titan_valuation_assurance_public_key_registry,
            verify_valuation_assurance_envelope,
        )
        from src.api.schemas.valuation_contracts import ValuationRunV2
        from src.config import get_settings

        run = self.valuation_result.valuation_run
        if not isinstance(run, ValuationRunV2):
            raise ValueError("valuation assurance requires valuation_run.v2")
        if not self.report_id:
            raise ValueError("valuation assurance requires an exact report_id")
        if self.valuation_assurance_envelope_id is None:
            raise ValueError("valuation assurance requires valuation_assurance_envelope_id")
        if self.assurance_audience is None:
            raise ValueError("valuation assurance requires an explicit assurance_audience")
        if not self.assurance_observation_ids:
            raise ValueError("valuation assurance requires exact assurance_observation_ids")
        if not run.currency:
            raise ValueError("valuation assurance requires sealed valuation_run currency")
        if self.assurance_observation_ids != sorted(set(self.assurance_observation_ids)):
            raise ValueError("assurance_observation_ids must be sorted and unique")

        registry = parse_titan_valuation_assurance_public_key_registry(
            get_settings().titan_valuation_assurance_public_key_registry_json
        )
        verify_valuation_assurance_envelope(envelope, registry=registry)
        bind_valuation_assurance_to_report(
            envelope,
            run=run,
            report_id=self.report_id,
            audience=self.assurance_audience,
            observation_ids=self.assurance_observation_ids,
            headline_value_basis=self.headline_value_basis,
            headline_currency=run.currency,
            headline_low=(
                self.valuation_result.enterprise_value_low
                if self.headline_value_basis == "enterprise_value"
                else self.valuation_result.equity_value_low
            ),
            headline_mid=(
                self.valuation_result.enterprise_value_mid
                if self.headline_value_basis == "enterprise_value"
                else self.valuation_result.equity_value_mid
            ),
            headline_high=(
                self.valuation_result.enterprise_value_high
                if self.headline_value_basis == "enterprise_value"
                else self.valuation_result.equity_value_high
            ),
        )
        return self


def _normalized_identity(value: str) -> str:
    return " ".join(value.casefold().split())


def _require_profile_match(field: str, supplied: object, committed: object) -> None:
    if supplied is None:
        return
    if isinstance(supplied, str) and isinstance(committed, str):
        matches = _normalized_identity(supplied) == _normalized_identity(committed)
    else:
        matches = supplied == committed
    if not matches:
        raise ValueError(f"report {field} does not match valuation_run company profile")


def _contract_field(value: object, field: str) -> object:
    if isinstance(value, Mapping):
        return value.get(field)
    return getattr(value, field, None)


def _canonical_run_report_binding(run: object) -> tuple[int, str, str, str]:
    fiscal_effective_date = _canonical_iso_date(
        _contract_field(run, "fiscal_effective_date"),
        "fiscal_effective_date",
    )
    valuation_lens_date = _canonical_iso_date(
        _contract_field(run, "valuation_lens_date"),
        "valuation_lens_date",
    )
    methodology_used = str(_contract_field(run, "methodology_used") or "").strip()
    if not methodology_used:
        raise ValueError("valuation_run methodology_used is required for report binding")
    selected_method = _RUN_METHODOLOGY_SELECTED_METHOD.get(
        methodology_used.upper(),
        normalize_selected_method_key(methodology_used),
    )
    if not selected_method:
        raise ValueError("valuation_run methodology_used cannot bind selected_method")
    return (
        date.fromisoformat(fiscal_effective_date).year,
        valuation_lens_date,
        fiscal_effective_date,
        selected_method,
    )


def _canonical_iso_date(value: object, field: str) -> str:
    raw = str(value or "").strip()
    try:
        parsed = date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(
            f"valuation_run {field} must be a canonical ISO date for report binding"
        ) from exc
    if parsed.isoformat() != raw:
        raise ValueError(f"valuation_run {field} must be a canonical ISO date for report binding")
    return raw


def _require_raw_match(
    value: Mapping[object, object],
    field: str,
    canonical: object,
) -> None:
    provided = value.get(field)
    if provided is not None and provided != canonical:
        raise ValueError(f"report {field} does not match valuation_run")


class GenerateReportResponse(BaseModel):
    """
    Report generation result.

    Returns HTML, PDF, and structured data for frontend rendering.
    """

    # === Identification ===
    valuation_id: str
    generated_at: str = Field(..., description="ISO 8601 timestamp")

    # === Report Content ===
    html_report: Optional[str] = Field(None, description="Complete HTML report")
    pdf_base64: Optional[str] = Field(None, description="Base64-encoded PDF")
    report_data: Optional[JsonObject] = Field(
        None, description="Structured JSON for React template"
    )

    # === Generation Metadata ===
    generation_time_ms: int = Field(..., description="Time to generate in milliseconds")
    template_version: str = Field(default="2.0.0", description="Template version used")
    report_manifest: Optional["ReportManifest"] = None
    generation_warnings: Optional[List[str]] = Field(
        None,
        description="Warnings about partial failures during generation (e.g. PDF skipped)",
    )


class ReportArtifactDigest(BaseModel):
    artifact: Literal["html", "pdf", "report_payload"]
    sha256: Sha256Hex
    bytes: int = Field(..., ge=0)


class ReportManifest(BaseModel):
    """Hash-locked T4-506 contract for one rendered report generation."""

    schema_version: Literal["report_manifest.v1"] = "report_manifest.v1"
    integrity_version: Literal["report_manifest_integrity.v1"] = "report_manifest_integrity.v1"
    manifest_id: str
    manifest_hash: Sha256Hex
    artifact_envelope_hash: Sha256Hex
    report_id: str
    valuation_id: str
    valuation_run_id: str
    valuation_run_hash: Sha256Hex
    generated_at: str
    company_snapshot: SnapshotReference
    uploaded_data_snapshot: Optional[SnapshotReference] = None
    uploaded_data_snapshot_status: Literal["priced", "attested_non_priced", "not_supplied"]
    classification_resolution: ClassificationResolutionSnapshot
    benchmark_snapshot_references: List[BenchmarkSnapshotReference] = Field(default_factory=list)
    source_citations: List[ReportSourceCitation] = Field(default_factory=list)
    model_versions: JsonObject
    normalization_adjustments: List[NormalizationAdjustmentSnapshot] = Field(default_factory=list)
    normalization_adjustments_hash: Sha256Hex
    report_review_decisions: List[GovernedReportReviewDecision] = Field(default_factory=list)
    content_provenance: ReportContentProvenanceSnapshot
    assurance: ReportAssuranceContract
    valuation_assurance_envelope: Optional[ValuationAssuranceEnvelopeV2] = None
    confidence_level: Literal["LOW", "MEDIUM", "HIGH"]
    confidence_score: int = Field(..., ge=0, le=100)
    generation_status: Literal[
        "draft_auto",
        "draft_review_required",
        "diagnostic_preview",
        "client_indicative",
        "automated_indicative",
    ]
    publication_status: Literal["publishable", "review_required", "blocked"]
    reviewer_requirement: Literal["none", "advisor_review", "classification_or_benchmark_review"]
    review_points: List[str] = Field(default_factory=list)
    final_requested: bool
    report_scope: Literal["standard", "client_indicative", "automated_indicative"] = "standard"
    scope_prohibits_customer_persistence: bool = False
    scope_prohibits_t4: bool = False
    template_version: str
    template_bundle_hash: Sha256Hex
    artifact_digests: List[ReportArtifactDigest] = Field(default_factory=list)
    generation_warnings: List[str] = Field(default_factory=list)
    artifact_status: Literal["pending", "complete", "incomplete"] = "pending"

    @model_validator(mode="after")
    def bind_uploaded_snapshot_status(self) -> "ReportManifest":
        snapshot = self.uploaded_data_snapshot
        status = self.uploaded_data_snapshot_status
        if (snapshot is None) != (status == "not_supplied"):
            raise ValueError(
                "uploaded_data_snapshot and uploaded_data_snapshot_status are inconsistent"
            )
        if status == "attested_non_priced" and snapshot is not None:
            if (
                snapshot.source_kind != "titan_annual_financials"
                or snapshot.trust_class is None
                or snapshot.evidence_tier is None
            ):
                raise ValueError(
                    "attested_non_priced snapshot requires Titan source, trust class, and tier"
                )
        prohibited = self.report_scope == "client_indicative"
        if self.scope_prohibits_customer_persistence != prohibited:
            raise ValueError("report scope/customer-persistence policy is inconsistent")
        if self.scope_prohibits_t4 != (
            self.report_scope in {"client_indicative", "automated_indicative"}
        ):
            raise ValueError("report scope/T4 policy is inconsistent")
        return self

    @model_validator(mode="after")
    def verify_manifest_integrity(self) -> "ReportManifest":
        from src.services.reports.stateless_report_manifest import (
            verify_report_manifest_integrity,
        )

        verify_report_manifest_integrity(self)
        return self


GenerateReportResponse.model_rebuild()
