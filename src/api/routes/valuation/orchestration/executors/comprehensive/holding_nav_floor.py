"""Equity NAV floor for the ambiguous head-office / holding class.

NACE 70.10 and a bare 'holding' / 'holding_company' tag are ambiguous between a
pure holding (valued on NAV) and an operating management/service company (valued
on earnings) — see `is_ambiguous_head_office_activity`. The methodology determiner
routes such an entity to ASSET_BASED only when book equity ≥ 5× EBITDA, and to
operating multiples otherwise. That binary route is fragile at the threshold and
when the equity data is thin.

This module adds the missing downside anchor: when an ambiguous head-office entity
is valued on an EARNINGS methodology (multiples / hybrid / DCF), its equity band is
floored at book NAV (total_assets − total_liabilities) — exactly the equity-level
floor the REAL_ESTATE_YIELD path already applies ("a buyer of the shares will not
pay less than the entity's book net assets"). A genuine holding that sat just under
the net-asset-dominance line, or whose EBITDA tripped a thin multiple, can no longer
print below its net assets.

The function is a no-op for every other entity and for methodologies that are
already NAV-based, so its blast radius is provably limited to the 70.10 / holding
class valued on earnings.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping, Optional, Tuple

from src.domain.asset_based_support import (
    book_nav_equity_floor,
    is_ambiguous_head_office_activity,
)

from .methodology_determiner import _extract_activity_code

# Methodologies that are already balance-sheet / NAV led — flooring them at NAV
# would be redundant (ASSET_BASED *is* the NAV; REAL_ESTATE_YIELD already floors
# equity at book NAV; LIQUIDATION is its own premise).
_NAV_FLOOR_EXEMPT_METHODOLOGIES = frozenset({"ASSET_BASED", "REAL_ESTATE_YIELD", "LIQUIDATION"})


def _balance_sheet_from_request(request: Any) -> Optional[Mapping[str, object]]:
    current_year_data = getattr(request, "current_year_data", None)
    if current_year_data is None:
        return None
    return {
        "total_assets": getattr(current_year_data, "total_assets", None),
        "current_assets": getattr(current_year_data, "current_assets", None),
        "cash": getattr(current_year_data, "cash", None),
        "accounts_receivable": getattr(current_year_data, "accounts_receivable", None),
        "inventory": getattr(current_year_data, "inventory", None),
        "total_liabilities": getattr(current_year_data, "total_liabilities", None),
        "current_liabilities": getattr(current_year_data, "current_liabilities", None),
        "total_debt": getattr(current_year_data, "total_debt", None),
        "total_equity": getattr(current_year_data, "total_equity", None),
    }


def _to_decimal(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return None


def apply_ambiguous_holding_nav_floor(
    *,
    request: Any,
    methodology: Optional[str],
    equity_value_low: Any,
    equity_value_mid: Any,
    equity_value_high: Any,
) -> Tuple[Any, Any, Any, Optional[dict]]:
    """Floor an ambiguous head-office / holding entity's equity band at book NAV.

    Returns ``(low, mid, high, meta)``. The first three are the (possibly floored)
    equity legs; ``meta`` is ``None`` when no floor was applied, otherwise a small
    dict describing the floor for transparent reporting. Pure and side-effect free.
    """
    token = (methodology or "").strip().upper()
    if token in _NAV_FLOOR_EXEMPT_METHODOLOGIES:
        return equity_value_low, equity_value_mid, equity_value_high, None

    activity_code = _extract_activity_code(request) or None
    industry = getattr(request, "industry", None)
    if not is_ambiguous_head_office_activity(activity_code, industry):
        return equity_value_low, equity_value_mid, equity_value_high, None

    nav_floor = book_nav_equity_floor(_balance_sheet_from_request(request))
    if nav_floor is None:
        return equity_value_low, equity_value_mid, equity_value_high, None

    floored: dict[str, Any] = {}
    applied = {"low": False, "mid": False, "high": False}
    for leg, value in (
        ("low", equity_value_low),
        ("mid", equity_value_mid),
        ("high", equity_value_high),
    ):
        current = _to_decimal(value)
        if current is not None and current < nav_floor:
            floored[leg] = nav_floor
            applied[leg] = True
        else:
            floored[leg] = value

    if not any(applied.values()):
        return equity_value_low, equity_value_mid, equity_value_high, None

    meta = {
        "book_nav": float(nav_floor),
        "floor_level": "equity",
        "methodology_floored": token,
        "floor_applied": applied,
        "rationale": (
            "Equity floored at book NAV (total assets − total liabilities): a "
            "head-office / holding entity valued on operating earnings cannot be "
            "worth less than its net assets to a share buyer."
        ),
    }
    return floored["low"], floored["mid"], floored["high"], meta
