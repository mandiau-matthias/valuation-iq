"""
Waterfall Builder Module

Functions for building valuation waterfall from response data.
"""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from src.api.schemas import ValuationResponse, ValuationRequest

from decimal import Decimal

from src.services.infrastructure.step_data_builder import get_step_output
from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


def _calculate_adjustment_percentage(
    adjustment: Decimal, before_value: Decimal
) -> Optional[Decimal]:
    """
    Calculate adjustment percentage from adjustment amount and before value.

    Args:
        adjustment: Adjustment amount (Decimal)
        before_value: Value before adjustment (Decimal)

    Returns:
        Adjustment percentage as Decimal, or None if calculation fails
    """
    if before_value is None or before_value == 0:
        return None

    try:
        adjustment_decimal = to_decimal(adjustment)
        current_value_decimal = to_decimal(before_value)
        if current_value_decimal != Decimal("0"):
            adjustment_percentage_decimal = (adjustment_decimal / current_value_decimal) * Decimal(
                "100"
            )
            return adjustment_percentage_decimal  # Return Decimal, not float
    except (TypeError, ZeroDivisionError):
        return None

    return None


def _build_waterfall_step(
    step_name: str,
    before_value: Decimal,
    adjustment: Optional[Decimal],
    after_value: Decimal,
    calculation: str,
) -> Dict[str, Any]:
    """
    Build a single waterfall step with calculated adjustment percentage.

    Args:
        step_name: Name of the step
        before_value: Value before adjustment (Decimal)
        adjustment: Adjustment amount (Decimal)
        after_value: Value after adjustment (Decimal)
        calculation: Calculation description

    Returns:
        Waterfall step dictionary (values converted to float for JSON serialization)
    """
    adjustment_percentage = None
    if adjustment is not None:
        adjustment_percentage = _calculate_adjustment_percentage(adjustment, before_value)

    return {
        "step_name": step_name,
        "before_value": from_decimal(before_value),  # Convert to float for JSON serialization
        "adjustment": (
            from_decimal(adjustment) if adjustment is not None else None
        ),  # Convert to float for JSON serialization
        "adjustment_percentage": (
            from_decimal(adjustment_percentage) if adjustment_percentage is not None else None
        ),  # Convert to float for JSON serialization
        "after_value": from_decimal(after_value),  # Convert to float for JSON serialization
        "calculation": calculation,
    }


def get_owner_concentration_adjustment(response: ValuationResponseProtocol) -> Optional[Decimal]:
    """
    Get owner concentration adjustment amount from response.

    UPDATED 2025-12-20: Fixed to look for correct field names from Step 4.

    Args:
        response: ValuationResponse containing calculation results

    Returns:
        Owner concentration adjustment amount as Decimal, or None if not available
    """
    # PRIMARY: Get directly from Step 4 output (most reliable)
    step_4_result = get_step_output(response, 4)
    if step_4_result and isinstance(step_4_result, dict):
        # Try owner_concentration_adjustment first (decimal format, e.g., "-0.03")
        owner_conc_adj = step_4_result.get("owner_concentration_adjustment")
        if owner_conc_adj is not None:
            # This is the adjustment as a decimal factor (e.g., -0.03 for -3%)
            # Multiply by base EV to get adjustment amount in euros
            base_ev = step_4_result.get("enterprise_value_mid_before_adjustment")
            if base_ev is not None:
                return to_decimal(owner_conc_adj) * to_decimal(base_ev)

        # Fallback: Try ev_change field
        ev_change = step_4_result.get("ev_change")
        if ev_change is not None:
            return to_decimal(ev_change)

    # SECONDARY: Try multiples_valuation.owner_concentration (legacy)
    if not response.multiples_valuation:
        return None

    owner_conc = response.multiples_valuation.owner_concentration
    if owner_conc and isinstance(owner_conc, dict):
        adjustment_factor = owner_conc.get("adjustment_factor")
        if adjustment_factor is not None:
            base_value = response.multiples_valuation.base_value
            if base_value:
                return to_decimal(base_value) * to_decimal(adjustment_factor)

    return None


