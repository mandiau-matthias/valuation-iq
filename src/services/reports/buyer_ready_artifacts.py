"""Buyer-ready artifact extraction for report readiness."""

from src.services.reports.buyer_package_manifest import summarize_buyer_package_manifest
from src.services.reports.report_readiness_common import (
    JsonMap,
    as_dict,
    as_list,
    first_present,
    safe_int,
)


def _pricing_artifact(context: JsonMap, pricing: JsonMap) -> JsonMap | None:
    pricing_low = first_present(
        pricing.get("equity_value_low_eur"),
        pricing.get("equity_value_low"),
        context.get("equity_value_low"),
        context.get("valuation_range_low"),
    )
    pricing_mid = first_present(
        pricing.get("equity_value_mid_eur"),
        pricing.get("equity_value_mid"),
        context.get("equity_value"),
        context.get("valuation"),
    )
    pricing_high = first_present(
        pricing.get("equity_value_high_eur"),
        pricing.get("equity_value_high"),
        context.get("equity_value_high"),
        context.get("valuation_range_high"),
    )
    asking_price = first_present(
        pricing.get("recommended_asking_price_eur"),
        pricing.get("recommended_asking_price"),
        context.get("recommended_asking_price"),
    )
    if not any(
        value is not None for value in (pricing_low, pricing_mid, pricing_high, asking_price)
    ):
        return None
    return {
        "present": True,
        "equity_value_low": pricing_low,
        "equity_value_mid": pricing_mid,
        "equity_value_high": pricing_high,
        "recommended_asking_price": asking_price,
        "basis": pricing.get("basis"),
        "confidence": pricing.get("confidence"),
    }


def _legal_readiness_artifact(legal_readiness: JsonMap) -> JsonMap | None:
    if not legal_readiness:
        return None
    return {
        "present": True,
        "jurisdiction": legal_readiness.get("jurisdiction"),
        "deal_structure": legal_readiness.get("deal_structure"),
        "buyer_release_status": legal_readiness.get("buyer_release_status"),
        "counsel_review_required": legal_readiness.get("counsel_review_required"),
        "clear_count": safe_int(legal_readiness.get("clear_count")),
        "review_count": safe_int(legal_readiness.get("review_count")),
        "blocked_count": safe_int(legal_readiness.get("blocked_count")),
    }


def _manifest_artifacts(package_manifest: JsonMap) -> list[JsonMap]:
    return [as_dict(artifact) for artifact in as_list(package_manifest.get("artifacts"))]


def _manifest_artifact_types(manifest_artifacts: list[JsonMap]) -> list[str]:
    return [
        str(artifact.get("artifact_type"))
        for artifact in manifest_artifacts
        if artifact.get("artifact_type")
    ]


def _first_manifest_artifact(manifest_artifacts: list[JsonMap], artifact_type: str) -> JsonMap:
    return next(
        (
            artifact
            for artifact in manifest_artifacts
            if artifact.get("artifact_type") == artifact_type
        ),
        {},
    )


def _assistant_surfaces(manifest_artifacts: list[JsonMap]) -> list[str]:
    return sorted(
        {
            str(surface)
            for artifact in manifest_artifacts
            for surface in as_list(artifact.get("assistant_surfaces"))
            if surface
        }
    )


def _artifact_value_map(manifest_artifacts: list[JsonMap], value_key: str) -> JsonMap:
    return {
        str(artifact.get("artifact_type")): artifact.get(value_key)
        for artifact in manifest_artifacts
        if artifact.get(value_key)
    }


def _content_provenance(manifest_artifacts: list[JsonMap]) -> JsonMap:
    return {
        str(artifact.get("artifact_type")): {
            "provider": artifact.get("custom_content_provider"),
            "status": artifact.get("custom_content_status"),
        }
        for artifact in manifest_artifacts
        if artifact.get("custom_content_provider") or artifact.get("custom_content_status")
    }


def _buyer_package_manifest_artifact(package_manifest: JsonMap) -> JsonMap | None:
    if not package_manifest:
        return None
    manifest_summary = summarize_buyer_package_manifest(package_manifest, locale="en")
    manifest_artifacts = _manifest_artifacts(package_manifest)
    valuation_report_artifact = _first_manifest_artifact(
        manifest_artifacts, "valuation_main_report"
    )
    valuation_pdf_artifact = _first_manifest_artifact(manifest_artifacts, "valuation_pdf")
    valuation_pdf_artifact_status = str(valuation_pdf_artifact.get("status") or "").strip()
    return {
        "present": True,
        "package_status": package_manifest.get("package_status"),
        "effective_package_status": manifest_summary["package_status"],
        "release_status": package_manifest.get("release_status"),
        "effective_release_status": manifest_summary["effective_release_status"],
        "invalid_release_status": manifest_summary["invalid_release_status"],
        "release_status_mismatch": manifest_summary["release_status_mismatch"],
        "valuation_report_id": package_manifest.get("valuation_report_id"),
        "valuation_pdf_status": package_manifest.get("valuation_pdf_status"),
        "valuation_pdf_artifact_status": valuation_pdf_artifact_status,
        "invalid_valuation_pdf_status": manifest_summary["invalid_valuation_pdf_status"],
        "valuation_pdf_status_mismatch": manifest_summary["valuation_pdf_status_mismatch"],
        "artifact_types": _manifest_artifact_types(manifest_artifacts),
        "duplicate_artifact_types": manifest_summary["duplicate_artifact_types"],
        "invalid_artifact_statuses": manifest_summary["invalid_artifact_statuses"],
        "missing_required_artifact_types": manifest_summary["missing_required_artifact_types"],
        "valuation_report_issued_at": valuation_report_artifact.get("issued_at"),
        "valuation_pdf_issued_at": valuation_pdf_artifact.get("issued_at"),
        "valuation_pdf_expires_at": valuation_pdf_artifact.get("expires_at"),
        "assistant_surfaces": _assistant_surfaces(manifest_artifacts),
        "integration_input_statuses": _artifact_value_map(
            manifest_artifacts, "integration_input_status"
        ),
        "open_input_count": sum(
            safe_int(artifact.get("open_input_count")) for artifact in manifest_artifacts
        ),
        "assistant_next_actions": _artifact_value_map(manifest_artifacts, "assistant_next_action"),
        "content_provenance": _content_provenance(manifest_artifacts),
        "included_artifact_count": package_manifest.get("included_artifact_count"),
        "artifact_count_mismatch": manifest_summary["artifact_count_mismatch"],
        "blocked_artifact_count": manifest_summary["blocked_artifact_count"],
        "review_artifact_count": manifest_summary["review_artifact_count"],
        "missing_artifact_count": manifest_summary["missing_artifact_count"],
        "missing_status_artifact_count": manifest_summary["missing_status_artifact_count"],
        "missing_required_artifact_count": manifest_summary["missing_required_artifact_count"],
        "package_integrity_issue_count": manifest_summary["package_integrity_issue_count"],
    }


