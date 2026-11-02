"""Official filing snapshot context for report aggregation."""

from collections.abc import Mapping

from src.services.infrastructure.official_financials_merge import (
    apply_trust_overlay,
    overlay_trust_dict,
)
from src.services.reports.protocol_adapter import DictWrapper, _attr, _unwrap

JsonMap = dict[str, object]


def _as_json_map(value: object) -> JsonMap:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def initial_official_financials() -> JsonMap:
    """Return the default official financials context."""
    return {
        "has_official_financials": False,
        "source": None,
        "source_label": None,
        "filing_year": None,
        "revenue": None,
        "revenue_source": None,
        "ebitda": None,
        "total_assets": None,
        "equity": None,
        "pdf_url": None,
        "source_links": [],
        "data_health": None,
        "variance_analysis": None,
        "verification_badge": None,
        "historical_years": None,
        "valuation_input_years": None,
        "excluded_valuation_years": None,
        "valuation_input_status": None,
    }


def _first_truthy(payload: Mapping[str, object], *keys: str) -> object | None:
    for key in keys:
        value = payload.get(key)
        if value:
            return value
    return None


def _first_present(payload: Mapping[str, object], *keys: str) -> object | None:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return value
    return None


def _merge_truthy_aliases(
    official: JsonMap,
    field: str,
    payload: Mapping[str, object],
    *keys: str,
) -> None:
    official[field] = _first_truthy(payload, *keys) or official[field]


def _merge_present_aliases(
    official: JsonMap,
    field: str,
    payload: Mapping[str, object],
    *keys: str,
) -> None:
    value = _first_present(payload, *keys)
    if value is not None:
        official[field] = value


def _merge_source_links(official: JsonMap, payload: Mapping[str, object]) -> None:
    links = _first_truthy(payload, "source_links", "sourceLinks") or []
    if isinstance(links, list):
        official["source_links"] = links


def _merge_data_health(official: JsonMap, payload: Mapping[str, object]) -> None:
    data_health = _first_present(payload, "data_health", "dataHealth")
    if isinstance(data_health, dict):
        official["data_health"] = data_health


def _merge_list_aliases(
    official: JsonMap,
    field: str,
    payload: Mapping[str, object],
    *keys: str,
) -> None:
    value = _first_present(payload, *keys)
    if isinstance(value, list):
        official[field] = value


def _merge_trust_payloads(
    official: JsonMap,
    payload: Mapping[str, object],
    root: Mapping[str, object],
) -> None:
    variance = _first_truthy(payload, "variance_analysis", "varianceAnalysis")
    root_variance = root.get("official_variance_analysis") if isinstance(root, dict) else None
    official["variance_analysis"] = apply_trust_overlay(
        official.get("variance_analysis"),
        variance if isinstance(variance, dict) else None,
        root_variance if isinstance(root_variance, dict) else None,
    )

    badge = _first_truthy(payload, "verification_badge", "verificationBadge")
    root_badge = root.get("official_verification_badge") if isinstance(root, dict) else None
    official["verification_badge"] = apply_trust_overlay(
        official.get("verification_badge"),
        badge if isinstance(badge, dict) else None,
        root_badge if isinstance(root_badge, dict) else None,
    )


def _merge_official_payload(
    official: JsonMap,
    payload: Mapping[str, object],
    root_payload: Mapping[str, object] | None = None,
) -> None:
    root = root_payload or payload
    _merge_truthy_aliases(official, "source", payload, "source")
    _merge_truthy_aliases(official, "source_label", payload, "source_label", "sourceLabel")
    _merge_truthy_aliases(official, "filing_year", payload, "filing_year", "filingYear")
    _merge_present_aliases(official, "revenue", payload, "revenue")
    _merge_truthy_aliases(official, "revenue_source", payload, "revenue_source", "revenueSource")
    _merge_present_aliases(official, "ebitda", payload, "ebitda")
    _merge_truthy_aliases(official, "total_assets", payload, "total_assets", "totalAssets")
    _merge_present_aliases(official, "equity", payload, "equity")
    _merge_truthy_aliases(official, "pdf_url", payload, "pdf_url", "pdfUrl")
    _merge_source_links(official, payload)
    _merge_data_health(official, payload)
    _merge_list_aliases(
        official, "historical_years", payload, "historical_years", "historicalYears"
    )
    _merge_list_aliases(
        official,
        "valuation_input_years",
        payload,
        "valuation_input_years",
        "valuationInputYears",
    )
    _merge_list_aliases(
        official,
        "excluded_valuation_years",
        payload,
        "excluded_valuation_years",
        "excludedValuationYears",
    )
    _merge_truthy_aliases(
        official,
        "valuation_input_status",
        payload,
        "valuation_input_status",
        "valuationInputStatus",
    )
    _merge_trust_payloads(official, payload, root)


def _merge_candidate_payloads(
    official: JsonMap,
    response: object,
    request: object | None,
) -> None:
    candidates = [
        getattr(response, "official_financials", None),
        getattr(request, "official_financials", None) if request else None,
    ]
    for candidate in candidates:
        payload = _unwrap(candidate) if isinstance(candidate, DictWrapper) else candidate
        payload = _as_json_map(payload)
        if not payload:
            continue
        root_payload = payload
        if "official_financials" in payload and isinstance(
            payload.get("official_financials"), dict
        ):
            payload = _as_json_map(payload["official_financials"])
        _merge_official_payload(official, payload, root_payload)


def _merge_top_level_trust(official: JsonMap, obj: object) -> None:
    if obj is None:
        return
    variance = _attr(obj, "official_variance_analysis")
    official["variance_analysis"] = overlay_trust_dict(
        official.get("variance_analysis"),
        variance if isinstance(variance, dict) else None,
    )
    badge = _attr(obj, "official_verification_badge")
    official["verification_badge"] = overlay_trust_dict(
        official.get("verification_badge"),
        badge if isinstance(badge, dict) else None,
    )


def _merge_report_context(official: JsonMap, response: object) -> None:
    report_context = getattr(response, "report_context", None)
    report_context = (
        _unwrap(report_context) if isinstance(report_context, DictWrapper) else report_context
    )
    if not isinstance(report_context, dict):
        return

    report_context_officials = report_context.get("official_financials")
    if isinstance(report_context_officials, dict):
        _merge_official_payload(official, report_context_officials, report_context)
        return

    variance = report_context.get("official_variance_analysis")
    official["variance_analysis"] = overlay_trust_dict(
        official.get("variance_analysis"),
        variance if isinstance(variance, dict) else None,
    )
    badge = report_context.get("official_verification_badge")
    official["verification_badge"] = overlay_trust_dict(
        official.get("verification_badge"),
        badge if isinstance(badge, dict) else None,
    )


def _mark_presence(official: JsonMap) -> None:
    official["has_official_financials"] = any(
        official[key] is not None
        for key in ("filing_year", "revenue", "ebitda", "total_assets", "equity")
    )


def build_official_financials_context(
    response: object,
    request: object | None,
) -> JsonMap:
    """Build official-filing snapshot for Jinja report context."""
    official = initial_official_financials()
    _merge_candidate_payloads(official, response, request)
    _merge_top_level_trust(official, request)
    _merge_top_level_trust(official, response)
    _merge_report_context(official, response)
    _mark_presence(official)
    return official
