"""T4-506 immutable report manifest and release-policy assembly."""

from __future__ import annotations

import base64
import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from pydantic import BaseModel

from src.api.schemas.stateless_report_schemas import (
    GenerateReportRequest,
    ReportArtifactDigest,
    ReportManifest,
)
from src.api.schemas.valuation_assurance_security import ValuationAssuranceEnvelopeV2
from src.api.schemas.valuation_contracts import ValuationRunV2
from src.services.reports.report_assurance import CERTIFIED_CALCULATION_STATUSES
from src.services.reports.stateless_valuation_run import canonical_hash, canonical_json_bytes
from src.services.reports.valuation_assurance_status import CurrentValuationAssuranceAuthority

REPORT_TEMPLATE_VERSION = "2.1.0"
REPORT_MANIFEST_SCHEMA_VERSION = "report_manifest.v1"
REPORT_MANIFEST_INTEGRITY_VERSION = "report_manifest_integrity.v1"
REPORT_RENDERER_CONTRACT_VERSION = "weasyprint_renderer.v1"

_REPORT_BUNDLE_DIRECTORY_INPUTS = (
    "src/templates/main_report",
    "src/templates/main_report_pdf",
    "src/templates/shared",
    "src/services/infrastructure/report_translation_catalog_nl_sections",
    "src/services/infrastructure/report_translation_catalog_en_sections",
    "src/services/infrastructure/report_translation_catalog_fr_sections",
    "src/services/infrastructure/report_translation_model",
    "src/services/infrastructure/report_translation_contract",
    "src/assets/fonts",
)
_REPORT_BUNDLE_FILE_INPUTS = (
    "requirements.lock",
    "src/services/reports/automated_indicative_renderer.py",
    "src/services/reports/automated_indicative_policy.py",
    "src/services/infrastructure/pdf/font_css.py",
    "src/services/infrastructure/report_generation/strategies/pdf_strategy.py",
    "src/services/infrastructure/weasyprint_env.py",
    "src/services/infrastructure/translations.py",
    "src/services/infrastructure/report_translation_catalog.py",
    "src/services/infrastructure/report_translation_catalog_en.py",
    "src/services/infrastructure/report_translation_catalog_fr.py",
    "src/services/infrastructure/report_translation_catalog_nl.py",
    "src/services/infrastructure/report_locale.py",
    "src/config/country_packs.py",
    "src/domain/dcf_policy.py",
    "src/domain/forward_method_contract.py",
    "src/domain/forward_method_registry.py",
    "src/domain/forward_method_specs.py",
    "src/domain/method_keys.py",
    "src/domain/method_certification_profiles.py",
    "src/domain/methodology_eligibility_decider.py",
    "src/services/reports/method_component_registry.py",
    "src/services/reports/stateless_benchmark_policy.py",
    "src/services/reports/stateless_method_weight_governance.py",
    "src/services/reports/stateless_methodology_selection.py",
    "src/api/routes/valuation/orchestration/executors/comprehensive/methodology_decision_policy.py",
)


class ReportContractUnavailable(ValueError):
    """The caller supplied no v2 run from which to build a T4-506 report."""


class ReportPublicationBlocked(ValueError):
    """A final artifact was requested while the sealed release gate is closed."""

    def __init__(self, manifest: ReportManifest):
        super().__init__("report is not publishable under the immutable release contract")
        self.manifest = manifest


@dataclass(frozen=True)
class ReportReleaseDecision:
    generation_status: str
    publication_status: str
    reviewer_requirement: str
    review_points: list[str]


def _is_canonical_recovery_assessment(run: ValuationRunV2) -> bool:
    recovery_resolution = run.response_snapshot.get("negative_ebitda_resolution")
    return bool(
        isinstance(recovery_resolution, Mapping)
        and recovery_resolution.get("status")
        in {
            "normalized_positive",
            "recovery_eligible",
            "revenue_benchmark_eligible",
            "asset_floor_only",
            "no_going_concern_range",
        }
    )


