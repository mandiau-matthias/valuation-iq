"""Versioned evidence-first contracts shared by stateless valuation runs.

These models deliberately separate reported accounting evidence, reviewer
decisions, the assembled valuation case, and the immutable calculation run.
They are additive to the existing stateless request during migration.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from datetime import date
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Annotated, Dict, List, Literal, Optional

import rfc8785
from pydantic import (
    BaseModel,
    Field,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

from .accounting_money_facts import accounting_monetary_facts
from .forecast_evidence import ForecastEvidence
from .accounting_money_authority import authoritative_reported_values
from .signed_wire_projection import signed_wire_fields

JsonObject = Dict[str, object]
Sha256Hex = Annotated[str, Field(pattern=r"^[0-9a-fA-F]{64}$")]
ACCOUNTING_EVIDENCE_CONTENT_HASH_VERSION = "accounting_evidence_content.v1"
ACCOUNTING_EVIDENCE_V2_CONTENT_HASH_VERSION = "accounting_evidence_content.v2"
ACCOUNTING_EVIDENCE_V3_CONTENT_HASH_VERSION = "accounting_evidence_content.v3"


class AccountingSourceReference(BaseModel):
    source_id: str
    source_kind: str
    provider: Optional[str] = None
    observed_at: Optional[datetime] = None
    document_hash: Optional[str] = None
    locator: Optional[str] = None


class AccountingReportedFact(BaseModel):
    fact_id: str
    field_key: str
    fiscal_year: Optional[int] = Field(None, ge=1900, le=2100)
    amount: Optional[Decimal] = None
    text_value: Optional[str] = None
    currency: Optional[str] = Field(None, pattern=r"^[A-Z]{3}$")
    unit: str = "currency"
    source_refs: List[AccountingSourceReference] = Field(default_factory=list)
    transformation_ids: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_one_value(self) -> "AccountingReportedFact":
        if self.amount is None and self.text_value is None:
            raise ValueError("reported fact requires amount or text_value")
        return self


class AccountingEvidencePackage(BaseModel):
    schema_version: Literal[
        "accounting_evidence_package.v1",
        "accounting_evidence_package.v2",
        "accounting_evidence_package.v3",
    ] = "accounting_evidence_package.v1"
    snapshot_id: str
    snapshot_hash: Sha256Hex
    content_hash: Optional[Sha256Hex] = None
    content_hash_version: Optional[
        Literal[
            "accounting_evidence_content.v1",
            "accounting_evidence_content.v2",
            "accounting_evidence_content.v3",
        ]
    ] = Field(
        None,
        description=(
            "Canonical content commitment used when this package is attached to "
            "priced inputs. Legacy packages without this value can only remain "
            "unattached/non-priced."
        ),
    )
    evidence_revision_id: str
    entity_id: Optional[str] = None
    tenant_id: Optional[str] = None
    provider_id: Optional[str] = None
    connection_id: Optional[str] = None
    company_name: Optional[str] = None
    country_code: Optional[str] = Field(None, pattern=r"^[A-Z]{2}$")
    currency: Optional[str] = Field(None, pattern=r"^[A-Z]{3}$")
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    reported_facts: List[AccountingReportedFact] = Field(default_factory=list)
    canonical_ledger_lines: List[JsonObject] = Field(default_factory=list)
    field_provenance: List[JsonObject] = Field(default_factory=list)
    conflicts: List[JsonObject] = Field(default_factory=list)
    rejected_candidates: List[JsonObject] = Field(default_factory=list)
    import_quality: Optional[JsonObject] = None
    evidence_tags: List[JsonObject] = Field(default_factory=list)
    periods: List[JsonObject] = Field(default_factory=list)
    years: List[JsonObject] = Field(default_factory=list)
    canonicalization: Optional[Literal["RFC8785"]] = None
    signature_algorithm: Optional[Literal["Ed25519-SHA256"]] = None
    issuer: Optional[str] = None
    key_id: Optional[str] = None
    issued_at: Optional[str] = None
    detached_signature: Optional[str] = None
    company_node_id: Optional[str] = Field(None, pattern=r"^[0-9a-fA-F-]{36}$")
    source_entity_aliases: List[str] = Field(default_factory=list)
    evidence_origin: Optional[Literal["connected_source"]] = None
    verification_level: Optional[Literal["source_verified"]] = None
    source_bound: Optional[Literal[True]] = None
    visibility_scope: Optional[Literal["workspace"]] = None
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None

    @field_validator("issued_at", "valid_from", "valid_until")
    @classmethod
    def preserve_wire_timestamp(cls, value: Optional[str]) -> Optional[str]:
        """Validate without normalizing bytes covered by the producer signature."""
        if value is None:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("issued_at must be an ISO-8601 timestamp") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("issued_at must include a timezone")
        return value

    @model_validator(mode="after")
    def verify_declared_content_hash(self) -> "AccountingEvidencePackage":
        if self.schema_version != "accounting_evidence_package.v1" and self.reported_facts:
            raise ValueError("signed accounting packages cannot contain unsigned top-level facts")
        if self.content_hash_version is None:
            return self
        if self.schema_version in {
            "accounting_evidence_package.v2",
            "accounting_evidence_package.v3",
        }:
            from .accounting_evidence_security import accounting_evidence_digest

            expected_content_version = (
                ACCOUNTING_EVIDENCE_V3_CONTENT_HASH_VERSION
                if self.schema_version == "accounting_evidence_package.v3"
                else ACCOUNTING_EVIDENCE_V2_CONTENT_HASH_VERSION
            )
            if self.content_hash_version != expected_content_version:
                raise ValueError(f"{self.schema_version} requires {expected_content_version}")
            if not self.content_hash:
                raise ValueError(f"{self.schema_version} requires content_hash")
            if self.schema_version == "accounting_evidence_package.v3":
                if not self.company_node_id:
                    raise ValueError("AccountingEvidencePackage v3 requires company_node_id")
                aliases = sorted(
                    {alias.strip() for alias in self.source_entity_aliases if alias.strip()}
                )
                if not aliases or not self.entity_id or self.entity_id not in aliases:
                    raise ValueError(
                        "AccountingEvidencePackage v3 must retain entity_id as a source alias"
                    )
                if (
                    self.evidence_origin != "connected_source"
                    or self.verification_level != "source_verified"
                    or self.source_bound is not True
                    or self.visibility_scope != "workspace"
                    or not self.valid_from
                ):
                    raise ValueError(
                        "AccountingEvidencePackage v3 requires a verified source-bound workspace contract"
                    )
                valid_from = datetime.fromisoformat(self.valid_from.replace("Z", "+00:00"))
                if self.valid_until is not None:
                    valid_until = datetime.fromisoformat(self.valid_until.replace("Z", "+00:00"))
                    if valid_until <= valid_from:
                        raise ValueError(
                            "AccountingEvidencePackage v3 valid_until must follow valid_from"
                        )
            expected = accounting_evidence_digest(self.model_dump(mode="json")).hex()
            if self.content_hash.lower() != expected or self.snapshot_hash.lower() != expected:
                raise ValueError(
                    "content_hash does not match the declared RFC8785 evidence payload"
                )
            return self
        expected = accounting_evidence_content_hash(self)
        if self.snapshot_hash.lower() != expected:
            raise ValueError(
                "snapshot_hash does not match accounting_evidence_content.v1 "
                "canonical package content"
            )
        return self


class AttestedUploadedDataSnapshot(BaseModel):
    """Titan T4/T5 source snapshot pinned for audit, never pricing authority."""

    snapshot_id: str
    snapshot_hash: Sha256Hex
    source_kind: Literal["titan_annual_financials"] = "titan_annual_financials"
    entity_id: str
    company_registry_number: Optional[str] = None
    accountant_customer_id: Optional[str] = None
    trust_class: Literal["owner_attested_private", "independently_reviewed_private"]
    evidence_tier: Literal["T4", "T5"]
    revision_id: str

    @model_validator(mode="after")
    def bind_tier_to_attestation(self) -> "AttestedUploadedDataSnapshot":
        expected = "T5" if self.trust_class == "independently_reviewed_private" else "T4"
        if self.evidence_tier != expected:
            raise ValueError("attested uploaded-data evidence_tier does not match trust_class")
        return self


class GovernedReportReviewDecision(BaseModel):
    """Advisor decision over the exact calculation committed by a v2 run."""

    schema_version: Literal["report_review_decision.v1"] = "report_review_decision.v1"
    decision_id: str = Field(..., min_length=1, max_length=128)
    scope: Literal["valuation_calculation"] = "valuation_calculation"
    scope_id: Sha256Hex = Field(
        ...,
        description=(
            "The valuation_run review_scope_hash reviewed by the advisor. This stable "
            "economic commitment excludes only the review receipt and its enclosing "
            "case-signature material."
        ),
    )
    decision: Literal["accepted", "rejected"]
    reviewer_id: str = Field(..., min_length=1, max_length=128)
    reviewer_role: Literal["advisor", "senior_advisor", "compliance_reviewer"]
    decided_at: datetime
    source_kind: Literal["advisor_review_record", "compliance_review_record"]
    source_id: str = Field(..., min_length=1, max_length=256)
    source_hash: Sha256Hex

    @model_validator(mode="after")
    def require_timezone_aware_decision(self) -> "GovernedReportReviewDecision":
        if self.decided_at.tzinfo is None or self.decided_at.utcoffset() is None:
            raise ValueError("report review decided_at must include an explicit timezone")
        return self


class ReportContentProvenanceSnapshot(BaseModel):
    """Sealed origin and review state for narrative and report evidence."""

    schema_version: Literal["report_content_provenance.v1"] = "report_content_provenance.v1"
    narrative_origin: Literal["deterministic_template", "human_authored", "llm_generated"] = (
        "deterministic_template"
    )
    evidence_origin: Literal["governed_structured", "human_reviewed", "llm_generated"] = (
        "governed_structured"
    )
    review_state: Literal["not_required", "approved", "unreviewed", "rejected"] = "not_required"
    model_id: Optional[str] = None
    reviewer_id: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    source_hash: Optional[Sha256Hex] = None

    @model_validator(mode="after")
    def bind_llm_review_evidence(self) -> "ReportContentProvenanceSnapshot":
        uses_llm = "llm_generated" in {self.narrative_origin, self.evidence_origin}
        if uses_llm and self.review_state == "not_required":
            raise ValueError("LLM-generated report content requires an explicit review state")
        if uses_llm and not self.model_id:
            raise ValueError("LLM-generated report content requires model_id")
        if self.review_state == "approved" and (
            not self.reviewer_id or self.reviewed_at is None or self.source_hash is None
        ):
            raise ValueError(
                "approved report content requires reviewer_id, reviewed_at, and source_hash"
            )
        if self.reviewed_at is not None and (
            self.reviewed_at.tzinfo is None or self.reviewed_at.utcoffset() is None
        ):
            raise ValueError("report content reviewed_at must include an explicit timezone")
        return self


class EvidenceMaturityAssurance(BaseModel):
    """Company-evidence maturity; this is never an accuracy claim."""

    tier: Literal["T0", "T1", "T2", "T3", "T4", "T5"] = "T2"
    rationale: Optional[str] = None
    legacy_data_tier: Optional[Literal["indicative", "defensible", "attested"]] = Field(
        None,
        description=(
            "Deprecated source label retained only for migration traceability. "
            "A legal attestation cannot promote evidence maturity."
        ),
    )


class EvidenceConfidenceAssurance(BaseModel):
    """Confidence in the evidence package, separate from certification."""

    level: Literal["LOW", "MEDIUM", "HIGH"] = "LOW"
    score: int = Field(0, ge=0, le=100)
    model_version: str = "evidence_confidence.v1"


class CalculationCertificationAssurance(BaseModel):
    """Independent certification state for the economic calculation."""

    status: Literal[
        "uncertified",
        "certified",
        "certified_with_qualifications",
        "failed",
        "revoked",
    ] = "uncertified"
    certification_id: Optional[str] = None
    certifier_id: Optional[str] = None
    certified_at: Optional[datetime] = None
    qualifications: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_certification_evidence(self) -> "CalculationCertificationAssurance":
        is_certified = self.status in {"certified", "certified_with_qualifications"}
        if is_certified and (
            not self.certification_id or not self.certifier_id or self.certified_at is None
        ):
            raise ValueError(
                "certified calculation requires certification_id, certifier_id, and certified_at"
            )
        if self.certified_at is not None and (
            self.certified_at.tzinfo is None or self.certified_at.utcoffset() is None
        ):
            raise ValueError("calculation certified_at must include an explicit timezone")
        return self


class LegalAttestationAssurance(BaseModel):
    """Signature/legal attestation state, explicitly outside calculation assurance."""

    status: Literal["not_attested", "attested", "revoked"] = "not_attested"
    attestation_id: Optional[str] = None
    signer_id: Optional[str] = None
    attested_at: Optional[datetime] = None
    eidas_tier: Optional[Literal["SES", "AES", "QES"]] = None
    scope: Literal["report_identity_and_signatures"] = "report_identity_and_signatures"
    calculation_certification_effect: Literal["none"] = "none"

    @model_validator(mode="after")
    def require_attestation_evidence(self) -> "LegalAttestationAssurance":
        if self.status == "attested" and (
            not self.attestation_id or not self.signer_id or self.attested_at is None
        ):
            raise ValueError(
                "legal attestation requires attestation_id, signer_id, and attested_at"
            )
        if self.attested_at is not None and (
            self.attested_at.tzinfo is None or self.attested_at.utcoffset() is None
        ):
            raise ValueError("legal attestation attested_at must include an explicit timezone")
        return self


class OutcomeAccuracyAssurance(BaseModel):
    """Accuracy observed only against a later transaction or adjudicated outcome."""

    status: Literal["not_observed", "observed"] = "not_observed"
    outcome_id: Optional[str] = None
    outcome_type: Optional[Literal["transaction", "adjudicated_outcome"]] = None
    observed_at: Optional[date] = None
    absolute_percentage_error: Optional[Decimal] = Field(None, ge=0)

    @model_validator(mode="after")
    def require_observed_outcome(self) -> "OutcomeAccuracyAssurance":
        if self.status == "observed" and (
            not self.outcome_id or self.outcome_type is None or self.observed_at is None
        ):
            raise ValueError(
                "observed outcome accuracy requires outcome_id, outcome_type, and observed_at"
            )
        return self


class ReportAssuranceContract(BaseModel):
    """Versioned, orthogonal assurance dimensions for calculation and report use."""

    schema_version: Literal["report_assurance.v1"] = "report_assurance.v1"
    evidence_maturity: EvidenceMaturityAssurance = Field(default_factory=EvidenceMaturityAssurance)
    evidence_confidence: EvidenceConfidenceAssurance = Field(
        default_factory=EvidenceConfidenceAssurance
    )
    calculation_certification: CalculationCertificationAssurance = Field(
        default_factory=CalculationCertificationAssurance
    )
    legal_attestation: LegalAttestationAssurance = Field(default_factory=LegalAttestationAssurance)
    outcome_accuracy: OutcomeAccuracyAssurance = Field(default_factory=OutcomeAccuracyAssurance)
    country_pack_certification_state: Literal["draft", "certified", "expired", "revoked"] = "draft"
    country_pack_certification_manifest_hash: Optional[Sha256Hex] = None
    country_pack_certification_reviewer_receipt_ids: List[str] = Field(default_factory=list)
    method_certification_profile_version: str = "method_certification_profile.v1"
    priced_method_certification_profile_keys: List[str] = Field(default_factory=list)
    method_certification_evaluations: List[JsonObject] = Field(default_factory=list)
    method_country_certification_eligible: bool = False

    @model_validator(mode="after")
    def require_country_pack_certification_evidence(self) -> "ReportAssuranceContract":
        if self.country_pack_certification_state == "certified" and (
            self.country_pack_certification_manifest_hash is None
            or len(set(self.country_pack_certification_reviewer_receipt_ids)) < 3
        ):
            raise ValueError(
                "certified country pack requires a manifest hash and three reviewer receipts"
            )
        from src.domain.method_certification_profiles import method_certification_profile

        evaluated_profile_keys: list[str] = []
        evaluated_method_keys: list[str] = []
        fully_eligible = bool(self.method_certification_evaluations)
        for raw in self.method_certification_evaluations:
            method_key = str(raw.get("method_key") or "").strip().lower()
            if not method_key or method_key in evaluated_method_keys:
                raise ValueError("method certification evaluations require unique method keys")
            evaluated_method_keys.append(method_key)
            profile = method_certification_profile(method_key)
            profile_version = raw.get("profile_version")
            evidence_checks = raw.get("evidence_checks")
            invariant_checks = raw.get("invariant_checks")
            review_checks = raw.get("review_checks")
            failures = raw.get("failures")
            if profile is not None:
                evaluated_profile_keys.append(profile.method_key)
                exact_evidence = isinstance(evidence_checks, Mapping) and set(
                    evidence_checks
                ) == set(profile.required_evidence)
                exact_invariants = isinstance(invariant_checks, Mapping) and set(
                    invariant_checks
                ) == set(profile.required_invariants)
            else:
                exact_evidence = False
                exact_invariants = False
            row_eligible = bool(
                profile is not None
                and profile_version == self.method_certification_profile_version
                and exact_evidence
                and exact_invariants
                and isinstance(review_checks, Mapping)
                and set(review_checks) == {"profile_review_accepted"}
                and all(value is True for value in evidence_checks.values())
                and all(value is True for value in invariant_checks.values())
                and all(value is True for value in review_checks.values())
                and failures == []
            )
            if bool(raw.get("eligible")) != row_eligible:
                raise ValueError("method certification evaluation eligibility is inconsistent")
            fully_eligible = fully_eligible and row_eligible
        if sorted(set(evaluated_profile_keys)) != sorted(
            set(self.priced_method_certification_profile_keys)
        ):
            raise ValueError(
                "priced method certification profile keys must match evaluated methods"
            )
        if self.method_country_certification_eligible != fully_eligible:
            raise ValueError(
                "method country certification eligibility must match per-run evaluations"
            )
        return self


DecisionState = Literal["accepted", "edited", "rejected", "proposed"]

_V2_DECISION_NULLABLE_FIELDS = (
    "fiscal_year",
    "signed_amount",
    "value_payload",
    "currency",
    "reason",
    "decided_by_organization",
    "supersedes_decision_id",
)
_V2_DECISION_COMMITMENT_FIELDS = (
    "schema_version",
    "decision_id",
    "company_id",
    "case_id",
    "evidence_revision_id",
    "evidence_id",
    "evidence_source",
    "evidence_content_hash",
    "evidence_provenance_hash",
    "field_key",
    "fiscal_year",
    "category",
    "state",
    "signed_amount",
    "value_payload",
    "currency",
    "unit",
    "reason",
    "decided_by",
    "decided_by_organization",
    "decided_by_role",
    "policy_version",
    "rule_version",
    "supersedes_decision_id",
    "decided_at",
)


def _rfc8785_sha256(value: object) -> str:
    return hashlib.sha256(rfc8785.dumps(value)).hexdigest()


def _v2_decision_content_commitment(raw: Mapping[str, object]) -> JsonObject:
    commitment: JsonObject = {}
    for field_name in _V2_DECISION_COMMITMENT_FIELDS:
        value = raw.get(field_name)
        if field_name in _V2_DECISION_NULLABLE_FIELDS and field_name not in raw:
            value = None
        commitment[field_name] = value
    return commitment


def _verify_v2_decision_wire(raw: Mapping[str, object]) -> None:
    if raw.get("schema_version") != "valuation_input_decision.v2":
        raise ValueError("server-resolved ValuationCase v2 requires v2 input decisions")
    signed_amount = raw.get("signed_amount")
    value_payload = raw.get("value_payload")
    state = raw.get("state")
    if state not in {"accepted", "edited", "rejected"}:
        raise ValueError("ValuationInputDecision v2 state must be accepted, edited, or rejected")
    if signed_amount is not None and not isinstance(signed_amount, str):
        raise ValueError("ValuationInputDecision v2 signed_amount must be an exact decimal string")
    if state in {"accepted", "edited"} and ((signed_amount is None) == (value_payload is None)):
        raise ValueError(
            "accepted/edited ValuationInputDecision v2 requires exactly one governed value"
        )
    expected = _rfc8785_sha256(_v2_decision_content_commitment(raw))
    if str(raw.get("content_hash") or "").lower() != expected:
        raise ValueError("ValuationInputDecision v2 content_hash does not match its payload")


class ValuationDecisionAuthority(BaseModel):
    schema_version: Literal["valuation_decision_authority.v1"] = "valuation_decision_authority.v1"
    issuer: Literal["titan"] = "titan"
    actor_scope: Literal["server_resolved"] = "server_resolved"
    company_id: str
    case_id: str
    evidence_revision_id: str
    policy_version: Optional[str] = None
    decision_set_hash: Sha256Hex
    decision_count: int = Field(..., ge=0)
    resolved_at: datetime
    content_hash: Sha256Hex

    @model_validator(mode="before")
    @classmethod
    def verify_wire_commitment(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        raw = dict(value)
        commitment = {key: item for key, item in raw.items() if key != "content_hash"}
        if str(raw.get("content_hash") or "").lower() != _rfc8785_sha256(commitment):
            raise ValueError("valuation decision authority content_hash mismatch")
        return value

    @model_validator(mode="after")
    def require_timezone(self) -> "ValuationDecisionAuthority":
        if self.resolved_at.tzinfo is None or self.resolved_at.utcoffset() is None:
            raise ValueError("valuation decision authority resolved_at must include timezone")
        return self


class ValuationInputDecision(BaseModel):
    schema_version: Literal["valuation_input_decision.v1", "valuation_input_decision.v2"] = (
        "valuation_input_decision.v1"
    )
    decision_id: str
    company_id: Optional[str] = None
    case_id: Optional[str] = None
    evidence_revision_id: Optional[str] = None
    evidence_id: str
    evidence_source: Optional[str] = None
    evidence_content_hash: Optional[Sha256Hex] = None
    evidence_provenance_hash: Optional[Sha256Hex] = None
    field_key: str
    fiscal_year: Optional[int] = Field(None, ge=1900, le=2100)
    category: str
    state: DecisionState
    signed_amount: Optional[Decimal] = None
    value_payload: Optional[JsonObject] = Field(
        None,
        description=(
            "Exact governed non-monetary input value. Required for composite "
            "qualitative inputs such as owner_dependency_factors."
        ),
    )
    currency: Optional[str] = Field(None, pattern=r"^[A-Z]{3}$")
    unit: str = "currency"
    reason: Optional[str] = None
    rule_version: Optional[str] = None
    policy_version: Optional[str] = None
    decided_by: Optional[str] = None
    decided_by_organization: Optional[str] = None
    decided_by_role: Optional[str] = None
    decided_at: Optional[datetime] = None
    content_hash: Optional[Sha256Hex] = None
    supersedes_decision_id: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def verify_v2_wire_hash(cls, value: object) -> object:
        if isinstance(value, Mapping) and value.get("schema_version") == (
            "valuation_input_decision.v2"
        ):
            _verify_v2_decision_wire(value)
        return value

    @model_validator(mode="after")
    def require_v2_authority_fields(self) -> "ValuationInputDecision":
        if self.schema_version != "valuation_input_decision.v2":
            return self
        required = {
            "company_id": self.company_id,
            "case_id": self.case_id,
            "evidence_revision_id": self.evidence_revision_id,
            "evidence_source": self.evidence_source,
            "evidence_content_hash": self.evidence_content_hash,
            "evidence_provenance_hash": self.evidence_provenance_hash,
            "rule_version": self.rule_version,
            "policy_version": self.policy_version,
            "decided_by": self.decided_by,
            "decided_by_role": self.decided_by_role,
            "decided_at": self.decided_at,
            "content_hash": self.content_hash,
        }
        missing = [name for name, item in required.items() if item is None or item == ""]
        if missing:
            raise ValueError(
                "ValuationInputDecision v2 is missing server authority fields: "
                + ", ".join(missing)
            )
        if self.state == "proposed":
            raise ValueError("ValuationInputDecision v2 cannot carry a proposed state")
        if self.decided_at is not None and (
            self.decided_at.tzinfo is None or self.decided_at.utcoffset() is None
        ):
            raise ValueError("ValuationInputDecision v2 decided_at must include timezone")
        return self


class ValuationCaseAttestation(BaseModel):
    """Titan's signed authority over one immutable valuation-case dispatch."""

    schema_version: Literal["valuation_case_attestation.v1"]
    content_hash_version: Literal["valuation_case_attestation_content.v1"]
    canonicalization: Literal["RFC8785"]
    signature_algorithm: Literal["Ed25519-SHA256"]
    issuer: str = Field(..., min_length=1)
    key_id: str = Field(..., min_length=1)
    issued_at: str
    company_id: str = Field(..., min_length=1)
    case_id: str = Field(..., min_length=1)
    evidence_revision_id: str = Field(..., min_length=1)
    case_hash: Sha256Hex
    evidence_hash: Sha256Hex
    decision_set_hash: Sha256Hex
    benchmark_hash: Sha256Hex
    economic_snapshot_hash: Sha256Hex
    country_pack_hash: Sha256Hex
    policy_hash: Sha256Hex
    content_hash: Sha256Hex
    detached_signature: str = Field(..., min_length=1)

    @field_validator("issued_at")
    @classmethod
    def preserve_wire_timestamp(cls, value: str) -> str:
        """Validate timestamp semantics without changing signed bytes."""

        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("case attestation issued_at must be ISO-8601") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("case attestation issued_at must include timezone")
        return value


