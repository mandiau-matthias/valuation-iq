"""Omni-Calc context overrides — single-method report presentation.

When the user selects a specific valuation method (other than
``upswitch_adaptive``), this module rewrites the headline valuation
figures, methodology labels, and bridge data in the report context
so templates render the chosen method as the primary result.

Pure business logic — no FastAPI, no I/O.
"""

from __future__ import annotations

from typing import Dict, Optional, TypeAlias, cast

from src.domain.valuation_contract import (
    REVENUE_METHOD_KEYS,
    is_sde_method_key,
    method_key_matches,
    normalize_method_key,
)
from src.services.infrastructure.translations import (
    ReportTranslations,
    get_translations,
    normalize_report_locale,
)
from src.services.reports.adaptive_report_gates import refresh_adaptive_gates_on_context
from src.services.reports.helpers import (
    extract_valuation_results_map,
    has_weighted_synthesis_payload,
    swap_multiple_metric_suffix,
)
from src.services.reports.omni_method_labels import resolve_omni_method_labels
from src.services.reports.omni_sde_overrides import apply_sde_channel_override
from src.utils.decimal_helpers import safe_float
from src.utils.logging import get_logger

logger = get_logger(__name__)

_KNOWN_BRIDGE_OPS = frozenset({"−", "+", "＋"})
JsonMap: TypeAlias = Dict[str, object]


def _is_noop_override(
    normalized_method: str | None,
    valuation_data: JsonMap,
) -> bool:
    return (
        not normalized_method
        or normalized_method == "upswitch_adaptive"
        or has_weighted_synthesis_payload(valuation_data)
    )


def _method_details(method_data: JsonMap) -> JsonMap:
    details = method_data.get("details")
    return details if isinstance(details, dict) else {}


def _method_unavailable(method_data: object) -> bool:
    return (
        not isinstance(method_data, dict)
        or not method_data.get("available")
        or method_data.get("value") is None
    )


def _eligibility_payload(method_details: JsonMap) -> JsonMap | None:
    eligibility = method_details.get("eligibility")
    return eligibility if isinstance(eligibility, dict) else None


def _validation_flags(method_details: JsonMap) -> list[object]:
    flags = method_details.get("validation_flags")
    return flags if isinstance(flags, list) else []


def _apply_unavailable_method_context(
    context: JsonMap,
    *,
    selected_method: Optional[str],
    normalized_method: str,
    lookup_key: str,
    method_data: object,
) -> None:
    method_map = method_data if isinstance(method_data, dict) else {}
    method_details_dict = _method_details(method_map)
    eligibility = _eligibility_payload(method_details_dict)
    suggested_alt = eligibility.get("suggested_alternative_method") if eligibility else None
    validation_flags = _validation_flags(method_details_dict)
    unavailable_reason = method_map.get("unavailable_reason")
    method_label = method_map.get("label") or normalized_method

    logger.warning(
        "Selected method '%s' (resolved to '%s') is unavailable — surfacing "
        "fallback context to report layer. reason=%r, suggested=%r, "
        "validation_flags=%d",
        selected_method,
        lookup_key,
        unavailable_reason,
        suggested_alt,
        len(validation_flags),
    )

    # Clear positive override markers first, then SET the explicit
    # error markers — order matters: the clear-helper resets the
    # unavailable markers too, so we must populate them after.
    _clear_method_override_context(context)
    context["method_override_unavailable"] = True
    context["method_override_unavailable_method"] = normalized_method
    context["method_override_unavailable_label"] = method_label
    context["method_override_unavailable_reason"] = unavailable_reason or (
        f"De geselecteerde methode '{method_label}' kon niet worden berekend "
        "voor dit bedrijf; het rapport toont de standaard UpSwitch Adaptive "
        "blend als alternatief."
    )
    context["method_override_unavailable_suggested"] = suggested_alt
    context["method_override_unavailable_validation_flags"] = validation_flags


def _clear_unavailable_method_context(context: JsonMap) -> None:
    context["method_override_unavailable"] = False
    context["method_override_unavailable_method"] = None
    context["method_override_unavailable_label"] = None
    context["method_override_unavailable_reason"] = None
    context["method_override_unavailable_suggested"] = None
    context["method_override_unavailable_validation_flags"] = []


