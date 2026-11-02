"""Dedicated report-track context application helpers."""

from collections.abc import Callable, Mapping

from src.services.reports.context_merge import safe_merge
from src.services.reports.adaptive_report_gates import refresh_adaptive_gates_on_context
from src.services.reports.report_audience_context import apply_report_audience_context
from src.services.reports.liquidation_report_context import build_liquidation_context
from src.services.reports.method_page_context import apply_method_page_context
from src.services.reports.startup_report_context import build_startup_context
from src.services.reports.weighted_synthesis_context import build_weighted_synthesis_context
from src.services.reports.report_value_admission import admitted_point_or_band

_SYNTHESIS_CLEAR_FIELDS = (
    "synthesis_blended_value",
    "synthesis_valuation_low",
    "synthesis_valuation_high",
    "synthesis_justification",
    "synthesis_formula_display",
    "synthesis_badge_label",
    "synthesis_methodology_label",
    "synthesis_method_list",
    "synthesis_weight_summary",
    "synthesis_method_count_label",
)


JsonMap = dict[str, object]


def _suppress_sme_synthesis(context: JsonMap) -> None:
    context["has_dcf"] = False
    context["show_dcf_before_calibration"] = False
    context["has_weighted_synthesis"] = False
    for field in _SYNTHESIS_CLEAR_FIELDS:
        context[field] = None
    context["synthesis_contributions"] = []
    context["show_method_override"] = False
    context["show_fiscal_reference"] = False


def _apply_headline_band_if_missing(
    context: JsonMap,
    *,
    mid: object,
    low: object,
    high: object,
) -> None:
    # An observed zero/deficit is an existing conclusion, not a missing slot.
    if context.get("valuation") is not None or mid is None:
        return
    low_decimal, mid_decimal, high_decimal = admitted_point_or_band(low, mid, high)
    context.update(
        {
            "valuation": mid_decimal,
            "equity_value": mid_decimal,
            "valuation_low": low_decimal if low is not None else None,
            "equity_value_low": low_decimal if low is not None else None,
            "valuation_high": high_decimal if high is not None else None,
            "equity_value_high": high_decimal if high is not None else None,
        }
    )


def apply_startup_report_track(
    context: JsonMap,
    *,
    selected_method: str | None,
    valuation_results: object,
    startup_inputs: object,
    advisor_cta_url: str | None,
    locale: str,
) -> None:
    """Apply startup-track context, suppressing SME pages when active."""
    startup_context = build_startup_context(
        selected_method=selected_method,
        valuation_results=valuation_results,
        startup_inputs=startup_inputs,
        advisor_cta_url=advisor_cta_url,
        locale=locale,
    )
    context["is_startup_valuation_report"] = bool(startup_context)
    context["startup_report"] = startup_context
    if not startup_context:
        return

    context["show_saas_appendix"] = False
    _suppress_sme_synthesis(context)
    _apply_headline_band_if_missing(
        context,
        mid=startup_context.get("equity_value_mid"),
        low=startup_context.get("equity_value_low"),
        high=startup_context.get("equity_value_high"),
    )


def apply_liquidation_report_track(
    context: JsonMap,
    *,
    selected_method: str | None,
    valuation_results: object,
    locale: str,
    country_code: str | None = None,
) -> None:
    """Apply liquidation-track context, unless the startup track already won."""
    if context.get("is_startup_valuation_report"):
        context.setdefault("is_liquidation_report", False)
        context.setdefault("liquidation_report", None)
        return

    liquidation_context = build_liquidation_context(
        selected_method=selected_method,
        valuation_results=valuation_results,
        locale=locale,
        country_code=country_code,
    )
    context["is_liquidation_report"] = bool(liquidation_context)
    context["liquidation_report"] = liquidation_context
    if not liquidation_context:
        return

    context["show_saas_appendix"] = False
    context["show_saas_cap_table"] = False
    _suppress_sme_synthesis(context)
    context["show_owner_profiling_section"] = False
    context["show_sellability_section"] = False
    _apply_headline_band_if_missing(
        context,
        mid=liquidation_context.get("headline_equity"),
        low=liquidation_context.get("value_low"),
        high=liquidation_context.get("value_high"),
    )


def _metadata_value(metadata: Mapping[str, object] | None, key: str) -> object:
    return metadata.get(key) if isinstance(metadata, Mapping) else None


def _clean_method(value: object) -> str:
    return str(value).strip() if value is not None else ""


def apply_methodology_report_context(
    context: dict[str, object],
    *,
    response: object,
    request: object | None,
    locale: str,
    report_locale: str,
    translations: object,
    request_metadata: Mapping[str, object] | None,
    dcf_data: dict[str, object],
    sde_data: dict[str, object],
    sde_cross_check: dict[str, object],
    hybrid_data: dict[str, object],
    report_intelligence: dict[str, object],
    promote_upswitch_adaptive: Callable[[], None] | None = None,
    logger: object,
) -> None:
    """Apply DCF/SDE/hybrid pages and dedicated report tracks."""
    safe_merge(context, dcf_data, "dcf_data", logger=logger)
    safe_merge(context, sde_data, "sde_data", logger=logger)
    safe_merge(context, sde_cross_check, "sde_cross_check", logger=logger)
    safe_merge(context, hybrid_data, "hybrid_data", logger=logger)

    context["is_dcf_only_methodology"] = bool(context.get("has_dcf")) and not bool(
        context.get("is_hybrid")
    )
    safe_merge(context, report_intelligence, "report_intelligence", logger=logger)
    if promote_upswitch_adaptive:
        promote_upswitch_adaptive()

    valuation_results = getattr(response, "valuation_results", None)
    apply_method_page_context(
        context,
        valuation_results=valuation_results,
        financial_metrics=getattr(response, "financial_metrics", None),
        request_selected_method=(getattr(request, "selected_method", None) if request else None),
        request_user_weights=(getattr(request, "user_weights", None) if request else None),
        request_primary_method_key=(
            getattr(request, "primary_method_key", None) if request else None
        ),
        request_country_code=(getattr(request, "country_code", None) if request else None),
        request_metadata=request_metadata,
    )

    context.update(
        build_weighted_synthesis_context(
            getattr(response, "weighted_valuation", None),
            t=translations,
            locale=report_locale,
        )
    )

    selected_method = (
        _clean_method(context.get("selected_method"))
        or _clean_method(getattr(request, "selected_method", None) if request else None)
        or _clean_method(_metadata_value(request_metadata, "selected_method"))
    )
    startup_inputs = (
        getattr(request, "startup_inputs", None) if request else None
    ) or _metadata_value(request_metadata, "startup_inputs")
    advisor_cta_url = _metadata_value(request_metadata, "startup_advisor_cta_url")

    apply_startup_report_track(
        context,
        selected_method=selected_method,
        valuation_results=valuation_results,
        startup_inputs=startup_inputs,
        advisor_cta_url=str(advisor_cta_url) if advisor_cta_url else None,
        locale=report_locale,
    )
    apply_liquidation_report_track(
        context,
        selected_method=selected_method,
        valuation_results=valuation_results,
        locale=report_locale,
        country_code=(getattr(request, "country_code", None) if request else None),
    )
    refresh_adaptive_gates_on_context(context)
    apply_report_audience_context(
        context,
        request=request,
        response=response,
        request_metadata=request_metadata if isinstance(request_metadata, Mapping) else None,
        translations=translations,
    )
