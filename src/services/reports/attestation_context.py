"""Enterprise attestation context for accountant-branded report packs."""

from __future__ import annotations

from collections.abc import Mapping

from src.services.defensibility.reference_formatter import format_valuation_reference
from src.services.infrastructure.translations import normalize_report_locale
from src.services.reports.report_hash_lock import (
    build_attestation_queue_payload,
    build_hash_lock,
    normalize_public_verify_url,
)

ReportMapping = Mapping[str, object]
SummaryRow = dict[str, str | None]
CoverSealHashes = tuple[str, str, str | None]

_INTERNAL_REPORT_CONTEXT_VERSION = "valuation-iq/report-context-v1"
_SUPPORTED_REGISTER_BODIES = {"ITAA", "IRE", "IBR", "NBA"}


def _clean(value: object) -> str | None:
    if value is None:
        return None
    rendered = str(value).strip()
    return rendered or None


def _sha256_hex(value: object) -> str | None:
    rendered = _clean(value)
    if (
        rendered
        and len(rendered) == 64
        and all(char in "0123456789abcdef" for char in rendered.lower())
    ):
        return rendered.lower()
    return None


def _metadata_value(metadata: ReportMapping | None, *keys: str) -> str | None:
    if not metadata:
        return None
    for key in keys:
        value = _clean(metadata.get(key))
        if value:
            return value
    return None


def _metadata_bool(metadata: ReportMapping | None, *keys: str) -> bool | None:
    if not metadata:
        return None
    for key in keys:
        if key not in metadata:
            continue
        value = metadata.get(key)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "y", "on"}:
                return True
            if normalized in {"false", "0", "no", "n", "off", ""}:
                return False
        return bool(value)
    return None


def _as_mapping(value: object) -> ReportMapping | None:
    return value if isinstance(value, Mapping) else None


def _first_mapping_value(
    context: ReportMapping,
    metadata: ReportMapping | None,
    *keys: str,
) -> ReportMapping | None:
    containers: tuple[ReportMapping | None, ...] = (metadata, context)
    for container in containers:
        if not container:
            continue
        for key in keys:
            value = _as_mapping(container.get(key))
            if value:
                return value
    return None


def _incoming_attestation_seal(
    context: ReportMapping,
    metadata: ReportMapping | None,
) -> ReportMapping | None:
    direct = _first_mapping_value(
        context,
        metadata,
        "attestation_seal",
        "attestationSeal",
        "seal",
    )
    if direct:
        return direct

    for container in (metadata, context):
        attestation = _as_mapping(container.get("attestation")) if container else None
        seal = _as_mapping(attestation.get("seal")) if attestation else None
        if seal:
            return seal
    return None


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "on"}
    return bool(value)


def _seal_signed_state(seal: ReportMapping) -> tuple[str, str] | None:
    state = (_clean(seal.get("state")) or "pending").lower()
    signed_at = _clean(seal.get("signed_at"))
    if _truthy(seal.get("renderable")) and state == "signed" and signed_at:
        return state, signed_at
    return None


def _register_identity(signer: ReportMapping) -> tuple[str | None, str | None]:
    register_body = (_clean(signer.get("register_body")) or "").upper()
    register_number = _clean(signer.get("register_number"))
    if register_body in _SUPPORTED_REGISTER_BODIES:
        return register_body, register_number

    fallback_fields = (
        ("ITAA", "itaa_number"),
        ("IRE", "ire_number"),
        ("NBA", "nba_number"),
    )
    for body, field in fallback_fields:
        fallback_number = _clean(signer.get(field))
        if fallback_number:
            return body, fallback_number
    return None, register_number


def _normalize_seal_hashes(
    seal: ReportMapping,
    expected_hash_lock: ReportMapping | None,
) -> CoverSealHashes | None:
    verify_url = normalize_public_verify_url(seal.get("verify_url"))
    display_hash = _clean(seal.get("display_hash"))
    content_hash = _clean(seal.get("content_hash"))
    if not display_hash and content_hash:
        display_hash = content_hash[:12]
    if not verify_url or not display_hash:
        return None

    expected_content_hash = (
        _clean(expected_hash_lock.get("content_hash")) if expected_hash_lock else None
    )
    if expected_content_hash:
        if not content_hash or content_hash.lower() != expected_content_hash.lower():
            return None
        display_hash = _clean(expected_hash_lock.get("short_hash")) or display_hash

    return verify_url, display_hash, content_hash


