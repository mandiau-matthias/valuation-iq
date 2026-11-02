"""SDE methodology context for owner-operated micro-SME reports."""

from decimal import Decimal, InvalidOperation
from logging import Logger
from typing import Dict, Optional, Protocol, Tuple, TypeAlias

from src.domain.valuation_contract import (
    is_sde_method_key,
    methodology_indicates_sde,
    resolve_effective_method_key,
)
from src.services.reports.protocol_adapter import DictWrapper, _attr, _unwrap
from src.utils.decimal_helpers import safe_decimal_or_zero, safe_float

_OWNER_CATEGORIES = {"owner", "owner_compensation_adjustment", "owner_compensation"}
_OWNER_NAME_TOKENS = {"owner", "eigenaar", "salary", "salaris", "compensation"}
JsonMap: TypeAlias = Dict[str, object]


class SdeTranslations(Protocol):
    dcf_row_ebitda: str
    sde_component_owner_salary_label: str
    sde_component_total_label: str


def _warn(logger: Optional[Logger], message: str, exc: Exception) -> None:
    if logger is not None:
        logger.warning(message, exc_info=exc)


def _unwrap_dict_wrapper(value: object) -> object:
    return _unwrap(value) if isinstance(value, DictWrapper) else value


def _to_decimal(value: object) -> Decimal:
    parsed = safe_decimal_or_zero(value)
    if isinstance(parsed, Decimal):
        return parsed
    try:
        return Decimal(str(parsed))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _to_optional_int(value: object) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _find_recommended_methodology(response: object, logger: Optional[Logger] = None) -> object:
    try:
        transparency = _attr(response, "transparency", None)
        steps = _attr(transparency, "calculation_steps", None)
        steps_d = _unwrap_dict_wrapper(steps)
        if not isinstance(steps_d, dict) or "multiples" not in steps_d:
            return None

        for step in steps_d.get("multiples") or []:
            step_d = _unwrap_dict_wrapper(step)
            if not isinstance(step_d, dict) or "result" not in step_d:
                continue
            result_d = _unwrap_dict_wrapper(step_d.get("result", {}))
            if isinstance(result_d, dict):
                recommended = result_d.get("recommended_methodology")
                if recommended:
                    return recommended
    except (TypeError, KeyError, AttributeError) as exc:
        _warn(logger, "SDE methodology detection failed", exc)
    return None


def _owner_salary_from_normalization(
    normalization_result: JsonMap,
    logger: Optional[Logger] = None,
) -> Decimal:
    owner_salary = Decimal("0")
    try:
        for adjustment in _normalization_adjustments(normalization_result):
            if _is_owner_salary_adjustment(adjustment):
                owner_salary += _owner_salary_adjustment_amount(adjustment)
    except (TypeError, KeyError, AttributeError) as exc:
        _warn(logger, "SDE owner salary extraction failed", exc)
    return owner_salary


def _normalization_adjustments(normalization_result: JsonMap) -> list[JsonMap]:
    adjustments = (
        normalization_result.get("adjustments")
        or normalization_result.get("ebitda_adjustments")
        or []
    )
    rows: list[JsonMap] = []
    for adjustment in adjustments:
        adjustment_d = _unwrap_dict_wrapper(adjustment)
        if isinstance(adjustment_d, dict):
            rows.append(adjustment_d)
    return rows


def _is_owner_salary_adjustment(adjustment: JsonMap) -> bool:
    category = str(adjustment.get("category") or "").lower()
    name = str(adjustment.get("name") or adjustment.get("field") or "").lower()
    return category in _OWNER_CATEGORIES or any(token in name for token in _OWNER_NAME_TOKENS)


def _owner_salary_adjustment_amount(adjustment: JsonMap) -> Decimal:
    return safe_decimal_or_zero(adjustment.get("amount") or adjustment.get("adjusted_value") or 0)


def _owner_salary_from_request(request: object) -> Decimal:
    raw_addback = _attr(request, "owner_salary_addback", None)
    if raw_addback and safe_float(raw_addback) > 0:
        return _to_decimal(raw_addback)
    return Decimal("0")


def _sde_multiple_from_transparency(response: object) -> object:
    try:
        transparency = _attr(response, "transparency", None)
        sub_steps = _attr(transparency, "sub_steps", None)
        if isinstance(sub_steps, list):
            for sub_step in sub_steps:
                sub_step_d = _unwrap_dict_wrapper(sub_step)
                if isinstance(sub_step_d, dict) and sub_step_d.get("step_number") == 2.7:
                    result_d = _unwrap_dict_wrapper(sub_step_d.get("result") or {})
                    return result_d.get("sde_multiple") if isinstance(result_d, dict) else None
    except (TypeError, KeyError, AttributeError):
        return None
    return None


