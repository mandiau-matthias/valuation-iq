"""Dedicated report-method page gates and sensitivity context wiring."""

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import TypeAlias

from src.services.infrastructure.report_locale import normalize_report_locale
from src.services.reports.adaptive_report_gates import (
    coalesce_user_weights_for_gates,
    compute_has_upswitch_adaptive_page,
    compute_is_adaptive_only_path,
    refresh_adaptive_gates_on_context,
    resolve_effective_selected_method_for_report_gates,
)
from src.services.reports.method_result_context import build_method_result_context
from src.services.reports.method_sensitivity_context import apply_saved_method_sensitivities
from src.services.reports.protocol_adapter import _unwrap
from src.services.reports.report_revenue_method import apply_revenue_method_context
from src.utils.decimal_helpers import safe_float

JsonMap: TypeAlias = dict[str, object]
MetadataMap: TypeAlias = Mapping[str, object]

_ADAPTIVE_CONTEXT_FIELDS = (
    "adaptive_primary_basis",
    "adaptive_methodology_justification",
    "adaptive_multiple_used",
    "adaptive_dcf_weight",
    "adaptive_multiples_weight",
)


def _clean_method(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _metadata_value(metadata: MetadataMap | None, key: str) -> object:
    if not isinstance(metadata, Mapping):
        return None
    return metadata.get(key)


def _unwrap_adaptive_result(adaptive: object) -> object:
    if adaptive is None:
        return None
    underlying = getattr(adaptive, "_data", None)
    if isinstance(underlying, dict):
        return underlying
    model_dump = getattr(adaptive, "model_dump", None)
    if callable(model_dump):
        try:
            return model_dump()
        except (TypeError, ValueError):
            return None
    return adaptive


def _adaptive_value(adaptive: object, key: str, default: object = None) -> object:
    if isinstance(adaptive, dict):
        return adaptive.get(key, default)
    if adaptive:
        return getattr(adaptive, key, default)
    return default


def _clear_adaptive_context_fields(context: JsonMap) -> None:
    for key in _ADAPTIVE_CONTEXT_FIELDS:
        context.pop(key, None)


def _valid_adaptive_payload(valuation_results: object) -> object:
    if not hasattr(valuation_results, "get"):
        return None

    adaptive = _unwrap_adaptive_result(valuation_results.get("upswitch_adaptive"))
    if not adaptive or not _adaptive_value(adaptive, "available", False):
        return None
    if _adaptive_value(adaptive, "value") is None:
        return None
    return adaptive


def _promote_adaptive_details(
    context: JsonMap,
    adaptive: object,
    *,
    locale: str | None,
) -> None:
    adaptive_details = _adaptive_value(adaptive, "details") or {}
    if not isinstance(adaptive_details, dict):
        return

    primary_basis = adaptive_details.get("primary_basis")
    if primary_basis:
        context["adaptive_primary_basis"] = str(primary_basis)

    methodology_justification = adaptive_details.get("methodology_justification")
    if methodology_justification:
        context["adaptive_methodology_justification"] = _localize_adaptive_justification(
            str(methodology_justification),
            locale,
        )


def _localize_adaptive_justification(
    justification_text: str,
    locale: str | None,
) -> str:
    # Reuse substitution-reason localisers; the engine emits both fields with
    # the same template family, so the existing pattern translators catch both.
    just_locale = normalize_report_locale(locale)
    if just_locale == "nl":
        from src.services.reports.report_quality_warnings import _localise_substitution_reason_to_nl

        return _localise_substitution_reason_to_nl(justification_text)
    if just_locale == "fr":
        from src.services.reports.report_quality_warnings import _localise_substitution_reason_to_fr

        return _localise_substitution_reason_to_fr(justification_text)
    return justification_text


def _promote_adaptive_multiple(context: JsonMap, adaptive: object) -> None:
    adaptive_multiple = _adaptive_value(adaptive, "multiple_used")
    if adaptive_multiple is not None:
        context["adaptive_multiple_used"] = safe_float(adaptive_multiple)

    headline_multiple = _positive_headline_multiple(context)
    if headline_multiple is not None:
        context["adaptive_multiple_used"] = headline_multiple


def _positive_headline_multiple(context: JsonMap) -> float | None:
    # Coherence ("aansluitend"): the Adaptive page prints this under an
    # "EV/EBITDA" (or EV/Revenue, EV/SDE) label, so it MUST equal the headline's
    # applied multiple. Prefer the already-resolved headline multiple so every
    # surface shows one applied multiple.
    headline_multiple = context.get("applied_multiple")
    try:
        parsed_multiple = float(headline_multiple) if headline_multiple is not None else 0
    except (TypeError, ValueError):
        return None
    return parsed_multiple if parsed_multiple > 0 else None


def _promote_adaptive_weights(
    context: JsonMap,
    *,
    dcf_weight: object,
    multiples_weight: object,
) -> None:
    if dcf_weight is not None:
        context["adaptive_dcf_weight"] = safe_float(dcf_weight)
    if multiples_weight is not None:
        context["adaptive_multiples_weight"] = safe_float(multiples_weight)


def promote_upswitch_adaptive_context(
    context: JsonMap,
    *,
    valuation_results: object,
    dcf_weight: object = None,
    multiples_weight: object = None,
    locale: str | None = None,
) -> None:
    """Promote ``valuation_results.upswitch_adaptive`` into report context.

    `locale` is optional — when "nl" the Adaptive page's method-selection
    rationale is localised through the same helper used by the method-
    substitution disclosure, so the Adaptive page no longer carries a wall of
    English engine prose inside an otherwise Dutch report (Three Towers
    Capital regression — was the final remaining English leak on the
    Adaptive page after every other localisation layer was in place).
    """
    _clear_adaptive_context_fields(context)
    adaptive = _valid_adaptive_payload(valuation_results)
    if adaptive is None:
        context["upswitch_adaptive_value"] = None
        return

    context["upswitch_adaptive_value"] = safe_float(_adaptive_value(adaptive, "value"))
    _promote_adaptive_details(context, adaptive, locale=locale)
    _promote_adaptive_multiple(context, adaptive)
    _promote_adaptive_weights(
        context,
        dcf_weight=dcf_weight,
        multiples_weight=multiples_weight,
    )
    # NOTE: ``is_adaptive_multiples_only`` and ``adaptive_presentation_*`` blend
    # weights are set by ``refresh_adaptive_gates_on_context`` once
    # ``is_adaptive_only_path``, ``adaptive_dcf_weight``, and ``has_dcf`` settle.


def _apply_selected_method_inputs(
    context: JsonMap,
    *,
    request_selected_method: object = None,
    request_user_weights: object = None,
    request_primary_method_key: object = None,
    request_country_code: object = None,
    request_metadata: MetadataMap | None = None,
) -> None:
    selected_method = (
        _clean_method(context.get("selected_method"))
        or _clean_method(request_selected_method)
        or _clean_method(_metadata_value(request_metadata, "selected_method"))
    )
    user_weights = context.get("user_weights")
    if user_weights is None:
        user_weights = request_user_weights

    context["selected_method"] = selected_method
    context["user_weights"] = coalesce_user_weights_for_gates(user_weights)

    if context.get("primary_method_key"):
        return
    primary_method_key = request_primary_method_key or _metadata_value(
        request_metadata,
        "primary_method_key",
    )
    if _clean_method(primary_method_key):
        context["primary_method_key"] = _clean_method(primary_method_key)


def _promote_revenue_growth_cagr(
    context: JsonMap,
    financial_metrics: object,
) -> None:
    metrics = _unwrap(financial_metrics or context.get("financial_metrics") or {})
    if not isinstance(metrics, Mapping):
        return
    context.pop("revenue_growth_3y_cagr", None)
    # This field is a decimal ratio for exactly three fiscal years. A latest
    # observation change is not an interchangeable CAGR; zero is evidence too.
    cagr = metrics.get("revenue_cagr_3y")
    if cagr is None or isinstance(cagr, bool):
        return
    try:
        cagr_decimal = Decimal(str(cagr))
    except (InvalidOperation, ValueError):
        return
    if not cagr_decimal.is_finite() or cagr_decimal < -1:
        return
    context["revenue_growth_3y_cagr"] = cagr_decimal


def _apply_multiple_sensitivity_matrices(context: JsonMap) -> None:
    apply_saved_method_sensitivities(context)


def _has_adjusted_nav_page(context: JsonMap) -> bool:
    return bool(context.get("show_nav_bridge") and context.get("nav_corrected_value") is not None)


def _has_ebitda_multiple_page(context: JsonMap) -> bool:
    return bool(
        (context.get("applied_multiple") or 0) > 0
        and (context.get("ebitda_normalized") or 0) > 0
        and (context.get("ev_ebitda_enterprise_value") or 0) > 0
    )


def _has_sde_page(context: JsonMap) -> bool:
    return bool(
        context.get("is_sde_methodology")
        or (
            (context.get("sde_value") or 0) > 0
            and (context.get("sde_base_multiple") or 0) > 0
            and (context.get("ev_sde_enterprise_value") or 0) > 0
        )
    )


def _revenue_multiple_inputs(context: JsonMap) -> tuple[float, float, bool]:
    ebitda = float(context.get("ebitda_normalized") or 0)
    revenue = float(context.get("operating_revenue") or context.get("revenue") or 0)
    ebitda_margin = (ebitda / revenue) if revenue > 0 else 0
    selected_for_revenue_gate = _clean_method(context.get("selected_method")).lower()
    explicit_revenue_selected = selected_for_revenue_gate in {
        "revenue_multiple",
        "omzet_multiple",
    }
    return revenue, ebitda_margin, explicit_revenue_selected


def _has_revenue_multiple_page(context: JsonMap) -> bool:
    _, ebitda_margin, explicit_revenue_selected = _revenue_multiple_inputs(context)
    revenue_ev = float(
        context.get("ev_revenue_enterprise_value")
        or context.get("enterprise_value_mid")
        or context.get("valuation")
        or 0
    )
    return bool(
        (
            explicit_revenue_selected
            or (context.get("revenue_multiple_applied") or 0) > 0
            and ebitda_margin < 0.05
        )
        and revenue_ev > 0
    )


def _apply_adaptive_page_gates(context: JsonMap) -> None:
    effective_method = resolve_effective_selected_method_for_report_gates(context)
    user_weights = context.get("user_weights")
    has_adaptive_page = compute_has_upswitch_adaptive_page(
        effective_method,
        user_weights,
        context.get("upswitch_adaptive_value"),
    )
    context["has_upswitch_adaptive_page"] = has_adaptive_page
    context["is_adaptive_only_path"] = compute_is_adaptive_only_path(
        effective_method,
        user_weights,
        has_adaptive_page,
    )


def _apply_method_page_gates(context: JsonMap) -> None:
    dcf_method_available = context.get("dcf_method_available")
    context["show_dcf_before_calibration"] = (
        bool(context.get("has_dcf")) and dcf_method_available is not False
    )
    context["has_adjusted_nav_page"] = _has_adjusted_nav_page(context)
    _apply_adaptive_page_gates(context)
    context["has_ebitda_multiple_page"] = _has_ebitda_multiple_page(context)
    context["has_sde_page"] = _has_sde_page(context)
    context["has_revenue_multiple_page"] = _has_revenue_multiple_page(context)


def apply_method_page_context(
    context: JsonMap,
    *,
    valuation_results: object = None,
    financial_metrics: object = None,
    request_selected_method: object = None,
    request_user_weights: object = None,
    request_primary_method_key: object = None,
    request_country_code: object = None,
    request_metadata: MetadataMap | None = None,
) -> None:
    """Apply method-page gates, method result aliases, and sensitivity matrices."""
    _apply_selected_method_inputs(
        context,
        request_selected_method=request_selected_method,
        request_user_weights=request_user_weights,
        request_primary_method_key=request_primary_method_key,
        request_metadata=request_metadata,
    )

    context.update(
        build_method_result_context(
            valuation_results,
            country_code=(
                str(request_country_code).strip().upper()
                if request_country_code is not None
                else None
            ),
        )
    )
    apply_revenue_method_context(context)
    _apply_method_page_gates(context)
    _promote_revenue_growth_cagr(context, financial_metrics)
    _apply_multiple_sensitivity_matrices(context)
    refresh_adaptive_gates_on_context(context)
