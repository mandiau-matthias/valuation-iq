"""Minimal HMAC JWT support for ValuationIQ service/user bearer tokens.

This intentionally supports only HS256/HS384/HS512. ValuationIQ receives
tokens from Titan/Supabase-style shared-secret flows; accepting asymmetric or
``none`` algorithms here would widen the auth surface without a current need.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import time
from datetime import date, datetime, timezone


class JWTError(ValueError):
    """Raised when a JWT cannot be decoded or verified."""


_DIGESTS = {
    "HS256": hashlib.sha256,
    "HS384": hashlib.sha384,
    "HS512": hashlib.sha512,
}


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))
    except (ValueError, binascii.Error) as exc:
        raise JWTError("Invalid JWT base64url segment") from exc


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _json_decode(segment: str) -> dict[str, object]:
    try:
        decoded = json.loads(_base64url_decode(segment))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise JWTError("Invalid JWT JSON segment") from exc
    if not isinstance(decoded, dict):
        raise JWTError("JWT segment must decode to an object")
    return decoded


def _json_default(value: object) -> int:
    if isinstance(value, datetime):
        normalized = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return int(normalized.timestamp())
    if isinstance(value, date):
        return int(datetime(value.year, value.month, value.day, tzinfo=timezone.utc).timestamp())
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def decode(token: str, secret: str, *, algorithms: list[str]) -> dict[str, object]:
    """Decode and verify an HMAC-signed JWT payload."""
    if not secret:
        raise JWTError("JWT secret is not configured")

    parts = token.split(".")
    if len(parts) != 3:
        raise JWTError("JWT must contain header, payload, and signature")

    header_segment, payload_segment, signature_segment = parts
    header = _json_decode(header_segment)
    payload = _json_decode(payload_segment)

    algorithm = header.get("alg")
    if not isinstance(algorithm, str) or algorithm not in algorithms:
        raise JWTError("JWT algorithm is not allowed")
    digest = _DIGESTS.get(algorithm)
    if digest is None:
        raise JWTError("JWT algorithm is unsupported")

    signed_content = f"{header_segment}.{payload_segment}".encode("ascii")
    expected_signature = hmac.new(secret.encode("utf-8"), signed_content, digest).digest()
    provided_signature = _base64url_decode(signature_segment)
    if not hmac.compare_digest(provided_signature, expected_signature):
        raise JWTError("JWT signature verification failed")

    now = int(time.time())
    exp = payload.get("exp")
    if isinstance(exp, (int, float)) and now >= int(exp):
        raise JWTError("JWT has expired")

    nbf = payload.get("nbf")
    if isinstance(nbf, (int, float)) and now < int(nbf):
        raise JWTError("JWT is not valid yet")

    return payload


def encode(payload: dict[str, object], secret: str, *, algorithm: str = "HS256") -> str:
    """Encode a JWT for tests and local service-token tooling."""
    digest = _DIGESTS.get(algorithm)
    if digest is None:
        raise JWTError("JWT algorithm is unsupported")

    header = {"alg": algorithm, "typ": "JWT"}
    header_segment = _base64url_encode(
        json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    payload_segment = _base64url_encode(
        json.dumps(payload, default=_json_default, separators=(",", ":"), sort_keys=True).encode(
            "utf-8"
        )
    )
    signed_content = f"{header_segment}.{payload_segment}".encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signed_content, digest).digest()
    return f"{header_segment}.{payload_segment}.{_base64url_encode(signature)}"