def report_release_decision(
    run: ValuationRunV2,
    *,
    assurance_authority: CurrentValuationAssuranceAuthority | None = None,
) -> ReportReleaseDecision:
    if _is_projection_only_run(run):
        return ReportReleaseDecision(
            generation_status="diagnostic_preview",
            publication_status="blocked",
            reviewer_requirement="advisor_review",
            review_points=[
                "A current-lens timeline projection is not an independently releasable valuation."
            ],
        )
    assurance_envelope: ValuationAssuranceEnvelopeV2 | None = (
        assurance_authority.envelope if assurance_authority is not None else None
    )
    declared_confidence = (
        assurance_envelope.evidence_confidence.band.upper()
        if assurance_envelope is not None
        else run.assurance.evidence_confidence.level
    )
    score = (
        int(Decimal(assurance_envelope.evidence_confidence.score))
        if assurance_envelope is not None
        else run.assurance.evidence_confidence.score
    )
    confidence = effective_confidence_band(
        declared_level=declared_confidence,
        score=score,
    )
    points: list[str] = []
    is_recovery_assessment = _is_canonical_recovery_assessment(run)

    if confidence != declared_confidence:
        points.append(
            f"Confidence label {declared_confidence} is capped to {confidence} by score {score}."
        )

    # A verified envelope binds an active advisor-verification receipt.  A
    # review declaration inside the calculation run is not equivalent Titan
    # publication authority.
    advisor_review = "accepted" if assurance_envelope is not None else "missing"
    if confidence == "HIGH":
        generation = "draft_auto"
        publication = "publishable"
        reviewer = "none"
    elif confidence == "MEDIUM":
        if is_recovery_assessment:
            generation = "draft_auto"
            publication = "publishable"
            reviewer = "none"
            points.append(
                "The canonical recovery assessment is releasable on its signed owner "
                "attestation or governed benchmark/floor evidence; advisor review is optional."
            )
        elif advisor_review == "accepted":
            generation = "draft_auto"
            publication = "publishable"
            reviewer = "none"
            points.append("Medium-confidence valuation has a sealed advisor acceptance.")
        elif advisor_review == "rejected":
            generation = "draft_review_required"
            publication = "blocked"
            reviewer = "advisor_review"
            points.append("A sealed advisor review rejected final publication.")
        else:
            generation = "draft_review_required"
            publication = "review_required"
            reviewer = "advisor_review"
            points.append("Medium-confidence valuation requires advisor review.")
    else:
        generation = "diagnostic_preview"
        publication = "blocked"
        reviewer = "classification_or_benchmark_review"
        points.append("Low-confidence valuation cannot be published as a final report.")

    if advisor_review == "rejected" and confidence != "MEDIUM":
        publication = "blocked"
        reviewer = "advisor_review"
        if generation == "draft_auto":
            generation = "draft_review_required"
        points.append("A sealed advisor review rejected final publication.")

    certification_status = (
        assurance_envelope.calculation_certification.status
        if assurance_envelope is not None
        else "uncertified"
    )
    if certification_status not in CERTIFIED_CALCULATION_STATUSES:
        publication = "blocked"
        reviewer = "calculation_certification" if is_recovery_assessment else "advisor_review"
        if generation == "draft_auto" and not is_recovery_assessment:
            generation = "draft_review_required"
        points.append(
            "The canonical calculation lacks a verified Titan assurance envelope; "
            "evidence maturity, confidence, and legal attestation do not authorize "
            "final publication."
        )
    country_pack_state = run.assurance.country_pack_certification_state
    if country_pack_state != "certified":
        publication = "blocked"
        reviewer = "classification_or_benchmark_review"
        if generation == "draft_auto":
            generation = "diagnostic_preview"
        points.append(
            f"Country pack {run.country_pack_version} certification is {country_pack_state}; "
            "draft, expired, or revoked policy cannot authorize a final report."
        )
    if not run.assurance.method_country_certification_eligible:
        publication = "blocked"
        reviewer = "classification_or_benchmark_review"
        if generation == "draft_auto":
            generation = "diagnostic_preview"
        points.append(
            "One or more priced methods are not eligible under the sealed country and "
            f"{run.assurance.method_certification_profile_version} registry."
        )

    content = run.content_provenance
    uses_llm = "llm_generated" in {
        content.narrative_origin,
        content.evidence_origin,
    }
    if uses_llm and content.review_state != "approved":
        generation = "diagnostic_preview"
        publication = "blocked"
        reviewer = "advisor_review"
        points.append("Unreviewed or rejected LLM-generated report content is never publishable.")

    if run.classification_resolution.resolution_status != "resolved":
        generation = "diagnostic_preview"
        publication = "blocked"
        reviewer = "classification_or_benchmark_review"
        points.append("Business type and NACE classification requires review.")

    if run.uploaded_data_snapshot_status == "attested_non_priced":
        generation = "diagnostic_preview"
        publication = "blocked"
        reviewer = "classification_or_benchmark_review"
        points.append(
            "Titan T4/T5 uploaded-data snapshot is pinned for audit but is not "
            "authorized as priced accounting evidence."
        )

    if _uses_untrusted_fallback(run):
        generation = "diagnostic_preview"
        publication = "blocked"
        reviewer = "classification_or_benchmark_review"
        points.append("Untrusted disclosed benchmark fallback is never publishable.")
    elif (
        _uses_priced_market_method(run)
        and not run.benchmark_snapshot_references
        and not _uses_governed_external_market_reference(run)
    ):
        generation = "diagnostic_preview"
        publication = "blocked"
        reviewer = "classification_or_benchmark_review"
        points.append("A priced market method has no pinned benchmark snapshot.")

    sealed_block_points = _sealed_publication_block_points(
        run,
        evidence_tier_override=(
            assurance_envelope.graph_tier if assurance_envelope is not None else None
        ),
    )
    if sealed_block_points:
        publication = "blocked"
        reviewer = "classification_or_benchmark_review"
        if generation == "draft_auto":
            generation = "diagnostic_preview"
        points.extend(sealed_block_points)

    if score < 0 or score > 100:
        publication = "blocked"
        reviewer = "classification_or_benchmark_review"
        points.append("Confidence score is outside the report contract bounds.")

    return ReportReleaseDecision(
        generation_status=generation,
        publication_status=publication,
        reviewer_requirement=reviewer,
        review_points=list(dict.fromkeys(points)),
    )


