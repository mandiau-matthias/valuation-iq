"""Report-facing MethodResult context builder."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, TypeAlias, runtime_checkable

from src.domain.method_keys import METHOD_KEY_ALIASES, normalize_method_key
from src.domain.method_certification_profiles import supported_certification_methods
from src.services.reports.method_component_registry import (
    build_active_method_report_profiles,
    build_method_report_registry_context,
)

MethodSource: TypeAlias = Mapping[object, object]
MethodResultMap: TypeAlias = dict[str, object]
ReportMap: TypeAlias = dict[str, object]


@runtime_checkable
class ModelDumpLike(Protocol):
    def model_dump(self) -> object: ...


@runtime_checkable
class Gettable(Protocol):
    def get(self, key: object, default: object = None) -> object: ...


METHOD_RESULT_CONTEXT_KEYS: dict[str, str] = {
    "dcf": "dcf_method",
    "ebitda_multiple": "ebitda_method",
    "omzet_multiple": "revenue_method",
    "sde_multiple": "sde_method",
    "adjusted_nav": "adjusted_nav_method",
    "holding_sotp": "holding_sotp_method",
    "upswitch_adaptive": "upswitch_adaptive_method",
    "arr_multiple": "arr_method",
    "fiscal_4x": "fiscal_4x_method",
    "startup_valuation": "startup_method",
    "liquidation_analysis": "liquidation_method",
}


_RAW_METHOD_KEYS: tuple[str, ...] = tuple(
    dict.fromkeys(
        [
            *METHOD_RESULT_CONTEXT_KEYS.keys(),
            *METHOD_KEY_ALIASES.keys(),
        ]
    )
)


def _as_mapping(value: object) -> MethodSource:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return value
    data = getattr(value, "_data", None)
    if isinstance(data, Mapping):
        return data
    if isinstance(value, ModelDumpLike):
        dumped = value.model_dump()
        return dumped if isinstance(dumped, Mapping) else {}
    return {}


def _get_method_key(method: object) -> str:
    if method is None:
        return ""
    if isinstance(method, Mapping):
        return normalize_method_key(method.get("method_key"))
    return normalize_method_key(getattr(method, "method_key", None))


def _is_method_available(method: object) -> bool:
    if method is None:
        return False
    if isinstance(method, Mapping):
        return bool(method.get("available", True))
    return bool(getattr(method, "available", True))


def extract_method_results_map(valuation_results: object) -> MethodResultMap:
    """Return a report-normalized method-result map.

    Keys are normalized to the canonical calculation contract while useful
    public aliases are preserved. In practice this means either
    ``valuation_results["omzet_multiple"]`` or a MethodResult stamped
    ``method_key="revenue_multiple"`` will be available under both
    ``omzet_multiple`` and ``revenue_multiple`` for report consumers.
    """

    source = _as_mapping(valuation_results)
    if not source and isinstance(valuation_results, Gettable):
        source = {key: valuation_results.get(key) for key in _RAW_METHOD_KEYS}

    normalized: MethodResultMap = {}
    for raw_key, method in source.items():
        if method is None:
            continue
        canonical_key = normalize_method_key(raw_key)
        if canonical_key:
            normalized[canonical_key] = method
        stamped_key = _get_method_key(method)
        if stamped_key:
            normalized[stamped_key] = method

    for alias, canonical in METHOD_KEY_ALIASES.items():
        if canonical in normalized and alias not in normalized:
            normalized[alias] = normalized[canonical]
        if alias in normalized and canonical not in normalized:
            normalized[canonical] = normalized[alias]

    return normalized


def build_method_result_context(
    valuation_results: object,
    *,
    country_code: str | None = None,
) -> ReportMap:
    method_results = extract_method_results_map(valuation_results)
    if country_code is not None:
        allowed = set(supported_certification_methods(country_code))
        if "omzet_multiple" in allowed:
            allowed.add("revenue_multiple")
        method_results = {key: result for key, result in method_results.items() if key in allowed}
    dcf_result = method_results.get("dcf")
    active_profiles = build_active_method_report_profiles(method_results.keys())
    profiles_by_key: dict[str, ReportMap] = {}
    for profile in active_profiles:
        method_key = profile.get("method_key")
        if isinstance(method_key, str) and method_key:
            profiles_by_key[method_key] = profile
    for profile in active_profiles:
        aliases = profile.get("aliases", [])
        if isinstance(aliases, list):
            for alias in aliases:
                if isinstance(alias, str) and alias:
                    profiles_by_key.setdefault(alias, profile)

    report_registry = build_method_report_registry_context()
    context: ReportMap = {
        "method_results_by_key": method_results,
        "report_method_result_keys": sorted(method_results.keys()),
        "available_method_result_keys": sorted(
            key for key, method in method_results.items() if _is_method_available(method)
        ),
        "method_report_registry": report_registry,
        "method_citation_registry": report_registry,
        "active_method_report_profiles": active_profiles,
        "method_report_profiles_by_key": profiles_by_key,
    }

    for method_key, context_key in METHOD_RESULT_CONTEXT_KEYS.items():
        context[context_key] = method_results.get(method_key)

    # Keep the explicit English alias because citation registries and older
    # report pages still refer to the revenue method by that name.
    context["revenue_method"] = (
        method_results.get("revenue_multiple")
        or method_results.get("omzet_multiple")
        or context.get("revenue_method")
    )
    context["dcf_method_available"] = (
        _is_method_available(dcf_result) if dcf_result is not None else None
    )
    return context