def _add_owner_concentration_step(
    response: "ValuationResponseProtocol", current_value: Decimal, steps: List[Dict[str, Any]]
) -> Optional[Decimal]:
    """
    Add owner concentration adjustment step and return updated value.

    ENHANCED: 2025-12-20 - Always show this step for Big 4 transparency,
    even when adjustment is 0% (LOW risk tier).
    """
    owner_conc_adjustment = get_owner_concentration_adjustment(response)

    # If no adjustment found, try to get from Step 4 output
    if owner_conc_adjustment is None:
        step_4_result = get_step_output(response, 4)
        if step_4_result and isinstance(step_4_result, dict):
            adjustment_pct = step_4_result.get("adjustment_percentage", 0)
            if adjustment_pct is not None:
                owner_conc_adjustment = current_value * to_decimal(adjustment_pct) / Decimal("100")

    # If still no adjustment, check if step executed with 0% adjustment (LOW risk)
    if owner_conc_adjustment is None or owner_conc_adjustment == 0:
        step_4_result = get_step_output(response, 4)
        if step_4_result and isinstance(step_4_result, dict):
            # Step executed but with 0% adjustment (LOW risk tier)
            steps.append(
                _build_waterfall_step(
                    step_name="Owner Concentration Assessment",
                    before_value=current_value,
                    adjustment=Decimal("0.0"),
                    after_value=current_value,
                    calculation="Owner concentration assessed as LOW risk. No adjustment applied.",
                )
            )
            return current_value
        # Step didn't execute at all
        return None

    adjustment_decimal = to_decimal(owner_conc_adjustment)
    after_value_decimal = current_value + adjustment_decimal

    # Get risk tier from Step 4 for better description
    step_4_result = get_step_output(response, 4)
    risk_tier = "UNKNOWN"
    if step_4_result and isinstance(step_4_result, dict):
        risk_tier = step_4_result.get("risk_tier", "UNKNOWN")

    calculation = (
        f"Owner concentration {risk_tier} risk tier. "
        f"Applied {abs(float(adjustment_decimal / current_value * 100)):.1f}% "
        f'{"discount" if adjustment_decimal < 0 else "premium"}. '
        f"Key person risk assessment per Damodaran (2012)."
    )

    steps.append(
        _build_waterfall_step(
            step_name="Owner Concentration Adjustment",
            before_value=current_value,
            adjustment=adjustment_decimal,
            after_value=after_value_decimal,
            calculation=calculation,
        )
    )
    return after_value_decimal  # Return Decimal


