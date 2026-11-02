"""Immutable contracts for the publishable valuation-memorandum render path."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from src.api.schemas.stateless_report_schemas import GenerateReportRequest
from src.api.schemas.valuation_contracts import ValuationRunV2
from src.services.reports.report_design_manifest import build_report_design_manifest
from src.services.reports.stateless_valuation_run import canonical_hash


class ReportRenderSnapshotV1(BaseModel):
    """One sealed, report-facing projection of a canonical valuation run.

    The snapshot is the sole input accepted by the publishable PDF endpoint.
    Its hash is verified against the raw JSON payload before Pydantic performs
    Decimal coercion, keeping the commitment byte-compatible with Titan.
    """

    schema_version: Literal["report_render_snapshot.v1"]
    report_id: str = Field(..., min_length=1, max_length=100)
    workspace_id: str = Field(..., min_length=1, max_length=100)
    artifact_kind: Literal["valuation_memorandum"] = "valuation_memorandum"
    assurance_level: Literal["indicative", "advisor_approved"]
    lifecycle_status: Literal["active"] = "active"
    locale: Literal["nl", "fr", "en"]
    template_contract_version: Literal["ma_valuation_memorandum.v2"] = (
        "ma_valuation_memorandum.v2"
    )

    valuation_run_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    evidence_bundle_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    edited_input_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    normalization_decisions_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    benchmark_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    method_manifest_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    advisor_judgment_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    branding_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    publication_contract_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    registry_snapshot_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")

    report_request: GenerateReportRequest
    snapshot_sha256: str = Field(..., pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="before")
    @classmethod
    def verify_raw_snapshot_commitment(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        supplied = str(value.get("snapshot_sha256") or "").lower()
        commitment = {
            key: item for key, item in value.items() if key != "snapshot_sha256"
        }
        if canonical_hash(commitment) != supplied:
            raise ValueError(
                "report render snapshot SHA-256 does not match its payload"
            )
        request = value.get("report_request")
        if isinstance(request, dict):
            publication_version = (
                "report_publication_contract.v2"
                if value.get("schema_version") == "report_render_snapshot.v2"
                else "report_publication_contract.v1"
            )
            publication_facts = {
                "schema_version": publication_version,
                "engagement_scope": request.get("engagement_scope"),
                "registry_snapshot": request.get("registry_snapshot"),
            }
            if publication_version == "report_publication_contract.v2":
                publication_facts["professional_review"] = value.get(
                    "professional_review"
                )
            if (
                canonical_hash(publication_facts)
                != str(value.get("publication_contract_hash") or "").lower()
            ):
                raise ValueError(
                    "publication_contract_hash does not match the report-facing facts"
                )
            if (
                canonical_hash(request.get("branding"))
                != str(value.get("branding_hash") or "").lower()
            ):
                raise ValueError(
                    "branding_hash does not match the report-facing branding"
                )
        return value

    @model_validator(mode="after")
    def enforce_publishable_memorandum_contract(self) -> "ReportRenderSnapshotV1":
        request = self.report_request
        run = request.valuation_result.valuation_run
        if not isinstance(run, ValuationRunV2):
            raise ValueError("publishable rendering requires valuation_run.v2")
        if run.run_hash != self.valuation_run_hash:
            raise ValueError("valuation_run_hash does not match valuation_run.v2")
        if run.input_hash != self.edited_input_hash:
            raise ValueError("edited_input_hash does not match valuation_run.v2")
        if run.benchmark_hash != self.benchmark_hash:
            raise ValueError("benchmark_hash does not match valuation_run.v2")
        if run.normalization_adjustments_hash != self.normalization_decisions_hash:
            raise ValueError(
                "normalization_decisions_hash does not match valuation_run.v2"
            )
        if run.accounting_evidence_bundle_hash != self.evidence_bundle_hash:
            raise ValueError("evidence_bundle_hash does not match valuation_run.v2")
        if request.report_id and request.report_id != self.report_id:
            raise ValueError("report_id does not match the sealed report request")
        if request.language.lower()[:2] != self.locale:
            raise ValueError("report locale does not match the sealed report request")
        if request.publication_intent != "final":
            raise ValueError(
                "publishable rendering requires publication_intent='final'"
            )
        if request.report_scope != "advisor_memorandum":
            raise ValueError(
                "sealed rendering requires report_scope='advisor_memorandum'"
            )
        if (
            not request.include_pdf
            or request.include_html
            or request.include_report_data
        ):
            raise ValueError("sealed rendering is binary-only")
        if request.engagement_scope is None:
            raise ValueError("sealed rendering requires a complete engagement scope")
        if request.engagement_scope.valuation_date != run.valuation_lens_date:
            raise ValueError(
                "engagement valuation date does not match valuation_run.v2"
            )
        if request.engagement_scope.evidence_date != run.fiscal_effective_date:
            raise ValueError("engagement evidence date does not match valuation_run.v2")
        if request.registry_snapshot is None:
            raise ValueError("sealed rendering requires a pinned KBO snapshot")
        if (
            canonical_hash(request.registry_snapshot.model_dump(mode="json"))
            != self.registry_snapshot_hash
        ):
            raise ValueError(
                "registry_snapshot_hash does not match the pinned KBO snapshot"
            )
        if request.report_assurance_level != self.assurance_level:
            raise ValueError("report assurance does not match the render snapshot")
        if request.branding is not None and request.branding.logo_url is not None:
            raise ValueError(
                "sealed rendering cannot dereference a mutable advisor logo URL"
            )
        if request.show_asking_price:
            raise ValueError("asking price is not part of the valuation memorandum")
        if request.include_transaction_readiness_section:
            raise ValueError("transaction readiness is a separate advisor deliverable")
        if request.include_business_growth_maturity_section:
            raise ValueError(
                "business growth planning is a separate advisor deliverable"
            )
        if request.include_generic_next_steps:
            raise ValueError(
                "transaction next steps are a separate advisor deliverable"
            )
        return self


class ReportDesignManifestV1(BaseModel):
    schema_version: Literal["report_design_manifest.v1"]
    design_profile: Literal["upswitch_advisor_memorandum.v1"]
    locale: Literal["nl", "fr", "en"]
    fonts: dict[str, str]
    colors: dict[str, str]
    spacing_scale_pt: list[int]
    advisor_logo: dict[str, str | int | None]
    upswitch_logo: dict[str, str | int]
    cover_archetype_revision: Literal["dark_icon_watermark.v4"]
    page_archetype_revision: Literal["sealed_adaptive_pages.v3"]
    industry_icon_registry_revision: Literal["industry_icon_registry.v1"]
    industry_icon_registry_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    business_card_motif_revision: Literal["business_card_knowledge_graph.v1"]
    business_card_motif_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    chart_specification_hashes: dict[str, str]
    template_contract_version: Literal["ma_valuation_memorandum.v3"]


class ProfessionalReviewerV2(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    firm: str = Field(..., min_length=1, max_length=200)
    credentials: list[str] = Field(default_factory=list, max_length=12)
    independence_confirmed: bool
    conflict_disclosures: list[str] = Field(default_factory=list, max_length=20)


class ProfessionalReviewFlagsV2(BaseModel):
    identity: bool
    scope: bool
    closed_periods: bool
    source_verification: bool
    normalizations: bool
    business_type: bool
    method: bool
    benchmark: bool
    balance_sheet: bool
    net_debt: bool
    conclusion: bool
    disclosures: bool
    visual_review: bool


class ProfessionalReviewChecklistV2(BaseModel):
    schema_version: Literal["professional_review_checklist.v2"]
    standards_profile: Literal["EVS_BV_2026_ALIGNED"]
    claim_state: Literal[
        "aligned_no_compliance_claim",
        "evs_bv_compliant",
        "ivs_compliant",
        "rics_compliant",
    ]
    checklist_revision: str = Field(..., min_length=1, max_length=80)
    reviewer: ProfessionalReviewerV2
    work_performed: list[str] = Field(..., min_length=1, max_length=30)
    work_not_performed: list[str] = Field(default_factory=list, max_length=30)
    checklist: ProfessionalReviewFlagsV2


class ReportRenderSnapshotV2(ReportRenderSnapshotV1):
    """Brand- and professional-review-bound successor to snapshot v1."""

    schema_version: Literal["report_render_snapshot.v2"]
    template_contract_version: Literal["ma_valuation_memorandum.v3"] = (
        "ma_valuation_memorandum.v3"
    )
    design_manifest: ReportDesignManifestV1
    design_manifest_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    professional_review: ProfessionalReviewChecklistV2
    professional_review_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def enforce_brand_and_professional_review_contract(
        self,
    ) -> "ReportRenderSnapshotV2":
        request = self.report_request
        branding = (
            request.branding.model_dump(mode="json", exclude_none=True)
            if request.branding is not None
            else {}
        )
        expected_design = build_report_design_manifest(
            branding=branding,
            locale=self.locale,
        )
        design = self.design_manifest.model_dump(mode="json")
        if canonical_hash(design) != self.design_manifest_hash:
            raise ValueError(
                "design_manifest_hash does not match ReportDesignManifestV1"
            )
        if design != expected_design:
            raise ValueError(
                "report design manifest does not match protected Upswitch assets"
            )
        review = self.professional_review.model_dump(mode="json")
        if canonical_hash(review) != self.professional_review_hash:
            raise ValueError(
                "professional_review_hash does not match ProfessionalReviewChecklistV2"
            )
        scope = request.engagement_scope
        if scope is None or not all(
            (
                scope.issue_date,
                scope.legal_rights,
                scope.investigations_performed,
                scope.assumptions,
                scope.material_uncertainty,
                scope.company_business_model,
                scope.products_services,
                scope.market_sector_overview,
                scope.competition_overview,
                scope.material_business_risks,
                scope.principal_value_drivers,
                scope.principal_caveats,
                scope.sustainable_earnings_commentary,
            )
        ):
            raise ValueError(
                "snapshot v2 requires the complete professional engagement scope"
            )
        if self.assurance_level == "advisor_approved":
            flags = self.professional_review.checklist.model_dump()
            if not self.professional_review.reviewer.independence_confirmed or not all(
                flags.values()
            ):
                raise ValueError(
                    "advisor_approved requires an independent reviewer and a complete checklist"
                )
        return self


class ReportRenderReceiptV1(BaseModel):
    schema_version: Literal["report_render_receipt.v1"]
    render_snapshot_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    valuation_run_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    report_context_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    template_bundle_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    renderer_revision: str = Field(..., min_length=1, max_length=160)
    renderer_version: str = Field(..., min_length=1, max_length=80)
    pdf_sha256: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    page_count: int = Field(..., ge=1)
    size_bytes: int = Field(..., ge=500)
    mime_type: Literal["application/pdf"] = "application/pdf"
    pdfa_profile: Literal["PDF/A-2b"] = "PDF/A-2b"
    pdfa_valid: bool
    pdfa_validation_engine: Literal["verapdf", "internal_structural_preflight"]
    pdfa_validator_version: str = Field(..., min_length=1, max_length=80)
    pdfa_validation_report_sha256: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    fonts_embedded: Literal[True] = True
    encrypted: Literal[False] = False
    locale: Literal["nl", "fr", "en"]
    receipt_sha256: str = Field(..., pattern=r"^[0-9a-f]{64}$")


class ReportRenderReceiptV2(ReportRenderReceiptV1):
    schema_version: Literal["report_render_receipt.v2"]
    design_manifest_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    industry_icon_registry_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    business_card_motif_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    deterministic_build: bool
