"""Adaptive and SDE presentation helpers for simplified report context."""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, Optional, Tuple, TypeAlias

from src.api.schemas import ValuationRequest, ValuationResponse
from src.domain.valuation_contract import is_sde_method_key, methodology_indicates_sde
from src.services.infrastructure.simplified_report_formatting import safe_decimal
from src.services.infrastructure.simplified_report_request_context import get_request_metadata
from src.services.infrastructure.translations import get_translations, normalize_report_locale
from src.services.reports.adaptive_report_gates import (
    coalesce_user_weights_for_gates,
    compute_has_upswitch_adaptive_page,
    compute_is_adaptive_only_path,
    resolve_effective_selected_method_for_report_gates,
)

JsonObject: TypeAlias = Dict[str, object]
TemplateContext: TypeAlias = Dict[str, object]


def coerce_adaptive_result_dict(adaptive: object) -> Optional[JsonObject]:
    """Normalize omni-calc ``upswitch_adaptive`` entry to a plain dict."""
    if adaptive is None:
        return None
    model_dump = getattr(adaptive, "model_dump", None)
    if callable(model_dump):
        try:
            adaptive = model_dump()
        except (TypeError, ValueError):
            return None
    if not isinstance(adaptive, dict):
        return None
    return {str(key): value for key, value in adaptive.items()}


def extract_upswitch_adaptive_value_for_gate(response: ValuationResponse) -> object:
    """Headline adaptive value for ``compute_has_upswitch_adaptive_page``."""
    vr = getattr(response, "valuation_results", None)
    if not vr or not hasattr(vr, "get"):
        return None
    adaptive = coerce_adaptive_result_dict(vr.get("upswitch_adaptive"))
    if not adaptive:
        return None
    if not adaptive.get("available", False):
        return None
    return adaptive.get("value")


def infer_sde_gate_hints(
    request: Optional[ValuationRequest],
    response: ValuationResponse,
) -> Tuple[str, str]:
    """``(multiple_metric_type, primary_method_key)`` when response suggests SDE presentation."""
    if request:
        if is_sde_method_key(getattr(request, "selected_method", None)):
            return ("SDE", "sde_multiple")
        if is_sde_method_key(getattr(request, "primary_method_key", None)):
            return (
                "SDE",
                str(getattr(request, "primary_method_key")).strip() or "sde_multiple",
            )
    mv = getattr(response, "multiples_valuation", None)
    if mv and methodology_indicates_sde(getattr(mv, "primary_method", None)):
        return ("SDE", "sde_multiple")
    if methodology_indicates_sde(getattr(response, "methodology", None)):
        return ("SDE", "sde_multiple")
    return ("", "")


def build_adaptive_gate_context(
    request: Optional[ValuationRequest],
    response: ValuationResponse,
) -> TemplateContext:
    """Mirror Titan report-context keys used by adaptive gate resolution."""
    md = get_request_metadata(request) or {}
    sel_raw = ""
    if request and getattr(request, "selected_method", None):
        sel_raw = str(request.selected_method).strip()
    elif md.get("selected_method"):
        sel_raw = str(md.get("selected_method")).strip()

    mmt = str(md.get("multiple_metric_type") or "").strip()
    pk = str(md.get("primary_method_key") or "").strip()
    if str(mmt).upper() != "SDE" or not pk:
        mmt_i, pk_i = infer_sde_gate_hints(request, response)
        if str(mmt).upper() != "SDE" and mmt_i:
            mmt = mmt_i
        if not pk and pk_i:
            pk = pk_i
        elif str(mmt).upper() == "SDE" and not pk:
            pk = pk_i or "sde_multiple"

    return {
        "show_method_override": bool(md.get("show_method_override")),
        "method_override_selected_method": md.get("method_override_selected_method"),
        "selected_method": sel_raw,
        "primary_method_key": pk,
        "multiple_metric_type": mmt,
    }


