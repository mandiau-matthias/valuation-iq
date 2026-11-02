"""Asking-price assembly helpers for the comprehensive response builder."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from src.api.routes.valuation.orchestration.executors.comprehensive.response_dcf_bridge import (
    decimal_from_dict,
)
from src.config.valuation_constants import get_asking_price_markup
from src.utils.decimal_helpers import to_decimal


@dataclass(frozen=True)
class AskingPriceFields:
    recommended_asking_price: object
    recommended_asking_multiple: object
    markup_pct: Optional[Decimal]
    markup_source: str
    markup_reasoning: Optional[str]


@dataclass(frozen=True)
class ExistingAskingPrice:
    price: object
    multiple: object


@dataclass(frozen=True)
class MarkupPolicy:
    multiplier: Decimal
    pct: Optional[Decimal]
    source: str
    reasoning: Optional[str]


def resolve_advisor_buffer_override(request: object) -> object:
    """Return advisor-configured asking-price buffer override, if present."""
    advisor_buffer_override = getattr(request, "asking_price_buffer_pct", None)
    if advisor_buffer_override is not None:
        return advisor_buffer_override

    branding = getattr(request, "branding", None)
    if isinstance(branding, dict):
        return branding.get("asking_price_buffer_pct")
    return None


def is_advisor_buffer_in_band(advisor_buffer_override: object) -> bool:
    """True when override is a valid fraction in the supported [0, 0.25] range."""
    if advisor_buffer_override is None:
        return False
    try:
        override_decimal = Decimal(str(advisor_buffer_override))
    except Exception:
        return False
    return Decimal("0") <= override_decimal <= Decimal("0.25")


def _existing_asking_price(
    *,
    requested_dcf_only: bool,
    detailed_results: dict[str, object],
    step_11_result: object,
) -> ExistingAskingPrice:
    if requested_dcf_only:
        return ExistingAskingPrice(price=None, multiple=None)

    price = detailed_results.get("step_11_asking_price")
    multiple = detailed_results.get("step_11_asking_multiple")
    if isinstance(step_11_result, dict):
        price = price if price is not None else step_11_result.get("asking_price")
        multiple = (
            multiple if multiple is not None else step_11_result.get("recommended_asking_multiple")
        )
    return ExistingAskingPrice(price=price, multiple=multiple)


def _markup_policy(
    *,
    confidence_level: str,
    advisor_buffer_override: object,
) -> MarkupPolicy:
    markup = get_asking_price_markup(
        confidence_level,
        advisor_override_pct=advisor_buffer_override,
    )
    markup_pct = (markup - Decimal("1")) if markup is not None else None

    if is_advisor_buffer_in_band(advisor_buffer_override):
        return MarkupPolicy(
            multiplier=markup,
            pct=markup_pct,
            source="advisor_override",
            reasoning="Advisor / firm-level branding override applied via asking_price_buffer_pct.",
        )

    confidence = str(confidence_level).lower() or "medium"
    return MarkupPolicy(
        multiplier=markup,
        pct=markup_pct,
        source=f"confidence_{confidence}",
        reasoning=(
            "Confidence-aware default per Pratt & Niculita (2008), "
            "IBBA Market Pulse (2024). "
            f"DCF confidence: {confidence_level}."
        ),
    )


def _enterprise_value_basis(
    *,
    requested_dcf_only: bool,
    raw_dcf_result: object,
    equity_value_mid: Decimal,
    net_debt: Decimal,
) -> Decimal:
    dcf_enterprise_value = (
        decimal_from_dict(raw_dcf_result, "enterprise_value")
        if requested_dcf_only and isinstance(raw_dcf_result, dict)
        else None
    )
    return (
        dcf_enterprise_value
        if dcf_enterprise_value and dcf_enterprise_value > 0
        else equity_value_mid + net_debt
    )


def _asking_multiple(
    *,
    requested_dcf_only: bool,
    existing_multiple: object,
    current_multiple: object,
    markup: Decimal,
) -> object:
    if requested_dcf_only:
        return None
    if existing_multiple is not None or not current_multiple:
        return existing_multiple
    return to_decimal(current_multiple) * markup


def resolve_recommended_asking_fields(
    *,
    requested_dcf_only: bool,
    detailed_results: dict[str, object],
    step_11_result: object,
    raw_dcf_result: object,
    equity_value_mid: Decimal,
    net_debt: Decimal,
    current_multiple: object,
    confidence_level: str,
    request: object,
) -> AskingPriceFields:
    """Resolve asking price, multiple, and markup provenance for the response."""
    existing = _existing_asking_price(
        requested_dcf_only=requested_dcf_only,
        detailed_results=detailed_results,
        step_11_result=step_11_result,
    )
    advisor_buffer_override = resolve_advisor_buffer_override(request)

    markup_policy = (
        _markup_policy(
            confidence_level=confidence_level,
            advisor_buffer_override=advisor_buffer_override,
        )
        if existing.price is None
        else None
    )
    recommended_asking_price = existing.price
    if markup_policy is not None:
        enterprise_value = _enterprise_value_basis(
            requested_dcf_only=requested_dcf_only,
            raw_dcf_result=raw_dcf_result,
            equity_value_mid=equity_value_mid,
            net_debt=net_debt,
        )
        recommended_asking_price = enterprise_value * markup_policy.multiplier - net_debt

    markup = (
        markup_policy.multiplier
        if markup_policy is not None
        else get_asking_price_markup(
            confidence_level,
            advisor_override_pct=advisor_buffer_override,
        )
    )

    return AskingPriceFields(
        recommended_asking_price=recommended_asking_price,
        recommended_asking_multiple=_asking_multiple(
            requested_dcf_only=requested_dcf_only,
            existing_multiple=existing.multiple,
            current_multiple=current_multiple,
            markup=markup,
        ),
        markup_pct=markup_policy.pct if markup_policy else None,
        markup_source=markup_policy.source if markup_policy else "confidence_default",
        markup_reasoning=markup_policy.reasoning if markup_policy else None,
    )
