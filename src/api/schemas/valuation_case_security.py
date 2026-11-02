"""Verify Titan's immutable valuation-case pricing authority.

The case signature binds the complete server-resolved decision envelope and
the exact benchmark, economic and country selectors sent to ValuationIQ.  A
plain SHA-256 commitment proves consistency only; the Ed25519 signature is the
origin-authentication boundary that prevents a caller from minting accepted
monetary authority by recomputing public hashes.
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Mapping

import rfc8785
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

VALUATION_CASE_ATTESTATION_SCHEMA = "valuation_case_attestation.v1"
VALUATION_CASE_ATTESTATION_CONTENT = "valuation_case_attestation_content.v1"
VALUATION_CASE_ATTESTATION_COMMITTED_FIELDS = (
    "schema_version",
    "content_hash_version",
    "canonicalization",
    "signature_algorithm",
    "issuer",
    "key_id",
    "issued_at",
    "company_id",
    "case_id",
    "evidence_revision_id",
    "case_hash",
    "evidence_hash",
    "decision_set_hash",
    "benchmark_hash",
    "economic_snapshot_hash",
    "country_pack_hash",
    "policy_hash",
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
    """Return the same JSON-only material accepted by Titan's RFC-8785 sealer."""

    if value is None or isinstance(value, (str, bool, int, float)):
        if isinstance(value, float) and not (float("-inf") < value < float("inf")):
            raise ValueError("valuation case contains a non-finite JSON number")
        return value
    if isinstance(value, Decimal):
        # Monetary authority is transported as a decimal string. Rejecting a
        # Decimal object here prevents accidental byte changes after parsing.
        raise ValueError("valuation case signed Decimal values must use JSON strings")
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError("valuation case JSON object keys must be strings")
            result[key] = _json_wire_value(child)
        return result
    if isinstance(value, (list, tuple)):
        return [_json_wire_value(child) for child in value]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _json_wire_value(model_dump(mode="json"))
    raise ValueError("valuation case contains a non-JSON value")


def valuation_case_sha256(value: object) -> str:
    return hashlib.sha256(rfc8785.dumps(_json_wire_value(value))).hexdigest()