def _translations_for_override(context: JsonMap, locale: str) -> ReportTranslations:
    country_code = str(context.get("country_code") or "BE").strip().upper() or "BE"
    return cast(
        ReportTranslations,
        context.get("t")
        or get_translations(
            normalize_report_locale(locale),
            country_code=country_code,
        ),
    )


def _method_equity_range(method_details: JsonMap, override_val: float) -> tuple[float, float]:
    equity_low = method_details.get("equity_range_low")
    equity_high = method_details.get("equity_range_high")
    return (
        safe_float(equity_low) if equity_low is not None else round(override_val * 0.8, 2),
        safe_float(equity_high) if equity_high is not None else round(override_val * 1.2, 2),
    )


def _method_enterprise_value(method_details: JsonMap) -> Optional[float]:
    enterprise_value = method_details.get("enterprise_value")
    if enterprise_value is None:
        enterprise_value = method_details.get("enterprise_value_mid")
    return safe_float(enterprise_value) if enterprise_value is not None else None


def _apply_holding_sotp_report_context(
    context: JsonMap,
    *,
    method_details: JsonMap,
) -> None:
    """Activate the dedicated SOTP dossier and disable the generic bridge page.

    A holding SOTP reconciles entity-level EV and equity ranges, participation
    eliminations, entity tax and group bridge entries. It is not equivalent to
    the legacy single-company ``EV - net debt = equity`` formula, so the generic
    override/bridge presentation must never narrate it.
    """

    context["holding_sotp"] = dict(method_details)
    context["has_holding_sotp_page"] = method_details.get("available", True) is True
    context["is_holding_sotp_report"] = context["has_holding_sotp_page"]
    context["show_method_override"] = False
    context["method_override_selected_method"] = None
    context["method_override_label"] = None
    context["method_override_value"] = None
    context["show_ev_equity_bridge"] = False
    context["show_enterprise_to_equity_bridge"] = False
    context["has_net_debt_adjustment"] = False
    context["suppress_sde_cross_check"] = True
    context["show_sde_cross_check"] = False
    context["show_multiple_calibration_bridge"] = False
    context["show_sotp_trigger"] = False
    context["show_limited_scope_advisory_panel"] = False


def _existing_bridge_inputs(
    context: JsonMap,
) -> tuple[Optional[float], Optional[float], object]:
    existing_net_debt = context.get("net_debt")
    existing_bridge_amount = context.get("bridge_net_debt_amount")
    return (
        safe_float(existing_net_debt) if existing_net_debt is not None else None,
        safe_float(existing_bridge_amount) if existing_bridge_amount is not None else None,
        context.get("bridge_net_debt_operator"),
    )


def _apply_headline_override(
    context: JsonMap,
    *,
    normalized_method: str,
    canonical_methodology: str,
    display_label: str,
    override_val: float,
    equity_low: float,
    equity_high: float,
) -> None:
    context["upswitch_adaptive_equity_value"] = context.get(
        "equity_value", context.get("valuation", 0)
    )
    context["equity_value_mid"] = override_val
    context["equity_value"] = override_val
    context["equity_value_low"] = equity_low
    context["equity_value_high"] = equity_high
    context["valuation_low"] = equity_low
    context["valuation_high"] = equity_high
    context["valuation_methodology"] = canonical_methodology
    context["valuation_methodology_display"] = display_label
    context["methodology"] = normalized_method
    context["recommended_methodology"] = canonical_methodology
    context["primary_method_key"] = normalized_method
    context["is_nav_methodology"] = normalized_method == "adjusted_nav"
    context["primary_method_label"] = display_label


def _apply_multiple_context(
    context: JsonMap,
    *,
    method_data: JsonMap,
    method_details: JsonMap,
) -> None:
    if method_data.get("multiple_used") is not None:
        context["applied_multiple"] = safe_float(method_data["multiple_used"])
        context["base_multiple"] = safe_float(method_data["multiple_used"])
    if (
        method_details.get("p25_multiple") is not None
        and method_details.get("p75_multiple") is not None
    ):
        context["multiple_low"] = safe_float(method_details["p25_multiple"])
        context["multiple_high"] = safe_float(method_details["p75_multiple"])


