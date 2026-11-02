"""Authenticate Titan's final stateless-calculation JSON wire commitment."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

import rfc8785


TITAN_REQUEST_WIRE_COMMITMENT_KEY = "titan_request_wire_commitment"
TITAN_REQUEST_WIRE_COMMITMENT_SCHEMA = "titan_request_wire_commitment.v1"


class TitanRequestWireCommitmentError(ValueError):
    """Raised when a claimed Titan request commitment cannot be authenticated."""


def _wire_projection(payload: Mapping[str, object]) -> dict[str, object]:
    projection = dict(payload)
    raw_metadata = projection.get("metadata")
    metadata = dict(raw_metadata) if isinstance(raw_metadata, Mapping) else {}
    metadata.pop(TITAN_REQUEST_WIRE_COMMITMENT_KEY, None)
    projection["metadata"] = metadata
    return projection


def verify_titan_request_wire_commitment(
    raw_body: bytes,
) -> dict[str, str] | None:
    """Verify the RFC-8785 hash over the exact parsed HTTP JSON wire.

    Requests without a commitment remain valid for legacy/non-canonical callers.
    A caller that supplies the field opts into strict verification and fails
    closed on every malformed or mismatched component.
    """

    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise TitanRequestWireCommitmentError(
            "stateless request body is not valid UTF-8 JSON"
        ) from exc
    if not isinstance(payload, Mapping):
        raise TitanRequestWireCommitmentError("stateless request body must be a JSON object")
    raw_metadata = payload.get("metadata")
    if not isinstance(raw_metadata, Mapping):
        return None
    raw_commitment = raw_metadata.get(TITAN_REQUEST_WIRE_COMMITMENT_KEY)
    if raw_commitment is None:
        return None
    if not isinstance(raw_commitment, Mapping):
        raise TitanRequestWireCommitmentError("Titan request commitment must be an object")

    commitment = {
        "schema_version": raw_commitment.get("schema_version"),
        "hash_algorithm": raw_commitment.get("hash_algorithm"),
        "canonicalization": raw_commitment.get("canonicalization"),
        "request_hash": raw_commitment.get("request_hash"),
    }
    if set(raw_commitment) != set(commitment):
        raise TitanRequestWireCommitmentError("Titan request commitment has unknown fields")
    if commitment["schema_version"] != TITAN_REQUEST_WIRE_COMMITMENT_SCHEMA:
        raise TitanRequestWireCommitmentError("Titan request commitment schema is unsupported")
    if commitment["hash_algorithm"] != "SHA-256":
        raise TitanRequestWireCommitmentError("Titan request commitment hash is unsupported")
    if commitment["canonicalization"] != "RFC8785":
        raise TitanRequestWireCommitmentError(
            "Titan request commitment canonicalization is unsupported"
        )
    request_hash = commitment["request_hash"]
    if (
        not isinstance(request_hash, str)
        or len(request_hash) != 64
        or any(character not in "0123456789abcdef" for character in request_hash)
    ):
        raise TitanRequestWireCommitmentError("Titan request commitment hash is invalid")

    expected = hashlib.sha256(rfc8785.dumps(_wire_projection(payload))).hexdigest()
    if request_hash != expected:
        raise TitanRequestWireCommitmentError(
            "Titan request commitment does not match the received JSON wire"
        )
    return {key: str(value) for key, value in commitment.items()}
