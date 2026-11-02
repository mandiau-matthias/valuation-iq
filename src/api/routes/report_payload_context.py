"""Payload context helpers for report render and PDF routes."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, TypeAlias

JsonMap: TypeAlias = dict[str, object]


def _coerce_boolish(value: object, default: bool = False) -> bool:
    """Parse JSON/body boolean-ish values safely."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return default


def _extract_persisted_report_context(valuation_data: JsonMap) -> JsonMap:
    """Extract persisted report_context from known payload locations."""
    candidates: list[object] = [
        valuation_data.get("report_context"),
        valuation_data.get("reportContext"),
    ]
    details = valuation_data.get("details")
    if isinstance(details, dict):
        candidates.extend([details.get("report_context"), details.get("reportContext")])
    for nested_key in ("valuation_result", "valuationResult"):
        nested = valuation_data.get(nested_key)
        if not isinstance(nested, dict):
            continue
        candidates.extend([nested.get("report_context"), nested.get("reportContext")])
        nested_details = nested.get("details")
        if isinstance(nested_details, dict):
            candidates.extend(
                [
                    nested_details.get("report_context"),
                    nested_details.get("reportContext"),
                ]
            )
    for candidate in candidates:
        if isinstance(candidate, dict):
            return candidate
    return {}


def _strip_safety_net_context(context: object) -> JsonMap:
    """Drop stale degraded-render markers before a fresh templated render."""
    if not isinstance(context, dict):
        return {}
    cleaned: JsonMap = dict(context)
    cleaned.pop("safety_net", None)
    cleaned.pop("safetyNet", None)
    return cleaned


def _extract_renderable_persisted_report_context(valuation_data: JsonMap) -> JsonMap:
    """Extract persisted report context after removing stale degraded markers."""
    return _strip_safety_net_context(_extract_persisted_report_context(valuation_data))


def _strip_safety_net_context_from_valuation_data(valuation_data: JsonMap) -> JsonMap:
    """Return valuation data with stale persisted safety-net context removed."""
    cleaned: JsonMap = dict(valuation_data)

    for key in ("report_context", "reportContext"):
        context = _strip_safety_net_context(cleaned.get(key))
        if context:
            cleaned[key] = context
        else:
            cleaned.pop(key, None)

    for nested_key in ("details", "valuation_result", "valuationResult"):
        nested = cleaned.get(nested_key)
        if isinstance(nested, dict):
            cleaned[nested_key] = _strip_safety_net_context_from_valuation_data(nested)

    return cleaned


def _is_blank_for_merge(value: object) -> bool:
    """True when a value carries no information and may be filled from context.

    Deliberately treats numeric zero as blank: the ICP scorer reads
    ``revenue`` by name, and a zero on a shape-trimmed Titan payload means
    "never populated", not "measured as zero". Booleans are exempt so a
    deliberate ``False`` stays authoritative.
    """
    if value is None:
        return True
    if isinstance(value, bool):
        return False
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    if isinstance(value, (int, float, Decimal)):
        return value == 0
    return False


