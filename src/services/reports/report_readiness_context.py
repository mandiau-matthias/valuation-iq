"""Internal report readiness context for enterprise packaging.

The generated client report should stay clean. Findings from this module are
for the AI agent, QA tooling, and advisor workflow surfaces that need to know
whether a draft is ready for sign-off.
"""

from __future__ import annotations

from src.services.reports.buyer_package_manifest import (
    REQUIRED_BUYER_READY_PACKAGE_ARTIFACT_TYPES,
    VALID_BUYER_READY_PACKAGE_ARTIFACT_STATUSES,
    VALID_BUYER_READY_RELEASE_STATUSES,
    buyer_package_readiness_score,
    derive_buyer_package_release_status,
    package_integrity_issue_count,
    strictest_buyer_release_status,
    summarize_buyer_package_manifest,
)
from src.services.reports.buyer_ready_artifacts import buyer_ready_artifacts_from_context
from src.services.reports.method_component_registry import build_method_component_coverage
from src.services.reports.report_readiness_buyer_checks import add_finding as _add_finding
from src.services.reports.report_readiness_buyer_checks import apply_buyer_ready_findings
from src.services.reports.report_readiness_common import (
    JsonMap,
    as_dict,
    as_list,
    first_present,
    safe_int,
)

# Backward-compatible private aliases for older tests/imports.
_as_list = as_list
_as_dict = as_dict
_first_present = first_present
_safe_int = safe_int

__all__ = [
    "REQUIRED_BUYER_READY_PACKAGE_ARTIFACT_TYPES",
    "VALID_BUYER_READY_PACKAGE_ARTIFACT_STATUSES",
    "VALID_BUYER_READY_RELEASE_STATUSES",
    "build_report_readiness_context",
    "buyer_package_readiness_score",
    "derive_buyer_package_release_status",
    "package_integrity_issue_count",
    "strictest_buyer_release_status",
    "summarize_buyer_package_manifest",
]


def _coverage_from_context(context: JsonMap) -> dict[str, JsonMap]:
    coverage = context.get("method_component_coverage")
    if isinstance(coverage, dict):
        return {str(key): as_dict(value) for key, value in coverage.items()}
    built = build_method_component_coverage(context)
    return built if isinstance(built, dict) else {}


def _state_from_findings(score: int, findings: list[JsonMap]) -> str:
    severities = {finding.get("severity") for finding in findings}
    if "critical" in severities or score < 60:
        return "blocked"
    if severities.intersection({"high", "medium"}) or score < 90:
        return "review_required"
    return "ready"


def _failed_formula_checks(context: JsonMap) -> list[JsonMap]:
    failed: list[JsonMap] = []
    for check in as_list(context.get("defensibility_checks")):
        if isinstance(check, dict) and check.get("passed") is False:
            failed.append(as_dict(check))
    return failed


def _defensibility_recommendation(value: object) -> str:
    return str(value or "").strip().lower()


def _buyer_ready_artifacts_from_context(context: JsonMap) -> JsonMap:
    return buyer_ready_artifacts_from_context(context)


def _report_track(context: JsonMap) -> str:
    if context.get("is_startup_valuation_report"):
        return "startup"
    if context.get("is_liquidation_report"):
        return "liquidation"
    return "sme"


def _apply_sme_manifest_findings(
    context: JsonMap,
    *,
    report_track: str,
    findings: list[JsonMap],
) -> int:
    sections = as_list(context.get("sme_report_sections"))
    if report_track != "sme" or len(sections) >= 5:
        return 0

    _add_finding(
        findings,
        code="sme_manifest_incomplete",
        severity="critical",
        title="SME report manifest incomplete",
        detail="The SME report has fewer than the fixed base sections.",
    )
    return -40


def _apply_method_coverage_findings(
    context: JsonMap,
    *,
    findings: list[JsonMap],
) -> int:
    score_delta = 0
    for method_key, coverage in _coverage_from_context(context).items():
        if not isinstance(coverage, dict):
            continue
        missing = as_list(coverage.get("missing_required_context_keys"))
        if not missing:
            continue
        _add_finding(
            findings,
            code="method_component_coverage_partial",
            severity="high",
            title=f"Method evidence incomplete: {method_key}",
            detail=(
                "One or more required method report components are missing "
                "their backing context keys."
            ),
            method_key=str(method_key),
            missing_required_context_keys=[str(key) for key in missing],
        )
        score_delta -= min(30, 8 + len(missing) * 4)
    return score_delta


def _apply_weighted_synthesis_findings(
    context: JsonMap,
    *,
    findings: list[JsonMap],
) -> int:
    if not context.get("has_weighted_synthesis"):
        return 0

    score_delta = 0
    contributions = as_list(context.get("synthesis_contributions"))
    if len(contributions) < 2:
        _add_finding(
            findings,
            code="weighted_synthesis_under_evidenced",
            severity="high",
            title="Weighted synthesis needs at least two method contributions",
            detail=(
                "A custom weighted valuation page is enabled, but fewer "
                "than two method contributions are available."
            ),
        )
        score_delta -= 15
    if not context.get("synthesis_formula_display"):
        _add_finding(
            findings,
            code="weighted_synthesis_formula_missing",
            severity="medium",
            title="Weighted synthesis formula missing",
            detail=(
                "The synthesis page should expose the advisor-facing "
                "weighting formula for auditability."
            ),
        )
        score_delta -= 8
    return score_delta


def _apply_attestation_findings(
    context: JsonMap,
    *,
    findings: list[JsonMap],
) -> int:
    if not context.get("has_attestation_page") or as_list(context.get("attestation_summary_rows")):
        return 0

    _add_finding(
        findings,
        code="attestation_summary_missing",
        severity="medium",
        title="Attestation summary rows missing",
        detail=(
            "The signature page is enabled but has no summary rows "
            "for scope, basis, standard, or engine traceability."
        ),
    )
    return -8


