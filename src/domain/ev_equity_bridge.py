"""Domain EV-to-equity bridge calculations.

The bridge is used by valuation engines before report rendering, so keep it
free of service/template dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Mapping, Sequence

from src.domain.nwc_normalizer import NWCNormalizer
from src.utils.decimal_helpers import to_decimal

BALANCE_SHEET_FIELDS = (
    "total_debt",
    "cash",
    "current_assets",
    "current_liabilities",
    "short_term_debt",
    "total_assets",
    "total_liabilities",
)


@dataclass(frozen=True)
class BalanceSheetBridgeAdjustment:
    """Signed balance-sheet adjustment applied after net debt."""

    label: str
    amount: Decimal
    type: str = "add"
    category: str = "other"
    signed_amount: Decimal = Decimal("0")
    id: str = ""
    description: str | None = None
    account_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "amount": self.amount,
            "type": self.type,
            "category": self.category,
            "signed_amount": self.signed_amount,
            "description": self.description,
            "account_code": self.account_code,
        }


@dataclass(frozen=True)
class EvEquityBridgeResult:
    """Auditable result of converting enterprise value to equity value."""

    enterprise_value: Decimal
    equity_value: Decimal
    total_debt: Decimal
    cash: Decimal
    net_debt: Decimal
    nwc_surplus_deficit: Decimal = Decimal("0")
    nwc_normalization: dict[str, Any] = field(default_factory=dict)
    nwc_status: str = "not_assessed"
    nwc_not_assessed_reason: str | None = None
    balance_sheet_adjustments: list[dict[str, Any]] = field(default_factory=list)
    balance_sheet_adjustments_total: Decimal = Decimal("0")
    balance_sheet_available: bool = False
    equity_value_before_floor: Decimal = Decimal("0")
    insolvency_shortfall: Decimal = Decimal("0")
    unresolved_fields: tuple[str, ...] = ()
    formula: str = (
        "Equity Value = Enterprise Value - Net Debt + NWC Surplus/Deficit "
        "+ Balance Sheet Adjustments"
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "ev_equity_bridge.v2",
            "equity_value_before_floor": self.equity_value_before_floor,
            "insolvency_shortfall": self.insolvency_shortfall,
            "unresolved_fields": list(self.unresolved_fields),
            "equity_bridge_is_illustrative": bool(self.unresolved_fields),
            "reported_cash": None if "cash" in self.unresolved_fields else self.cash,
            "reported_total_debt": (
                None if "total_debt" in self.unresolved_fields else self.total_debt
            ),
            "enterprise_value": self.enterprise_value,
            "equity_value": self.equity_value,
            "total_debt": self.total_debt,
            "cash": self.cash,
            "net_debt": self.net_debt,
            "nwc_surplus_deficit": self.nwc_surplus_deficit,
            "nwc_normalization": self.nwc_normalization,
            "nwc_status": self.nwc_status,
            "nwc_not_assessed_reason": self.nwc_not_assessed_reason,
            "balance_sheet_adjustments": self.balance_sheet_adjustments,
            "balance_sheet_adjustments_total": self.balance_sheet_adjustments_total,
            "balance_sheet_available": self.balance_sheet_available,
            "formula": self.formula,
        }


def calculate_ev_equity_bridge(
    *,
    financial_data: Any,
    enterprise_value: Any,
    balance_sheet_adjustments: Sequence[Any] | None = None,
) -> EvEquityBridgeResult:
    """Convert EV to equity value with NWC and surplus/non-operating adjustments."""
    current_year = getattr(financial_data, "current_year", None)
    if enterprise_value is None:
        raise ValueError("enterprise_value is required for an EV-to-equity bridge")
    enterprise_value_decimal = _safe_decimal(enterprise_value)
    unresolved_fields = tuple(
        name for name in ("cash", "total_debt") if _attr(current_year, name) is None
    )
    total_debt = _safe_decimal(_attr(current_year, "total_debt"))
    cash = _safe_decimal(_attr(current_year, "cash"))
    net_debt = total_debt - cash

    adjustments = _normalize_balance_sheet_adjustments(balance_sheet_adjustments or [])
    balance_sheet_adjustments_total = sum(
        (item.signed_amount for item in adjustments),
        Decimal("0"),
    )

    nwc_normalization: dict[str, Any] = {}
    nwc_surplus_deficit = Decimal("0")
    nwc_status = "not_assessed"
    nwc_not_assessed_reason: str | None = None

    try:
        normalized = NWCNormalizer().normalize(
            list(getattr(financial_data, "historical_years", []) or []),
            current_year,
        )
    except Exception:
        normalized = None

    if normalized is not None:
        nwc_status = "assessed"
        nwc_surplus_deficit = _safe_decimal(normalized.surplus_deficit)
        nwc_normalization = normalized.to_dict()
    elif _has_any_balance_sheet_data(financial_data):
        nwc_not_assessed_reason = "insufficient working-capital history"
    else:
        nwc_not_assessed_reason = "not assessed - no balance sheet"

    equity_value = (
        enterprise_value_decimal - net_debt + nwc_surplus_deficit + balance_sheet_adjustments_total
    )

    return EvEquityBridgeResult(
        enterprise_value=enterprise_value_decimal,
        equity_value=max(equity_value, Decimal("0")),
        equity_value_before_floor=equity_value,
        insolvency_shortfall=max(-equity_value, Decimal("0")),
        unresolved_fields=unresolved_fields,
        total_debt=total_debt,
        cash=cash,
        net_debt=net_debt,
        nwc_surplus_deficit=nwc_surplus_deficit,
        nwc_normalization=nwc_normalization,
        nwc_status=nwc_status,
        nwc_not_assessed_reason=nwc_not_assessed_reason,
        balance_sheet_adjustments=[item.to_dict() for item in adjustments],
        balance_sheet_adjustments_total=balance_sheet_adjustments_total,
        balance_sheet_available=_has_any_balance_sheet_data(financial_data) or bool(adjustments),
    )


def _normalize_balance_sheet_adjustments(
    adjustments: Sequence[Any],
) -> list[BalanceSheetBridgeAdjustment]:
    normalized: list[BalanceSheetBridgeAdjustment] = []
    by_id: dict[str, BalanceSheetBridgeAdjustment] = {}
    for raw in adjustments:
        if _attr(raw, "amount") is None:
            raise ValueError("balance-sheet adjustment amount is required")
        amount = _safe_decimal(_attr(raw, "amount"))
        if amount < 0:
            raise ValueError(
                "balance-sheet adjustment amount must be unsigned; use type for direction"
            )
        if amount == Decimal("0"):
            continue
        adjustment_type = str(_attr(raw, "type") or "add").lower()
        if adjustment_type not in {"add", "subtract", "deduct", "minus"}:
            raise ValueError("unknown balance-sheet adjustment direction")
        signed_amount = -amount if adjustment_type in {"subtract", "deduct", "minus"} else amount
        normalized.append(
            BalanceSheetBridgeAdjustment(
                id=str(_attr(raw, "id") or ""),
                label=str(
                    _attr(raw, "label") or _attr(raw, "description") or "Balance sheet adjustment"
                ),
                amount=amount,
                type=adjustment_type,
                category=str(_attr(raw, "category") or "other"),
                signed_amount=signed_amount,
                description=_optional_str(_attr(raw, "description")),
                account_code=_optional_str(_attr(raw, "account_code")),
            )
        )
    unique: list[BalanceSheetBridgeAdjustment] = []
    for item in normalized:
        if item.id and item.id in by_id:
            if by_id[item.id] != item:
                raise ValueError("conflicting revisions of a balance-sheet adjustment")
            continue
        if item.id:
            by_id[item.id] = item
        unique.append(item)
    return unique


def _has_any_balance_sheet_data(financial_data: Any) -> bool:
    years = [getattr(financial_data, "current_year", None)]
    years.extend(list(getattr(financial_data, "historical_years", []) or []))
    return any(
        _attr(year, field_name) is not None for year in years for field_name in BALANCE_SHEET_FIELDS
    )


def _safe_decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    try:
        result = to_decimal(value)
    except Exception as exc:
        raise ValueError("bridge inputs must be finite decimal amounts") from exc
    if not result.is_finite():
        raise ValueError("bridge inputs must be finite decimal amounts")
    return result


def _attr(obj: Any, key: str) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key)
    return getattr(obj, key, None)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