def _fallback_sde_multiple(response: object) -> float:
    revenue_value = safe_float(_attr(response, "revenue", 0) or 0)
    if revenue_value < 500000:
        return 1.5
    if revenue_value < 2000000:
        return 2.0
    return 2.5


def _cross_check_fallback_multiple(revenue: object) -> Decimal:
    revenue_value = safe_float(revenue or 0)
    if revenue_value < 500000:
        return Decimal("1.5")
    if revenue_value < 2000000:
        return Decimal("2.0")
    return Decimal("2.5")


def _engine_sde_legs(response: object) -> Tuple[Decimal, Decimal, Decimal, Decimal]:
    """Read the engine's REAL SDE leg from ``transparency.calculation_steps``.

    Returns ``(sde, sde_multiple, sde_valuation, sde_weight)``. The first three
    come from Step 2.7 (the SDE calculation: keys ``sde`` / ``sde_multiple`` /
    ``sde_valuation``); ``sde_weight`` is the weight the Step-11 synthesis blended
    the SDE leg in at (0 when SDE was not weighted into the headline).

    This deliberately reads ``calculation_steps`` — the SAME source the report's
    ``step_data`` is built from — instead of the legacy ``sub_steps`` path, which
    is not populated on the report path and silently forced the cross-check onto
    revenue-based fallbacks that contradicted the blended headline.
    """
    sde = sde_multiple = sde_valuation = sde_weight = Decimal("0")
    try:
        transparency = _attr(response, "transparency", None)
        steps = _unwrap_dict_wrapper(_attr(transparency, "calculation_steps", None))
        step_list = steps.get("multiples") if isinstance(steps, dict) else steps
        # Live CalculationStep objects retain display text but omit economic
        # key_outputs. Prefer executed records on both live and restored paths;
        # waiting until the public list is compacted misses calculate-time HTML.
        detailed = _unwrap_dict_wrapper(_attr(response, "detailed_results", None))
        raw_steps = detailed.get("step_results") if isinstance(detailed, dict) else None
        if isinstance(raw_steps, dict) and raw_steps:
            step_list = [
                {
                    "step": key,
                    "result": (
                        value.get("result", {})
                        if isinstance(value, dict)
                        else _attr(value, "result", {})
                    ),
                }
                for key, value in raw_steps.items()
            ]
        if not isinstance(step_list, list):
            return sde, sde_multiple, sde_valuation, sde_weight
        for step in step_list:
            step_d = _unwrap_dict_wrapper(step)
            if not isinstance(step_d, dict):
                continue
            num = step_d.get("step", step_d.get("step_number"))
            # Public transparency steps expose curated ``key_outputs`` (NOT the
            # raw ``result``); step 11's key_outputs now carries ``sde_cross_check``.
            # Prefer key_outputs, fall back to result for raw/legacy shapes.
            result_d = _unwrap_dict_wrapper(step_d.get("key_outputs") or step_d.get("result") or {})
            if not isinstance(result_d, dict):
                continue
            if str(num) == "2.7":
                sde = _to_decimal(result_d.get("sde"))
                sde_multiple = _to_decimal(result_d.get("sde_multiple"))
                sde_valuation = _to_decimal(result_d.get("sde_valuation"))
            elif str(num) in {"11", "11.0"}:
                cross_check = _unwrap_dict_wrapper(result_d.get("sde_cross_check") or {})
                if isinstance(cross_check, dict) and cross_check.get("applied"):
                    sde_weight = _to_decimal(cross_check.get("sde_weight"))
                    if sde_valuation <= Decimal("0"):
                        sde_valuation = _to_decimal(cross_check.get("sde_mid"))
    except (TypeError, KeyError, AttributeError, ValueError):
        pass
    return sde, sde_multiple, sde_valuation, sde_weight


