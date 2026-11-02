"""Authenticate Titan's final valuation-assurance report authority.

The ValuationRun hash proves calculation consistency.  It does not prove that
Titan admitted the evidence, resolved the current decision/observation heads,
or authorized a particular audience to receive a report.  This module mirrors
Titan's ``ValuationAssuranceEnvelopeV2`` wire exactly and verifies its detached
Ed25519 signature over the SHA-256 digest of the RFC-8785 unsigned envelope.

There is deliberately no signing helper here.  ValuationIQ can verify Titan's
rotating, pinned keys; it cannot mint its own T4/T5 or publication authority,
including in local development.
"""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

import rfc8785
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.api.schemas.valuation_contracts import Sha256Hex, ValuationRunV2

VALUATION_ASSURANCE_ENVELOPE_SCHEMA = "ValuationAssuranceEnvelopeV2"
VALUATION_ASSURANCE_ENVELOPE_CONTENT = "valuation_assurance_envelope_content.v2.audience_band"
VALUATION_ASSURANCE_CONTRACT_REVISION = "v2_audience_band"


class _StrictWireModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ValuationAssuranceEvidenceConfidence(_StrictWireModel):
    score: str = Field(..., min_length=1)
    band: Literal["low", "medium", "high"]
    components: dict[str, Any]
    model_version: str = Field(..., min_length=1)

    @field_validator("score")
    @classmethod
    def validate_decimal_score(cls, value: str) -> str:
        try:
            score = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("assurance evidence-confidence score must be Decimal text") from exc
        if not score.is_finite() or score < 0 or score > 100:
            raise ValueError("assurance evidence-confidence score must be between 0 and 100")
        return value


class ValuationAssuranceCalculationCertification(_StrictWireModel):
    status: Literal["certified", "certified_with_qualifications"]
    manifest_id: str = Field(..., min_length=1)
    manifest_hash: Sha256Hex
    scopes: dict[str, Any]


class ValuationAssuranceLegalAttestation(_StrictWireModel):
    status: Literal["not_attested", "signed"]
    record_id: str | None
    artifact_hash: Sha256Hex | None
    signer_id: str | None
    signer_firm: str | None
    scope: dict[str, Any]
    signed_at: str | None

    @model_validator(mode="after")
    def bind_signed_fields(self) -> "ValuationAssuranceLegalAttestation":
        values = (self.record_id, self.artifact_hash, self.signer_id, self.signed_at)
        if self.status == "signed" and any(value is None for value in values):
            raise ValueError("signed legal assurance requires record, artifact, signer and time")
        if self.status == "signed" and not self.scope:
            raise ValueError("signed legal assurance requires an explicit attestation scope")
        if self.status == "not_attested" and (
            any(value is not None for value in (*values, self.signer_firm)) or self.scope
        ):
            raise ValueError("not-attested legal assurance cannot carry signed authority")
        if self.signed_at is not None:
            _parse_timestamp(self.signed_at, field="legal_attestation.signed_at")
        return self


class ValuationAssuranceOutcomeAccuracy(_StrictWireModel):
    status: Literal["not_observed", "recorded_unmeasured", "measured"]
    observation_id: str | None
    observation_hash: Sha256Hex | None
    review_status: Literal["not_applicable", "pending_dual_review", "dual_reviewed", "rejected"]
    review_hashes: list[Sha256Hex]

    @model_validator(mode="after")
    def bind_outcome_fields(self) -> "ValuationAssuranceOutcomeAccuracy":
        if self.review_hashes != sorted(set(self.review_hashes)):
            raise ValueError("outcome review hashes must be sorted and unique")
        if self.status == "not_observed":
            if (
                self.observation_id is not None
                or self.observation_hash is not None
                or self.review_status != "not_applicable"
                or self.review_hashes
            ):
                raise ValueError("not-observed outcome cannot carry outcome authority")
        elif self.observation_id is None or self.observation_hash is None:
            raise ValueError("recorded outcome requires an observation id and hash")
        if self.status == "measured" and self.review_status != "dual_reviewed":
            raise ValueError("measured outcome accuracy requires dual review")
        return self