def parse_titan_valuation_case_public_key_registry(
    raw_json: str,
) -> dict[str, dict[str, object]]:
    try:
        payload = json.loads(raw_json or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("Titan valuation-case public-key registry must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("Titan valuation-case public-key registry must be a JSON object")
    registry: dict[str, dict[str, object]] = {}
    for key_id, entry in payload.items():
        if not isinstance(key_id, str) or not key_id.strip() or not isinstance(entry, dict):
            raise ValueError(
                "Titan valuation-case registry entries require a non-empty key_id object"
            )
        registry[key_id] = dict(entry)
    return registry


def valuation_case_attestation_digest(attestation: Mapping[str, object]) -> bytes:
    commitment = {
        key: _json_wire_value(attestation.get(key))
        for key in VALUATION_CASE_ATTESTATION_COMMITTED_FIELDS
    }
    return hashlib.sha256(rfc8785.dumps(commitment)).digest()


def valuation_case_component_hashes(
    valuation_case: Mapping[str, object],
    *,
    benchmark_contract: object,
    economic_context: object,
    country_pack_selector: Mapping[str, object],
    external_market_reference_contract: object = None,
    wacc_evidence_contract: object = None,
    real_estate_yield_evidence_contract: object = None,
) -> dict[str, str]:
    unsigned_case = {
        key: _json_wire_value(value)
        for key, value in valuation_case.items()
        if key != "case_attestation"
    }
    # Keep the original commitment bytes for every case without a governed
    # external reference. A priced reference upgrades the commitment shape so
    # a legacy signature over only benchmark_contract cannot authorize it.
    benchmark_commitment = (
        {
            "schema_version": "valuation_case_benchmark_commitment.v1",
            "benchmark_contract": _json_wire_value(benchmark_contract),
        }
        if external_market_reference_contract is None
        and real_estate_yield_evidence_contract is None
        else (
            {
                "schema_version": "valuation_case_benchmark_commitment.v2",
                "benchmark_contract": _json_wire_value(benchmark_contract),
                "external_market_reference_contract": _json_wire_value(
                    external_market_reference_contract
                ),
            }
            if real_estate_yield_evidence_contract is None
            else {
                "schema_version": "valuation_case_benchmark_commitment.v3",
                "benchmark_contract": _json_wire_value(benchmark_contract),
                "external_market_reference_contract": _json_wire_value(
                    external_market_reference_contract
                ),
                "real_estate_yield_evidence_contract": _json_wire_value(
                    real_estate_yield_evidence_contract
                ),
            }
        )
    )
    economic_commitment = (
        {
            "schema_version": "valuation_case_economic_commitment.v1",
            "economic_context": _json_wire_value(economic_context),
        }
        if wacc_evidence_contract is None
        else {
            "schema_version": "valuation_case_economic_commitment.v2",
            "economic_context": _json_wire_value(economic_context),
            "wacc_evidence_contract": _json_wire_value(wacc_evidence_contract),
        }
    )
    accounting_evidence_bundle = valuation_case.get("accounting_evidence_bundle")
    evidence_commitment = (
        {
            "schema_version": "valuation_case_evidence_commitment.v1",
            "evidence_revision_id": valuation_case.get("evidence_revision_id"),
            "accounting_evidence_attachment": valuation_case.get("accounting_evidence_attachment"),
            "accounting_evidence_snapshot_id": valuation_case.get(
                "accounting_evidence_snapshot_id"
            ),
            "accounting_evidence_snapshot_hash": valuation_case.get(
                "accounting_evidence_snapshot_hash"
            ),
            "accounting_evidence": _json_wire_value(valuation_case.get("accounting_evidence")),
        }
        if accounting_evidence_bundle is None
        else {
            "schema_version": "valuation_case_evidence_commitment.v2",
            "evidence_revision_id": valuation_case.get("evidence_revision_id"),
            "accounting_evidence_attachment": valuation_case.get("accounting_evidence_attachment"),
            "accounting_evidence_snapshot_id": valuation_case.get(
                "accounting_evidence_snapshot_id"
            ),
            "accounting_evidence_snapshot_hash": valuation_case.get(
                "accounting_evidence_snapshot_hash"
            ),
            "accounting_evidence": _json_wire_value(valuation_case.get("accounting_evidence")),
            "accounting_evidence_bundle": _json_wire_value(accounting_evidence_bundle),
        }
    )
    return {
        "case_hash": valuation_case_sha256(unsigned_case),
        "evidence_hash": valuation_case_sha256(evidence_commitment),
        "benchmark_hash": valuation_case_sha256(benchmark_commitment),
        "economic_snapshot_hash": valuation_case_sha256(economic_commitment),
        "country_pack_hash": valuation_case_sha256(country_pack_selector),
        "policy_hash": valuation_case_sha256(
            {
                "schema_version": "valuation_case_policy_commitment.v1",
                "policy_version": valuation_case.get("policy_version"),
            }
        ),
    }


def _verify_registry_and_signature(
    attestation: Mapping[str, object],
    *,
    registry: Mapping[str, Mapping[str, object]],
    now: datetime | None,
) -> None:
    key_id = attestation.get("key_id")
    issuer = attestation.get("issuer")
    if not isinstance(key_id, str) or key_id not in registry:
        raise ValueError("Titan valuation-case key_id is unknown")
    entry = registry[key_id]
    if entry.get("revoked") is True:
        raise ValueError("Titan valuation-case signing key is revoked")
    if not isinstance(issuer, str) or entry.get("issuer") != issuer:
        raise ValueError("Titan valuation-case issuer does not match key registry")

    issued_at = _parse_timestamp(attestation.get("issued_at"), field="issued_at")
    check_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if issued_at > check_time:
        raise ValueError("Titan valuation-case issued_at cannot be in the future")
    if entry.get("not_before") is not None:
        not_before = _parse_timestamp(entry["not_before"], field="key not_before")
        if issued_at < not_before or check_time < not_before:
            raise ValueError("Titan valuation-case signing key is not yet valid")
    if entry.get("not_after") is not None:
        not_after = _parse_timestamp(entry["not_after"], field="key not_after")
        if issued_at > not_after or check_time > not_after:
            raise ValueError("Titan valuation-case signing key is expired")

    digest = valuation_case_attestation_digest(attestation)
    content_hash = attestation.get("content_hash")
    if not isinstance(content_hash, str) or content_hash.lower() != digest.hex():
        raise ValueError("Titan valuation-case content_hash does not match RFC8785 payload")
    public_key_b64 = entry.get("public_key_b64")
    signature_b64 = attestation.get("detached_signature")
    if not isinstance(public_key_b64, str) or not isinstance(signature_b64, str):
        raise ValueError("Titan valuation-case signature material is missing")
    try:
        raw_public_key = base64.b64decode(public_key_b64, validate=True)
        signature = base64.b64decode(signature_b64, validate=True)
        if len(raw_public_key) != 32 or len(signature) != 64:
            raise ValueError("invalid Ed25519 material")
        public_key = Ed25519PublicKey.from_public_bytes(raw_public_key)
        public_key.verify(signature, digest)
    except (ValueError, InvalidSignature) as exc:
        raise ValueError("Titan valuation-case signature verification failed") from exc


def verify_valuation_case_attestation(
    valuation_case: Mapping[str, object],
    *,
    registry: Mapping[str, Mapping[str, object]],
    now: datetime | None = None,
) -> None:
    """Verify origin and the components intrinsic to a raw ValuationCase v2."""

    if valuation_case.get("schema_version") != "valuation_case.v2":
        raise ValueError("Titan valuation-case attestation requires valuation_case.v2")
    attestation = valuation_case.get("case_attestation")
    if not isinstance(attestation, Mapping):
        raise ValueError("ValuationCase v2 requires Titan case_attestation")
    if (
        attestation.get("schema_version") != VALUATION_CASE_ATTESTATION_SCHEMA
        or attestation.get("content_hash_version") != VALUATION_CASE_ATTESTATION_CONTENT
        or attestation.get("canonicalization") != "RFC8785"
        or attestation.get("signature_algorithm") != "Ed25519-SHA256"
    ):
        raise ValueError("Titan valuation-case attestation contract is unsupported")
    for field in ("company_id", "case_id", "evidence_revision_id", "decision_set_hash"):
        if attestation.get(field) != valuation_case.get(field):
            raise ValueError(f"Titan valuation-case attestation {field} scope mismatch")

    intrinsic = valuation_case_component_hashes(
        valuation_case,
        benchmark_contract=None,
        economic_context=None,
        country_pack_selector={
            "schema_version": "country_pack_selector.v1",
            "country_code": "",
            "currency": None,
        },
    )
    for field in ("case_hash", "evidence_hash", "policy_hash"):
        if attestation.get(field) != intrinsic[field]:
            raise ValueError(f"Titan valuation-case {field} commitment mismatch")
    _verify_registry_and_signature(attestation, registry=registry, now=now)


def verify_valuation_case_external_commitments(
    valuation_case: Mapping[str, object],
    *,
    benchmark_contract: object,
    economic_context: object,
    country_pack_selector: Mapping[str, object],
    external_market_reference_contract: object = None,
    wacc_evidence_contract: object = None,
    real_estate_yield_evidence_contract: object = None,
) -> None:
    """Bind the signed case to the exact external pricing selectors received."""

    attestation = valuation_case.get("case_attestation")
    if not isinstance(attestation, Mapping):
        raise ValueError("ValuationCase v2 requires Titan case_attestation")
    expected = valuation_case_component_hashes(
        valuation_case,
        benchmark_contract=benchmark_contract,
        economic_context=economic_context,
        country_pack_selector=country_pack_selector,
        external_market_reference_contract=external_market_reference_contract,
        wacc_evidence_contract=wacc_evidence_contract,
        real_estate_yield_evidence_contract=real_estate_yield_evidence_contract,
    )
    for field in ("benchmark_hash", "economic_snapshot_hash", "country_pack_hash"):
        if attestation.get(field) != expected[field]:
            raise ValueError(f"Titan valuation-case {field} commitment mismatch")