def scoped_report_release_decision(
    run: ValuationRunV2,
    *,
    report_scope: str = "standard",
    assurance_authority: CurrentValuationAssuranceAuthority | None = None,
) -> ReportReleaseDecision:
    """Resolve standard certification or limited client-indicative release.

    ``client_indicative`` deliberately does not promote calculation
    certification, evidence maturity, legal attestation, customer persistence,
    or T4. It is a narrower handoff policy with strict evidence gates. Canonical
    recovery assessments use signed owner attestation and never depend on an
    advisor being available.
    """

    if _is_projection_only_run(run):
        return ReportReleaseDecision(
            generation_status="diagnostic_preview",
            publication_status="blocked",
            reviewer_requirement="advisor_review",
            review_points=[
                "A current-lens timeline projection is not an independently releasable valuation."
            ],
        )

    if report_scope == "automated_indicative":
        from src.services.reports.automated_indicative_policy import automatic_release_blockers

        points = automatic_release_blockers(run)
        return ReportReleaseDecision(
            generation_status="diagnostic_preview" if points else "automated_indicative",
            publication_status="blocked" if points else "publishable",
            reviewer_requirement="none",
            review_points=points
            or [
                "Automatic indicative estimate; assumptions retain their evidence status. Private saving and export are permitted."
            ],
        )

    if report_scope != "client_indicative":
        return report_release_decision(run, assurance_authority=assurance_authority)

    points: list[str] = []
    is_recovery_assessment = _is_canonical_recovery_assessment(run)
    reviewer = "none" if is_recovery_assessment else "advisor_review"
    confidence = effective_confidence_band(
        declared_level=run.assurance.evidence_confidence.level,
        score=run.assurance.evidence_confidence.score,
    )
    if confidence == "LOW":
        points.append("Low-confidence calculations cannot be released to an indicative client.")
        reviewer = "classification_or_benchmark_review"
    if run.assurance.evidence_maturity.tier not in {"T2", "T3"}:
        points.append(
            "client_indicative requires T2/T3 evidence and cannot masquerade as a T4 artifact."
        )
    if str(run.response_snapshot.get("data_tier") or "").lower() != "indicative":
        points.append("client_indicative must retain the indicative calculation tier.")
    if not is_recovery_assessment and _governed_advisor_review_state(run) != "accepted":
        points.append("A sealed advisor acceptance is required for client delivery.")
    if run.classification_resolution.resolution_status != "resolved":
        points.append("Business type and NACE classification requires review.")
        reviewer = "classification_or_benchmark_review"
    content = run.content_provenance
    if "llm_generated" in {content.narrative_origin, content.evidence_origin} and (
        content.review_state != "approved"
    ):
        if is_recovery_assessment:
            points.append(
                "Canonical recovery delivery requires deterministic report copy; "
                "unapproved LLM-generated content is not releasable."
            )
            reviewer = "classification_or_benchmark_review"
        else:
            points.append("LLM-generated report content requires sealed advisor approval.")
    if run.uploaded_data_snapshot_status == "attested_non_priced":
        points.append("Unpriced uploaded financial evidence cannot support client delivery.")
    if run.evidence_hash_source != "accounting_evidence_package":
        points.append("Client delivery requires a priced AccountingEvidencePackage.")
    lineage = run.calculation_lineage if isinstance(run.calculation_lineage, Mapping) else {}
    if not isinstance(lineage.get("valuation_case_attestation"), Mapping):
        points.append("Client delivery requires a Titan-signed valuation_case.v2.")

    if _uses_untrusted_fallback(run):
        points.append("An untrusted fallback cannot support client delivery.")
        reviewer = "classification_or_benchmark_review"
    elif (
        _uses_priced_market_method(run)
        and not run.benchmark_snapshot_references
        and not _uses_governed_external_market_reference(run)
    ):
        points.append("The priced market method has no governed evidence contract.")
        reviewer = "classification_or_benchmark_review"
    if _uses_priced_dcf_method(run) and not _uses_direct_sector_wacc(run):
        points.append("The priced DCF has no sealed direct-sector WACC contract.")
        reviewer = "classification_or_benchmark_review"

    points.extend(_sealed_publication_block_points(run, require_final_maturity=False))
    points = list(dict.fromkeys(points))
    if points:
        return ReportReleaseDecision(
            generation_status="diagnostic_preview",
            publication_status="blocked",
            reviewer_requirement=reviewer,
            review_points=points,
        )
    return ReportReleaseDecision(
        generation_status="client_indicative",
        publication_status="publishable",
        reviewer_requirement="none",
        review_points=[
            "Approved for client delivery — indicative/as-reported; customer persistence "
            "and T4 remain prohibited by report scope."
        ],
    )