class ValuationCase(BaseModel):
    forecast_evidence: Optional[ForecastEvidence] = None

    @model_serializer(mode="wrap")
    def preserve_historical_case_shape(self, handler: SerializerFunctionWrapHandler) -> dict:
        result = handler(self)
        if self.schema_version == "valuation_case.v2":
            # Preserve the authenticated producer envelope on parse/reload.
            # Reader defaults must not become new signature/hash material.
            result = signed_wire_fields(self, result)
        if self.forecast_evidence is None:
            result.pop("forecast_evidence", None)
        return result

    schema_version: Literal["valuation_case.v1", "valuation_case.v2"] = "valuation_case.v1"
    case_id: str
    company_id: Optional[str] = None
    scenario_id: str = "observed"
    evidence_revision_id: Optional[str] = None
    accounting_evidence_attachment: Literal["priced", "unattached_non_priced"] = Field(
        "unattached_non_priced",
        description=(
            "Whether the nested AccountingEvidencePackage is bound to monetary "
            "inputs. The safe migration default is unattached_non_priced."
        ),
    )
    accounting_evidence_snapshot_id: Optional[str] = None
    accounting_evidence_snapshot_hash: Optional[Sha256Hex] = None
    accounting_evidence: Optional[AccountingEvidencePackage | JsonObject] = Field(
        None,
        description=(
            "AccountingEvidencePackage for priced accounting facts, or a sealed "
            "non-accounting evidence envelope retained only when attachment is "
            "unattached_non_priced. Open evidence can never authorize pricing."
        ),
    )
    accounting_evidence_bundle: Optional[JsonObject] = Field(
        None,
        description=(
            "Hermes AccountingEvidenceBundleV1 binding the signed package to "
            "source snapshots, mappings, period admission and truth-ledger hashes."
        ),
    )
    attested_uploaded_data_snapshot: Optional[AttestedUploadedDataSnapshot] = Field(
        None,
        description=(
            "Titan owner-attested or independently reviewed annual-financial snapshot "
            "preserved for report audit only. This field never authorizes pricing; "
            "priced accounting evidence still requires the signed v2 boundary."
        ),
    )
    report_review_decisions: List[GovernedReportReviewDecision] = Field(default_factory=list)
    content_provenance: ReportContentProvenanceSnapshot = Field(
        default_factory=ReportContentProvenanceSnapshot
    )
    input_decisions: List[ValuationInputDecision] = Field(default_factory=list)
    decision_set_hash: Optional[Sha256Hex] = None
    decision_authority: Optional[ValuationDecisionAuthority] = None
    case_attestation: Optional[ValuationCaseAttestation] = None
    forecast_revision_id: Optional[str] = None
    recovery_inputs_snapshot: Optional[JsonObject] = Field(
        None,
        description=("Exact recovery_inputs.v1 wire payload committed by Titan's case signature."),
    )
    recovery_verification_receipt: Optional[JsonObject] = Field(
        None,
        description=(
            "Titan-derived authenticated owner/advisor receipt committed by the case signature."
        ),
    )
    recovery_automated_review: Optional[JsonObject] = Field(
        None,
        description=(
            "Titan-minted, role-independent review binding the complete recovery schedule "
            "to automated evidence, driver, reinvestment, funding and assumption checks."
        ),
    )
    ownership_revision_id: Optional[str] = None
    holdings_revision_id: Optional[str] = None
    capital_structure_revision_id: Optional[str] = None
    benchmark_snapshot_ids: List[str] = Field(default_factory=list)
    company_snapshot_id: Optional[str] = None
    company_snapshot_hash: Optional[Sha256Hex] = None
    classification_resolution: Optional[JsonObject] = None
    source_citations: List[JsonObject] = Field(default_factory=list)
    policy_version: str = "evidence_first_2026_08"

    @property
    def authoritative_input_decisions(self) -> List[ValuationInputDecision]:
        """Return only Titan-signed v2 decisions that may affect economics.

        Legacy v1 cases remain readable for audit/report compatibility, but a
        caller-controlled ``accepted`` string is not monetary authority.  All
        economic consumers must use this projection rather than the raw
        ``input_decisions`` list.
        """

        if self.schema_version != "valuation_case.v2" or self.case_attestation is None:
            return []
        return [
            decision
            for decision in self.input_decisions
            if decision.schema_version == "valuation_input_decision.v2"
        ]

    @model_validator(mode="before")
    @classmethod
    def verify_v2_decision_set(cls, value: object) -> object:
        if not isinstance(value, Mapping) or value.get("schema_version") != "valuation_case.v2":
            return value
        raw = dict(value)
        decisions = raw.get("input_decisions")
        if not isinstance(decisions, list):
            raise ValueError("ValuationCase v2 input_decisions must be an ordered list")
        for decision in decisions:
            if not isinstance(decision, Mapping):
                raise ValueError("ValuationCase v2 contains a malformed input decision")
            _verify_v2_decision_wire(decision)
        decision_set_hash = _rfc8785_sha256(decisions)
        if str(raw.get("decision_set_hash") or "").lower() != decision_set_hash:
            raise ValueError("ValuationCase v2 decision_set_hash mismatch")
        authority = raw.get("decision_authority")
        if not isinstance(authority, Mapping):
            raise ValueError("ValuationCase v2 requires Titan decision_authority")
        authority_commitment = {
            key: item for key, item in authority.items() if key != "content_hash"
        }
        if str(authority.get("content_hash") or "").lower() != _rfc8785_sha256(
            authority_commitment
        ):
            raise ValueError("ValuationCase v2 decision_authority content_hash mismatch")
        from src.config import get_settings

        from .valuation_case_security import (
            parse_titan_valuation_case_public_key_registry,
            verify_valuation_case_attestation,
        )

        verify_valuation_case_attestation(
            raw,
            registry=parse_titan_valuation_case_public_key_registry(
                get_settings().titan_valuation_case_public_key_registry_json
            ),
        )
        return value

    @model_validator(mode="after")
    def bind_priced_accounting_evidence(self) -> "ValuationCase":
        if self.schema_version == "valuation_case.v2":
            if (
                not self.company_id
                or not self.evidence_revision_id
                or self.decision_set_hash is None
                or self.decision_authority is None
                or self.case_attestation is None
            ):
                raise ValueError(
                    "ValuationCase v2 requires complete signed Titan decision authority"
                )
            authority = self.decision_authority
            if (
                authority.company_id != self.company_id
                or authority.case_id != self.case_id
                or authority.evidence_revision_id != self.evidence_revision_id
                or authority.policy_version != self.policy_version
                or authority.decision_set_hash.lower() != self.decision_set_hash.lower()
                or authority.decision_count != len(self.input_decisions)
            ):
                raise ValueError("ValuationCase v2 decision authority does not match the case")
            for decision in self.input_decisions:
                if (
                    decision.schema_version != "valuation_input_decision.v2"
                    or decision.company_id != self.company_id
                    or decision.case_id != self.case_id
                    or decision.evidence_revision_id != self.evidence_revision_id
                    or decision.policy_version != self.policy_version
                ):
                    raise ValueError(
                        "ValuationCase v2 input decision identity/policy does not match the case"
                    )
        elif (
            self.decision_set_hash is not None
            or self.decision_authority is not None
            or self.case_attestation is not None
        ):
            raise ValueError("ValuationCase v1 cannot claim Titan v2 decision authority")
        attested = self.attested_uploaded_data_snapshot
        if attested is not None and (not self.company_id or self.company_id != attested.entity_id):
            raise ValueError(
                "attested uploaded-data snapshot entity_id must match valuation_case.company_id"
            )
        if self.accounting_evidence_attachment != "priced":
            return self

        package = self.accounting_evidence
        # The permissive JsonObject branch exists for explicitly unattached
        # legacy evidence. For priced input, re-run the typed package validator
        # so a tampered signed package surfaces its precise binding/hash error
        # instead of collapsing into a generic "package required" message.
        if isinstance(package, Mapping):
            package = AccountingEvidencePackage.model_validate(package)
            self.accounting_evidence = package
        if not isinstance(package, AccountingEvidencePackage):
            raise ValueError("priced accounting evidence attachment requires accounting_evidence")
        supported_signed_package = (
            package.schema_version == "accounting_evidence_package.v2"
            and package.content_hash_version == ACCOUNTING_EVIDENCE_V2_CONTENT_HASH_VERSION
        ) or (
            package.schema_version == "accounting_evidence_package.v3"
            and package.content_hash_version == ACCOUNTING_EVIDENCE_V3_CONTENT_HASH_VERSION
        )
        if not supported_signed_package:
            raise ValueError(
                "priced accounting evidence requires a signed AccountingEvidencePackage"
            )
        if package.schema_version == "accounting_evidence_package.v3":
            if not self.company_id or self.company_id != package.company_node_id:
                raise ValueError(
                    "priced accounting evidence company_node_id must match valuation_case.company_id"
                )
        elif not package.entity_id or not self.company_id or self.company_id != package.entity_id:
            raise ValueError(
                "priced accounting evidence entity_id must match valuation_case.company_id"
            )
        if (
            not self.evidence_revision_id
            or self.evidence_revision_id != package.evidence_revision_id
        ):
            raise ValueError(
                "priced accounting evidence evidence_revision_id must match valuation case"
            )
        if (
            not self.accounting_evidence_snapshot_id
            or self.accounting_evidence_snapshot_id != package.snapshot_id
        ):
            raise ValueError("priced accounting evidence snapshot_id must match valuation case")
        if (
            not self.accounting_evidence_snapshot_hash
            or self.accounting_evidence_snapshot_hash.lower() != package.snapshot_hash.lower()
        ):
            raise ValueError("priced accounting evidence snapshot_hash must match valuation case")
        bundle = self.accounting_evidence_bundle
        if not isinstance(bundle, Mapping):
            if self.schema_version == "valuation_case.v2":
                raise ValueError(
                    "priced ValuationCase v2 evidence requires AccountingEvidenceBundleV1"
                )
            return self
        if (
            bundle.get("schema_version") != "accounting_evidence_bundle.v1"
            or bundle.get("canonicalization") != "RFC8785"
        ):
            raise ValueError("accounting evidence bundle schema is invalid")
        if (
            bundle.get("accounting_evidence_package_hash") != package.content_hash
            or bundle.get("tenant_id") != package.tenant_id
            or bundle.get("client_id") != package.entity_id
            or bundle.get("provider_id") != package.provider_id
            or bundle.get("connection_id") != package.connection_id
            or (
                package.schema_version == "accounting_evidence_package.v3"
                and bundle.get("company_node_id") != package.company_node_id
            )
        ):
            raise ValueError("accounting evidence bundle does not match the signed package")
        bundle_material = {
            "schema_version": bundle.get("schema_version"),
            "canonicalization": bundle.get("canonicalization"),
            "provider_id": bundle.get("provider_id"),
            "tenant_id": bundle.get("tenant_id"),
            "firm_id": bundle.get("firm_id"),
            "client_id": bundle.get("client_id"),
            "connection_id": bundle.get("connection_id"),
            "company_node_id": bundle.get("company_node_id"),
            "company_name": bundle.get("company_name"),
            "source_timestamps": bundle.get("source_timestamps", []),
            "mapping_version": bundle.get("mapping_version"),
            "periods": bundle.get("periods"),
            "ledger_mappings": bundle.get("ledger_mappings", []),
            "validation_issues": bundle.get("validation_issues", []),
            "accounting_evidence_package_hash": bundle.get("accounting_evidence_package_hash"),
            "truth_ledger_hash": bundle.get("truth_ledger_hash"),
            "issued_at": bundle.get("issued_at"),
        }
        bundle_hash = _rfc8785_sha256(bundle_material)
        if (
            bundle.get("bundle_hash") != bundle_hash
            or bundle.get("bundle_id") != f"aeb_{bundle_hash[:24]}"
        ):
            raise ValueError("accounting evidence bundle hash mismatch")
        return self


