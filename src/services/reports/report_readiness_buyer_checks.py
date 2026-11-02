"""Buyer-ready package checks for internal report readiness."""

from __future__ import annotations

from dataclasses import dataclass

from src.services.reports.buyer_package_manifest import (
    VALID_BUYER_READY_PACKAGE_ARTIFACT_STATUSES,
    VALID_BUYER_READY_RELEASE_STATUSES,
)
from src.services.reports.report_readiness_common import JsonMap, as_dict, as_list, safe_int


@dataclass(frozen=True)
class BuyerReadyFindingResult:
    score_delta: int
    effective_legal_release_status: str
    effective_manifest_release_status: str


@dataclass(frozen=True)
class _LegalHandoffSignals:
    release_status: str
    invalid_release_status: str
    blocked_count: int
    review_count: int
    counsel_review_required: object
    effective_release_status: str


@dataclass(frozen=True)
class _PackageStatusSignals:
    package_status: str
    invalid_package_status: str
    blocked_artifact_count: int
    review_artifact_count: int
    missing_artifact_count: int
    duplicate_artifact_types: list[str]
    invalid_artifact_statuses: list[JsonMap]
    artifact_count_mismatch: JsonMap
    invalid_valuation_pdf_status: str
    valuation_pdf_status_mismatch: JsonMap
    invalid_manifest_release_status: str
    manifest_release_status_mismatch: JsonMap
    effective_manifest_release_status: str
    missing_required_artifact_types: list[str]


_PACKAGE_METADATA_ARTIFACT_FIELDS = (
    ("release_status", "release_status", False),
    ("valuation_pdf_status", "valuation_pdf_status", False),
    (
        "valuation_pdf_artifact_status",
        "valuation_pdf_artifact_status",
        False,
    ),
)

_PACKAGE_METADATA_STATE_FIELDS = (
    ("package_status", "package_status", False),
    ("invalid_package_status", "invalid_package_status", True),
    ("effective_release_status", "effective_manifest_release_status", True),
    ("invalid_release_status", "invalid_manifest_release_status", True),
    ("release_status_mismatch", "manifest_release_status_mismatch", True),
    ("blocked_artifact_count", "blocked_artifact_count", False),
    ("review_artifact_count", "review_artifact_count", False),
    ("missing_artifact_count", "missing_artifact_count", False),
    ("duplicate_artifact_types", "duplicate_artifact_types", False),
    ("invalid_artifact_statuses", "invalid_artifact_statuses", False),
    ("artifact_count_mismatch", "artifact_count_mismatch", True),
    ("invalid_valuation_pdf_status", "invalid_valuation_pdf_status", True),
    ("valuation_pdf_status_mismatch", "valuation_pdf_status_mismatch", True),
    ("package_integrity_issue_count", "package_integrity_issues", True),
)


def add_finding(
    findings: list[JsonMap],
    *,
    code: str,
    severity: str,
    title: str,
    detail: str,
    method_key: str | None = None,
    missing_required_context_keys: list[str] | None = None,
    metadata: JsonMap | None = None,
) -> None:
    finding: JsonMap = {
        "code": code,
        "severity": severity,
        "title": title,
        "detail": detail,
        "visibility": "agent",
    }
    if method_key:
        finding["method_key"] = method_key
    if missing_required_context_keys:
        finding["missing_required_context_keys"] = missing_required_context_keys
    if metadata:
        finding["metadata"] = metadata
    findings.append(finding)


def apply_buyer_ready_findings(
    findings: list[JsonMap],
    buyer_ready_artifacts: JsonMap,
) -> BuyerReadyFindingResult:
    score_delta = 0
    score_delta += _apply_pricing_findings(findings, buyer_ready_artifacts)
    legal_status, legal_delta = _apply_legal_handoff_findings(findings, buyer_ready_artifacts)
    manifest_status, manifest_delta = _apply_package_manifest_findings(
        findings,
        buyer_ready_artifacts,
    )
    score_delta += legal_delta + manifest_delta
    score_delta += _apply_im_content_findings(findings, buyer_ready_artifacts)
    score_delta += _apply_ebitda_bridge_findings(findings, buyer_ready_artifacts)
    return BuyerReadyFindingResult(
        score_delta=score_delta,
        effective_legal_release_status=legal_status,
        effective_manifest_release_status=manifest_status,
    )