def _apply_dcf_flag_context(
    context: JsonMap,
    *,
    normalized_method: str,
    method_data: JsonMap,
) -> None:
    if method_data.get("wacc") is not None:
        context["dcf_wacc"] = safe_float(method_data["wacc"])
        context["has_dcf"] = True
    else:
        context["has_dcf"] = method_key_matches(normalized_method, "dcf")


def _apply_method_override_visibility(
    context: JsonMap,
    *,
    normalized_method: str,
    display_label: str,
    override_val: float,
) -> None:
    if bool(context.get("method_override_visibility_locked")):
        context["show_method_override"] = bool(context.get("show_method_override"))
    else:
        context["show_method_override"] = True
    context["method_override_selected_method"] = normalized_method
    context["method_override_label"] = display_label
    context["method_override_value"] = override_val


def apply_omni_calc_overrides(
    context: JsonMap,
    valuation_data: JsonMap,
    selected_method: Optional[str],
    locale: str = "nl",
) -> JsonMap:
    """Apply single-method overrides to *context* and return it.

    No-op if *selected_method* is ``None``, ``"upswitch_adaptive"``, or when
    the payload already carries weighted-synthesis data.
    """
    normalized_method = normalize_method_key(selected_method)
    if _is_noop_override(normalized_method, valuation_data):
        _clear_method_override_context(context)
        refresh_adaptive_gates_on_context(context)
        return context

    vr = extract_valuation_results_map(valuation_data)
    lookup_key = normalized_method
    method_data = vr.get(lookup_key)

    if _method_unavailable(method_data):
        # ── Selected-method-unavailable handler ─────────────────────────
        # Previously this branch silently cleared the override and let
        # the report render the adaptive default — the user got a number
        # for a method they did not pick. We now expose the failure in a
        # structured way so the report can render a banner / fallback
        # disclosure instead of pretending nothing happened.
        _apply_unavailable_method_context(
            context,
            selected_method=selected_method,
            normalized_method=normalized_method,
            lookup_key=lookup_key,
            method_data=method_data,
        )
        refresh_adaptive_gates_on_context(context)
        return context

    # Successful override path — make sure any prior "unavailable"
    # markers on the context (e.g. from a previous render) are cleared
    # so the report doesn't show a stale error banner alongside a
    # successful headline.
    _clear_unavailable_method_context(context)
    method_details = _method_details(method_data)
    method_label = method_data.get("label", normalized_method)
    omni_labels = resolve_omni_method_labels(
        selected_method=normalized_method,
        locale=locale,
        method_label=method_label,
    )
    canonical_methodology = omni_labels.canonical_methodology
    display_label = omni_labels.display_label
    _raw_val = safe_float(method_data.get("value"))
    override_val: float = _raw_val if _raw_val is not None else 0.0

    equity_low, equity_high = _method_equity_range(method_details, override_val)
    enterprise_value = _method_enterprise_value(method_details)
    existing_net_debt, existing_bridge_amount, existing_bridge_operator = _existing_bridge_inputs(
        context
    )

    # --- headline figures ---
    _apply_headline_override(
        context,
        normalized_method=normalized_method,
        canonical_methodology=canonical_methodology,
        display_label=display_label,
        override_val=override_val,
        equity_low=equity_low,
        equity_high=equity_high,
    )

    _apply_multiple_context(context, method_data=method_data, method_details=method_details)

    # --- EV → equity bridge ---
    _apply_bridge(
        context,
        enterprise_value,
        override_val,
        equity_low,
        equity_high,
        existing_net_debt,
        existing_bridge_amount,
        existing_bridge_operator,
    )

    # --- WACC / DCF flag ---
    _apply_dcf_flag_context(context, normalized_method=normalized_method, method_data=method_data)

    # --- method-specific overrides ---
    _apply_method_specifics(
        context,
        normalized_method,
        method_details,
        valuation_data,
        enterprise_value,
        override_val,
        _translations_for_override(context, locale),
        locale=locale,
    )

    if method_key_matches(normalized_method, "dcf"):
        context["has_dcf"] = True

    if method_key_matches(normalized_method, "holding_sotp"):
        _apply_holding_sotp_report_context(context, method_details=method_details)
    else:
        _apply_method_override_visibility(
            context,
            normalized_method=normalized_method,
            display_label=display_label,
            override_val=override_val,
        )

    logger.info(
        "Omni-Calc: overriding report context with selected method",
        extra={"selected_method": normalized_method, "override_val": override_val},
    )

    refresh_adaptive_gates_on_context(context)
    return context


