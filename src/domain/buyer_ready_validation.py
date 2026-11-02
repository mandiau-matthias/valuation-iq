"""Validation policy helpers for buyer-ready render contracts."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Optional

from .buyer_ready_types import (
    BUYER_READY_REQUIRED_PACKAGE_ARTIFACT_TYPES,
    BuyerReadyBridgeBeliefStatus,
    BuyerReadyBridgeEvidenceStatus,
    BuyerReadyConfidence,
)


def confidence_floor(values: Sequence[BuyerReadyConfidence]) -> BuyerReadyConfidence:
    if "low" in values:
        return "low"
    if "medium" in values:
        return "medium"
    return "high"


def classify_bridge_step_evidence(
    *,
    delta_eur: int,
    step_confidence: BuyerReadyConfidence,
    evidence_refs: Sequence[object],
) -> BuyerReadyBridgeEvidenceStatus:
    if not evidence_refs:
        return "unsupported"

    lowest_source_confidence = min(float(getattr(ref, "confidence", 0)) for ref in evidence_refs)
    categories = {str(getattr(ref, "source_category", "")).strip().lower() for ref in evidence_refs}
    has_document_ref = any(getattr(ref, "document_id", None) for ref in evidence_refs)
    has_system_ref = any(getattr(ref, "source_ref", None) for ref in evidence_refs)
    advisor_only = categories <= {
        "advisor_input",
        "owner_profile",
        "other",
        "other_readiness_evidence",
    }

    if step_confidence == "low" or lowest_source_confidence < 0.6:
        return "weak_evidence"
    if delta_eur > 0 and (not has_document_ref or advisor_only):
        return "weak_evidence"
    if delta_eur <= 0 and not (has_document_ref or has_system_ref):
        return "weak_evidence"
    return "documented"


def bridge_step_warning(
    status: BuyerReadyBridgeEvidenceStatus,
    *,
    delta_eur: int,
) -> Optional[str]:
    if status == "documented":
        return None
    if status == "unsupported":
        if delta_eur > 0:
            return "Add-back is not supported by buyer-verifiable evidence."
        return "Bridge step lacks a buyer-verifiable evidence trail."
    if delta_eur > 0:
        return "Add-back needs stronger third-party or document evidence before buyer release."
    return "Bridge step should be reviewed before buyer release."


def bridge_confidence_reason(
    status: BuyerReadyBridgeEvidenceStatus,
    evidence_refs: Sequence[object],
) -> str:
    if status == "unsupported":
        return "No citation-ready evidence was supplied for this bridge step."

    evidence_count = len(evidence_refs)
    minimum = min(float(getattr(ref, "confidence", 0)) for ref in evidence_refs)
    if status == "weak_evidence":
        return (
            f"{evidence_count} source"
            f"{'s' if evidence_count != 1 else ''} supplied, but the weakest "
            f"source confidence is {minimum:.0%}."
        )
    return (
        f"{evidence_count} buyer-verifiable source"
        f"{'s' if evidence_count != 1 else ''} supplied; weakest source confidence "
        f"is {minimum:.0%}."
    )


def bridge_buyer_belief_status(
    *,
    unsupported_step_count: int,
    weak_evidence_step_count: int,
    derived_confidence: BuyerReadyConfidence,
) -> BuyerReadyBridgeBeliefStatus:
    if unsupported_step_count:
        return "not_buyer_ready"
    if weak_evidence_step_count or derived_confidence == "low":
        return "advisor_review"
    return "buyer_believable"


def validate_legal_readiness_counts(model: object) -> None:
    items = list(getattr(model, "items", []))
    expected = {
        "clear": sum(1 for item in items if getattr(item, "status", None) == "clear"),
        "review": sum(1 for item in items if getattr(item, "status", None) == "review"),
        "blocked": sum(1 for item in items if getattr(item, "status", None) == "blocked"),
    }
    if getattr(model, "clear_count", None) != expected["clear"]:
        raise ValueError("legal_readiness.clear_count does not match clear items")
    if getattr(model, "review_count", None) != expected["review"]:
        raise ValueError("legal_readiness.review_count does not match review items")
    if getattr(model, "blocked_count", None) != expected["blocked"]:
        raise ValueError("legal_readiness.blocked_count does not match blocked items")
    if not getattr(model, "counsel_review_required", False):
        raise ValueError("legal_readiness.counsel_review_required must remain true")
    buyer_release_status = getattr(model, "buyer_release_status", None)
    if getattr(model, "blocked_count", 0) > 0 and buyer_release_status != "blocked":
        raise ValueError("legal_readiness blocked items require blocked buyer_release_status")
    if getattr(model, "review_count", 0) > 0 and buyer_release_status in {
        "teaser_ready",
        "nda_required",
    }:
        raise ValueError(
            "legal_readiness review items require lawyer_review_required buyer_release_status"
        )


def _source_ref_is_raw_url(source_ref: object) -> bool:
    return bool(source_ref) and str(source_ref).strip().lower().startswith(("http://", "https://"))


def _validate_valuation_artifact_controlled_source_ref(artifact: object) -> None:
    artifact_type = getattr(artifact, "artifact_type", None)
    source_ref = getattr(artifact, "source_ref", None)
    if artifact_type in {"valuation_main_report", "valuation_pdf"} and _source_ref_is_raw_url(
        source_ref
    ):
        raise ValueError("valuation report artifacts must use controlled source_ref IDs, not URLs")


def _validate_ready_im_cim_custom_content(artifact: object) -> None:
    if getattr(artifact, "artifact_type", None) != "im_cim":
        return
    if getattr(artifact, "status", None) != "ready":
        return

    custom_content_provider = getattr(artifact, "custom_content_provider", None)
    custom_content_status = getattr(artifact, "custom_content_status", None)
    if (
        not custom_content_provider
        or not str(custom_content_provider).startswith("claude_")
        or custom_content_status != "claude_generated"
    ):
        raise ValueError(
            "im_cim ready status requires Claude-generated custom narrative provenance"
        )


def _validate_legal_readiness_artifact_gate(artifact: object) -> None:
    if getattr(artifact, "artifact_type", None) != "legal_readiness":
        return
    if getattr(artifact, "status", None) == "missing":
        return

    if (
        getattr(artifact, "owner", None) != "lawyer"
        or getattr(artifact, "access_gate", None) != "lawyer_only"
        or getattr(artifact, "custom_content_provider", None) != "counsel_owned"
        or getattr(artifact, "custom_content_status", None) != "counsel_review_required"
    ):
        raise ValueError("legal_readiness artifact must remain counsel-owned and lawyer-gated")


def _validate_assistant_integrated_artifact(artifact: object, artifact_type: object) -> None:
    if artifact_type not in {"dd_checklist", "data_room_manifest"}:
        return

    assistant_surfaces = set(getattr(artifact, "assistant_surfaces", []) or [])
    if not {"venus", "mercury"}.issubset(assistant_surfaces):
        raise ValueError(f"{artifact_type} artifact requires Venus/Mercury assistant surfaces")
    if getattr(artifact, "integration_input_status", None) is None:
        raise ValueError(f"{artifact_type} artifact requires integration_input_status")
    if getattr(artifact, "open_input_count", None) is None:
        raise ValueError(f"{artifact_type} artifact requires open_input_count")
    if not getattr(artifact, "assistant_next_action", None):
        raise ValueError(f"{artifact_type} artifact requires assistant_next_action")


def validate_package_artifact_controlled_source_refs(artifact: object) -> None:
    artifact_type = getattr(artifact, "artifact_type", None)
    _validate_valuation_artifact_controlled_source_ref(artifact)
    _validate_ready_im_cim_custom_content(artifact)
    _validate_legal_readiness_artifact_gate(artifact)
    _validate_assistant_integrated_artifact(artifact, artifact_type)


def validate_package_manifest_count_and_pdf_status(manifest: object) -> None:
    artifacts = list(getattr(manifest, "artifacts", []))
    if getattr(manifest, "included_artifact_count", None) != len(artifacts):
        raise ValueError("buyer_package_manifest.included_artifact_count must match artifacts")

    artifact_types = [getattr(artifact, "artifact_type", None) for artifact in artifacts]
    missing_types = [
        artifact_type
        for artifact_type in BUYER_READY_REQUIRED_PACKAGE_ARTIFACT_TYPES
        if artifact_type not in artifact_types
    ]
    if missing_types:
        raise ValueError(
            "buyer_package_manifest.artifacts missing required artifacts: "
            + ", ".join(missing_types)
        )

    duplicate_types = sorted(
        {
            artifact_type
            for artifact_type in artifact_types
            if artifact_type and artifact_types.count(artifact_type) > 1
        }
    )
    if duplicate_types:
        raise ValueError(
            "buyer_package_manifest.artifacts contains duplicate artifacts: "
            + ", ".join(duplicate_types)
        )

    pdf_artifacts = [
        artifact
        for artifact in artifacts
        if getattr(artifact, "artifact_type", None) == "valuation_pdf"
    ]
    if pdf_artifacts and getattr(manifest, "valuation_pdf_status", None) != getattr(
        pdf_artifacts[0],
        "status",
        None,
    ):
        raise ValueError("buyer_package_manifest.valuation_pdf_status must match PDF artifact")


def validate_package_manifest_payload_consistency(package: object) -> None:
    """D0 cannot mark an artifact ready when its body is absent."""
    buyer_package_manifest = getattr(package, "buyer_package_manifest", None)
    if not buyer_package_manifest:
        return

    artifacts = {
        getattr(artifact, "artifact_type", None): artifact
        for artifact in getattr(buyer_package_manifest, "artifacts", [])
    }

    _validate_valuation_report_artifacts(package, buyer_package_manifest, artifacts)
    _validate_im_cim_artifact(package, artifacts)
    _validate_price_recommendation_artifact(package, buyer_package_manifest, artifacts)
    _validate_wc_tax_artifact(package, artifacts)
    _validate_data_room_manifest_artifact(package, artifacts)
    _validate_legal_readiness_artifact(package, artifacts)


def _artifact_is_ready(artifact: object) -> bool:
    return bool(artifact) and getattr(artifact, "status", None) == "ready"


def _validate_ready_artifact_issued_at(artifact: object, artifact_type: str) -> None:
    if not getattr(artifact, "issued_at", None):
        raise ValueError(f"{artifact_type} ready status requires issued_at")


def _validate_source_ref_matches_valuation_report_id(
    artifact: object,
    buyer_package_manifest: object,
    artifact_type: str,
) -> None:
    valuation_report_id = getattr(buyer_package_manifest, "valuation_report_id", None)
    source_ref = getattr(artifact, "source_ref", None)
    if valuation_report_id and source_ref and source_ref != valuation_report_id:
        raise ValueError(f"{artifact_type} source_ref must match valuation_report_id")


def _validate_ready_valuation_main_report(
    buyer_package_manifest: object,
    valuation_report: object,
) -> None:
    if not _artifact_is_ready(valuation_report):
        return

    if not (
        getattr(valuation_report, "source_ref", None)
        or getattr(buyer_package_manifest, "valuation_report_id", None)
    ):
        raise ValueError(
            "valuation_main_report ready status requires controlled valuation_report_id/source_ref"
        )
    _validate_ready_artifact_issued_at(valuation_report, "valuation_main_report")
    _validate_source_ref_matches_valuation_report_id(
        valuation_report,
        buyer_package_manifest,
        "valuation_main_report",
    )


def _validate_ready_valuation_pdf(
    buyer_package_manifest: object,
    valuation_pdf: object,
) -> None:
    if not _artifact_is_ready(valuation_pdf):
        return

    if not getattr(valuation_pdf, "source_ref", None):
        raise ValueError("valuation_pdf ready status requires controlled source_ref")
    _validate_ready_artifact_issued_at(valuation_pdf, "valuation_pdf")
    _validate_source_ref_matches_valuation_report_id(
        valuation_pdf,
        buyer_package_manifest,
        "valuation_pdf",
    )


def _validate_valuation_report_artifacts(
    package: object,
    buyer_package_manifest: object,
    artifacts: dict[object, object],
) -> None:
    del package
    _validate_ready_valuation_main_report(
        buyer_package_manifest,
        artifacts.get("valuation_main_report"),
    )
    _validate_ready_valuation_pdf(
        buyer_package_manifest,
        artifacts.get("valuation_pdf"),
    )


def _validate_im_cim_artifact(package: object, artifacts: dict[object, object]) -> None:
    im_cim = artifacts.get("im_cim")
    engine_signals = getattr(package, "engine_signals", None)
    if im_cim and getattr(im_cim, "status", None) == "ready":
        llm_provider = getattr(engine_signals, "llm_provider", None)
        if not llm_provider:
            raise ValueError("im_cim ready status requires engine_signals.llm_provider")
        if getattr(im_cim, "custom_content_provider", None) != llm_provider:
            raise ValueError(
                "im_cim custom_content_provider must match engine_signals.llm_provider"
            )
        if (
            getattr(engine_signals, "llm_sections_with_narrative", None) != 3
            or getattr(engine_signals, "llm_sections_placeholder", None) != 0
        ):
            raise ValueError(
                "im_cim ready status requires complete Claude narrative engine signals"
            )


def _validate_price_recommendation_artifact(
    package: object,
    buyer_package_manifest: object,
    artifacts: dict[object, object],
) -> None:
    price_recommendation = artifacts.get("price_recommendation")
    pricing = getattr(package, "pricing", None)
    if (
        price_recommendation
        and getattr(price_recommendation, "status", None) == "ready"
        and not pricing
    ):
        raise ValueError("price_recommendation ready status requires pricing payload")
    if (
        price_recommendation
        and getattr(price_recommendation, "status", None) == "ready"
        and pricing
    ):
        valuation_report_id = getattr(buyer_package_manifest, "valuation_report_id", None)
        has_matching_valuation_provenance = any(
            getattr(ref, "source", None) == "valuation_report"
            and (
                not valuation_report_id
                or not getattr(ref, "source_id", None)
                or getattr(ref, "source_id", None) == valuation_report_id
            )
            for ref in getattr(pricing, "provenance", [])
        )
        if not has_matching_valuation_provenance:
            raise ValueError(
                "price_recommendation ready status requires valuation_report provenance"
            )


def _validate_wc_tax_artifact(package: object, artifacts: dict[object, object]) -> None:
    wc_tax = artifacts.get("wc_tax")
    if (
        wc_tax
        and getattr(wc_tax, "status", None) == "ready"
        and not getattr(package, "wc_peg", None)
    ):
        raise ValueError("wc_tax ready status requires working-capital peg payload")


def _validate_data_room_manifest_artifact(package: object, artifacts: dict[object, object]) -> None:
    data_room_manifest_artifact = artifacts.get("data_room_manifest")
    data_room_manifest_payload = getattr(package, "data_room_manifest", None)
    if (
        data_room_manifest_artifact
        and getattr(data_room_manifest_artifact, "status", None) == "ready"
        and (
            not data_room_manifest_payload
            or getattr(data_room_manifest_payload, "doc_count", 0) == 0
        )
    ):
        raise ValueError("data_room_manifest ready status requires indexed data-room payload")


def _validate_legal_readiness_artifact(package: object, artifacts: dict[object, object]) -> None:
    legal_readiness_artifact = artifacts.get("legal_readiness")
    legal_readiness_payload = getattr(package, "legal_readiness", None)
    if (
        legal_readiness_artifact
        and getattr(legal_readiness_artifact, "status", None) != "missing"
        and not legal_readiness_payload
    ):
        raise ValueError("legal_readiness non-missing status requires legal readiness payload")
    if legal_readiness_artifact and legal_readiness_payload:
        if getattr(legal_readiness_payload, "buyer_release_status", None) == "blocked":
            expected_legal_artifact_status = "blocked"
        elif (
            getattr(legal_readiness_payload, "buyer_release_status", None)
            == "lawyer_review_required"
        ):
            expected_legal_artifact_status = "needs_review"
        else:
            expected_legal_artifact_status = "ready"
        if getattr(legal_readiness_artifact, "status", None) != expected_legal_artifact_status:
            raise ValueError("legal_readiness artifact status must match buyer_release_status")