def _add_revenue_trend_step(
    response: "ValuationResponseProtocol", current_value: Decimal, steps: List[Dict[str, Any]]
) -> Optional[Decimal]:
    """
    Add revenue trend adjustment step with correlation-aware calibration transparency.

    ADDED: 2025-12-20 per comprehensive audit findings.
    ENHANCED: 2025-12-20 to show both base and calibrated discounts for transparency.

    This step shows the revenue decline discount applied in Step 4.5, including
    correlation-aware calibration details when size discount is also present.
    """
    # Get Step 4.5 output
    step_45_result = get_step_output(response, 4.5)
    if not step_45_result or not isinstance(step_45_result, dict):
        return None

    # Get adjustment percentage from step result (this is the CALIBRATED discount)
    revenue_trend_adjustment = step_45_result.get("revenue_trend_adjustment")
    if revenue_trend_adjustment is None:
        return None

    adjustment_pct = to_decimal(revenue_trend_adjustment)

    # If no adjustment (growth scenario), still show the step for transparency
    if adjustment_pct == Decimal("0.0"):
        steps.append(
            _build_waterfall_step(
                step_name="Revenue Trend Assessment",
                before_value=current_value,
                adjustment=Decimal("0.0"),
                after_value=current_value,
                calculation="Revenue growing or stable. No decline discount applied.",
            )
        )
        return current_value

    # Calculate adjustment amount
    adjustment_decimal = current_value * adjustment_pct
    after_value_decimal = current_value + adjustment_decimal  # adjustment_pct is negative

    # Get additional context from step result
    yoy_growth = step_45_result.get("yoy_growth_percentage", 0)
    severity = step_45_result.get("severity", "unknown")

    # Check if correlation calibration was applied
    calibration_applied = step_45_result.get("calibration_applied", False)
    base_adjustment = step_45_result.get("base_revenue_trend_adjustment")
    size_tier = step_45_result.get("size_tier", "unknown")

    # Build calculation description with calibration transparency
    if calibration_applied and base_adjustment is not None:
        base_adjustment_pct = to_decimal(base_adjustment)

        calculation = (
            f"Revenue declined {abs(yoy_growth):.1f}% YoY. "
            f"Base discount: {abs(float(base_adjustment_pct * 100)):.1f}% (Damodaran 2012). "
            f'Calibrated to {abs(float(adjustment_pct * 100)):.1f}% for {size_tier.replace("_", " ")} company. '
            f"Correlation-aware adjustment accounts for size × revenue trend interaction (r ≈ 0.40). "
            f"Methodology: McKinsey (2015) Ch. 11, prevents over-discounting."
        )

        logger.info(
            f"Added revenue trend step to waterfall WITH calibration: "
            f"{float(current_value):,.0f} → {float(after_value_decimal):,.0f} "
            f"(base: {float(base_adjustment_pct * 100):.1f}%, "
            f"calibrated: {float(adjustment_pct * 100):.1f}%)"
        )
    else:
        # No calibration applied
        calculation = (
            f"Revenue declined {abs(yoy_growth):.1f}% YoY. "
            f"Applied {abs(float(adjustment_pct * 100)):.1f}% decline discount "
            f'({severity.replace("_", " ").title()}). '
            f"Damodaran (2012) distressed asset framework."
        )

        logger.info(
            f"Added revenue trend step to waterfall WITHOUT calibration: "
            f"{float(current_value):,.0f} → {float(after_value_decimal):,.0f} "
            f"({float(adjustment_pct * 100):.1f}%)"
        )

    steps.append(
        _build_waterfall_step(
            step_name="Revenue Trend Discount",
            before_value=current_value,
            adjustment=adjustment_decimal,
            after_value=after_value_decimal,
            calculation=calculation,
        )
    )

    return after_value_decimal  # Return Decimal


def _add_size_discount_step(
    multiples: Any, current_value: Decimal, steps: List[Dict[str, Any]]
) -> Optional[Decimal]:
    """
    Add size discount step and return updated value.

    ENHANCED: 2025-12-20 - Added academic citations for transparency.
    """
    if not multiples.size_discount:
        return None

    # BANK-GRADE: multiples.size_discount is a PERCENTAGE (e.g., -0.05 for -5%)
    # Convert to adjustment amount: current_value × percentage
    size_discount_pct = to_decimal(multiples.size_discount)
    adjustment_decimal = current_value * size_discount_pct
    after_value_decimal = current_value + adjustment_decimal

    # Enhanced calculation description with academic sources
    calculation = (
        f"Size discount for micro-cap/small company. "
        f"Applied {abs(float(size_discount_pct * 100)):.1f}% discount per "
        f"Fama-French (1992), Ibbotson SBBI (2024). "
        f"Reflects systematic risk premium for smaller companies."
    )

    steps.append(
        _build_waterfall_step(
            step_name="Size Discount",
            before_value=current_value,
            adjustment=adjustment_decimal,
            after_value=after_value_decimal,
            calculation=calculation,
        )
    )
    return after_value_decimal  # Return Decimal


