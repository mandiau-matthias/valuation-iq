"""Value-free assessment identity; never a zero-valued ValuationRun."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Literal

import rfc8785
from pydantic import BaseModel, ConfigDict, Field, model_validator

# Frozen with v1 so future registry changes cannot invalidate historical reports.
# Extend the assessment contract explicitly when the executable registry changes.
ASSESSMENT_V1_METHOD_KEYS: tuple[str, ...] = (
    "upswitch_adaptive",
    "ebitda_multiple",
    "omzet_multiple",
    "dcf",
    "sde_multiple",
    "arr_multiple",
    "adjusted_nav",
    "real_estate_yield",
    "fiscal_4x",
    "startup_valuation",
    "liquidation_analysis",
    "holding_sotp",
)
ASSESSMENT_V1_METHOD_REGISTRY_VERSION = "canonical_runtime_methods.2026-10-01"


def assessment_hash(payload: object) -> str:
    return hashlib.sha256(rfc8785.dumps(payload)).hexdigest()


class MissingFinancialFact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    field: str = Field(min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    fiscal_year: int | None = Field(ge=1900, le=2100)
    amount: None
    availability: Literal["missing"]
    source_reference: str | None = Field(max_length=300)


class AssessmentMethodExclusion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    method: str
    reason: Literal["no_financial_basis"]


class ValuationAssessmentV1(BaseModel):
    """Titan policy's no-basis outcome, sealed independently from numeric runs.

    The hash detects changes; it is not an authorization credential. Titan must
    authorize the dossier and verify the evidence revision before dispatch/save.
    This first policy covers entirely absent financial inputs, not an alternative
    to valuing supplied revenue, assets, cash flows or startup/holdings evidence.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    schema_version: Literal["valuation_assessment.v1"]
    assessment_id: str
    assessment_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    report_id: str = Field(min_length=1, max_length=100)
    workspace_id: str = Field(min_length=1, max_length=100)
    case_id: str = Field(min_length=1, max_length=100)
    evidence_revision_id: str = Field(min_length=1, max_length=100)
    evidence_snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    company_name: str = Field(min_length=1, max_length=300)
    country_code: str = Field(pattern=r"^[A-Z]{2}$")
    currency: str | None = Field(pattern=r"^[A-Z]{3}$")
    assessed_at: str = Field(
        pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
    )
    method_registry_version: Literal["canonical_runtime_methods.2026-10-01"]
    policy_version: Literal["financial_basis_assessment.v1"]
    conclusion: Literal["no_numerical_valuation"]
    reason: Literal["no_financial_basis"]
    financial_facts: list[MissingFinancialFact] = Field(min_length=1, max_length=256)
    method_exclusions: list[AssessmentMethodExclusion]

    @model_validator(mode="after")
    def validate_commitments(self) -> "ValuationAssessmentV1":
        timestamp = datetime.fromisoformat(self.assessed_at.replace("Z", "+00:00"))
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("assessment timestamp requires a timezone")
        methods = [item.method for item in self.method_exclusions]
        if sorted(methods) != sorted(ASSESSMENT_V1_METHOD_KEYS):
            raise ValueError(
                "assessment must exclude each executable canonical method exactly once"
            )
        facts = [(row.field, row.fiscal_year) for row in self.financial_facts]
        if len(facts) != len(set(facts)):
            raise ValueError("assessment contains duplicate financial fact identities")
        payload = self.model_dump(mode="json", exclude={"assessment_id", "assessment_hash"})
        expected = assessment_hash(payload)
        if self.assessment_hash != expected or self.assessment_id != f"assessment_{expected}":
            raise ValueError("assessment identity does not match its immutable payload")
        return self


class GenerateAssessmentReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    assessment: ValuationAssessmentV1
    language: Literal["en", "nl", "fr"]
    include_pdf: bool = False


class AssessmentReportManifestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    schema_version: Literal["assessment_report_manifest.v1"]
    report_id: str
    workspace_id: str
    assessment_id: str
    assessment_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_revision_id: str
    evidence_snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    valuation_run_id: None
    valuation_run_hash: None
    language: Literal["en", "nl", "fr"]
    template_version: Literal["financial_basis_assessment_report.v1"]
    html_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    pdf_sha256: str | None = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_hash(self) -> "AssessmentReportManifestV1":
        if self.manifest_hash != assessment_hash(
            self.model_dump(mode="json", exclude={"manifest_hash"})
        ):
            raise ValueError("assessment report manifest hash mismatch")
        return self


class AssessmentReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    assessment: ValuationAssessmentV1
    report_manifest: AssessmentReportManifestV1
    html_report: str = Field(min_length=1)
    pdf_base64: str | None

    @model_validator(mode="after")
    def validate_artifact_binding(self) -> "AssessmentReportResponse":
        import base64

        a, m = self.assessment, self.report_manifest
        for field in (
            "report_id",
            "workspace_id",
            "assessment_id",
            "assessment_hash",
            "evidence_revision_id",
            "evidence_snapshot_hash",
        ):
            if getattr(a, field) != getattr(m, field):
                raise ValueError(f"assessment report {field} mismatch")
        if hashlib.sha256(self.html_report.encode()).hexdigest() != m.html_sha256:
            raise ValueError("assessment HTML hash mismatch")
        pdf_hash = None
        if self.pdf_base64 is not None:
            pdf = base64.b64decode(self.pdf_base64, validate=True)
            if base64.b64encode(pdf).decode() != self.pdf_base64 or not pdf.startswith(b"%PDF-"):
                raise ValueError("invalid assessment PDF bytes")
            pdf_hash = hashlib.sha256(pdf).hexdigest()
        if pdf_hash != m.pdf_sha256:
            raise ValueError("assessment PDF hash mismatch")
        return self
