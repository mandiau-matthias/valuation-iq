"""BET-298 — attestation verification verdict (the ``/attest/verify`` decision core).

The public verification endpoint must answer, for a signed report, the three
questions BET-298 lists: does the report still hash to what was signed, is the
manifest a valid ITAA/NBA-bound artefact, and is the valuer's registration still
active. This module is that pure verdict — reusing ``verify_content_hash`` and
``validate_attestation_manifest`` — so the Titan endpoint is a thin wrapper that
just recomputes the report payload, looks up the live ITAA/NBA status, and calls
this.

Pure — no HTTP, no register lookup — so the verdict logic is unit-tested
directly, including the BET-298 acceptance "re-rendering after signing fails
verification".
"""

from __future__ import annotations

from collections.abc import Mapping

from src.services.reports.attestation_manifest import validate_attestation_manifest
from src.services.reports.report_hash_lock import verify_content_hash

#: Live ITAA/NBA register status that permits a valid verdict.
ITAA_STATUS_ACTIVE = "active"


def verify_attestation(
    stored_manifest: Mapping[str, object],
    recomputed_payload: Mapping[str, object],
    *,
    itaa_status: object = None,
) -> dict[str, object]:
    """Verdict for a signed attestation.

    Args:
        stored_manifest: the manifest captured at signing time (must carry the
            signed ``content_hash``).
        recomputed_payload: the freshly re-derived report content payload (same
            shape fed to ``build_hash_lock`` at signing) — recomputed from the
            live report so tampering / re-rendering is detectable.
        itaa_status: the valuer's live ITAA/NBA register status (e.g. "active",
            "revoked"). AES/QES attestations fail closed when this is missing.

    Returns ``{valid, hash_match, manifest_valid, itaa_status, reasons}``.
    """
    manifest = stored_manifest if isinstance(stored_manifest, Mapping) else {}

    # 1. The re-rendered report still hashes to what was signed.
    hash_match = verify_content_hash(recomputed_payload, manifest.get("content_hash"))

    # 2. The signed manifest is itself a valid ITAA/NBA-bound artefact.
    manifest_valid = bool(validate_attestation_manifest(manifest)["ok"])

    # 3. The valuer's registration is still active. AES/QES cannot claim a
    # legal-moat verdict unless the public verifier actually checked the
    # eligible-signer register.
    eidas_tier = str(manifest.get("eidas_tier") or "").strip().upper()
    normalized_status = str(itaa_status).strip().lower() if itaa_status is not None else ""
    normalized_status = normalized_status or None
    if eidas_tier in {"AES", "QES"}:
        registration_ok = normalized_status == ITAA_STATUS_ACTIVE
    else:
        registration_ok = normalized_status in (None, ITAA_STATUS_ACTIVE)

    reasons: list[str] = []
    if not hash_match:
        reasons.append("content_hash_mismatch")
    if not manifest_valid:
        reasons.append("manifest_invalid")
    if not registration_ok:
        reasons.append(f"valuer_registration_{normalized_status or 'unchecked'}")

    return {
        "valid": hash_match and manifest_valid and registration_ok,
        "hash_match": hash_match,
        "manifest_valid": manifest_valid,
        "itaa_status": normalized_status,
        "reasons": reasons,
    }
