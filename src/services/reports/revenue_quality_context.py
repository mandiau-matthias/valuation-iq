"""Revenue-quality report context for valuation inputs.

This converts Venus' adaptive revenue-quality inputs into auditable report
fields. The calculation model may consume the same raw keys for calibration,
but the report needs an explicit disclosure so buyer/readiness sections do not
silently depend on hidden UI inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional

from src.utils.adaptive_input_helpers import (
    get_business_context,
    get_business_context_percent,
    get_contract_backlog_override,
    get_customer_concentration_amount_override,
    get_customer_concentration_override,
    get_direct_percent_override,
    get_recurring_revenue_amount_override,
    get_recurring_revenue_override,
)

JsonMap = dict[str, object]


@dataclass(frozen=True)
class _RevenueQualitySnapshot:
    revenue: Optional[Decimal]
    recurring_pct: Optional[Decimal]
    recurring_amount: Optional[Decimal]
    recurring_source: str
    top_client_pct: Optional[Decimal]
    top_client_amount: Optional[Decimal]
    top_client_source: str
    backlog_amount: Optional[Decimal]
    backlog_months: Optional[Decimal]


def _positive_decimal(value: object) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _float_or_none(value: Optional[Decimal]) -> Optional[float]:
    return float(value) if value is not None else None


def _amount_from_pct(
    pct: Optional[Decimal], latest_revenue: Optional[Decimal]
) -> Optional[Decimal]:
    if pct is None or pct <= 0 or latest_revenue is None or latest_revenue <= 0:
        return None
    return pct * latest_revenue


def _pct_from_amount(
    amount: Optional[Decimal], latest_revenue: Optional[Decimal]
) -> Optional[Decimal]:
    if amount is None or amount <= 0 or latest_revenue is None or latest_revenue <= 0:
        return None
    return min(max(amount / latest_revenue, Decimal("0")), Decimal("1"))


def _label(locale: str, nl: str, en: str, fr: str | None = None) -> str:
    loc = str(locale).lower()
    if loc.startswith("fr"):
        return fr if fr is not None else en
    return en if loc.startswith("en") else nl


def _positive_business_context_percent(context: dict[str, object], key: str) -> Optional[Decimal]:
    value = get_business_context_percent(context, key)
    return value if value is not None and value > 0 else None


def _positive_direct_percent(request: object, key: str) -> Optional[Decimal]:
    value = get_direct_percent_override(request, key)
    return value if value is not None and value > 0 else None


def _positive_direct_recurring_pct(request: object) -> Optional[Decimal]:
    value = getattr(request, "recurring_revenue_percentage", None)
    parsed = _positive_decimal(value)
    if parsed is None:
        return None
    if parsed > Decimal("1"):
        parsed = parsed / Decimal("100")
    return parsed if parsed > 0 else None


def _positive_override(value: Optional[Decimal]) -> Optional[Decimal]:
    return value if value is not None and value > 0 else None


def _resolved_amount(
    explicit_amount: Optional[Decimal],
    pct: Optional[Decimal],
    revenue: Optional[Decimal],
) -> Optional[Decimal]:
    return explicit_amount if explicit_amount is not None else _amount_from_pct(pct, revenue)


def _backlog_months(
    backlog_amount: Optional[Decimal],
    revenue: Optional[Decimal],
) -> Optional[Decimal]:
    if backlog_amount is None or revenue is None:
        return None
    return (backlog_amount / revenue) * Decimal("12")


def _recurring_source(
    *,
    explicit_amount: Optional[Decimal],
    context_pct: Optional[Decimal],
    direct_adaptive_pct: Optional[Decimal],
    direct_recurring_pct: Optional[Decimal],
) -> str:
    if explicit_amount is not None:
        return "rev_recurring_amount"
    if context_pct is not None or direct_adaptive_pct is not None:
        return "rev_recurring_pct"
    if direct_recurring_pct is not None:
        return "recurring_revenue_percentage"
    return "rev_recurring_pct"


def _revenue_quality_snapshot(
    *,
    request: object,
    latest_revenue: object,
) -> _RevenueQualitySnapshot:
    revenue = _positive_decimal(latest_revenue)
    business_context = get_business_context(request)

    recurring_pct = _positive_override(get_recurring_revenue_override(request))
    top_client_pct = _positive_override(get_customer_concentration_override(request))
    backlog_amount = _positive_override(get_contract_backlog_override(request))
    recurring_amount_input = _positive_override(get_recurring_revenue_amount_override(request))
    top_client_amount_input = _positive_override(
        get_customer_concentration_amount_override(request)
    )

    context_recurring_pct = _positive_business_context_percent(
        business_context, "rev_recurring_pct"
    )
    direct_adaptive_recurring_pct = _positive_direct_percent(request, "rev_recurring_pct")
    direct_recurring_pct = _positive_direct_recurring_pct(request)

    recurring_pct = recurring_pct or _pct_from_amount(recurring_amount_input, revenue)
    top_client_pct = top_client_pct or _pct_from_amount(top_client_amount_input, revenue)
    recurring_amount = _resolved_amount(recurring_amount_input, recurring_pct, revenue)
    top_client_amount = _resolved_amount(top_client_amount_input, top_client_pct, revenue)

    return _RevenueQualitySnapshot(
        revenue=revenue,
        recurring_pct=recurring_pct,
        recurring_amount=recurring_amount,
        recurring_source=_recurring_source(
            explicit_amount=recurring_amount_input,
            context_pct=context_recurring_pct,
            direct_adaptive_pct=direct_adaptive_recurring_pct,
            direct_recurring_pct=direct_recurring_pct,
        ),
        top_client_pct=top_client_pct,
        top_client_amount=top_client_amount,
        top_client_source=(
            "rev_top_client_amount"
            if top_client_amount_input is not None
            else "rev_top_client_concentration_pct"
        ),
        backlog_amount=backlog_amount,
        backlog_months=_backlog_months(backlog_amount, revenue),
    )


def _pct_to_display(pct: Optional[Decimal]) -> Optional[Decimal]:
    return pct * Decimal("100") if pct is not None else None


def _recurring_row(snapshot: _RevenueQualitySnapshot, locale: str) -> JsonMap | None:
    if snapshot.recurring_pct is None and snapshot.recurring_amount is None:
        return None
    return {
        "id": "recurring_revenue",
        "label": _label(
            locale,
            "Terugkerende omzet",
            "Recurring revenue",
            "Chiffre d'affaires récurrent",
        ),
        "amount_eur": _float_or_none(snapshot.recurring_amount),
        "ratio_pct": _float_or_none(_pct_to_display(snapshot.recurring_pct)),
        "source": snapshot.recurring_source,
    }


def _top_client_row(snapshot: _RevenueQualitySnapshot, locale: str) -> JsonMap | None:
    if snapshot.top_client_pct is None and snapshot.top_client_amount is None:
        return None
    return {
        "id": "top_client_concentration",
        "label": _label(
            locale,
            "Omzet top-3 klanten",
            "Top-3 client revenue",
            "Chiffre d'affaires des 3 premiers clients",
        ),
        "amount_eur": _float_or_none(snapshot.top_client_amount),
        "ratio_pct": _float_or_none(_pct_to_display(snapshot.top_client_pct)),
        "source": snapshot.top_client_source,
    }


def _backlog_row(snapshot: _RevenueQualitySnapshot, locale: str) -> JsonMap | None:
    if snapshot.backlog_amount is None:
        return None
    return {
        "id": "contracted_backlog",
        "label": _label(
            locale,
            "Gecontracteerde backlog",
            "Contracted backlog",
            "Carnet de commandes contracté",
        ),
        "amount_eur": _float_or_none(snapshot.backlog_amount),
        "months": _float_or_none(snapshot.backlog_months),
        "source": "rev_contract_backlog",
    }


def _summary_rows(snapshot: _RevenueQualitySnapshot, locale: str) -> list[JsonMap]:
    rows = [
        _recurring_row(snapshot, locale),
        _top_client_row(snapshot, locale),
        _backlog_row(snapshot, locale),
    ]
    return [row for row in rows if row is not None]


def build_revenue_quality_context(
    *,
    request: object | None,
    latest_revenue: object,
    locale: str = "nl",
) -> JsonMap:
    """Build report context for recurring revenue, concentration and backlog."""
    if request is None:
        return {"has_revenue_quality_inputs": False, "revenue_quality_summary_rows": []}

    snapshot = _revenue_quality_snapshot(request=request, latest_revenue=latest_revenue)
    rows = _summary_rows(snapshot, locale)

    return {
        "has_revenue_quality_inputs": bool(rows),
        "revenue_quality_latest_revenue_eur": _float_or_none(snapshot.revenue),
        "revenue_quality_recurring_amount_eur": _float_or_none(snapshot.recurring_amount),
        "revenue_quality_recurring_pct": _float_or_none(_pct_to_display(snapshot.recurring_pct)),
        "revenue_quality_top_client_amount_eur": _float_or_none(snapshot.top_client_amount),
        "revenue_quality_top_client_concentration_pct": _float_or_none(
            _pct_to_display(snapshot.top_client_pct)
        ),
        "revenue_quality_contract_backlog_eur": _float_or_none(snapshot.backlog_amount),
        "revenue_quality_backlog_months": _float_or_none(snapshot.backlog_months),
        "revenue_quality_summary_rows": rows,
    }