def _apply_pricing_findings(
    findings: list[JsonMap],
    buyer_ready_artifacts: JsonMap,
) -> int:
    pricing_artifact = as_dict(buyer_ready_artifacts.get("pricing"))
    if not pricing_artifact:
        return 0

    missing_pricing_fields = [
        field
        for field in ("equity_value_low", "equity_value_mid", "equity_value_high")
        if pricing_artifact.get(field) is None
    ]
    if not missing_pricing_fields:
        return 0

    add_finding(
        findings,
        code="buyer_ready_pricing_range_incomplete",
        severity="high",
        title="Buyer package price range is incomplete",
        detail=(
            "The buyer-ready package must pin low, midpoint, and high values "
            "to the final valuation report before external distribution."
        ),
        missing_required_context_keys=missing_pricing_fields,
    )
    return -12


def _apply_legal_handoff_findings(
    findings: list[JsonMap],
    buyer_ready_artifacts: JsonMap,
) -> tuple[str, int]:
    legal_artifact = as_dict(buyer_ready_artifacts.get("legal_readiness"))
    if not legal_artifact:
        return "", 0

    signals = _legal_handoff_signals(legal_artifact)
    if signals.effective_release_status not in {"blocked", "lawyer_review_required"}:
        return signals.effective_release_status, 0

    severity = "critical" if signals.effective_release_status == "blocked" else "high"
    add_finding(
        findings,
        code="buyer_ready_legal_handoff_not_clear",
        severity=severity,
        title="Legal readiness handoff is not clear",
        detail=(
            "The legal-readiness review gate blocks external distribution."
            if signals.effective_release_status == "blocked"
            else "Legal advisor or transaction advisor review is required before external distribution."
        ),
        metadata=_legal_handoff_metadata(signals),
    )
    return signals.effective_release_status, -25 if severity == "critical" else -12


def _legal_handoff_signals(legal_artifact: JsonMap) -> _LegalHandoffSignals:
    release_status = str(legal_artifact.get("buyer_release_status") or "").strip()
    invalid_release_status = (
        release_status
        if release_status and release_status not in VALID_BUYER_READY_RELEASE_STATUSES
        else ""
    )
    blocked_count = safe_int(legal_artifact.get("blocked_count"))
    review_count = safe_int(legal_artifact.get("review_count"))
    counsel_review_required = legal_artifact.get("counsel_review_required")
    return _LegalHandoffSignals(
        release_status=release_status,
        invalid_release_status=invalid_release_status,
        blocked_count=blocked_count,
        review_count=review_count,
        counsel_review_required=counsel_review_required,
        effective_release_status=_effective_legal_release_status(
            release_status=release_status,
            invalid_release_status=invalid_release_status,
            blocked_count=blocked_count,
            review_count=review_count,
            counsel_review_required=counsel_review_required,
        ),
    )


def _effective_legal_release_status(
    *,
    release_status: str,
    invalid_release_status: str,
    blocked_count: int,
    review_count: int,
    counsel_review_required: object,
) -> str:
    if (
        not release_status
        or invalid_release_status
        or counsel_review_required is not True
        or release_status == "blocked"
        or blocked_count
    ):
        return "blocked"
    if release_status == "lawyer_review_required" or review_count:
        return "lawyer_review_required"
    return release_status


def _legal_handoff_metadata(signals: _LegalHandoffSignals) -> JsonMap:
    return {
        "buyer_release_status": signals.release_status,
        "effective_buyer_release_status": signals.effective_release_status,
        "invalid_buyer_release_status": signals.invalid_release_status or None,
        "counsel_review_required": signals.counsel_review_required,
        "blocked_count": signals.blocked_count,
        "review_count": signals.review_count,
    }


