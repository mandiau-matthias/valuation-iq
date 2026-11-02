"""Buyer package manifest validation and summary policy."""

from src.services.reports.report_readiness_common import JsonMap, as_dict, as_list, safe_int
from src.services.reports.transaction_readiness_labels import buyer_package_artifact_label

REQUIRED_BUYER_READY_PACKAGE_ARTIFACT_TYPES = (
    "valuation_main_report",
    "valuation_pdf",
    "im_cim",
    "dd_checklist",
    "buyer_faq",
    "ebitda_bridge",
    "wc_tax",
    "data_room_manifest",
    "price_recommendation",
    "legal_readiness",
)

VALID_BUYER_READY_PACKAGE_ARTIFACT_STATUSES = {
    "ready",
    "needs_review",
    "blocked",
    "missing",
}

VALID_BUYER_READY_RELEASE_STATUSES = {
    "teaser_ready",
    "nda_required",
    "lawyer_review_required",
    "blocked",
}


def derive_buyer_package_release_status(
    *,
    release_status: str,
    package_status: str,
    blocked_artifact_count: int = 0,
    review_artifact_count: int = 0,
    missing_artifact_count: int = 0,
) -> JsonMap:
    """Clamp manifest release status to artifact and package-status reality."""
    raw_release_status = str(release_status or "").strip()
    normalized_package_status = str(package_status or "").strip()
    invalid_release_status = _invalid_buyer_release_status(raw_release_status)
    effective_release_status = _effective_buyer_release_status(
        raw_release_status=raw_release_status,
        invalid_release_status=invalid_release_status,
        package_status=normalized_package_status,
        blocked_artifact_count=blocked_artifact_count,
        review_artifact_count=review_artifact_count,
        missing_artifact_count=missing_artifact_count,
    )
    return {
        "release_status": raw_release_status,
        "effective_release_status": effective_release_status,
        "invalid_release_status": invalid_release_status,
        "release_status_mismatch": _release_status_mismatch(
            raw_release_status, effective_release_status
        ),
    }


def _invalid_buyer_release_status(raw_release_status: str) -> str:
    if raw_release_status and raw_release_status not in VALID_BUYER_READY_RELEASE_STATUSES:
        return raw_release_status
    return ""


def _effective_buyer_release_status(
    *,
    raw_release_status: str,
    invalid_release_status: str,
    package_status: str,
    blocked_artifact_count: int,
    review_artifact_count: int,
    missing_artifact_count: int,
) -> str:
    if _release_status_must_block(
        raw_release_status=raw_release_status,
        invalid_release_status=invalid_release_status,
        package_status=package_status,
        blocked_artifact_count=blocked_artifact_count,
        missing_artifact_count=missing_artifact_count,
    ):
        return "blocked"
    if _release_status_needs_lawyer_review(
        package_status=package_status,
        review_artifact_count=review_artifact_count,
    ):
        return "lawyer_review_required"
    return raw_release_status or "nda_required"


def _release_status_must_block(
    *,
    raw_release_status: str,
    invalid_release_status: str,
    package_status: str,
    blocked_artifact_count: int,
    missing_artifact_count: int,
) -> bool:
    return bool(
        not raw_release_status
        or invalid_release_status
        or package_status in {"blocked", "missing"}
        or blocked_artifact_count
        or missing_artifact_count
    )


def _release_status_needs_lawyer_review(
    *,
    package_status: str,
    review_artifact_count: int,
) -> bool:
    return bool(review_artifact_count or package_status == "needs_review")


def _release_status_mismatch(
    raw_release_status: str,
    effective_release_status: str,
) -> JsonMap | None:
    if not raw_release_status or effective_release_status == raw_release_status:
        return None
    return {
        "manifest_status": raw_release_status,
        "effective_status": effective_release_status,
    }


_BUYER_RELEASE_PRECEDENCE = {
    "blocked": 0,
    "lawyer_review_required": 1,
    "nda_required": 2,
    "teaser_ready": 3,
}


def strictest_buyer_release_status(*statuses: str) -> str:
    known = [
        str(status or "").strip()
        for status in statuses
        if str(status or "").strip() in VALID_BUYER_READY_RELEASE_STATUSES
    ]
    if not known:
        return "nda_required"
    return min(known, key=lambda status: _BUYER_RELEASE_PRECEDENCE[status])


