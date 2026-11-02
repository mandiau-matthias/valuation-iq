"""SDE selected-method override helpers for Omni-Calc report context."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Optional, TypeAlias

from src.services.reports.adaptive_report_gates import refresh_adaptive_gates_on_context
from src.services.reports.sde_channel import (
    SdeChannelInputs,
    apply_sde_channel_to_context,
    build_sde_channel,
)
from src.utils.decimal_helpers import safe_float

JsonMap: TypeAlias = Dict[str, object]


@dataclass(frozen=True)
class SdeOwnerInputs:
    owner_role: object
    owner_salary_addback: object
    owner_salary_estimate: object
    owner_salary_source: object
    owner_concentration_override: object
    num_owners: int


@dataclass(frozen=True)
class SdeBalanceInputs:
    total_debt: object
    cash: object
    nwc_adjustment: object


@dataclass(frozen=True)
class SdeBusinessInputs:
    revenue: object
    business_size: object
    country_code: object
    industry: object
    business_type_id: object


def apply_sde_channel_override(
    context: JsonMap,
    *,
    method_details: JsonMap,
    valuation_data: JsonMap,
    enterprise_value: Optional[float],
    override_val: float,
    locale: str = "nl",
) -> None:
    """Apply the SDE channel atomically for a selected SDE method."""
    sde_value = _resolve_sde_value(method_details, valuation_data)
    owner_inputs = _resolve_owner_inputs(context, method_details, valuation_data)
    channel = build_sde_channel(
        _build_sde_inputs(
            context=context,
            method_details=method_details,
            valuation_data=valuation_data,
            sde_value=sde_value,
            owner_inputs=owner_inputs,
        )
    )
    context["sde_bridge"] = build_sde_bridge(
        context=context,
        method_details=method_details,
        valuation_data=valuation_data,
        owner_salary_addback=owner_inputs.owner_salary_addback,
    )

    if not channel.calibration_steps:
        _apply_legacy_sde_fallback(
            context,
            sde_value=sde_value,
            owner_salary_addback=owner_inputs.owner_salary_addback,
        )
        return

    apply_sde_channel_to_context(context, channel=channel, locale=locale)


def build_sde_bridge(
    *,
    context: JsonMap,
    method_details: JsonMap,
    valuation_data: JsonMap,
    owner_salary_addback: object,
) -> JsonMap:
    """Build Net Income -> SDE bridge data for the dedicated report partial."""
    depreciation = _first_truthy(
        valuation_data.get("depreciation"),
        context.get("depreciation"),
        default=0,
    )
    amortization = _first_truthy(
        valuation_data.get("amortization"),
        context.get("amortization"),
        default=0,
    )
    return {
        "net_income": safe_float(
            _first_truthy(
                method_details.get("net_income"),
                valuation_data.get("net_income"),
                context.get("net_income"),
                default=0,
            )
        ),
        "interest": safe_float(
            _first_truthy(
                valuation_data.get("interest_expense"),
                valuation_data.get("interest"),
                context.get("interest_expense"),
                default=0,
            )
        ),
        "taxes": safe_float(
            _first_truthy(
                valuation_data.get("taxes"),
                valuation_data.get("tax_expense"),
                context.get("taxes"),
                default=0,
            )
        ),
        "depreciation": safe_float(float(depreciation) + float(amortization)),
        "owner_comp": safe_float(owner_salary_addback),
        "other": 0.0,
    }


def _build_sde_inputs(
    *,
    context: JsonMap,
    method_details: JsonMap,
    valuation_data: JsonMap,
    sde_value: object,
    owner_inputs: SdeOwnerInputs,
) -> SdeChannelInputs:
    business_inputs = _resolve_business_inputs(context, method_details, valuation_data)
    balance_inputs = _resolve_balance_inputs(context, valuation_data)
    return SdeChannelInputs(
        sde_value=_decimal(sde_value),
        sde_base_multiple=_decimal(_resolve_sde_base_multiple(context, method_details)),
        revenue=_decimal(business_inputs.revenue),
        total_debt=_decimal(balance_inputs.total_debt),
        cash=_decimal(balance_inputs.cash),
        nwc_adjustment=_decimal(balance_inputs.nwc_adjustment),
        owner_salary_addback=_decimal(owner_inputs.owner_salary_addback),
        owner_salary_estimate=_decimal(owner_inputs.owner_salary_estimate),
        owner_salary_source=str(owner_inputs.owner_salary_source or "estimate"),
        owner_role=str(owner_inputs.owner_role or "working"),
        num_owners=owner_inputs.num_owners,
        business_size=str(business_inputs.business_size or "small"),
        country_code=str(business_inputs.country_code or "BE"),
        industry=str(business_inputs.industry or ""),
        business_type_id=str(business_inputs.business_type_id or ""),
        sde_multiple_p25=_optional_decimal(
            _first_present(method_details, "sde_multiple_p25", "p25_multiple")
        ),
        sde_multiple_p75=_optional_decimal(
            _first_present(method_details, "sde_multiple_p75", "p75_multiple")
        ),
        owner_concentration_tier_override=owner_inputs.owner_concentration_override,
    )


def _resolve_sde_value(method_details: JsonMap, valuation_data: JsonMap) -> object:
    sde_value = _first_present(method_details, "sde")
    if sde_value is not None:
        return sde_value
    if valuation_data.get("sde") is not None:
        return valuation_data.get("sde")
    details = valuation_data.get("details")
    return details.get("sde") if isinstance(details, dict) else None


def _resolve_sde_base_multiple(context: JsonMap, method_details: JsonMap) -> object:
    return method_details.get("sde_base_multiple") or _first_present(
        context, "applied_multiple", "base_multiple"
    )


def _resolve_business_inputs(
    context: JsonMap,
    method_details: JsonMap,
    valuation_data: JsonMap,
) -> SdeBusinessInputs:
    revenue = _first_present(context, "revenue")
    if revenue is None:
        revenue = _first_present(valuation_data, "revenue")
    if revenue is None:
        revenue = 0
    return SdeBusinessInputs(
        revenue=revenue,
        business_size=_resolve_business_size(method_details, valuation_data, revenue),
        country_code=_first_truthy(
            valuation_data.get("country_code"),
            method_details.get("country_code"),
            default="BE",
        ),
        industry=_first_truthy(
            method_details.get("industry"),
            valuation_data.get("industry"),
            context.get("industry"),
            default="",
        ),
        business_type_id=_first_truthy(
            method_details.get("business_type_id"),
            valuation_data.get("business_type_id"),
            default="",
        ),
    )


def _resolve_owner_inputs(
    context: JsonMap,
    method_details: JsonMap,
    valuation_data: JsonMap,
) -> SdeOwnerInputs:
    return SdeOwnerInputs(
        owner_role=_first_truthy(
            _first_present(method_details, "owner_role"),
            _first_present(context, "sde_owner_role"),
            default="working",
        ),
        owner_salary_addback=_first_truthy(
            _first_present(method_details, "owner_salary_addback"), default=0
        ),
        owner_salary_estimate=_first_truthy(
            _first_present(method_details, "owner_salary_estimate"), default=0
        ),
        owner_salary_source=_first_truthy(
            _first_present(method_details, "owner_salary_source"), default="estimate"
        ),
        owner_concentration_override=_first_truthy(
            method_details.get("owner_concentration_tier_override"),
            valuation_data.get("owner_concentration_tier_override"),
            default=None,
        ),
        num_owners=int(
            _first_truthy(
                method_details.get("number_of_owners"),
                valuation_data.get("number_of_owners"),
                context.get("number_of_owners"),
                default=1,
            )
        ),
    )


def _resolve_balance_inputs(context: JsonMap, valuation_data: JsonMap) -> SdeBalanceInputs:
    return SdeBalanceInputs(
        total_debt=(
            _first_present(context, "total_debt")
            if _first_present(context, "total_debt") is not None
            else (_first_present(valuation_data, "total_debt") or 0)
        ),
        cash=(
            _first_present(context, "cash")
            if _first_present(context, "cash") is not None
            else (_first_present(valuation_data, "cash") or 0)
        ),
        nwc_adjustment=_first_present(context, "nwc_adjustment") or 0,
    )


def _apply_legacy_sde_fallback(
    context: JsonMap,
    *,
    sde_value: object,
    owner_salary_addback: object,
) -> None:
    context["has_sde"] = True
    context["is_sde_methodology"] = True
    context["sde_value"] = safe_float(sde_value)
    context["sde_owner_salary"] = safe_float(owner_salary_addback)
    if context.get("applied_multiple") is not None:
        context["sde_multiple"] = safe_float(context.get("applied_multiple"))
    refresh_adaptive_gates_on_context(context)


def _first_present(mapping: JsonMap, *keys: str) -> object:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def _first_truthy(*values: object, default: object = None) -> object:
    for value in values:
        if value:
            return value
    return default


def _resolve_business_size(
    method_details: JsonMap,
    valuation_data: JsonMap,
    revenue: object,
) -> object:
    return _first_truthy(
        method_details.get("business_size"),
        valuation_data.get("business_size"),
        default=classify_size_from_revenue(revenue),
    )


def _decimal(value: object) -> Decimal:
    return Decimal(str(value or 0))


def _optional_decimal(value: object) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


def classify_size_from_revenue(revenue: object) -> str:
    """Classify business size by revenue band — matches Step 2.7 thresholds."""
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
