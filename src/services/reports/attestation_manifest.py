"""BET-298 — the signable, ITAA/NBA-bound, eIDAS-tiered attestation manifest.

Wraps the content hash-lock (``report_hash_lock``) with the legal-binding
metadata a third party verifies: the valuer's ITAA/NBA registration, the eIDAS
assurance tier, the engine version, and the report identity. This is the
structured artefact DocuSeal signs and the public ``/attest/verify`` endpoint
recomputes (BET-298 acceptance: "verification endpoint returns hash match +
ITAA status").

Pure — reuses ``report_hash_lock`` for the digest, no DocuSeal / DB coupling —
so it is unit-tested directly and consumed by the Titan attestation service.
"""

from __future__ import annotations

from collections.abc import Mapping

from src.services.reports.report_hash_lock import HASH_ALGORITHM, SHORT_HASH_LENGTH, build_hash_lock

#: eIDAS assurance tiers (BET-290): Simple, Advanced, Qualified e-signature.
EIDAS_TIERS: tuple[str, ...] = ("SES", "AES", "QES")
#: BET-298 targets AES (ITAA/NBA-bound) as the default assurance tier.
DEFAULT_EIDAS_TIER = "AES"
MANIFEST_VERSION = "upswitch-attest/manifest-v1"


def _clean(value: object) -> str | None:
    if value is None:
        return None
    rendered = str(value).strip()
    return rendered or None


def _is_sha256_hex(value: object) -> bool:
    rendered = _clean(value)
    return bool(
        rendered
        and len(rendered) == 64
        and all(char in "0123456789abcdef" for char in rendered.lower())
    )


def normalize_eidas_tier(tier: object) -> str:
    """Coerce to a known eIDAS tier; unknown / empty → the AES default."""
    candidate = str(tier or "").strip().upper()
    return candidate if candidate in EIDAS_TIERS else DEFAULT_EIDAS_TIER


def build_attestation_manifest(
    *,
    content_payload: Mapping[str, object],
    report_id: object,
    engine_version: object,
    valuer: Mapping[str, object] | None = None,
    eidas_tier: object = DEFAULT_EIDAS_TIER,
) -> dict[str, object]:
    """Build the signable attestation manifest: the content hash-lock plus the
    ITAA/NBA-bound, eIDAS-tiered legal metadata."""
    hash_lock = build_hash_lock(content_payload)
    v = valuer if isinstance(valuer, Mapping) else {}
    return {
        "manifest_version": MANIFEST_VERSION,
        "report_id": _clean(report_id),
        "engine_version": _clean(engine_version),
        "eidas_tier": normalize_eidas_tier(eidas_tier),
        "hash_lock": hash_lock,
        "content_hash": hash_lock["content_hash"],
        "valuer": {
            "name": _clean(v.get("name")),
            "firm": _clean(v.get("firm")),
            # Eligible-signer registration numbers (BET-319 legal sign-off):
            # ITAA = Belgian accountant / tax adviser; IRE/IBR = Belgian
            # bedrijfsrevisor (statutory auditor — already performs WVV-mandated
            # valuations); NBA = Netherlands accountant. Any one binds the valuer.
            "itaa_number": _clean(v.get("itaa_number")),
            "ire_number": _clean(v.get("ire_number")),
            "nba_number": _clean(v.get("nba_number")),
        },
    }


def _validate_manifest_identity(
    manifest: Mapping[str, object],
    content_hash: str | None,
) -> list[str]:
    errors: list[str] = []
    if _clean(manifest.get("manifest_version")) != MANIFEST_VERSION:
        errors.append("manifest_version")
    if not _clean(manifest.get("engine_version")):
        errors.append("engine_version")
    if not _is_sha256_hex(content_hash):
        errors.append("content_hash")
    return errors


def _hash_lock_mapping(manifest: Mapping[str, object]) -> Mapping[str, object]:
    hash_lock = manifest.get("hash_lock")
    if isinstance(hash_lock, Mapping):
        return hash_lock
    return {}


def _validate_hash_lock(
    hash_lock: Mapping[str, object],
    content_hash: str | None,
) -> list[str]:
    if not hash_lock:
        return ["hash_lock"]

    errors: list[str] = []
    hash_lock_hash = _clean(hash_lock.get("content_hash"))
    short_hash = _clean(hash_lock.get("short_hash"))
    if _clean(hash_lock.get("algorithm")) != HASH_ALGORITHM:
        errors.append("hash_lock.algorithm")
    if not _is_sha256_hex(hash_lock_hash) or hash_lock_hash.lower() != (content_hash or "").lower():
        errors.append("hash_lock.content_hash")
    if short_hash != (content_hash or "")[:SHORT_HASH_LENGTH]:
        errors.append("hash_lock.short_hash")
    return errors


def _validate_report_reference(manifest: Mapping[str, object]) -> list[str]:
    if _clean(manifest.get("report_id")):
        return []
    return ["report_id"]


def _validate_eidas_tier(tier: object) -> list[str]:
    if tier in EIDAS_TIERS:
        return []
    return ["eidas_tier"]


def _valuer_mapping(manifest: Mapping[str, object]) -> Mapping[str, object]:
    valuer = manifest.get("valuer")
    if isinstance(valuer, Mapping):
        return valuer
    return {}


def _has_eligible_registration(valuer: Mapping[str, object]) -> bool:
    return bool(
        _clean(valuer.get("itaa_number"))
        or _clean(valuer.get("ire_number"))
        or _clean(valuer.get("nba_number"))
    )


def _validate_valuer_binding(
    tier: object,
    valuer: Mapping[str, object],
) -> list[str]:
    if tier not in ("AES", "QES"):
        return []

    errors: list[str] = []
    if not _clean(valuer.get("name")):
        errors.append("valuer.name")
    if not _has_eligible_registration(valuer):
        errors.append("valuer.registration")
    return errors


def validate_attestation_manifest(manifest: Mapping[str, object]) -> dict[str, object]:
    """Is a manifest signable? Returns ``{ok, errors}``.

    AES/QES (the M&A-grade tiers) require an identified valuer with at least one
    eligible-signer registration number — ITAA (accountant/tax adviser), IRE/IBR
    (bedrijfsrevisor) or NBA (NL accountant); that binding is the whole point of
    the legal moat. SES is looser (no registration gate).
    """
    content_hash = _clean(manifest.get("content_hash"))
    hash_lock = _hash_lock_mapping(manifest)
    tier = manifest.get("eidas_tier")
    valuer = _valuer_mapping(manifest)

    errors = [
        *_validate_manifest_identity(manifest, content_hash),
        *_validate_hash_lock(hash_lock, content_hash),
        *_validate_report_reference(manifest),
        *_validate_eidas_tier(tier),
        *_validate_valuer_binding(tier, valuer),
    ]

    return {"ok": not errors, "errors": errors}