# ── private helpers ──────────────────────────────────────────────────


def _clear_method_override_context(context: JsonMap) -> None:
    """Clear explicit single-method override markers when no override applies.

    Also resets the unavailable-method markers so a successful re-render
    after a failed one (or a no-override path) doesn't leak stale error
    state into the new report context.
    """
    context["show_method_override"] = False
    context["method_override_selected_method"] = None
    context["method_override_label"] = None
    context["method_override_value"] = None
    context["is_asset_methodology"] = False
    context["method_override_unavailable"] = False
    context["method_override_unavailable_method"] = None
    context["method_override_unavailable_label"] = None
    context["method_override_unavailable_reason"] = None
    context["method_override_unavailable_suggested"] = None
    context["method_override_unavailable_validation_flags"] = []


def _apply_bridge(
    context: JsonMap,
    enterprise_value: Optional[float],
    override_val: float,
    equity_low: float,
    equity_high: float,
    existing_net_debt: Optional[float],
    existing_bridge_amount: Optional[float],
    existing_bridge_operator: object,
) -> None:
    if enterprise_value is not None:
        bridge_delta = enterprise_value - override_val
        net_debt = existing_net_debt if existing_net_debt is not None else bridge_delta
        bridge_amount = (
            existing_bridge_amount if existing_bridge_amount is not None else abs(net_debt)
        )
        bridge_operator = (
            existing_bridge_operator
            if existing_bridge_operator in _KNOWN_BRIDGE_OPS
            else ("−" if net_debt > 0 else "+")
        )
        has_net_debt_adjustment = (
            bool(context.get("has_net_debt_adjustment")) or abs(net_debt) > 0.01
        )
        show_bridge = (
            has_net_debt_adjustment
            or bool(context.get("has_tax_latencies"))
            or bool(context.get("has_balance_sheet_adjustments"))
            or abs(bridge_delta) > 0.01
        )
        context["valuation"] = enterprise_value
        context["enterprise_value_mid"] = enterprise_value
        context["enterprise_value_low"] = round(equity_low + bridge_delta, 2)
        context["enterprise_value_high"] = round(equity_high + bridge_delta, 2)
        context["valuation_low"] = context["enterprise_value_low"]
        context["valuation_high"] = context["enterprise_value_high"]
        context["show_ev_equity_bridge"] = show_bridge
        context["has_net_debt_adjustment"] = has_net_debt_adjustment
        context["bridge_net_debt_operator"] = bridge_operator
        context["bridge_net_debt_amount"] = round(bridge_amount, 2)
        context["net_debt"] = round(net_debt, 2)
    else:
        context["valuation"] = override_val
        context["enterprise_value_mid"] = override_val
        context["enterprise_value_low"] = equity_low
        context["enterprise_value_high"] = equity_high
        context["show_ev_equity_bridge"] = False
        context["has_net_debt_adjustment"] = False
        context["bridge_net_debt_amount"] = 0.0
        context["net_debt"] = 0.0