def package_integrity_issue_count(
    *,
    invalid_artifact_statuses: list[JsonMap],
    duplicate_artifact_types: list[str],
    invalid_package_status: str,
    artifact_count_mismatch: JsonMap,
    invalid_valuation_pdf_status: str,
    valuation_pdf_status_mismatch: JsonMap,
    invalid_package_release_status: str,
    package_release_status_mismatch: JsonMap,
) -> int:
    return (
        len(invalid_artifact_statuses)
        + len(duplicate_artifact_types)
        + (1 if invalid_package_status else 0)
        + (1 if artifact_count_mismatch else 0)
        + (1 if invalid_valuation_pdf_status else 0)
        + (1 if valuation_pdf_status_mismatch else 0)
        + (1 if invalid_package_release_status else 0)
        + (1 if package_release_status_mismatch else 0)
    )


def buyer_package_readiness_score(
    *,
    missing_artifact_count: int,
    review_artifact_count: int,
    blocked_artifact_count: int,
    integrity_issue_count: int,
    package_status: str,
) -> int:
    score = (
        100
        - missing_artifact_count * 18
        - review_artifact_count * 8
        - blocked_artifact_count * 20
        - integrity_issue_count * 12
    )
    normalized_status = str(package_status or "").strip()
    if normalized_status == "blocked":
        score = min(score, 35)
    elif normalized_status == "needs_review":
        score = min(score, 65)
    elif normalized_status == "missing":
        score = 0
    return max(0, score)


def _artifact_rows(manifest: JsonMap) -> list[JsonMap]:
    return [as_dict(artifact) for artifact in as_list(manifest.get("artifacts"))]


def _artifact_type_list(artifact_rows: list[JsonMap]) -> list[str]:
    return [
        str(artifact.get("artifact_type"))
        for artifact in artifact_rows
        if artifact.get("artifact_type")
    ]


def _duplicate_artifact_types(artifact_type_list: list[str]) -> list[str]:
    artifact_types = set(artifact_type_list)
    return sorted(
        artifact_type
        for artifact_type in artifact_types
        if artifact_type_list.count(artifact_type) > 1
    )


def _invalid_artifact_statuses(artifact_rows: list[JsonMap]) -> list[JsonMap]:
    return [
        {
            "artifact_type": str(artifact.get("artifact_type") or "unknown"),
            "status": str(artifact.get("status") or ""),
        }
        for artifact in artifact_rows
        if str(artifact.get("status") or "").strip()
        not in VALID_BUYER_READY_PACKAGE_ARTIFACT_STATUSES
    ]


def _artifact_count_mismatch(manifest: JsonMap, artifact_rows: list[JsonMap]) -> JsonMap | None:
    included_artifact_count_raw = manifest.get("included_artifact_count")
    included_artifact_count = safe_int(included_artifact_count_raw)
    if included_artifact_count_raw is not None and included_artifact_count == len(artifact_rows):
        return {}
    return {
        "declared": included_artifact_count_raw,
        "actual": len(artifact_rows),
    }


def _valuation_pdf_artifact(artifact_rows: list[JsonMap]) -> JsonMap:
    return next(
        (
            artifact
            for artifact in artifact_rows
            if artifact.get("artifact_type") == "valuation_pdf"
        ),
        {},
    )


def _invalid_valuation_pdf_status(manifest: JsonMap) -> str:
    valuation_pdf_status = str(manifest.get("valuation_pdf_status") or "").strip()
    if valuation_pdf_status in VALID_BUYER_READY_PACKAGE_ARTIFACT_STATUSES:
        return ""
    return valuation_pdf_status


def _valuation_pdf_status_mismatch(
    manifest: JsonMap, artifact_rows: list[JsonMap]
) -> JsonMap | None:
    valuation_pdf_status = str(manifest.get("valuation_pdf_status") or "").strip()
    artifact_status = str(_valuation_pdf_artifact(artifact_rows).get("status") or "").strip()
    if not artifact_status or valuation_pdf_status == artifact_status:
        return {}
    return {
        "manifest_status": valuation_pdf_status or None,
        "artifact_status": artifact_status or None,
    }


def _missing_required_artifact_types(artifact_types: set[str]) -> list[str]:
    return [
        artifact_type
        for artifact_type in REQUIRED_BUYER_READY_PACKAGE_ARTIFACT_TYPES
        if artifact_type not in artifact_types
    ]