class ValuationAssurancePublication(_StrictWireModel):
    authority_type: Literal["private_graph_snapshot", "buyer_disclosure_bundle"]
    authority_id: str = Field(..., min_length=1)
    authority_hash: Sha256Hex
    effective_at: str
    expires_at: str
    limitations: list[Any]
    revoked_at: str | None

    @model_validator(mode="after")
    def bind_publication_window(self) -> "ValuationAssurancePublication":
        effective = _parse_timestamp(self.effective_at, field="publication.effective_at")
        expires = _parse_timestamp(self.expires_at, field="publication.expires_at")
        if expires <= effective:
            raise ValueError("assurance publication expiry must follow its effective time")
        if self.revoked_at is not None:
            _parse_timestamp(self.revoked_at, field="publication.revoked_at")
        return self


class ValuationAssuranceAudienceDisplayBand(_StrictWireModel):
    schema_version: Literal["valuation_assurance_audience_display_band.v1"]
    derivation_policy_version: Literal["audience_band_floor.v1"]
    source_observation_id: str = Field(..., min_length=1)
    value_basis: Literal["equity_value", "enterprise_value"]
    currency: str = Field(..., pattern=r"^[A-Z]{3}$")
    raw_low: str = Field(..., pattern=r"^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")
    raw_mid: str = Field(..., pattern=r"^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")
    raw_high: str = Field(..., pattern=r"^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")
    display_low: str = Field(..., pattern=r"^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")
    display_mid: str = Field(..., pattern=r"^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")
    display_high: str = Field(..., pattern=r"^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")
    minimum_half_width: Literal["0.30", "0.18", "0.12", "0.08", "0.05"]

    @model_validator(mode="after")
    def validate_decimal_band(self) -> "ValuationAssuranceAudienceDisplayBand":
        values: list[Decimal] = []
        for field in (
            "raw_low",
            "raw_mid",
            "raw_high",
            "display_low",
            "display_mid",
            "display_high",
        ):
            try:
                value = Decimal(getattr(self, field))
            except InvalidOperation as exc:
                raise ValueError(f"audience display band {field} must be Decimal text") from exc
            if not value.is_finite():
                raise ValueError(f"audience display band {field} must be finite")
            values.append(value)
        raw_low, raw_mid, raw_high, display_low, display_mid, display_high = values
        floor = Decimal(self.minimum_half_width)
        all_zero = all(value == 0 for value in values)
        if not all_zero and (
            raw_low < 0
            or raw_mid <= 0
            or raw_low > raw_mid
            or raw_mid > raw_high
            or display_low < 0
            or display_low > raw_low
            or display_mid != raw_mid
            or display_high < raw_high
            or display_low > display_mid
            or display_mid > display_high
            or display_mid - display_low < display_mid * floor
            or display_high - display_mid < display_mid * floor
        ):
            raise ValueError("audience display band does not preserve raw values and its floor")
        return self


