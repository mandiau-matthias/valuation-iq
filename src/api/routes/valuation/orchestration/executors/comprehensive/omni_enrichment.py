"""Omni-method enrichment helpers for comprehensive valuation responses."""

from decimal import Decimal
from typing import Optional

from src.api.routes.valuation.orchestration.executors.comprehensive.omni_calculation_inputs import (
    build_omni_calculation_inputs,
)
from src.api.routes.valuation.orchestration.executors.comprehensive.omni_methodology_context import (
    _normalize_methodology_token_for_omni,
    _omni_primary_basis_from_executed_methodology,
    _OmniExecutionContext,
    _resolve_omni_execution_context,
)
from src.api.routes.valuation.orchestration.executors.comprehensive.omni_startup_override import (
    _apply_startup_valuation_override,
)
from src.api.schemas import ValuationRequest, ValuationResponse
from src.domain.omni_calc_coordinator import calculate_all_methods, calculate_weighted_average

# Multiples-family OmniCalc legs are computed GROSS (``calculate_ebitda_result`` &
# siblings apply owner / net-debt bridging but NOT the Step 5/6 size & liquidity
# discounts the primary pipeline applies at the EV level). Weighting a gross leg
# into the user-weighted cover synthesis overstates the cover versus the body
# (VAL-2026 two-brain regression: EUR 582K cover vs EUR 554K body). We reconcile
# the multiples-family legs to the engine's canonical NET multiples equity *for
# the synthesis only*, so the user-weighted cover blends the same single source
# of truth values the body displays. Method results / comparison cards are untouched.
_MULTIPLES_FAMILY_KEYS = (
    "ebitda_multiple",
    "sde_multiple",
    "ev_ebitda",
    "omzet_multiple",
    "revenue_multiple",
)


def _canonical_net_multiples_equity(response: object) -> Optional[Decimal]:
    """Return the engine's net multiples equity value shown in the report body."""
    mv = getattr(response, "multiples_valuation", None)
    if mv is None:
        return None
    for attr in ("equity_value", "enterprise_value"):
        raw = getattr(mv, attr, None)
        if raw is None and isinstance(mv, dict):
            raw = mv.get(attr)
        if raw is None:
            continue
        try:
            val = Decimal(str(raw))
        except (ArithmeticError, ValueError, TypeError):
            continue
        if val > 0:
            return val
    return None


def reconcile_synthesis_multiples_legs(
    methods: dict[str, object],
    response: object,
    logger: Optional[object] = None,
) -> dict[str, object]:
    """Return a synthesis-only copy with gross multiples legs capped to net equity."""
    net_equity = _canonical_net_multiples_equity(response)
    if net_equity is None:
        return methods
    tolerance = net_equity * Decimal("0.01")
    reconciled: dict[str, object] = dict(methods)
    for key in _MULTIPLES_FAMILY_KEYS:
        method = reconciled.get(key)
        if (
            method is None
            or not getattr(method, "available", False)
            or getattr(method, "value", None) is None
        ):
            continue
        try:
            current = Decimal(str(method.value))
        except (ArithmeticError, ValueError, TypeError):
            continue
        if current > net_equity + tolerance:
            details = dict(getattr(method, "details", None) or {})
            details.update(
                {
                    "weighted_synthesis_value_basis": "net_engine",
                    "weighted_synthesis_value_before_bridge": current,
                    "weighted_synthesis_reconciled_to": net_equity,
                    "weighted_synthesis_reconciliation_reason": (
                        "Gross multiples method result reconciled to the canonical "
                        "net engine multiples equity for user-weighted synthesis."
                    ),
                }
            )
            reconciled[key] = method.model_copy(
                update={
                    "value": net_equity,
                    "equity_value": net_equity,
                    "details": details,
                }
            )
            if logger:
                logger.info(
                    "[OmniCalc] Synthesis leg '%s' reconciled to canonical net "
                    "multiples equity (gross %s -> net %s) so the weighted cover "
                    "matches the body",
                    key,
                    str(current),
                    str(net_equity),
                )
    return reconciled


def _attach_weighted_valuation(
    request: ValuationRequest,
    response: ValuationResponse,
    vr: dict[str, object],
    _logger: object,
) -> None:
    user_weights = getattr(request, "user_weights", None)
    if not (user_weights and isinstance(user_weights, dict) and len(user_weights) > 0):
        return

    try:
        weighted_result = calculate_weighted_average(
            methods=reconcile_synthesis_multiples_legs(vr, response, _logger),
            weights=user_weights,
            justification=getattr(request, "user_weight_justification", None),
        )
        response.weighted_valuation = weighted_result.model_dump()
    except ValueError as exc:
        _logger.warning("[OmniCalc] Weighted average failed: %s", exc)


def _enrich_with_omni_calc(
    request: ValuationRequest,
    response: ValuationResponse,
    equity_value_low: Decimal,
    equity_value_mid: Decimal,
    equity_value_high: Decimal,
    dcf_exclusion_reason: Optional[str],
    _logger: object,
    methodology: Optional[str] = None,
) -> None:
    """Compute the omni-calc method map and attach it to the response."""
    omni_inputs = build_omni_calculation_inputs(
        request,
        response,
        equity_value_low=equity_value_low,
        equity_value_mid=equity_value_mid,
        equity_value_high=equity_value_high,
        dcf_exclusion_reason=dcf_exclusion_reason,
        methodology=methodology,
        logger=_logger,
    )
    vr = calculate_all_methods(**omni_inputs.as_calculate_all_methods_kwargs())

    _apply_startup_valuation_override(request, response, vr, _logger)

    response.valuation_results = {k: v.model_dump() for k, v in vr.items()}

    if omni_inputs.fiscal_ebitda > 0 and omni_inputs.country_code == "BE":
        response.fiscal_4x_anchor = Decimal(str(round(omni_inputs.fiscal_ebitda * 4, 2)))

    _attach_weighted_valuation(request, response, vr, _logger)

    _logger.info(
        "[OmniCalc] Enriched comprehensive response with %d methods",
        len(vr),
    )