def _artifact_status_count(artifact_rows: list[JsonMap], status: str) -> int:
    return sum(
        1 for artifact in artifact_rows if str(artifact.get("status") or "").strip() == status
    )


def _missing_artifact_labels(
    artifact_rows: list[JsonMap],
    missing_required_artifact_types: list[str],
    *,
    locale: str,
) -> list[str]:
    labels = [
        buyer_package_artifact_label(artifact_type, locale)
        for artifact_type in missing_required_artifact_types
    ]
    labels.extend(
        str(
            artifact.get("label")
            or buyer_package_artifact_label(str(artifact.get("artifact_type")), locale)
        )
        for artifact in artifact_rows
        if str(artifact.get("status") or "").strip() == "missing" and artifact.get("artifact_type")
    )
    return labels


def _invalid_package_status(raw_package_status: str) -> str:
    if raw_package_status in VALID_BUYER_READY_PACKAGE_ARTIFACT_STATUSES:
        return ""
    return raw_package_status


def _default_package_status(
    *,
    missing_artifact_count: int,
    blocked_artifact_count: int,
    duplicate_artifact_types: list[str],
    invalid_artifact_statuses: list[JsonMap],
    review_artifact_count: int,
) -> str:
    if (
        missing_artifact_count
        or blocked_artifact_count
        or duplicate_artifact_types
        or invalid_artifact_statuses
    ):
        return "blocked"
    if review_artifact_count:
        return "needs_review"
    return "ready"


def _package_status_has_blocking_integrity_issue(
    *,
    missing_artifact_count: int,
    blocked_artifact_count: int,
    duplicate_artifact_types: list[str],
    invalid_package_status: str,
    invalid_artifact_statuses: list[JsonMap],
    artifact_count_mismatch: JsonMap | None,
    invalid_valuation_pdf_status: str,
    valuation_pdf_status_mismatch: JsonMap | None,
    package_status: str,
) -> bool:
    return bool(
        missing_artifact_count
        or blocked_artifact_count
        or duplicate_artifact_types
        or invalid_package_status
        or invalid_artifact_statuses
        or artifact_count_mismatch
        or invalid_valuation_pdf_status
        or valuation_pdf_status_mismatch
        or package_status == "missing"
    )


def _apply_artifact_truth_to_package_status(
    *,
    raw_package_status: str,
    missing_artifact_count: int,
    blocked_artifact_count: int,
    duplicate_artifact_types: list[str],
    invalid_package_status: str,
    invalid_artifact_statuses: list[JsonMap],
    artifact_count_mismatch: JsonMap | None,
    invalid_valuation_pdf_status: str,
    valuation_pdf_status_mismatch: JsonMap | None,
    review_artifact_count: int,
) -> str:
    package_status = raw_package_status or _default_package_status(
        missing_artifact_count=missing_artifact_count,
        blocked_artifact_count=blocked_artifact_count,
        duplicate_artifact_types=duplicate_artifact_types,
        invalid_artifact_statuses=invalid_artifact_statuses,
        review_artifact_count=review_artifact_count,
    )
    if _package_status_has_blocking_integrity_issue(
        missing_artifact_count=missing_artifact_count,
        blocked_artifact_count=blocked_artifact_count,
        duplicate_artifact_types=duplicate_artifact_types,
        invalid_package_status=invalid_package_status,
        invalid_artifact_statuses=invalid_artifact_statuses,
        artifact_count_mismatch=artifact_count_mismatch,
        invalid_valuation_pdf_status=invalid_valuation_pdf_status,
        valuation_pdf_status_mismatch=valuation_pdf_status_mismatch,
        package_status=package_status,
    ):
        return "blocked"
    if review_artifact_count and package_status == "ready":
        return "needs_review"
    return package_status


def _apply_release_truth_to_package_status(package_status: str, release_fields: JsonMap) -> str:
    if release_fields["invalid_release_status"]:
        return "blocked"
    if (
        release_fields["release_status_mismatch"]
        and release_fields["effective_release_status"] == "blocked"
    ):
        return "blocked"
    if (
        release_fields["release_status_mismatch"]
        and release_fields["effective_release_status"] == "lawyer_review_required"
        and package_status == "ready"
    ):
        return "needs_review"
    return package_status