def _build_defensibility_input(
    valuation_data: JsonMap,
    report_context: Optional[JsonMap] = None,
) -> JsonMap:
    """Build a canonical defensibility payload from valuation + context.

    Why: valuation_data can be shape-trimmed in some Titan cycles while
    report_context still carries the canonical year map and engine warnings.
    Merging selected keys avoids PRELIMINARY/LIMITED_SCOPE drift between
    /render and /pdf defensibility passes.

    Three passes, with deliberately different precedence:

      1. ``preferred_keys`` — context wins (fresh aggregation beats a stale
         persisted snapshot), except ``current_year_data``, which is merged
         per field because the context projection omits ``total_debt``.
      2. ``identity_keys`` — fill only, raw wins. These reach the ICP scorer
         and must never overwrite something the engine measured.
      3. ``metadata`` — union, raw wins per key.
    """
    merged: JsonMap = dict(valuation_data or {})
    ctx = report_context or {}
    if not isinstance(ctx, dict):
        return merged

    preferred_keys = (
        "years_of_data",
        "data_years",
        "historical_years_count",
        "year_data",
        "historical_years_data",
        "current_year_data",
        "engine_warnings",
        "data_quality_warnings",
    )
    for key in preferred_keys:
        candidate = ctx.get(key)
        if candidate in (None, "", [], {}):
            continue
        if key == "current_year_data" and isinstance(candidate, dict):
            existing_cur = merged.get("current_year_data")
            if isinstance(existing_cur, dict):
                # ``build_current_year_data_context`` projects only year /
                # revenue / ebitda / net_income / total_assets /
                # total_liabilities / cash — it carries NO ``total_debt``. A
                # blind overwrite therefore erased the raw payload's debt and
                # silently failed the academic balance-sheet pillar, which
                # reads cash OR total_debt. Context still wins per field; raw
                # only fills what the projection omits.
                candidate = {
                    **existing_cur,
                    **{k: v for k, v in candidate.items() if not _is_blank_for_merge(v)},
                }
        # Report context comes from fresh aggregation and should win over
        # stale persisted valuation snapshots for defensibility decisions.
        merged[key] = candidate

    # ICP identity keys. ``compute_icp_score`` reads these by exact top-level
    # name, but a shape-trimmed Titan valuation payload carries none of them —
    # they are canonical only on the aggregated report context
    # (``country_code`` from ``build_registry_report_context``,
    # ``business_type_id`` from ``build_benchmark_report_context``, ``revenue``
    # from the aggregator). Without this pass an accountant-delivered report
    # scored 0/10 on ICP while its own cover displayed country BE and a
    # resolved business type.
    #
    # Fill-only by design: a non-blank value already on ``valuation_data``
    # always wins, so this can only turn an unknown into a known — it can never
    # overwrite something the engine actually measured, which preserves the
    # /render vs /pdf parity this helper exists to guarantee.
    identity_keys = (
        "country_code",
        "country",
        "business_type_id",
        "revenue",
    )
    for key in identity_keys:
        if not _is_blank_for_merge(merged.get(key)):
            continue
        candidate = ctx.get(key)
        if _is_blank_for_merge(candidate):
            continue
        merged[key] = candidate

    # ``metadata`` is the only carrier the platform stamps preparer identity on
    # (actor_role / accountant_customer_id / report_commissioned_audience).
    # Union-merge rather than replace so a context-side blob can add keys but
    # never drop keys the raw payload already had.
    ctx_metadata = ctx.get("metadata")
    raw_metadata = merged.get("metadata")
    if isinstance(ctx_metadata, dict) or isinstance(raw_metadata, dict):
        combined_metadata: JsonMap = {}
        if isinstance(ctx_metadata, dict):
            combined_metadata.update(ctx_metadata)
        if isinstance(raw_metadata, dict):
            combined_metadata.update(raw_metadata)
        merged["metadata"] = combined_metadata

    if isinstance(merged.get("detailed_results"), dict):
        detailed = dict(merged.get("detailed_results") or {})
        if merged.get("years_of_data") not in (None, "", 0):
            detailed["years_of_data"] = merged.get("years_of_data")
        if merged.get("engine_warnings") not in (None, [], {}):
            detailed["engine_warnings"] = merged.get("engine_warnings")
        merged["detailed_results"] = detailed
    elif merged.get("years_of_data") not in (None, "", 0):
        merged["detailed_results"] = {"years_of_data": merged.get("years_of_data")}

    return merged


def _looks_degenerate_preview_payload(valuation_data: JsonMap) -> bool:
    """Detect sparse payloads that should not render full screen previews."""
    if not isinstance(valuation_data, dict):
        return True
    persisted_context = _extract_renderable_persisted_report_context(valuation_data)
    if persisted_context:
        context_rich_keys = (
            "company_name",
            "valuation",
            "equity_value",
            "sme_report_sections",
            "method_report_registry",
        )
        if any(persisted_context.get(key) not in (None, "", [], {}) for key in context_rich_keys):
            return False
    rich_sections = (
        "current_year_data",
        "historical_years_data",
        "year_data",
        "valuation_results",
        "detailed_results",
        "transparency",
    )
    for key in rich_sections:
        value = valuation_data.get(key)
        if isinstance(value, dict) and value:
            return False
        if isinstance(value, list) and len(value) > 0:
            return False
    details = valuation_data.get("details")
    if isinstance(details, dict) and details:
        return False
    return True


def _json_safe(value: object) -> object:
    """Convert report context values to plain JSON-serializable types."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        if value.is_nan() or value.is_infinite():
            return 0.0
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(val) for key, val in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    wrapped_data = getattr(value, "_data", None)
    if isinstance(wrapped_data, dict):
        return {str(key): _json_safe(val) for key, val in wrapped_data.items()}
    return str(value)
