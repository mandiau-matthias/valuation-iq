"""Pure helpers shared by report-context builders.

These functions extract and transform valuation data structures
used by the Omni-Calc overrides and SaaS context builder.

TS mirrors: Titan/Mercury/Venus ``extractValuationResultsMap`` — keep candidate order and
``_with_method_aliases`` / ``withMethodAliases`` in sync; run
``node scripts/verify-valuation-extract-parity.mjs`` from the repo root.
"""

from __future__ import annotations

from typing import TypeAlias, cast

ReportMap: TypeAlias = dict[str, object]


METHOD_KEY_ALIASES = {
    "revenue_multiple": "omzet_multiple",
}


def _as_report_map(value: object) -> ReportMap:
    if not isinstance(value, dict):
        return {}
    return cast(ReportMap, value)


def normalize_method_key(method_key: object) -> str:
    if method_key is None:
        return ""
    raw = str(method_key).strip().lower().replace("-", "_")
    normalized = "_".join(raw.split())
    return METHOD_KEY_ALIASES.get(normalized, normalized)


def _is_dcf_method_key(method_key: object) -> bool:
    normalized = normalize_method_key(method_key)
    return normalized in {
        "dcf",
        "dcf_analysis",
        "discounted_cash_flow",
        "discounted_cash_flow_(dcf)",
        "discounted_cash_flow_dcf",
    }


def _is_hybrid_method_key(method_key: object) -> bool:
    normalized = normalize_method_key(method_key)
    return normalized in {"hybrid", "hybrid_dcf", "hybrid_valuation"}


def _with_method_aliases(method_map: ReportMap) -> ReportMap:
    """Mirror revenue aliases so report consumers can use either key safely."""
    if not method_map:
        return {}
    out = dict(method_map)
    if "omzet_multiple" in out and "revenue_multiple" not in out:
        out["revenue_multiple"] = out["omzet_multiple"]
    elif "revenue_multiple" in out and "omzet_multiple" not in out:
        out["omzet_multiple"] = out["revenue_multiple"]
    return out


def _canonical_report_context(valuation_data: ReportMap) -> ReportMap:
    vr = valuation_data.get("valuation_result")
    nested = _as_report_map(vr)
    details = _as_report_map(valuation_data.get("details"))
    nested_details = _as_report_map(nested.get("details"))
    candidates = [
        valuation_data.get("report_context"),
        details.get("report_context"),
        nested.get("report_context"),
        nested_details.get("report_context"),
    ]
    for candidate in candidates:
        if isinstance(candidate, dict):
            return cast(ReportMap, candidate)
    return {}


def _resolve_explicit_selected_method(valuation_data: ReportMap) -> str:
    vr = valuation_data.get("valuation_result")
    nested = _as_report_map(vr)
    details = _as_report_map(valuation_data.get("details"))
    report_ctx = _canonical_report_context(valuation_data)
    candidates = [
        report_ctx.get("selected_valuation_method"),
        valuation_data.get("selected_valuation_method"),
        details.get("selected_valuation_method"),
        nested.get("selected_valuation_method"),
    ]
    for candidate in candidates:
        normalized = normalize_method_key(candidate)
        if normalized:
            return normalized
    return ""


def _prune_stale_dcf_method(
    method_map: ReportMap,
    valuation_data: ReportMap,
) -> ReportMap:
    if "dcf" not in method_map:
        return method_map

    selected_method = _resolve_explicit_selected_method(valuation_data)
    if (
        not selected_method
        or _is_dcf_method_key(selected_method)
        or _is_hybrid_method_key(selected_method)
        or has_weighted_synthesis_payload(valuation_data)
    ):
        return method_map

    return {key: value for key, value in method_map.items() if key != "dcf"}


def extract_valuation_results_map(valuation_data: ReportMap) -> ReportMap:
    """Match Titan/Venus candidate order for legacy ``valuation_results`` placement."""
    vr = valuation_data.get("valuation_result")
    nested = _as_report_map(vr) if isinstance(vr, dict) else {}
    details = _as_report_map(valuation_data.get("details"))
    report_ctx = _as_report_map(valuation_data.get("report_context"))
    details_rc = _as_report_map(details.get("report_context"))
    nested_details = _as_report_map(nested.get("details"))
    nested_rc = _as_report_map(nested.get("report_context"))
    nested_details_rc = _as_report_map(nested_details.get("report_context"))

    candidates = [
        valuation_data.get("valuation_results"),
        details.get("valuation_results"),
        nested.get("valuation_results") if nested else None,
        nested_details.get("valuation_results") if nested_details else None,
        report_ctx.get("valuation_results"),
        details_rc.get("valuation_results"),
        nested_rc.get("valuation_results") if nested_rc else None,
        nested_details_rc.get("valuation_results") if nested_details_rc else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, dict) and candidate:
            pruned = _prune_stale_dcf_method(cast(ReportMap, candidate), valuation_data)
            if pruned:
                return _with_method_aliases(pruned)
    return {}


def has_weighted_synthesis_payload(valuation_data: ReportMap) -> bool:
    """Return True when *valuation_data* carries a blended weighted synthesis."""
    details = _as_report_map(valuation_data.get("details"))
    report_ctx = _as_report_map(valuation_data.get("report_context"))
    details_rc = _as_report_map(details.get("report_context"))
    vr = _as_report_map(valuation_data.get("valuation_result"))
    nested_details = _as_report_map(vr.get("details"))
    nested_rc = _as_report_map(vr.get("report_context"))
    nested_details_rc = _as_report_map(nested_details.get("report_context"))
    candidates = [
        valuation_data,
        valuation_data.get("weighted_valuation"),
        details,
        report_ctx,
        details_rc,
        vr,
        nested_details,
        nested_rc,
        nested_details_rc,
    ]
    for candidate in candidates:
        if isinstance(candidate, dict):
            candidate_map = cast(ReportMap, candidate)
            if (
                candidate_map.get("has_weighted_synthesis") is True
                or candidate_map.get("synthesis_blended_value") is not None
                or candidate_map.get("blended_equity_value") is not None
            ):
                return True
            weighted = candidate_map.get("weighted_valuation")
            if isinstance(weighted, dict) and (
                weighted.get("synthesis_blended_value") is not None
                or weighted.get("blended_equity_value") is not None
            ):
                return True
    return False


def swap_multiple_metric_suffix(label: object, metric_suffix: str) -> object:
    """Replace EV/EBITDA or EV/SDE in *label* with *metric_suffix*."""
    if not isinstance(label, str):
        return label
    return label.replace("EV/EBITDA", metric_suffix).replace("EV/SDE", metric_suffix)
