"""Fail-closed, binary-only rendering for publishable valuation memoranda."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from io import BytesIO
from pathlib import Path

import pikepdf
import weasyprint

from src.api.schemas.sealed_report_schemas import (
    ReportRenderReceiptV1,
    ReportRenderReceiptV2,
    ReportRenderSnapshotV1,
    ReportRenderSnapshotV2,
)
from src.services.infrastructure.pdf.pdf_validator import PDFValidator
from src.services.infrastructure.pdf.pdfa_conformance_validator import (
    PdfaConformanceValidationError,
    validate_pdfa_2b,
)
from src.services.infrastructure.report_generation.metrics_collector import (
    MetricsCollector,
)
from src.services.infrastructure.report_generation.strategies.pdf_strategy import (
    PDFGenerationStrategy,
)
from src.services.reports.formula_consistency_gate import apply_gate_to_context
from src.services.reports.report_design_manifest import (
    ReportDesignManifestError,
    build_report_design_manifest,
)
from src.services.reports.sealed_method_pack_gate import (
    SealedMethodPackError,
    assert_sealed_method_pack,
)
from src.services.reports.sealed_memorandum_model import (
    SealedMemorandumModelError,
    build_sealed_memorandum_model,
)
from src.services.reports.sealed_report_display_model import (
    SealedDisplayModelError,
    build_sealed_report_display_model,
)
from src.services.reports.sealed_report_html_audit import (
    SealedReportHtmlAuditError,
    audit_sealed_report_html,
)
from src.services.reports.sealed_report_pack import (
    SealedReportPackError,
    build_sealed_report_pack,
)
from src.services.reports.sealed_template_policy import (
    SealedTemplatePolicyError,
    assert_sealed_template_policy,
)
from src.services.reports.stateless_report_context import build_stateless_report_context
from src.services.reports.stateless_valuation_run import canonical_hash


class SealedReportRenderError(RuntimeError):
    def __init__(self, code: str, message: str, diagnostics: object | None = None):
        super().__init__(message)
        self.code = code
        self.diagnostics = diagnostics


_DISPLAY_COMMITMENT_FIELDS = (
    "engagement_scope",
    "registry_snapshot",
    "report_assurance_level",
    "selected_method",
    "multiple_metric_type",
    "sustainable_ebitda",
    "valuation_basis_value",
    "applied_multiple",
    "enterprise_value_low",
    "enterprise_value_mid",
    "enterprise_value_high",
    "net_debt",
    "cash",
    "debt",
    "nwc_adjustment",
    "nwc_surplus_deficit",
    "tax_latency_net_impact",
    "equity_value_low",
    "equity_value",
    "equity_value_mid",
    "equity_value_high",
    "normalization_adjustments",
    "benchmark_contract",
    "valuation_methodology_display",
    "defensibility_checks",
    "sealed_display",
    "sealed_memorandum",
)


def _template_bundle_hash() -> str:
    root = Path(__file__).resolve().parents[2] / "templates" / "main_report_pdf"
    digest = hashlib.sha256()
    files = sorted(path for path in root.rglob("*") if path.is_file())
    if not files:
        raise SealedReportRenderError(
            "TEMPLATE_BUNDLE_MISSING",
            "The audited report template bundle is unavailable.",
        )
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        content = path.read_bytes()
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def _renderer_revision() -> str:
    return (
        os.getenv("RAILWAY_GIT_COMMIT_SHA")
        or os.getenv("GIT_COMMIT_SHA")
        or os.getenv("SOURCE_VERSION")
        or "local-unidentified"
    )


def _encode_receipt_header(
    receipt: ReportRenderReceiptV1 | ReportRenderReceiptV2,
) -> str:
    encoded = json.dumps(
        receipt.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return base64.urlsafe_b64encode(encoded).rstrip(b"=").decode("ascii")


async def render_sealed_report(
    snapshot: ReportRenderSnapshotV1 | ReportRenderSnapshotV2,
) -> tuple[bytes, ReportRenderReceiptV1 | ReportRenderReceiptV2, str]:
    """Render exactly once. No stale HTML, arithmetic fallback or error PDF exists here."""

    request = snapshot.report_request
    try:
        report_context = build_stateless_report_context(request, locale=snapshot.locale)
    except Exception as exc:
        raise SealedReportRenderError(
            "REPORT_CONTEXT_BUILD_FAILED",
            "The sealed report context could not be built.",
            {"error_type": type(exc).__name__, "message": str(exc)},
        ) from exc

    context = report_context.template_context
    gate = apply_gate_to_context(context, soft=False)
    if not gate.passed:
        raise SealedReportRenderError(
            "REPORT_FORMULA_INVARIANTS_FAILED",
            "The sealed report failed formula or EV-to-equity reconciliation.",
            gate.to_context_dict(),
        )
    try:
        sealed_display = build_sealed_report_display_model(context)
    except SealedDisplayModelError as exc:
        raise SealedReportRenderError(
            "REPORT_DISPLAY_MODEL_INVALID",
            "The sealed report display projection could not be constructed.",
            {"message": str(exc)},
        ) from exc
    context["render_snapshot_sha256"] = snapshot.snapshot_sha256
    context["sealed_valuation_run_hash"] = snapshot.valuation_run_hash
    context["sealed_evidence_bundle_hash"] = snapshot.evidence_bundle_hash
    context["sealed_benchmark_hash"] = snapshot.benchmark_hash
    context["sealed_template_contract_version"] = snapshot.template_contract_version
    if isinstance(snapshot, ReportRenderSnapshotV2):
        context["professional_review"] = snapshot.professional_review.model_dump(
            mode="json"
        )
    branding = (
        request.branding.model_dump(mode="json", exclude_none=True)
        if request.branding is not None
        else {}
    )
    try:
        design_manifest = build_report_design_manifest(
            branding=branding,
            locale=snapshot.locale,
        )
        design_manifest_hash = canonical_hash(design_manifest)
        if (
            isinstance(snapshot, ReportRenderSnapshotV2)
            and design_manifest_hash != snapshot.design_manifest_hash
        ):
            raise ReportDesignManifestError(
                "protected design manifest changed after the render snapshot was sealed"
            )
        context["report_design_manifest"] = design_manifest
        context["report_design_manifest_hash"] = design_manifest_hash
        sealed_memorandum = build_sealed_memorandum_model(context)
        context["sealed_report_sections"] = build_sealed_report_pack(context)
        assert_sealed_template_policy()
    except (
        SealedMemorandumModelError,
        SealedReportPackError,
        SealedTemplatePolicyError,
        ReportDesignManifestError,
    ) as exc:
        raise SealedReportRenderError(
            "SEALED_REPORT_PACK_INVALID",
            "The audited memorandum display or template pack is invalid.",
            {"message": str(exc)},
        ) from exc
    try:
        assert_sealed_method_pack(context)
    except SealedMethodPackError as exc:
        raise SealedReportRenderError(exc.code, str(exc), exc.diagnostics) from exc

    display_model_hash = canonical_hash(
        {"sealed_display": sealed_display, "sealed_memorandum": sealed_memorandum}
    )
    context["sealed_display_model_hash"] = display_model_hash

    try:
        html = report_context.template_service.render_main_report_pdf(
            context, locale=snapshot.locale
        )
    except Exception as exc:
        raise SealedReportRenderError(
            "REPORT_TEMPLATE_RENDER_FAILED",
            "The audited memorandum template failed to render.",
            {"error_type": type(exc).__name__, "message": str(exc)},
        ) from exc
    if len(html) < 500 or "valuation-report" not in html or "cover-page" not in html:
        raise SealedReportRenderError(
            "REPORT_TEMPLATE_OUTPUT_INVALID",
            "The audited memorandum template produced incomplete output.",
        )
    try:
        html_audit = audit_sealed_report_html(
            html,
            snapshot_sha256=snapshot.snapshot_sha256,
            valuation_run_hash=snapshot.valuation_run_hash,
            display_model_hash=display_model_hash,
            locale=snapshot.locale,
            assurance_level=snapshot.assurance_level,
        )
    except SealedReportHtmlAuditError as exc:
        raise SealedReportRenderError(exc.code, str(exc), exc.diagnostics) from exc
    prohibited_deliverable_copy = {
        "nl": ("vraagprijs", "transactiegereedheid"),
        "fr": ("prix demandé", "préparation à la transaction"),
        "en": ("asking price", "transaction readiness"),
    }
    forbidden = [
        phrase for phrase in prohibited_deliverable_copy[snapshot.locale] if phrase in html.lower()
    ]
    if forbidden:
        raise SealedReportRenderError(
            "REPORT_DELIVERABLE_SCOPE_VIOLATION",
            "The valuation memorandum contains content reserved for a separate deliverable.",
            {"forbidden_phrases": forbidden},
        )

    strategy = PDFGenerationStrategy(metrics_collector=MetricsCollector())
    pdf_bytes = await strategy.generate(
        html_content=html,
        template_data={
            "company_name": request.company_name,
            "company_id": request.valuation_result.valuation_id,
            "valuation_id": request.valuation_result.valuation_id,
            "valuation_date": request.valuation_date,
            "archival_pdfa": True,
            "pdfa_profile": "PDF/A-2b",
            "artifact_timestamp": request.valuation_result.valuation_run.recording_timestamp,
            "artifact_identifier": snapshot.snapshot_sha256,
            "locale": snapshot.locale,
        },
        correlation_id=snapshot.report_id[:16],
    )
    if not pdf_bytes or len(pdf_bytes) < 500 or not pdf_bytes.startswith(b"%PDF-"):
        raise SealedReportRenderError(
            "REPORT_PDF_RENDER_FAILED",
            "The renderer did not produce a valid PDF artifact.",
        )

    validation = PDFValidator().validate_pdf(pdf_bytes)
    if (
        not validation.is_valid_pdfa
        or not validation.fonts_embedded
        or validation.encryption_level != "none"
        or validation.page_count < 1
    ):
        raise SealedReportRenderError(
            "REPORT_PDFA_VALIDATION_FAILED",
            "The rendered artifact failed the structural PDF/A preflight.",
            validation.to_dict(),
        )

    try:
        conformance = validate_pdfa_2b(pdf_bytes)
    except PdfaConformanceValidationError as exc:
        raise SealedReportRenderError(
            "REPORT_PDFA_CONFORMANCE_VALIDATION_FAILED",
            "Independent PDF/A-2b conformance could not be established.",
            {"message": str(exc)},
        ) from exc
    if conformance is not None and not conformance.is_compliant:
        raise SealedReportRenderError(
            "REPORT_PDFA_CONFORMANCE_FAILED",
            "The rendered artifact is not PDF/A-2b conformant.",
            {
                "validator": conformance.engine,
                "validator_version": conformance.validator_version,
                "failed_rules": conformance.failed_rules,
                "failed_checks": conformance.failed_checks,
                "validation_report_sha256": conformance.report_sha256,
            },
        )

    if conformance is None:
        # Local development can still exercise layout and formula gates, but
        # Titan will refuse to publish this receipt because it lacks an
        # independent conformance result. Production images require veraPDF.
        validation_report_sha256 = canonical_hash(validation.to_dict())
        validation_engine = "internal_structural_preflight"
        validator_version = "upswitch-pdf-validator.v1"
        pdfa_valid = False
    else:
        validation_report_sha256 = conformance.report_sha256
        validation_engine = conformance.engine
        validator_version = conformance.validator_version
        pdfa_valid = True

    # Opening with a second parser catches malformed cross-reference tables
    # independently of the renderer's success return.
    with pikepdf.Pdf.open(BytesIO(pdf_bytes)) as document:
        page_count = len(document.pages)

    pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    display_context = {
        "report_fields": {key: context.get(key) for key in _DISPLAY_COMMITMENT_FIELDS},
        "sealed_display_model_hash": display_model_hash,
        "html_audit": html_audit,
    }
    receipt_fields = {
        "schema_version": (
            "report_render_receipt.v2"
            if isinstance(snapshot, ReportRenderSnapshotV2)
            else "report_render_receipt.v1"
        ),
        "render_snapshot_hash": snapshot.snapshot_sha256,
        "valuation_run_hash": snapshot.valuation_run_hash,
        "report_context_hash": canonical_hash(display_context),
        "template_bundle_hash": _template_bundle_hash(),
        "renderer_revision": _renderer_revision(),
        "renderer_version": f"weasyprint-{weasyprint.__version__}",
        "pdf_sha256": pdf_sha256,
        "page_count": page_count,
        "size_bytes": len(pdf_bytes),
        "mime_type": "application/pdf",
        "pdfa_profile": "PDF/A-2b",
        "pdfa_valid": pdfa_valid,
        "pdfa_validation_engine": validation_engine,
        "pdfa_validator_version": validator_version,
        "pdfa_validation_report_sha256": validation_report_sha256,
        "fonts_embedded": True,
        "encrypted": False,
        "locale": snapshot.locale,
    }
    if isinstance(snapshot, ReportRenderSnapshotV2):
        receipt_fields.update(
            {
                "design_manifest_hash": snapshot.design_manifest_hash,
                "industry_icon_registry_hash": snapshot.design_manifest.industry_icon_registry_hash,
                "business_card_motif_hash": snapshot.design_manifest.business_card_motif_hash,
                "deterministic_build": True,
            }
        )
        receipt: ReportRenderReceiptV1 | ReportRenderReceiptV2 = ReportRenderReceiptV2(
            **receipt_fields,
            receipt_sha256=canonical_hash(receipt_fields),
        )
    else:
        receipt = ReportRenderReceiptV1(
            **receipt_fields,
            receipt_sha256=canonical_hash(receipt_fields),
        )
    return pdf_bytes, receipt, _encode_receipt_header(receipt)