class ValuationAssuranceEnvelopeV2(_StrictWireModel):
    """Byte-compatible Pydantic contract for Titan's audience-band assurance wire."""

    schema_version: Literal["ValuationAssuranceEnvelopeV2"]
    content_hash_version: Literal["valuation_assurance_envelope_content.v2.audience_band"]
    assurance_contract_revision: Literal["v2_audience_band"]
    canonicalization: Literal["RFC8785"]
    signature_algorithm: Literal["Ed25519-SHA256"]
    issuer: str = Field(..., min_length=1)
    key_id: str = Field(..., min_length=1)
    issued_at: str
    component_hash: Sha256Hex
    company_node_ref_id: str = Field(..., min_length=1)
    audience: Literal["owner", "advisor", "buyer"]
    maturity_snapshot_id: str = Field(..., min_length=1)
    workspace_company_id: str | None
    valuation_report_id: str = Field(..., min_length=1)
    advisor_verification_receipt_id: str = Field(..., min_length=1)
    evidence_admission_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    run_hash: Sha256Hex
    calculation_hash: Sha256Hex
    case_id: str = Field(..., min_length=1)
    case_attestation_hash: Sha256Hex
    case_hash: Sha256Hex
    evidence_revision_id: str = Field(..., min_length=1)
    evidence_snapshot_id: str = Field(..., min_length=1)
    evidence_hash: Sha256Hex
    evidence_content_hash: Sha256Hex
    decision_set_hash: Sha256Hex
    observation_ids: list[str] = Field(..., min_length=1)
    observation_set_hash: Sha256Hex
    graph_tier: Literal["T4", "T5"]
    public_value_grade: str | None
    private_graph_grade: Literal["T4-A", "T4-Q", "T4-C"]
    graph_revision: str = Field(..., min_length=1)
    maturity_ruleset_version: str = Field(..., min_length=1)
    maturity_snapshot_fingerprint: str = Field(..., min_length=1)
    audience_display_band: ValuationAssuranceAudienceDisplayBand
    evidence_confidence: ValuationAssuranceEvidenceConfidence
    calculation_certification: ValuationAssuranceCalculationCertification
    legal_attestation: ValuationAssuranceLegalAttestation
    outcome_accuracy: ValuationAssuranceOutcomeAccuracy
    publication: ValuationAssurancePublication
    supersedes_envelope_id: str | None
    content_hash: Sha256Hex
    detached_signature: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def bind_internal_heads(self) -> "ValuationAssuranceEnvelopeV2":
        if self.observation_ids != sorted(set(self.observation_ids)):
            raise ValueError("assurance observation_ids must be sorted and unique")
        if self.observation_set_hash != valuation_assurance_hash(self.observation_ids):
            raise ValueError("assurance observation_set_hash does not match observation_ids")
        if self.graph_tier == "T5" and self.private_graph_grade != "T4-C":
            raise ValueError("T5 assurance requires T4-C private-graph maturity")
        if self.audience == "buyer" and self.graph_tier != "T5":
            raise ValueError("buyer assurance requires T5")
        if self.audience == "buyer":
            if self.publication.authority_type != "buyer_disclosure_bundle":
                raise ValueError("buyer assurance requires buyer-disclosure publication authority")
        elif self.publication.authority_type != "private_graph_snapshot":
            raise ValueError(
                "owner and advisor assurance require private-graph publication authority"
            )
        expected_floor = (
            "0.05"
            if self.audience == "buyer"
            else (
                "0.08"
                if self.graph_tier == "T5"
                else {"T4-A": "0.30", "T4-Q": "0.18", "T4-C": "0.12"}[self.private_graph_grade]
            )
        )
        if self.audience_display_band.minimum_half_width != expected_floor:
            raise ValueError("audience display band floor does not match maturity and audience")
        if self.audience_display_band.source_observation_id not in self.observation_ids:
            raise ValueError("audience display band is outside the assured observation set")
        expected_component = valuation_assurance_hash(
            {
                field: _json_wire_value(getattr(self, field))
                for field in _COMPONENT_COMMITMENT_FIELDS
            }
        )
        if self.component_hash != expected_component:
            raise ValueError("assurance component_hash does not match governed components")
        _parse_timestamp(self.issued_at, field="issued_at")
        return self


_COMPONENT_COMMITMENT_FIELDS = (
    "company_node_ref_id",
    "audience",
    "maturity_snapshot_id",
    "workspace_company_id",
    "valuation_report_id",
    "advisor_verification_receipt_id",
    "evidence_admission_id",
    "run_id",
    "run_hash",
    "calculation_hash",
    "case_id",
    "case_attestation_hash",
    "case_hash",
    "evidence_revision_id",
    "evidence_snapshot_id",
    "evidence_hash",
    "evidence_content_hash",
    "decision_set_hash",
    "observation_ids",
    "observation_set_hash",
    "graph_tier",
    "public_value_grade",
    "private_graph_grade",
    "graph_revision",
    "maturity_ruleset_version",
    "maturity_snapshot_fingerprint",
    "audience_display_band",
    "evidence_confidence",
    "calculation_certification",
    "legal_attestation",
    "outcome_accuracy",
    "publication",
)