def _apply_method_specifics(
    context: JsonMap,
    selected_method: str,
    method_details: JsonMap,
    valuation_data: JsonMap,
    enterprise_value: Optional[float],
    override_val: float,
    _t: ReportTranslations,
    *,
    locale: str = "nl",
) -> None:
    context["is_asset_methodology"] = False
    context["is_asset_anchored_methodology"] = False
    if is_sde_method_key(selected_method):
        # Delegate to the SDE channel — single source of truth for every
        # SDE-related context field. No EBITDA cascade leak after this point.
        _apply_sde_channel(
            context,
            method_details=method_details,
            valuation_data=valuation_data,
            enterprise_value=enterprise_value,
            override_val=override_val,
            locale=locale,
        )
    else:
        context["has_sde"] = False
        context["is_sde_methodology"] = False
        context["sde_value"] = None
        context["sde_multiple"] = None
        context["sde_owner_salary"] = None
        context["sde_components"] = []

    if selected_method in REVENUE_METHOD_KEYS:
        _apply_revenue_overrides(context, method_details, valuation_data, _t)
    elif method_key_matches(selected_method, "ebitda_multiple"):
        context["multiple_metric_type"] = "EBITDA"
        ebitda_basis = context.get("sustainable_ebitda")
        if ebitda_basis is not None:
            context["valuation_basis_value"] = safe_float(ebitda_basis)
    elif method_key_matches(selected_method, "arr_multiple"):
        _apply_arr_overrides(context, method_details, _t)
    elif method_key_matches(selected_method, "dcf"):
        _apply_dcf_overrides(context, enterprise_value, override_val, _t)
    elif method_key_matches(selected_method, "adjusted_nav", "fiscal_4x"):
        _apply_non_multiple_overrides(context, selected_method, method_details, _t)


def _apply_revenue_overrides(
    context: JsonMap,
    method_details: JsonMap,
    valuation_data: JsonMap,
    _t: ReportTranslations,
) -> None:
    context["multiple_metric_type"] = "REVENUE"
    revenue_basis = context.get("revenue")
    if revenue_basis is None:
        revenue_basis = method_details.get("revenue")
    if revenue_basis is None:
        revenue_basis = valuation_data.get("revenue")
    if revenue_basis is None and isinstance(valuation_data.get("details"), dict):
        revenue_basis = valuation_data["details"].get("revenue")
    if revenue_basis is None:
        vr_nested = valuation_data.get("valuation_result")
        if isinstance(vr_nested, dict):
            revenue_basis = vr_nested.get("revenue")
            if revenue_basis is None and isinstance(vr_nested.get("details"), dict):
                revenue_basis = vr_nested["details"].get("revenue")
    if revenue_basis is not None:
        context["valuation_basis_value"] = safe_float(revenue_basis)
    context["multiple_display_label"] = swap_multiple_metric_suffix(
        context.get("multiple_display_label"),
        _t.report_multiple_suffix_ev_revenue,
    )
    context["benchmark_multiple_label"] = swap_multiple_metric_suffix(
        context.get("benchmark_multiple_label"),
        _t.report_multiple_suffix_ev_revenue,
    )


def _apply_arr_overrides(
    context: JsonMap,
    method_details: JsonMap,
    _t: ReportTranslations,
) -> None:
    context["multiple_metric_type"] = "ARR"
    context["supports_metric_to_ev_bridge"] = False
    arr_basis = method_details.get("arr") or method_details.get("annual_recurring_revenue")
    if arr_basis is not None:
        context["valuation_basis_value"] = safe_float(arr_basis)
    arr_mult = method_details.get("arr_multiple")
    if arr_mult is not None:
        context["applied_multiple"] = safe_float(arr_mult)
        context["base_multiple"] = safe_float(arr_mult)


def _apply_dcf_overrides(
    context: JsonMap,
    enterprise_value: Optional[float],
    override_val: float,
    _t: ReportTranslations,
) -> None:
    context["multiple_metric_type"] = None
    context["multiple_display_label"] = None
    context["benchmark_multiple_label"] = None
    context["benchmark_multiple_mid"] = None
    context["benchmark_sample_size"] = None
    context["has_industry_benchmarks"] = False
    context["applied_multiple"] = None
    context["base_multiple"] = None
    context["multiple_low"] = None
    context["multiple_high"] = None
    context["methodology_statement"] = _t.omni_methodology_statement_dcf
    context["is_dcf_only_methodology"] = True
    context["is_asset_methodology"] = False
    context["is_hybrid"] = False
    context["supports_metric_to_ev_bridge"] = False
    if not context.get("show_dcf_before_calibration"):
        context["show_dcf_before_calibration"] = True
    if enterprise_value is not None:
        dcf_bridge = enterprise_value - override_val
        if abs(dcf_bridge) < 0.01:
            context["show_ev_equity_bridge"] = False
            context["has_net_debt_adjustment"] = False
            context["bridge_net_debt_amount"] = 0.0
            context["net_debt"] = 0.0
        else:
            context["net_debt"] = round(dcf_bridge, 2)
            context["bridge_net_debt_amount"] = round(abs(dcf_bridge), 2)
            context["bridge_net_debt_operator"] = "−" if dcf_bridge > 0 else "+"
            context["has_net_debt_adjustment"] = True
            context["show_ev_equity_bridge"] = True


