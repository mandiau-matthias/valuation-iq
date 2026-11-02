"""
Assumptions Log Builder

Builds structured assumptions log for Info Tab display, documenting all
assumptions made during valuation in Big 4 format.

Academic Reference: Big 4 valuation standards require comprehensive assumptions
documentation for auditability and transparency.
"""

from decimal import Decimal
from typing import TYPE_CHECKING, Dict, List, Optional, TypeAlias

if TYPE_CHECKING:
    from src.services.interfaces.request_response_protocol import (
        ValuationResponseProtocol,
        ValuationRequestProtocol,
    )

from src.utils.core.data_extraction_helpers import extract_step_result
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)

AssumptionEntry: TypeAlias = Dict[str, object]
AssumptionsLog: TypeAlias = Dict[str, List[AssumptionEntry]]
StepResult: TypeAlias = Dict[str, object]


def _empty_assumptions_log() -> AssumptionsLog:
    return {
        "financial_assumptions": [],
        "multiple_assumptions": [],
        "risk_assumptions": [],
    }


def _detailed_step_results(response: object) -> Dict[object, object]:
    detailed_results = getattr(response, "detailed_results", None)
    if not isinstance(detailed_results, dict):
        return {}
    step_results = detailed_results.get("step_results", {})
    return step_results if isinstance(step_results, dict) else {}


def _step_output(step_results: Dict[object, object], step_number: int) -> object | None:
    if step_number in step_results:
        return step_results[step_number]
    return step_results.get(str(step_number))


def _step_result(step_results: Dict[object, object], step_number: int) -> Optional[StepResult]:
    result = extract_step_result(_step_output(step_results, step_number))
    return result if isinstance(result, dict) else None


def _rounded_float(value: object) -> float:
    return float(from_decimal(to_decimal(value)))


def _percentage_value(value: object) -> float:
    percentage = to_decimal(value)
    if abs(percentage) < Decimal("1.0") and percentage != 0:
        percentage *= Decimal("100")
    return float(from_decimal(percentage))


def _first_present(result: StepResult, *keys: str) -> object | None:
    for key in keys:
        value = result.get(key)
        if value is not None:
            return value
    return None


def _append_financial_assumptions(
    assumptions: AssumptionsLog,
    step_results: Dict[object, object],
) -> None:
    step_1_result = _step_result(step_results, 1)
    if not step_1_result:
        return
    ebitda = _first_present(step_1_result, "ebitda", "normalized_ebitda")
    if ebitda is None:
        return
    assumptions["financial_assumptions"].append(
        {
            "assumption": "Normalized EBITDA",
            "value": _rounded_float(ebitda),
            "rationale": "Normalized earnings based on historical performance and adjustments",
            "source": "Step 1: Financial Normalization",
            "confidence": "HIGH",
        }
    )


def _append_base_multiple_assumption(
    assumptions: AssumptionsLog,
    step_results: Dict[object, object],
) -> None:
    step_2_result = _step_result(step_results, 2)
    if not step_2_result:
        return
    base_multiple = _first_present(
        step_2_result,
        "final_ebitda_multiple",
        "ev_ebitda_multiple",
        "ev_ebitda_p50",
    )
    if base_multiple is None:
        return
    assumptions["multiple_assumptions"].append(
        {
            "assumption": "Base EBITDA Multiple",
            "value": _rounded_float(base_multiple),
            "rationale": "P50 median multiple from comparable company analysis",
            "source": "Step 2: Multiple Selection",
            "confidence": "HIGH",
        }
    )


def _append_owner_concentration_assumption(
    assumptions: AssumptionsLog,
    step_results: Dict[object, object],
) -> None:
    step_4_result = _step_result(step_results, 4)
    if not step_4_result:
        return
    adjustment_pct = step_4_result.get("adjustment_percentage")
    if adjustment_pct is None:
        return
    assumptions["risk_assumptions"].append(
        {
            "assumption": "Owner Concentration Discount",
            "value": _rounded_float(adjustment_pct),
            "rationale": (
                f"{step_4_result.get('risk_level')} owner dependency risk based on "
                "owner/employee ratio"
            ),
            "source": "Step 4: Owner Concentration Analysis",
            "confidence": "MEDIUM",
        }
    )