def _normalize_signed_pdf_sha256(seal: ReportMapping) -> tuple[bool, str | None]:
    signed_pdf_sha256 = _clean(seal.get("signed_pdf_sha256"))
    if not signed_pdf_sha256:
        return True, None
    normalized = _sha256_hex(signed_pdf_sha256)
    return bool(normalized), normalized


def _normalize_cover_seal(
    seal: ReportMapping | None,
    *,
    expected_hash_lock: ReportMapping | None = None,
) -> dict[str, object] | None:
    """Normalize Titan's cover/UI-ready seal and reject non-signed states."""
    if not seal:
        return None

    signed_state = _seal_signed_state(seal)
    if not signed_state:
        return None
    state, signed_at = signed_state

    signer = _as_mapping(seal.get("signer")) or {}
    register_body, register_number = _register_identity(signer)

    normalized_hashes = _normalize_seal_hashes(seal, expected_hash_lock)
    if not normalized_hashes:
        return None
    verify_url, display_hash, content_hash = normalized_hashes

    valid_signed_pdf, signed_pdf_sha256 = _normalize_signed_pdf_sha256(seal)
    if not valid_signed_pdf:
        return None

    return {
        "renderable": True,
        "state": state,
        "verify_url": verify_url,
        "display_hash": display_hash,
        "content_hash": content_hash,
        "manifest_version": _clean(seal.get("manifest_version")),
        "engine_version": _clean(seal.get("engine_version")),
        "eidas_tier": (_clean(seal.get("eidas_tier")) or "AES").upper(),
        "signature_provider": _clean(seal.get("signature_provider")) or "docuseal",
        "signed_at": signed_at,
        "register_checked_at": _clean(seal.get("register_checked_at")),
        "signer": {
            "name": _clean(signer.get("name")),
            "firm": _clean(signer.get("firm")),
            "register_body": register_body,
            "register_number": register_number,
            "register_status": _clean(signer.get("register_status")),
        },
        "signed_pdf_sha256": signed_pdf_sha256,
        "audit_log_url": _clean(seal.get("audit_log_url")),
        "revoked_reason": _clean(seal.get("revoked_reason")),
    }


def _public_model_version(value: object) -> str | None:
    rendered = _clean(value)
    if not rendered:
        return None
    normalized = rendered.lower()
    if normalized == _INTERNAL_REPORT_CONTEXT_VERSION or "report-context" in normalized:
        return None
    if normalized.startswith("valuation-iq/"):
        rendered = rendered.split("/", 1)[1].strip()
    return rendered or None


def _defaults(locale: str) -> dict[str, str]:
    loc = normalize_report_locale(locale)
    if loc == "nl":
        return {
            "basis_of_value": "Marktwaarde voor M&A-doeleinden",
            "premise_of_value": "Going-concern",
            "scope_of_work": (
                "Indicatieve SME-waardering op basis van aangeleverde en beschikbare " "marktdata"
            ),
            "standard_reference": "IVS-geïnspireerde rapportstructuur voor SME M&A",
            "basis_label": "Waarderingsbasis",
            "premise_label": "Premisse",
            "scope_label": "Reikwijdte",
            "standard_label": "Rapportstandaard",
            "reference_label": "Rapportreferentie",
            "engine_label": "Modelversie",
            "fingerprint_label": "Documentvingerafdruk (SHA-256)",
        }
    return {
        "basis_of_value": "Market value for M&A purposes",
        "premise_of_value": "Going concern",
        "scope_of_work": (
            "Indicative SME valuation based on submitted data and available market evidence"
        ),
        "standard_reference": "IVS-inspired SME M&A report structure",
        "basis_label": "Basis of value",
        "premise_label": "Premise",
        "scope_label": "Scope",
        "standard_label": "Report standard",
        "reference_label": "Report reference",
        "engine_label": "Calculation model version",
        "fingerprint_label": "Document fingerprint (SHA-256)",
    }


def _empty_attestation_context() -> dict[str, object]:
    return {
        "has_attestation_page": False,
        "attestation": None,
        "attestation_summary_rows": [],
        "attestation_preparer_display": None,
        "attestation_client_display": None,
    }


def _is_specialty_report(context: ReportMapping) -> bool:
    return bool(context.get("is_startup_valuation_report") or context.get("is_liquidation_report"))


def _attestation_firm_name(
    context: ReportMapping,
    metadata: ReportMapping | None,
) -> str | None:
    return _metadata_value(metadata, "accountant_firm_name") or _clean(
        context.get("accountant_firm_name")
    )