def _clear_multiple_benchmark_context(context: JsonMap) -> None:
    context["multiple_metric_type"] = None
    context["multiple_display_label"] = None
    context["benchmark_multiple_label"] = None
    context["benchmark_multiple_mid"] = None
    context["benchmark_sample_size"] = None
    context["has_industry_benchmarks"] = False
    context["applied_multiple"] = None
    context["base_multiple"] = None
    context["multiple_low"] = None
    context["multiple_high"] = None
    context["supports_metric_to_ev_bridge"] = False


def _nav_bridge_values(nav_d: JsonMap) -> tuple[float, float, float, float, float]:
    book_assets = safe_float(nav_d.get("total_assets_book"))
    book_liab = safe_float(nav_d.get("total_liabilities_book"))
    book_equity = round(book_assets - book_liab, 2)
    nav_before = safe_float(nav_d.get("net_asset_value_before_deductions"))
    gross_corrections = round(nav_before - book_equity, 2)
    tax_lat = safe_float(nav_d.get("tax_latency_deduction"))
    off_bal = safe_float(nav_d.get("off_balance_deduction"))
    corrected_nav = safe_float(nav_d.get("net_asset_value"))
    return book_equity, gross_corrections, tax_lat, off_bal, corrected_nav


def _nav_adjustment_labels(_t: ReportTranslations) -> JsonMap:
    return {
        "nav_real_estate_adjustment": _t.nav_label_real_estate,
        "nav_hidden_reserves": _t.nav_label_hidden_reserves,
        "nav_inventory_adjustment": _t.nav_label_inventory,
        "nav_receivables_adjustment": _t.nav_label_receivables,
        "nav_goodwill_writeoff": _t.nav_label_goodwill_writeoff,
        "nav_other_revaluations": _t.nav_label_other_revaluations,
        "nav_off_balance_items": _t.nav_label_off_balance,
        "real_estate_revaluation": _t.nav_label_real_estate_appraisal,
        "equipment_revaluation": _t.nav_label_equipment_revaluation,
    }


def _nav_revaluation_payloads(nav_d: JsonMap) -> tuple[JsonMap | None, JsonMap | None]:
    re_reval = nav_d.get("real_estate_revaluation")
    eq_reval = nav_d.get("equipment_revaluation")
    return (
        re_reval if isinstance(re_reval, dict) else None,
        eq_reval if isinstance(eq_reval, dict) else None,
    )


def _nav_manual_adjustments(
    nav_d: JsonMap,
    *,
    re_reval: JsonMap | None,
    eq_reval: JsonMap | None,
) -> JsonMap:
    raw_adjustments = nav_d.get("manual_nav_adjustments", {})
    adjustments = dict(raw_adjustments) if isinstance(raw_adjustments, dict) else {}

    if re_reval is not None:
        re_meerwaarde = safe_float(re_reval.get("meerwaarde"))
        if re_meerwaarde:
            if adjustments.get("nav_real_estate_adjustment"):
                adjustments.pop("nav_real_estate_adjustment", None)
            adjustments["real_estate_revaluation"] = re_meerwaarde
    if eq_reval is not None:
        eq_meerwaarde = safe_float(eq_reval.get("meerwaarde"))
        if eq_meerwaarde:
            adjustments["equipment_revaluation"] = eq_meerwaarde

    return adjustments


