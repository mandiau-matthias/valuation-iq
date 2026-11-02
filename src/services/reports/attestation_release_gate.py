"""BET-298 release gate for Upswitch Attest on the ValuationIQ side.

The local report contracts can be green while the production signing runtime is
still blocked. This packet makes that explicit: it proves the ValuationIQ
hash-lock, manifest, queue, verify, and cover-seal contracts, then fails closed
until production DocuSeal and first signed-report evidence are attached.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from src.services.reports.attestation_context import build_attestation_context
from src.services.reports.attestation_manifest import (
    DEFAULT_EIDAS_TIER,
    build_attestation_manifest,
    validate_attestation_manifest,
)
from src.services.reports.attestation_verification import verify_attestation
from src.services.reports.report_hash_lock import (
    build_attestation_queue_payload,
    build_hash_lock,
    compute_content_hash,
    verify_content_hash,
)

TICKET_ID = "BET-298"
BLOCKING_RUNTIME_TICKET = "BET-391"
_SRC_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class AttestationReleaseEvidence:
    """External evidence required before BET-298 can move to Done."""

    docuseal_runtime_ready: bool = False
    docuseal_runtime_ref: str | None = None
    signed_report_ref: str | None = None
    verify_endpoint_ref: str | None = None
    delivery_surface_ref: str | None = None

    @classmethod
    def from_mapping(
        cls,
        value: Mapping[str, object] | None,
    ) -> "AttestationReleaseEvidence":
        if not value:
            return cls()
        return cls(
            docuseal_runtime_ready=bool(value.get("docuseal_runtime_ready")),
            docuseal_runtime_ref=_clean(value.get("docuseal_runtime_ref")),
            signed_report_ref=_clean(value.get("signed_report_ref")),
            verify_endpoint_ref=_clean(value.get("verify_endpoint_ref")),
            delivery_surface_ref=_clean(value.get("delivery_surface_ref")),
        )


@dataclass(frozen=True)
class _GateCheck:
    id: str
    category: str
    ok: bool
    detail: str
    blocking_issue: str | None = None

    def as_dict(self) -> dict[str, object]:
        out: dict[str, object] = {
            "id": self.id,
            "category": self.category,
            "ok": self.ok,
            "detail": self.detail,
        }
        if self.blocking_issue:
            out["blocking_issue"] = self.blocking_issue
        return out


def _clean(value: object) -> str | None:
    if value is None:
        return None
    rendered = str(value).strip()
    return rendered or None


def _contract_check(check_id: str, ok: bool, detail: str) -> _GateCheck:
    return _GateCheck(
        id=f"valuation_iq.{check_id}",
        category="local_contract",
        ok=ok,
        detail=detail,
    )


def _external_check(
    check_id: str,
    ok: bool,
    detail: str,
    *,
    blocking_issue: str = TICKET_ID,
) -> _GateCheck:
    return _GateCheck(
        id=f"production.{check_id}",
        category="external_evidence",
        ok=ok,
        detail=detail,
        blocking_issue=blocking_issue,
    )


def _sample_payload() -> dict[str, object]:
    return {
        "report_id": "VAL-BET-298-SAMPLE",
        "client": "ACME BV",
        "valuation_date": "2026-06-09",
        "basis_of_value": "Market value for M&A purposes",
        "premise_of_value": "Going concern",
        "scope_of_work": "Advisor-reviewed SME valuation",
        "standard_reference": "IVS-inspired SME M&A report structure",
        "engine_version": "valuation-iq/2026.06",
        "preparer_firm_name": "Mandiau & Co",
        "preparer_name": "Jan Janssens",
    }


def _sample_valuer() -> dict[str, object]:
    return {
        "name": "Jan Janssens",
        "firm": "Mandiau & Co",
        "itaa_number": "ITAA-12345",
    }


def _sample_context() -> dict[str, object]:
    return {
        "company_name": "ACME BV",
        "report_id": "VAL-BET-298-SAMPLE",
        "valuation_date": "2026-06-09",
        "accountant_firm_name": "Mandiau & Co",
        "engine_version": "valuation-iq/2026.06",
    }


def _sample_metadata() -> dict[str, object]:
    return {
        "show_attestation": True,
        "preparer_name": "Jan Janssens",
        "itaa_number": "ITAA-12345",
        "basis_of_value": "Market value for M&A purposes",
        "premise_of_value": "Going concern",
        "scope_of_work": "Advisor-reviewed SME valuation",
        "standard_reference": "IVS-inspired SME M&A report structure",
    }


def _signed_seal(content_hash: str) -> dict[str, object]:
    return {
        "renderable": True,
        "state": "signed",
        "verify_url": "/attest/verify/att-bet-298-sample",
        "display_hash": content_hash[:12],
        "content_hash": content_hash,
        "eidas_tier": DEFAULT_EIDAS_TIER,
        "signed_at": "2026-06-09T00:00:00.000Z",
        "signed_pdf_sha256": "f" * 64,
        "signer": {
            "name": "Jan Janssens",
            "firm": "Mandiau & Co",
            "register_body": "ITAA",
            "register_number": "ITAA-12345",
            "register_status": "active",
        },
    }


def _check_hash_lock_contract() -> _GateCheck:
    payload = _sample_payload()
    lock = build_hash_lock(payload)
    tampered = {**payload, "basis_of_value": "Investment value"}
    ok = (
        lock["content_hash"] == compute_content_hash(payload)
        and lock["short_hash"] == lock["content_hash"][:12]
        and verify_content_hash(payload, lock["content_hash"])
        and not verify_content_hash(tampered, lock["content_hash"])
    )
    return _contract_check(
        "hash_lock_roundtrip",
        ok,
        "Canonical report hash is stable and tamper-evident.",
    )


def _check_manifest_contract() -> _GateCheck:
    manifest = build_attestation_manifest(
        content_payload=_sample_payload(),
        report_id="VAL-BET-298-SAMPLE",
        engine_version="valuation-iq/2026.06",
        valuer=_sample_valuer(),
        eidas_tier=DEFAULT_EIDAS_TIER,
    )
    verdict = validate_attestation_manifest(manifest)
    ok = bool(verdict["ok"]) and manifest["eidas_tier"] == DEFAULT_EIDAS_TIER
    return _contract_check(
        "manifest_signable",
        ok,
        (
            "AES manifest requires report identity, engine version, hash-lock, "
            "and ITAA/NBA/IRE valuer binding."
        ),
    )


def _check_verification_contract() -> _GateCheck:
    payload = _sample_payload()
    manifest = build_attestation_manifest(
        content_payload=payload,
        report_id="VAL-BET-298-SAMPLE",
        engine_version="valuation-iq/2026.06",
        valuer=_sample_valuer(),
        eidas_tier=DEFAULT_EIDAS_TIER,
    )
    valid = verify_attestation(manifest, payload, itaa_status="active")
    unchecked = verify_attestation(manifest, payload)
    tampered = verify_attestation(
        manifest,
        {**payload, "preparer_name": "Different Signer"},
        itaa_status="active",
    )
    ok = (
        bool(valid["valid"])
        and not bool(unchecked["valid"])
        and "valuer_registration_unchecked" in unchecked["reasons"]
        and not bool(tampered["valid"])
    )
    return _contract_check(
        "verification_verdict",
        ok,
        (
            "Verification accepts unchanged reports only with an active register "
            "check and rejects re-rendered content."
        ),
    )


def _check_queue_contract() -> _GateCheck:
    payload = _sample_payload()
    safe = build_attestation_queue_payload(
        content_payload=payload,
        report_id="VAL-BET-298-SAMPLE",
        engine_version="valuation-iq/2026.06",
        valuer=_sample_valuer(),
        eidas_tier=DEFAULT_EIDAS_TIER,
        verify_url="https://attest.upswitch.app/attest/verify/att-bet-298-sample",
    )
    unsafe = build_attestation_queue_payload(
        content_payload=payload,
        report_id="VAL-BET-298-SAMPLE",
        verify_url="https://attacker.example/attest/verify/att-bet-298-sample",
    )
    ambiguous = build_attestation_queue_payload(
        content_payload=payload,
        report_id="VAL-BET-298-SAMPLE",
        verify_url="/attest/verify/att-bet-298-sample/extra",
    )
    ok = (
        safe["type"] == "valuation_report.attestation.requested"
        and safe["content_hash"] == compute_content_hash(payload)
        and safe["verify_url"] == "https://attest.upswitch.app/attest/verify/att-bet-298-sample"
        and unsafe["verify_url"] is None
        and ambiguous["verify_url"] is None
    )
    return _contract_check(
        "queue_payload_boundary",
        ok,
        "Signing queue payload shares the report hash-lock and rejects unsafe verify URLs.",
    )


def _check_cover_seal_contract() -> _GateCheck:
    context = _sample_context()
    metadata = _sample_metadata()
    unsigned = build_attestation_context(context, metadata=metadata, locale="en")
    content_hash = str(unsigned["attestation_content_hash"])
    signed = build_attestation_context(
        {**context, "attestation_seal": _signed_seal(content_hash)},
        metadata=metadata,
        locale="en",
    )
    stale = build_attestation_context(
        {**context, "attestation_seal": _signed_seal("0" * 64)},
        metadata=metadata,
        locale="en",
    )
    ok = (
        signed["attestation_signed"] is True
        and signed["attestation_cover_seal"]["content_hash"] == content_hash
        and signed["attestation_queue_payload"]["content_hash"] == content_hash
        and stale["attestation_signed"] is False
    )
    return _contract_check(
        "cover_seal_hash_binding",
        ok,
        "Cover seal renders only when Titan's signed hash matches the current report hash.",
    )


def _check_template_contract() -> _GateCheck:
    template_root = _SRC_ROOT / "templates"
    required = (
        "main_report/partials/attestation-block.jinja",
        "main_report_pdf/partials/attestation-block.jinja",
        "main_report/pages/cover_page.html",
        "main_report_pdf/pages/cover_page.html",
    )
    missing = [path for path in required if not (template_root / path).exists()]
    if missing:
        return _contract_check(
            "cover_templates",
            False,
            f"Missing attestation templates: {', '.join(missing)}.",
        )

    html_partial = (template_root / required[0]).read_text(encoding="utf-8")
    pdf_partial = (template_root / required[1]).read_text(encoding="utf-8")
    html_cover = (template_root / required[2]).read_text(encoding="utf-8")
    pdf_cover = (template_root / required[3]).read_text(encoding="utf-8")
    ok = (
        "cover-attestation-seal" in html_partial
        and "cover-attestation-seal" in pdf_partial
        and "attestation-block.jinja" in html_cover
        and "attestation-block.jinja" in pdf_cover
    )
    return _contract_check(
        "cover_templates",
        ok,
        "HTML and PDF cover templates include the attestation seal partial.",
    )


def _external_evidence_checks(evidence: AttestationReleaseEvidence) -> list[_GateCheck]:
    runtime_ok = bool(evidence.docuseal_runtime_ready and evidence.docuseal_runtime_ref)
    return [
        _external_check(
            "docuseal_runtime",
            runtime_ok,
            (
                f"Production DocuSeal runtime evidence: {evidence.docuseal_runtime_ref}."
                if runtime_ok
                else "Missing BET-391 public DocuSeal DNS/TLS /up evidence."
            ),
            blocking_issue=BLOCKING_RUNTIME_TICKET,
        ),
        _external_check(
            "first_signed_report",
            bool(evidence.signed_report_ref),
            (
                f"First signed production report evidence: {evidence.signed_report_ref}."
                if evidence.signed_report_ref
                else "Missing first design-partner signed report artifact."
            ),
        ),
        _external_check(
            "verify_endpoint",
            bool(evidence.verify_endpoint_ref),
            (
                f"Public verify endpoint evidence: {evidence.verify_endpoint_ref}."
                if evidence.verify_endpoint_ref
                else (
                    "Missing public /attest/verify evidence showing hash match "
                    "and live register status."
                )
            ),
        ),
        _external_check(
            "delivery_surface",
            bool(evidence.delivery_surface_ref),
            (
                f"UI/email delivery evidence: {evidence.delivery_surface_ref}."
                if evidence.delivery_surface_ref
                else "Missing UI/email evidence that the signed seal is visible to the recipient."
            ),
        ),
    ]


def build_attestation_release_gate_packet(
    evidence: Mapping[str, object] | AttestationReleaseEvidence | None = None,
) -> dict[str, object]:
    """Build the machine-readable BET-298 release packet."""
    release_evidence = (
        evidence
        if isinstance(evidence, AttestationReleaseEvidence)
        else AttestationReleaseEvidence.from_mapping(evidence)
    )
    checks = [
        _check_hash_lock_contract(),
        _check_manifest_contract(),
        _check_verification_contract(),
        _check_queue_contract(),
        _check_cover_seal_contract(),
        _check_template_contract(),
        *_external_evidence_checks(release_evidence),
    ]
    checks_out = [check.as_dict() for check in checks]
    failures = [check for check in checks if not check.ok]
    blocking_issues = sorted({check.blocking_issue for check in failures if check.blocking_issue})
    ready = not failures
    local_checks = [check for check in checks if check.category == "local_contract"]
    external_checks = [check for check in checks if check.category == "external_evidence"]

    return {
        "ticket": TICKET_ID,
        "name": "Digital Valuation Attestation - Upswitch Attest",
        "ready_for_release": ready,
        "done_gate": "move_to_done" if ready else "keep_in_progress",
        "blocked_by": blocking_issues,
        "summary": {
            "local_contract_checks": {
                "passed": sum(1 for check in local_checks if check.ok),
                "failed": sum(1 for check in local_checks if not check.ok),
            },
            "external_evidence_checks": {
                "passed": sum(1 for check in external_checks if check.ok),
                "failed": sum(1 for check in external_checks if not check.ok),
            },
        },
        "checks": checks_out,
    }
