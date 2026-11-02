"""
Equity range normalization — single source of truth for the
``low <= mid <= high`` invariant on the canonical valuation band.

Background
----------
The Step 11 synthesis is the canonical source of (low, mid, high). Multiple
downstream stages (multiples_executor, value_extractor, the final validator,
PDF aggregator) historically each implemented their own ad-hoc repair when
the band drifted, with conflicting strategies:

* "swap and rebuild from mid ±20%" — silently invents bounds.
* "median sort" — silently rewrites the central estimate (the mid).
* "raise 422" — kills the whole valuation.

These all violate the same principle: **mid is the user's economic answer.**
The bounds describe how confident we are in it. When the two disagree, the
honest fix is to widen the uncertainty, never to move the answer.

Policy
------
Bound-widening (``low' = min(low, mid)``, ``high' = max(high, mid)``):

* preserves the canonical mid bit-for-bit,
* always restores ordering for any finite triple,
* communicates "the central estimate sits at the edge of the reported band"
  rather than papering over the divergence.

Every layer that mutates the band must call into this module so the
invariant is enforced consistently. Single source of truth, no duplicated
repair logic.
"""

from decimal import Decimal
from typing import Any, Dict, Tuple, Union

from src.utils.decimal_helpers import to_decimal

# Nested mirrors of the canonical band. When the parent band is widened,
# these mirrors must be updated in lockstep or downstream consumers will
# read stale values.
NESTED_EQUITY_RANGE_CONTAINERS = ("multiples_valuation", "dcf_valuation")

NestableMoney = Union[str, int, float, Decimal]


def normalize_equity_bounds_to_contain_mid(
    low: NestableMoney,
    mid: NestableMoney,
    high: NestableMoney,
) -> Tuple[Decimal, Decimal]:
    """Return ``(low', high')`` such that ``low' <= mid <= high'``.

    Strategy: ``low' = min(low, mid)`` and ``high' = max(high, mid)``.

    The mid is *never* moved by this function — that is its central
    contract. If you need a function that adjusts mid into [low, high],
    add a different helper; do not change this one.
    """
    low_d = to_decimal(low)
    mid_d = to_decimal(mid)
    high_d = to_decimal(high)
    return min(low_d, mid_d), max(high_d, mid_d)


def coerce_equity_range_triple(
    low: NestableMoney,
    mid: NestableMoney,
    high: NestableMoney,
) -> Tuple[Decimal, Decimal, Decimal, bool]:
    """Coerce ``(low, mid, high)`` to ``Decimal`` and widen if mid is outside.

    Returns ``(low', mid', high', bounds_widened)`` with ``mid' == mid``.

    ``bounds_widened`` is ``True`` iff the input was unordered. Callers
    should log this at WARNING with structured context so a non-zero rate
    in production is visible — it indicates an upstream synthesis bug.
    """
    low_d = to_decimal(low)
    mid_d = to_decimal(mid)
    high_d = to_decimal(high)

    if low_d <= mid_d <= high_d:
        return low_d, mid_d, high_d, False

    low_d, high_d = normalize_equity_bounds_to_contain_mid(low_d, mid_d, high_d)
    if not (low_d <= mid_d <= high_d):
        # Should be mathematically unreachable — the only ways this can
        # fail are NaN/Infinity in ``mid``, which to_decimal already
        # rejects. Surface as a real bug if it ever happens.
        raise ValueError(
            "Equity range invariant failed after widening "
            f"(low={low_d}, mid={mid_d}, high={high_d})"
        )
    return low_d, mid_d, high_d, True


def sync_nested_equity_range_bounds(parent: Dict[str, Any]) -> None:
    """Normalize each method's own range without copying the blended headline.

    DCF and market multiples are independent components, not mirrors of a
    hybrid result. Copying the parent into them destroys the audit trail and
    changes the component values used by subsequent render/replay operations.
    """
    for key in NESTED_EQUITY_RANGE_CONTAINERS:
        nested = parent.get(key)
        if not isinstance(nested, dict):
            continue
        low = nested.get("equity_value_low")
        mid = nested.get("equity_value_mid", nested.get("equity_value"))
        high = nested.get("equity_value_high")
        if low is None or mid is None or high is None:
            continue
        low, _, high, _ = coerce_equity_range_triple(low, mid, high)
        nested["equity_value_low"] = low
        nested["equity_value_high"] = high