def summarize_buyer_package_manifest(manifest: JsonMap, *, locale: str = "en") -> JsonMap:
    """Single source of truth for manifest artifact truth vs header fields."""
    artifact_rows = _artifact_rows(manifest)
    artifact_type_list = _artifact_type_list(artifact_rows)
    artifact_types = set(artifact_type_list)
    duplicate_artifact_types = _duplicate_artifact_types(artifact_type_list)
    invalid_artifact_statuses = _invalid_artifact_statuses(artifact_rows)
    artifact_count_mismatch = _artifact_count_mismatch(manifest, artifact_rows)
    invalid_valuation_pdf_status = _invalid_valuation_pdf_status(manifest)
    valuation_pdf_status_mismatch = _valuation_pdf_status_mismatch(manifest, artifact_rows)
    missing_required_artifact_types = _missing_required_artifact_types(artifact_types)
    missing_status_artifact_count = _artifact_status_count(artifact_rows, "missing")
    missing_required_artifact_count = len(missing_required_artifact_types)
    missing_artifact_count = missing_status_artifact_count + missing_required_artifact_count
    missing_artifact_labels = _missing_artifact_labels(
        artifact_rows,
        missing_required_artifact_types,
        locale=locale,
    )
    blocked_artifact_count = _artifact_status_count(artifact_rows, "blocked")
    review_artifact_count = _artifact_status_count(artifact_rows, "needs_review")
    raw_package_status = str(manifest.get("package_status") or "").strip()
    invalid_package_status = _invalid_package_status(raw_package_status)
    package_status = _apply_artifact_truth_to_package_status(
        raw_package_status=raw_package_status,
        missing_artifact_count=missing_artifact_count,
        blocked_artifact_count=blocked_artifact_count,
        duplicate_artifact_types=duplicate_artifact_types,
        invalid_package_status=invalid_package_status,
        invalid_artifact_statuses=invalid_artifact_statuses,
        artifact_count_mismatch=artifact_count_mismatch,
        invalid_valuation_pdf_status=invalid_valuation_pdf_status,
        valuation_pdf_status_mismatch=valuation_pdf_status_mismatch,
        review_artifact_count=review_artifact_count,
    )
    release_fields = derive_buyer_package_release_status(
        release_status=str(manifest.get("release_status") or ""),
        package_status=package_status,
        blocked_artifact_count=blocked_artifact_count,
        review_artifact_count=review_artifact_count,
        missing_artifact_count=missing_artifact_count,
    )
    invalid_package_release_status = str(release_fields["invalid_release_status"] or "")
    package_release_status_mismatch = as_dict(release_fields["release_status_mismatch"])
    package_status = _apply_release_truth_to_package_status(package_status, release_fields)
    integrity_issue_count = package_integrity_issue_count(
        invalid_artifact_statuses=invalid_artifact_statuses,
        duplicate_artifact_types=duplicate_artifact_types,
        invalid_package_status=invalid_package_status,
        artifact_count_mismatch=artifact_count_mismatch,
        invalid_valuation_pdf_status=invalid_valuation_pdf_status,
        valuation_pdf_status_mismatch=valuation_pdf_status_mismatch,
        invalid_package_release_status=invalid_package_release_status,
        package_release_status_mismatch=package_release_status_mismatch,
    )
    return {
        "package_status": package_status,
        "raw_package_status": raw_package_status,
        "release_status": release_fields["release_status"],
        "effective_release_status": release_fields["effective_release_status"],
        "invalid_release_status": release_fields["invalid_release_status"],
        "release_status_mismatch": release_fields["release_status_mismatch"],
        "missing_artifact_count": missing_artifact_count,
        "missing_status_artifact_count": missing_status_artifact_count,
        "missing_required_artifact_count": missing_required_artifact_count,
        "missing_required_artifact_types": missing_required_artifact_types,
        "review_artifact_count": review_artifact_count,
        "blocked_artifact_count": blocked_artifact_count,
        "duplicate_artifact_types": duplicate_artifact_types,
        "invalid_artifact_statuses": invalid_artifact_statuses,
        "invalid_package_status": invalid_package_status,
        "artifact_count_mismatch": artifact_count_mismatch,
        "invalid_valuation_pdf_status": invalid_valuation_pdf_status,
        "valuation_pdf_status_mismatch": valuation_pdf_status_mismatch,
        "missing_artifact_labels": missing_artifact_labels,
        "package_integrity_issue_count": integrity_issue_count,
    }
