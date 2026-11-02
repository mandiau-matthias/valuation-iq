"""Idempotent SDE channel applicator for report contexts."""

from __future__ import annotations

from src.services.reports.sde_channel import (
    ReportContext,
    SdeChannelInputs,
    apply_sde_channel_to_context,
    build_sde_channel,
)
from src.utils.decimal_helpers import safe_decimal


def _first_present(mapping: ReportContext, *keys: str) -> object:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def _first_present_across(
    primary: ReportContext,
    primary_key: str,
    fallback: ReportContext,
    fallback_key: str,
    default: object = 0,
) -> object:
    value = _first_present(primary, primary_key)
    if value is not None:
        return value
    value = _first_present(fallback, fallback_key)
    return default if value is None else value


def _is_sde_channel_already_applied(context: ReportContext) -> bool:
    return str(context.get("multiple_metric_type") or "").upper() == "SDE"


def _mentions_sde_multiple(value: object) -> bool:
    return "sde_multiple" in str(value or "").lower()


def _is_sde_methodology_active(context: ReportContext) -> bool:
    return bool(context.get("is_sde_methodology")) or any(
        _mentions_sde_multiple(context.get(key))
        for key in ("methodology", "primary_method_key", "recommended_methodology")
    )


def _is_positive_number(value: object) -> bool:
    if not value:
        return False
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def _resolve_sde_value(
    context: ReportContext,
    valuation_data: ReportContext,
) -> object:
    value = _first_present(context, "sde_value")
    if value is not None:
        return value
    return _first_present(valuation_data, "sde")


def _resolve_base_multiple(context: ReportContext) -> object:
    return _first_present(
        context,
        "sde_base_multiple",
        "sde_multiple",
        "applied_multiple",
        "base_multiple",
    )


def _resolve_revenue(
    context: ReportContext,
    valuation_data: ReportContext,
) -> object:
    revenue = _first_present(context, "revenue")
    if revenue is None:
        revenue = _first_present(valuation_data, "revenue")
    return 0 if revenue is None else revenue


def _resolve_business_size(
    context: ReportContext,
    valuation_data: ReportContext,
    revenue: object,
) -> object:
    return (
        context.get("business_size")
        or valuation_data.get("business_size")
        or _classify_size_from_revenue(revenue)
    )


def _resolve_channel_identity(
    context: ReportContext,
    valuation_data: ReportContext,
    revenue: object,
) -> dict[str, str]:
    business_size = _resolve_business_size(context, valuation_data, revenue)
    country_code = _first_present_across(
        context, "country_code", valuation_data, "country_code", default="BE"
    )
    industry = _first_present_across(context, "industry", valuation_data, "industry", default="")
    business_type_id = _first_present_across(
        context, "business_type_id", valuation_data, "business_type_id", default=""
    )
    return {
        "business_size": str(business_size or "small"),
        "country_code": str(country_code or "BE"),
        "industry": str(industry or ""),
        "business_type_id": str(business_type_id or ""),
    }


def _resolve_balance_sheet_inputs(
    context: ReportContext,
    valuation_data: ReportContext,
) -> dict[str, object]:
    return {
        "total_debt": _first_present_across(context, "total_debt", valuation_data, "total_debt"),
        "cash": _first_present_across(context, "cash", valuation_data, "cash"),
        "nwc_adjustment": _first_present(context, "nwc_adjustment") or 0,
    }


def _resolve_owner_inputs(
    context: ReportContext,
    valuation_data: ReportContext,
) -> dict[str, object]:
    return {
        "owner_salary_addback": _first_present_across(
            context,
            "sde_owner_salary",
            valuation_data,
            "owner_salary_addback",
        ),
        "owner_salary_estimate": context.get("sde_owner_salary_estimate") or 0,
        "owner_salary_source": str(context.get("sde_owner_salary_source") or "estimate"),
        "owner_role": str(context.get("sde_owner_role") or "working"),
        "num_owners": int(
            context.get("number_of_owners") or valuation_data.get("number_of_owners") or 1
        ),
    }


def _build_sde_channel_inputs(
    context: ReportContext,
    valuation_data: ReportContext,
    *,
    sde_value: object,
    base_multiple: object,
    revenue: object,
) -> SdeChannelInputs:
    identity = _resolve_channel_identity(context, valuation_data, revenue)
    balance_sheet = _resolve_balance_sheet_inputs(context, valuation_data)
    owner = _resolve_owner_inputs(context, valuation_data)

    return SdeChannelInputs(
        sde_value=safe_decimal(sde_value),
        sde_base_multiple=safe_decimal(base_multiple),
        revenue=safe_decimal(revenue),
        total_debt=safe_decimal(balance_sheet["total_debt"]),
        cash=safe_decimal(balance_sheet["cash"]),
        nwc_adjustment=safe_decimal(balance_sheet["nwc_adjustment"]),
        owner_salary_addback=safe_decimal(owner["owner_salary_addback"]),
        owner_salary_estimate=safe_decimal(owner["owner_salary_estimate"]),
        owner_salary_source=str(owner["owner_salary_source"]),
        owner_role=str(owner["owner_role"]),
        num_owners=int(owner["num_owners"]),
        business_size=identity["business_size"],
        country_code=identity["country_code"],
        industry=identity["industry"],
        business_type_id=identity["business_type_id"],
    )


def ensure_sde_channel_applied(
    context: ReportContext,
    valuation_data: ReportContext,
    *,
    locale: str = "nl",
) -> bool:
    """Apply the SDE channel when SDE is the active valuation method."""
    if _is_sde_channel_already_applied(context) or not _is_sde_methodology_active(context):
        return False

    sde_value = _resolve_sde_value(context, valuation_data)
    if not _is_positive_number(sde_value):
        return False

    base_multiple = _resolve_base_multiple(context)
    if not _is_positive_number(base_multiple):
        return False

    inputs = _build_sde_channel_inputs(
        context,
        valuation_data,
        sde_value=sde_value,
        base_multiple=base_multiple,
        revenue=_resolve_revenue(context, valuation_data),
    )
    channel = build_sde_channel(inputs)
    if not channel.calibration_steps:
        return False

    apply_sde_channel_to_context(context, channel=channel, locale=locale)
    return True


def _classify_size_from_revenue(revenue: object) -> str:
    """Local size classifier matching Step 2.7 thresholds."""
    try:
        value = float(revenue or 0)
    except (TypeError, ValueError):
        return "small"
    if value < 500_000:
        return "micro"
    if value < 2_000_000:
        return "small"
    if value < 5_000_000:
        return "lower_middle"
    return "large"