def _is_projection_only_run(run: ValuationRunV2) -> bool:
    lineage = run.calculation_lineage
    if not isinstance(lineage, Mapping):
        return False
    projection = lineage.get("timeline_projection")
    if isinstance(projection, Mapping):
        return bool(
            projection.get("calculation_purpose") == "current_lens_timeline_projection"
            and projection.get("independent_release_authorized") is False
        )
    # Backward-compatible recognition for projection runs sealed during the
    # short-lived top-level lineage rollout. Headline runs never carried these
    # values before that rollout.
    return bool(
        lineage.get("calculation_purpose") == "current_lens_timeline_projection"
        and lineage.get("independent_release_authorized") is False
    )


def build_report_manifest(
    *,
    request: GenerateReportRequest,
    generated_at: str,
    verified_assurance_authority: CurrentValuationAssuranceAuthority | None = None,
    artifact_digests: list[ReportArtifactDigest] | None = None,
    generation_warnings: list[str] | None = None,
    artifacts_finalized: bool = False,
) -> ReportManifest:
    run = request.valuation_result.valuation_run
    if not isinstance(run, ValuationRunV2):
        raise ReportContractUnavailable("T4-506 report generation requires valuation_run.v2")

    decision = scoped_report_release_decision(
        run,
        report_scope=request.report_scope,
        assurance_authority=verified_assurance_authority,
    )
    verified_assurance_envelope = (
        verified_assurance_authority.envelope if verified_assurance_authority is not None else None
    )
    report_id = request.report_id or (
        f"report_{canonical_hash({'run_id': run.run_id, 'generated_at': generated_at})[:24]}"
    )
    digests = list(artifact_digests or [])
    warnings = list(generation_warnings or [])
    generation_status = decision.generation_status
    publication_status = decision.publication_status
    reviewer_requirement = decision.reviewer_requirement
    review_points = list(decision.review_points)
    artifact_status = "pending"
    if artifacts_finalized and request.publication_intent == "final":
        artifact_points = _final_artifact_block_points(
            request=request,
            artifact_digests=digests,
            generation_warnings=warnings,
        )
        if artifact_points:
            artifact_status = "incomplete"
            generation_status = "diagnostic_preview"
            publication_status = "blocked"
            reviewer_requirement = (
                "classification_or_benchmark_review"
                if _is_canonical_recovery_assessment(run)
                else "advisor_review"
            )
            review_points.extend(artifact_points)
        else:
            artifact_status = "complete"
    elif artifacts_finalized:
        artifact_status = "complete"
    fields: dict[str, object] = {
        "schema_version": REPORT_MANIFEST_SCHEMA_VERSION,
        "integrity_version": REPORT_MANIFEST_INTEGRITY_VERSION,
        "report_id": report_id,
        "valuation_id": request.valuation_result.valuation_id,
        "valuation_run_id": run.run_id,
        "valuation_run_hash": run.run_hash,
        "generated_at": generated_at,
        "company_snapshot": run.company_snapshot,
        "uploaded_data_snapshot": run.uploaded_data_snapshot,
        "uploaded_data_snapshot_status": run.uploaded_data_snapshot_status,
        "classification_resolution": run.classification_resolution,
        "benchmark_snapshot_references": run.benchmark_snapshot_references,
        "source_citations": run.source_citations,
        "model_versions": {
            "engine_version": run.engine_version,
            "policy_version": run.policy_version,
            "confidence_model_version": run.confidence_model_version,
        },
        "normalization_adjustments": run.normalization_adjustments,
        "normalization_adjustments_hash": run.normalization_adjustments_hash,
        "report_review_decisions": run.report_review_decisions,
        "content_provenance": run.content_provenance,
        "assurance": run.assurance,
        "valuation_assurance_envelope": verified_assurance_envelope,
        "confidence_level": str(
            effective_confidence_band(
                declared_level=(
                    verified_assurance_envelope.evidence_confidence.band.upper()
                    if verified_assurance_envelope is not None
                    else run.assurance.evidence_confidence.level
                ),
                score=(
                    int(Decimal(verified_assurance_envelope.evidence_confidence.score))
                    if verified_assurance_envelope is not None
                    else run.assurance.evidence_confidence.score
                ),
            )
        ),
        "confidence_score": (
            int(Decimal(verified_assurance_envelope.evidence_confidence.score))
            if verified_assurance_envelope is not None
            else run.assurance.evidence_confidence.score
        ),
        "generation_status": generation_status,
        "publication_status": publication_status,
        "reviewer_requirement": reviewer_requirement,
        "review_points": list(dict.fromkeys(review_points)),
        "final_requested": request.publication_intent == "final",
        "report_scope": request.report_scope,
        "scope_prohibits_customer_persistence": request.report_scope == "client_indicative",
        "scope_prohibits_t4": request.report_scope in {"client_indicative", "automated_indicative"},
        "template_version": REPORT_TEMPLATE_VERSION,
        "template_bundle_hash": report_template_bundle_hash(),
        "artifact_digests": digests,
        "generation_warnings": warnings,
        "artifact_status": artifact_status,
    }
    core_hash = canonical_hash(report_manifest_core_commitment(fields))
    fields["manifest_hash"] = core_hash
    fields["manifest_id"] = f"rmanifest_{core_hash[:24]}"
    fields["artifact_envelope_hash"] = canonical_hash(report_artifact_envelope_commitment(fields))
    return ReportManifest.model_validate(fields)