def _add_liquidity_discount_step(
    multiples: Any, current_value: Decimal, steps: List[Dict[str, Any]]
) -> Optional[Decimal]:
    """
    Add liquidity discount step and return updated value.

    ENHANCED: 2025-12-20 - Always show this step for Big 4 transparency,
    even when skipped for SMEs.
    """
    # Check if liquidity discount was applied
    if not multiples.liquidity_discount or multiples.liquidity_discount == 0:
        # ALWAYS add step to show it was considered but skipped
        steps.append(
            _build_waterfall_step(
                step_name="Liquidity Discount",
                before_value=current_value,
                adjustment=Decimal("0.0"),
                after_value=current_value,
                calculation=(
                    "Illiquidity discount skipped for SME valuations. "
                    "Database multiples already reflect private company illiquidity "
                    "(Koeplin 2000, Officer 2007). Applying additional discount would "
                    "result in double-counting."
                ),
            )
        )
        return current_value

    # BANK-GRADE: multiples.liquidity_discount is a PERCENTAGE (e.g., -0.17 for -17%)
    # Convert to adjustment amount: current_value × percentage
    liquidity_discount_pct = to_decimal(multiples.liquidity_discount)
    adjustment_decimal = current_value * liquidity_discount_pct
    adjusted_ev = getattr(multiples, "adjusted_enterprise_value", None)
    after_value_decimal = (
        to_decimal(adjusted_ev) if adjusted_ev is not None else current_value + adjustment_decimal
    )
    steps.append(
        _build_waterfall_step(
            step_name="Liquidity Discount",
            before_value=current_value,
            adjustment=adjustment_decimal,
            after_value=after_value_decimal,
            calculation=f'Liquidity {"discount" if adjustment_decimal < 0 else "premium"} applied',
        )
    )
    return after_value_decimal  # Return Decimal


def _get_net_debt(
    response: "ValuationResponseProtocol", request: "ValuationRequestProtocol"
) -> Decimal:
    """Extract or calculate net debt from step results or request data."""
    step_7_result = get_step_output(response, 7)
    if step_7_result and step_7_result.get("outputs"):
        outputs = step_7_result.get("outputs", {})
        if isinstance(outputs, dict):
            net_debt = outputs.get("net_debt")
            if net_debt is None:
                net_debt = outputs.get("inputs", {}).get("net_debt")
            if net_debt is None:
                net_debt = Decimal("0")
            if net_debt != Decimal("0"):
                return to_decimal(net_debt)

    # Fallback: Calculate from request data
    if request.current_year_data:
        _td = getattr(request.current_year_data, "total_debt", None)
        total_debt = _td if _td is not None else Decimal("0")
        _c = getattr(request.current_year_data, "cash", None)
        cash = _c if _c is not None else Decimal("0")
        total_debt_decimal = to_decimal(total_debt)
        cash_decimal = to_decimal(cash)
        net_debt_decimal = total_debt_decimal - cash_decimal
        return net_debt_decimal  # Return Decimal

    return Decimal("0")


def _add_ev_to_equity_step(
    multiples: Any,
    response: "ValuationResponseProtocol",
    request: ValuationRequestProtocol,
    current_value: Decimal,
    steps: List[Dict[str, Any]],
) -> Optional[Decimal]:
    """Add EV to equity conversion step and return updated value."""
    if multiples.adjusted_equity_value is None:
        return None

    net_debt_decimal = _get_net_debt(response, request)
    adjustment_decimal = -net_debt_decimal  # Negative because we subtract debt
    equity_value_decimal = to_decimal(multiples.adjusted_equity_value)
    steps.append(
        _build_waterfall_step(
            step_name="EV to Equity Conversion",
            before_value=current_value,
            adjustment=adjustment_decimal,
            after_value=equity_value_decimal,
            calculation=f"Adjusted EV - Net Debt = {from_decimal(current_value)} - {from_decimal(net_debt_decimal)}",
        )
    )
    return equity_value_decimal  # Return Decimal