def _apply_adjusted_nav_bridge_context(
    context: JsonMap,
    nav_d: JsonMap,
    _t: ReportTranslations,
) -> tuple[float, JsonMap | None, JsonMap | None]:
    book_equity, gross_corrections, tax_lat, off_bal, corrected_nav = _nav_bridge_values(nav_d)
    re_reval, eq_reval = _nav_revaluation_payloads(nav_d)

    context["methodology_statement"] = _t.omni_methodology_statement_adjusted_nav
    context["show_nav_bridge"] = True
    context["nav_book_equity"] = book_equity
    context["nav_gross_corrections"] = gross_corrections
    context["nav_tax_latency_deduction"] = tax_lat
    context["nav_off_balance_deduction"] = off_bal
    context["nav_corrected_value"] = corrected_nav
    context["nav_manual_adjustments"] = _nav_manual_adjustments(
        nav_d,
        re_reval=re_reval,
        eq_reval=eq_reval,
    )
    context["nav_adjustment_labels"] = _nav_adjustment_labels(_t)
    return tax_lat, re_reval, eq_reval


def _nav_audit_trail(
    nav_d: JsonMap,
    *,
    tax_lat: float,
    re_reval: JsonMap | None,
    eq_reval: JsonMap | None,
) -> tuple[JsonMap, bool]:
    audit_trail: JsonMap = {}
    has_content = False
    dtb = nav_d.get("deferred_tax_breakdown")
    if isinstance(dtb, list) and dtb:
        audit_trail["deferred_tax_breakdown"] = dtb
        has_content = True
    sme = nav_d.get("sme_eligibility")
    if isinstance(sme, dict):
        audit_trail["sme_eligibility"] = sme
        has_content = True
    if re_reval is not None:
        audit_trail["real_estate_revaluation"] = re_reval
        has_content = True
    if eq_reval is not None:
        audit_trail["equipment_revaluation"] = eq_reval
        has_content = True
    eff_pct = safe_float(nav_d.get("effective_tax_latency_pct"))
    if eff_pct:
        audit_trail["effective_tax_latency_pct"] = eff_pct
    if tax_lat:
        audit_trail["tax_latency_deduction"] = tax_lat
    return audit_trail, has_content


def _apply_nav_audit_trail_context(
    context: JsonMap,
    nav_d: JsonMap,
    *,
    tax_lat: float,
    re_reval: JsonMap | None,
    eq_reval: JsonMap | None,
) -> None:
    audit_trail, has_content = _nav_audit_trail(
        nav_d,
        tax_lat=tax_lat,
        re_reval=re_reval,
        eq_reval=eq_reval,
    )
    context["nav_audit_trail"] = audit_trail if has_content else {}
    context["has_nav_audit_trail"] = has_content


def _apply_nav_deal_structure_context(context: JsonMap, nav_d: JsonMap) -> None:
    deal_struct = nav_d.get("deal_structure_comparison")
    if isinstance(deal_struct, dict) and (
        deal_struct.get("share_deal") or deal_struct.get("asset_deal")
    ):
        context["nav_deal_structure"] = deal_struct
        context["has_nav_deal_structure"] = True
        return
    context["has_nav_deal_structure"] = False


def _apply_adjusted_nav_context(
    context: JsonMap,
    method_details: JsonMap,
    _t: ReportTranslations,
) -> None:
    tax_lat, re_reval, eq_reval = _apply_adjusted_nav_bridge_context(
        context,
        method_details,
        _t,
    )
    _apply_nav_audit_trail_context(
        context,
        method_details,
        tax_lat=tax_lat,
        re_reval=re_reval,
        eq_reval=eq_reval,
    )
    _apply_nav_deal_structure_context(context, method_details)


def _apply_non_multiple_overrides(
    context: JsonMap,
    selected_method: str,
    method_details: JsonMap,
    _t: ReportTranslations,
) -> None:
    _clear_multiple_benchmark_context(context)
    context["is_asset_methodology"] = True
    context["is_asset_anchored_methodology"] = True
    if selected_method == "adjusted_nav":
        _apply_adjusted_nav_context(context, method_details, _t)
    else:
        context["methodology_statement"] = _t.omni_methodology_statement_fiscal_4x


def _apply_sde_channel(
    context: JsonMap,
    *,
    method_details: JsonMap,
    valuation_data: JsonMap,
    enterprise_value: Optional[float],
    override_val: float,
    locale: str = "nl",
) -> None:
    """Compatibility wrapper for tests and older internal imports."""
    apply_sde_channel_override(
        context,
        method_details=method_details,
        valuation_data=valuation_data,
        enterprise_value=enterprise_value,
        override_val=override_val,
        locale=locale,
    )
