"""BET-298 Upswitch Attest — deterministic content hash-lock.

Per BET-290 the legal moat is not the signature tech (DocuSeal) but *what gets
signed*: a tamper-evident, hash-locked valuation artefact. This module computes
a canonical SHA-256 over the material attestation facts (parties, basis of
value, report identity, engine version, headline figures) so that any change to
the signed claims yields a different fingerprint — which is exactly the BET-298
acceptance "re-rendering report after signing fails verification."

Pure (``hashlib`` + ``json``) — no I/O, no DB, no DocuSeal coupling — so it is
unit-tested directly and reused by both the report layer (prints the
fingerprint on the attestation page) and the Titan attestation service (locks +
publishes the hash to the signing queue).

Note: deliberately distinct from ``src/utils/manifest.hash_data`` (the
valuation-*run* reproducibility hash). This module applies stronger
canonicalisation — None-stripping + compact separators + ``allow_nan=False`` —
so the attestation fingerprint stays stable as optional report fields toggle,
a guarantee run-traceability doesn't need. Two intentional hashing contracts,
not a duplicate.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from collections.abc import Mapping
from urllib.parse import SplitResult, urlsplit

HASH_ALGORITHM = "SHA-256"
SHORT_HASH_LENGTH = 12
_SHA256_HEX_LEN = 64
ATTESTATION_QUEUE_PAYLOAD_VERSION = "valuation-iq/attestation-queue-v1"
ATTESTATION_QUEUE_EVENT_TYPE = "valuation_report.attestation.requested"
_ALLOWED_VERIFY_HOSTS = {
    "app.upswitch.app",
    "attest.upswitch.app",
    "www.upswitch.app",
}
_ALLOWED_VERIFY_PORTS = {None, 443}
_VERIFY_PATH_RE = re.compile(r"^/attest/verify/[A-Za-z0-9][A-Za-z0-9_-]*$")


def _normalize(value: object) -> object:
    """Recursively normalise to an order-stable, ``None``-free structure so
    equivalent payloads hash identically regardless of dict insertion order or
    absent-vs-null. Scalars other than b/int/float are coerced to ``str`` so a
    Decimal and its string form can't disagree."""
    if isinstance(value, Mapping):
        return {
            str(k): _normalize(value[k]) for k in sorted(value, key=str) if value[k] is not None
        }
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if isinstance(value, bool) or isinstance(value, (int, float)):
        return value
    return str(value)


def canonicalize(payload: Mapping[str, object]) -> str:
    """Canonical JSON for hashing: sorted keys, compact separators, no NaN."""
    return json.dumps(
        _normalize(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def compute_content_hash(payload: Mapping[str, object]) -> str:
    """Canonical SHA-256 hex digest of the payload (lowercase)."""
    return hashlib.sha256(canonicalize(payload).encode("utf-8")).hexdigest()


def build_hash_lock(payload: Mapping[str, object]) -> dict[str, str]:
    """The hash-lock block for the attestation page + signing queue: algorithm,
    full digest, and a short human-checkable prefix (cover/footer fingerprint)."""
    digest = compute_content_hash(payload)
    return {
        "algorithm": HASH_ALGORITHM,
        "content_hash": digest,
        "short_hash": digest[:SHORT_HASH_LENGTH],
    }


def verify_content_hash(payload: Mapping[str, object], expected_hash: object) -> bool:
    """True iff the payload re-hashes to ``expected_hash``. Constant-time compare;
    rejects malformed (non-64-hex) expectations. Case-insensitive on the hex."""
    expected = str(expected_hash if expected_hash is not None else "").strip().lower()
    if len(expected) != _SHA256_HEX_LEN:
        return False
    return hmac.compare_digest(compute_content_hash(payload), expected)


def _clean(value: object) -> str | None:
    if value is None:
        return None
    rendered = str(value).strip()
    return rendered or None


def _has_unsafe_url_characters(value: str) -> bool:
    return "\\" in value or any(char.isspace() for char in value)


def _has_verify_path_without_client_state(parsed: SplitResult) -> bool:
    return (
        _VERIFY_PATH_RE.fullmatch(parsed.path) is not None
        and not parsed.query
        and not parsed.fragment
    )


def _parsed_port(parsed: SplitResult) -> int | None | object:
    try:
        return parsed.port
    except ValueError:
        return _INVALID_PORT


def _is_allowed_absolute_verify_url(parsed: SplitResult) -> bool:
    hostname = (parsed.hostname or "").lower()
    return (
        parsed.scheme.lower() == "https"
        and bool(parsed.netloc)
        and hostname in _ALLOWED_VERIFY_HOSTS
        and parsed.username is None
        and parsed.password is None
        and _parsed_port(parsed) in _ALLOWED_VERIFY_PORTS
    )


def _is_allowed_relative_verify_url(rendered: str, parsed: SplitResult) -> bool:
    return not parsed.netloc and rendered.startswith("/")


_INVALID_PORT = object()


def normalize_public_verify_url(value: object) -> str | None:
    """Return a public Upswitch Attest verify URL, or None for unsafe input."""
    rendered = _clean(value)
    if not rendered or _has_unsafe_url_characters(rendered):
        return None

    parsed = urlsplit(rendered)
    if not _has_verify_path_without_client_state(parsed):
        return None

    if parsed.scheme:
        if _is_allowed_absolute_verify_url(parsed):
            return rendered
        return None

    if _is_allowed_relative_verify_url(rendered, parsed):
        return rendered
    return None


def build_attestation_queue_payload(
    *,
    content_payload: Mapping[str, object],
    report_id: object,
    engine_version: object = None,
    valuer: Mapping[str, object] | None = None,
    eidas_tier: object = "AES",
    verify_url: object = None,
) -> dict[str, object]:
    """Deterministic payload ValuationIQ hands to the signing/attestation queue.

    This is intentionally side-effect free: ValuationIQ owns the report facts
    and hash-lock; Titan owns persistence, signer eligibility, DocuSeal, and
    webhook state. Keeping the boundary as data lets both sides test the same
    artefact without coupling report rendering to a queue client.
    """
    hash_lock = build_hash_lock(content_payload)
    v = valuer if isinstance(valuer, Mapping) else {}

    return {
        "type": ATTESTATION_QUEUE_EVENT_TYPE,
        "version": ATTESTATION_QUEUE_PAYLOAD_VERSION,
        "report_id": _clean(report_id),
        "engine_version": _clean(engine_version),
        "eidas_tier": (_clean(eidas_tier) or "AES").upper(),
        "hash_lock": hash_lock,
        "content_hash": hash_lock["content_hash"],
        "short_hash": hash_lock["short_hash"],
        "verify_url": normalize_public_verify_url(verify_url),
        "content_payload": _normalize(content_payload),
        "valuer": {
            "name": _clean(v.get("name")),
            "firm": _clean(v.get("firm")),
            "itaa_number": _clean(v.get("itaa_number")),
            "ire_number": _clean(v.get("ire_number")),
            "nba_number": _clean(v.get("nba_number")),
        },
    }