def _add_ownership_adjustment_step(
    response: "ValuationResponseProtocol", current_value: Decimal, steps: List[Dict[str, Any]]
) -> None:
    """Add ownership adjustment step."""
    if not response.owner_dependency_adjustment:
        return

    adjustment_decimal = to_decimal(response.owner_dependency_adjustment)
    equity_value_decimal = to_decimal(response.equity_value_mid)
    steps.append(
        _build_waterfall_step(
            step_name="Ownership Adjustment",
            before_value=current_value,
            adjustment=adjustment_decimal,
            after_value=equity_value_decimal,
            calculation=f'Owner dependency {"discount" if adjustment_decimal < 0 else "premium"} applied',
        )
    )


def _initial_metric_from_step_results(
    response: "ValuationResponseProtocol",
) -> tuple[Optional[Dict[str, Any]], Optional[Decimal], str, Optional[Any]]:
    """Resolve Step 2/Step 1 market metric hints before object fallbacks."""
    step_2_result = get_step_output(response, 2)
    metric_value = None
    metric_type = "EBITDA"
    unadjusted_multiple = None

    if step_2_result and isinstance(step_2_result, dict):
        primary_method = step_2_result.get("primary_method", "EV/EBITDA")
        metric_type = "Revenue" if primary_method == "EV/Revenue" else "EBITDA"
        unadjusted_multiple = step_2_result.get(
            "ev_revenue_multiple" if metric_type == "Revenue" else "ev_ebitda_multiple"
        )

        step_1_result = get_step_output(response, 1)
        if step_1_result and isinstance(step_1_result, dict):
            metric_value = to_decimal(step_1_result.get(metric_type.lower(), 0))

    return step_2_result, metric_value, metric_type, unadjusted_multiple


def _resolve_unadjusted_multiple(
    multiples: Any,
    response: "ValuationResponseProtocol",
    metric_value: Optional[Decimal],
    metric_type: str,
    unadjusted_multiple: Optional[Any],
) -> tuple[Decimal, str]:
    """Resolve the starting market multiple with legacy fallbacks preserved."""
    if unadjusted_multiple is not None:
        return to_decimal(unadjusted_multiple), metric_type

    if hasattr(multiples, "ebitda_multiple") and multiples.ebitda_multiple:
        return to_decimal(multiples.ebitda_multiple), "EBITDA"

    if hasattr(multiples, "revenue_multiple") and multiples.revenue_multiple:
        return to_decimal(multiples.revenue_multiple), "Revenue"

    if multiples.base_value and metric_value and metric_value > 0:
        return to_decimal(multiples.base_value) / metric_value, metric_type

    if hasattr(multiples, "base_value") and multiples.base_value:
        logger.warning(
            "Using default multiple for waterfall (could not determine from steps)",
            extra={
                "company_name": (
                    response.company_name if hasattr(response, "company_name") else "unknown"
                )
            },
        )
        return Decimal("4.0"), metric_type

    return Decimal("0.0"), metric_type


def _metric_from_current_year_data(
    request: ValuationRequestProtocol,
) -> tuple[Optional[Decimal], Optional[str]]:
    if not request or not hasattr(request, "current_year_data") or not request.current_year_data:
        return None, None

    if hasattr(request.current_year_data, "ebitda") and request.current_year_data.ebitda:
        return to_decimal(request.current_year_data.ebitda), "EBITDA"

    if hasattr(request.current_year_data, "revenue") and request.current_year_data.revenue:
        return to_decimal(request.current_year_data.revenue), "Revenue"

    return None, None


def _metric_from_multiples_backsolve(multiples: Any) -> Optional[Decimal]:
    if not (hasattr(multiples, "ebitda_valuation") and hasattr(multiples, "ebitda_multiple")):
        return None

    if multiples.ebitda_multiple and multiples.ebitda_multiple != 0 and multiples.ebitda_valuation:
        return to_decimal(multiples.ebitda_valuation / multiples.ebitda_multiple)

    return None


