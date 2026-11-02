"""Buyer-ready package state for transaction-readiness report context."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from src.services.reports.report_readiness_context import (
    REQUIRED_BUYER_READY_PACKAGE_ARTIFACT_TYPES,
)
from src.services.reports.report_readiness_context import (
    buyer_package_readiness_score as compute_buyer_package_readiness_score,
)
from src.services.reports.report_readiness_context import (
    strictest_buyer_release_status,
    summarize_buyer_package_manifest,
)
from src.services.reports.transaction_readiness_package import (
    artifact_status_from_release_status as _artifact_status_from_release_status,
)
from src.services.reports.transaction_readiness_package import (
    formal_generated_package_manifest as _formal_generated_package_manifest,
)
from src.services.reports.transaction_readiness_package import (
    generated_package_artifact as _generated_package_artifact,
)

JsonMap = dict[str, object]


@dataclass(frozen=True)
class BuyerPackageState:
    package_manifest: JsonMap
    formal_package_manifest: JsonMap
    manifest_summary: JsonMap
    package_status: str
    missing_artifact_count: int
    review_artifact_count: int
    blocked_artifact_count: int
    duplicate_artifact_types: list[str]
    invalid_artifact_statuses: list[JsonMap]
    invalid_package_status: str
    artifact_count_mismatch: JsonMap
    invalid_valuation_pdf_status: str
    valuation_pdf_status_mismatch: JsonMap
    missing_artifact_labels: list[str]
    manifest_release_status: str
    effective_manifest_release_status: str
    invalid_manifest_release_status: str
    manifest_release_status_mismatch: JsonMap
    has_buyer_package_manifest: bool
    full_package_requested: bool
    package_gate_active: bool
    package_integrity_issue_count: int
    buyer_package_score: int
    effective_buyer_release_status: str
    display_readiness_score: int


def _as_dict(value: object) -> JsonMap:
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _as_dict(model_dump())
    return {}


def _as_list(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _clean_text(value: object) -> str:
    return str(value).strip() if value is not None and str(value).strip() else ""


def _text_items(value: object) -> list[str]:
    return [_clean_text(item) for item in _as_list(value) if _clean_text(item)]


def _existing_buyer_package_manifest(context: JsonMap) -> JsonMap:
    return (
        _as_dict(context.get("buyer_ready_package_manifest"))
        or _as_dict(context.get("buyer_package_manifest"))
        or _as_dict(context.get("package_manifest"))
    )


def _full_buyer_package_requested(context: JsonMap, metadata: Mapping[str, object] | None) -> bool:
    keys = (
        "full_buyer_package_requested",
        "buyer_ready_package_requested",
        "generate_buyer_ready_package",
        "include_buyer_ready_package",
    )
    sources = [context]
    if metadata is not None:
        sources.append({str(key): value for key, value in metadata.items()})
    for source in sources:
        if any(_truthy(source.get(key)) for key in keys):
            return True
    return bool(_existing_buyer_package_manifest(context))


def _default_artifact_status(artifact_type: str, legal_artifact_status: str) -> str:
    if artifact_type in {"valuation_main_report", "price_recommendation"}:
        return "needs_review"
    if artifact_type == "legal_readiness":
        return legal_artifact_status
    return "missing"


def _default_artifact_reason(artifact_type: str) -> str:
    if artifact_type in {"valuation_main_report", "price_recommendation"}:
        return (
            "Valuation memo exists, but the controlled buyer-package artifact has not been issued."
        )
    if artifact_type == "legal_readiness":
        return "Legal readiness requires legal/advisor review before external distribution."
    return "Artifact is required for a complete buyer-ready package and has not been assembled yet."


def _owner_transferability_challenge(context: JsonMap) -> JsonMap:
    for challenge in _as_list(context.get("transaction_buyer_challenges")):
        challenge_map = _as_dict(challenge)
        if challenge_map.get("code") == "owner_transferability_discount":
            return challenge_map
    return {}


def _owner_lineage_assistant_action(artifact_type: str, challenge: JsonMap) -> str:
    discount_key = _clean_text(challenge.get("multiple_discount_key")) or "owner dependency"
    data_points = _text_items(challenge.get("strength_factor_data_point_ids"))
    data_point_text = ", ".join(data_points[:4])
    if artifact_type == "data_room_manifest":
        action = f"Add owner-transferability proof for {discount_key} to the data-room manifest"
    else:
        action = f"Collect owner-transferability diligence evidence to retest {discount_key}"
    if data_point_text:
        return f"{action}: {data_point_text}."
    return f"{action}."


def _apply_owner_lineage_artifact_requirements(
    artifact: JsonMap,
    owner_challenge: JsonMap,
) -> JsonMap:
    artifact_type = str(artifact.get("artifact_type") or "")
    if artifact_type not in {"dd_checklist", "data_room_manifest"} or not owner_challenge:
        return artifact

    data_points = _text_items(owner_challenge.get("strength_factor_data_point_ids"))
    discount_key = _clean_text(owner_challenge.get("multiple_discount_key"))
    artifact["reason"] = (
        "Owner-transferability evidence is required to rebut "
        f"{discount_key or 'owner dependency'} before buyer diligence."
    )
    artifact["open_input_count"] = max(1, min(len(data_points), 4))
    artifact["assistant_next_action"] = _owner_lineage_assistant_action(
        artifact_type,
        owner_challenge,
    )
    return artifact


def _build_default_package_artifacts(
    *,
    context: JsonMap,
    locale: str,
    legal_release_status: str,
) -> list[JsonMap]:
    legal_artifact_status = _artifact_status_from_release_status(legal_release_status)
    owner_challenge = _owner_transferability_challenge(context)
    artifacts: list[JsonMap] = []
    for artifact_type in REQUIRED_BUYER_READY_PACKAGE_ARTIFACT_TYPES:
        artifact = _generated_package_artifact(
            artifact_type,
            locale=locale,
            status=_default_artifact_status(artifact_type, legal_artifact_status),
            reason=_default_artifact_reason(artifact_type),
        )
        artifacts.append(_apply_owner_lineage_artifact_requirements(artifact, owner_challenge))
    return artifacts


def _default_package_status(
    *,
    legal_release_status: str,
    missing_artifact_count: int,
    review_artifact_count: int,
) -> str:
    if legal_release_status == "blocked" or missing_artifact_count:
        return "blocked"
    if legal_release_status != "nda_required" or review_artifact_count:
        return "needs_review"
    return "ready"


def _build_default_package_manifest(
    context: JsonMap,
    *,
    locale: str,
    legal_release_status: str,
) -> JsonMap:
    package_artifacts = _build_default_package_artifacts(
        context=context,
        locale=locale,
        legal_release_status=legal_release_status,
    )
    missing_artifact_count = sum(
        1 for artifact in package_artifacts if artifact.get("status") == "missing"
    )
    review_artifact_count = sum(
        1 for artifact in package_artifacts if artifact.get("status") == "needs_review"
    )
    blocked_artifact_count = sum(
        1 for artifact in package_artifacts if artifact.get("status") == "blocked"
    )
    package_status = _default_package_status(
        legal_release_status=legal_release_status,
        missing_artifact_count=missing_artifact_count,
        review_artifact_count=review_artifact_count,
    )
    return {
        "package_status": package_status,
        "release_status": legal_release_status,
        "valuation_report_id": context.get("report_id"),
        "valuation_pdf_status": "missing",
        "artifacts": package_artifacts,
        "included_artifact_count": len(package_artifacts),
        "missing_artifact_count": missing_artifact_count,
        "review_artifact_count": review_artifact_count,
        "blocked_artifact_count": blocked_artifact_count,
        "duplicate_artifact_types": [],
    }


def build_buyer_package_state(
    context: JsonMap,
    *,
    locale: str,
    metadata: Mapping[str, object] | None,
    legal_release_status: str,
    memo_readiness_score: int,
) -> BuyerPackageState:
    package_manifest = _build_default_package_manifest(
        context,
        locale=locale,
        legal_release_status=legal_release_status,
    )
    existing_manifest = _existing_buyer_package_manifest(context)
    full_package_requested = _full_buyer_package_requested(context, metadata)
    formal_package_manifest = existing_manifest or package_manifest
    manifest_summary = summarize_buyer_package_manifest(formal_package_manifest, locale=locale)
    package_status = str(manifest_summary["package_status"])
    missing_artifact_count = int(manifest_summary["missing_artifact_count"])
    review_artifact_count = int(manifest_summary["review_artifact_count"])
    blocked_artifact_count = int(manifest_summary["blocked_artifact_count"])
    duplicate_artifact_types = [
        str(artifact_type)
        for artifact_type in _as_list(manifest_summary["duplicate_artifact_types"])
    ]
    invalid_artifact_statuses = [
        _as_dict(status)
        for status in _as_list(manifest_summary["invalid_artifact_statuses"])
        if _as_dict(status)
    ]
    package_integrity_issue_count = int(manifest_summary["package_integrity_issue_count"])
    has_buyer_package_manifest = bool(existing_manifest)
    package_gate_active = full_package_requested or has_buyer_package_manifest
    effective_manifest_release_status = str(manifest_summary.get("effective_release_status") or "")
    buyer_package_score = compute_buyer_package_readiness_score(
        missing_artifact_count=missing_artifact_count,
        review_artifact_count=review_artifact_count,
        blocked_artifact_count=blocked_artifact_count,
        integrity_issue_count=package_integrity_issue_count,
        package_status=package_status,
    )
    effective_buyer_release_status = strictest_buyer_release_status(
        legal_release_status,
        effective_manifest_release_status if package_gate_active else "",
    )
    display_readiness_score = (
        min(memo_readiness_score, buyer_package_score)
        if package_gate_active
        else memo_readiness_score
    )
    return BuyerPackageState(
        package_manifest=package_manifest,
        formal_package_manifest=formal_package_manifest,
        manifest_summary=manifest_summary,
        package_status=package_status,
        missing_artifact_count=missing_artifact_count,
        review_artifact_count=review_artifact_count,
        blocked_artifact_count=blocked_artifact_count,
        duplicate_artifact_types=duplicate_artifact_types,
        invalid_artifact_statuses=invalid_artifact_statuses,
        invalid_package_status=str(manifest_summary["invalid_package_status"] or ""),
        artifact_count_mismatch=_as_dict(manifest_summary["artifact_count_mismatch"]),
        invalid_valuation_pdf_status=str(manifest_summary["invalid_valuation_pdf_status"] or ""),
        valuation_pdf_status_mismatch=_as_dict(manifest_summary["valuation_pdf_status_mismatch"]),
        missing_artifact_labels=[
            str(label) for label in _as_list(manifest_summary["missing_artifact_labels"])
        ],
        manifest_release_status=str(manifest_summary.get("release_status") or ""),
        effective_manifest_release_status=effective_manifest_release_status,
        invalid_manifest_release_status=str(manifest_summary.get("invalid_release_status") or ""),
        manifest_release_status_mismatch=_as_dict(manifest_summary.get("release_status_mismatch")),
        has_buyer_package_manifest=has_buyer_package_manifest,
        full_package_requested=full_package_requested,
        package_gate_active=package_gate_active,
        package_integrity_issue_count=package_integrity_issue_count,
        buyer_package_score=buyer_package_score,
        effective_buyer_release_status=effective_buyer_release_status,
        display_readiness_score=display_readiness_score,
    )


def attach_buyer_package_manifest(result: JsonMap, package_state: BuyerPackageState) -> None:
    if package_state.has_buyer_package_manifest:
        result["buyer_ready_package_manifest"] = package_state.formal_package_manifest
    elif package_state.full_package_requested:
        result["buyer_ready_package_manifest"] = _formal_generated_package_manifest(
            package_state.package_manifest
        )
