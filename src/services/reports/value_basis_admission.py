"""Publication boundaries for source-aware enterprise and shareholder values."""

from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import overload

from src.api.schemas.multiple_build_up import EquityBridge, MultipleBuildUp
from src.api.schemas.stateless_response_schemas import MethodResult
from .stateless_completion_accounts import CompletionAccountBridge

ENTERPRISE_METHODS = frozenset(
    {
        "upswitch_adaptive",
        "ebitda_multiple",
        "sde_multiple",
        "omzet_multiple",
        "revenue_multiple",
        "arr_multiple",
        "dcf",
    }
)


def uses_accounting_basis_policy(request: object) -> bool:
    case = getattr(request, "valuation_case", None)
    evidence = getattr(case, "accounting_evidence", None)
    years = (
        evidence.get("years", [])
        if isinstance(evidence, Mapping)
        else getattr(evidence, "years", [])
    )
    for year in years:
        facts = (
            year.get("reported_facts")
            if isinstance(year, Mapping)
            else getattr(year, "reported_facts", None)
        )
        if isinstance(facts, Mapping) and facts.get("accounting_basis") is not None:
            return True
    return False


def exact_equity_bridge(
    enterprise_value: Decimal,
    bridge: CompletionAccountBridge,
    *,
    working_capital_adjustment: Decimal | None,
    surplus_assets: Decimal | None,
    ownership_fraction: Decimal,
) -> Decimal | None:
    if bridge.unresolved_fields or working_capital_adjustment is None or surplus_assets is None:
        return None
    assert bridge.available_cash is not None and bridge.total_debt_like is not None
    with localcontext() as context:
        context.prec = 60
        return (
            (
                enterprise_value
                + bridge.available_cash
                - bridge.total_debt_like
                + working_capital_adjustment
                + surplus_assets
            )
            * ownership_fraction
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def enterprise_only_method_results(results: Mapping[str, MethodResult]) -> dict[str, MethodResult]:
    """Keep independently calculated EV; remove every unsupported equity projection."""
    output = dict(results)
    for key, result in results.items():
        if key not in ENTERPRISE_METHODS or not result.available:
            continue
        ev = result.enterprise_value
        if ev is None:
            output[key] = result.model_copy(
                update={
                    "available": False,
                    "value": None,
                    "value_low": None,
                    "value_high": None,
                    "equity_value": None,
                    "equity_value_low": None,
                    "equity_value_high": None,
                    "unavailable_reason": "EQUITY_BRIDGE_INCOMPLETE: independent enterprise value unavailable",
                }
            )
            continue
        output[key] = result.model_copy(
            update={
                "value_basis": "enterprise_value",
                "value": ev,
                "value_low": result.enterprise_value_low,
                "value_high": result.enterprise_value_high,
                "equity_value": None,
                "equity_value_low": None,
                "equity_value_high": None,
                "details": remove_equity_projections(result.details),
            }
        )
    return output


# Financial facts and discount inputs such as book equity and the equity risk
# premium remain evidence. Only priced shareholder outputs are unavailable.
_EQUITY_PRICE_KEYS = frozenset(
    {
        "equity_value",
        "equity_value_low",
        "equity_value_mid",
        "equity_value_high",
        "equity_range_low",
        "equity_range_mid",
        "equity_range_high",
        "equity_range",
        "blended_equity_value",
        "equity_bridge",
        "equity_bridge_adjustments",
        "recommended_asking_price",
        "headline_equity_value_low",
        "headline_equity_value_mid",
        "headline_equity_value_high",
        "bridge_equity_value",
        "equity_before_owner_dependency",
        "equity_after_owner_dependency",
        "current_equity_value",
        "pre_common_bridge_blended_equity_value",
        "pre_shareholder_transaction_blended_equity_value",
    }
)


@overload
def remove_equity_projections(value: Mapping[str, object]) -> dict[str, object]: ...


@overload
def remove_equity_projections(value: object) -> object: ...


def remove_equity_projections(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            key: None if str(key) in _EQUITY_PRICE_KEYS else remove_equity_projections(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [remove_equity_projections(item) for item in value]
    return value


def enterprise_only_build_up(
    build_up: MultipleBuildUp | None, unresolved_fields: tuple[str, ...]
) -> MultipleBuildUp | None:
    """Retain the EV calculation and replace the unavailable completion bridge."""
    if build_up is None:
        return None
    return build_up.model_copy(
        update={
            "equity_value": None,
            "equity_bridge": EquityBridge(
                enterprise_value=build_up.enterprise_value,
                equity_status="unavailable_incomplete_bridge",
                unresolved_fields=list(unresolved_fields),
                notes=["Verified completion accounts are required for shareholder value."],
            ),
        }
    )