def _apply_package_manifest_findings(
    findings: list[JsonMap],
    buyer_ready_artifacts: JsonMap,
) -> tuple[str, int]:
    package_manifest_artifact = as_dict(buyer_ready_artifacts.get("buyer_package_manifest"))
    if not package_manifest_artifact:
        return "", 0

    package_state = _package_manifest_state(package_manifest_artifact)
    score_delta = 0
    if package_state["missing_required_artifact_types"]:
        _add_required_artifact_finding(findings, package_manifest_artifact, package_state)
        score_delta -= 20

    effective_package_status = str(package_state["effective_package_status"])
    if effective_package_status in {"blocked", "needs_review"}:
        _add_package_status_finding(
            findings,
            package_manifest_artifact,
            package_state,
            effective_package_status,
        )
        score_delta -= 20 if effective_package_status == "blocked" else 10

    return str(package_state["effective_manifest_release_status"]), score_delta


def _package_manifest_state(package_manifest_artifact: JsonMap) -> JsonMap:
    package_status = str(package_manifest_artifact.get("package_status") or "").strip()
    invalid_package_status = (
        package_status
        if package_status and package_status not in VALID_BUYER_READY_PACKAGE_ARTIFACT_STATUSES
        else ""
    )
    blocked_artifact_count = safe_int(package_manifest_artifact.get("blocked_artifact_count"))
    review_artifact_count = safe_int(package_manifest_artifact.get("review_artifact_count"))
    missing_artifact_count = safe_int(package_manifest_artifact.get("missing_artifact_count"))
    duplicate_artifact_types = [
        str(artifact_type)
        for artifact_type in as_list(package_manifest_artifact.get("duplicate_artifact_types"))
        if artifact_type
    ]
    invalid_artifact_statuses = [
        as_dict(status)
        for status in as_list(package_manifest_artifact.get("invalid_artifact_statuses"))
        if as_dict(status)
    ]
    artifact_count_mismatch = as_dict(package_manifest_artifact.get("artifact_count_mismatch"))
    invalid_valuation_pdf_status = str(
        package_manifest_artifact.get("invalid_valuation_pdf_status") or ""
    ).strip()
    valuation_pdf_status_mismatch = as_dict(
        package_manifest_artifact.get("valuation_pdf_status_mismatch")
    )
    invalid_manifest_release_status = str(
        package_manifest_artifact.get("invalid_release_status") or ""
    ).strip()
    manifest_release_status_mismatch = as_dict(
        package_manifest_artifact.get("release_status_mismatch")
    )
    effective_manifest_release_status = str(
        package_manifest_artifact.get("effective_release_status") or ""
    ).strip()
    missing_required_artifact_types = [
        str(artifact_type)
        for artifact_type in as_list(
            package_manifest_artifact.get("missing_required_artifact_types")
        )
        if artifact_type
    ]
    package_status_signals = _PackageStatusSignals(
        package_status=package_status,
        invalid_package_status=invalid_package_status,
        blocked_artifact_count=blocked_artifact_count,
        review_artifact_count=review_artifact_count,
        missing_artifact_count=missing_artifact_count,
        duplicate_artifact_types=duplicate_artifact_types,
        invalid_artifact_statuses=invalid_artifact_statuses,
        artifact_count_mismatch=artifact_count_mismatch,
        invalid_valuation_pdf_status=invalid_valuation_pdf_status,
        valuation_pdf_status_mismatch=valuation_pdf_status_mismatch,
        invalid_manifest_release_status=invalid_manifest_release_status,
        manifest_release_status_mismatch=manifest_release_status_mismatch,
        effective_manifest_release_status=effective_manifest_release_status,
        missing_required_artifact_types=missing_required_artifact_types,
    )
    effective_package_status = _effective_package_status(
        package_manifest_artifact,
        package_status_signals,
    )
    return {
        "package_status": package_status_signals.package_status,
        "effective_package_status": effective_package_status,
        "invalid_package_status": package_status_signals.invalid_package_status,
        "blocked_artifact_count": package_status_signals.blocked_artifact_count,
        "review_artifact_count": package_status_signals.review_artifact_count,
        "missing_artifact_count": package_status_signals.missing_artifact_count,
        "duplicate_artifact_types": package_status_signals.duplicate_artifact_types,
        "invalid_artifact_statuses": package_status_signals.invalid_artifact_statuses,
        "artifact_count_mismatch": package_status_signals.artifact_count_mismatch,
        "invalid_valuation_pdf_status": package_status_signals.invalid_valuation_pdf_status,
        "valuation_pdf_status_mismatch": package_status_signals.valuation_pdf_status_mismatch,
        "invalid_manifest_release_status": package_status_signals.invalid_manifest_release_status,
        "manifest_release_status_mismatch": package_status_signals.manifest_release_status_mismatch,
        "effective_manifest_release_status": (
            package_status_signals.effective_manifest_release_status
        ),
        "missing_required_artifact_types": (package_status_signals.missing_required_artifact_types),
        "package_integrity_issues": safe_int(
            package_manifest_artifact.get("package_integrity_issue_count")
        ),
    }