def _append_size_discount_assumption(
    assumptions: AssumptionsLog,
    step_results: Dict[object, object],
) -> None:
    step_5_result = _step_result(step_results, 5)
    if not step_5_result:
        return
    size_discount = step_5_result.get("size_discount_percentage")
    if size_discount is None:
        return
    assumptions["risk_assumptions"].append(
        {
            "assumption": "Size Discount",
            "value": _percentage_value(size_discount),
            "rationale": f"Size effect premium for {step_5_result.get('size_tier')} revenue tier",
            "source": "Step 5: Size Discount Analysis",
            "confidence": "MEDIUM",
        }
    )


def _append_liquidity_discount_assumption(
    assumptions: AssumptionsLog,
    step_results: Dict[object, object],
) -> None:
    step_6_result = _step_result(step_results, 6)
    if not step_6_result:
        return
    liquidity_discount = step_6_result.get("total_discount_percentage")
    if liquidity_discount is None:
        return
    assumptions["risk_assumptions"].append(
        {
            "assumption": "Liquidity Discount (DLOM)",
            "value": _percentage_value(liquidity_discount),
            "rationale": "Private company illiquidity discount",
            "source": "Step 6: Liquidity Discount Analysis",
            "confidence": "MEDIUM",
        }
    )


def _append_risk_assumptions(
    assumptions: AssumptionsLog,
    step_results: Dict[object, object],
) -> None:
    _append_owner_concentration_assumption(assumptions, step_results)
    _append_size_discount_assumption(assumptions, step_results)
    _append_liquidity_discount_assumption(assumptions, step_results)


def _append_final_multiple_assumption(
    assumptions: AssumptionsLog,
    *,
    response: object,
    step_results: Dict[object, object],
) -> None:
    equity_value_mid = getattr(response, "equity_value_mid", None)
    if not equity_value_mid:
        return
    step_1_result = _step_result(step_results, 1)
    if not step_1_result:
        return
    ebitda = step_1_result.get("ebitda") or step_1_result.get("normalized_ebitda")
    if not ebitda or to_decimal(ebitda) <= 0:
        return
    try:
        final_multiple = to_decimal(equity_value_mid) / to_decimal(ebitda)
    except (ValueError, TypeError, ZeroDivisionError):
        return

    assumptions["multiple_assumptions"].append(
        {
            "assumption": "Final Adjusted Multiple",
            "value": float(from_decimal(final_multiple)),
            "rationale": "Risk-adjusted multiple after all quality and risk adjustments",
            "source": "Multiple Journey (Steps 2-6)",
            "confidence": "HIGH",
        }
    )


class AssumptionsLogBuilder:
    """
    Builds structured assumptions log for valuation reports.

    Extracts assumptions from step results and structures them in Big 4 format:
    - Financial Assumptions
    - Multiple Assumptions
    - Risk Assumptions
    """

    @staticmethod
    def build_assumptions_log(
        response: "ValuationResponseProtocol",
        _request: "ValuationRequestProtocol",
    ) -> AssumptionsLog:
        """
        Build structured assumptions log.

        WHAT: Extracts all assumptions from step results
        WHY: Provides transparency and auditability (Big 4 Manager Persona requirement)
        HOW: Extracts assumptions from each step and categorizes them
        WHEN: Called during Info Tab HTML generation

        Args:
            response: ValuationResponse with detailed_results
            request: ValuationRequest with input data

        Returns:
            Dictionary with categorized assumptions lists
        """
        assumptions = _empty_assumptions_log()

        try:
            step_results = _detailed_step_results(response)
            if not step_results:
                return assumptions
            _append_financial_assumptions(assumptions, step_results)
            _append_base_multiple_assumption(assumptions, step_results)
            _append_risk_assumptions(assumptions, step_results)
            _append_final_multiple_assumption(
                assumptions,
                response=response,
                step_results=step_results,
            )

            return assumptions

        except Exception as e:
            logger.error(
                "[ASSUMPTIONS-LOG-BUILDER] Failed to build assumptions log",
                extra={
                    "company_name": getattr(response, "company_name", None),
                    "error": str(e),
                },
                exc_info=True,
            )
            return assumptions