def report_manifest_core_commitment(manifest: object) -> dict[str, object]:
    payload = _manifest_mapping(manifest)
    for field in (
        "manifest_id",
        "manifest_hash",
        "artifact_envelope_hash",
        "artifact_digests",
        "generation_warnings",
    ):
        payload.pop(field, None)
    return payload


def report_artifact_envelope_commitment(manifest: object) -> dict[str, object]:
    payload = _manifest_mapping(manifest)
    return {
        "manifest_hash": payload.get("manifest_hash"),
        "artifact_digests": payload.get("artifact_digests", []),
        "generation_warnings": payload.get("generation_warnings", []),
    }


def verify_report_manifest_integrity(manifest: object) -> None:
    payload = _manifest_mapping(manifest)
    expected = canonical_hash(report_manifest_core_commitment(payload))
    if payload.get("manifest_hash") != expected:
        raise ValueError("report_manifest manifest_hash integrity check failed")
    if payload.get("manifest_id") != f"rmanifest_{expected[:24]}":
        raise ValueError("report_manifest manifest_id does not match manifest_hash")
    envelope = canonical_hash(report_artifact_envelope_commitment(payload))
    if payload.get("artifact_envelope_hash") != envelope:
        raise ValueError("report_manifest artifact_envelope_hash integrity check failed")


