"""Balance-sheet payload projection for stateless valuation routes."""

from __future__ import annotations

from src.api.schemas.stateless_api import YearDataStateless


def build_balance_sheet_payload(year_data: YearDataStateless) -> dict[str, object]:
    """Project a YearDataInput onto the balance_sheet dict the engine consumes.

    Phase 1 (liquidation): forwards the 12-class asset breakdown +
    retained_earnings whenever the request supplies them. Each field
    uses ``getattr`` because legacy payloads (older tests, older Hermes
    pipelines) may emit a ``YearDataInput`` shape without these
    attributes — defaulting to None preserves backwards compatibility.
    """
    payload: dict[str, object] = {
        "total_assets": year_data.total_assets,
        "current_assets": year_data.current_assets,
        "cash": year_data.cash,
        "accounts_receivable": year_data.accounts_receivable,
        "accounts_payable": year_data.accounts_payable,
        "inventory": year_data.inventory,
        "total_liabilities": year_data.total_liabilities,
        "current_liabilities": year_data.current_liabilities,
        "short_term_debt": year_data.short_term_debt,
        "total_debt": year_data.total_debt,
        "total_equity": year_data.total_equity,
    }
    # Phase 1 — 12-class asset breakdown + retained earnings (Z'' X2).
    for field in (
        "other_receivables",
        "inventory_finished",
        "inventory_wip",
        "inventory_raw",
        "land",
        "buildings",
        "machinery_equipment",
        "vehicles",
        "it_equipment",
        "intangibles",
        "investments",
        "other_tangible",
        "retained_earnings",
        "depreciation",
        "amortization",
        "ebit",
    ):
        value = getattr(year_data, field, None)
        if value is not None:
            payload[field] = value
    return payload
