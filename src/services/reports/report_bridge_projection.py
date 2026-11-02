"""Present committed bridge facts without replacing unavailable amounts by zero."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from src.api.schemas.stateless_response_schemas import CalculateResponse
from src.domain.financial_arithmetic import decimal_number

from .report_context_types import ReportMap


def optional_decimal(value: object, field: str) -> Decimal | None:
    return None if value is None else decimal_number(value, field)


def display_amount(value: Decimal | None) -> float | None:
    """Legacy presentation projection; the sealed monetary fact remains unchanged."""
    return None if value is None else float(value)


@dataclass(frozen=True)
class ReportBridge:
    debt: Decimal | None
    cash: Decimal | None
    net_debt: Decimal | None
    available: bool

    def projection(self) -> ReportMap:
        net_debt = self.net_debt
        return {
            "total_debt": display_amount(self.debt),
            "cash_balance": display_amount(self.cash),
            "net_debt": display_amount(net_debt),
            "has_net_debt_adjustment": net_debt is not None and net_debt != 0,
            "bridge_net_debt_amount": (
                display_amount(abs(net_debt)) if net_debt is not None else None
            ),
            "bridge_net_debt_operator": (
                ("+" if net_debt < 0 else "−") if net_debt is not None else None
            ),
            "bridge_uses_net_cash_label": net_debt is not None and net_debt < 0,
            "show_ev_equity_bridge": self.available,
            "show_enterprise_to_equity_bridge": self.available,
        }


def report_bridge(result: CalculateResponse) -> ReportBridge:
    metrics = result.financial_metrics or {}
    debt = optional_decimal(metrics.get("total_debt"), "total debt")
    cash = optional_decimal(metrics.get("cash"), "cash")
    explicit_net_debt = optional_decimal(metrics.get("net_debt"), "net debt")
    # A supplied aggregate does not establish the missing component facts.
    net_debt = (
        (explicit_net_debt if explicit_net_debt is not None else debt - cash)
        if debt is not None and cash is not None
        else None
    )
    available = net_debt is not None and all(
        amount is not None
        for amount in (
            result.enterprise_value_low,
            result.enterprise_value_mid,
            result.enterprise_value_high,
            result.equity_value_low,
            result.equity_value_mid,
            result.equity_value_high,
        )
    )
    return ReportBridge(debt=debt, cash=cash, net_debt=net_debt, available=available)