def report_artifact_digests(
    *,
    html_report: str | None,
    pdf_base64: str | None,
    report_payload: Mapping[str, object] | None,
) -> list[ReportArtifactDigest]:
    rows: list[ReportArtifactDigest] = []
    if html_report is not None:
        rows.append(_artifact_digest("html", html_report.encode("utf-8")))
    if pdf_base64 is not None:
        rows.append(_artifact_digest("pdf", base64.b64decode(pdf_base64)))
    if report_payload is not None:
        payload_commitment = dict(report_payload)
        payload_commitment.pop("report_manifest", None)
        canonical_payload = canonical_json_bytes(payload_commitment)
        # The payload digest is the canonical JSON commitment, not a hash of a
        # self-referential manifest-bearing response object.
        rows.append(
            ReportArtifactDigest(
                artifact="report_payload",
                sha256=hashlib.sha256(canonical_payload).hexdigest(),
                bytes=len(canonical_payload),
            )
        )
    return rows


@lru_cache(maxsize=1)
def report_template_bundle_hash() -> str:
    project_root = Path(__file__).resolve().parents[3]
    try:
        renderer_version = version("weasyprint")
    except PackageNotFoundError:
        renderer_version = "unavailable"
    return _report_template_bundle_hash_at(
        project_root,
        renderer_version=renderer_version,
        strict=True,
    )


def _report_template_bundle_hash_at(
    project_root: Path,
    *,
    renderer_version: str,
    strict: bool,
) -> str:
    """Hash every deterministic report renderer, policy, template and font input."""

    hasher = hashlib.sha256()
    metadata = canonical_json_bytes(
        {
            "contract_version": REPORT_RENDERER_CONTRACT_VERSION,
            "renderer": "weasyprint",
            "renderer_version": renderer_version,
        }
    )
    hasher.update(len(metadata).to_bytes(8, "big"))
    hasher.update(metadata)
    paths: list[Path] = []
    for relative_root in _REPORT_BUNDLE_DIRECTORY_INPUTS:
        root = project_root / relative_root
        if strict and not root.is_dir():
            raise FileNotFoundError(f"required report bundle directory is missing: {root}")
        if not root.is_dir():
            continue
        paths.extend(
            item for item in root.rglob("*") if item.is_file() and _is_report_bundle_source(item)
        )
    for relative_file in _REPORT_BUNDLE_FILE_INPUTS:
        path = project_root / relative_file
        if strict and not path.is_file():
            raise FileNotFoundError(f"required report bundle file is missing: {path}")
        if path.is_file():
            paths.append(path)
    for path in sorted(set(paths)):
        relative = path.relative_to(project_root).as_posix().encode("utf-8")
        hasher.update(len(relative).to_bytes(4, "big"))
        hasher.update(relative)
        content = path.read_bytes()
        hasher.update(len(content).to_bytes(8, "big"))
        hasher.update(content)
    return hasher.hexdigest()


def _is_report_bundle_source(path: Path) -> bool:
    """Exclude interpreter and workstation artifacts from the stable bundle."""

    return (
        "__pycache__" not in path.parts
        and path.suffix not in {".pyc", ".pyo"}
        and path.name not in {".DS_Store"}
    )