def _attestation_requested(metadata: ReportMapping | None) -> bool | None:
    return _metadata_bool(
        metadata,
        "show_attestation",
        "enable_attestation",
        "include_attestation",
    )


def _attestation_identity(
    context: ReportMapping,
    metadata: ReportMapping | None,
) -> tuple[str | None, str | None, str | None, str | None]:
    preparer_name = _metadata_value(
        metadata,
        "preparer_name",
        "accountant_name",
        "engagement_partner",
        "advisor_name",
    )
    client_name = _metadata_value(metadata, "client_name") or _clean(context.get("company_name"))
    # Route through the same formatter the page header / cover / disclaimers use
    # so the attestation reference can never diverge from the rest of the document
    # (the stale-render divergence showed a raw internal code on the attestation
    # vs "VAL-YYYY-XXXX" in the header). Idempotent: an already-formatted "VAL-"
    # ref or a non-UUID legacy code is returned unchanged.
    _raw_ref = _clean(context.get("report_id_display")) or _clean(context.get("report_id"))
    report_ref = format_valuation_reference(_raw_ref, context.get("valuation_date")) or _raw_ref
    engine_version = _public_model_version(
        _metadata_value(metadata, "engine_version", "valuation_engine_version")
        or _clean(context.get("engine_version"))
    )
    return preparer_name, client_name, report_ref, engine_version


def _attestation_scope(
    metadata: ReportMapping | None,
    defaults: dict[str, str],
) -> dict[str, str]:
    return {
        "basis_of_value": (
            _metadata_value(metadata, "basis_of_value", "valuation_basis_statement")
            or defaults["basis_of_value"]
        ),
        "premise_of_value": (
            _metadata_value(metadata, "premise_of_value") or defaults["premise_of_value"]
        ),
        "scope_of_work": (
            _metadata_value(metadata, "scope_of_work", "valuation_scope")
            or defaults["scope_of_work"]
        ),
        "standard_reference": (
            _metadata_value(metadata, "standard_reference", "report_standard")
            or defaults["standard_reference"]
        ),
    }


def _attestation_summary_rows(
    *,
    defaults: dict[str, str],
    scope: dict[str, str],
    report_ref: str | None,
    engine_version: str | None,
) -> list[SummaryRow]:
    summary_rows: list[SummaryRow] = [
        {"label": defaults["basis_label"], "value": scope["basis_of_value"]},
        {"label": defaults["premise_label"], "value": scope["premise_of_value"]},
        {"label": defaults["scope_label"], "value": scope["scope_of_work"]},
        {"label": defaults["standard_label"], "value": scope["standard_reference"]},
        {"label": defaults["reference_label"], "value": report_ref},
    ]
    if engine_version:
        summary_rows.append({"label": defaults["engine_label"], "value": engine_version})
    return summary_rows


def _attestation_content_payload(
    context: ReportMapping,
    *,
    firm_name: str,
    preparer_name: str | None,
    client_name: str | None,
    report_ref: str | None,
    engine_version: str | None,
    scope: dict[str, str],
) -> dict[str, object]:
    return {
        "report_id": report_ref,
        "client": client_name,
        "valuation_date": _clean(context.get("valuation_date")),
        "basis_of_value": scope["basis_of_value"],
        "premise_of_value": scope["premise_of_value"],
        "scope_of_work": scope["scope_of_work"],
        "standard_reference": scope["standard_reference"],
        "engine_version": engine_version,
        "preparer_firm_name": firm_name,
        "preparer_name": preparer_name,
        # Bind the attestation to the financial claims as well as the parties.
        # Recalculating the same client/date must invalidate an earlier seal.
        "financial_claims": {key: context.get(key) for key in (
            "enterprise_value_low", "enterprise_value_mid", "enterprise_value_high",
            "equity_value_low", "equity_value", "equity_value_high",
            "recommended_asking_price", "valuation_methodology",
            "adaptive_dcf_weight", "adaptive_multiples_weight",
            "sustainable_ebitda", "reported_ebitda", "latest_normalized_ebitda",
            "total_adjustments", "applied_multiple", "net_debt", "has_balance_data",
            "multi_year_ebitda", "normalization_adjustments",
            "fiscal_ebitda_component", "fiscal_book_equity",
        )},
    }


