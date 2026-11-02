"""
Assumption Extractor

Extracts assumptions from step results for methodology statement.
"""

from collections.abc import Mapping
from typing import Any, Dict, List

from src.api.routes.valuation.steps.base_step import StepStatus

_SOLE_TRADER_ASSUMPTION = (
    "Sole trader business structure: Valuation optimized for owner-dependent businesses "
    "with maximum risk adjustments applied"
)


def _completed_step_result(
    previous_results: Mapping[int, object], step_num: int
) -> Mapping[str, object] | None:
    step = previous_results.get(step_num)
    if not step or getattr(step, "status", None) != StepStatus.COMPLETED:
        return None

    result = getattr(step, "result", None)
    return result if isinstance(result, Mapping) else None


def _data_quality_assumption(previous_results: Mapping[int, object]) -> str | None:
    step0_result = _completed_step_result(previous_results, 0)
    if step0_result is None:
        return None

    quality_score = step0_result.get("quality_score", 0)
    if quality_score >= 70:
        return "High-quality financial data validated"
    if quality_score >= 50:
        return "Moderate-quality financial data validated"
    return "Limited financial data available"


def _data_source_assumption(previous_results: Mapping[int, object]) -> str | None:
    step2_result = _completed_step_result(previous_results, 2)
    if step2_result is None:
        return None

    data_source = step2_result.get("data_source", "")
    if "fmp_api" in data_source or "cache" in data_source:
        return "Comparable companies selected from same industry and size range"
    return "Comparable companies selected using industry benchmarks"


def _growth_assumption(previous_results: Mapping[int, object]) -> str | None:
    step1_result = _completed_step_result(previous_results, 1)
    if step1_result is None:
        return None

    growth_rate = step1_result.get("growth_rate")
    if growth_rate and growth_rate > 0:
        return "Growth projections based on historical CAGR"
    return None


class AssumptionExtractor:
    """Extracts assumptions from step results."""

    @staticmethod
    def extract(previous_results: Dict[int, Any], is_sole_trader: bool) -> List[str]:
        """
        Extract assumptions from steps 0, 1, 2.

        Args:
            previous_results: Previous step results
            is_sole_trader: Whether business is a sole trader

        Returns:
            List of assumption strings
        """
        assumptions = [
            assumption
            for assumption in (
                _data_quality_assumption(previous_results),
                _data_source_assumption(previous_results),
                _growth_assumption(previous_results),
            )
            if assumption is not None
        ]

        if is_sole_trader:
            assumptions.append(_SOLE_TRADER_ASSUMPTION)

        return assumptions