def enforce_final_publication(
    manifest: ReportManifest,
    *,
    run: ValuationRunV2,
    assurance_authority: CurrentValuationAssuranceAuthority | None = None,
    require_artifacts: bool = False,
) -> None:
    """Recompute authorization from the run and authenticated Titan authority."""
    decision = scoped_report_release_decision(
        run,
        report_scope=manifest.report_scope,
        assurance_authority=assurance_authority,
    )
    assurance_envelope = assurance_authority.envelope if assurance_authority is not None else None
    declared_level = (
        assurance_envelope.evidence_confidence.band.upper()
        if assurance_envelope is not None
        else run.assurance.evidence_confidence.level
    )
    confidence_score = (
        int(Decimal(assurance_envelope.evidence_confidence.score))
        if assurance_envelope is not None
        else run.assurance.evidence_confidence.score
    )
    expected_level = effective_confidence_band(
        declared_level=declared_level,
        score=confidence_score,
    )
    manifest_binds_run = (
        manifest.valuation_run_id == run.run_id
        and manifest.valuation_run_hash == run.run_hash
        and manifest.confidence_level == expected_level
        and manifest.confidence_score == confidence_score
        and manifest.assurance == run.assurance
        and manifest.valuation_assurance_envelope == assurance_envelope
    )
    status_is_authorized = (
        decision.publication_status == "publishable"
        and manifest.publication_status == "publishable"
        and manifest.generation_status == decision.generation_status
        and manifest.reviewer_requirement == decision.reviewer_requirement
    )
    artifacts_are_complete = True
    if require_artifacts:
        counts = {
            artifact: sum(1 for row in manifest.artifact_digests if row.artifact == artifact)
            for artifact in ("html", "pdf", "report_payload")
        }
        if manifest.report_scope == "automated_indicative":
            counts = {key: value for key, value in counts.items() if value > 0}
        artifacts_are_complete = (
            bool(counts)
            and manifest.artifact_status == "complete"
            and not manifest.generation_warnings
            and all(count == 1 for count in counts.values())
            and all(row.bytes > 0 for row in manifest.artifact_digests)
        )
    if manifest.final_requested and not (
        manifest_binds_run and status_is_authorized and artifacts_are_complete
    ):
        raise ReportPublicationBlocked(manifest)


def _artifact_digest(artifact: str, content: bytes) -> ReportArtifactDigest:
    return ReportArtifactDigest(
        artifact=artifact,
        sha256=hashlib.sha256(content).hexdigest(),
        bytes=len(content),
    )


def _manifest_mapping(value: object) -> dict[str, object]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return dict(value)
    raise TypeError("report manifest must be a mapping or Pydantic model")


