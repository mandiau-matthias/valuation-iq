"""
Adjustment Extractor

Extracts adjustments from step results for methodology statement.
"""

from collections.abc import Mapping
from decimal import Decimal
from typing import Any, Dict, List

from src.api.routes.valuation.steps.base_step import StepStatus


def _completed_step_result(
    previous_results: Mapping[int, object], step_num: int
) -> Mapping[str, object] | None:
    step = previous_results.get(step_num)
    if not step or getattr(step, "status", None) != StepStatus.COMPLETED:
        return None

    result = getattr(step, "result", None)
    return result if isinstance(result, Mapping) else None


def _owner_concentration_adjustment(
    previous_results: Mapping[int, object], is_sole_trader: bool
) -> dict[str, str] | None:
    step4_result = _completed_step_result(previous_results, 4)
    if step4_result is None:
        return None

    owner_adj = step4_result.get("owner_concentration_adjustment")
    if not owner_adj:
        return None

    rationale = (
        "for key person risk (sole trader: maximum discount applied)"
        if is_sole_trader
        else "for key person risk"
    )
    return {
        "name": "Owner Concentration",
        "value": f"{owner_adj * 100:.1f}%",
        "rationale": rationale,
    }


def _size_discount_adjustment(
    previous_results: Mapping[int, object], is_sole_trader: bool
) -> dict[str, str] | None:
    step5_result = _completed_step_result(previous_results, 5)
    if step5_result is None:
        return None

    size_discount = step5_result.get("size_discount_percentage")
    if not size_discount:
        return None

    tier = step5_result.get("size_tier", "")
    rationale = (
        f"for {tier} company (academic size premium methodology, sole trader: additional discount applied)"
        if is_sole_trader
        else f"for {tier} company (academic size premium methodology)"
    )
    return {
        "name": "Size Discount",
        "value": f"{size_discount * 100:.1f}%",
        "rationale": rationale,
    }


def _liquidity_discount_adjustment(
    previous_results: Mapping[int, object], is_sole_trader: bool
) -> dict[str, str] | None:
    step6_result = _completed_step_result(previous_results, 6)
    if step6_result is None:
        return None

    liquidity_discount = step6_result.get("total_discount_percentage")
    if not liquidity_discount:
        return None

    rationale = (
        "for private company illiquidity (sole trader: higher discount for reduced marketability)"
        if is_sole_trader
        else "for private company illiquidity"
    )
    return {
        "name": "Liquidity Discount",
        "value": f"{liquidity_discount * 100:.1f}%",
        "rationale": rationale,
    }


def _ownership_adjustment(
    previous_results: Mapping[int, object],
) -> dict[str, str] | None:
    step8_result = _completed_step_result(previous_results, 8)
    if step8_result is None:
        return None

    ownership_pct = step8_result.get("ownership_percentage", 100)
    adjustment_type = step8_result.get("adjustment_type")
    adjustment_pct = step8_result.get("adjustment_percentage", 0)
    if adjustment_pct == 0:
        return None

    rationale = AdjustmentExtractor._get_ownership_rationale(adjustment_type, ownership_pct)
    return {
        "name": "Ownership Adjustment",
        "value": f"{adjustment_pct:+.1f}%",
        "rationale": rationale,
    }


class AdjustmentExtractor:
    """Extracts adjustments from step results."""

    @staticmethod
    def extract(previous_results: Dict[int, Any], is_sole_trader: bool) -> List[Dict[str, str]]:
        """
        Extract adjustments from steps 4, 5, 6, 8.

        Args:
            previous_results: Previous step results
            is_sole_trader: Whether business is a sole trader

        Returns:
            List of adjustment dictionaries
        """
        return [
            adjustment
            for adjustment in (
                _owner_concentration_adjustment(previous_results, is_sole_trader),
                _size_discount_adjustment(previous_results, is_sole_trader),
                _liquidity_discount_adjustment(previous_results, is_sole_trader),
                _ownership_adjustment(previous_results),
            )
            if adjustment is not None
        ]

    @staticmethod
    def _get_ownership_rationale(adjustment_type: str, ownership_pct: Decimal) -> str:
        """Get rationale for ownership adjustment."""
        if adjustment_type == "control_premium":
            return f"for majority control ({ownership_pct:.2f}% ownership)"
        elif adjustment_type == "minority_discount":
            return f"for minority stake ({ownership_pct:.2f}% ownership, limited control)"
        elif adjustment_type == "deadlock_discount":
            return f"for equal control deadlock risk ({ownership_pct:.2f}% ownership)"
        else:
            return f"for ownership structure ({ownership_pct:.2f}% ownership)"