def _resolve_metric_value(
    request: ValuationRequestProtocol,
    multiples: Any,
    response: "ValuationResponseProtocol",
    metric_value: Optional[Decimal],
    metric_type: str,
) -> tuple[Decimal, str]:
    """Resolve the value multiplied by the starting market multiple."""
    if metric_value is not None and metric_value != 0:
        return metric_value, metric_type

    request_metric_value, request_metric_type = _metric_from_current_year_data(request)
    if request_metric_value is not None:
        return request_metric_value, request_metric_type or metric_type

    backsolved_metric_value = _metric_from_multiples_backsolve(multiples)
    if backsolved_metric_value is not None:
        return backsolved_metric_value, "EBITDA"

    logger.warning(
        "Using default metric value for waterfall (could not determine from request)",
        extra={
            "company_name": (
                response.company_name if hasattr(response, "company_name") else "unknown"
            )
        },
    )
    return Decimal("100000"), metric_type


def _add_market_consensus_step(
    *,
    steps: List[Dict[str, Any]],
    metric_type: str,
    metric_value: Decimal,
    current_multiple: Decimal,
) -> Decimal:
    current_value = current_multiple * metric_value
    steps.append(
        {
            "step_name": "Market Consensus (Unadjusted)",
            "before_value": None,
            "adjustment": None,
            "adjustment_percentage": None,
            "after_value": from_decimal(current_value),
            "calculation": f"{metric_type} × {from_decimal(current_multiple)}x base multiple",
        }
    )
    return current_value


def _add_sme_market_calibration_step(
    *,
    steps: List[Dict[str, Any]],
    step_2_result: Optional[Dict[str, Any]],
    metric_type: str,
    metric_value: Decimal,
    current_value: Decimal,
    current_multiple: Decimal,
) -> tuple[Decimal, Decimal]:
    if not step_2_result or not isinstance(step_2_result, dict):
        return current_value, current_multiple

    sme_cal = step_2_result.get("sme_calibration", {})
    if not isinstance(sme_cal, dict):
        return current_value, current_multiple

    cal_details = sme_cal.get(metric_type.lower() + "_multiple", {})
    raw = to_decimal(cal_details.get("raw", 0))
    final = to_decimal(cal_details.get("final", 0))
    if raw <= 0 or final <= 0 or final == raw:
        return current_value, current_multiple

    multiple_adj = final - raw
    val_adj = multiple_adj * metric_value
    after_val = current_value + val_adj
    steps.append(
        _build_waterfall_step(
            step_name="SME Market Calibration",
            before_value=current_value,
            adjustment=val_adj,
            after_value=after_val,
            calculation="Multiple calibrated for SME scale and market liquidity",
        )
    )
    return after_val, final


def _add_quality_calibration_step(
    *,
    response: "ValuationResponseProtocol",
    steps: List[Dict[str, Any]],
    metric_value: Decimal,
    current_value: Decimal,
    current_multiple: Decimal,
) -> tuple[Decimal, Decimal]:
    step_2_5_result = get_step_output(response, 2.5)
    if not step_2_5_result or not isinstance(step_2_5_result, dict):
        return current_value, current_multiple

    quality_adj = to_decimal(step_2_5_result.get("quality_multiple_adjustment", 0))
    if quality_adj == 0:
        return current_value, current_multiple

    val_adj = quality_adj * metric_value
    after_val = current_value + val_adj
    steps.append(
        _build_waterfall_step(
            step_name="Quality & Volatility Calibration",
            before_value=current_value,
            adjustment=val_adj,
            after_value=after_val,
            calculation="Multiple adjusted for earnings quality and margin stability",
        )
    )
    return after_val, current_multiple + quality_adj