def _ebitda_bridge_artifact(bridge: JsonMap) -> JsonMap | None:
    if not bridge:
        return None
    return {
        "present": True,
        "buyer_belief_status": bridge.get("buyer_belief_status"),
        "aggregate_confidence": bridge.get("aggregate_confidence"),
        "weak_evidence_step_count": bridge.get("weak_evidence_step_count", 0),
        "unsupported_step_count": bridge.get("unsupported_step_count", 0),
    }


def _wc_peg_artifact(wc_peg: JsonMap, wc_evidence: JsonMap) -> JsonMap | None:
    if not wc_peg and not wc_evidence:
        return None
    return {
        "present": True,
        "target_eur": first_present(wc_peg.get("target_eur"), wc_peg.get("target")),
        "confidence": wc_peg.get("confidence") or wc_evidence.get("confidence"),
        "derived_from": wc_peg.get("derived_from") or wc_evidence.get("derived_from"),
        "evidence_signal_count": len(
            as_list(wc_evidence.get("signals") or wc_evidence.get("source_refs"))
        ),
    }


def _tax_latency_flags(context: JsonMap, tax_latency: JsonMap) -> list[object]:
    if tax_latency:
        return as_list(tax_latency.get("flags"))
    return as_list(context.get("tax_latencies"))


def _tax_latency_artifact(context: JsonMap, tax_latency: JsonMap) -> JsonMap | None:
    tax_flags = _tax_latency_flags(context, tax_latency)
    if not tax_latency and not tax_flags:
        return None
    return {
        "present": True,
        "jurisdiction": tax_latency.get("jurisdiction"),
        "flag_count": first_present(tax_latency.get("flag_count"), len(tax_flags)),
        "net_impact_eur": context.get("tax_latency_net_impact"),
    }


def _tax_return_variance_artifact(variance_signals: list[object]) -> JsonMap | None:
    if not variance_signals:
        return None
    return {
        "present": True,
        "signal_count": len(variance_signals),
        "critical_count": sum(
            1 for signal in variance_signals if as_dict(signal).get("severity") == "critical"
        ),
    }


def _connector_quality_artifact(context: JsonMap, readiness_evidence: JsonMap) -> JsonMap | None:
    connector_quality_score = first_present(
        context.get("connector_quality_score"),
        readiness_evidence.get("connector_quality_score"),
    )
    if connector_quality_score is None:
        return None
    return {
        "present": True,
        "score": connector_quality_score,
    }


def _set_artifact(artifacts: JsonMap, key: str, artifact: JsonMap | None) -> None:
    if artifact:
        artifacts[key] = artifact


def buyer_ready_artifacts_from_context(context: JsonMap) -> JsonMap:
    readiness_evidence = as_dict(context.get("readiness_evidence"))
    wc_evidence = as_dict(readiness_evidence.get("working_capital_evidence"))
    pricing = as_dict(context.get("buyer_ready_pricing") or context.get("pricing"))
    legal_readiness = as_dict(
        context.get("buyer_ready_legal_readiness") or context.get("legal_readiness")
    )
    package_manifest = as_dict(
        context.get("buyer_ready_package_manifest")
        or context.get("buyer_package_manifest")
        or context.get("package_manifest")
    )
    wc_peg = as_dict(context.get("buyer_ready_wc_peg") or context.get("wc_peg"))
    tax_latency = as_dict(context.get("buyer_ready_tax_latency") or context.get("tax_latency"))
    bridge = as_dict(context.get("buyer_ready_ebitda_bridge") or context.get("ebitda_bridge"))

    artifacts: JsonMap = {}
    _set_artifact(artifacts, "pricing", _pricing_artifact(context, pricing))
    _set_artifact(artifacts, "legal_readiness", _legal_readiness_artifact(legal_readiness))
    _set_artifact(
        artifacts,
        "buyer_package_manifest",
        _buyer_package_manifest_artifact(package_manifest),
    )
    _set_artifact(artifacts, "ebitda_bridge", _ebitda_bridge_artifact(bridge))
    _set_artifact(artifacts, "wc_peg", _wc_peg_artifact(wc_peg, wc_evidence))
    _set_artifact(artifacts, "tax_latency", _tax_latency_artifact(context, tax_latency))
    _set_artifact(
        artifacts,
        "tax_return_variance",
        _tax_return_variance_artifact(as_list(readiness_evidence.get("variance_signals"))),
    )
    _set_artifact(
        artifacts,
        "connector_quality",
        _connector_quality_artifact(context, readiness_evidence),
    )

    return artifacts
