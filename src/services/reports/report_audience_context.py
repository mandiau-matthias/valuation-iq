"""Report audience (seller vs advisor) and role-aware M&A advisory panels."""

from __future__ import annotations

from typing import Mapping, Optional

from src.services.infrastructure.report_classifier import ReportClassification
from src.utils.decimal_helpers import to_decimal

JsonMap = dict[str, object]

_SELLER_AUDIENCE = "seller"
_ADVISOR_AUDIENCE = "advisor"
_SELLER_ROLES = frozenset({"seller"})
_ADVISOR_ROLES = frozenset({"buyer", "accountant", "expert", "enterprise", "admin"})


def _first_present(mapping: Mapping[str, object], *keys: str) -> object:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def normalize_report_audience(raw: object) -> str:
    value = str(raw or "").strip().lower()
    return _SELLER_AUDIENCE if value == _SELLER_AUDIENCE else _ADVISOR_AUDIENCE


def _normalize_actor_role(metadata: Mapping[str, object]) -> str:
    role = metadata.get("actor_role") or metadata.get("actorRole")
    return str(role or "").strip().lower()


def resolve_effective_report_audience(metadata: object) -> str:
    """Display audience: viewer override first, then commissioned/default signals."""
    if not isinstance(metadata, Mapping):
        return _ADVISOR_AUDIENCE
    view = metadata.get("report_view_audience") or metadata.get("reportViewAudience")
    if view:
        return normalize_report_audience(view)
    return resolve_report_audience_from_metadata(metadata)


def resolve_report_audience_from_metadata(metadata: object) -> str:
    if not isinstance(metadata, Mapping):
        return _ADVISOR_AUDIENCE

    explicit_audience = _explicit_report_audience(metadata)
    if explicit_audience:
        return normalize_report_audience(explicit_audience)
    if _has_accountant_customer(metadata):
        return _ADVISOR_AUDIENCE
    if _is_seller_valuation(metadata):
        return _SELLER_AUDIENCE

    role = _normalize_actor_role(metadata)
    if role in _SELLER_ROLES:
        return _SELLER_AUDIENCE
    if role in _ADVISOR_ROLES:
        return _ADVISOR_AUDIENCE
    if _is_venus_report(metadata):
        return _SELLER_AUDIENCE
    return _ADVISOR_AUDIENCE


def _explicit_report_audience(metadata: Mapping[str, object]) -> object:
    return (
        metadata.get("report_commissioned_audience")
        or metadata.get("reportCommissionedAudience")
        or metadata.get("report_audience")
        or metadata.get("reportAudience")
    )


def _has_accountant_customer(metadata: Mapping[str, object]) -> bool:
    return bool(metadata.get("accountant_customer_id") or metadata.get("accountantCustomerId"))


def _is_seller_valuation(metadata: Mapping[str, object]) -> bool:
    return metadata.get("is_seller_valuation") is True or metadata.get("isSellerValuation") is True


def _is_venus_report(metadata: Mapping[str, object]) -> bool:
    report_source = metadata.get("report_source") or metadata.get("reportSource")
    return str(report_source or "").strip().lower() == "venus"


def _years_of_data(request: object) -> int:
    historical = getattr(request, "historical_years_data", None) or []
    return 1 + len(list(historical))


def _has_balance_sheet(request: object) -> bool:
    current = getattr(request, "current_year_data", None)
    if current is None:
        return False
    for field in ("total_assets", "total_debt", "cash", "total_equity"):
        if getattr(current, field, None) not in (None, "", 0):
            return True
    return False


def _margin_deviation_note(
    request: object,
    translations: object,
    *,
    audience: str,
) -> Optional[str]:
    reported_margin = _reported_ebitda_margin(request)
    if reported_margin is None:
        return None
    typical = _typical_ebitda_margin(request)
    if typical is None or reported_margin >= typical * 0.85:
        return None

    template = _margin_note_template(translations, audience)
    if not template:
        return None
    return str(template).format(
        reported_pct=round(reported_margin * 100, 1),
        typical_pct=round(typical * 100, 1),
    )


def _reported_ebitda_margin(request: object) -> float | None:
    current = getattr(request, "current_year_data", None)
    if current is None:
        return None

    revenue = to_decimal(getattr(current, "revenue", None) or 0)
    # Venus may supply a normalized calculation basis in `ebitda`. The note
    # explicitly describes the filed/reported margin, so preserve that basis.
    reported = getattr(current, "reported_ebitda", None)
    ebitda = to_decimal(reported if reported is not None else getattr(current, "ebitda", None) or 0)
    if revenue <= 0 or ebitda <= 0:
        return None
    return float(ebitda / revenue)


def _typical_ebitda_margin(request: object) -> float | None:
    benchmarks = getattr(request, "industry_benchmarks", None)
    if not isinstance(benchmarks, dict):
        return None
    return _coerce_typical_margin(benchmarks.get("typical_ebitda_margin"))


def _coerce_typical_margin(raw: object) -> float | None:
    # `typical_ebitda_margin` from a resolved Upswitch Index benchmark contract is a band
    # dict ({"min", "median", "max"}), not a scalar. Pull the central value before
    # coercing so contract-resolved reports cannot fall into the HTML safety net.
    if isinstance(raw, Mapping):
        raw = _central_margin_value(raw)
    try:
        typical = float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None
    if typical is not None and typical > 1:
        return typical / 100.0
    return typical


def _central_margin_value(raw: Mapping[str, object]) -> object:
    return next(
        (raw[key] for key in ("median", "p50", "min", "max") if raw.get(key) is not None), None
    )


def _margin_note_template(translations: object, audience: str) -> object:
    if audience == _SELLER_AUDIENCE:
        return getattr(translations, "seller_margin_diligence_note", None)
    return getattr(translations, "advisor_margin_diligence_note", None)


