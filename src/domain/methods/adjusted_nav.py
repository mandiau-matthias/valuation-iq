"""Adjusted NAV (Gecorrigeerde Netto Actiefwaarde) method wrapper."""

from collections.abc import Mapping
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Optional

from src.api.schemas.stateless_api import MethodResult
from src.domain.asset_based_support import calculate_adjusted_nav_payload
from src.domain.asset_nav_core import ADJUSTED_NAV_LABEL
from src.domain.financial_arithmetic import decimal_number


def _reconciled_asset_components(
    balance_sheet: Mapping[str, object],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Bound legacy modeled components to assets remaining after observed amounts."""
    payload = dict(balance_sheet)
    if payload.get("total_assets") is None:
        return payload, []
    total: Decimal = decimal_number(payload["total_assets"], "total assets")
    if total <= 0:
        return payload, []
    known = Decimal(0)
    for field in ("cash", "accounts_receivable", "inventory"):
        if payload.get(field) is not None:
            amount: Decimal = decimal_number(payload[field], field)
            if amount < 0:
                raise ValueError(f"{field} must be nonnegative for asset reconciliation")
            known += amount
    if known > total:
        raise ValueError("Observed cash, receivables and inventory exceed total assets")
    remaining = total - known
    assumptions: list[dict[str, object]] = []
    for field, share in (("accounts_receivable", Decimal(".20")), ("inventory", Decimal(".15"))):
        if payload.get(field) is None:
            amount = min(total * share, remaining)
            payload[field] = amount
            remaining -= amount
            assumptions.append(
                {
                    "field": field,
                    "amount": amount,
                    "reported_value": None,
                    "status": "modeled_scenario",
                    "rule": "legacy_share_capped_at_unallocated_total_assets",
                    "assumed_share": share,
                    "is_observed_zero": False,
                }
            )
    return payload, assumptions


def calculate_adjusted_nav_result(
    *,
    company_name: str,
    industry: str,
    business_model: str,
    founding_year: Optional[int],
    reporting_year: Optional[int],
    revenue: float,
    ebitda: float,
    ownership_multiplier: Decimal,
    country_code: str,
    balance_sheet: Optional[Mapping[str, object]],
    business_context: Optional[Mapping[str, object]],
) -> MethodResult:
    """Adjusted NAV (Gecorrigeerde Netto Actiefwaarde) valuation.

    Thin adapter: delegates the balance-sheet revaluation to
    ``asset_based_support.calculate_adjusted_nav_payload`` and maps the
    resulting payload onto a ``MethodResult``.
    """
    try:
        ownership = decimal_number(ownership_multiplier, "ownership multiplier")
        if not Decimal(0) <= ownership <= Decimal(1):
            raise ValueError("Ownership multiplier must fall between zero and one.")
        asset_assumptions: list[dict[str, object]] = []
        if balance_sheet is not None:
            balance_sheet, asset_assumptions = _reconciled_asset_components(balance_sheet)
            for field in ("total_assets", "total_liabilities", "total_equity"):
                if balance_sheet.get(field) is not None:
                    decimal_number(balance_sheet[field], field)
    except ValueError as exc:
        return MethodResult(
            value=None,
            method_key="adjusted_nav",
            label=ADJUSTED_NAV_LABEL,
            available=False,
            unavailable_reason=str(exc),
        )
    # Existing NAV quantizers inherit a context: enforce the declared policy.
    with localcontext() as context:
        context.rounding = ROUND_HALF_EVEN
        payload = calculate_adjusted_nav_payload(
            company_name=company_name,
            industry=industry,
            business_model=business_model,
            founding_year=founding_year,
            reporting_year=reporting_year,
            revenue=revenue,
            ebitda=ebitda,
            ownership_multiplier=ownership if ownership != 0 else Decimal(1),
            country_code=country_code,
            balance_sheet=dict(balance_sheet) if balance_sheet is not None else None,
            business_context=dict(business_context) if business_context is not None else None,
        )

    details = dict(payload.get("details") or {})
    details["modeled_asset_components"] = asset_assumptions
    details["value_basis"] = "equity_value"
    details["ownership_multiplier"] = ownership
    details["range_basis"] = {
        "schema_version": "valuation_range_basis.v1",
        "kind": "assumed_nav_spread",
        "assumed_spread": Decimal("0.10"),
        "empirical_percentiles": False,
        "statistical_coverage": None,
    }
    # NAV already subtracts all liabilities; it must not receive a second debt bridge.
    details["additional_ev_to_equity_bridge_required"] = False
    if payload.get("available") and ownership == 0:
        for field in ("equity_value", "equity_value_low", "equity_value_high"):
            payload[field] = Decimal("0.00")
        details["equity_range_low"] = details["equity_range_high"] = Decimal("0.00")
    if payload.get("available"):
        details["canonical_equity_range"] = {
            "low": payload.get("equity_value_low"),
            "mid": payload.get("equity_value"),
            "high": payload.get("equity_value_high"),
        }
    # The legacy negative-path metadata is approximate; retain it visibly without
    # presenting a float round-trip as exact source-money evidence.
    elif details.get("corrected_nav") is not None:
        details["debt_overhang"] = {
            "full_company_equity_before_floor": details["corrected_nav"],
            "encoding": "legacy_approximate_numeric_metadata",
        }

    return MethodResult(
        value=payload.get("equity_value"),
        equity_value=payload.get("equity_value"),
        equity_value_low=payload.get("equity_value_low"),
        equity_value_high=payload.get("equity_value_high"),
        value_basis="equity_value",
        value_low=payload.get("equity_value_low"),
        value_high=payload.get("equity_value_high"),
        method_key="adjusted_nav",
        label=payload["label"],
        available=payload["available"],
        unavailable_reason=payload.get("unavailable_reason"),
        details=details,
    )