def _effective_package_status(
    package_manifest_artifact: JsonMap,
    signals: _PackageStatusSignals,
) -> str:
    summarized_effective_package_status = str(
        package_manifest_artifact.get("effective_package_status") or ""
    ).strip()
    if summarized_effective_package_status:
        return summarized_effective_package_status

    if _has_blocking_package_status(signals):
        return "blocked"
    if _needs_package_review(signals):
        return "needs_review"
    return signals.package_status


def _has_blocking_package_status(signals: _PackageStatusSignals) -> bool:
    return any(
        (
            signals.package_status == "missing",
            bool(signals.missing_required_artifact_types),
            bool(signals.missing_artifact_count),
            bool(signals.blocked_artifact_count),
            bool(signals.duplicate_artifact_types),
            bool(signals.invalid_package_status),
            bool(signals.invalid_artifact_statuses),
            bool(signals.artifact_count_mismatch),
            bool(signals.invalid_valuation_pdf_status),
            bool(signals.valuation_pdf_status_mismatch),
            bool(signals.invalid_manifest_release_status),
            _has_blocking_release_status_mismatch(signals),
        )
    )


def _has_blocking_release_status_mismatch(signals: _PackageStatusSignals) -> bool:
    return bool(
        signals.manifest_release_status_mismatch
        and signals.effective_manifest_release_status == "blocked"
    )


def _needs_package_review(signals: _PackageStatusSignals) -> bool:
    return bool(signals.review_artifact_count and signals.package_status in {"", "ready"})


def _add_required_artifact_finding(
    findings: list[JsonMap],
    package_manifest_artifact: JsonMap,
    package_state: JsonMap,
) -> None:
    add_finding(
        findings,
        code="buyer_ready_package_manifest_required_artifacts_missing",
        severity="critical",
        title="Buyer package manifest is missing required artifacts",
        detail=(
            "The controlled SME transaction package must include the main valuation report, "
            "valuation PDF, IM/CIM, DD checklist, buyer FAQ, EBITDA bridge, WC/tax pack, "
            "data-room manifest, price recommendation, and legal-readiness handoff."
        ),
        missing_required_context_keys=package_state["missing_required_artifact_types"],
        metadata={
            "artifact_types": package_manifest_artifact.get("artifact_types", []),
            "included_artifact_count": package_manifest_artifact.get("included_artifact_count"),
        },
    )


def _add_package_status_finding(
    findings: list[JsonMap],
    package_manifest_artifact: JsonMap,
    package_state: JsonMap,
    effective_package_status: str,
) -> None:
    add_finding(
        findings,
        code="buyer_ready_package_manifest_not_clear",
        severity=_package_status_finding_severity(effective_package_status),
        title="Buyer package manifest requires distribution review",
        detail=_package_status_finding_detail(effective_package_status),
        metadata=_package_status_finding_metadata(
            package_manifest_artifact=package_manifest_artifact,
            package_state=package_state,
            effective_package_status=effective_package_status,
        ),
    )


