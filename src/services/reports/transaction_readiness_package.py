"""Buyer-package helpers for transaction-readiness report context."""

from __future__ import annotations

from collections.abc import Mapping

from src.services.reports.report_readiness_common import JsonMap, as_list
from src.services.reports.transaction_readiness_labels import (
    BUYER_PACKAGE_ARTIFACT_ACCESS_GATE_BY_TYPE,
    BUYER_PACKAGE_ARTIFACT_OWNER_BY_TYPE,
    buyer_package_artifact_label,
)


def legal_release_status(report_handoff_status: str) -> str:
    if report_handoff_status == "blocked":
        return "blocked"
    if report_handoff_status == "lawyer_review_required":
        return "lawyer_review_required"
    return "nda_required"


def artifact_status_from_release_status(release_status: str) -> str:
    if release_status == "blocked":
        return "blocked"
    return "needs_review"


def generated_package_artifact(
    artifact_type: str,
    *,
    locale: str,
    status: str = "missing",
    reason: str,
) -> JsonMap:
    artifact: JsonMap = {
        "artifact_type": artifact_type,
        "title": buyer_package_artifact_label(artifact_type, locale),
        "label": buyer_package_artifact_label(artifact_type, locale),
        "status": status,
        "access_gate": BUYER_PACKAGE_ARTIFACT_ACCESS_GATE_BY_TYPE.get(
            artifact_type,
            "internal",
        ),
        "owner": BUYER_PACKAGE_ARTIFACT_OWNER_BY_TYPE.get(artifact_type, "advisor"),
        "reason": reason,
    }
    if artifact_type in {"dd_checklist", "data_room_manifest"}:
        artifact.update(
            {
                "assistant_surfaces": ["venus", "mercury"],
                "integration_input_status": "missing",
                "open_input_count": 1,
                "assistant_next_action": (
                    "Collect the missing diligence evidence and refresh the buyer package."
                ),
            }
        )
    if artifact_type == "legal_readiness" and status != "missing":
        artifact.update(
            {
                "custom_content_provider": "counsel_owned",
                "custom_content_status": "counsel_review_required",
            }
        )
    return artifact


def formal_generated_package_manifest(manifest: JsonMap) -> JsonMap:
    formal_artifacts: list[JsonMap] = []
    for raw_artifact in as_list(manifest.get("artifacts")):
        if not isinstance(raw_artifact, Mapping):
            continue
        artifact = dict(raw_artifact)
        artifact.pop("label", None)
        formal_artifacts.append(artifact)

    return {
        "package_status": manifest.get("package_status"),
        "release_status": manifest.get("release_status"),
        "included_artifact_count": len(formal_artifacts),
        "valuation_report_id": manifest.get("valuation_report_id"),
        "valuation_pdf_status": manifest.get("valuation_pdf_status", "missing"),
        "artifacts": formal_artifacts,
    }
