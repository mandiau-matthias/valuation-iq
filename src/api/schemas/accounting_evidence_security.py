from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping

import rfc8785
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def _parse_timestamp(value: object, *, field: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{field} must be an ISO-8601 timestamp") from exc
    else:
        raise ValueError(f"{field} must be an ISO-8601 timestamp")
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


_V2_COMMITTED_KEYS = (
    "schema_version",
    "content_hash_version",
    "canonicalization",
    "signature_algorithm",
    "snapshot_id",
    "evidence_revision_id",
    "entity_id",
    "tenant_id",
    "provider_id",
    "connection_id",
    "company_name",
    "country_code",
    "currency",
    "periods",
    "years",
    "issuer",
    "key_id",
    "issued_at",
)

_V3_COMMITTED_KEYS = _V2_COMMITTED_KEYS + (
    "company_node_id",
    "source_entity_aliases",
    "evidence_origin",
    "verification_level",
    "source_bound",
    "visibility_scope",
    "valid_from",
    "valid_until",
)


def accounting_evidence_digest(payload: Mapping[str, Any]) -> bytes:
    """Return the exact Hermes RFC-8785 commitment for package v2 or v3."""

    schema_version = payload.get("schema_version")
    if schema_version == "accounting_evidence_package.v2":
        committed_keys = _V2_COMMITTED_KEYS
    elif schema_version == "accounting_evidence_package.v3":
        committed_keys = _V3_COMMITTED_KEYS
    else:
        raise ValueError("Accounting evidence schema version is unsupported")
    canonical_payload = {key: payload.get(key) for key in committed_keys}
    return hashlib.sha256(rfc8785.dumps(canonical_payload)).digest()


def accounting_evidence_v2_digest(payload: Mapping[str, Any]) -> bytes:
    """Compatibility wrapper pinned to the v2 wire contract."""

    if payload.get("schema_version") != "accounting_evidence_package.v2":
        raise ValueError("Accounting evidence v2 digest requires package v2")
    return accounting_evidence_digest(payload)


def parse_hermes_public_key_registry(raw_json: str) -> dict[str, dict[str, object]]:
    try:
        payload = json.loads(raw_json or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("Hermes evidence public-key registry must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("Hermes evidence public-key registry must be a JSON object")
    registry: dict[str, dict[str, object]] = {}
    for key_id, entry in payload.items():
        if not isinstance(key_id, str) or not key_id.strip() or not isinstance(entry, dict):
            raise ValueError("Hermes evidence registry entries require a non-empty key_id object")
        registry[key_id] = dict(entry)
    return registry


def verify_accounting_evidence_signature(
    payload: Mapping[str, Any],
    *,
    registry: Mapping[str, Mapping[str, object]],
    now: datetime | None = None,
) -> None:
    schema_version = payload.get("schema_version")
    content_hash_version = payload.get("content_hash_version")
    expected_content_version = {
        "accounting_evidence_package.v2": "accounting_evidence_content.v2",
        "accounting_evidence_package.v3": "accounting_evidence_content.v3",
    }.get(schema_version)
    if expected_content_version is None or content_hash_version != expected_content_version:
        raise ValueError("Accounting evidence schema/content version is unsupported")
    key_id = payload.get("key_id")
    issuer = payload.get("issuer")
    if not isinstance(key_id, str) or key_id not in registry:
        raise ValueError("Accounting evidence key_id is unknown")
    entry = registry[key_id]
    if entry.get("revoked") is True:
        raise ValueError("Accounting evidence signing key is revoked")
    if not isinstance(issuer, str) or entry.get("issuer") != issuer:
        raise ValueError("Accounting evidence issuer does not match signing key registry")
    if payload.get("signature_algorithm") != "Ed25519-SHA256":
        raise ValueError("Accounting evidence signature algorithm is unsupported")
    if payload.get("canonicalization") != "RFC8785":
        raise ValueError("Accounting evidence canonicalization is unsupported")

    issued_at = _parse_timestamp(payload.get("issued_at"), field="issued_at")
    check_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if issued_at > check_time:
        raise ValueError("Accounting evidence issued_at cannot be in the future")
    if entry.get("not_before") is not None:
        not_before = _parse_timestamp(entry["not_before"], field="key not_before")
        if issued_at < not_before:
            raise ValueError("Accounting evidence predates signing-key validity")
    if entry.get("not_after") is not None:
        not_after = _parse_timestamp(entry["not_after"], field="key not_after")
        if issued_at > not_after or check_time > not_after:
            raise ValueError("Accounting evidence signing key is expired")

    if schema_version == "accounting_evidence_package.v3":
        if payload.get("source_bound") is not True:
            raise ValueError("Accounting evidence v3 must be source-bound")
        if payload.get("evidence_origin") != "connected_source":
            raise ValueError("Accounting evidence v3 origin is unsupported")
        if payload.get("verification_level") != "source_verified":
            raise ValueError("Accounting evidence v3 must be source-verified")
        if payload.get("visibility_scope") != "workspace":
            raise ValueError("Accounting evidence v3 visibility scope is unsupported")
        valid_from = _parse_timestamp(payload.get("valid_from"), field="valid_from")
        valid_until_raw = payload.get("valid_until")
        if issued_at < valid_from:
            raise ValueError("Accounting evidence predates its v3 validity interval")
        if valid_from > check_time:
            raise ValueError("Accounting evidence v3 is not yet valid")
        if valid_until_raw is not None:
            valid_until = _parse_timestamp(valid_until_raw, field="valid_until")
            if valid_until <= valid_from:
                raise ValueError("Accounting evidence v3 validity interval is invalid")
            if issued_at > valid_until or check_time > valid_until:
                raise ValueError("Accounting evidence v3 is expired")

    digest = accounting_evidence_digest(payload)
    content_hash = payload.get("content_hash")
    if not isinstance(content_hash, str) or content_hash.lower() != digest.hex():
        raise ValueError("Accounting evidence content_hash does not match RFC8785 payload")
    if payload.get("snapshot_hash") != content_hash:
        raise ValueError("Accounting evidence snapshot_hash must equal content_hash")

    public_key_b64 = entry.get("public_key_b64")
    signature_b64 = payload.get("detached_signature")
    if not isinstance(public_key_b64, str) or not isinstance(signature_b64, str):
        raise ValueError("Accounting evidence signature material is missing")
    try:
        public_key = Ed25519PublicKey.from_public_bytes(
            base64.b64decode(public_key_b64, validate=True)
        )
        signature = base64.b64decode(signature_b64, validate=True)
        public_key.verify(signature, digest)
    except (ValueError, InvalidSignature) as exc:
        raise ValueError("Accounting evidence signature verification failed") from exc


def verify_accounting_evidence_v2_signature(
    payload: Mapping[str, Any],
    *,
    registry: Mapping[str, Mapping[str, object]],
    now: datetime | None = None,
) -> None:
    """Compatibility wrapper retaining the public v2 verifier."""

    if payload.get("schema_version") != "accounting_evidence_package.v2":
        raise ValueError("Accounting evidence v2 verifier requires package v2")
    verify_accounting_evidence_signature(payload, registry=registry, now=now)
