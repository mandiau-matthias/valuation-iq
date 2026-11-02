"""Value-context preparation for comprehensive response assembly."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from src.api.routes.valuation.orchestration.executors.comprehensive.response_asking_price import (
    resolve_recommended_asking_fields,
)
from src.api.routes.valuation.orchestration.executors.comprehensive.response_dcf_bridge import (
    canonicalize_dcf_only_bridge,
    is_requested_dcf_only,
    requested_method_signal,
)
from src.api.routes.valuation.orchestration.executors.comprehensive.response_value_normalization import (
    normalize_response_values,
)
from src.utils.decimal_helpers import to_decimal


@dataclass(frozen=True)
class PreparedResponseValues:
    methodology: str
    current_year_data: dict[str, object]
    requested_methodology_raw: object
    requested_dcf_only: bool
    raw_dcf_result: object
    equity_value_low: Decimal
    equity_value_mid: Decimal
    equity_value_high: Decimal
    recommended_asking_price: object
    recommended_asking_multiple: object
    markup_pct: object
    markup_source: str
    markup_reasoning: object
    confidence_level: str
    clamped_confidence_score: int
    dcf_weight: Decimal
    multiples_weight: Decimal


def prepare_response_values(
    *,
    request: object,
    detailed_results: dict[str, object],
    methodology: str,
    equity_value_low: Decimal,
    equity_value_mid: Decimal,
    equity_value_high: Decimal,
    confidence_score: Decimal,
    response_builder: object,
    confidence_scorer: object,
    logger: object,
) -> PreparedResponseValues:
    """Prepare valuation values before schema assembly."""
    confidence_level = confidence_scorer.map_score_to_level(confidence_score)
    current_year_data = _current_year_data(response_builder, request, detailed_results)
    net_debt = _net_debt(current_year_data)
    requested_raw = requested_method_signal(request)
    requested_dcf_only = is_requested_dcf_only(requested_raw)

    dcf_state = _apply_dcf_only_bridge(
        detailed_results=detailed_results,
        requested_dcf_only=requested_dcf_only,
        net_debt=net_debt,
        methodology=methodology,
        equity_value_low=equity_value_low,
        equity_value_mid=equity_value_mid,
        equity_value_high=equity_value_high,
    )
    current_multiple, step_11_result = _multiple_context(detailed_results)
    current_multiple = _implied_current_multiple(
        current_multiple=current_multiple,
        current_year_data=current_year_data,
        equity_value_mid=dcf_state.equity_value_mid,
        net_debt=net_debt,
    )
    asking_fields = resolve_recommended_asking_fields(
        requested_dcf_only=requested_dcf_only,
        detailed_results=detailed_results,
        step_11_result=step_11_result,
        raw_dcf_result=dcf_state.raw_dcf_result,
        equity_value_mid=dcf_state.equity_value_mid,
        net_debt=net_debt,
        current_multiple=current_multiple,
        confidence_level=confidence_level,
        request=request,
    )
    normalized = normalize_response_values(
        logger=logger,
        detailed_results=detailed_results,
        methodology=dcf_state.methodology,
        recommended_asking_price=asking_fields.recommended_asking_price,
        recommended_asking_multiple=asking_fields.recommended_asking_multiple,
        confidence_level=confidence_level,
        confidence_score=confidence_score,
        equity_value_low=dcf_state.equity_value_low,
        equity_value_mid=dcf_state.equity_value_mid,
        equity_value_high=dcf_state.equity_value_high,
    )

    return PreparedResponseValues(
        methodology=dcf_state.methodology,
        current_year_data=current_year_data,
        requested_methodology_raw=requested_raw,
        requested_dcf_only=requested_dcf_only,
        raw_dcf_result=dcf_state.raw_dcf_result,
        equity_value_low=normalized.equity_value_low,
        equity_value_mid=normalized.equity_value_mid,
        equity_value_high=normalized.equity_value_high,
        recommended_asking_price=normalized.recommended_asking_price,
        recommended_asking_multiple=normalized.recommended_asking_multiple,
        markup_pct=asking_fields.markup_pct,
        markup_source=asking_fields.markup_source,
        markup_reasoning=asking_fields.markup_reasoning,
        confidence_level=normalized.confidence_level,
        clamped_confidence_score=normalized.clamped_confidence_score,
        dcf_weight=normalized.dcf_weight,
        multiples_weight=normalized.multiples_weight,
    )


@dataclass(frozen=True)
class _DcfBridgeState:
    methodology: str
    raw_dcf_result: object
    equity_value_low: Decimal
    equity_value_mid: Decimal
    equity_value_high: Decimal


def _current_year_data(
    response_builder: object,
    request: object,
    detailed_results: dict[str, object],
) -> dict[str, object]:
    current_year_data = response_builder.extract_current_year_data(request, detailed_results)
    return current_year_data if isinstance(current_year_data, dict) else {}


def _net_debt(current_year_data: dict[str, object]) -> Decimal:
    total_debt = to_decimal(current_year_data.get("total_debt") or 0)
    cash = to_decimal(current_year_data.get("cash") or 0)
    return total_debt - cash


def _apply_dcf_only_bridge(
    *,
    detailed_results: dict[str, object],
    requested_dcf_only: bool,
    net_debt: Decimal,
    methodology: str,
    equity_value_low: Decimal,
    equity_value_mid: Decimal,
    equity_value_high: Decimal,
) -> _DcfBridgeState:
    raw_dcf_result = detailed_results.get("dcf_valuation")
    if requested_dcf_only and isinstance(raw_dcf_result, dict):
        bridge = canonicalize_dcf_only_bridge(raw_dcf_result, net_debt)
        if bridge is not None:
            detailed_results["dcf_valuation"] = bridge["dcf_valuation"]
            detailed_results["dcf_weight"] = Decimal("1.0")
            detailed_results["multiples_weight"] = Decimal("0.0")
            return _DcfBridgeState(
                methodology="DCF",
                raw_dcf_result=bridge["dcf_valuation"],
                equity_value_low=bridge["equity_value_low"],
                equity_value_mid=bridge["equity_value_mid"],
                equity_value_high=bridge["equity_value_high"],
            )

    return _DcfBridgeState(
        methodology=methodology,
        raw_dcf_result=raw_dcf_result,
        equity_value_low=equity_value_low,
        equity_value_mid=equity_value_mid,
        equity_value_high=equity_value_high,
    )


def _multiple_context(detailed_results: dict[str, object]) -> tuple[object, object]:
    multiples_res = detailed_results.get("multiples_valuation", {})
    if not isinstance(multiples_res, dict):
        return None, None

    current_multiple = multiples_res.get("ebitda_multiple") or multiples_res.get("revenue_multiple")
    step_results = multiples_res.get("_step_results", {})
    if not isinstance(step_results, dict):
        return current_multiple, None

    step_11_output = step_results.get(11)
    step_11_result = (
        step_11_output.result
        if step_11_output is not None and hasattr(step_11_output, "result")
        else None
    )
    return current_multiple, step_11_result


def _implied_current_multiple(
    *,
    current_multiple: object,
    current_year_data: dict[str, object],
    equity_value_mid: Decimal,
    net_debt: Decimal,
) -> object:
    ebitda = (
        to_decimal(current_year_data.get("ebitda"))
        if current_year_data.get("ebitda") is not None
        else None
    )
    if current_multiple is None and ebitda and ebitda > 0:
        return (equity_value_mid + net_debt) / ebitda
    return current_multiple