def _limited_scope_signals(
    *,
    request: object | None,
    existing: Mapping[str, object],
) -> tuple[bool, int, bool, bool, bool]:
    years = _years_of_data(request) if request else 1
    sample_size_raw = existing.get("benchmark_sample_size")
    try:
        sample_size = int(sample_size_raw) if sample_size_raw is not None else 0
    except (TypeError, ValueError):
        sample_size = 0

    classification = str(existing.get("report_classification") or "")
    limited_scope = classification == ReportClassification.LIMITED_SCOPE.value or years <= 2
    thin_benchmark = sample_size > 0 and sample_size <= 3
    no_balance = not _has_balance_sheet(request) if request else True
    owner_comp_estimated = bool(
        existing.get("owner_compensation_estimated")
        or (getattr(request, "owner_salary_addback", None) in (None, "", 0) if request else True)
    )
    show_limited_panel = limited_scope or thin_benchmark or no_balance
    return show_limited_panel, years, thin_benchmark, no_balance, owner_comp_estimated


def _multiple_calibration_bridge(
    *,
    request: object | None,
    existing: Mapping[str, object],
) -> JsonMap:
    contract = None
    if request is not None:
        from src.api.routes.valuation.benchmark_contract_utils import (
            extract_request_resolved_benchmark_contract,
        )

        contract = extract_request_resolved_benchmark_contract(request)
    reference_multiple = _first_present(existing, "benchmark_multiple_mid", "base_multiple")
    applied_multiple = _first_present(existing, "applied_multiple", "adaptive_multiple_used")

    # ``benchmark_multiple_mid`` is the RAW sector reference (the business-types
    # DB anchor when no live contract resolved — B1/Jan #1) while
    # ``base_multiple`` is the calibrated contract basis. When they coincide
    # (no size/margin calibration applied — e.g. advisor B/C), printing the
    # base as a separate "gekalibreerde contractbasis" row would fabricate a
    # calibration step that never happened, so the row is suppressed.
    base_multiple = existing.get("base_multiple")
    try:
        if (
            base_multiple is not None
            and reference_multiple is not None
            and abs(float(base_multiple) - float(reference_multiple)) < 0.005
        ):
            base_multiple = None
    except (TypeError, ValueError):
        pass

    return {
        "show_multiple_calibration_bridge": bool(
            reference_multiple and applied_multiple and existing.get("is_adaptive_multiples_only")
        ),
        "bridge_reference_multiple": reference_multiple,
        "bridge_base_multiple": base_multiple,
        "bridge_applied_multiple": applied_multiple,
        "bridge_contract_resolved": contract is not None,
    }


def build_limited_scope_advisory_context(
    *,
    request: object | None,
    existing: Mapping[str, object],
) -> JsonMap:
    show_limited_panel, years, thin_benchmark, no_balance, owner_comp_estimated = (
        _limited_scope_signals(request=request, existing=existing)
    )
    return {
        "show_limited_scope_advisory_panel": show_limited_panel,
        "limited_scope_years": years,
        "limited_scope_thin_benchmark": thin_benchmark,
        "limited_scope_no_balance": no_balance,
        "owner_compensation_estimated": owner_comp_estimated,
    }


def build_seller_advisory_context(
    *,
    request: object | None,
    response: object | None,
    translations: object,
    existing: Mapping[str, object],
) -> JsonMap:
    """Panels and flags for seller-facing Adaptive reports."""
    limited = build_limited_scope_advisory_context(request=request, existing=existing)
    show_advisor_cta = bool(existing.get("show_seller_advisor_cta"))
    bridge = _multiple_calibration_bridge(request=request, existing=existing)

    return {
        **limited,
        "seller_margin_diligence_note": _margin_deviation_note(
            request, translations, audience=_SELLER_AUDIENCE
        ),
        "show_seller_advisor_cta": show_advisor_cta,
        **bridge,
    }


def build_advisor_advisory_context(
    *,
    request: object | None,
    response: object | None,
    translations: object,
    existing: Mapping[str, object],
) -> JsonMap:
    """M&A checklist panels for advisor-commissioned reports."""
    limited = build_limited_scope_advisory_context(request=request, existing=existing)
    bridge = _multiple_calibration_bridge(request=request, existing=existing)

    return {
        **limited,
        "advisor_margin_diligence_note": _margin_deviation_note(
            request, translations, audience=_ADVISOR_AUDIENCE
        ),
        "show_seller_advisor_cta": False,
        **bridge,
    }


def apply_report_audience_context(
    context: JsonMap,
    *,
    request: object | None,
    response: object | None,
    request_metadata: Mapping[str, object] | None,
    translations: object,
) -> None:
    audience = resolve_effective_report_audience(request_metadata)
    context["report_audience"] = audience
    context["is_seller_report"] = audience == _SELLER_AUDIENCE
    context["is_advisor_report"] = audience == _ADVISOR_AUDIENCE

    existing: JsonMap = dict(context)
    if request_metadata:
        if request_metadata.get("show_seller_advisor_cta") is True:
            existing["show_seller_advisor_cta"] = True

    if audience == _SELLER_AUDIENCE:
        context.update(
            build_seller_advisory_context(
                request=request,
                response=response,
                translations=translations,
                existing=existing,
            )
        )
        if not context.get("seller_advisor_cta_url"):
            locale = str(context.get("locale") or context.get("report_locale") or "nl").lower()
            context["seller_advisor_cta_url"] = (
                "/nl/client/dashboard" if locale.startswith("nl") else "/en/client/dashboard"
            )
        return

    context.update(
        build_advisor_advisory_context(
            request=request,
            response=response,
            translations=translations,
            existing=existing,
        )
    )
    context["show_seller_advisor_cta"] = False