def resolve_presentation_metric_type(
    response: ValuationResponse,
    request: Optional[ValuationRequest],
    *,
    base_metric_type: str,
) -> str:
    """Return ``EBITDA``, ``REVENUE``, or ``SDE`` for simplified report math and copy."""
    gate_ctx = build_adaptive_gate_context(request, response)
    eff = resolve_effective_selected_method_for_report_gates(gate_ctx)
    if is_sde_method_key(eff) or str(gate_ctx.get("multiple_metric_type") or "").upper() == "SDE":
        return "SDE"
    return base_metric_type


def sde_method_row(response: ValuationResponse) -> Optional[JsonObject]:
    """Return the omni SDE result row as a plain dict when present."""
    vr = getattr(response, "valuation_results", None)
    if not isinstance(vr, dict):
        return None
    row = vr.get("sde_multiple")
    return {str(key): value for key, value in row.items()} if isinstance(row, dict) else None


def extract_sde_basis(
    response: ValuationResponse,
    request: Optional[ValuationRequest],
) -> Decimal:
    """SDE currency basis from omni ``valuation_results`` (mirrors Titan SDE channel)."""
    _ = request
    row = sde_method_row(response)
    if row:
        details = row.get("details") if isinstance(row.get("details"), dict) else {}
        for key in ("sde", "sde_value", "sustainable_sde", "sellers_discretionary_earnings"):
            raw = details.get(key)
            if raw is not None:
                d = safe_decimal(raw)
                if d > 0:
                    return d
        ev = details.get("enterprise_value")
        mu = row.get("multiple_used")
        if mu is None:
            mu = details.get("sde_applied_multiple") or details.get("multiple_used")
        if ev is not None and mu is not None:
            try:
                evf = float(ev)
                mf = float(mu)
                if evf > 0 and mf > 0:
                    return Decimal(str(round(evf / mf, 2)))
            except (TypeError, ValueError, ZeroDivisionError):
                pass
    return Decimal("0")


def user_weights_for_adaptive_gates(request: Optional[ValuationRequest]) -> object:
    """Coerce user weights into the shape expected by adaptive report gates."""
    if not request:
        return None
    return coalesce_user_weights_for_gates(getattr(request, "user_weights", None))


def _get_request_locale(request: Optional[ValuationRequest]) -> str:
    locale = None
    if request is not None:
        locale = getattr(request, "locale", None) or getattr(request, "language", None)
    return locale if locale in {"nl", "en", "fr"} else "nl"


def resolve_methodology_description(
    *,
    metric_type: str,
    request: Optional[ValuationRequest],
    response: ValuationResponse,
) -> Tuple[str, bool, bool]:
    """Return ``(description, has_upswitch_adaptive_page, is_adaptive_only_path)``."""
    adaptive_val = extract_upswitch_adaptive_value_for_gate(response)
    gate_ctx = build_adaptive_gate_context(request, response)
    eff_sm = resolve_effective_selected_method_for_report_gates(gate_ctx)
    uw = user_weights_for_adaptive_gates(request)
    has_adaptive_page = compute_has_upswitch_adaptive_page(eff_sm, uw, adaptive_val)
    is_adaptive_only = compute_is_adaptive_only_path(eff_sm, uw, has_adaptive_page)

    country_code = (getattr(request, "country_code", None) or "BE") if request else "BE"
    country_code = str(country_code).strip().upper() or "BE"
    report_loc = normalize_report_locale(_get_request_locale(request))
    t = get_translations(report_loc, country_code=country_code)

    if is_adaptive_only:
        return (t.exec_methodology_adaptive, has_adaptive_page, is_adaptive_only)

    if metric_type == "SDE":
        return (t.exec_methodology_sde, has_adaptive_page, is_adaptive_only)
    if metric_type == "REVENUE":
        return ("marktbenadering (EV/Revenue multiple)", has_adaptive_page, is_adaptive_only)
    return ("marktbenadering (EV/EBITDA multiple)", has_adaptive_page, is_adaptive_only)
