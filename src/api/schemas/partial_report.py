"""Reports project a saved partial assessment; no new calculation is admitted."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.api.schemas.partial_valuation import PartialValuationResponse


class GeneratePartialReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    partial_valuation: PartialValuationResponse
    report_id: str = Field(min_length=1, max_length=100)
    language: Literal["en", "nl", "fr"]
    include_pdf: bool = False


class PartialReportManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["partial_report_manifest.v1"] = "partial_report_manifest.v1"
    report_id: str
    assessment_id: str
    content_sha256: str
    evidence_revision_id: str
    language: Literal["en", "nl", "fr"]
    html_sha256: str
    html_bytes: int
    pdf_sha256: str | None
    pdf_bytes: int | None
    reviewer_requirement: Literal["none"] = "none"
    private_save_allowed: Literal[True] = True
    certification_claim: Literal[False] = False


class PartialReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    partial_valuation: PartialValuationResponse
    report_manifest: PartialReportManifest
    html_report: str
    pdf_base64: str | None = None
