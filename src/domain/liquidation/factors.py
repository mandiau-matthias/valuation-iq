"""Recovery factors for orderly + forced liquidation scenarios.

Single source of truth for the per-asset-class recovery rates the
liquidation engine applies. The factors mirror the academic defaults
in Pratt & Niculita (2008) and Hitchner (2017) and match the dormant
``LIQUIDATION_FACTORS`` table in ``asset_based_engine.py``.

These constants are deliberately shared with the engine via the same
numbers — the engine remains the implementation, and this module is
the public contract that downstream callers (method wrapper, tests,
report templates) depend on. NACE-mapped sector overrides are out of
scope for the MVP; a future Delphi integration would replace the flat
factors below with a per-NACE lookup.
"""

from decimal import Decimal
from typing import Mapping

# ----------------------------------------------------------------------
# Orderly Liquidation — assets sold over a 6–12 month wind-down.
# Factors >0.5 reflect that the seller has time to find buyers and is
# not forced to accept fire-sale prices.
# ----------------------------------------------------------------------
ORDERLY_FACTORS: Mapping[str, Decimal] = {
    "cash": Decimal("1.00"),
    "accounts_receivable": Decimal("0.85"),
    "inventory": Decimal("0.65"),
    "equipment": Decimal("0.50"),
    "vehicles": Decimal("0.60"),
    "real_estate": Decimal("0.90"),
    "intangibles": Decimal("0.20"),
    "other_assets": Decimal("0.50"),
}

# ----------------------------------------------------------------------
# Forced Liquidation — immediate auction, distressed sale.
# Recovery rates are roughly half the orderly figures for non-cash
# items, reflecting the distress discount buyers demand.
# ----------------------------------------------------------------------
FORCED_FACTORS: Mapping[str, Decimal] = {
    "cash": Decimal("1.00"),
    "accounts_receivable": Decimal("0.60"),
    "inventory": Decimal("0.35"),
    "equipment": Decimal("0.25"),
    "vehicles": Decimal("0.40"),
    "real_estate": Decimal("0.70"),
    "intangibles": Decimal("0.05"),
    "other_assets": Decimal("0.25"),
}

# Liquidation costs as a fraction of adjusted asset value.
# Orderly winddowns absorb broker, legal, and runway costs; forced sales
# pay auction fees + accelerated wind-down overhead.
LIQUIDATION_COST_PCT_ORDERLY: Decimal = Decimal("0.05")
LIQUIDATION_COST_PCT_FORCED: Decimal = Decimal("0.10")

LIQUIDATION_SOURCES: tuple[str, ...] = (
    "Pratt & Niculita (2008) Valuing a Business",
    "Hitchner (2017) Financial Valuation",
)