def _attestation_valuer(
    metadata: ReportMapping | None,
    *,
    preparer_name: str | None,
    firm_name: str,
) -> dict[str, str | None]:
    return {
        "name": preparer_name,
        "firm": firm_name,
        "itaa_number": _metadata_value(
            metadata,
            "itaa_number",
            "valuer_itaa_number",
            "preparer_itaa_number",
        ),
        "ire_number": _metadata_value(
            metadata,
            "ire_number",
            "ibr_number",
            "valuer_ire_number",
            "preparer_ire_number",
        ),
        "nba_number": _metadata_value(
            metadata,
            "nba_number",
            "valuer_nba_number",
            "preparer_nba_number",
        ),
    }


def _attestation_result(
    *,
    attestation: dict[str, object],
    summary_rows: list[SummaryRow],
    client_name: str | None,
    hash_lock: ReportMapping,
    queue_payload: ReportMapping,
    cover_seal: dict[str, object] | None,
) -> dict[str, object]:
    return {
        "has_attestation_page": True,
        "attestation": attestation,
        "attestation_summary_rows": summary_rows,
        "attestation_preparer_display": attestation["preparer_display"],
        "attestation_client_display": client_name,
        "attestation_content_hash": hash_lock["content_hash"],
        "attestation_queue_payload": queue_payload,
        "attestation_cover_seal": cover_seal,
        "attestation_signed": cover_seal is not None,
    }


def build_attestation_context(
    context: ReportMapping,
    *,
    metadata: ReportMapping | None = None,
    locale: str = "nl",
) -> dict[str, object]:
    """Build first-class attestation context from report metadata.

    The page remains enterprise/accountant-branded: a firm name is required
    unless a future commercial gate deliberately changes that policy.
    """

    firm_name = _attestation_firm_name(context, metadata)
    requested = _attestation_requested(metadata)
    if not firm_name or requested is False or _is_specialty_report(context):
        return _empty_attestation_context()

    d = _defaults(locale)
    preparer_name, client_name, report_ref, engine_version = _attestation_identity(
        context,
        metadata,
    )
    scope = _attestation_scope(metadata, d)

    summary_rows = _attestation_summary_rows(
        defaults=d,
        scope=scope,
        report_ref=report_ref,
        engine_version=engine_version,
    )
    content_payload = _attestation_content_payload(
        context,
        firm_name=firm_name,
        preparer_name=preparer_name,
        client_name=client_name,
        report_ref=report_ref,
        engine_version=engine_version,
        scope=scope,
    )
    # BET-298 — tamper-evident hash-lock over the material attestation facts.
    # Any change to the signed claims changes this fingerprint, so a
    # re-rendered report fails verification against the hash that was signed.
    hash_lock = build_hash_lock(content_payload)
    summary_rows.append({"label": d["fingerprint_label"], "value": hash_lock["short_hash"]})

    eidas_tier = _metadata_value(metadata, "eidas_tier", "attestation_eidas_tier") or "AES"
    valuer = _attestation_valuer(
        metadata,
        preparer_name=preparer_name,
        firm_name=firm_name,
    )
    cover_seal = _normalize_cover_seal(
        _incoming_attestation_seal(context, metadata),
        expected_hash_lock=hash_lock,
    )
    queue_payload = build_attestation_queue_payload(
        content_payload=content_payload,
        report_id=report_ref,
        engine_version=engine_version,
        valuer=valuer,
        eidas_tier=eidas_tier,
        verify_url=cover_seal.get("verify_url") if cover_seal else None,
    )

    attestation = {
        "preparer_firm_name": firm_name,
        "preparer_name": preparer_name,
        "preparer_display": f"{preparer_name} - {firm_name}" if preparer_name else firm_name,
        "client_display": client_name,
        "valuation_date": _clean(context.get("valuation_date")),
        "report_id": report_ref,
        "basis_of_value": scope["basis_of_value"],
        "premise_of_value": scope["premise_of_value"],
        "scope_of_work": scope["scope_of_work"],
        "standard_reference": scope["standard_reference"],
        "engine_version": engine_version,
        "hash_lock": hash_lock,
        "content_hash": hash_lock["content_hash"],
        "queue_payload": queue_payload,
        "seal": cover_seal,
        "summary_rows": summary_rows,
    }

    return _attestation_result(
        attestation=attestation,
        summary_rows=summary_rows,
        client_name=client_name,
        hash_lock=hash_lock,
        queue_payload=queue_payload,
        cover_seal=cover_seal,
    )