def _sde_blend_reconciliation(*, response: object, sde_ev: Decimal, sde_weight: Decimal) -> JsonMap:
    """Reconstruct the EBITDA/SDE blend so the headline reconciles to both legs.

    When the Step-11 synthesis weights an SDE leg into the headline (e.g. 25%),
    the blended headline is NOT the EBITDA-multiple leg alone. This surfaces
    ``EBITDA_leg × (1−w) + SDE_leg × w = headline`` (the EBITDA leg is derived
    from the headline, the SDE leg and the weight, so it ties out to the cent)
    so the report can show the bridge instead of an unexplained drop from the
    EBITDA leg to the headline. Returns ``{"sde_blend_applied": False}`` when no
    genuine two-leg blend was applied (weight 0 or 1, or data missing).
    """
    if not (sde_ev > Decimal("0") and Decimal("0") < sde_weight < Decimal("1")):
        return {"sde_blend_applied": False}
    # The blended headline is the FINAL synthesized equity (post-SDE-blend).
    # Prefer ``equity_value_mid`` — ``multiples_valuation.equity_value`` is the
    # pre-blend market leg on some engine paths, which would mis-derive the legs
    # (back-solving the EBITDA leg from the wrong total).
    headline = _to_decimal(_attr(response, "equity_value_mid", None))
    if headline <= Decimal("0"):
        multiples_valuation = _attr(response, "multiples_valuation", None)
        headline = (
            _to_decimal(_attr(multiples_valuation, "equity_value", None))
            if multiples_valuation is not None
            else Decimal("0")
        )
    if headline <= Decimal("0"):
        return {"sde_blend_applied": False}
    ebitda_weight = Decimal("1") - sde_weight
    ebitda_leg = (headline - sde_weight * sde_ev) / ebitda_weight
    if ebitda_leg <= Decimal("0"):
        return {"sde_blend_applied": False}
    return {
        "sde_blend_applied": True,
        "sde_blend_weight_pct": int(round(float(sde_weight) * 100)),
        "ebitda_blend_weight_pct": int(round(float(ebitda_weight) * 100)),
        "sde_blend_leg_ev": safe_float(sde_ev),
        "ebitda_blend_leg_ev": safe_float(ebitda_leg),
        "sde_blend_headline_ev": safe_float(headline),
    }


def build_sde_cross_check_context(
    *,
    response: object,
    sde_data: JsonMap,
    revenue: object,
    owners: object,
    employees: object,
    ebitda: Decimal,
) -> JsonMap:
    """Build SDE cross-check context for owner-led micro-SMEs.

    Prefers the engine's REAL Step-2.7 SDE leg — the exact leg the Step-11
    synthesis weights into the blended headline — over the revenue-based
    fallback, and surfaces the EBITDA/SDE blend reconciliation so the headline
    is never left below both displayed legs without a visible bridge.
    """
    revenue_decimal = _to_decimal(revenue)
    owner_count = _to_optional_int(owners) or 0
    employee_count = _to_optional_int(employees)

    # Engine real SDE leg + Step-11 blend weight, read from the same
    # calculation_steps the rest of the report is built from. Computed up front
    # so the blend reconciliation is available even when the owner-led PANEL is
    # gated off (the headline bridge does not depend on the panel rendering).
    eng_sde, eng_multiple, eng_sde_ev, eng_sde_weight = _engine_sde_legs(response)
    if eng_sde_ev <= Decimal("0") and eng_sde > Decimal("0") and eng_multiple > Decimal("0"):
        eng_sde_ev = eng_sde * eng_multiple
    blend = _sde_blend_reconciliation(
        response=response, sde_ev=eng_sde_ev, sde_weight=eng_sde_weight
    )

    # M&A defensibility guard. SDE = earnings + owner compensation, so for an
    # owner-operated business SDE (and its EV) must exceed EBITDA — a buyer-
    # operator replaces the owner and takes no salary. When the EBITDA-
    # normalization metadata captured operating add-backs (rent, fees, social
    # charges) but NO owner-salary component, the engine's SDE leg collapses to
    # ~EBITDA, an impossible figure. Refuse to display that leg: drop the blend
    # so the report falls back to the correct owner-comp-inclusive SDE cross-
    # check (EBITDA + a market owner-comp add-back) instead of surfacing a sub-
    # EBITDA SDE. The genuine-SDE-leg case (leg >= floor) is unaffected.
    defensible_sde_floor = _fallback_sde_cross_check_value(ebitda=ebitda, revenue=revenue_decimal)
    if (
        blend.get("sde_blend_applied")
        and defensible_sde_floor > Decimal("0")
        and _to_decimal(blend.get("sde_blend_leg_ev")) < defensible_sde_floor
    ):
        blend = {"sde_blend_applied": False, "sde_blend_suppressed_low_leg": True}

    engine_leg_available = eng_sde > Decimal("0") and eng_multiple > Decimal("0")
    # When a blend was applied but the engine's SDE leg is NOT fully readable
    # (e.g. step 2.7 is not in the public transparency steps), the standalone
    # panel would fall back to a revenue-based ESTIMATE that disagrees with the
    # blend leg — two contradictory SDE figures. Suppress the panel; the blend
    # reconciliation discloses the engine's real leg. (When the engine leg IS
    # readable the panel shows that same leg, consistent with the blend, so it
    # is kept below.)
    if blend.get("sde_blend_applied") and not engine_leg_available:
        return {"show_sde_cross_check": False, **blend}

    if not _should_show_sde_cross_check(
        sde_data=sde_data,
        revenue=revenue_decimal,
        owner_count=owner_count,
        employee_count=employee_count,
    ):
        return {"show_sde_cross_check": False, **blend}

    # Panel values: prefer the engine's real leg; fall back to the
    # revenue-based estimate only when the engine produced no SDE step.
    if eng_sde > Decimal("0") and eng_multiple > Decimal("0"):
        payload = _sde_cross_check_payload(sde_value=eng_sde, sde_multiple=eng_multiple)
        if eng_sde_ev > Decimal("0"):
            # Honour the engine's exact SDE EV (sde × multiple can round-drift).
            payload["sde_cross_check_ev"] = safe_float(eng_sde_ev)
        return {**payload, **blend}

    sde_value = _fallback_sde_cross_check_value(ebitda=ebitda, revenue=revenue_decimal)
    sde_multiple = _cross_check_fallback_multiple(revenue)
    if sde_value <= Decimal("0") or sde_multiple <= Decimal("0"):
        return {"show_sde_cross_check": False, **blend}
    return {**_sde_cross_check_payload(sde_value=sde_value, sde_multiple=sde_multiple), **blend}


