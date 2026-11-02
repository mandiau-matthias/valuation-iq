"""SaaS appendix context builder.

Builds the template context for the SaaS/ARR appendix page, including
ARR metrics, adjustment breakdowns, and quality scores.  Pure function
with no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, TypeAlias, cast

from src.domain.valuation_contract import normalize_method_key
from src.services.infrastructure.translations import (
    get_translations,
    localize_saas_adjustment_breakdown,
    normalize_report_locale,
)
from src.services.reports.helpers import extract_valuation_results_map
from src.utils.decimal_helpers import float_or_none

ReportMap: TypeAlias = dict[str, object]


@dataclass(frozen=True)
class SaasMethodSelection:
    method_data: ReportMap | None
    method_key: str | None
    details: ReportMap


@dataclass(frozen=True)
class SaasReportInputs:
    selection: SaasMethodSelection
    arr_method_data: ReportMap | None
    arr_method_details: ReportMap
    metrics: ReportMap
    arr_value: float | None
    arr_multiple: float | None
    enterprise_value: float | None
    adjustment_breakdown: list[object]


def _method_preference(
    *,
    selected_method: str | None,
    context: ReportMap,
) -> list[object]:
    return [
        selected_method,
        context.get("primary_method_key"),
        context.get("method_override_selected_method"),
        "arr_multiple",
        "upswitch_adaptive",
        "ebitda_multiple",
    ]


def _method_details(method_data: object) -> ReportMap:
    if not isinstance(method_data, dict):
        return {}
    details = method_data.get("details")
    return cast(ReportMap, details) if isinstance(details, dict) else {}


def _has_saas_payload(*, canonical: str, details: ReportMap) -> bool:
    return (
        bool(details.get("saas_metrics"))
        or details.get("secondary_method_key") == "arr_multiple"
        or canonical == "arr_multiple"
    )


def _select_saas_method(
    *,
    valuation_results: ReportMap,
    method_preference: Sequence[object],
) -> SaasMethodSelection:
    for candidate in method_preference:
        if not candidate or not isinstance(candidate, str):
            continue
        canonical = normalize_method_key(candidate)
        method_data = valuation_results.get(canonical)
        if not isinstance(method_data, dict):
            continue
        method_map = cast(ReportMap, method_data)
        details = _method_details(method_map)
        if _has_saas_payload(canonical=canonical, details=details):
            return SaasMethodSelection(
                method_data=method_map,
                method_key=canonical,
                details=details,
            )
    return SaasMethodSelection(method_data=None, method_key=None, details={})


def _first_metrics(*sources: object) -> ReportMap:
    for candidate_metrics in sources:
        if isinstance(candidate_metrics, dict) and candidate_metrics:
            return cast(ReportMap, candidate_metrics)
    return {}


def _first_float(*values: object) -> float | None:
    for value in values:
        parsed = float_or_none(value)
        if parsed is not None:
            return parsed
    return None


def _resolve_adjustment_breakdown(
    *,
    arr_method_details: ReportMap,
    saas_details: ReportMap,
    context: ReportMap,
) -> list[object]:
    for candidate in (
        arr_method_details.get("saas_adjustment_breakdown"),
        saas_details.get("saas_adjustment_breakdown"),
        context.get("saas_adjustment_breakdown"),
    ):
        if isinstance(candidate, list):
            return list(candidate)
    return []


def _resolve_saas_report_inputs(
    *,
    valuation_results: ReportMap,
    context: ReportMap,
    method_preference: Sequence[object],
) -> SaasReportInputs:
    selection = _select_saas_method(
        valuation_results=valuation_results,
        method_preference=method_preference,
    )
    arr_method_data_raw = valuation_results.get("arr_multiple")
    arr_method_data = (
        cast(ReportMap, arr_method_data_raw) if isinstance(arr_method_data_raw, dict) else None
    )
    arr_method_details = _method_details(arr_method_data)
    metrics = _first_metrics(
        arr_method_details.get("saas_metrics"),
        selection.details.get("saas_metrics"),
    )
    arr_value = _first_float(
        arr_method_details.get("arr"),
        metrics.get("arr"),
        context.get("saas_arr"),
    )
    arr_multiple = _first_float(
        arr_method_data.get("multiple_used") if arr_method_data else None,
        context.get("saas_arr_multiple"),
    )
    enterprise_value = _first_float(arr_method_details.get("enterprise_value"))
    if enterprise_value is None and arr_value is not None and arr_multiple is not None:
        enterprise_value = round(arr_value * arr_multiple, 2)
    if enterprise_value is None:
        enterprise_value = float_or_none(context.get("saas_enterprise_value"))
    return SaasReportInputs(
        selection=selection,
        arr_method_data=arr_method_data,
        arr_method_details=arr_method_details,
        metrics=metrics,
        arr_value=arr_value,
        arr_multiple=arr_multiple,
        enterprise_value=enterprise_value,
        adjustment_breakdown=_resolve_adjustment_breakdown(
            arr_method_details=arr_method_details,
            saas_details=selection.details,
            context=context,
        ),
    )


def _metric_with_context_fallback(
    *,
    metrics: ReportMap,
    context: ReportMap,
    key: str,
) -> float | None:
    return _first_float(metrics.get(key), context.get(f"saas_{key}"))


def _has_saas_context(inputs: SaasReportInputs, context: ReportMap) -> bool:
    return (
        bool(inputs.metrics)
        or bool(inputs.adjustment_breakdown)
        or (inputs.arr_value is not None and inputs.arr_multiple is not None)
        or bool(context.get("show_saas_appendix"))
    )


def _empty_saas_context() -> ReportMap:
    # Always emit the cap-table flag (never as a missing key) so the
    # master_report ``{% if show_saas_cap_table %}`` mount works
    # uniformly on every code path, with or without SaaS context.
    return {
        "show_saas_formula": False,
        "show_saas_appendix": False,
        "show_saas_cap_table": False,
        "saas_cap_table_simulator": None,
        "saas_adjustment_breakdown": [],
    }


def _quality_score(metrics: ReportMap, context: ReportMap) -> float | None:
    return _first_float(metrics.get("saas_quality_score"), context.get("saas_quality_score"))


def _resolved_metric_fields(inputs: SaasReportInputs, context: ReportMap) -> ReportMap:
    metric_keys = {
        "saas_rule_of_40": "rule_of_40",
        "saas_nrr_pct": "nrr_pct",
        "saas_gross_revenue_churn_pct": "gross_revenue_churn_pct",
        "saas_customer_churn_pct": "customer_churn_pct",
        "saas_customer_concentration_pct": "customer_concentration_pct",
        "saas_gross_margin_pct": "gross_margin_pct",
        "saas_arr_growth_pct": "arr_growth_pct",
        "saas_ltv_cac": "ltv_cac",
        "saas_magic_number": "magic_number",
        "saas_nrr_expansion_spread": "nrr_expansion_spread",
        "saas_cac_payback_months": "cac_payback_months",
        "saas_expansion_revenue_pct": "expansion_revenue_pct",
    }
    return {
        output_key: _metric_with_context_fallback(
            metrics=inputs.metrics,
            context=context,
            key=source_key,
        )
        for output_key, source_key in metric_keys.items()
    }


def _is_primary_arr_method(
    *,
    selected_method: str | None,
    context: ReportMap,
) -> bool:
    return (
        normalize_method_key(selected_method or context.get("primary_method_key")) == "arr_multiple"
    )


def _show_saas_appendix(inputs: SaasReportInputs) -> bool:
    return bool(inputs.arr_value is not None or inputs.metrics or inputs.adjustment_breakdown)


def _cap_table_simulator(arr_method_details: ReportMap) -> ReportMap | None:
    # Keep the cap-table extraction beside the display policy so callers
    # never reach into nested valuation-result shapes directly.
    raw_cap_table_simulator = arr_method_details.get("cap_table_simulator")
    return (
        cast(ReportMap, raw_cap_table_simulator)
        if isinstance(raw_cap_table_simulator, dict)
        else None
    )


def _show_saas_formula(inputs: SaasReportInputs) -> bool:
    return all(
        value is not None
        for value in (inputs.arr_value, inputs.arr_multiple, inputs.enterprise_value)
    )


def _method_label(selection: SaasMethodSelection, fallback: str) -> object:
    method_data = selection.method_data or {}
    label = method_data.get("label")
    return label if isinstance(label, str) else fallback


def _translations_for_context(context: ReportMap, locale: str):
    country_code = str(context.get("country_code") or "BE").strip().upper() or "BE"
    return get_translations(
        normalize_report_locale(locale),
        country_code=country_code,
    )


def _base_multiple(inputs: SaasReportInputs, context: ReportMap) -> float | None:
    return (
        _metric_with_context_fallback(
            metrics=inputs.metrics,
            context=context,
            key="base_multiple",
        )
        or 5.0
    )


def _build_saas_payload(
    *,
    inputs: SaasReportInputs,
    context: ReportMap,
    selected_method: str | None,
    locale: str,
) -> ReportMap:
    translations = _translations_for_context(context, locale)
    show_saas_appendix = _show_saas_appendix(inputs)
    cap_table_simulator = _cap_table_simulator(inputs.arr_method_details)

    return {
        "show_saas_formula": _show_saas_formula(inputs),
        "show_saas_appendix": show_saas_appendix,
        "show_saas_cap_table": bool(show_saas_appendix and cap_table_simulator),
        "saas_cap_table_simulator": cap_table_simulator,
        "saas_method_key": inputs.selection.method_key,
        "saas_method_label": _method_label(
            inputs.selection,
            translations.synthesis_method_arr,
        ),
        "saas_secondary_method_label": inputs.selection.details.get("secondary_method_label"),
        "saas_is_primary_method": _is_primary_arr_method(
            selected_method=selected_method,
            context=context,
        ),
        "saas_arr": inputs.arr_value,
        "saas_arr_multiple": inputs.arr_multiple,
        # Base multiple is bound to the engine output so the report
        # waterfall never lies if the engine shifts to a tiered base.
        "saas_base_multiple": _base_multiple(inputs, context),
        "saas_enterprise_value": inputs.enterprise_value,
        **_resolved_metric_fields(inputs, context),
        "saas_quality_score": _quality_score(inputs.metrics, context),
        "saas_quality_label": inputs.metrics.get("saas_quality_label")
        or context.get("saas_quality_label"),
        "saas_adjustment_breakdown": localize_saas_adjustment_breakdown(
            inputs.adjustment_breakdown, locale
        ),
    }


def build_saas_report_context(
    valuation_data: ReportMap,
    context: ReportMap,
    selected_method: str | None = None,
    locale: str = "nl",
) -> ReportMap:
    """Return SaaS appendix context to merge into the report context.

    Returns a dict with ``show_saas_appendix``, ``saas_arr``,
    ``saas_adjustment_breakdown``, etc.  Callers should ``context.update()``
    the result.
    """
    valuation_results = extract_valuation_results_map(valuation_data)
    inputs = _resolve_saas_report_inputs(
        valuation_results=valuation_results,
        context=context,
        method_preference=_method_preference(
            selected_method=selected_method,
            context=context,
        ),
    )
    if not _has_saas_context(inputs, context):
        return _empty_saas_context()
    return _build_saas_payload(
        inputs=inputs,
        context=context,
        selected_method=selected_method,
        locale=locale,
    )