def _apply_method_results_findings(
    context: JsonMap,
    *,
    report_track: str,
    findings: list[JsonMap],
) -> int:
    if report_track != "sme" or context.get("method_results_by_key"):
        return 0

    _add_finding(
        findings,
        code="method_results_missing",
        severity="medium",
        title="No method result map available",
        detail=(
            "The report can render from scalar context, but the typed "
            "method-result map is missing for enterprise audit workflows."
        ),
    )
    return -8


def _apply_formula_consistency_findings(
    context: JsonMap,
    *,
    findings: list[JsonMap],
) -> int:
    failed_checks = _failed_formula_checks(context)
    block_reason = str(context.get("defensibility_block_reason") or "").strip()
    if not block_reason and not failed_checks:
        return 0

    check_names = [
        str(check.get("name") or check.get("code") or "formula_check") for check in failed_checks
    ]
    _add_finding(
        findings,
        code="formula_consistency_failed",
        severity="critical",
        title="Formula consistency gate failed",
        detail=(
            block_reason
            or "At least one displayed formula check failed in the final report context."
        ),
        metadata={"failed_checks": check_names} if check_names else None,
    )
    return -40


def _apply_defensibility_submit_findings(
    context: JsonMap,
    *,
    findings: list[JsonMap],
) -> int:
    submit_recommendation = _defensibility_recommendation(
        context.get("defensibility_submit_recommendation")
    )
    if submit_recommendation not in {"warn", "block_soft"}:
        return 0

    reasons = as_list(context.get("defensibility_submit_reasons_en"))
    severity = "critical" if submit_recommendation == "block_soft" else "high"
    _add_finding(
        findings,
        code="defensibility_submit_gate_not_clear",
        severity=severity,
        title="Defensibility submit gate is not clear",
        detail=(
            "The final defensibility gate recommends advisor review before distribution."
            if submit_recommendation == "warn"
            else "The final defensibility gate recommends not distributing this report."
        ),
        metadata={
            "recommendation": submit_recommendation,
            "reason_count": len(reasons),
        },
    )
    return -25 if submit_recommendation == "block_soft" else -12


def _apply_defensibility_watermark_findings(
    context: JsonMap,
    *,
    findings: list[JsonMap],
) -> int:
    if not context.get("defensibility_auto_watermark"):
        return 0

    _add_finding(
        findings,
        code="defensibility_scope_watermark_active",
        severity="medium",
        title="Defensibility scope watermark active",
        detail=(
            "The final report requires a scope watermark or disclosure banner, "
            "so it is not yet enterprise-ready for clean external sign-off."
        ),
    )
    return -8


def _effective_transaction_release_status(
    buyer_ready_artifacts: JsonMap,
    buyer_ready_result: object,
) -> str:
    return strictest_buyer_release_status(
        (
            buyer_ready_result.effective_legal_release_status
            if as_dict(buyer_ready_artifacts.get("legal_readiness"))
            else ""
        ),
        (
            buyer_ready_result.effective_manifest_release_status
            if as_dict(buyer_ready_artifacts.get("buyer_package_manifest"))
            else ""
        ),
    )


def _readiness_result(
    *,
    state: str,
    score: int,
    report_track: str,
    buyer_ready_artifacts: JsonMap,
    effective_transaction_release_status: str,
    findings: list[JsonMap],
) -> JsonMap:
    readiness = {
        "state": state,
        "score": score,
        "track": report_track,
        "is_enterprise_ready": state == "ready",
        "buyer_ready_artifacts": buyer_ready_artifacts,
        "effective_transaction_release_status": effective_transaction_release_status,
        "client_visible_findings": [],
        "agent_findings": findings,
        "finding_count": len(findings),
    }

    return {
        "report_readiness": readiness,
        "report_readiness_state": state,
        "report_readiness_score": score,
        "effective_transaction_release_status": effective_transaction_release_status,
        "buyer_ready_artifacts": buyer_ready_artifacts,
        "ai_agent_report_findings": findings,
        "client_visible_report_findings": [],
    }


def build_report_readiness_context(context: JsonMap) -> JsonMap:
    """Build an internal readiness payload from report context.

    The payload intentionally uses agent-facing names and keeps
    ``client_visible_findings`` empty so report templates do not start showing
    operational notes by accident.
    """

    findings: list[JsonMap] = []
    score = 100
    report_track = _report_track(context)
    score += _apply_sme_manifest_findings(
        context,
        report_track=report_track,
        findings=findings,
    )
    score += _apply_method_coverage_findings(context, findings=findings)
    score += _apply_weighted_synthesis_findings(context, findings=findings)
    score += _apply_attestation_findings(context, findings=findings)
    score += _apply_method_results_findings(
        context,
        report_track=report_track,
        findings=findings,
    )
    score += _apply_formula_consistency_findings(context, findings=findings)
    score += _apply_defensibility_submit_findings(context, findings=findings)
    score += _apply_defensibility_watermark_findings(context, findings=findings)

    buyer_ready_artifacts = buyer_ready_artifacts_from_context(context)
    buyer_ready_result = apply_buyer_ready_findings(findings, buyer_ready_artifacts)
    score += buyer_ready_result.score_delta
    effective_transaction_release_status = _effective_transaction_release_status(
        buyer_ready_artifacts,
        buyer_ready_result,
    )

    score = max(0, min(100, int(score)))
    state = _state_from_findings(score, findings)
    return _readiness_result(
        state=state,
        score=score,
        report_track=report_track,
        buyer_ready_artifacts=buyer_ready_artifacts,
        effective_transaction_release_status=effective_transaction_release_status,
        findings=findings,
    )