def _should_show_sde_cross_check(
    *,
    sde_data: JsonMap,
    revenue: Decimal,
    owner_count: int,
    employee_count: int | None,
) -> bool:
    if sde_data.get("is_sde_methodology"):
        return False
    return owner_count >= 1 and _is_micro_sme(revenue=revenue, employee_count=employee_count)


def _is_micro_sme(*, revenue: Decimal, employee_count: int | None) -> bool:
    revenue_present = revenue != Decimal("0")
    return (revenue_present and revenue <= Decimal("2000000")) or (
        employee_count is not None and employee_count <= 10
    )


def _fallback_sde_cross_check_value(*, ebitda: Decimal, revenue: Decimal) -> Decimal:
    ebitda_decimal = _to_decimal(ebitda)
    if ebitda_decimal <= Decimal("0"):
        return Decimal("0")
    return ebitda_decimal + _owner_addback_estimate(revenue)


def _owner_addback_estimate(revenue: Decimal) -> Decimal:
    if revenue != Decimal("0") and revenue >= Decimal("750000"):
        return Decimal("65000")
    return Decimal("45000")


def _sde_cross_check_payload(*, sde_value: Decimal, sde_multiple: Decimal) -> JsonMap:
    sde_ev = sde_value * sde_multiple
    return {
        "show_sde_cross_check": True,
        "sde_cross_check_value": safe_float(sde_value),
        "sde_cross_check_multiple": safe_float(sde_multiple),
        "sde_cross_check_ev": safe_float(sde_ev),
    }


def build_sde_methodology_context(
    *,
    response: object,
    request: object,
    t: SdeTranslations,
    ebitda: Decimal,
    normalization_result: Optional[JsonMap] = None,
    logger: Optional[Logger] = None,
) -> JsonMap:
    """Build SDE-specific valuation context for owner-operated micro-SMEs."""
    active_method_key = resolve_effective_method_key(
        _attr(request, "selected_method", None),
        _attr(request, "method_override_selected_method", None),
        _attr(request, "primary_method_key", None),
    )
    user_selected_sde = is_sde_method_key(active_method_key)
    recommended = _find_recommended_methodology(response, logger)
    is_sde = user_selected_sde or methodology_indicates_sde(recommended)

    if not is_sde:
        return {
            "has_sde": False,
            "is_sde_methodology": False,
            "sde_components": [],
        }

    owner_salary = _owner_salary_from_normalization(
        normalization_result or {},
        logger,
    )
    if owner_salary == 0 and request is not None:
        owner_salary = _owner_salary_from_request(request)

    sde_value = ebitda + owner_salary

    sde_multiple = _sde_multiple_from_transparency(response)
    if sde_multiple is None:
        multiples_valuation = _attr(response, "multiples_valuation", None)
        sde_multiple = _attr(multiples_valuation, "sde_multiple", None)
    if sde_multiple is None:
        sde_multiple = _fallback_sde_multiple(response)

    return {
        "has_sde": True,
        "is_sde_methodology": True,
        "sde_value": safe_float(sde_value),
        "sde_ebitda_base": safe_float(ebitda),
        "sde_owner_salary": safe_float(owner_salary),
        "sde_multiple": safe_float(sde_multiple),
        "sde_components": [
            {"label": t.dcf_row_ebitda, "amount": safe_float(ebitda), "type": "base"},
            {
                "label": t.sde_component_owner_salary_label,
                "amount": safe_float(owner_salary),
                "type": "add",
            },
            {
                "label": t.sde_component_total_label,
                "amount": safe_float(sde_value),
                "type": "result",
            },
        ],
    }