def _confidence_score(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _governed_advisor_review_state(run: ValuationRunV2) -> str:
    """Return the strictest sealed decision over this exact calculation."""
    decisions = list(run.report_review_decisions)
    if any(decision.decision == "rejected" for decision in decisions):
        return "rejected"
    if any(decision.decision == "accepted" for decision in decisions):
        return "accepted"
    return "missing"


def _final_artifact_block_points(
    *,
    request: GenerateReportRequest,
    artifact_digests: list[ReportArtifactDigest],
    generation_warnings: list[str],
) -> list[str]:
    by_artifact: dict[str, list[ReportArtifactDigest]] = {}
    for digest in artifact_digests:
        by_artifact.setdefault(digest.artifact, []).append(digest)

    # A final/share-ready report is a canonical three-artifact bundle. Caller
    # omission is itself a publication block; draft generation remains selective.
    required = (
        {
            "html": request.include_html,
            "pdf": request.include_pdf,
            "report_payload": request.include_report_data,
        }
        if request.report_scope == "automated_indicative"
        else {"html": True, "pdf": True, "report_payload": True}
    )
    points: list[str] = []
    for artifact, requested in required.items():
        if not requested:
            continue
        rows = by_artifact.get(artifact, [])
        if len(rows) != 1 or rows[0].bytes <= 0:
            points.append(
                f"Requested final {artifact} artifact is missing or lacks one non-empty digest."
            )
    if generation_warnings:
        points.append("Final generation produced a blocking artifact warning.")
    return points


def effective_confidence_band(*, declared_level: str, score: int) -> str:
    """Take the more conservative of the label and numeric T4-506 band."""
    score_band = "HIGH" if score >= 80 else "MEDIUM" if score >= 55 else "LOW"
    ranks = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    declared = declared_level if declared_level in ranks else "LOW"
    return declared if ranks[declared] <= ranks[score_band] else score_band


def _sealed_publication_block_points(
    run: ValuationRunV2,
    *,
    require_final_maturity: bool = True,
    evidence_tier_override: str | None = None,
) -> list[str]:
    points: list[str] = []
    evidence_tier = evidence_tier_override or run.assurance.evidence_maturity.tier
    if require_final_maturity and evidence_tier not in {"T3", "T4", "T5"}:
        points.append(f"Evidence maturity {evidence_tier} is not final-publication ready.")

    for qualification in run.qualifications:
        if not isinstance(qualification, Mapping):
            continue
        severity = str(qualification.get("severity") or "").strip().lower()
        issue = str(qualification.get("issue") or "").strip().lower()
        if severity in {"critical", "error"} or "publication_block" in issue:
            points.append(f"Sealed qualification requires review: {issue or severity}.")

    for raw in run.method_results.values():
        if not isinstance(raw, Mapping):
            continue
        details = raw.get("details")
        if isinstance(details, Mapping) and details.get("publication_blocked") is True:
            points.append("A sealed priced method is blocked from publication.")
            break
    return list(dict.fromkeys(points))


def _uses_untrusted_fallback(run: ValuationRunV2) -> bool:
    multiples = run.multiples_results
    if isinstance(multiples, Mapping) and (
        multiples.get("multiples_source") == "DISCLOSED_EXTERNAL_MARKET_FALLBACK"
    ):
        return True
    for raw in run.method_results.values():
        if not isinstance(raw, Mapping):
            continue
        details = raw.get("details")
        if isinstance(details, Mapping) and (
            details.get("multiples_source") == "DISCLOSED_EXTERNAL_MARKET_FALLBACK"
            or details.get("fallback_reason") == "explicit_untrusted_multiples_fallback"
        ):
            return True
    return False


def _uses_governed_external_market_reference(run: ValuationRunV2) -> bool:
    """Recognize a sealed, non-Index external contract pinned inside the run.

    The contract is intentionally not projected into ``benchmark_snapshot_references``:
    that field represents resolved benchmark datasets, while this route carries
    disclosed non-statistical market evidence. Fail closed unless the immutable run
    contains a reviewed contract and at least one hashed source.
    """

    multiples = run.multiples_results
    if not isinstance(multiples, Mapping):
        return False
    contract = multiples.get("external_market_reference_contract")
    if not isinstance(contract, Mapping):
        return False
    if str(contract.get("status") or "").strip().lower() != "reviewed_sealed":
        return False
    required_text = ("contract_id", "methodology_version", "reviewer", "metric")
    if any(not str(contract.get(key) or "").strip() for key in required_text):
        return False
    sources = contract.get("sources")
    if not isinstance(sources, list) or not sources:
        return False
    for source in sources:
        if not isinstance(source, Mapping):
            return False
        source_hash = (
            str(source.get("content_sha256") or source.get("source_hash") or "").strip().lower()
        )
        if len(source_hash) != 64 or any(char not in "0123456789abcdef" for char in source_hash):
            return False
        if not str(source.get("source_url") or source.get("url") or "").strip():
            return False
    return True


def _uses_priced_market_method(run: ValuationRunV2) -> bool:
    for row in run.method_mix:
        if not isinstance(row, Mapping):
            continue
        key = str(row.get("method_key") or "").lower()
        try:
            weight = float(row.get("weight") or 0)
        except (TypeError, ValueError):
            weight = 0
        if weight > 0 and key in {
            "market_approach",
            "upswitch_adaptive",
            "ebitda_multiple",
            "omzet_multiple",
            "revenue_multiple",
            "sde_multiple",
            "arr_multiple",
        }:
            return True
    return False


def _uses_priced_dcf_method(run: ValuationRunV2) -> bool:
    for row in run.method_mix:
        if not isinstance(row, Mapping):
            continue
        try:
            weight = float(row.get("weight") or 0)
        except (TypeError, ValueError):
            weight = 0
        if weight > 0 and str(row.get("method_key") or "").strip().lower() == "dcf":
            return True
    return False


def _uses_direct_sector_wacc(run: ValuationRunV2) -> bool:
    dcf = run.dcf_results
    if not isinstance(dcf, Mapping):
        return False
    contract = dcf.get("wacc_evidence_contract")
    if not isinstance(contract, Mapping):
        buildup = dcf.get("wacc_buildup")
        contract = buildup.get("wacc_evidence_contract") if isinstance(buildup, Mapping) else None
    if not isinstance(contract, Mapping):
        return False
    return (
        contract.get("schema_version") == "wacc_evidence.v1"
        and contract.get("mode") == "direct_sector_wacc"
        and contract.get("includes_size_premium") is True
        and isinstance(contract.get("content_sha256"), str)
        and len(str(contract.get("content_sha256"))) == 64
    )