def _parse_timestamp(value: object, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _json_wire_value(value: object) -> object:
    if value is None or isinstance(value, (str, bool, int, float)):
        if isinstance(value, float) and not (float("-inf") < value < float("inf")):
            raise ValueError("assurance envelope contains a non-finite JSON number")
        return value
    if isinstance(value, Decimal):
        raise ValueError("assurance envelope Decimal values must use JSON strings")
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError("assurance envelope JSON object keys must be strings")
            result[key] = _json_wire_value(child)
        return result
    if isinstance(value, (list, tuple)):
        return [_json_wire_value(child) for child in value]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _json_wire_value(model_dump(mode="python"))
    raise ValueError("assurance envelope contains a non-JSON value")


def valuation_assurance_hash(value: object) -> str:
    return hashlib.sha256(rfc8785.dumps(_json_wire_value(value))).hexdigest()


def parse_titan_valuation_assurance_public_key_registry(
    raw_json: str,
) -> dict[str, dict[str, object]]:
    try:
        payload = json.loads(raw_json or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Titan valuation-assurance public-key registry must be valid JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError("Titan valuation-assurance public-key registry must be a JSON object")
    registry: dict[str, dict[str, object]] = {}
    for key_id, entry in payload.items():
        if not isinstance(key_id, str) or not key_id.strip() or not isinstance(entry, dict):
            raise ValueError(
                "Titan valuation-assurance registry entries require a non-empty key_id object"
            )
        registry[key_id] = dict(entry)
    return registry


def _canonical_base64(value: object, *, length: int, field: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} is required")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise ValueError(f"{field} must be canonical base64") from exc
    if len(decoded) != length or base64.b64encode(decoded).decode("ascii") != value:
        raise ValueError(f"{field} must be canonical base64")
    return decoded


def _unsigned_envelope(envelope: ValuationAssuranceEnvelopeV2) -> dict[str, object]:
    payload = envelope.model_dump(mode="python")
    payload.pop("content_hash")
    payload.pop("detached_signature")
    return _json_wire_value(payload)  # type: ignore[return-value]


def verify_valuation_assurance_envelope(
    envelope: ValuationAssuranceEnvelopeV2,
    *,
    registry: Mapping[str, Mapping[str, object]],
    now: datetime | None = None,
) -> None:
    """Verify Titan origin, current key validity and publication validity."""

    check_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    issued_at = _parse_timestamp(envelope.issued_at, field="issued_at")
    if issued_at > check_time:
        raise ValueError("valuation-assurance envelope was issued in the future")
    entry = registry.get(envelope.key_id)
    if entry is None:
        raise ValueError("Titan valuation-assurance key_id is unknown")
    if entry.get("revoked") is True:
        raise ValueError("Titan valuation-assurance signing key is revoked")
    if entry.get("issuer") != envelope.issuer:
        raise ValueError("Titan valuation-assurance issuer does not match key registry")
    if entry.get("not_before") is not None:
        not_before = _parse_timestamp(entry["not_before"], field="key not_before")
        if issued_at < not_before or check_time < not_before:
            raise ValueError("Titan valuation-assurance signing key is not yet valid")
    if entry.get("not_after") is not None:
        not_after = _parse_timestamp(entry["not_after"], field="key not_after")
        if issued_at > not_after or check_time > not_after:
            raise ValueError("Titan valuation-assurance signing key is expired")

    digest = hashlib.sha256(rfc8785.dumps(_unsigned_envelope(envelope))).digest()
    if envelope.content_hash != digest.hex():
        raise ValueError("valuation-assurance content hash does not match RFC8785 payload")
    raw_public_key = _canonical_base64(
        entry.get("public_key_b64"), length=32, field="valuation-assurance public key"
    )
    signature = _canonical_base64(
        envelope.detached_signature,
        length=64,
        field="valuation-assurance detached signature",
    )
    try:
        Ed25519PublicKey.from_public_bytes(raw_public_key).verify(signature, digest)
    except InvalidSignature as exc:
        raise ValueError("valuation-assurance signature verification failed") from exc

    effective = _parse_timestamp(
        envelope.publication.effective_at, field="publication.effective_at"
    )
    expires = _parse_timestamp(envelope.publication.expires_at, field="publication.expires_at")
    if effective > check_time:
        raise ValueError("valuation-assurance publication is not yet effective")
    if expires <= check_time:
        raise ValueError("valuation-assurance publication has expired")
    if envelope.publication.revoked_at is not None:
        raise ValueError("valuation-assurance publication is revoked")


def bind_valuation_assurance_to_report(
    envelope: ValuationAssuranceEnvelopeV2,
    *,
    run: ValuationRunV2,
    report_id: str,
    audience: str,
    observation_ids: list[str],
    headline_value_basis: str,
    headline_currency: str,
    headline_low: Decimal,
    headline_mid: Decimal,
    headline_high: Decimal,
) -> None:
    """Bind the verified Titan authority to one exact calculation/report view."""

    direct_bindings = {
        "company_node_ref_id": (envelope.company_node_ref_id, run.company_id),
        "valuation_report_id": (envelope.valuation_report_id, report_id),
        "audience": (envelope.audience, audience),
        "run_id": (envelope.run_id, run.run_id),
        "run_hash": (envelope.run_hash, run.run_hash),
        "calculation_hash": (envelope.calculation_hash, run.calculation_hash),
        "case_id": (envelope.case_id, run.case_id),
        "evidence_revision_id": (envelope.evidence_revision_id, run.evidence_revision_id),
    }
    for field, (assured, committed) in direct_bindings.items():
        if assured != committed:
            raise ValueError(f"valuation-assurance {field} does not match report/run")
    if envelope.observation_ids != observation_ids:
        raise ValueError("valuation-assurance observation_ids do not match report request")
    display_band = envelope.audience_display_band
    if (
        display_band.value_basis != headline_value_basis
        or display_band.currency != headline_currency
        or Decimal(display_band.raw_low) != headline_low
        or Decimal(display_band.raw_mid) != headline_mid
        or Decimal(display_band.raw_high) != headline_high
    ):
        raise ValueError(
            "valuation-assurance audience display band does not match the sealed headline"
        )

    lineage = run.calculation_lineage
    if not isinstance(lineage, Mapping):
        raise ValueError("valuation run has no case/evidence lineage for assurance")
    lineage_bindings = {
        "case_attestation_hash": (
            envelope.case_attestation_hash,
            lineage.get("valuation_case_attestation_content_hash"),
        ),
        "case_hash": (envelope.case_hash, lineage.get("valuation_case_hash")),
        "evidence_hash": (envelope.evidence_hash, lineage.get("evidence_hash")),
        "decision_set_hash": (envelope.decision_set_hash, lineage.get("decision_set_hash")),
        "evidence_revision_id": (
            envelope.evidence_revision_id,
            lineage.get("evidence_revision_id"),
        ),
    }
    for field, (assured, committed) in lineage_bindings.items():
        if assured != committed:
            raise ValueError(f"valuation-assurance {field} does not match calculation lineage")

    nodes = lineage.get("nodes")
    reported_facts = (
        next(
            (
                node
                for node in nodes
                if isinstance(nodes, list)
                and isinstance(node, Mapping)
                and node.get("id") == "reported_facts"
            ),
            None,
        )
        if isinstance(nodes, list)
        else None
    )
    if not isinstance(reported_facts, Mapping):
        raise ValueError("valuation run has no priced reported-facts lineage")
    evidence_bindings = {
        "evidence_snapshot_id": (
            envelope.evidence_snapshot_id,
            reported_facts.get("snapshot_id"),
        ),
        "evidence_content_hash": (
            envelope.evidence_content_hash,
            reported_facts.get("hash"),
        ),
        "evidence_revision_id": (
            envelope.evidence_revision_id,
            reported_facts.get("evidence_revision_id"),
        ),
    }
    for field, (assured, committed) in evidence_bindings.items():
        if assured != committed:
            raise ValueError(f"valuation-assurance {field} does not match reported evidence")
    if (
        reported_facts.get("attachment") != "priced"
        or reported_facts.get("content_hash_version") != "accounting_evidence_content.v3"
    ):
        raise ValueError("T4/T5 assurance requires priced AccountingEvidencePackage v3")

    scopes = envelope.calculation_certification.scopes
    manifest_hash = envelope.calculation_certification.manifest_hash
    for scope_name in ("arithmetic", "methodology", "value_basis", "parity"):
        scope = scopes.get(scope_name)
        if (
            not isinstance(scope, Mapping)
            or scope.get("status") != "certified"
            or scope.get("manifest_hash") != manifest_hash
        ):
            raise ValueError(f"valuation-assurance {scope_name} certification scope is invalid")
    country_scope = scopes.get("country")
    if (
        not isinstance(country_scope, Mapping)
        or country_scope.get("status") != "certified"
        or country_scope.get("manifest_hash") != manifest_hash
        or country_scope.get("country_code") != run.country_code
        or country_scope.get("country_pack_version") != run.country_pack_version
    ):
        raise ValueError("valuation-assurance country certification scope does not match run")
