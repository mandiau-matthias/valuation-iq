"""SDE and EBITDA blend helpers for Step 11 synthesis."""

from decimal import Decimal
from typing import Protocol

from src.utils.decimal_helpers import to_decimal
from src.utils.equity_range_normalization import coerce_equity_range_triple


class SdeSynthesisLogger(Protocol):
    """Small logger protocol for Step 11 SDE blend diagnostics."""

    def debug(self, message: str, *, extra: dict[str, object] | None = None) -> object: ...

    def warning(self, message: str, *, extra: dict[str, object] | None = None) -> object: ...


def synthesize_with_sde(
    *,
    ebitda_valuation_mid: Decimal,
    ebitda_valuation_low: Decimal,
    ebitda_valuation_high: Decimal,
    sde_valuation_mid: Decimal | None,
    sde_valuation_low: Decimal | None,
    sde_valuation_high: Decimal | None,
    sde_weight: Decimal = Decimal("0.0"),
    logger: SdeSynthesisLogger,
) -> tuple[Decimal, Decimal, Decimal, dict[str, object]]:
    """
    Synthesize EBITDA and SDE valuations with configurable weights.

    SDE is usually more relevant for small owner-operated businesses, while
    EBITDA should dominate larger mid-market contexts. The helper normalizes
    unordered input bands before blending so downstream Step 11 ordering guards
    receive a coherent range.
    """
    sde_weight_original = to_decimal(sde_weight)
    sde_weight = min(Decimal("1.0"), max(Decimal("0.0"), sde_weight_original))
    if sde_weight != sde_weight_original:
        logger.warning(
            "Step 11 SDE synthesis clamped invalid SDE weight",
            extra={
                "step_number": 11,
                "original_sde_weight": str(sde_weight_original),
                "clamped_sde_weight": str(sde_weight),
            },
        )

    ebitda_valuation_low, ebitda_valuation_mid, ebitda_valuation_high, ebitda_widened = (
        coerce_equity_range_triple(
            ebitda_valuation_low,
            ebitda_valuation_mid,
            ebitda_valuation_high,
        )
    )
    if ebitda_widened:
        logger.warning(
            "Step 11 SDE synthesis widened unordered EBITDA band before blending",
            extra={
                "step_number": 11,
                "ebitda_low": str(ebitda_valuation_low),
                "ebitda_mid": str(ebitda_valuation_mid),
                "ebitda_high": str(ebitda_valuation_high),
            },
        )

    if sde_valuation_mid is None:
        return (
            ebitda_valuation_mid,
            ebitda_valuation_low,
            ebitda_valuation_high,
            {
                "methodology": "EBITDA Multiples Only",
                "ebitda_weight": 1.0,
                "sde_weight": 0.0,
                "sde_available": False,
                "input_bounds_normalized": ebitda_widened,
            },
        )

    sde_valuation_mid = to_decimal(sde_valuation_mid)
    if sde_valuation_mid <= 0:
        return (
            ebitda_valuation_mid,
            ebitda_valuation_low,
            ebitda_valuation_high,
            {
                "methodology": "EBITDA Multiples Only",
                "ebitda_weight": 1.0,
                "sde_weight": 0.0,
                "sde_available": False,
                "input_bounds_normalized": ebitda_widened,
            },
        )

    ebitda_weight = Decimal("1.0") - sde_weight
    synthesized_mid = (ebitda_valuation_mid * ebitda_weight) + (sde_valuation_mid * sde_weight)
    sde_low = (
        sde_valuation_low if sde_valuation_low is not None else sde_valuation_mid * Decimal("0.85")
    )
    sde_high = (
        sde_valuation_high
        if sde_valuation_high is not None
        else sde_valuation_mid * Decimal("1.15")
    )

    sde_low, sde_valuation_mid, sde_high, sde_widened = coerce_equity_range_triple(
        sde_low,
        sde_valuation_mid,
        sde_high,
    )
    if sde_widened:
        logger.warning(
            "Step 11 SDE synthesis widened unordered SDE band before blending",
            extra={
                "step_number": 11,
                "sde_low": str(sde_low),
                "sde_mid": str(sde_valuation_mid),
                "sde_high": str(sde_high),
            },
        )

    synthesized_low = (ebitda_valuation_low * ebitda_weight) + (sde_low * sde_weight)
    synthesized_high = (ebitda_valuation_high * ebitda_weight) + (sde_high * sde_weight)
    synthesized_low, synthesized_mid, synthesized_high, synthesized_widened = (
        coerce_equity_range_triple(
            synthesized_low,
            synthesized_mid,
            synthesized_high,
        )
    )
    if synthesized_widened:
        logger.warning(
            "Step 11 SDE synthesis widened blended band after weighting",
            extra={
                "step_number": 11,
                "valuation_low": str(synthesized_low),
                "valuation_mid": str(synthesized_mid),
                "valuation_high": str(synthesized_high),
            },
        )

    breakdown = {
        "methodology": "Weighted Synthesis (EBITDA + SDE)",
        "ebitda_weight": float(ebitda_weight),
        "sde_weight": float(sde_weight),
        "sde_available": True,
        "ebitda_contribution_mid": float(ebitda_valuation_mid * ebitda_weight),
        "sde_contribution_mid": float(sde_valuation_mid * sde_weight),
        "input_bounds_normalized": ebitda_widened or sde_widened,
        "synthesized_bounds_normalized": synthesized_widened,
        "academic_source": "Pratt & Niculita (2008): Multiple methodology reconciliation",
    }

    logger.debug(
        "✅ Weighted synthesis completed (EBITDA + SDE)",
        extra={
            "ebitda_mid": float(ebitda_valuation_mid),
            "sde_mid": float(sde_valuation_mid),
            "ebitda_weight": float(ebitda_weight),
            "sde_weight": float(sde_weight),
            "synthesized_mid": float(synthesized_mid),
        },
    )

    return synthesized_mid, synthesized_low, synthesized_high, breakdown


__all__ = ["synthesize_with_sde"]