def _package_status_finding_severity(effective_package_status: str) -> str:
    return "critical" if effective_package_status == "blocked" else "high"


def _package_status_finding_detail(effective_package_status: str) -> str:
    if effective_package_status == "blocked":
        return "One or more controlled buyer-package artifacts blocks external distribution."
    return "One or more controlled buyer-package artifacts needs advisor or legal review."


def _package_status_finding_metadata(
    *,
    package_manifest_artifact: JsonMap,
    package_state: JsonMap,
    effective_package_status: str,
) -> JsonMap:
    metadata = _package_metadata_from_state(package_state)
    metadata["effective_package_status"] = effective_package_status
    metadata.update(_package_metadata_from_artifact(package_manifest_artifact))
    return metadata


def _package_metadata_from_state(package_state: JsonMap) -> JsonMap:
    return {
        output_key: _metadata_value(package_state.get(state_key), empty_as_none=empty_as_none)
        for output_key, state_key, empty_as_none in _PACKAGE_METADATA_STATE_FIELDS
    }


def _package_metadata_from_artifact(package_manifest_artifact: JsonMap) -> JsonMap:
    return {
        output_key: _metadata_value(
            package_manifest_artifact.get(artifact_key),
            empty_as_none=empty_as_none,
        )
        for output_key, artifact_key, empty_as_none in _PACKAGE_METADATA_ARTIFACT_FIELDS
    }


def _metadata_value(value: object, *, empty_as_none: bool) -> object:
    if empty_as_none and not value:
        return None
    return value


def _apply_im_content_findings(
    findings: list[JsonMap],
    buyer_ready_artifacts: JsonMap,
) -> int:
    package_manifest_artifact = as_dict(buyer_ready_artifacts.get("buyer_package_manifest"))
    if not package_manifest_artifact:
        return 0

    manifest_artifact_types = [
        str(artifact_type)
        for artifact_type in as_list(package_manifest_artifact.get("artifact_types"))
        if artifact_type
    ]
    if "im_cim" not in manifest_artifact_types:
        return 0

    content_provenance = as_dict(package_manifest_artifact.get("content_provenance"))
    im_content = as_dict(content_provenance.get("im_cim"))
    im_provider = str(im_content.get("provider") or "").strip()
    im_status = str(im_content.get("status") or "").strip()
    if im_provider.startswith("claude_") and im_status == "claude_generated":
        return 0

    add_finding(
        findings,
        code="buyer_ready_im_claude_narrative_not_clear",
        severity="high",
        title="IM/CIM custom narrative is not Claude-generated",
        detail=(
            "The buyer-ready IM/CIM should carry Titan Claude custom narrative "
            "provenance before external distribution. Structured-only or "
            "advisor-review content must stay in review."
        ),
        metadata={
            "provider": im_provider or None,
            "status": im_status or None,
        },
    )
    return -12


def _apply_ebitda_bridge_findings(
    findings: list[JsonMap],
    buyer_ready_artifacts: JsonMap,
) -> int:
    bridge_artifact = as_dict(buyer_ready_artifacts.get("ebitda_bridge"))
    bridge_status = str(bridge_artifact.get("buyer_belief_status") or "").strip()
    if bridge_status not in {"advisor_review", "not_buyer_ready"}:
        return 0

    severity = "critical" if bridge_status == "not_buyer_ready" else "high"
    add_finding(
        findings,
        code="buyer_belief_bridge_not_clear",
        severity=severity,
        title="Normalised EBITDA bridge needs buyer-belief review",
        detail=(
            "One or more EBITDA bridge steps lacks enough buyer-verifiable evidence "
            "for external distribution."
        ),
        metadata={
            "buyer_belief_status": bridge_status,
            "weak_evidence_step_count": bridge_artifact.get("weak_evidence_step_count", 0),
            "unsupported_step_count": bridge_artifact.get("unsupported_step_count", 0),
        },
    )
    return -25 if bridge_status == "not_buyer_ready" else -12
