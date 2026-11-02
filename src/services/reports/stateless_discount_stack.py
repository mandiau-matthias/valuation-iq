"""Discount stack adapter for the stateless valuation path."""

from __future__ import annotations

from src.domain.multiples.advisor_controls import (
    DEFAULT_DISCOUNT_FLOOR_FACTOR,
    compose_discount_stack,
)
from src.domain.multiples.strength_factor_discount_evidence import (
    annotate_discount_stack_with_strength_factor_evidence,
    apply_strength_factor_discount_adjustments,
)
from src.utils.decimal_helpers import safe_decimal_or_zero


def build_stateless_discount_stack(
    *,
    size_discount: object,
    liquidity_discount: object,
    country_adjustment: object,
    advisor_discount_weights: dict[str, object] | None,
    risk_analysis_enabled: bool | None,
    discount_floor_factor: object | None,
    strength_factor_discount_adjustments: object = None,
) -> dict[str, object]:
    """Build the canonical discount stack from legacy positive discount rates."""
    adjustments, strength_factor_evidence = apply_strength_factor_discount_adjustments(
        {
            "size_discount": -safe_decimal_or_zero(size_discount),
            "liquidity_discount": -safe_decimal_or_zero(liquidity_discount),
            "country_adjustment": -safe_decimal_or_zero(country_adjustment),
        },
        strength_factor_discount_adjustments,
    )
    stack = compose_discount_stack(
        adjustments,
        raw_weights=advisor_discount_weights,
        enabled=True if risk_analysis_enabled is None else bool(risk_analysis_enabled),
        floor_factor=(
            discount_floor_factor
            if discount_floor_factor is not None
            else DEFAULT_DISCOUNT_FLOOR_FACTOR
        ),
    )
    stack = annotate_discount_stack_with_strength_factor_evidence(
        stack,
        strength_factor_evidence,
    )
    stack["basis"] = "pre-adjustment comparable multiple"
    stack["owner_concentration_policy"] = "excluded_from_stateless_discount_stack"
    stack["owner_concentration_policy_reason"] = (
        "Owner concentration is handled by the owner-dependency pipeline; "
        "the stateless discount stack must not double-count it as liquidity/DLOM."
    )
    return stack