def _canonical_evidence_value(value: object) -> object:
    if isinstance(value, BaseModel):
        return _canonical_evidence_value(value.model_dump(mode="json"))
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, Enum):
        return _canonical_evidence_value(value.value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _canonical_evidence_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_canonical_evidence_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def accounting_evidence_content_commitment(
    package: AccountingEvidencePackage | Mapping[str, object],
) -> JsonObject:
    """Return the complete v1 content committed by ``snapshot_hash``.

    Producers should hash a fully materialized package (including defaults),
    excluding only ``snapshot_hash``. The version marker is included both in
    the package and as the commitment envelope so later canonicalization rules
    can evolve without reinterpreting an old digest.
    """

    if isinstance(package, BaseModel):
        material = package.model_dump(mode="json", exclude={"snapshot_hash"})
    else:
        raw = dict(package)
        raw["snapshot_hash"] = "0" * 64
        # Materialize every schema default without attempting to verify the
        # caller's not-yet-computed digest.
        raw["content_hash_version"] = None
        material = AccountingEvidencePackage.model_validate(raw).model_dump(
            mode="json", exclude={"snapshot_hash"}
        )
    material["content_hash_version"] = ACCOUNTING_EVIDENCE_CONTENT_HASH_VERSION
    return {
        "content_hash_version": ACCOUNTING_EVIDENCE_CONTENT_HASH_VERSION,
        "package": material,
    }


def accounting_evidence_content_hash(
    package: AccountingEvidencePackage | Mapping[str, object],
) -> str:
    commitment = accounting_evidence_content_commitment(package)
    payload = json.dumps(
        _canonical_evidence_value(commitment),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def priced_accounting_evidence(
    valuation_case: ValuationCase | None,
) -> AccountingEvidencePackage | None:
    if valuation_case is None or valuation_case.accounting_evidence_attachment != "priced":
        return None
    package = valuation_case.accounting_evidence
    return package if isinstance(package, AccountingEvidencePackage) else None


def validate_priced_accounting_evidence_request(request: object) -> None:
    """Fail closed unless every used actual annual amount matches evidence.

    Forecast rows and ``normalized_ebitda`` are valuation assumptions rather
    than reported accounting facts. When ``reported_ebitda`` is supplied it is
    the reported baseline reconciled to evidence; otherwise the executable
    ``ebitda`` value itself must match the evidence package.
    """

    valuation_case = getattr(request, "valuation_case", None)
    package = priced_accounting_evidence(valuation_case)
    if package is None:
        return

    # Recheck model-level commitments at every pricing boundary. Pydantic
    # ``model_copy(update=...)`` deliberately skips validators and is used by
    # timeline/scenario code, so construction-time checks alone are not a
    # sufficient security boundary.
    valuation_case.bind_priced_accounting_evidence()
    if package.schema_version not in {
        "accounting_evidence_package.v2",
        "accounting_evidence_package.v3",
    }:
        raise ValueError("priced accounting evidence requires a signed AccountingEvidencePackage")
    from src.config import get_settings

    from .accounting_evidence_security import (
        parse_hermes_public_key_registry,
        verify_accounting_evidence_signature,
    )

    verify_accounting_evidence_signature(
        package.model_dump(mode="json"),
        registry=parse_hermes_public_key_registry(
            get_settings().hermes_evidence_public_key_registry_json
        ),
    )
    if package.conflicts or any(
        isinstance(year, Mapping) and bool(year.get("conflicts")) for year in package.years
    ):
        raise ValueError("priced accounting evidence cannot contain unresolved conflicts")

    request_currency = getattr(request, "currency", None)
    if not request_currency or not package.currency:
        raise ValueError(
            "priced accounting evidence requires explicit request and package currency"
        )
    if request_currency != package.currency:
        raise ValueError("priced accounting evidence currency must match CalculateRequest currency")

    for year in package.years:
        reported = year.get("reported_facts", {})
        basis = reported.get("accounting_basis") if isinstance(reported, Mapping) else None
        if isinstance(basis, Mapping) and (
            basis.get("schema_version") != "accounting-basis.v1"
            or basis.get("status") != "reconciled"
            or basis.get("deficiencies")
        ):
            raise ValueError(
                "ACCOUNTING_BASIS_UNRESOLVED: source classification, currency, period or completeness requires verification"
            )

    actual_rows = _effective_priced_actual_rows(request)
    if not actual_rows:
        raise ValueError("priced accounting evidence requires at least one actual annual fact row")

    facts_by_year_and_field: dict[tuple[int, str], list[AccountingReportedFact]] = {}
    fact_ids: set[str] = set()
    for fact in iter_accounting_reported_facts(package):
        if not fact.fact_id.strip():
            raise ValueError("priced accounting evidence fact_id cannot be empty")
        if fact.fact_id in fact_ids:
            raise ValueError(
                f"priced accounting evidence contains duplicate fact_id {fact.fact_id}"
            )
        fact_ids.add(fact.fact_id)
        if fact.fiscal_year is None:
            continue
        key = (fact.fiscal_year, fact.field_key.strip().lower())
        facts_by_year_and_field.setdefault(key, []).append(fact)

    reconciled: dict[tuple[int, str], Decimal] = {}
    for row in actual_rows:
        fiscal_year = int(getattr(row, "year"))
        row_values = vars(row)
        for field_key, value in row_values.items():
            if not isinstance(value, Decimal):
                continue
            if field_key in {"normalized_ebitda", "reported_ebitda"}:
                continue
            expected = value
            evidence_field_keys = [field_key]
            if field_key == "ebitda" and getattr(row, "reported_ebitda", None) is not None:
                expected = getattr(row, "reported_ebitda")
                # Both aliases describe reported facts. If both are present,
                # every observation must agree; one correct alias cannot hide
                # a contradictory second value.
                evidence_field_keys = ["reported_ebitda", "ebitda"]

            reconciliation_key = (fiscal_year, field_key)
            existing = reconciled.get(reconciliation_key)
            if existing is not None and existing != expected:
                raise ValueError(
                    "priced request contains conflicting annual values for "
                    f"{field_key} in FY{fiscal_year}"
                )
            reconciled[reconciliation_key] = expected
            candidates = [
                fact
                for evidence_field_key in evidence_field_keys
                for fact in facts_by_year_and_field.get((fiscal_year, evidence_field_key), [])
            ]
            if not candidates:
                raise ValueError(
                    "priced accounting evidence is missing canonical fact "
                    f"{field_key} for FY{fiscal_year}"
                )
            for fact in candidates:
                if not fact.source_refs or any(
                    not source.source_id.strip() or not source.source_kind.strip()
                    for source in fact.source_refs
                ):
                    raise ValueError(
                        "priced accounting evidence fact requires source provenance: "
                        f"{field_key} FY{fiscal_year}"
                    )
                if fact.amount is None:
                    raise ValueError(
                        "priced accounting evidence fact must carry an amount: "
                        f"{field_key} FY{fiscal_year}"
                    )
                if fact.unit != "currency" or fact.currency != request_currency:
                    raise ValueError(
                        "priced accounting evidence fact currency/unit mismatch for "
                        f"{field_key} FY{fiscal_year}"
                    )
                if fact.amount != expected:
                    raise ValueError(
                        "priced accounting evidence amount mismatch for "
                        f"{field_key} FY{fiscal_year}: "
                        f"request={expected}, evidence={fact.amount}"
                    )


def iter_accounting_reported_facts(
    package: AccountingEvidencePackage,
) -> list[AccountingReportedFact]:
    if package.reported_facts:
        if package.schema_version != "accounting_evidence_package.v1":
            raise ValueError("signed accounting packages cannot contain unsigned top-level facts")
        return list(package.reported_facts)
    facts: list[AccountingReportedFact] = []
    for year_payload in package.years:
        if not isinstance(year_payload, Mapping):
            continue
        period = year_payload.get("period")
        reported = year_payload.get("reported_facts")
        if not isinstance(period, Mapping) or not isinstance(reported, Mapping):
            continue
        fiscal_year = int(period.get("fiscal_year"))
        currency = str(period.get("currency") or package.currency or "").upper()
        reported = authoritative_reported_values(reported, currency)
        observed_at = period.get("observed_at")
        provenance_rows = year_payload.get("field_provenance")
        provenance_by_field: dict[str, Mapping[str, object]] = {}
        if isinstance(provenance_rows, Sequence):
            for row in provenance_rows:
                if isinstance(row, Mapping) and isinstance(row.get("field"), str):
                    provenance_by_field[str(row["field"])] = row
        amounts = accounting_monetary_facts(reported, currency)
        money_locator = "._money_v2.values" if "_money_v2" in reported else ""
        for field_key, amount in amounts.items():
            provenance = provenance_by_field.get(str(field_key), {})
            evidence_id = str(
                provenance.get("evidence_id") or f"{package.snapshot_id}:{fiscal_year}:{field_key}"
            )
            provider = str(provenance.get("source_system") or package.provider_id or "hermes")
            facts.append(
                AccountingReportedFact(
                    fact_id=evidence_id,
                    field_key=str(field_key),
                    fiscal_year=fiscal_year,
                    amount=amount,
                    currency=currency,
                    source_refs=[
                        AccountingSourceReference(
                            source_id=evidence_id,
                            source_kind="accounting_provider_snapshot",
                            provider=provider,
                            observed_at=observed_at,
                            document_hash=package.snapshot_hash,
                            locator=f"years[{fiscal_year}].reported_facts{money_locator}.{field_key}",
                        )
                    ],
                )
            )
    return facts


def _effective_priced_actual_rows(request: object) -> list[object]:
    current_year = getattr(request, "current_year")
    historical_years = list(getattr(request, "historical_years", []) or [])

    # Use the exact executable annual-basis rules so a no-books placeholder that
    # is re-anchored is not incorrectly treated as a priced reported period.
    from src.services.reports.stateless_calculation_helpers import (
        filter_usable_actual_years,
        maybe_reanchor_placeholder_current_year,
    )

    current_year, historical_years, _ = maybe_reanchor_placeholder_current_year(
        current_year, historical_years
    )
    rows: list[object] = []
    if not bool(getattr(current_year, "is_forecast", False)):
        rows.append(current_year)
    rows.extend(filter_usable_actual_years(historical_years))
    return rows


class CanonicalValuationRange(BaseModel):
    low: Decimal = Field(..., ge=Decimal("0"))
    mid: Decimal = Field(..., ge=Decimal("0"))
    high: Decimal = Field(..., ge=Decimal("0"))
    currency: Optional[str] = Field(None, pattern=r"^[A-Z]{3}$")
    value_basis: Literal["equity_value", "enterprise_value"]
    uncertainty_type: str = "valuation_range"

    @model_validator(mode="after")
    def validate_ordered_finite_band(self) -> "CanonicalValuationRange":
        if not all(value.is_finite() for value in (self.low, self.mid, self.high)):
            raise ValueError("valuation range values must be finite")
        if not self.low <= self.mid <= self.high:
            raise ValueError("valuation range must satisfy low <= mid <= high")
        return self

    def get(self, key: str, default: object = None) -> object:
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> object:
        return getattr(self, key)


class CanonicalCompanyProfileSnapshot(BaseModel):
    """Report-visible company identity committed by the calculation run."""

    company_name: str = Field(..., min_length=1, max_length=200)
    country_code: str = Field(..., pattern=r"^[A-Z]{2}$")
    industry: str = Field(..., min_length=1, max_length=100)
    business_model: str
    founding_year: int = Field(..., ge=1900, le=2100)
    number_of_employees: Optional[int] = Field(None, ge=0)
    registration_number: Optional[str] = Field(None, max_length=50)
    nace_code: Optional[str] = Field(None, max_length=20)
    legal_form: Optional[str] = Field(None, max_length=100)
    city: Optional[str] = Field(None, max_length=100)
    incorporated_on: Optional[str] = Field(None, max_length=20)
    business_type_id: Optional[str] = None
    business_type_label: Optional[str] = Field(None, max_length=100)


class SnapshotReference(BaseModel):
    """Immutable identity of one upstream snapshot consumed by a run."""

    snapshot_id: str
    snapshot_hash: Sha256Hex
    source_kind: str
    revision_id: Optional[str] = None
    entity_id: Optional[str] = None
    company_registry_number: Optional[str] = None
    accountant_customer_id: Optional[str] = None
    trust_class: Optional[Literal["owner_attested_private", "independently_reviewed_private"]] = (
        None
    )
    evidence_tier: Optional[Literal["T4", "T5"]] = None


class EconomicSnapshotReference(BaseModel):
    """Exact macro evidence consumed by the DCF eligibility and WACC policy."""

    schema_version: Literal["economic_snapshot.v1"]
    snapshot_id: str = Field(..., min_length=1, max_length=200)
    snapshot_hash: Sha256Hex
    snapshot_issuer: str = Field(..., min_length=1, max_length=200)
    country_code: str = Field(..., pattern=r"^[A-Z]{2}$")
    risk_free_rate_observed_at: str
    equity_risk_premium_observed_at: str
    growth_rates_observed_at: str
    source: str = Field(..., min_length=1, max_length=200)
    source_references: List[str] = Field(..., min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_source_dates(self) -> "EconomicSnapshotReference":
        for field in (
            "risk_free_rate_observed_at",
            "equity_risk_premium_observed_at",
            "growth_rates_observed_at",
        ):
            try:
                date.fromisoformat(getattr(self, field))
            except (TypeError, ValueError) as error:
                raise ValueError(f"{field} must be an ISO date") from error
        if self.source == "static_defaults":
            raise ValueError("economic snapshot source must be governed")
        if any(not reference.startswith("https://") for reference in self.source_references):
            raise ValueError("economic snapshot source references must use HTTPS")
        return self


class ClassificationResolutionSnapshot(BaseModel):
    """The exact NACE-to-business-type decision used by the valuation."""

    requested_nace_code: Optional[str] = None
    canonical_nace_code: Optional[str] = None
    business_type_id: Optional[str] = None
    business_type_label: Optional[str] = None
    resolution_level: str = "request_calibration"
    resolution_status: Literal["resolved", "manual_review_required"] = "resolved"
    confidence: Optional[Decimal] = Field(None, ge=0, le=1)
    mapping_version: Optional[str] = None
    taxonomy_version: Optional[str] = None
    reviewer_state: Optional[str] = None
    mapping_hash: Optional[Sha256Hex] = None


class BenchmarkSnapshotReference(BaseModel):
    """Metric-scoped benchmark evidence that actually entered the price."""

    metric: str
    benchmark_id: str
    snapshot_hash: Sha256Hex
    resolution_contract_id: str
    resolution_contract_hash: Sha256Hex
    dataset_version_id: Optional[str] = None
    source_dataset_version_id: Optional[str] = None
    resolution_level: Optional[str] = None
    source_benchmark_id: Optional[str] = None
    borrowed_from_country: Optional[str] = None
    borrowed_from_business_type: Optional[str] = None
    adjustments: List[JsonObject] = Field(default_factory=list)
    evidence_window: Optional[JsonObject] = None
    confidence: Optional[str] = None
    review_state: Optional[str] = None
    published_at: Optional[str] = None


class ReportSourceCitation(BaseModel):
    """Typed, report-visible citation sealed at calculation time."""

    citation_id: str
    source_kind: str
    title: Optional[str] = None
    source_id: Optional[str] = None
    provider: Optional[str] = None
    url: Optional[str] = None
    document_hash: Optional[str] = None
    locator: Optional[str] = None
    observed_at: Optional[str] = None
    published_at: Optional[str] = None
    use: Optional[str] = None


class NormalizationAdjustmentSnapshot(BaseModel):
    """Immutable report projection of one governed normalization decision."""

    adjustment_id: str
    field: str
    label: str
    original_value: Decimal
    adjusted_value: Decimal
    adjustment_amount: Decimal
    reason: str
    source: str
    status: str
    fiscal_year: Optional[int] = None
    evidence_id: Optional[str] = None
    approved_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    rule_version: Optional[str] = None


class ValuationRun(BaseModel):
    schema_version: Literal["valuation_run.v1"] = "valuation_run.v1"
    integrity_version: Literal["valuation_run_integrity.v1"] = "valuation_run_integrity.v1"
    execution_id: str = Field(
        ...,
        pattern=r"^exec_[0-9a-f]{32}$",
        description="Unique calculation invocation; calculation_hash remains deterministic.",
    )
    run_id: str
    run_hash: Sha256Hex
    valuation_id: Optional[str] = None
    case_id: str
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    country_code: Optional[str] = Field(None, min_length=2, max_length=2)
    company_profile_snapshot: CanonicalCompanyProfileSnapshot
    scenario_id: str
    evidence_revision_id: Optional[str] = None
    calculation_timestamp: str
    recording_timestamp: str
    fiscal_effective_date: Optional[str] = None
    valuation_lens_date: str
    source_as_of: Optional[str] = None
    currency: Optional[str] = Field(None, pattern=r"^[A-Z]{3}$")
    value_basis: Literal["equity_value", "enterprise_value", "mixed"] = "mixed"
    engine_version: str
    policy_version: str
    confidence_model_version: Optional[str] = None
    methodology_used: str
    input_hash: Sha256Hex
    evidence_hash: Sha256Hex
    evidence_hash_source: str
    benchmark_hash: Sha256Hex
    benchmark_hash_source: str
    calculation_hash: Sha256Hex
    review_scope_hash: Optional[Sha256Hex] = None
    audit_hash: Sha256Hex
    valuation_range: CanonicalValuationRange
    enterprise_value_range: Optional[CanonicalValuationRange] = Field(
        ...,
        description=(
            "Canonical enterprise-value range, or explicit null when the selected "
            "method is an equity-premise method for which enterprise value is not applicable."
        ),
    )
    method_mix: List[JsonObject] = Field(default_factory=list)
    method_results: JsonObject = Field(default_factory=dict)
    weighted_valuation: Optional[JsonObject] = None
    methodology_weights: JsonObject = Field(default_factory=dict)
    financial_metrics: JsonObject = Field(default_factory=dict)
    dcf_results: Optional[JsonObject] = None
    multiples_results: Optional[JsonObject] = None
    response_snapshot: JsonObject = Field(default_factory=dict)
    benchmark_snapshot: JsonObject
    calculation_lineage: JsonObject = Field(default_factory=dict)
    projection_layers: JsonObject = Field(default_factory=dict)
    qualifications: List[JsonObject] = Field(default_factory=list)
    public_valuation_audit_snapshot: Optional[JsonObject] = None
    driver_ledger: JsonObject = Field(default_factory=dict)

    @model_validator(mode="after")
    def verify_immutable_hash_commitments(self) -> "ValuationRun":
        from src.services.reports.stateless_valuation_run import (
            verify_valuation_run_integrity,
        )

        if self.company_name != self.company_profile_snapshot.company_name:
            raise ValueError("valuation_run company_name must match company_profile_snapshot")
        if self.country_code != self.company_profile_snapshot.country_code:
            raise ValueError("valuation_run country_code must match company_profile_snapshot")
        verify_valuation_run_integrity(self)
        return self


class ValuationRunV2(ValuationRun):
    """T4-506 calculation run with report-critical evidence pinned in identity."""

    schema_version: Literal["valuation_run.v2"] = "valuation_run.v2"
    integrity_version: Literal["valuation_run_integrity.v2"] = "valuation_run_integrity.v2"
    accounting_evidence_bundle_hash: Optional[Sha256Hex] = None
    country_pack_schema_version: Literal["country_pack.v1"]
    country_pack_version: str = Field(..., min_length=1, max_length=96)
    economic_snapshot: Optional[EconomicSnapshotReference] = None
    economic_snapshot_status: Literal[
        "used_for_dcf",
        "valuation_iq_modeled_public_dcf",
        "available_not_used",
        "not_supplied",
    ] = "not_supplied"
    company_snapshot: SnapshotReference
    uploaded_data_snapshot: Optional[SnapshotReference] = None
    uploaded_data_snapshot_status: Literal["priced", "attested_non_priced", "not_supplied"] = (
        "not_supplied"
    )
    classification_resolution: ClassificationResolutionSnapshot
    benchmark_snapshot_references: List[BenchmarkSnapshotReference] = Field(default_factory=list)
    source_citations: List[ReportSourceCitation] = Field(default_factory=list)
    normalization_adjustments: List[NormalizationAdjustmentSnapshot] = Field(default_factory=list)
    normalization_adjustments_hash: Sha256Hex
    review_scope_hash: Sha256Hex
    report_review_decisions: List[GovernedReportReviewDecision] = Field(default_factory=list)
    content_provenance: ReportContentProvenanceSnapshot = Field(
        default_factory=ReportContentProvenanceSnapshot
    )
    assurance: ReportAssuranceContract = Field(default_factory=ReportAssuranceContract)

    @model_validator(mode="after")
    def bind_uploaded_snapshot_status(self) -> "ValuationRunV2":
        from src.services.reports.stateless_valuation_run import canonical_hash
        from src.services.reports.source_policy_contracts import (
            validate_optional_source_policy_contracts,
        )

        validate_optional_source_policy_contracts(self.calculation_lineage, currency=self.currency)

        mapping_hash = self.classification_resolution.mapping_hash
        if mapping_hash is None:
            raise ValueError("valuation_run.v2 classification mapping_hash is required")
        mapping_material = self.classification_resolution.model_dump(
            mode="json", exclude={"mapping_hash"}
        )
        if mapping_hash.lower() != canonical_hash(mapping_material):
            raise ValueError(
                "valuation_run.v2 classification mapping_hash does not match its canonical mapping"
            )

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
            if not snapshot.entity_id or snapshot.entity_id != self.company_id:
                raise ValueError(
                    "attested_non_priced snapshot entity_id must match valuation_run.company_id"
                )
            profile_registry = _normalized_registry_number(
                self.company_profile_snapshot.registration_number
            )
            snapshot_registry = _normalized_registry_number(snapshot.company_registry_number)
            if profile_registry and snapshot_registry and profile_registry != snapshot_registry:
                raise ValueError(
                    "attested_non_priced snapshot registry number must match company profile"
                )
        economic_status = self.economic_snapshot_status
        snapshot_absent_statuses = {
            "not_supplied",
            "valuation_iq_modeled_public_dcf",
        }
        if (self.economic_snapshot is None) != (economic_status in snapshot_absent_statuses):
            raise ValueError("economic_snapshot and economic_snapshot_status are inconsistent")
        dcf_weight = Decimal(str(self.methodology_weights.get("dcf", 0)))
        audit = self.public_valuation_audit_snapshot or {}
        modeled_public_dcf = audit.get("modeled_dcf") or {}
        modeled_public_dcf_valid = bool(
            audit.get("schema_version") == "public_valuation_audit.v3"
            and audit.get("approach") in {"income", "hybrid"}
            and isinstance(modeled_public_dcf, dict)
            and modeled_public_dcf.get("schema_version") == "public_modeled_dcf_resolution.v1"
            and modeled_public_dcf.get("authority") == "valuation_iq"
            and modeled_public_dcf.get("policy_version")
            in {
                "valuation_iq_public_dcf_defaults.v1",
                "valuation_iq_public_dcf_defaults.v2",
                "valuation_iq_public_dcf_defaults.v3",
                "valuation_iq_public_dcf_defaults.v4",
            }
            and isinstance(modeled_public_dcf.get("resolution_hash"), str)
            and re.fullmatch(
                r"sha256:[0-9a-f]{64}",
                str(modeled_public_dcf.get("resolution_hash")),
            )
            and modeled_public_dcf.get("forecast_classification")
            == "modeled_forward_assumptions_not_actuals"
            and isinstance(modeled_public_dcf.get("assumptions"), dict)
            and isinstance(modeled_public_dcf.get("free_cash_flow_projection"), list)
            and len(modeled_public_dcf.get("free_cash_flow_projection") or []) >= 3
        )
        timeline_projection = self.calculation_lineage.get("timeline_projection")
        projection_target_year = (
            int(timeline_projection.get("target_fiscal_year") or 0)
            if isinstance(timeline_projection, dict)
            else 0
        )
        fiscal_effective_year = (
            int(str(self.fiscal_effective_date)[:4])
            if self.fiscal_effective_date
            and len(str(self.fiscal_effective_date)) >= 4
            and str(self.fiscal_effective_date)[:4].isdigit()
            else 0
        )
        sealed_non_releasable_projection = bool(
            isinstance(timeline_projection, dict)
            and timeline_projection.get("calculation_purpose") == "current_lens_timeline_projection"
            and timeline_projection.get("independent_release_authorized") is False
            and timeline_projection.get("headline_review_receipt_applied") is False
            and timeline_projection.get("release_policy")
            == "projection_only_not_independently_releasable"
            and projection_target_year > 0
            and projection_target_year == fiscal_effective_year
        )
        if dcf_weight > 0 and economic_status not in {
            "used_for_dcf",
            "valuation_iq_modeled_public_dcf",
        }:
            raise ValueError(
                "a priced DCF leg requires a governed economic snapshot or "
                "ValuationIQ-modeled public DCF resolution"
            )
        if (
            economic_status == "valuation_iq_modeled_public_dcf"
            and not modeled_public_dcf_valid
            and not sealed_non_releasable_projection
        ):
            raise ValueError("modeled public DCF status requires a sealed ValuationIQ public audit")
        if economic_status == "used_for_dcf" and dcf_weight <= 0:
            raise ValueError("economic_snapshot cannot be labelled used_for_dcf at zero DCF weight")
        if economic_status == "valuation_iq_modeled_public_dcf" and dcf_weight <= 0:
            raise ValueError("modeled public DCF status requires a positive DCF weight")
        for decision in self.report_review_decisions:
            if decision.scope_id.lower() != self.review_scope_hash.lower():
                # Name both hashes: the review flow is two-pass (compute the
                # run's scope hash first, then sign the decision against it),
                # and an error that hides the expected value forces operators
                # to rerun a whole calculation just to learn the target.
                raise ValueError(
                    "report review decision must scope the valuation_run review_scope_hash "
                    f"(expected review_scope_hash {self.review_scope_hash}, decision "
                    f"{decision.decision_id or '<unnamed>'} scopes {decision.scope_id})"
                )
        return self


def _normalized_registry_number(value: object) -> str:
    normalized = "".join(character for character in str(value or "").upper() if character.isalnum())
    if len(normalized) > 2 and normalized[:2].isalpha():
        normalized = normalized[2:]
    return normalized.lstrip("0") or normalized


class ValuationInputFieldSpec(BaseModel):
    field_id: str
    path: str
    data_type: str
    required: bool
    description: Optional[str] = None
    unit: str
    currency_treatment: str
    business_applicability: List[str] = Field(default_factory=list)
    evidence_requirement: str
    validation: JsonObject = Field(default_factory=dict)
    provenance_requirement: str
    affects_value: bool
    affects_uncertainty: bool


class ValuationInputCatalog(BaseModel):
    schema_version: Literal["valuation_input_catalog.v1"] = "valuation_input_catalog.v1"
    request_schema: str = "CalculateRequest.v2"
    fields: List[ValuationInputFieldSpec]
    conditional_sections: List[JsonObject] = Field(default_factory=list)
    monetary_policy: JsonObject = Field(default_factory=dict)
