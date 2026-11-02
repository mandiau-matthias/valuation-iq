"""One-time completion-account inputs for the stateless EV/equity bridge."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from src.utils.decimal_helpers import safe_decimal_or_zero


def _optional_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


@dataclass(frozen=True)
class CompletionAccountBridge:
    reported_cash: Decimal | None
    restricted_cash: Decimal | None
    available_cash: Decimal | None
    financial_debt: Decimal | None
    lease_liabilities: Decimal | None
    debt_like_items: Decimal | None
    normalized_nwc_target: Decimal | None
    total_debt_like: Decimal | None
    bridge_cash: Decimal
    bridge_total_debt: Decimal
    unresolved_fields: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "reported_cash": self.reported_cash,
            "restricted_cash": self.restricted_cash,
            "available_cash": self.available_cash,
            "financial_debt": self.financial_debt,
            "lease_liabilities": self.lease_liabilities,
            "debt_like_items": self.debt_like_items,
            "normalized_nwc_target": self.normalized_nwc_target,
            "total_debt_like": self.total_debt_like,
            "completion_accounts_complete": not self.unresolved_fields,
            "completion_account_unresolved_fields": list(self.unresolved_fields),
            "equity_bridge_is_illustrative": bool(self.unresolved_fields),
        }


def completion_account_bridge(request: object) -> CompletionAccountBridge:
    current = getattr(request, "current_year")
    reported_cash = _optional_decimal(getattr(current, "cash", None))
    financial_debt = _optional_decimal(getattr(current, "total_debt", None))
    restricted_cash = _optional_decimal(getattr(request, "restricted_cash", None))
    lease_liabilities = _optional_decimal(getattr(request, "lease_liabilities", None))
    debt_like_items = _optional_decimal(getattr(request, "debt_like_items", None))
    normalized_nwc_target = _optional_decimal(
        getattr(request, "normalized_nwc_target", None)
    )
    unresolved = tuple(
        name
        for name, value in (
            ("cash", reported_cash),
            ("financial_debt", financial_debt),
            ("restricted_cash", restricted_cash),
            ("lease_liabilities", lease_liabilities),
            ("debt_like_items", debt_like_items),
            ("normalized_nwc_target", normalized_nwc_target),
        )
        if value is None
    )
    available_cash = (
        reported_cash - restricted_cash
        if reported_cash is not None and restricted_cash is not None
        else None
    )
    total_debt_like = (
        financial_debt + lease_liabilities + debt_like_items
        if financial_debt is not None
        and lease_liabilities is not None
        and debt_like_items is not None
        else None
    )
    # The engine can still show an expressly illustrative bridge from the
    # known components. Crucially, missing fields remain null in the outward
    # evidence payload; they are never relabelled as observed zeroes.
    bridge_cash = safe_decimal_or_zero(reported_cash) - safe_decimal_or_zero(restricted_cash)
    bridge_total_debt = (
        safe_decimal_or_zero(financial_debt)
        + safe_decimal_or_zero(lease_liabilities)
        + safe_decimal_or_zero(debt_like_items)
    )
    return CompletionAccountBridge(
        reported_cash=reported_cash,
        restricted_cash=restricted_cash,
        available_cash=available_cash,
        financial_debt=financial_debt,
        lease_liabilities=lease_liabilities,
        debt_like_items=debt_like_items,
        normalized_nwc_target=normalized_nwc_target,
        total_debt_like=total_debt_like,
        bridge_cash=bridge_cash,
        bridge_total_debt=bridge_total_debt,
        unresolved_fields=unresolved,
    )


def explicit_nwc_normalization(request: object) -> dict[str, object] | None:
    target = getattr(request, "normalized_nwc_target", None)
    if target is None:
        return None
    current = getattr(request, "current_year")
    target_nwc = safe_decimal_or_zero(target)

    receivables = getattr(current, "accounts_receivable", None)
    inventory = getattr(current, "inventory", None)
    payables = getattr(current, "accounts_payable", None)
    if receivables is not None and inventory is not None and payables is not None:
        actual_nwc = (
            safe_decimal_or_zero(receivables)
            + safe_decimal_or_zero(inventory)
            - safe_decimal_or_zero(payables)
        )
        basis = "receivables_plus_inventory_minus_payables"
    else:
        current_assets = getattr(current, "current_assets", None)
        current_liabilities = getattr(current, "current_liabilities", None)
        cash = getattr(current, "cash", None)
        short_term_debt = getattr(current, "short_term_debt", None)
        if None in (current_assets, current_liabilities, cash, short_term_debt):
            raise ValueError(
                "normalized_nwc_target requires either receivables/inventory/payables "
                "or complete current-assets/current-liabilities/cash/short-term-debt inputs"
            )
        actual_nwc = (
            safe_decimal_or_zero(current_assets)
            - safe_decimal_or_zero(cash)
            - safe_decimal_or_zero(current_liabilities)
            + safe_decimal_or_zero(short_term_debt)
        )
        basis = "operating_current_assets_minus_operating_current_liabilities"

    surplus = actual_nwc - target_nwc
    revenue = safe_decimal_or_zero(getattr(current, "revenue", None))
    return {
        "available": True,
        "source": "advisor_supported_absolute_target",
        "basis": basis,
        "target_nwc_absolute": target_nwc,
        "actual_nwc": actual_nwc,
        "surplus_deficit": surplus,
        "is_surplus": surplus >= 0,
        "latest_revenue": revenue,
        "target_nwc_pct": (
            target_nwc / revenue * Decimal("100") if revenue > 0 else None
        ),
        "actual_nwc_pct": (
            actual_nwc / revenue * Decimal("100") if revenue > 0 else None
        ),
    }