def _initial_waterfall_state(
    response: "ValuationResponseProtocol",
    request: ValuationRequestProtocol,
    multiples: Any,
    steps: List[Dict[str, Any]],
) -> tuple[Decimal, Decimal]:
    step_2_result, metric_value, metric_type, unadjusted_multiple = (
        _initial_metric_from_step_results(response)
    )
    current_multiple, metric_type = _resolve_unadjusted_multiple(
        multiples,
        response,
        metric_value,
        metric_type,
        unadjusted_multiple,
    )
    metric_value, metric_type = _resolve_metric_value(
        request,
        multiples,
        response,
        metric_value,
        metric_type,
    )

    current_value = _add_market_consensus_step(
        steps=steps,
        metric_type=metric_type,
        metric_value=metric_value,
        current_multiple=current_multiple,
    )
    current_value, current_multiple = _add_sme_market_calibration_step(
        steps=steps,
        step_2_result=step_2_result,
        metric_type=metric_type,
        metric_value=metric_value,
        current_value=current_value,
        current_multiple=current_multiple,
    )
    return _add_quality_calibration_step(
        response=response,
        steps=steps,
        metric_value=metric_value,
        current_value=current_value,
        current_multiple=current_multiple,
    )


def build_valuation_waterfall(
    response: "ValuationResponseProtocol", request: ValuationRequestProtocol
) -> Optional[Dict[str, Any]]:
    """
    Build valuation waterfall showing step-by-step adjustments from base EV to final equity value.

    Args:
        response: ValuationResponse containing calculation results
        request: Original ValuationRequest for context

    Returns:
        Dictionary with waterfall steps and summary, or None if no multiples valuation
    """
    if not response.multiples_valuation:
        return None

    multiples = response.multiples_valuation
    valuation_waterfall_steps = []
    current_value, _current_multiple = _initial_waterfall_state(
        response,
        request,
        multiples,
        valuation_waterfall_steps,
    )

    # --- PHASE 2: VALUE DISCOUNTS & STRUCTURAL ADJUSTMENTS ---
    # ENHANCED 2025-12-20: Added Step 4.5 (Revenue Trend) and improved transparency

    # Step 4: Owner Concentration
    updated_value = _add_owner_concentration_step(
        response, current_value, valuation_waterfall_steps
    )
    if updated_value is not None:
        current_value = updated_value

    # Step 4.5: Revenue Trend Adjustment (NEW - 2025-12-20)
    updated_value = _add_revenue_trend_step(response, current_value, valuation_waterfall_steps)
    if updated_value is not None:
        current_value = updated_value

    # Step 5: Size Discount
    updated_value = _add_size_discount_step(multiples, current_value, valuation_waterfall_steps)
    if updated_value is not None:
        current_value = updated_value

    # Step 6: Liquidity Discount (ALWAYS shown, even when skipped)
    updated_value = _add_liquidity_discount_step(
        multiples, current_value, valuation_waterfall_steps
    )
    if updated_value is not None:
        current_value = updated_value

    # Step 7: EV to Equity
    updated_value = _add_ev_to_equity_step(
        multiples, response, request, current_value, valuation_waterfall_steps
    )
    if updated_value is not None:
        current_value = updated_value

    # Step 8: Ownership Adjustment
    _add_ownership_adjustment_step(response, current_value, valuation_waterfall_steps)

    if not valuation_waterfall_steps:
        return None

    # Calculate total adjustments using Decimal
    total_adjustments_decimal = Decimal("0")
    for step in valuation_waterfall_steps:
        adjustment = step.get("adjustment")
        if adjustment is not None:
            total_adjustments_decimal += to_decimal(adjustment)

    return {
        "steps": valuation_waterfall_steps,
        "summary": {
            "starting_value": from_decimal(valuation_waterfall_steps[0]["after_value"]),
            "final_value": (
                from_decimal(to_decimal(response.equity_value_mid))
                if response.equity_value_mid
                else None
            ),
            "total_adjustments": from_decimal(total_adjustments_decimal),
        },
    }
